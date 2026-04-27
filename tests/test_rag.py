"""
RAG reliability tests for PawPal+.

These tests verify that the retrieval step returns the correct source
documents for known questions — without calling the Groq API.
All tests run locally using the sentence-transformers embedding model
and the ChromaDB index.
"""

import pytest
import rag_engine


@pytest.fixture(scope="module", autouse=True)
def ensure_index():
    """Build the ChromaDB index once before all tests in this module."""
    rag_engine.build_index()


class TestRetrieval:
    """Verify that known questions retrieve the correct knowledge-base files."""

    def test_feeding_question_retrieves_feeding_source(self):
        """A question about feeding schedules should retrieve feeding_schedules.txt."""
        _, sources, _ = rag_engine.retrieve("How many times a day should I feed my large dog?")
        assert "feeding_schedules.txt" in sources, (
            f"Expected feeding_schedules.txt in sources, got: {sources}"
        )

    def test_exercise_question_retrieves_exercise_source(self):
        """A question about exercise should retrieve exercise_guide.txt."""
        _, sources, _ = rag_engine.retrieve("How much exercise does a small dog need each day?")
        assert "exercise_guide.txt" in sources, (
            f"Expected exercise_guide.txt in sources, got: {sources}"
        )

    def test_grooming_question_retrieves_grooming_source(self):
        """A question about grooming should retrieve grooming_frequency.txt."""
        _, sources, _ = rag_engine.retrieve("How often should I brush a medium-sized dog?")
        assert "grooming_frequency.txt" in sources, (
            f"Expected grooming_frequency.txt in sources, got: {sources}"
        )

    def test_retrieval_returns_correct_number_of_chunks(self):
        """Retrieval should return exactly TOP_K chunks (or fewer if index is small)."""
        chunks, _, _ = rag_engine.retrieve("How do I take care of my dog?")
        assert 1 <= len(chunks) <= rag_engine.TOP_K, (
            f"Expected 1–{rag_engine.TOP_K} chunks, got {len(chunks)}"
        )

    def test_confidence_scores_are_in_valid_range(self):
        """All confidence scores should be between 0.0 and 1.0."""
        _, _, scores = rag_engine.retrieve("What should I feed my puppy?")
        for score in scores:
            assert 0.0 <= score <= 1.0, f"Score out of range: {score}"

    def test_top_confidence_score_is_reasonable(self):
        """A highly relevant question should return at least one score above 0.3."""
        _, _, scores = rag_engine.retrieve("How often should I feed my dog?")
        assert max(scores) >= 0.3, (
            f"Expected top score >= 0.3 for a relevant question, got {max(scores)}"
        )

    def test_sources_are_nonempty_strings(self):
        """All returned source names should be non-empty strings."""
        _, sources, _ = rag_engine.retrieve("Tell me about dog grooming.")
        assert all(isinstance(s, str) and s.endswith(".txt") for s in sources), (
            f"Unexpected source format: {sources}"
        )
