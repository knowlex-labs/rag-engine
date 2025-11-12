import re
import uuid
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
import pdfplumber
from models.api_models import (
    HierarchicalChunk,
    ChunkType,
    TopicMetadata,
    ChunkMetadata
)

logger = logging.getLogger(__name__)

class HierarchicalChunkingService:

    def __init__(self):
        # Header detection patterns (for text-based fallback)
        self.chapter_pattern = re.compile(
            r'^(?:chapter|ch\.?)\s*(\d+)[:\-\s]*(.+?)$',
            re.IGNORECASE
        )
        self.section_pattern = re.compile(
            r'^(\d+(?:\.\d+)+)[:\-\s]+(.+?)$',
            re.IGNORECASE
        )

        # Header text patterns for chunk type classification
        self.example_header_patterns = [
            'example', 'sample', 'worked', 'demonstration',
            'illustration', 'case study'
        ]
        self.question_header_patterns = [
            'exercise', 'problem', 'question', 'checkpoint',
            'practice', 'review', 'test yourself'
        ]

        # Equation patterns
        self.equation_pattern = re.compile(r'[=+\-*/]\s*[A-Za-z0-9]|[A-Za-z]\s*=')
        self.formula_pattern = re.compile(r'([A-Z][a-z]?\s*=|∑|∫|√|π|α|β|γ|Δ)')

    def chunk_pdf_hierarchically(
        self,
        file_path: str,
        document_id: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50
    ) -> List[HierarchicalChunk]:

        chunks = []

        logger.info("Chunk PDF Hierarchiaclly called")
        logger.info(f"DEBUG: Attempting to open file_path: '{file_path}'")
        logger.info(f"DEBUG: File path exists check: {os.path.exists(file_path) if file_path else 'N/A'}")
        try:
            with pdfplumber.open(file_path) as pdf:
                logger.info(f"Processing PDF with {len(pdf.pages)} pages for document {document_id}")

                headers = self._extract_headers_with_font_sizes(pdf)
                logger.info(f"Extracted {len(headers)} headers from PDF")

                if not headers:
                    logger.warning(f"No headers found in PDF {file_path}. Falling back to basic text chunking.")
                    full_text = ""
                    for page_num, page in enumerate(pdf.pages, start=1):
                        text = page.extract_text()
                        if text:
                            full_text += text + "\n"

                    if full_text.strip():
                        return self._create_basic_chunks(full_text, document_id, chunk_size, chunk_overlap)
                    else:
                        logger.error(f"No text content extracted from PDF {file_path}")
                        return []

                for i, header in enumerate(headers):
                    next_header = headers[i + 1] if i + 1 < len(headers) else None

                    chunk = self._create_chunk_from_header(
                        pdf=pdf,
                        header=header,
                        next_header=next_header,
                        document_id=document_id,
                        chunk_size=chunk_size
                    )

                    if chunk:
                        chunks.append(chunk)

                logger.info(f"Successfully created {len(chunks)} chunks from {len(headers)} headers")

        except FileNotFoundError as e:
            logger.error(f"PDF file not found: {file_path}")
            return []
        except Exception as e:
            logger.error(f"Error processing PDF {file_path}: {e}", exc_info=True)
            return []

        return chunks

    def _create_basic_chunks(
        self,
        text: str,
        document_id: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50
    ) -> List[HierarchicalChunk]:

        chunks = []
        text = text.strip()

        if not text:
            return chunks

        sentences = re.split(r'(?<=[.!?])\s+', text)

        current_chunk = ""
        chunk_num = 0

        for sentence in sentences:
            if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
                chunk_num += 1
                chunk_id = f"{document_id}_chunk_{chunk_num}"

                chunk = HierarchicalChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    text=current_chunk.strip(),
                    topic_metadata=TopicMetadata(
                        chapter_num=None,
                        chapter_title="Document Content",
                        section_num=f"Part {chunk_num}",
                        section_title=f"Content Part {chunk_num}",
                        page_start=None,
                        page_end=None
                    ),
                    chunk_metadata=ChunkMetadata(
                        chunk_type=ChunkType.CONCEPT,  # Default to concept
                        topic_id=document_id,
                        key_terms=self._extract_key_terms(current_chunk),
                        equations=self._extract_equations(current_chunk),
                        has_equations=bool(self._extract_equations(current_chunk)),
                        has_diagrams=False
                    )
                )
                chunks.append(chunk)

                words = current_chunk.split()
                overlap_words = words[-chunk_overlap:] if len(words) > chunk_overlap else words
                current_chunk = ' '.join(overlap_words) + ' ' + sentence
            else:
                current_chunk += ' ' + sentence if current_chunk else sentence

        if current_chunk.strip():
            chunk_num += 1
            chunk_id = f"{document_id}_chunk_{chunk_num}"

            chunk = HierarchicalChunk(
                chunk_id=chunk_id,
                document_id=document_id,
                text=current_chunk.strip(),
                topic_metadata=TopicMetadata(
                    chapter_num=None,
                    chapter_title="Document Content",
                    section_num=f"Part {chunk_num}",
                    section_title=f"Content Part {chunk_num}",
                    page_start=None,
                    page_end=None
                ),
                chunk_metadata=ChunkMetadata(
                    chunk_type=ChunkType.CONCEPT,
                    topic_id=document_id,
                    key_terms=self._extract_key_terms(current_chunk),
                    equations=self._extract_equations(current_chunk),
                    has_equations=bool(self._extract_equations(current_chunk)),
                    has_diagrams=False
                )
            )
            chunks.append(chunk)

        logger.info(f"Created {len(chunks)} basic chunks from text")
        return chunks

    def _extract_headers_with_font_sizes(self, pdf) -> List[Dict[str, Any]]:

        headers = []
        font_sizes = []

        for page_num, page in enumerate(pdf.pages, start=1):
            chars = page.chars
            if chars:
                for char in chars:
                    if 'size' in char:
                        font_sizes.append(char['size'])

        if not font_sizes:
            return self._extract_headers_text_based(pdf)

        font_sizes.sort()
        median_size = font_sizes[len(font_sizes) // 2]
        max_size = max(font_sizes)

        header_threshold = median_size * 1.2
        chapter_threshold = median_size * 1.5

        current_chapter = None
        current_section = None

        for page_num, page in enumerate(pdf.pages, start=1):
            lines = self._extract_lines_with_font_info(page)

            for line_data in lines:
                text = line_data['text'].strip()
                font_size = line_data['font_size']

                if not text or len(text) < 3:
                    continue

                if len(text) > 200:
                    continue

                is_chapter_header = font_size >= chapter_threshold
                is_section_header = header_threshold <= font_size < chapter_threshold

                if is_chapter_header:
                    chapter_match = self.chapter_pattern.match(text)
                    if chapter_match:
                        chapter_num = int(chapter_match.group(1))
                        chapter_title = chapter_match.group(2).strip()
                    else:
                        chapter_num = None
                        chapter_title = text

                    current_chapter = {
                        'type': 'chapter',
                        'chapter_num': chapter_num,
                        'chapter_title': chapter_title,
                        'section_num': None,
                        'section_title': None,
                        'page': page_num,
                        'y_position': line_data['y0'],
                        'text': text,
                        'font_size': font_size
                    }
                    headers.append(current_chapter)
                    current_section = None

                elif is_section_header:
                    section_match = self.section_pattern.match(text)
                    if section_match:
                        section_num = section_match.group(1)
                        section_title = section_match.group(2).strip()
                    else:
                        section_num = None
                        section_title = text

                    current_section = {
                        'type': 'section',
                        'chapter_num': current_chapter['chapter_num'] if current_chapter else None,
                        'chapter_title': current_chapter['chapter_title'] if current_chapter else None,
                        'section_num': section_num,
                        'section_title': section_title,
                        'page': page_num,
                        'y_position': line_data['y0'],
                        'text': text,
                        'font_size': font_size
                    }
                    headers.append(current_section)

        if not headers:
            headers.append({
                'type': 'chapter',
                'chapter_num': None,
                'chapter_title': 'Document Content',
                'section_num': None,
                'section_title': None,
                'page': 1,
                'y_position': 0,
                'text': 'Document Content',
                'font_size': 12
            })

        return headers

    def _extract_lines_with_font_info(self, page) -> List[Dict[str, Any]]:

        chars = page.chars
        if not chars:
            return []

        lines_dict = {}
        for char in chars:
            if 'text' not in char or not char['text'].strip():
                continue

            y0 = round(char.get('y0', 0))
            if y0 not in lines_dict:
                lines_dict[y0] = {
                    'chars': [],
                    'font_sizes': [],
                    'y0': y0
                }

            lines_dict[y0]['chars'].append(char['text'])
            if 'size' in char:
                lines_dict[y0]['font_sizes'].append(char['size'])

        lines = []
        for y0, line_data in sorted(lines_dict.items()):
            text = ''.join(line_data['chars'])
            avg_font_size = (
                sum(line_data['font_sizes']) / len(line_data['font_sizes'])
                if line_data['font_sizes'] else 12
            )

            lines.append({
                'text': text,
                'font_size': avg_font_size,
                'y0': y0
            })

        return lines

    def _extract_headers_text_based(self, pdf) -> List[Dict[str, Any]]:
 
        headers = []
        current_chapter = None

        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            lines = text.split('\n')

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                chapter_match = self.chapter_pattern.match(line)
                if chapter_match:
                    chapter_num = int(chapter_match.group(1))
                    chapter_title = chapter_match.group(2).strip()
                    current_chapter = {
                        'type': 'chapter',
                        'chapter_num': chapter_num,
                        'chapter_title': chapter_title,
                        'section_num': None,
                        'section_title': None,
                        'page': page_num,
                        'y_position': 0,
                        'text': line,
                        'font_size': 16
                    }
                    headers.append(current_chapter)
                    continue

                section_match = self.section_pattern.match(line)
                if section_match:
                    section_num = section_match.group(1)
                    section_title = section_match.group(2).strip()
                    headers.append({
                        'type': 'section',
                        'chapter_num': current_chapter['chapter_num'] if current_chapter else None,
                        'chapter_title': current_chapter['chapter_title'] if current_chapter else None,
                        'section_num': section_num,
                        'section_title': section_title,
                        'page': page_num,
                        'y_position': 0,
                        'text': line,
                        'font_size': 14
                    })

        if not headers:
            headers.append({
                'type': 'chapter',
                'chapter_num': None,
                'chapter_title': 'Document Content',
                'section_num': None,
                'section_title': None,
                'page': 1,
                'y_position': 0,
                'text': 'Document Content',
                'font_size': 12
            })

        return headers

    def _create_chunk_from_header(
        self,
        pdf,
        header: Dict[str, Any],
        next_header: Optional[Dict[str, Any]],
        document_id: str,
        chunk_size: int
    ) -> Optional[HierarchicalChunk]:

        content = self._extract_content_between_headers(pdf, header, next_header)

        if not content or len(content.strip()) < 50:
            return None

        chunk_type = self._classify_chunk_type_from_header(header['text'])

        topic_metadata = TopicMetadata(
            chapter_num=header.get('chapter_num'),
            chapter_title=header.get('chapter_title'),
            section_num=header.get('section_num'),
            section_title=header.get('section_title'),
            page_start=header.get('page'),
            page_end=next_header.get('page', header.get('page')) if next_header else header.get('page')
        )

        key_terms = self._extract_key_terms(content)
        equations = self._extract_equations(content)

        chunk_metadata = ChunkMetadata(
            chunk_type=chunk_type,
            topic_id=str(uuid.uuid4()),
            key_terms=key_terms,
            equations=equations,
            has_equations=len(equations) > 0,
            has_diagrams=self._has_diagram_reference(content)
        )

        return HierarchicalChunk(
            chunk_id=str(uuid.uuid4()),
            document_id=document_id,
            topic_metadata=topic_metadata,
            chunk_metadata=chunk_metadata,
            text=content
        )

    def _extract_content_between_headers(
        self,
        pdf,
        header: Dict[str, Any],
        next_header: Optional[Dict[str, Any]]
    ) -> str:

        content_parts = []
        start_page = header['page'] - 1 
        start_y = header['y_position']

        if next_header:
            end_page = next_header['page'] - 1
            end_y = next_header['y_position']
        else:
            end_page = len(pdf.pages) - 1
            end_y = float('inf')

        for page_idx in range(start_page, min(end_page + 1, len(pdf.pages))):
            page = pdf.pages[page_idx]
            text = page.extract_text() or ""

            if page_idx == start_page:
                lines = text.split('\n')
                header_found = False
                for i, line in enumerate(lines):
                    if header['text'] in line:
                        header_found = True
                        content_parts.append('\n'.join(lines[i+1:]))
                        break
                if not header_found:
                    content_parts.append(text)

            elif page_idx == end_page and next_header:
                lines = text.split('\n')
                for i, line in enumerate(lines):
                    if next_header['text'] in line:
                        content_parts.append('\n'.join(lines[:i]))
                        break
                else:
                    content_parts.append(text)

            else:
                content_parts.append(text)

        return '\n'.join(content_parts)

    def _classify_chunk_type_from_header(self, header_text: str) -> ChunkType:
        header_lower = header_text.lower()

        for pattern in self.example_header_patterns:
            if pattern in header_lower:
                return ChunkType.EXAMPLE

        for pattern in self.question_header_patterns:
            if pattern in header_lower:
                return ChunkType.QUESTION

        return ChunkType.CONCEPT


    def _extract_key_terms(self, text: str) -> List[str]:
        terms = []
        quoted = re.findall(r'"([^"]+)"', text)
        terms.extend(quoted)
        capitalized = re.findall(r'(?<!^)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', text)
        terms.extend(capitalized)
        return list(set(terms))[:10] 

    def _extract_equations(self, text: str) -> List[str]:
        equations = []
        lines = text.split('\n')
        for line in lines:
            if self.equation_pattern.search(line) or self.formula_pattern.search(line):
                eq = line.strip()
                if len(eq) < 100:
                    equations.append(eq)

        return equations[:5]

    def _has_diagram_reference(self, text: str) -> bool:
        diagram_keywords = ['figure', 'diagram', 'fig.', 'illustration', 'graph', 'chart']
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in diagram_keywords)
