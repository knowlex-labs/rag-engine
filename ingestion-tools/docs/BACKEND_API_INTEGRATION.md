# Legal RAG Engine API Integration Guide

## Overview
This document provides complete integration instructions for the Legal RAG Engine APIs designed for constitutional law education and exam preparation.

## Base URL
```
http://localhost:8000
```

## Authentication
All APIs require a user identifier in the header:
```
x-user-id: your-user-id
```

---

## 1. Legal Assistant API (Chatbot)

**Endpoint:** `POST /api/v1/law/chat`

**Purpose:** Interactive Q&A chatbot for constitutional law queries

### Request Structure
```json
{
  "question": "string (required, 10-500 chars)"
}
```

### Headers
```
Content-Type: application/json
x-user-id: string (required)
```

### Response Structure
```json
{
  "answer": "string",
  "sources": [
    {
      "text": "string (first 200 chars of source)",
      "article": "string (article reference)"
    }
  ],
  "total_chunks": "integer"
}
```

### Example Usage

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/law/chat \
  -H "Content-Type: application/json" \
  -H "x-user-id: user123" \
  -d '{
    "question": "What is Article 21 of Indian Constitution?"
  }'
```

**Response:**
```json
{
  "answer": "Article 21 is about the protection of life and personal liberty.",
  "sources": [
    {
      "text": "- **Article 21**: Protection of life and personal liberty.\n- **Article 21A**: Right to education.\n- **Article 22**: Protection against arrest and detention...",
      "article": "Protection of life and personal liberty."
    }
  ],
  "total_chunks": 5
}
```

---

## 2. Question Generation API

**Endpoint:** `POST /api/v1/law/questions`

**Purpose:** Generate legal exam-style questions for constitutional law education

### Request Structure
```json
{
  "questions": [
    {
      "type": "string (required)",
      "difficulty": "string (required)",
      "count": "integer (required, 1-10)",
      "filters": {
        "collection_ids": ["string array (optional)"]
      }
    }
  ],
  "context": {
    "subject": "string (optional)"
  }
}
```

### Question Types
- `"assertion_reasoning"` - Assertion-Reason format questions
- `"match_following"` - Match List I with List II questions
- `"comprehension"` - Passage-based questions with multiple MCQs

### Difficulty Levels
- `"easy"` - Basic factual questions
- `"moderate"` - Application and analysis questions
- `"difficult"` - Complex legal reasoning (limited support)

### Response Structure
```json
{
  "success": "boolean",
  "total_generated": "integer",
  "questions": [
    {
      "metadata": {
        "question_id": "string (UUID)",
        "type": "string",
        "difficulty": "string",
        "estimated_time": "integer (minutes)",
        "source_files": ["string array"],
        "generated_at": "string (ISO timestamp)"
      },
      "content": {
        // Question-specific content based on type
      }
    }
  ],
  "generation_stats": {
    "total_requested": "integer",
    "by_type": {"type": "count"},
    "by_difficulty": {"difficulty": "count"},
    "content_selection_time": "float (seconds)",
    "generation_time": "float (seconds)"
  },
  "errors": ["string array"],
  "warnings": ["string array"]
}
```

### Question Content Structures

#### Assertion-Reasoning Questions
```json
{
  "question_text": "Read the following statements about constitutional law and select the correct option:",
  "assertion": "Assertion (A): Statement about constitutional law",
  "reason": "Reason (R): Related explanation or principle",
  "options": [
    "Both A and R are true and R is the correct explanation of A.",
    "Both A and R are true but R is not the correct explanation of A.",
    "A is true but R is false.",
    "A is false but R is true."
  ],
  "correct_option": "string",
  "explanation": "Detailed legal explanation",
  "difficulty": "string",
  "source_chunks": ["string array"]
}
```

#### Match-Following Questions
```json
{
  "question_text": "Match List I with List II and select the correct answer from the options given below:",
  "list_I": ["Item 1", "Item 2", "Item 3", "Item 4"],
  "list_II": ["Definition A", "Definition B", "Definition C", "Definition D"],
  "correct_matches": {
    "Item 1": "Definition A",
    "Item 2": "Definition B",
    "Item 3": "Definition C",
    "Item 4": "Definition D"
  },
  "explanation": "Detailed explanation of each match",
  "difficulty": "string",
  "source_chunks": ["string array"]
}
```

#### Comprehension Questions
```json
{
  "passage": "Legal text passage for comprehension",
  "questions": [
    {
      "question_text": "Question based on passage",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_option": "Option A",
      "explanation": "Explanation with passage reference"
    }
  ],
  "difficulty": "string",
  "source_chunks": ["string array"]
}
```

### Example Usage

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/law/questions \
  -H "Content-Type: application/json" \
  -d '{
    "questions": [
      {
        "type": "assertion_reasoning",
        "difficulty": "easy",
        "count": 2,
        "filters": {
          "collection_ids": ["constitution-golden-source"]
        }
      }
    ],
    "context": {
      "subject": "Constitutional Law"
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "total_generated": 2,
  "questions": [
    {
      "metadata": {
        "question_id": "715c24df-6cc1-46c8-9546-4c90122b7a77",
        "type": "assertion_reasoning",
        "difficulty": "easy",
        "estimated_time": 2,
        "source_files": ["constitution-art-14", "constitution-art-53"],
        "generated_at": "2025-12-20T22:03:11.234944"
      },
      "content": {
        "question_text": "Read the following statements about constitutional law and select the correct option:",
        "assertion": "Assertion (A): Article 245 of the Indian Constitution defines the extent of laws made by Parliament and by the Legislatures of States.",
        "reason": "Reason (R): Article 123 of the Indian Constitution allows the President to promulgate Ordinances during the recess of Parliament.",
        "options": [
          "Both A and R are true and R is the correct explanation of A.",
          "Both A and R are true but R is not the correct explanation of A.",
          "A is true but R is false.",
          "A is false but R is true."
        ],
        "correct_option": "Both A and R are true but R is not the correct explanation of A.",
        "explanation": "Article 245 indeed defines the extent of laws made by Parliament and the State Legislatures, making the assertion true. Article 123 allows the President to promulgate Ordinances during the recess of Parliament, which is also true. However, Article 123 does not explain Article 245, so the reason is not the correct explanation of the assertion.",
        "difficulty": "easy",
        "source_chunks": ["constitution-art-243p-chunk-001", "constitution-art-38-chunk-001"]
      }
    }
  ],
  "generation_stats": {
    "total_requested": 2,
    "by_type": {"assertion_reasoning": 2},
    "by_difficulty": {"easy": 2},
    "content_selection_time": 1.108,
    "generation_time": 4.327
  },
  "errors": [],
  "warnings": []
}
```

---

## 3. Content Retrieval API

**Endpoint:** `POST /api/v1/law/retrieve`

**Purpose:** Direct constitutional content retrieval for legal research

### Request Structure
```json
{
  "query": "string (required)",
  "user_id": "string (required)",
  "collection_ids": ["string array (required)"],
  "top_k": "integer (optional, default 10, max 20)"
}
```

### Headers
```
Content-Type: application/json
x-user-id: string (required)
```

### Response Structure
```json
{
  "success": "boolean",
  "results": [
    {
      "chunk_id": "string",
      "chunk_text": "string",
      "relevance_score": "float (0-1)",
      "file_id": "string",
      "page_number": "integer or null",
      "concepts": ["string array"]
    }
  ]
}
```

### Example Usage

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/law/retrieve \
  -H "Content-Type: application/json" \
  -H "x-user-id: user123" \
  -d '{
    "query": "fundamental rights Article 21",
    "user_id": "user123",
    "collection_ids": ["constitution-golden-source"],
    "top_k": 3
  }'
```

**Response:**
```json
{
  "success": true,
  "results": [
    {
      "chunk_id": "constitution-art-21-chunk-001",
      "chunk_text": "- **Article 21**: Protection of life and personal liberty.\n- **Article 21A**: Right to education.\n- **Article 22**: Protection against arrest and detention in certain cases.",
      "relevance_score": 0.924,
      "file_id": "constitution-art-368",
      "page_number": null,
      "concepts": ["21", "Protection of life and personal liberty."]
    }
  ]
}
```

---

## Error Handling

All APIs return standard HTTP status codes:

### Success Responses
- `200 OK` - Request successful
- `201 Created` - Resource created successfully

### Error Responses
- `400 Bad Request` - Invalid request parameters
- `422 Unprocessable Entity` - Validation errors
- `500 Internal Server Error` - Server error

### Error Response Format
```json
{
  "detail": "string (error message)"
}
```

Or for validation errors:
```json
{
  "detail": [
    {
      "type": "string",
      "loc": ["string array"],
      "msg": "string",
      "input": "any"
    }
  ]
}
```

---

## Best Practices

### 1. Rate Limiting
- Implement client-side rate limiting
- Question generation can take 3-8 seconds per question
- Legal assistant typically responds in 1-3 seconds

### 2. Error Handling
- Always check the `success` field in responses
- Handle timeout errors gracefully for question generation
- Implement retry logic for server errors

### 3. Caching
- Cache frequently asked legal assistant questions
- Store generated questions for reuse
- Content retrieval results can be cached by query

### 4. User Experience
- Show loading indicators for question generation
- Display progress for batch question requests
- Provide fallback content if APIs are unavailable

### 5. Security
- Always include `x-user-id` header for user tracking
- Validate and sanitize user input before sending
- Implement request size limits

---

## Collection IDs

### Available Collections
- `"constitution-golden-source"` - Complete Constitution of India content

### Future Collections (Planned)
- `"bnc-act"` - Bharatiya Nyaya Sanhita
- `"ipc-sections"` - Indian Penal Code
- `"evidence-act"` - Indian Evidence Act

---

## Integration Examples

### JavaScript/React Example
```javascript
// Legal Assistant Integration
const askLegalQuestion = async (question, userId) => {
  try {
    const response = await fetch('http://localhost:8000/api/v1/law/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-user-id': userId
      },
      body: JSON.stringify({ question })
    });

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Legal query failed:', error);
    throw error;
  }
};

// Question Generation Integration
const generateQuestions = async (type, difficulty, count) => {
  try {
    const response = await fetch('http://localhost:8000/api/v1/law/questions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        questions: [{
          type,
          difficulty,
          count,
          filters: {
            collection_ids: ['constitution-golden-source']
          }
        }],
        context: {
          subject: 'Constitutional Law'
        }
      })
    });

    const data = await response.json();
    return data.questions;
  } catch (error) {
    console.error('Question generation failed:', error);
    throw error;
  }
};
```

### Python Example
```python
import requests

class LegalRAGClient:
    def __init__(self, base_url="http://localhost:8000", user_id="default"):
        self.base_url = base_url
        self.user_id = user_id

    def ask_question(self, question):
        response = requests.post(
            f"{self.base_url}/api/v1/law/chat",
            json={"question": question},
            headers={"x-user-id": self.user_id}
        )
        return response.json()

    def generate_questions(self, question_type, difficulty, count=5):
        payload = {
            "questions": [{
                "type": question_type,
                "difficulty": difficulty,
                "count": count,
                "filters": {
                    "collection_ids": ["constitution-golden-source"]
                }
            }],
            "context": {"subject": "Constitutional Law"}
        }

        response = requests.post(
            f"{self.base_url}/api/v1/law/questions",
            json=payload
        )
        return response.json()

# Usage
client = LegalRAGClient(user_id="user123")
answer = client.ask_question("What is Article 21?")
questions = client.generate_questions("assertion_reasoning", "easy", 3)
```

---

## Monitoring and Analytics

### Recommended Metrics to Track
- API response times
- Question generation success rates
- Most frequently asked legal questions
- User engagement with generated content
- Error rates and types

### Logging
- Log all user queries for analytics
- Track question generation patterns
- Monitor API performance metrics

This documentation provides everything needed to integrate the Legal RAG Engine APIs into your backend system.