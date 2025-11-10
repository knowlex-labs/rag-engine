# RAG Engine Test Suite - Test-Driven Development

## 🎯 Overview

This test suite defines the **expected behavior** of a sophisticated book indexing and querying system for **Resnick Halliday Physics (10th Edition)**.

We're using **Test-Driven Development (TDD)**: tests are written FIRST to define success criteria, then we implement to make tests pass.

---

## 📁 Test Structure

```
tests/
├── conftest.py              # Shared fixtures and test configuration
├── fixtures/                # Test data and expected outputs
│   ├── mock_chunks.json     # Mock Qdrant data (5 chunks from Chapter 5)
│   ├── expected_responses.json  # Expected response structures
│   └── test_queries.json    # Test queries for each type
├── unit/                    # Unit tests for individual components
│   └── test_chunking.py     # Tests for PDF extraction, chunking, metadata
├── integration/             # Integration tests for combined components
│   └── test_query_pipeline.py   # Tests for full pipeline flow
└── e2e/                     # End-to-end tests for user-facing features
    ├── test_concept_explanation.py  # "What is Newton's second law?"
    ├── test_knowledge_testing.py    # "Give me questions from the book"
    ├── test_problem_generation.py   # "Give me 2 big problems to solve"
    └── test_analogies.py            # "Give me real-world analogies"
```

---

## 🧪 Test Categories

### 1️⃣ **E2E Tests** (User-Facing Features)

These tests define what users will experience:

#### **Concept Explanation** (`test_concept_explanation.py`)
- **Query**: "What is Newton's second law of motion?"
- **Expected Output**:
  - Concise explanation (200-500 chars)
  - Contains: force, mass, acceleration, F=ma
  - Sources from Chapter 5, Section 5.4, Page 92
  - Response time < 500ms
  - Confidence > 0.8

#### **Knowledge Testing** (`test_knowledge_testing.py`)
- **Query**: "Give me questions from the book to test my knowledge"
- **Expected Output**:
  - 3-5 questions from actual sample problems
  - Each has correct answer and source citation
  - Mix of numerical and conceptual questions
  - Response time < 1000ms

#### **Test Generation** (`test_knowledge_testing.py`)
- **Query**: "Generate a test of 10 questions. Include diagrams, equations, MCQ and short answer"
- **Expected Output**:
  - Exactly 10 questions
  - Mix: MCQ (≥3), Multiple Correct (≥2), Short Answer (≥2)
  - Some reference diagrams (≥1)
  - Some include equations (≥3)
  - Response time < 2000ms

#### **Problem Generation** (`test_problem_generation.py`)
- **Query**: "Give me 2 big problem statements to solve"
- **Expected Output**:
  - Exactly 2 challenging, multi-step problems
  - Based on book concepts but NOT direct copies
  - Includes: given data, what to find, hints, estimated time
  - Response time < 1500ms

#### **Analogy Generation** (`test_analogies.py`)
- **Query**: "Give me real-world analogies to understand Newton's second law better"
- **Expected Output**:
  - 3-5 relatable analogies
  - Clear concept mapping (force → X, mass → Y, acceleration → Z)
  - Based on book's application sections
  - Response time < 1000ms

---

### 2️⃣ **Unit Tests** (Component-Level)

#### **Chunking Logic** (`test_chunking.py`)

Tests the core document processing:

- **PDF Extraction**
  - Extract text from PDF pages
  - Preserve structure (headers, paragraphs)
  - Handle equations and special characters

- **Structure Detection**
  - Detect chapter headers (e.g., "CHAPTER 5 FORCE AND MOTION - I")
  - Detect section headers (e.g., "5.4 Newton's Second Law")
  - Identify sample problems
  - Build hierarchical tree

- **Semantic Chunking**
  - Chunk at paragraph boundaries (not mid-sentence)
  - Respect token limits (≤512 tokens)
  - Implement overlap (50 tokens)
  - Keep equations intact
  - Keep sample problems together

- **Metadata Generation**
  - Extract chapter, section, page numbers
  - Detect chunk type (concept_explanation, sample_problem, etc.)
  - Extract equations from text
  - Identify key terms

---

### 3️⃣ **Integration Tests** (Pipeline-Level)

#### **Query Pipeline** (`test_query_pipeline.py`)

Tests complete flow:

```
Query → Embedding → Vector Search → Reranking → LLM → Response
```

- **Components Tested**:
  - BGE embedding generation (1024-dim vectors)
  - Qdrant operations (create, upsert, search)
  - CrossEncoder reranking
  - Gemini LLM with OpenAI fallback
  - End-to-end latency

- **Indexing Pipeline**:
  - PDF → Text → Structure → Chunks → Embeddings → Qdrant
  - Batch processing
  - Incremental indexing

- **Advanced Features**:
  - Filtering (by chapter, chunk type)
  - Concurrent queries
  - Performance benchmarks

---

## ⚡ Performance Thresholds

All tests enforce strict performance requirements:

| Operation | Threshold | Rationale |
|-----------|-----------|-----------|
| **Concept Explanation** | < 500ms | User expects instant answers |
| **Knowledge Testing** | < 1000ms | Generating questions takes longer |
| **Test Generation** | < 2000ms | 10 questions with variety |
| **Problem Generation** | < 1500ms | Complex problem creation |
| **Analogy Generation** | < 1000ms | Multiple analogies |
| **Embedding (single)** | < 100ms | BGE on CPU |
| **Vector Search** | < 50ms | Qdrant HNSW index |
| **Reranking (20 items)** | < 200ms | CrossEncoder on CPU |

---

## 🎓 Quality Thresholds

Tests enforce minimum quality standards:

| Metric | Threshold | Meaning |
|--------|-----------|---------|
| **Relevance Score** | > 0.7 | Vector similarity |
| **Confidence** | > 0.8 | Overall confidence in answer |
| **Rerank Score** | > 0.6 | CrossEncoder score |

---

## 🔧 Running Tests

### Install Dependencies

```bash
pip install pytest pytest-asyncio pytest-mock
```

### Run All Tests

```bash
# From project root
pytest tests/ -v

# Run specific test category
pytest tests/e2e/ -v                    # E2E tests only
pytest tests/unit/ -v                   # Unit tests only
pytest tests/integration/ -v            # Integration tests only

# Run specific test file
pytest tests/e2e/test_concept_explanation.py -v

# Run specific test
pytest tests/e2e/test_concept_explanation.py::TestConceptExplanation::test_basic_concept_query -v
```

### Current Status

**All tests are currently SKIPPED** with `pytest.skip("Implementation pending")`.

This is intentional - these are **specification tests** that define what we need to build.

---

## 🏗️ Development Workflow (TDD)

### Step 1: Pick a Feature to Implement

Start with the simplest, most critical feature:

**Recommended First Feature**: Concept Explanation Query

### Step 2: Read the Test

```python
# tests/e2e/test_concept_explanation.py
def test_basic_concept_query(self, test_queries, performance_thresholds):
    """
    Test: User asks "What is Newton's second law of motion?"

    Expected:
    - Answer explains F=ma relationship
    - Sources from Chapter 5, Section 5.4
    - Contains key terms: force, mass, acceleration
    - Response time < 500ms
    - Confidence > 0.8
    """
```

This test tells you EXACTLY what success looks like.

### Step 3: Uncomment Test Assertions

Remove `pytest.skip()` and uncomment the assertions:

```python
def test_basic_concept_query(self, ...):
    query = "What is Newton's second law of motion?"

    # Act
    response = query_engine.query(query, query_type="concept_explanation")

    # Assert
    assert "answer" in response
    assert "force" in response["answer"].lower()
    assert response["metadata"]["response_time_ms"] < 500
    # ... more assertions
```

### Step 4: Run Test (It Will Fail)

```bash
pytest tests/e2e/test_concept_explanation.py::TestConceptExplanation::test_basic_concept_query -v
```

Expected: `ModuleNotFoundError: No module named 'query_engine'`

**This is good!** The test tells you what to build next.

### Step 5: Implement Just Enough to Pass

Create the minimum code to make the test pass:

```python
# src/book_indexing/query_engine.py
class QueryEngine:
    def query(self, query: str, query_type: str) -> dict:
        # TODO: Implement
        pass
```

### Step 6: Iterate

Keep running the test and implementing until it passes:

1. Test fails: `AttributeError: 'NoneType' object has no attribute 'lower'`
2. Implement: Return a dict with "answer" key
3. Test fails: `AssertionError: 'force' not in answer`
4. Implement: Add embedding → search → LLM pipeline
5. Test passes! ✅

### Step 7: Refactor

Once test passes, refactor code for clarity/performance.

### Step 8: Move to Next Test

Repeat for all tests.

---

## 📊 Test Coverage Goals

| Component | Target Coverage | Priority |
|-----------|-----------------|----------|
| **Chunking Logic** | 90% | High |
| **Query Pipeline** | 85% | High |
| **Indexing Pipeline** | 80% | Medium |
| **LLM Integration** | 70% | Medium |
| **Edge Cases** | 60% | Low |

---

## 🔍 Key Testing Principles

### 1. **Tests Define Behavior, Not Implementation**

❌ **Bad Test** (tests implementation):
```python
def test_uses_bge_embeddings():
    assert isinstance(embedder.model, SentenceTransformer)
```

✅ **Good Test** (tests behavior):
```python
def test_embedding_is_1024_dimensional():
    embedding = embedder.embed("test")
    assert len(embedding) == 1024
```

### 2. **Tests Should Be Independent**

Each test should:
- Set up its own data
- Not depend on other tests
- Clean up after itself

### 3. **Use Fixtures for Reusable Data**

```python
@pytest.fixture
def mock_chunks():
    """Load mock Qdrant chunks"""
    # Reused across many tests
```

### 4. **Test at Multiple Levels**

- **Unit**: Does chunking preserve sentence boundaries?
- **Integration**: Does embedding + search work together?
- **E2E**: Does the user get a good answer?

---

## 🎯 Next Steps

### Week 1: Mock Data & Basic Pipeline

1. ✅ Tests written (done!)
2. Create mock Qdrant collection with 5 chunks
3. Implement basic query pipeline:
   - Embedding generation
   - Vector search
   - Simple LLM call
4. Make `test_basic_concept_query` pass

### Week 2: Chunking & Indexing

1. Implement PDF extraction (pdfplumber)
2. Implement structure detection
3. Implement semantic chunking
4. Make unit tests in `test_chunking.py` pass

### Week 3: Advanced Features

1. Implement reranking
2. Implement all 5 query types
3. Make all E2E tests pass

### Week 4: Optimization & Polish

1. Performance optimization (hit <500ms target)
2. Error handling
3. Edge case tests
4. Documentation

---

## 📚 Additional Resources

### Fixture Data

- **mock_chunks.json**: 5 realistic chunks from Chapter 5, Section 5.4
- **expected_responses.json**: Detailed response structures for each query type
- **test_queries.json**: Example queries for each type

### Test Helpers

`conftest.py` provides:
- `validate_response_structure()`: Check response matches expected shape
- `validate_performance()`: Check latency thresholds
- `validate_source_attribution()`: Check citations are correct

---

## 🐛 Debugging Failed Tests

### Test fails: "response_time_ms exceeded threshold"

**Solution**: Optimize the bottleneck:
- Profile code to find slow component
- Use batch embedding
- Cache embeddings
- Stream LLM responses

### Test fails: "Confidence < 0.8"

**Solution**: Improve retrieval:
- Better chunking (more semantic coherence)
- Better reranking
- Verify Qdrant indexing worked

### Test fails: "Missing key in response"

**Solution**: Fix response structure:
- Check response matches expected schema
- Add missing fields

---

## 💡 Philosophy

**"Tests are not just validation - they are specifications."**

These tests document:
- What the system should do
- How fast it should be
- What quality is acceptable
- What edge cases to handle

When in doubt, read the tests. They tell you everything.

---

## 📞 Questions?

If unsure about:
- What a test expects → Read the docstring
- Why a test exists → Read the "Expected" section
- How to implement → Look at similar passing tests

Remember: **Tests first, code second.** Let the tests guide you.

---

**Good luck! 🚀**
