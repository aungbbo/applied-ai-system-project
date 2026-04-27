from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from groq import Groq
from sentence_transformers import SentenceTransformer

load_dotenv()

KB_DIR = Path(__file__).parent / "knowledge_base"
CHROMA_DIR = Path(__file__).parent / "chroma_db"
LOG_FILE = Path(__file__).parent / "rag_log.txt"
COLLECTION_NAME = "pawpal_kb"
GROQ_MODEL = "llama-3.1-8b-instant"
TOP_K = 3

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Local embedding model — downloaded once (~90 MB), then cached
_embedder: SentenceTransformer | None = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _log.info("Loading embedding model: all-MiniLM-L6-v2")
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        _log.info("Embedding model loaded successfully")
    return _embedder


def _groq_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        _log.error("GROQ_API_KEY not found in environment")
        raise EnvironmentError("GROQ_API_KEY not found. Check your .env file.")
    return Groq(api_key=api_key)


def _collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(COLLECTION_NAME)


def _chunk_text(text: str, chunk_size: int = 200, overlap: int = 40) -> list[str]:
    """Split text into overlapping word-count chunks."""
    words = text.split()
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks


def _distance_to_score(distance: float) -> float:
    """Convert a ChromaDB L2 distance to a 0–1 confidence score.

    ChromaDB returns L2 distances where 0 = perfect match.
    We convert to a confidence score where 1.0 = perfect match.
    """
    return round(max(0.0, 1.0 - distance), 2)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_index(force: bool = False) -> int:
    """Load .txt files from knowledge_base/, embed locally, and store in ChromaDB.

    Skips indexing if the collection already has documents unless *force* is True.
    Returns the number of chunks indexed.
    """
    col = _collection()

    if col.count() > 0 and not force:
        _log.info("Index already exists (%d chunks) — skipping rebuild", col.count())
        return col.count()

    if force:
        existing = col.get()["ids"]
        if existing:
            col.delete(ids=existing)
            _log.info("Force rebuild: cleared %d existing chunks", len(existing))

    documents: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []

    for txt_file in sorted(KB_DIR.glob("*.txt")):
        text = txt_file.read_text(encoding="utf-8")
        for i, chunk in enumerate(_chunk_text(text)):
            documents.append(chunk)
            metadatas.append({"source": txt_file.name, "chunk_index": i})
            ids.append(f"{txt_file.stem}_{i}")

    if not documents:
        _log.warning("No .txt files found in knowledge_base/")
        return 0

    embedder = _get_embedder()
    embeddings = embedder.encode(documents, show_progress_bar=False).tolist()
    col.add(documents=documents, embeddings=embeddings, metadatas=metadatas, ids=ids)

    _log.info("Index built: %d chunks from %d files", len(documents),
              len(list(KB_DIR.glob("*.txt"))))
    return len(documents)


def retrieve(question: str) -> tuple[list[str], list[str], list[float]]:
    """Retrieve the top-k chunks most relevant to *question*.

    Returns:
        chunks     — list of retrieved text passages
        sources    — deduplicated list of source filenames
        scores     — confidence scores (0–1) for each chunk, higher = better match
    """
    build_index()

    col = _collection()
    embedder = _get_embedder()

    q_embedding = embedder.encode([question], show_progress_bar=False).tolist()[0]

    results = col.query(
        query_embeddings=[q_embedding],
        n_results=min(TOP_K, col.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks = results["documents"][0]
    metas = results["metadatas"][0]
    distances = results["distances"][0]

    sources = list(dict.fromkeys(m["source"] for m in metas))
    scores = [_distance_to_score(d) for d in distances]

    _log.info(
        "Retrieved %d chunks for question: %r | sources: %s | scores: %s",
        len(chunks), question, sources, scores,
    )
    return chunks, sources, scores


def query(question: str) -> tuple[str, list[str], list[float]]:
    """Answer *question* using retrieved knowledge-base chunks via Groq LLM.

    Returns:
        answer   — natural-language response from the LLM
        sources  — deduplicated list of source filenames used as context
        scores   — confidence scores (0–1) for each retrieved chunk
    """
    _log.info("New question received: %r", question)

    try:
        chunks, sources, scores = retrieve(question)
    except Exception as exc:
        _log.error("Retrieval failed: %s", exc)
        raise

    context = "\n\n---\n\n".join(chunks)

    system_prompt = (
        "You are PawPal, a friendly and knowledgeable pet care assistant. "
        "Answer the user's question using ONLY the context provided below. "
        "Be concise, specific, and practical. "
        "If the context does not contain enough information to answer, "
        "say so honestly and suggest the owner consult a veterinarian."
    )
    user_prompt = f"Context:\n{context}\n\nQuestion: {question}"

    try:
        client = _groq_client()
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        answer = completion.choices[0].message.content or ""
        _log.info("Answer generated successfully (%d chars)", len(answer))
    except Exception as exc:
        _log.error("LLM call failed: %s", exc)
        raise

    return answer, sources, scores
