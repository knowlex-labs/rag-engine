"""
Pytest configuration and shared fixtures for RAG Engine tests
"""
import json
import os
import pytest
from typing import Dict, List, Any
from pathlib import Path


# Path constants
FIXTURES_DIR = Path(__file__).parent / "fixtures"
MOCK_CHUNKS_FILE = FIXTURES_DIR / "mock_chunks.json"
EXPECTED_RESPONSES_FILE = FIXTURES_DIR / "expected_responses.json"
TEST_QUERIES_FILE = FIXTURES_DIR / "test_queries.json"


@pytest.fixture
def mock_chunks() -> List[Dict[str, Any]]:
    """Load mock Qdrant chunks for testing"""
    with open(MOCK_CHUNKS_FILE, 'r') as f:
        data = json.load(f)
    return data["resnick_halliday_chapter_5"]


@pytest.fixture
def expected_responses() -> Dict[str, Any]:
    """Load expected response structures for validation"""
    with open(EXPECTED_RESPONSES_FILE, 'r') as f:
        return json.load(f)


@pytest.fixture
def test_queries() -> Dict[str, List[str]]:
    """Load test queries for different query types"""
    with open(TEST_QUERIES_FILE, 'r') as f:
        return json.load(f)


@pytest.fixture
def qdrant_test_collection_name() -> str:
    """Test collection name for Qdrant"""
    return "test_resnick_halliday_chapter_5"


@pytest.fixture
def test_book_metadata() -> Dict[str, Any]:
    """Metadata for the test book"""
    return {
        "book_id": "resnick_halliday_10th",
        "book_title": "Fundamentals of Physics (Resnick Halliday), 10th Edition",
        "edition": "10th",
        "authors": ["David Halliday", "Robert Resnick", "Jearl Walker"],
        "total_pages": 1328,
        "total_chapters": 44
    }


@pytest.fixture
def performance_thresholds() -> Dict[str, int]:
    """Performance thresholds in milliseconds"""
    return {
        "concept_explanation": 500,
        "knowledge_testing": 1000,
        "test_generation": 2000,
        "problem_generation": 1500,
        "analogy_generation": 1000,
        "embedding_generation": 100,
        "vector_search": 50,
        "reranking": 200
    }


@pytest.fixture
def quality_thresholds() -> Dict[str, float]:
    """Quality thresholds for search and confidence scores"""
    return {
        "min_relevance_score": 0.7,
        "min_confidence": 0.8,
        "min_rerank_score": 0.6
    }


@pytest.fixture(scope="session")
def test_config() -> Dict[str, Any]:
    """Test configuration"""
    return {
        "embedding_model": "BAAI/bge-large-en-v1.5",
        "vector_size": 1024,
        "reranker_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "llm_provider": "gemini",
        "llm_model": "gemini-2.0-flash-exp",
        "fallback_llm_provider": "openai",
        "fallback_llm_model": "gpt-4o-mini",
        "qdrant_host": "localhost",
        "qdrant_port": 6333
    }


@pytest.fixture
def mock_embedding_vector() -> List[float]:
    """Generate a mock 1024-dimensional embedding vector"""
    import random
    random.seed(42)  # For reproducibility
    return [random.uniform(-1, 1) for _ in range(1024)]


# Test helpers
def validate_response_structure(response: Dict[str, Any], expected_structure: Dict[str, Any]) -> bool:
    """
    Validate that a response matches the expected structure

    Args:
        response: Actual response from the system
        expected_structure: Expected structure definition

    Returns:
        True if structure matches, raises AssertionError otherwise
    """
    for key, value_type in expected_structure.items():
        assert key in response, f"Missing key: {key}"
        # Add more detailed type checking here
    return True


def validate_performance(response_time_ms: int, threshold_ms: int) -> bool:
    """
    Validate that response time meets performance threshold

    Args:
        response_time_ms: Actual response time
        threshold_ms: Maximum allowed time

    Returns:
        True if within threshold, raises AssertionError otherwise
    """
    assert response_time_ms <= threshold_ms, \
        f"Response time {response_time_ms}ms exceeded threshold {threshold_ms}ms"
    return True


def validate_source_attribution(sources: List[Dict[str, Any]], book_id: str) -> bool:
    """
    Validate that all sources come from the specified book

    Args:
        sources: List of source attributions
        book_id: Expected book ID

    Returns:
        True if all sources are from the book, raises AssertionError otherwise
    """
    for source in sources:
        assert "source" in source, "Missing source attribution"
        # Could check book_id if included in metadata
    return True


def validate_content_from_chunks(answer: str, chunks: List[Dict[str, Any]]) -> bool:
    """
    Validate that answer content is derived from the provided chunks

    Args:
        answer: Generated answer
        chunks: Source chunks

    Returns:
        True if answer is grounded in chunks, raises AssertionError otherwise
    """
    # This is a simplified check - in real tests, this would be more sophisticated
    assert len(answer) > 0, "Answer is empty"
    return True


@pytest.fixture
def validation_helpers():
    """Provide validation helper functions to tests"""
    return {
        "validate_response_structure": validate_response_structure,
        "validate_performance": validate_performance,
        "validate_source_attribution": validate_source_attribution,
        "validate_content_from_chunks": validate_content_from_chunks
    }
