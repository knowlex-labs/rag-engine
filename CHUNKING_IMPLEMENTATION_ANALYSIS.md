# RAG Engine - Chunking Implementation Analysis

## Overview
The RAG Engine is a FastAPI-based system for indexing and querying documents using vector embeddings and Qdrant vector database. Currently, it implements a **simple whole-file chunking approach** without semantic paragraph-based chunking or hierarchical organization.

---

## 1. Current Chunking Implementation

### Location & Files Involved
- **Main Service**: `/home/user/rag-engine/src/services/collection_service.py`
- **Data Layer**: `/home/user/rag-engine/src/repositories/qdrant_repository.py`
- **File Processing**: `/home/user/rag-engine/src/services/file_service.py` & `gcs_file_service.py`
- **Configuration**: `/home/user/rag-engine/src/config.py`

### Current Strategy: Whole-File Chunking

**Problem**: The system treats entire files as single documents/chunks:

```python
# From collection_service.py (line 69-81)
def _generate_embedding_and_document(self, file_id: str, file_content: str, file_type: str):
    """Generates SINGLE embedding for entire file"""
    embedding = self.embedding_client.generate_single_embedding(file_content)
    documents = [{
        "document_id": file_id,
        "text": file_content,        # ENTIRE FILE!
        "source": file_type,
        "metadata": {"file_type": file_type},
        "vector": embedding
    }]
    return documents
```

**Impact**:
- A 100-page physics textbook becomes ONE vector embedding
- Query returns entire file, losing granularity
- Performance issues with very large documents
- Cannot target specific sections/chapters

---

## 2. Chunk Data Structure

### ChunkConfig Model (api_models.py)
```python
class ChunkConfig(BaseModel):
    source: str        # Document/file ID
    text: str          # Chunk content
```

### Stored Chunk Structure (qdrant_repository.py)
```python
payload = {
    "document_id": doc_id,              # File ID
    "text": text,                       # Full chunk text
    "source": source_file_type,         # File type (pdf, txt, etc)
    "metadata": {
        "file_type": file_type,
        # NOTE: No chapter/section info!
    }
}
```

**Missing Hierarchical Metadata**:
- No `chapter_num`, `section_num`, `page_number`
- No `chunk_type` (concept, problem, application, etc)
- No `parent_chunk_id` for relationships
- No `key_terms` or semantic markers

---

## 3. Chunking Strategies Comparison

### Current Approach: NO CHUNKING
```
File Input → Full Text Extraction → Single Embedding → Single Vector Point
```

### Planned Approach (from TDD_STRATEGY.md)
```
PDF Input → Extract Sections → Semantic Chunking → Multiple Embeddings → Hierarchical Metadata
```

**Expected Chunk Types**:
- `concept_explanation`: Core concepts (Newton's Laws, Forces, etc)
- `sample_problem`: Worked examples with solutions
- `application`: Real-world applications
- `question`: Exercise or test question
- `diagram_description`: Explanations of figures/diagrams

---

## 4. How Chunks Are Stored & Indexed

### Storage Location: Qdrant Vector Database

**Configuration** (config.py):
```python
class EmbeddingConfig:
    CHUNK_SIZE: int = 512          # DEFINED but NOT USED!
    CHUNK_OVERLAP: int = 50         # DEFINED but NOT USED!
    VECTOR_SIZE: int = 1024
    MODEL_NAME: str = "BAAI/bge-large-en-v1.5"
```

**Database Setup** (qdrant_repository.py):
```python
def create_collection(self, collection_name: str):
    self.client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=1024,                 # Fixed 1024-dim vectors
            distance=Distance.COSINE   # Cosine similarity
        )
    )
```

**Indexing Process**:
1. File uploaded via `/files` endpoint
2. Text extracted (PDF parsing or raw text)
3. ENTIRE content embedded (ignores CHUNK_SIZE config!)
4. Single PointStruct created with UUID
5. Upserted to Qdrant collection

```python
# From qdrant_repository.py (line 82-112)
def link_content(self, collection_name: str, documents: List[Dict]):
    points = []
    for doc in documents:
        point = PointStruct(
            id=str(uuid.uuid4()),      # Random UUID per document
            vector=vector,              # Single vector per file!
            payload={
                "document_id": doc_id,
                "text": text,
                "source": source,
                "metadata": {...}
            }
        )
    self.client.upsert(collection_name, points)
```

---

## 5. Query & Retrieval Pipeline

### Query Flow

```
User Query
    ↓
EmbeddingClient.generate_single_embedding(query)
    ↓
Qdrant.search(collection_name, query_vector, limit=5)
    ↓
Results: [{"id": uuid, "score": 0.94, "payload": {...}}]
    ↓
Reranker.rerank(query, results)  [Optional CrossEncoder]
    ↓
QueryService._extract_relevant_chunks(results)
    ↓
ChunkConfig[] with (source, text)
    ↓
LLM.generate_answer(query, chunks)
    ↓
QueryResponse with answer + chunks + confidence
```

### Chunk Extraction (query_service.py, lines 27-43)
```python
def _extract_relevant_chunks(self, results: List[Dict]) -> List[ChunkConfig]:
    chunks = []
    seen_texts = set()
    
    for result in results:
        payload = result.get("payload", {})
        text = payload.get("text", "")
        source = payload.get("document_id", "unknown")
        
        if text and self._is_valid_text(text):
            chunks.append(ChunkConfig(source=source, text=text))
    
    return chunks[:3]  # Hard-coded limit to 3 chunks!
```

**Issues**:
- Returns max 3 chunks (hard-coded!)
- No chunk ranking beyond vector similarity
- No chunk context preservation

---

## 6. Existing Hierarchy/Categorization

### Current Hierarchy: NONE
- All documents flat (no chapter/section nesting)
- All chunks treated equally in queries
- No way to query "Chapter 5 only"

### Available Context (Query Response Structure)
```python
class QueryResponse(BaseModel):
    answer: str
    confidence: float              # Max score from top result
    is_relevant: bool              # Score > 0.5
    chunks: List[ChunkConfig]      # [(source, text), ...]
    critic: Optional[CriticEvaluation] = None
```

### Missing Hierarchy Features
- No book/textbook level organization
- No chapter/section filtering
- No chunk relationship tracking
- No parent-child chunk references

---

## 7. File Processing Pipeline

### PDF Extraction (file_service.py & gcs_file_service.py)

```python
def get_file_content(self, file_id: str) -> Optional[str]:
    file_path = self.get_file_path(file_id)
    file_extension = os.path.splitext(file_path)[1].lower()
    
    if file_extension == ".pdf":
        return self._extract_pdf_text(file_path)
    else:
        return self._extract_text_file(file_path)

def _extract_pdf_text(self, file_path: str) -> Optional[str]:
    import pdfplumber
    with pdfplumber.open(file_path) as pdf:
        text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()
```

**Limitations**:
- Naive page-by-page concatenation
- No structure detection (chapters, sections, problems)
- No semantic chunking
- All text treated equally

---

## 8. Configuration Available

### Unused Chunking Parameters (config.py, lines 18-19)
```python
class EmbeddingConfig:
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "512"))      # NOT USED
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50")) # NOT USED
```

### Used Configuration
- Model: BAAI/bge-large-en-v1.5 (1024-dim)
- Distance: COSINE
- Query limit: Hard-coded to 5-10
- Chunk extraction: Hard-coded max 3 chunks
- Reranker: CrossEncoder (ms-marco-MiniLM-L-6-v2) - OPTIONAL
- Critic: Gemini evaluation - OPTIONAL

---

## 9. Future Chunking Design (From TDD Strategy)

### Expected Mock Chunk Structure
```json
{
  "id": "chunk_5_4_intro",
  "text": "5.4 NEWTON'S SECOND LAW\n...",
  "metadata": {
    "book_id": "resnick_halliday_10th",
    "book_title": "Fundamentals of Physics",
    "chapter_num": 5,
    "chapter_title": "Force and Motion - I",
    "section_num": "5.4",
    "section_title": "Newton's Second Law",
    "chunk_type": "concept_explanation",  # NEW
    "page_start": 92,
    "page_end": 92,
    "has_equations": true,
    "equations": ["F_net = ma"],
    "key_terms": ["Newton's second law", "force", "mass"]
  }
}
```

### Planned Chunk Types
1. **concept_explanation** - Core concepts
2. **sample_problem** - Worked examples
3. **application** - Real-world use cases
4. **question** - Exercise/test questions
5. **diagram_description** - Figure explanations

---

## 10. Service Dependencies & Architecture

### Service Layer Stack
```
CollectionService
├── QdrantRepository          # Vector DB operations
├── EmbeddingClient           # Sentence-Transformers
├── FileService              # File upload/storage
└── QueryService             # Query processing
    ├── QdrantRepository      # Search
    ├── Reranker             # CrossEncoder (optional)
    ├── Critic               # Gemini evaluation (optional)
    └── LLMClient            # OpenAI/Gemini answer generation
```

### Key Integration Points
- **Files → Embeddings**: FileService → EmbeddingClient → Qdrant
- **Query → Answer**: QueryService → Embeddings → Qdrant → Reranker → LLM
- **Feedback Loop**: FeedbackRepository → Query scoring

---

## 11. Performance Characteristics

### Current Metrics
- Query response: ~300-600ms (depends on LLM)
- Indexing: Single embedding generation
- Vector size: 1024 dimensions
- Collection search limit: 5-10 results
- Returned chunks: Hard-coded max 3

### Configured Thresholds
- Relevance threshold: 0.5 similarity score
- Feedback similarity threshold: 0.8
- Valid text: >80% printable characters
- Confidence: Highest result score

---

## 12. Test Suite Structure (From feat/book-indexing)

### Planned Test Coverage (74+ tests)

**Unit Tests** (test_chunking.py):
- PDF text extraction
- Chapter/section detection
- Semantic chunking logic
- Metadata generation

**Integration Tests** (test_query_pipeline.py):
- End-to-end indexing flow
- Query performance (<500ms)
- Chunk quality validation

**E2E Tests** (40+ tests):
- Concept Explanation queries
- Knowledge Testing
- Test Generation
- Problem Generation
- Analogy Generation

### Mock Data Fixtures
- `mock_chunks.json`: 5 realistic Chapter 5.4 chunks
- `expected_responses.json`: Expected response structures
- `test_queries.json`: Sample queries for each type

---

## Summary: Current State vs. Planned State

### What Works Now
✅ File upload (local & GCS)
✅ Full-text PDF extraction
✅ Whole-document embedding
✅ Vector similarity search
✅ LLM answer generation
✅ Optional reranking
✅ Optional critic evaluation

### What's Missing
❌ Semantic chunking (currently whole-file)
❌ Chapter/section hierarchy
❌ Chunk-type categorization
❌ Paragraph-aware splitting
❌ Structure detection (headers, sections)
❌ Page number tracking
❌ Related chunk linking
❌ Query-type specific responses

### Implementation Status
- **Current Branch**: `feat/chunking-chapter` (just added PDF)
- **Test Branch**: `origin/claude/qdrant-book-indexing-strategy-*` (TDD suite ready)
- **Config**: Chunking parameters defined but not implemented
- **Architecture**: Ready to accept hierarchical metadata

---

## Recommended Next Steps

1. **Phase 1**: Implement basic semantic chunking with token limits
2. **Phase 2**: Add structure detection (chapters, sections, problems)
3. **Phase 3**: Implement hierarchical metadata storage
4. **Phase 4**: Add query-type routing and specialized responses
5. **Phase 5**: Performance optimization & batch processing

