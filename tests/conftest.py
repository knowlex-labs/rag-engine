"""Pytest configuration and shared fixtures"""
import json
import pytest
from typing import Dict, List, Any
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_chunks() -> List[Dict[str, Any]]:
    with open(FIXTURES_DIR / "mock_chunks.json") as f:
        return json.load(f)["resnick_halliday_chapter_5"]


@pytest.fixture
def expected_responses() -> Dict[str, Any]:
    with open(FIXTURES_DIR / "expected_responses.json") as f:
        return json.load(f)


@pytest.fixture
def test_queries() -> Dict[str, List[str]]:
    with open(FIXTURES_DIR / "test_queries.json") as f:
        return json.load(f)


@pytest.fixture
def qdrant_test_collection_name() -> str:
    return "test_resnick_halliday_chapter_5"


@pytest.fixture
def test_book_metadata() -> Dict[str, Any]:
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
    return {
        "min_relevance_score": 0.7,
        "min_confidence": 0.8,
        "min_rerank_score": 0.6
    }


@pytest.fixture(scope="session")
def test_config() -> Dict[str, Any]:
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
    import random
    random.seed(42)
    return [random.uniform(-1, 1) for _ in range(1024)]
