# Header-Based Chunking Strategy

## Overview

This document explains the new header-based chunking strategy for educational books and textbooks.

## Problems with Previous Approach

1. **Paragraph-based chunking was risky** - Text could span across pages, causing splits in the middle of concepts
2. **Content extraction had overlaps** - Topics extracted content until 5000 chars, not until next topic
3. **Classification was complex** - Used keyword counting across content, not straightforward
4. **No font size detection** - Couldn't reliably identify headers
5. **No natural structure** - Didn't follow concept → example → question flow

## New Strategy

### 1. Header-Based Boundaries

Chunks are now defined by **headers**, not paragraphs:

- Each header creates a new chunk
- Content is extracted strictly between consecutive headers
- No arbitrary character limits or paragraph breaks

### 2. Font Size Detection

Headers are identified using font size analysis:

```python
# Calculate font size thresholds
median_size = median(all_font_sizes)
header_threshold = median_size * 1.2
chapter_threshold = median_size * 1.5

# Classify by font size
if font_size >= chapter_threshold:
    → Chapter header
elif font_size >= header_threshold:
    → Section header
else:
    → Body text
```

Fallback to text pattern matching if no font info available.

### 3. Straightforward Classification

Chunk types are determined by **header text**, not content keywords:

```python
if header contains ["example", "sample", "worked", "demonstration"]:
    → ChunkType.EXAMPLE

elif header contains ["exercise", "problem", "question", "checkpoint"]:
    → ChunkType.QUESTION

else:
    → ChunkType.CONCEPT  (default for explanatory sections)
```

This follows the natural book structure: **concept → example → question**

### 4. No Overlaps

Content extraction is precise:

```python
for each header:
    start = current_header position
    end = next_header position (or end of document)
    extract content strictly between start and end
```

Previous bug: extracted until 5000 chars, causing overlaps between sections.

## Implementation Details

### Header Extraction

```python
def _extract_headers_with_font_sizes(pdf):
    1. Collect all font sizes from PDF
    2. Calculate median and thresholds
    3. Extract lines with font info
    4. Identify headers by font size
    5. Build hierarchy (chapter → section)
    6. Return ordered list of headers
```

### Content Extraction

```python
def _extract_content_between_headers(pdf, header, next_header):
    1. Start at current header page/position
    2. End at next header page/position
    3. Extract text page by page
    4. Skip header line itself
    5. Stop before next header
    6. Return clean content
```

### Chunk Creation

```python
def _create_chunk_from_header(pdf, header, next_header, document_id):
    1. Extract content between headers
    2. Classify type from header text
    3. Extract metadata (equations, key terms)
    4. Create chunk with topic hierarchy
    5. Return HierarchicalChunk object
```

## Advantages

1. ✓ **No gaps** - Every section has clear boundaries
2. ✓ **No overlaps** - Content belongs to exactly one chunk
3. ✓ **Straightforward** - Classification based on headers, not assumptions
4. ✓ **Natural structure** - Follows how books are actually written
5. ✓ **Robust** - Font size detection with text-based fallback
6. ✓ **Accurate page tracking** - Knows exact start and end pages

## Example

Given a textbook with:

```
CHAPTER 5: Force and Motion (font size: 18pt)
[concept explanation text...]

5.4 Newton's Second Law (font size: 14pt)
[concept explanation text...]

Example 5.1 - Calculating Force (font size: 14pt)
[worked example text...]

Exercise 5.2 - Practice Problems (font size: 14pt)
[questions text...]
```

Results in chunks:

1. Chunk 1: Chapter 5 header → Type: CONCEPT, Pages: 1-5
2. Chunk 2: Section 5.4 → Type: CONCEPT, Pages: 5-7
3. Chunk 3: Example 5.1 → Type: EXAMPLE, Pages: 7-8
4. Chunk 4: Exercise 5.2 → Type: QUESTION, Pages: 8-9

Each chunk contains only the content between its header and the next header.

## Migration Notes

- Old paragraph-based chunking: REMOVED
- Old keyword-based classification: REMOVED
- Old `_split_into_paragraphs()`: REMOVED
- Old `_classify_content_type()`: REMOVED
- Old `_extract_topic_content()`: REPLACED with `_extract_content_between_headers()`

The new implementation is cleaner, more accurate, and follows the natural structure of educational books.
