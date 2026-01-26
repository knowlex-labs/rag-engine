# LLM Prompts for Question Generation

## Overview
This document details the LLM prompts used for generating different types of questions at various difficulty levels. The system uses context-aware prompts that adapt based on difficulty level and question type.

---

## MCQ (Multiple Choice Questions) Prompts

### Location
File: `src/services/enhanced_question_generator.py`
Method: `_build_mcq_prompt()` (lines 489-538)

### Difficulty-Specific Instructions

#### EASY Level
```
- Focus on basic concepts, definitions, and direct factual recall
- Clear, unambiguous options
```

#### MODERATE Level
```
- Require application of principles or understanding of relationships
- Use plausible distractors that require careful reading to eliminate
```

#### DIFFICULT Level
```
- Complex analytical questions involving multiple principles
- Subtle distinctions between options requiring deep legal knowledge
```

### Full MCQ Prompt Template

```python
Role: UGC NET Legal Exam Setter specializing in Law.
Task: Create a high-quality Multiple Choice Question (MCQ) for UGC NET Paper-II.

Difficulty Level: {difficulty.value.upper()}  # EASY, MODERATE, or DIFFICULT
Subject Area: {context.subject if context else 'Law'}

{difficulty_instructions[difficulty]}

Source Content:
{chunk.text}

Requirements:
1. Base the question strictly on the provided content
2. Create 4 options (A, B, C, D) with only one correct answer
3. Ensure the question is professionally phrased and student-friendly

Output JSON format:
{
    "question_text": "The clear and complete question text",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_option": "The exact text of the correct option",
    "explanation": "Detailed professional explanation referencing the legal principles"
}
```

### Example Generated MCQ (EASY difficulty)
```json
{
  "question_text": "Under Section 342, what is the maximum term of imprisonment for a clerk, officer, or servant who, with intent to defraud, falsifies any book, electronic record, or account belonging to their employer?",
  "options": [
    "A term which may extend to three years",
    "A term which may extend to five years",
    "A term which may extend to seven years",
    "A term which may extend to ten years"
  ],
  "correct_option": "A term which may extend to seven years",
  "explanation": "According to Section 342, the maximum punishment for a clerk, officer, or servant who, with intent to defraud, falsifies any book, electronic record, or account belonging to their employer is imprisonment of either description for a term which may extend to seven years, or with fine, or with both."
}
```

---

## Assertion-Reasoning Questions Prompts

### Location
File: `src/services/enhanced_question_generator.py`
Method: `_build_assertion_reasoning_prompt()` (lines 344-413)

### Difficulty-Specific Instructions

#### EASY Level
```
- Create straightforward assertion and reason statements
- Use direct, clear language with basic legal concepts
- The relationship should be obvious and factual
```

#### MODERATE Level
```
- Include some complexity with conditional language
- Use moderate legal terminology and concepts
- The relationship should require some analysis but be determinable
```

#### DIFFICULT Level
```
- Use complex legal principles with nuanced relationships
- Include exceptions, limitations, or contradictory elements
- Require deep constitutional/legal reasoning to determine the relationship
```

### Full Assertion-Reasoning Prompt Template

```python
Role: UGC NET Legal Exam Setter specializing in Constitutional and Administrative Law.
Task: Create a high-quality "Assertion-Reason" question for UGC NET Paper-II.

Difficulty Level: {difficulty.value.upper()}
Subject Area: {context.subject if context else 'Law'}

{difficulty_instructions[difficulty]}

Source Legal Content:
{chunks_text}  # Multiple chunks combined

UGC NET Assertion-Reason Format Requirements:
1. Create a clear, legally accurate assertion statement
2. Create a related reason that may or may not correctly explain the assertion
3. Both statements must be factually verifiable from constitutional/legal principles
4. Use standard UGC NET options format exactly as provided

Standard UGC NET Options (use exactly these):
1. "Both A and R are true and R is the correct explanation of A."
2. "Both A and R are true but R is not the correct explanation of A."
3. "A is true but R is false."
4. "A is false but R is true."

Output JSON format:
{
    "question_text": "Read the following statements about constitutional law and select the correct option:",
    "assertion": "Assertion (A): [Clear legal principle or constitutional provision]",
    "reason": "Reason (R): [Related explanation, context, or supporting principle]",
    "options": [
        "Both A and R are true and R is the correct explanation of A.",
        "Both A and R are true but R is not the correct explanation of A.",
        "A is true but R is false.",
        "A is false but R is true."
    ],
    "correct_option": "[Exact option text from above]",
    "explanation": "Detailed explanation referencing constitutional provisions, case law, or legal principles. Explain why each part of the assertion and reason is true/false and why the relationship is/isn't correct."
}
```

---

## Match the Following Questions Prompts

### Location
File: `src/services/enhanced_question_generator.py`
Method: `_build_match_following_prompt()` (lines 415-487)

### Difficulty-Specific Instructions

#### EASY Level
```
- Use direct concept-definition or case-outcome relationships
- Clear, unambiguous matches with basic legal terminology
- Factual relationships that are straightforward
```

#### MODERATE Level
```
- Include case law, statutory provisions, and their applications
- Some complexity in relationships (cause-effect, principle-application)
- Require good understanding of legal concepts
```

#### DIFFICULT Level
```
- Complex legal principles with multiple related concepts
- Advanced constitutional doctrines, judicial precedents
- Subtle relationships requiring deep legal knowledge
```

### Full Match the Following Prompt Template

```python
Role: UGC NET Legal Exam Setter specializing in Constitutional and Administrative Law.
Task: Create a "Match the Following" question for UGC NET Paper-II.

Difficulty Level: {difficulty.value.upper()}
Subject Area: {context.subject if context else 'Law'}

{difficulty_instructions[difficulty]}

Source Legal Content:
{chunks_text}  # Multiple chunks (4-6 chunks)

UGC NET Match the Following Requirements:
1. Create exactly 4 items in List I and 4 items in List II
2. Each item in List I should have exactly one correct match in List II
3. Ensure all matches are factually accurate and legally sound
4. Use proper legal terminology and constitutional references

Output JSON format:
{
    "question_text": "Match List I with List II and select the correct answer from the options given below:",
    "list_I": [
        "Legal Concept/Case/Provision 1",
        "Legal Concept/Case/Provision 2",
        "Legal Concept/Case/Provision 3",
        "Legal Concept/Case/Provision 4"
    ],
    "list_II": [
        "Definition/Outcome/Application A",
        "Definition/Outcome/Application B",
        "Definition/Outcome/Application C",
        "Definition/Outcome/Application D"
    ],
    "correct_matches": {
        "Legal Concept/Case/Provision 1": "Definition/Outcome/Application A",
        "Legal Concept/Case/Provision 2": "Definition/Outcome/Application B",
        "Legal Concept/Case/Provision 3": "Definition/Outcome/Application C",
        "Legal Concept/Case/Provision 4": "Definition/Outcome/Application D"
    },
    "explanation": "Detailed explanation of each correct match with constitutional/legal basis. Reference specific articles, cases, or legal principles that establish these relationships."
}
```

---

## Comprehension Questions Prompts

### Location
File: `src/services/enhanced_question_generator.py`
Method: `_build_comprehension_prompt()` (lines 540-611)

### Difficulty-Specific Instructions

#### EASY Level
```
- Direct questions testing basic understanding and factual recall
- Clear questions with obvious answers from the passage
- Simple inference and application questions
```

#### MODERATE Level
```
- Questions requiring analysis and interpretation
- Some implicit information requiring inference
- Application of legal principles to given scenarios
```

#### DIFFICULT Level
```
- Complex analytical and evaluative questions
- Multiple layers of reasoning required
- Critical analysis of legal implications and consequences
```

### Full Comprehension Prompt Template

```python
Role: UGC NET Legal Exam Setter specializing in Constitutional and Administrative Law.
Task: Create a comprehension passage with 3 questions for UGC NET Paper-II.

Difficulty Level: {difficulty.value.upper()}
Subject Area: {context.subject if context else 'Law'}

{difficulty_instructions[difficulty]}

Source Legal Passage:
{chunk.text}

UGC NET Comprehension Requirements:
1. Use the provided text as the passage (may edit for clarity/length)
2. Create exactly 3 multiple choice questions based on the passage
3. Each question should have 4 options with only one correct answer
4. Questions should test: (a) factual understanding, (b) inference/analysis, (c) application/implication

Output JSON format:
{
    "passage": "Legal passage text (edited for clarity if needed, 300-500 words)",
    "questions": [
        {
            "question_text": "Question 1 testing factual understanding from passage",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_option": "Option A",
            "explanation": "Explanation with reference to specific part of passage"
        },
        {
            "question_text": "Question 2 requiring inference or analysis",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_option": "Option B",
            "explanation": "Explanation with analytical reasoning"
        },
        {
            "question_text": "Question 3 testing application or implication",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_option": "Option C",
            "explanation": "Explanation with legal application reasoning"
        }
    ]
}
```

---

## Language Support

### Current Implementation
The system currently uses **English** as the default language for question generation.

### Language Configuration
Location: `src/models/question_models.py` - `GenerationContext` class (lines 91-97)

```python
class GenerationContext(BaseModel):
    """Context for question generation"""
    exam_type: ExamType = Field(ExamType.UGC_NET, description="Type of exam")
    subject: Optional[str] = Field("law", description="Subject area (e.g., 'law', 'political_science')")
    avoid_duplicates: bool = Field(True, description="Avoid generating duplicate questions")
    include_explanations: bool = Field(True, description="Include detailed explanations")
    language: str = Field("english", description="Language for questions")
```

### How Language is Used
The `language` field in `GenerationContext` is passed to the question generator but is **currently not actively used in the prompts**. The prompts are hardcoded in English.

### Adding Multi-Language Support

To add support for other languages (e.g., Hindi, regional languages), you would need to:

1. **Update the prompts to include language instructions:**
```python
def _build_mcq_prompt(self, chunk, difficulty: DifficultyLevel, context) -> str:
    language = context.language if context else "english"
    
    language_instruction = ""
    if language.lower() == "hindi":
        language_instruction = "Generate the question, options, and explanation in Hindi."
    elif language.lower() == "english":
        language_instruction = "Generate the question, options, and explanation in English."
    
    prompt = f"""
    Role: UGC NET Legal Exam Setter specializing in Law.
    Task: Create a high-quality Multiple Choice Question (MCQ) for UGC NET Paper-II.
    
    Language: {language.upper()}
    {language_instruction}
    
    Difficulty Level: {difficulty.value.upper()}
    ...
    """
```

2. **Update the API to accept language parameter:**
```python
class SimpleQuestionGenerationRequest(BaseModel):
    title: str
    scope: List[str]
    num_questions: int
    difficulty: str
    language: str = "english"  # Add this field
    question_data: List[QuestionTypeData]
```

3. **Pass language to GenerationContext:**
```python
context = GenerationContext(
    subject="law",
    language=request.language  # Pass from request
)
```

---

## Estimated Time by Difficulty

The system assigns estimated completion times based on question type and difficulty:

### MCQ Questions
- **EASY**: 1 minute
- **MODERATE**: 2 minutes
- **DIFFICULT**: 2 minutes

### Assertion-Reasoning Questions
- **EASY**: 2 minutes
- **MODERATE**: 3 minutes
- **DIFFICULT**: 4 minutes

### Match the Following Questions
- **EASY**: 2 minutes
- **MODERATE**: 3 minutes
- **DIFFICULT**: 4 minutes

### Comprehension Questions
- **EASY**: 5 minutes
- **MODERATE**: 7 minutes
- **DIFFICULT**: 10 minutes

---

## Key Characteristics by Difficulty Level

### EASY Questions
- **Language**: Clear, direct, simple
- **Concepts**: Basic definitions, factual recall
- **Complexity**: Straightforward relationships
- **Terminology**: Basic legal terms
- **Answer**: Obvious from content

### MODERATE Questions
- **Language**: Conditional, some complexity
- **Concepts**: Application of principles
- **Complexity**: Requires analysis
- **Terminology**: Moderate legal terminology
- **Answer**: Requires careful reading

### DIFFICULT Questions
- **Language**: Complex, nuanced
- **Concepts**: Multiple principles, exceptions
- **Complexity**: Deep analysis required
- **Terminology**: Advanced legal terminology
- **Answer**: Subtle distinctions, deep knowledge needed

---

## Summary

The LLM prompt system is highly structured and calibrated for UGC NET exam standards:

1. ✅ **Difficulty-aware**: Each difficulty level has specific instructions
2. ✅ **Type-specific**: Different prompts for MCQ, Assertion-Reasoning, Match the Following, and Comprehension
3. ✅ **Context-aware**: Uses subject area and exam type
4. ✅ **Format-enforced**: Requires strict JSON output format
5. ⚠️ **Language support**: Currently English-only, but infrastructure exists for multi-language

To add language support, you need to:
- Add language instructions to each prompt builder
- Update API models to accept language parameter
- Pass language through to GenerationContext
- Ensure LLM can generate in the target language
