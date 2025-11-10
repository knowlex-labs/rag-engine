"""
Hierarchical Chunking Service
Implements header-based chunking with font size detection and structural classification.
"""

import re
import uuid
from typing import List, Dict, Any, Optional, Tuple
import pdfplumber
from models.api_models import (
    HierarchicalChunk,
    ChunkType,
    TopicMetadata,
    ChunkMetadata
)

class HierarchicalChunkingService:
    """
    Service for creating hierarchical chunks from documents.

    Strategy:
    1. Extract headers using font size detection
    2. Build hierarchical structure (Chapter → Section → Subsection)
    3. Create chunks between consecutive headers (not paragraphs)
    4. Classify chunks based on header text patterns
    """

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
        """
        Extract and chunk a PDF using header-based boundaries.

        Strategy:
        1. Extract all headers with font size detection
        2. Build header hierarchy
        3. Create chunks between consecutive headers
        4. Classify chunks based on header text

        Args:
            file_path: Path to PDF file
            document_id: Unique identifier for the document
            chunk_size: Max size for chunks (only split if content > chunk_size)
            chunk_overlap: Not used (headers define natural boundaries)

        Returns:
            List of hierarchical chunks
        """
        chunks = []

        try:
            with pdfplumber.open(file_path) as pdf:
                # Extract all headers with their positions and hierarchy
                headers = self._extract_headers_with_font_sizes(pdf)

                # Create chunks between consecutive headers
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

        except Exception as e:
            print(f"Error processing PDF: {e}")
            import traceback
            traceback.print_exc()
            return []

        return chunks

    def _extract_headers_with_font_sizes(self, pdf) -> List[Dict[str, Any]]:
        """
        Extract headers using font size detection.

        Books typically have:
        - Chapter headers: Largest font
        - Section headers: Medium-large font
        - Subsection headers: Medium font
        - Body text: Smallest font

        Returns:
            List of headers with hierarchy metadata
        """
        headers = []
        font_sizes = []

        # First pass: Collect all font sizes to determine thresholds
        for page_num, page in enumerate(pdf.pages, start=1):
            chars = page.chars
            if chars:
                for char in chars:
                    if 'size' in char:
                        font_sizes.append(char['size'])

        if not font_sizes:
            # Fallback to text-based detection if no font info
            return self._extract_headers_text_based(pdf)

        # Calculate font size thresholds
        font_sizes.sort()
        median_size = font_sizes[len(font_sizes) // 2]
        max_size = max(font_sizes)

        # Thresholds: anything significantly larger than median is likely a header
        header_threshold = median_size * 1.2
        chapter_threshold = median_size * 1.5

        # Second pass: Extract headers based on font size
        current_chapter = None
        current_section = None

        for page_num, page in enumerate(pdf.pages, start=1):
            # Group characters into lines
            lines = self._extract_lines_with_font_info(page)

            for line_data in lines:
                text = line_data['text'].strip()
                font_size = line_data['font_size']

                if not text or len(text) < 3:
                    continue

                # Skip lines that are too long (likely body text, not headers)
                if len(text) > 200:
                    continue

                # Determine if this is a header based on font size
                is_chapter_header = font_size >= chapter_threshold
                is_section_header = header_threshold <= font_size < chapter_threshold

                if is_chapter_header:
                    # Extract chapter number and title
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
                    # Extract section number and title
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

        # If no headers found, create a default one
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
        """
        Extract lines from a page with font size information.

        Groups characters into lines and calculates average font size per line.
        """
        chars = page.chars
        if not chars:
            return []

        # Group characters by y-position (line)
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

        # Convert to list of line data
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
        """
        Fallback: Extract headers using text patterns only (no font info).
        """
        headers = []
        current_chapter = None

        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            lines = text.split('\n')

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Check for chapter headers
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

                # Check for section headers
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
        """
        Create a chunk from content between this header and the next header.

        This fixes the overlap bug - content is strictly between headers.
        """
        # Extract content between current header and next header
        content = self._extract_content_between_headers(pdf, header, next_header)

        if not content or len(content.strip()) < 50:
            return None

        # Classify chunk type based on header text (not content)
        chunk_type = self._classify_chunk_type_from_header(header['text'])

        # Create topic metadata from header info
        topic_metadata = TopicMetadata(
            chapter_num=header.get('chapter_num'),
            chapter_title=header.get('chapter_title'),
            section_num=header.get('section_num'),
            section_title=header.get('section_title'),
            page_start=header.get('page'),
            page_end=next_header.get('page', header.get('page')) if next_header else header.get('page')
        )

        # Extract metadata from content
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
        """
        Extract content strictly between current header and next header.

        This prevents overlaps by extracting only the content that belongs
        to this section.
        """
        content_parts = []
        start_page = header['page'] - 1  # 0-indexed
        start_y = header['y_position']

        # Determine end boundary
        if next_header:
            end_page = next_header['page'] - 1
            end_y = next_header['y_position']
        else:
            # Last header - extract to end of document
            end_page = len(pdf.pages) - 1
            end_y = float('inf')

        # Extract content page by page
        for page_idx in range(start_page, min(end_page + 1, len(pdf.pages))):
            page = pdf.pages[page_idx]
            text = page.extract_text() or ""

            if page_idx == start_page:
                # First page - skip content before header
                lines = text.split('\n')
                # Find header line and start after it
                header_found = False
                for i, line in enumerate(lines):
                    if header['text'] in line:
                        header_found = True
                        # Start from next line
                        content_parts.append('\n'.join(lines[i+1:]))
                        break
                if not header_found:
                    content_parts.append(text)

            elif page_idx == end_page and next_header:
                # Last page - stop at next header
                lines = text.split('\n')
                # Find next header line and stop before it
                for i, line in enumerate(lines):
                    if next_header['text'] in line:
                        content_parts.append('\n'.join(lines[:i]))
                        break
                else:
                    content_parts.append(text)

            else:
                # Middle pages - take all content
                content_parts.append(text)

        return '\n'.join(content_parts)

    def _classify_chunk_type_from_header(self, header_text: str) -> ChunkType:
        """
        Classify chunk type based on header text.

        Books follow a natural structure:
        - Concept sections: Explain theory, definitions, laws
        - Example sections: Show worked problems, samples
        - Question sections: Practice problems, exercises

        This is straightforward - just look at the header text.
        """
        header_lower = header_text.lower()

        # Check for example patterns first
        for pattern in self.example_header_patterns:
            if pattern in header_lower:
                return ChunkType.EXAMPLE

        # Check for question patterns
        for pattern in self.question_header_patterns:
            if pattern in header_lower:
                return ChunkType.QUESTION

        # Default to concept (most sections are concept explanations)
        return ChunkType.CONCEPT


    def _extract_key_terms(self, text: str) -> List[str]:
        """
        Extract key terms from text (simplified version).
        """
        # Look for capitalized terms (potential key concepts)
        # This is a simple heuristic - in production, use NLP
        terms = []

        # Find terms in quotes
        quoted = re.findall(r'"([^"]+)"', text)
        terms.extend(quoted)

        # Find capitalized multi-word terms (not at sentence start)
        capitalized = re.findall(r'(?<!^)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', text)
        terms.extend(capitalized)

        return list(set(terms))[:10]  # Limit to 10 terms

    def _extract_equations(self, text: str) -> List[str]:
        """
        Extract equations from text.
        """
        equations = []

        # Find lines with equals signs and mathematical operators
        lines = text.split('\n')
        for line in lines:
            if self.equation_pattern.search(line) or self.formula_pattern.search(line):
                # Clean up the equation
                eq = line.strip()
                if len(eq) < 100:  # Reasonable equation length
                    equations.append(eq)

        return equations[:5]  # Limit to 5 equations

    def _has_diagram_reference(self, text: str) -> bool:
        """
        Check if text references diagrams or figures.
        """
        diagram_keywords = ['figure', 'diagram', 'fig.', 'illustration', 'graph', 'chart']
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in diagram_keywords)
