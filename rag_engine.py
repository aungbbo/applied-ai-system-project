from __future__ import annotations

import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from groq import Groq
from sentence_transformers import SentenceTransformer

load_dotenv()

KB_DIR = Path(__file__).parent / "knowledge_base"
CHROMA_DIR = Path(__file__).parent / "chroma_db"
COLLECTION_NAME = "pawpal_kb"
GROQ_MODEL = "llama-3.1-8b-instant"
TOP_K = 3

# Local embedding model — downloaded once (~90 MB), then cached
_embedder: SentenceTransformer | None = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


def _groq_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
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


def build_index(force: bool = False) -> int:
    """Load .txt files from knowledge_base/, embed locally, and store in ChromaDB.

    Skips indexing if the collection already has documents unless *force* is True.
    Returns the number of chunks indexed.
    """
    col = _collection()

    if col.count() > 0 and not force:
        return col.count()

    if force:
        existing = col.get()["ids"]
        if existing:
            col.delete(ids=existing)

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
        return 0

    embedder = _get_embedder()
    embeddings = embedder.encode(documents, show_progress_bar=False).tolist()

    col.add(documents=documents, embeddings=embeddings, metadatas=metadatas, ids=ids)
    return len(documents)


def query(question: str) -> tuple[str, list[str]]:
    """Answer *question* using retrieved knowledge-base chunks via Groq LLM.

    Returns a (answer, sources) tuple where *sources* is a deduplicated list
    of filenames that contributed context to the answer.
    """
    build_index()

    col = _collection()
    embedder = _get_embedder()

    q_embedding = embedder.encode([question], show_progress_bar=False).tolist()[0]

    results = col.query(
        query_embeddings=[q_embedding],
        n_results=min(TOP_K, col.count()),
        include=["documents", "metadatas"],
    )

    chunks = results["documents"][0]
    metas = results["metadatas"][0]
    sources = list(dict.fromkeys(m["source"] for m in metas))

    context = "\n\n---\n\n".join(chunks)

    system_prompt = (
        "You are PawPal, a friendly and knowledgeable pet care assistant. "
        "Answer the user's question using ONLY the context provided below. "
        "Be concise, specific, and practical. "
        "If the context does not contain enough information to answer, "
        "say so honestly and suggest the owner consult a veterinarian."
    )
    user_prompt = f"Context:\n{context}\n\nQuestion: {question}"

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
    return answer, sources
