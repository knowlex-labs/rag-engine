"""
PDF parser using pdfplumber with font-based header detection.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import pdfplumber

from .base_parser import BaseParser
from .models import ParsedContent, ParsedMetadata, ContentSection

logger = logging.getLogger(__name__)


class PDFParser(BaseParser):
    """
    PDF parser that extracts hierarchical structure using font size analysis.

    Methodology:
    1. Analyze font sizes across entire document
    2. Identify headers based on font size thresholds:
       - Chapter headers: 1.5x median font size
       - Section headers: 1.2x median font size
    3. Fallback to regex-based header detection if font info unavailable
    4. Extract content sections with page numbers and styling metadata
    """

    def __init__(self):
        super().__init__()

        # Header detection patterns (for text-based fallback)
        self.chapter_pattern = re.compile(
            r'^(?:chapter|ch\.?)\s*(\d+)[:\-\s]*(.+?)$',
            re.IGNORECASE
        )
        self.section_pattern = re.compile(
            r'^(\d+(?:\.\d+)+)[:\-\s]+(.+?)$',
            re.IGNORECASE
        )

        # Equation patterns
        self.equation_pattern = re.compile(r'[=+\-*/]\s*[A-Za-z0-9]|[A-Za-z]\s*=')
        self.formula_pattern = re.compile(r'([A-Z][a-z]?\s*=|∑|∫|√|π|α|β|γ|Δ)')

        # Diagram detection keywords
        self.diagram_keywords = ['figure', 'diagram', 'illustration', 'graph', 'chart', 'image']

    def can_handle(self, source: str | Path) -> bool:
        """Check if source is a PDF file."""
        if isinstance(source, str):
            source = Path(source)

        return source.exists() and source.suffix.lower() == '.pdf'

    def parse(self, source: str | Path) -> ParsedContent:
        """
        Parse PDF and extract hierarchical structure.

        Args:
            source: Path to PDF file

        Returns:
            ParsedContent with sections and metadata

        Raises:
            FileNotFoundError: If PDF file doesn't exist
            ValueError: If PDF cannot be parsed
        """
        if isinstance(source, str):
            source = Path(source)

        self.validate_source(source)

        if not self.can_handle(source):
            raise ValueError(f"Cannot handle file: {source}. Must be a PDF file.")

        logger.info(f"Parsing PDF: {source}")

        try:
            with pdfplumber.open(source) as pdf:
                # Extract metadata
                metadata = self._extract_metadata(pdf, source)

                # Extract headers with font size analysis
                headers = self._extract_headers_with_font_sizes(pdf)
                logger.info(f"Extracted {len(headers)} headers from PDF")

                # Extract full text
                full_text = ""
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"

                # Build content sections from headers
                sections = self._build_sections_from_headers(pdf, headers)

                # Detect features
                has_equations = bool(self.equation_pattern.search(full_text) or self.formula_pattern.search(full_text))
                has_diagrams = any(keyword in full_text.lower() for keyword in self.diagram_keywords)

                return ParsedContent(
                    text=full_text,
                    metadata=metadata,
                    sections=sections,
                    source_type='pdf',
                    has_equations=has_equations,
                    has_diagrams=has_diagrams,
                    has_code_blocks=False  # PDFs rarely have code blocks
                )

        except FileNotFoundError:
            logger.error(f"PDF file not found: {source}")
            raise
        except Exception as e:
            logger.error(f"Error parsing PDF {source}: {e}", exc_info=True)
            raise ValueError(f"Failed to parse PDF: {e}")

    def _extract_metadata(self, pdf, file_path: Path) -> ParsedMetadata:
        """Extract PDF metadata."""
        pdf_metadata = pdf.metadata or {}

        title = pdf_metadata.get('Title') or file_path.stem
        page_count = len(pdf.pages)

        return ParsedMetadata(
            title=title,
            url=None,
            page_count=page_count
        )

    def _extract_headers_with_font_sizes(self, pdf) -> List[Dict[str, Any]]:
        """
        Extract headers using font size analysis.

        This is the core logic from hierarchical_chunking_service.py.
        """
        headers = []
        font_sizes = []

        # Collect all font sizes
        for page in pdf.pages:
            chars = page.chars
            if chars:
                for char in chars:
                    if 'size' in char:
                        font_sizes.append(char['size'])

        if not font_sizes:
            logger.warning("No font information found, using text-based header detection")
            return self._extract_headers_text_based(pdf)

        # Calculate thresholds
        font_sizes.sort()
        median_size = font_sizes[len(font_sizes) // 2]

        header_threshold = median_size * 1.2  # Section headers
        chapter_threshold = median_size * 1.5  # Chapter headers

        logger.info(f"Font size thresholds - Median: {median_size:.1f}, Section: {header_threshold:.1f}, Chapter: {chapter_threshold:.1f}")

        current_chapter = None

        for page_num, page in enumerate(pdf.pages, start=1):
            lines = self._extract_lines_with_font_info(page)

            for line_data in lines:
                text = line_data['text'].strip()
                font_size = line_data['font_size']

                # Skip empty or very long lines
                if not text or len(text) < 3 or len(text) > 200:
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
                        'level': 1,
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

                elif is_section_header:
                    section_match = self.section_pattern.match(text)
                    if section_match:
                        section_num = section_match.group(1)
                        section_title = section_match.group(2).strip()
                    else:
                        section_num = None
                        section_title = text

                    headers.append({
                        'type': 'section',
                        'level': 2,
                        'chapter_num': current_chapter['chapter_num'] if current_chapter else None,
                        'chapter_title': current_chapter['chapter_title'] if current_chapter else None,
                        'section_num': section_num,
                        'section_title': section_title,
                        'page': page_num,
                        'y_position': line_data['y0'],
                        'text': text,
                        'font_size': font_size
                    })

        # If no headers found, create default header
        if not headers:
            headers.append({
                'type': 'chapter',
                'level': 1,
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
        """Extract lines with average font size per line."""
        chars = page.chars
        if not chars:
            return []

        # Group characters by y-position (same line)
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

        # Build lines with average font size
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
        Fallback header extraction using regex patterns.

        Used when font information is not available.
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

                # Try to match chapter pattern
                chapter_match = self.chapter_pattern.match(line)
                if chapter_match:
                    chapter_num = int(chapter_match.group(1))
                    chapter_title = chapter_match.group(2).strip()
                    current_chapter = {
                        'type': 'chapter',
                        'level': 1,
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

                # Try to match section pattern
                section_match = self.section_pattern.match(line)
                if section_match:
                    section_num = section_match.group(1)
                    section_title = section_match.group(2).strip()
                    headers.append({
                        'type': 'section',
                        'level': 2,
                        'chapter_num': current_chapter['chapter_num'] if current_chapter else None,
                        'chapter_title': current_chapter['chapter_title'] if current_chapter else None,
                        'section_num': section_num,
                        'section_title': section_title,
                        'page': page_num,
                        'y_position': 0,
                        'text': line,
                        'font_size': 14
                    })

        # Default header if none found
        if not headers:
            headers.append({
                'type': 'chapter',
                'level': 1,
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

    def _build_sections_from_headers(self, pdf, headers: List[Dict[str, Any]]) -> List[ContentSection]:
        """Build ContentSection objects from headers."""
        sections = []

        for i, header in enumerate(headers):
            next_header = headers[i + 1] if i + 1 < len(headers) else None

            # Extract content between this header and the next
            content = self._extract_content_between_headers(pdf, header, next_header)

            if not content.strip():
                continue

            section = ContentSection(
                level=header['level'],
                text=content,
                title=header.get('chapter_title') or header.get('section_title'),
                parent_id=None,  # Could be enhanced to track parent relationships
                page_number=header['page'],
                timestamp=None,
                section_id=f"section_{i}",
                font_size=header.get('font_size'),
                is_bold=None,  # Could be enhanced to detect bold text
                is_italic=None  # Could be enhanced to detect italic text
            )

            sections.append(section)

        return sections

    def _extract_content_between_headers(
        self,
        pdf,
        header: Dict[str, Any],
        next_header: Optional[Dict[str, Any]]
    ) -> str:
        """Extract text content between two headers."""
        start_page = header['page'] - 1  # 0-indexed
        start_y = header.get('y_position', 0)

        if next_header:
            end_page = next_header['page'] - 1
            end_y = next_header.get('y_position', float('inf'))
        else:
            end_page = len(pdf.pages) - 1
            end_y = float('inf')

        content = ""

        for page_idx in range(start_page, min(end_page + 1, len(pdf.pages))):
            page = pdf.pages[page_idx]
            page_text = page.extract_text() or ""

            # For the first page, skip header line
            if page_idx == start_page:
                lines = page_text.split('\n')
                # Skip the header line itself
                page_text = '\n'.join(lines[1:]) if len(lines) > 1 else ""

            # For the last page (if next_header exists), stop before next header
            if page_idx == end_page and next_header:
                # This is simplified - ideally we'd stop at exact y_position
                # For now, just stop at the next page
                if page_idx < end_page:
                    content += page_text + "\n"
                else:
                    # Last page, might need to stop mid-page
                    content += page_text + "\n"
                break

            content += page_text + "\n"

        return content.strip()

    def validate_source(self, source: str | Path) -> None:
        """Validate PDF source exists."""
        super().validate_source(source)

        if isinstance(source, str):
            source = Path(source)

        if not source.exists():
            raise FileNotFoundError(f"PDF file not found: {source}")

        if not source.is_file():
            raise ValueError(f"Source is not a file: {source}")
