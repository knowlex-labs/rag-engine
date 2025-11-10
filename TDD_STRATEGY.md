# Test-Driven Development Strategy for Book Indexing

## 🎯 Executive Summary

We've designed a **comprehensive test suite** that defines the complete behavior of a sophisticated RAG system for **Resnick Halliday Physics (10th Edition)**.

**Approach**: Top-down TDD - Tests define success, then we implement to make them pass.

---

## 📦 What We've Built

### **Test Suite Structure**

```
tests/
├── conftest.py                         # Shared fixtures, validation helpers
├── pytest.ini                          # Pytest configuration
├── requirements-test.txt               # Test dependencies
├── README.md                           # Comprehensive test documentation
│
├── fixtures/
│   ├── mock_chunks.json                # 5 realistic chunks from Chapter 5.4
│   ├── expected_responses.json         # Expected response structures
│   └── test_queries.json               # Test queries for each type
│
├── unit/
│   └── test_chunking.py                # 20+ tests for chunking logic
│
├── integration/
│   └── test_query_pipeline.py          # 15+ tests for full pipeline
│
└── e2e/
    ├── test_concept_explanation.py     # 8+ tests for concept queries
    ├── test_knowledge_testing.py       # 12+ tests for question extraction
    ├── test_problem_generation.py      # 10+ tests for problem creation
    └── test_analogies.py               # 9+ tests for analogy generation

**Total: 74+ test cases** covering every aspect of the system.
```

---

## 🔬 Test Coverage

### **1. End-to-End Tests (User Features)**

#### **Query Type: Concept Explanation**
```
User: "What is Newton's second law of motion?"

Expected Response:
{
  "answer": "Newton's second law states that the acceleration of an object...",
  "sources": [
    {
      "text": "5.4 NEWTON'S SECOND LAW\n\nThe acceleration...",
      "source": {
        "book": "Fundamentals of Physics (Resnick Halliday), 10th Edition",
        "chapter": "5. Force and Motion - I",
        "section": "5.4 Newton's Second Law",
        "page": 92
      },
      "relevance_score": 0.94
    }
  ],
  "metadata": {
    "response_time_ms": 342,
    "chunks_used": 2,
    "confidence": 0.92
  }
}
```

**Tests cover**:
- ✅ Answer contains key concepts (force, mass, acceleration, F=ma)
- ✅ Sources cite correct chapter/section/page
- ✅ Response time < 500ms
- ✅ Confidence > 0.8
- ✅ Multiple query phrasings return consistent answers
- ✅ Answers only from book (no hallucination)

---

#### **Query Type: Knowledge Testing**
```
User: "Give me questions from the book to test my knowledge"

Expected Response:
{
  "questions": [
    {
      "question": "A 2.0 kg block is pushed with 10 N. Find acceleration.",
      "type": "numerical",
      "correct_answer": "5.0 m/s²",
      "source": {
        "problem_id": "Sample Problem 5.2",
        "chapter": 5,
        "section": "5.4",
        "page": 94
      },
      "difficulty": "easy"
    }
  ],
  "metadata": {
    "total_questions": 3,
    "from_book": true
  }
}
```

**Tests cover**:
- ✅ Questions extracted from actual sample problems
- ✅ Correct answers provided
- ✅ Source attribution (Sample Problem X.X, Page Y)
- ✅ Mix of numerical and conceptual questions
- ✅ Difficulty levels assigned

---

#### **Query Type: Test Generation**
```
User: "Generate a test of 10 questions. Include diagrams, equations, MCQ and short answer."

Expected Response:
{
  "test": {
    "title": "Newton's Second Law Assessment",
    "total_questions": 10,
    "total_marks": 50,
    "questions": [
      {
        "id": 1,
        "type": "mcq",
        "question": "If the net force on an object doubles, what happens to acceleration?",
        "options": ["Halves", "Doubles", "Stays same", "Quadruples"],
        "correct_answers": ["Doubles"],
        "marks": 2,
        "has_equation": true,
        "equations": ["F = ma"]
      }
      // ... 9 more questions
    ]
  }
}
```

**Tests cover**:
- ✅ Exactly 10 questions
- ✅ Mix of types: MCQ (≥3), Multiple Correct (≥2), Short Answer (≥2)
- ✅ Includes diagrams (≥1)
- ✅ Includes equations (≥3)
- ✅ Balanced difficulty distribution
- ✅ Total marks calculation correct

---

#### **Query Type: Problem Generation**
```
User: "Give me 2 big problem statements to solve"

Expected Response:
{
  "problems": [
    {
      "id": 1,
      "title": "Multi-Force Acceleration Problem",
      "problem_statement": "A 5.0 kg object is acted upon by three forces...",
      "difficulty": "hard",
      "given_data": ["Mass: 5.0 kg", "Force 1: 10 N east", "Force 2: 8 N north"],
      "to_find": ["Net force", "Magnitude and direction of acceleration"],
      "hints": ["Use vector addition", "Components method"],
      "estimated_time_minutes": 20,
      "source": {
        "inspired_by": "Sample Problem 5.3",
        "chapter": 5
      }
    }
  ]
}
```

**Tests cover**:
- ✅ Problems are challenging and multi-step
- ✅ Not direct copies from book
- ✅ Clear structure (given, to find, hints)
- ✅ Difficulty levels
- ✅ Time estimates

---

#### **Query Type: Analogy Generation**
```
User: "Give me real-world analogies to understand Newton's second law better"

Expected Response:
{
  "analogies": [
    {
      "title": "Shopping Cart Analogy",
      "analogy": "Pushing a shopping cart demonstrates F=ma perfectly...",
      "mapping": {
        "force": "Your push on the cart handle",
        "mass": "Weight of items in cart",
        "acceleration": "How quickly cart speeds up"
      },
      "example_scenario": "An empty cart accelerates quickly with small push...",
      "why_it_works": "The relationship is identical to F=ma because..."
    }
  ]
}
```

**Tests cover**:
- ✅ Multiple analogies (3-5)
- ✅ Clear concept mapping
- ✅ Relatable scenarios
- ✅ Based on book's application sections
- ✅ Explains why analogy works

---

### **2. Unit Tests (Component Logic)**

#### **Chunking Logic Tests**

**PDF Extraction**:
- Extract text from PDF pages
- Preserve formatting and structure
- Handle equations and special characters

**Structure Detection**:
- Detect chapter headers: "CHAPTER 5 FORCE AND MOTION - I"
- Detect section headers: "5.4 Newton's Second Law"
- Identify sample problems: "Sample Problem 5.2"
- Build hierarchical tree

**Semantic Chunking**:
- Chunk at paragraph boundaries (no mid-sentence breaks)
- Respect token limits (≤512 tokens)
- Implement overlap (50 tokens at sentence boundary)
- Keep equations intact
- Keep sample problems together (problem + solution)

**Metadata Generation**:
- Extract chapter, section, page numbers
- Detect chunk type (concept_explanation, sample_problem, application, etc.)
- Extract equations from text
- Identify key terms
- Detect if chunk has diagrams/equations

---

### **3. Integration Tests (Pipeline Logic)**

**Query Pipeline Flow**:
```
Query → Embedding → Vector Search → Reranking → LLM → Response
  ↓        ↓            ↓              ↓         ↓        ↓
 50ms    100ms        50ms          150ms     200ms   550ms
```

**Tests**:
- BGE embedding generation (1024-dim vectors)
- Qdrant operations (create, upsert, search, filter)
- CrossEncoder reranking (top 50 → top 10)
- Gemini LLM with OpenAI fallback
- End-to-end latency breakdown
- Concurrent queries (10 simultaneous)

**Indexing Pipeline**:
- PDF → Text → Structure → Chunks → Embeddings → Qdrant
- Batch embedding (32 chunks at a time)
- Incremental indexing (add new chapters)
- Performance: 1000 pages in <15 minutes

---

## ⚡ Performance Requirements

All tests enforce strict performance thresholds:

| Operation | Target | Test Enforces |
|-----------|--------|---------------|
| **Concept Query** | <500ms | ✅ Assertion in test |
| **Knowledge Testing** | <1000ms | ✅ Assertion in test |
| **Test Generation** | <2000ms | ✅ Assertion in test |
| **Problem Generation** | <1500ms | ✅ Assertion in test |
| **Analogy Generation** | <1000ms | ✅ Assertion in test |
| **Embedding (single)** | <100ms | ✅ Assertion in test |
| **Vector Search** | <50ms | ✅ Assertion in test |
| **Reranking (20)** | <200ms | ✅ Assertion in test |
| **Indexing 1000 pages** | <15min | ✅ Assertion in test |

---

## 🎓 Quality Requirements

| Metric | Threshold | Test Enforces |
|--------|-----------|---------------|
| **Relevance Score** | >0.7 | ✅ Assertion in test |
| **Confidence** | >0.8 | ✅ Assertion in test |
| **Source Attribution** | 100% | ✅ Assertion in test |
| **Answer from Book** | 100% | ✅ Assertion in test |

---

## 🚀 Implementation Roadmap

### **Phase 1: Prove the Concept (Week 1)**

**Goal**: Make ONE query work end-to-end with mock data.

**Tasks**:
1. ✅ Tests written (DONE!)
2. Create mock Qdrant collection
3. Upload 5 mock chunks (from mock_chunks.json)
4. Implement basic query pipeline:
   ```python
   query → embedding → search → LLM → response
   ```
5. Make `test_basic_concept_query` pass

**Success Metric**:
```bash
pytest tests/e2e/test_concept_explanation.py::TestConceptExplanation::test_basic_concept_query
PASSED ✅
```

---

### **Phase 2: Real Chunking (Week 2)**

**Goal**: Extract and chunk actual PDF content.

**Tasks**:
1. Implement PDF text extraction (pdfplumber)
2. Implement structure detection (chapters, sections, problems)
3. Implement semantic chunking (paragraph-aware, token-limited)
4. Implement metadata generation
5. Extract Chapter 5 from Resnick Halliday PDF
6. Make unit tests in `test_chunking.py` pass

**Success Metric**:
```bash
pytest tests/unit/test_chunking.py
15 passed ✅
```

---

### **Phase 3: All Query Types (Week 3)**

**Goal**: Implement all 5 query types.

**Tasks**:
1. Concept Explanation ✅ (from Phase 1)
2. Knowledge Testing (extract questions from sample problems)
3. Test Generation (create 10-question tests)
4. Problem Generation (create challenging problems)
5. Analogy Generation (real-world analogies)
6. Make all E2E tests pass

**Success Metric**:
```bash
pytest tests/e2e/
40+ passed ✅
```

---

### **Phase 4: Optimization (Week 4)**

**Goal**: Hit all performance targets.

**Tasks**:
1. Optimize query pipeline (<500ms)
   - Batch embedding
   - Parallel reranking
   - Streaming LLM
2. Optimize indexing (<15min for 1000 pages)
   - Parallel PDF processing
   - Batch Qdrant upload
3. Make performance tests pass

**Success Metric**:
```bash
pytest tests/integration/test_query_pipeline.py::TestPerformanceBenchmarks
5 passed ✅
```

---

## 🛠️ How to Use These Tests

### **Step 1: Install Test Dependencies**

```bash
pip install -r requirements-test.txt
```

### **Step 2: Run Tests (They Will Skip)**

```bash
pytest tests/ -v
```

**Expected Output**:
```
tests/e2e/test_concept_explanation.py::test_basic_concept_query SKIPPED
tests/e2e/test_knowledge_testing.py::test_extract_questions_from_book SKIPPED
...
74 skipped
```

**This is normal!** Tests are skipped because implementation doesn't exist yet.

---

### **Step 3: Pick First Feature**

Start with: **Concept Explanation Query**

**File**: `tests/e2e/test_concept_explanation.py`
**Test**: `test_basic_concept_query`

---

### **Step 4: Read the Test**

```python
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
    query = "What is Newton's second law of motion?"

    # TODO: Uncomment this when implementing:
    # response = query_engine.query(query, query_type="concept_explanation")

    # Assert - What MUST be true:
    # assert "answer" in response
    # assert "force" in response["answer"].lower()
    # assert response["metadata"]["response_time_ms"] < 500

    pytest.skip("Implementation pending")
```

**The test tells you EXACTLY what to build.**

---

### **Step 5: Uncomment Test & Run**

Edit file:
```python
def test_basic_concept_query(self, ...):
    query = "What is Newton's second law of motion?"

    # Uncomment:
    response = query_engine.query(query, query_type="concept_explanation")

    # Uncomment assertions:
    assert "answer" in response
    assert "force" in response["answer"].lower()
    # ...

    # Remove skip:
    # pytest.skip("Implementation pending")
```

Run test:
```bash
pytest tests/e2e/test_concept_explanation.py::TestConceptExplanation::test_basic_concept_query -v
```

**Expected**: `ModuleNotFoundError: No module named 'query_engine'`

**Good!** The test is telling you what to build next.

---

### **Step 6: Implement Minimum Code**

Create file: `src/book_indexing/query_engine.py`

```python
class QueryEngine:
    def query(self, query: str, query_type: str) -> dict:
        return {
            "answer": "",
            "sources": [],
            "metadata": {
                "response_time_ms": 0,
                "confidence": 0.0
            }
        }
```

Run test again. It will fail differently:
```
AssertionError: assert 'force' in ''
```

**Good!** You're making progress. Keep iterating.

---

### **Step 7: Full Implementation**

Implement the complete pipeline:

```python
class QueryEngine:
    def __init__(self):
        self.embedder = EmbeddingClient()
        self.qdrant = QdrantRepository()
        self.reranker = Reranker()
        self.llm = LLMClient()

    def query(self, query: str, query_type: str) -> dict:
        start_time = time.time()

        # 1. Generate embedding
        query_embedding = self.embedder.generate_single_embedding(query)

        # 2. Vector search
        search_results = self.qdrant.search(
            collection_name="resnick_halliday",
            query_vector=query_embedding,
            limit=50
        )

        # 3. Rerank
        reranked = self.reranker.rerank(query, search_results)

        # 4. Generate answer
        context = self._assemble_context(reranked[:3])
        answer = self.llm.generate_answer(query, context)

        # 5. Format response
        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "answer": answer,
            "sources": self._format_sources(reranked[:3]),
            "metadata": {
                "response_time_ms": elapsed_ms,
                "chunks_used": 3,
                "confidence": reranked[0]["score"]
            }
        }
```

---

### **Step 8: Iterate Until Test Passes**

Run test repeatedly, fixing issues:

```bash
pytest tests/e2e/test_concept_explanation.py::TestConceptExplanation::test_basic_concept_query -v
```

**Iteration 1**: Fails on embedding
**Iteration 2**: Fails on Qdrant
**Iteration 3**: Fails on LLM
**Iteration 4**: Fails on performance (600ms, needs <500ms)
**Iteration 5**: **PASSES** ✅

---

### **Step 9: Move to Next Test**

Once `test_basic_concept_query` passes, move to:
- `test_concept_with_equation_emphasis`
- `test_concept_with_real_world_context`
- ... and so on

Repeat process for all 74 tests.

---

## 📊 Progress Tracking

Create a file `TEST_PROGRESS.md` to track:

```markdown
# Test Progress

## E2E Tests (40 tests)
- [x] test_basic_concept_query ✅
- [ ] test_concept_with_equation_emphasis
- [ ] test_concept_with_real_world_context
...

## Unit Tests (20 tests)
- [ ] test_extract_text_from_pdf_page
- [ ] test_detect_chapter_headers
...

## Integration Tests (14 tests)
- [ ] test_end_to_end_query_flow
...

**Total: 1 / 74 passed (1.4%)**
```

---

## 🎯 Success Criteria

**System is production-ready when:**

1. ✅ All 74 tests pass
2. ✅ All performance thresholds met (<500ms queries)
3. ✅ All quality thresholds met (>0.8 confidence)
4. ✅ Handles all 5 query types
5. ✅ Indexes 1000-page book in <15 minutes
6. ✅ No hallucination (100% answers from book)

---

## 💡 Key Principles

### **1. Tests Are Specifications**

Tests don't just validate - they **define** what the system should do.

### **2. Red → Green → Refactor**

1. **Red**: Write failing test
2. **Green**: Make it pass (don't worry about elegance)
3. **Refactor**: Clean up code while keeping tests green

### **3. One Test at a Time**

Don't try to pass all tests at once. Focus on ONE test, make it pass, move on.

### **4. Tests Guide Design**

If a test is hard to write, your design might be wrong. Let tests guide you to better architecture.

### **5. Fast Feedback**

Run tests frequently. Every 5-10 minutes. Fast feedback = fast learning.

---

## 🏆 What Success Looks Like

**In 4 weeks, you'll have:**

1. ✅ 74 passing tests
2. ✅ A robust, well-tested RAG system
3. ✅ Confidence that it works correctly
4. ✅ Documentation (the tests themselves!)
5. ✅ Easy maintenance (change code, tests tell you if you broke something)
6. ✅ Foundation for future features

**Most importantly**: You'll have learned TDD by doing it, not just reading about it.

---

## 📚 Next Actions

1. **Read tests**: Understand what each test expects
2. **Pick first test**: `test_basic_concept_query`
3. **Set up mock data**: Load mock_chunks.json into Qdrant
4. **Implement query pipeline**: Make the test pass
5. **Repeat**: For all 74 tests

---

## 🤝 Need Help?

**Stuck on a test?**
- Read the test docstring carefully
- Check the expected response in `expected_responses.json`
- Look at similar passing tests for patterns

**Not sure what to implement?**
- The test assertions tell you exactly what's needed
- Start with the simplest possible implementation
- Iterate based on test failures

**Performance issues?**
- Profile your code to find bottlenecks
- Check integration tests for optimization patterns
- Remember: Optimization comes AFTER tests pass

---

**Ready to build? Let's start with Week 1, Task 1: Mock Data Setup!** 🚀
