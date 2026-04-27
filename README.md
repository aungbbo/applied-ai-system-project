# PawPal+ — AI-Powered Pet Care Assistant

**PawPal+** is a Streamlit-powered pet care planning assistant that combines deterministic scheduling algorithms with a Retrieval-Augmented Generation (RAG) Q&A system. It helps busy pet owners organise daily care tasks across multiple pets and get instant, knowledge-grounded answers to pet care questions — all in one interface.

---

## Original Project (Modules 1–3)

PawPal+ started as a pure scheduling tool built in Modules 1–3. Its original goals were to help pet owners manage multi-pet care tasks by priority, preferred time, and available daily minutes. The core system implemented greedy time-budget packing, conflict detection across overlapping task windows, and automatic daily/weekly task recurrence — all without any AI components. The Module 2 version was a fully functional, tested Python application with a clean Streamlit UI, 23 passing unit tests, and well-defined OOP architecture.

---

## What's New — RAG Integration

This version extends PawPal+ with an **"Ask PawPal"** feature: a natural language Q&A assistant grounded in a pet care knowledge base. Users can ask questions like *"How often should I feed my large dog?"* and receive factual, sourced answers without leaving the scheduling app.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│                  Streamlit UI (app.py)           │
│  Sections 1–5: Scheduling  │  Section 6: Ask    │
└────────────────────────────┬────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  rag_engine.py  │
                    │                 │
                    │  build_index()  │◄── knowledge_base/*.txt
                    │  query()        │
                    └──┬──────────┬──┘
                       │          │
           ┌───────────▼──┐  ┌────▼──────────────┐
           │  ChromaDB    │  │ Groq API           │
           │  (local      │  │ llama-3.1-8b-      │
           │  vector DB)  │  │ instant            │
           └───────────┬──┘  └────────────────────┘
                       │
           ┌───────────▼──────────────┐
           │  sentence-transformers   │
           │  all-MiniLM-L6-v2        │
           │  (local embeddings)      │
           └──────────────────────────┘
```

**How it works:**
1. On first question, `build_index()` reads and chunks the `.txt` knowledge base files, embeds them locally using `all-MiniLM-L6-v2`, and stores the vectors in ChromaDB on disk.
2. When a user asks a question, it is embedded using the same local model.
3. ChromaDB finds the top 3 most semantically similar chunks.
4. The retrieved chunks are sent as context to Groq's LLaMA 3.1 model, which generates a grounded, natural-language answer.
5. The answer and source file names are displayed in the UI.

The scheduling system (`pawpal_system.py`) operates entirely independently of the RAG pipeline — it is deterministic and requires no AI services.

---

## Project Structure

```
applied-ai-system-project/
├── app.py                  # Streamlit UI (Sections 1–6)
├── pawpal_system.py        # Core classes: Task, Pet, Owner, Scheduler
├── rag_engine.py           # RAG pipeline: indexing + querying
├── main.py                 # Terminal demo script
├── knowledge_base/
│   ├── exercise_guide.txt
│   ├── feeding_schedules.txt
│   └── grooming_frequency.txt
├── chroma_db/              # Auto-generated vector store (git-ignored)
├── tests/
│   └── test_pawpal.py      # 23 pytest unit tests
├── .env                    # API keys (git-ignored)
├── .gitignore
├── requirements.txt
├── uml.md
└── README.md
```

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd applied-ai-system-project
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API keys

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_groq_api_key_here
HF_TOKEN=your_huggingface_token_here
```

- **Groq API key** — free at [console.groq.com](https://console.groq.com)
- **HuggingFace token** — free at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) (needed to download the embedding model on first run)

### 5. Run the app

```bash
streamlit run app.py
```

> **First run note:** The first question asked in Section 6 will trigger a one-time download of the `all-MiniLM-L6-v2` embedding model (~90 MB) and index the knowledge base. Subsequent questions are fast (~2–4 seconds).

### 6. Run the tests

```bash
python -m pytest tests/test_pawpal.py -v
```

---

## Sample Interactions

### Example 1 — Feeding schedule question

**Input:** *"How many times a day should I feed my large dog?"*

**PawPal says:**
> Large dogs should be fed 2 meals per day as adults. Avoid feeding one large meal per day, as it may increase the risk of bloat (gastric torsion). Allow rest time after meals before vigorous activity.

**Sources used:** `feeding_schedules.txt`

---

### Example 2 — Grooming frequency question

**Input:** *"How often should I brush a small dog?"*

**PawPal says:**
> Small dogs should be brushed 3–5 times per week, and daily if they have a long coat. Bathing is recommended every 3–4 weeks, and nails should be trimmed every 3–4 weeks as well.

**Sources used:** `grooming_frequency.txt`

---

### Example 3 — Exercise question

**Input:** *"How much exercise does a medium-sized dog need each day?"*

**PawPal says:**
> Medium-sized dogs typically need 60–90 minutes of exercise per day. Good activities include brisk walks, jogging, hiking, agility training, and playtime in a yard or park. Many medium dogs are working or sporting breeds that also benefit from mental challenges alongside physical exercise.

**Sources used:** `exercise_guide.txt`

---

## Design Decisions

### Why RAG instead of fine-tuning?
RAG is far more practical for a project of this scope. Fine-tuning an LLM requires large datasets, significant compute, and ongoing maintenance. RAG lets us plug in a curated knowledge base of `.txt` files and get grounded, trustworthy answers immediately — with full control over what the model can and cannot say.

### Why ChromaDB?
ChromaDB runs entirely locally with no external account or service required. It persists the vector index to disk so re-indexing is skipped on every restart. For a project with a small knowledge base (3–10 files), it is the simplest possible vector store with zero infrastructure overhead.

### Why sentence-transformers for embeddings instead of an API?
Using `all-MiniLM-L6-v2` locally means embeddings are free, private, and fast after the one-time download. It avoids a second paid API dependency alongside Groq and keeps the embedding step offline.

### Why Groq?
Groq provides a free-tier LLM API with very fast inference (often under 2 seconds). It was chosen as a practical alternative to OpenAI after the OpenAI free tier was discontinued.

### Trade-offs
- The knowledge base is currently dog-only. Cats and other species are supported by the scheduling system but not yet by the RAG Q&A.
- ChromaDB's local persistence means the vector index is machine-specific and not portable across deployments without re-indexing.
- The RAG system is instructed to only answer from retrieved context, which means it will decline questions outside the knowledge base rather than hallucinating.

---

## Testing Summary

The project uses three complementary reliability methods: automated unit tests, confidence scoring, and logging.

### Running all tests

```bash
# Scheduling system tests (no API required)
python -m pytest tests/test_pawpal.py -v

# RAG retrieval tests (no API required — runs locally)
python -m pytest tests/test_rag.py -v

# All tests together
python -m pytest tests/ -v
```

### Scheduling system tests — 23 tests, all passing

| Test class | Tests | What it verifies |
|---|---|---|
| `TestTaskCompletion` | 4 | `mark_complete()` and `reset()` toggle correctly; idempotent calls are safe |
| `TestPetTaskAddition` | 4 | Adding tasks increases count; duplicate titles are rejected |
| `TestSortByTime` | 4 | Tasks sort in `HH:MM` order; untimed tasks come last |
| `TestRecurrence` | 6 | Daily/weekly tasks auto-renew; `as_needed` tasks stay done |
| `TestConflictDetection` | 5 | Overlapping times flagged; adjacent times pass; three-way overlap produces exactly 3 warnings |

### RAG retrieval tests — 7 tests, all passing

Located in `tests/test_rag.py`. These tests verify the retrieval step is working correctly without calling the Groq API — making them fast, free, and reproducible.

| Test | What it verifies |
|---|---|
| `test_feeding_question_retrieves_feeding_source` | Feeding question → retrieves `feeding_schedules.txt` |
| `test_exercise_question_retrieves_exercise_source` | Exercise question → retrieves `exercise_guide.txt` |
| `test_grooming_question_retrieves_grooming_source` | Grooming question → retrieves `grooming_frequency.txt` |
| `test_retrieval_returns_correct_number_of_chunks` | Returns 1–3 chunks per query |
| `test_confidence_scores_are_in_valid_range` | All scores are between 0.0 and 1.0 |
| `test_top_confidence_score_is_reasonable` | Relevant questions score ≥ 0.30 |
| `test_sources_are_nonempty_strings` | Source names are valid `.txt` filenames |

### Confidence scoring

Every answer in the UI displays a retrieval confidence score (0–100%) derived from the ChromaDB vector similarity distance. Scores are labelled 🟢 High (≥70%), 🟡 Medium (≥40%), or 🔴 Low (<40%). This gives users and reviewers a transparent signal of how well the retrieved context matched the question.

Example from real usage:
> *"how many times should i feed my small dog?"* — best match: **40%** 🟡, average: **23%**

### Logging

All queries, retrieval results, confidence scores, and errors are automatically written to `rag_log.txt`. Example log entries from real usage:

```
2026-04-26 21:03:03 | INFO | New question received: 'what should i feed my big dog?'
2026-04-26 21:03:07 | INFO | Retrieved 3 chunks | sources: ['feeding_schedules.txt'] | scores: [0.21, 0.15, 0.0]
2026-04-26 21:03:07 | INFO | Answer generated successfully (315 chars)

2026-04-26 21:03:36 | INFO | New question received: 'how many times should i feed my small dog?'
2026-04-26 21:03:36 | INFO | Retrieved 3 chunks | sources: ['feeding_schedules.txt'] | scores: [0.4, 0.28, 0.0]
2026-04-26 21:03:36 | INFO | Answer generated successfully (149 chars)
```

### What worked well
- The scheduling core (sorting, conflict detection, greedy packing) is robust and fully covered by unit tests.
- The RAG pipeline correctly retrieves the right source document for topic-specific questions in all 3 retrieval tests.
- Groq's `llama-3.1-8b-instant` produces concise, grounded answers in under 2 seconds after the first run.
- Confidence scoring makes it easy to spot when a question is outside the knowledge base scope.

### What didn't work / challenges
- The original `llama3-8b-8192` Groq model was decommissioned mid-development and had to be updated to `llama-3.1-8b-instant`.
- HuggingFace rate-limits unauthenticated downloads, causing the first-run embedding model download to stall without an `HF_TOKEN`.
- The RAG system has no memory across questions — each question is answered independently with no conversation history.

### Gaps remaining
- No end-to-end UI tests for the Streamlit interface.
- Knowledge base does not yet cover cats, medical conditions, or enrichment activities.
- Confidence scores for some questions are low (< 0.3), indicating the knowledge base needs more content to handle edge-case queries reliably.

---

## Reflection

Building PawPal+ with RAG taught me that the hardest part of an AI system is not the model — it's the data pipeline around it. Deciding how to chunk documents, what embedding model to use, and how to craft a system prompt that keeps answers grounded all required more thought than the LLM call itself.

I also learned that real-world AI development involves constant adaptation: models get deprecated, APIs change pricing, and rate limits appear unexpectedly. The ability to swap components (OpenAI → Groq, API embeddings → local embeddings) without rewriting the entire system was only possible because `rag_engine.py` was kept modular and separate from the UI.

The biggest insight was understanding the difference between what an LLM *knows* from training and what it *retrieves* from context. RAG makes AI systems more trustworthy and controllable — the model can only answer from what you give it, which is exactly what a pet care app needs.
