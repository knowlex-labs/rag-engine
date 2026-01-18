"""
Bare Acts Parser - Line-by-Line Approach
Specialized parser for Indian Bare Acts with robust extraction.

Enhanced with:
- Comprehensive error handling
- Validation of extracted content
- Better edge case handling for scanned PDFs
- Detailed logging and progress tracking
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import traceback

from .ocr_service import OCRService

# Configure logging
logger = logging.getLogger(__name__)


class ParserError(Exception):
    """Custom exception for parsing errors."""
    pass


@dataclass
class ParsedSection:
    """A parsed section from a bare act."""
    number: str
    title: str
    content: str
    chapter_number: str = ""
    chapter_title: str = ""
    subsections: List[Dict[str, Any]] = field(default_factory=list)
    has_proviso: bool = False
    has_explanation: bool = False
    cross_references: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate section data."""
        self.number = str(self.number).strip()
        self.title = str(self.title).strip() if self.title else ""
        self.content = str(self.content).strip() if self.content else ""


@dataclass 
class ParsedChapter:
    """A parsed chapter from a bare act."""
    number: str
    title: str
    section_numbers: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate chapter data."""
        self.number = str(self.number).strip()
        self.title = str(self.title).strip() if self.title else ""


@dataclass
class ParsedBareAct:
    """Complete parsed bare act document."""
    name: str
    year: int
    act_number: str
    preamble: str
    chapters: List[ParsedChapter]
    sections: List[ParsedSection]
    schedules: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    
    def __post_init__(self):
        """Validate and clean data."""
        self.name = str(self.name).strip() if self.name else "Unknown Act"
        self.year = int(self.year) if self.year else 0
        self.act_number = str(self.act_number).strip() if self.act_number else ""
        self.preamble = str(self.preamble).strip()[:2000] if self.preamble else ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "year": self.year,
            "act_number": self.act_number,
            "preamble": self.preamble,
            "document_type": "bare_act",
            "total_chapters": len(self.chapters),
            "total_sections": len(self.sections),
            "chapters": [
                {
                    "number": ch.number,
                    "title": ch.title,
                    "section_numbers": ch.section_numbers
                }
                for ch in self.chapters
            ],
            "sections": [
                {
                    "number": sec.number,
                    "title": sec.title,
                    "content": sec.content,
                    "chapter_number": sec.chapter_number,
                    "chapter_title": sec.chapter_title,
                    "has_proviso": sec.has_proviso,
                    "has_explanation": sec.has_explanation,
                    "cross_references": sec.cross_references,
                    "subsections": sec.subsections
                }
                for sec in self.sections
            ],
            "schedules": self.schedules,
            "metadata": self.metadata
        }
    
    def validate(self) -> Tuple[bool, List[str]]:
        """Validate the parsed document."""
        errors = []
        warnings = []
        
        if not self.name or self.name == "Unknown Act":
            warnings.append("Act name could not be determined")
        
        if self.year == 0:
            warnings.append("Act year could not be determined")
        
        if not self.sections:
            errors.append("No sections were extracted")
        
        # Check for reasonable section count
        if len(self.sections) < 2:
            warnings.append(f"Only {len(self.sections)} section(s) found - may be incomplete")
        
        # Check for empty sections
        empty_sections = [s for s in self.sections if not s.content.strip()]
        if empty_sections and len(empty_sections) > len(self.sections) * 0.5:
            warnings.append(f"{len(empty_sections)} of {len(self.sections)} sections have no content")
        
        return len(errors) == 0, errors + warnings


class BareActParser:
    """
    Parser specialized for Indian Bare Acts using line-by-line approach.
    Enhanced with robust error handling and validation.
    """
    
    # Patterns to identify footnotes (should be excluded)
    FOOTNOTE_STARTERS = [
        'ins. by', 'subs. by', 'omitted by', 'added by', 'the words',
        'w.e.f.', 'clause (', 'section ', 'sub-section'
    ]
    
    # Minimum text length to consider extraction successful
    MIN_TEXT_LENGTH = 500
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.logger = logging.getLogger(f"{__name__}.BareActParser")
        if debug:
            self.logger.setLevel(logging.DEBUG)
    
    def _log(self, message: str, level: str = "info"):
        """Log with appropriate level."""
        if self.debug:
            print(f"[{level.upper()}] {message}")
        getattr(self.logger, level)(message)
    
    def _is_footnote(self, text: str) -> bool:
        """Check if line is a footnote."""
        if not text:
            return False
            
        text_lower = text.lower().strip()
        
        # Check if starts with number followed by footnote indicator
        if re.match(r'^\d+\.\s*(?:ins|subs|omitted|added|the words|w\.e\.f)', text_lower):
            return True
        
        # Check act reference pattern like "14 of 1947"
        if re.match(r'^\d+\s+of\s+\d{4}', text_lower):
            return True
        
        # Check for amendment indicators at line start
        if text_lower.startswith(('1.', '2.', '3.', '4.', '5.')) and \
           any(kw in text_lower for kw in ['ins.', 'subs.', 'omitted', 'added']):
            return True
            
        return False
    
    def _is_chapter_header(self, line: str) -> Optional[str]:
        """Check if line is a chapter header, return chapter number if so."""
        if not line:
            return None
            
        match = re.match(r'^CHAPTER\s+([IVX]+|\d+)\s*$', line.strip(), re.IGNORECASE)
        if match:
            return match.group(1)
        return None
    
    def _is_section_header(self, line: str) -> Optional[Tuple[str, str]]:
        """Check if line is a section header, return (number, title) if so."""
        if not line:
            return None
            
        # Pattern: "1. Short title, extent and commencement."
        # Must start with number, followed by period, then capitalized text
        match = re.match(r'^(\d+[A-Z]?)\.\s+([A-Z][^\n]+?)\.?\s*$', line.strip())
        if match:
            num = match.group(1)
            title = match.group(2).strip()
            # Additional check: title should not start with footnote-like text
            if not self._is_footnote(f"{num}. {title}"):
                return (num, title)
        return None
    
    def _is_chapter_title(self, line: str) -> bool:
        """Check if line looks like a chapter title (all caps or mostly caps)."""
        if not line:
            return False
            
        stripped = line.strip()
        if len(stripped) < 5:
            return False
        
        # Must be mostly uppercase
        upper_count = sum(1 for c in stripped if c.isupper())
        alpha_count = sum(1 for c in stripped if c.isalpha())
        
        if alpha_count == 0:
            return False
            
        return upper_count > alpha_count * 0.6
    
    def parse_pdf(self, pdf_path: str, use_ocr: bool = False) -> ParsedBareAct:
        """Parse a bare act PDF file with error handling."""
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise ParserError(f"PDF file not found: {pdf_path}")
        
        if not pdf_path.suffix.lower() == '.pdf':
            raise ParserError(f"File is not a PDF: {pdf_path}")
        
        self._log(f"Parsing PDF: {pdf_path.name}")
        
        try:
            text = self._extract_text_from_pdf(str(pdf_path), use_ocr)
            filename = pdf_path.name
            
            result = self.parse_text(text, filename)
            
            # Validate the result
            is_valid, issues = result.validate()
            if issues:
                for issue in issues:
                    self._log(f"Validation: {issue}", "warning")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error parsing {pdf_path}: {e}")
            self.logger.debug(traceback.format_exc())
            raise ParserError(f"Failed to parse PDF: {e}")
    
    def _extract_text_from_pdf(self, pdf_path: str, force_ocr: bool = False) -> str:
        """Extract text from PDF using pdftotext or OCR fallback."""
        text = ""
        
        if not force_ocr:
            try:
                result = subprocess.run(
                    ['pdftotext', '-layout', pdf_path, '-'],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    text = result.stdout
                    
                    # Check if we got meaningful content
                    if len(text.strip()) >= self.MIN_TEXT_LENGTH:
                        self._log(f"Extracted {len(text)} chars via pdftotext")
                        return text
                    else:
                        self._log(f"pdftotext returned only {len(text.strip())} chars - likely scanned PDF")
                        
            except subprocess.TimeoutExpired:
                self._log("pdftotext timed out", "warning")
            except FileNotFoundError:
                self._log("pdftotext not found - falling back to OCR", "warning")
            except Exception as e:
                self._log(f"pdftotext failed: {e}", "warning")
        
        # Fallback to OCR
        self._log("Attempting OCR extraction...")
        try:
            ocr_text = OCRService.pdf_to_text(pdf_path)
            if ocr_text and len(ocr_text.strip()) >= self.MIN_TEXT_LENGTH:
                self._log(f"Extracted {len(ocr_text)} chars via OCR")
                return ocr_text
        except Exception as e:
            self._log(f"OCR failed: {e}", "warning")
        
        # If we have any text from pdftotext, use it
        if text.strip():
            self._log(f"Using limited pdftotext output ({len(text.strip())} chars)", "warning")
            return text
        
        raise ParserError(f"Failed to extract text from {pdf_path} (both pdftotext and OCR failed)")
    
    def parse_text(self, text: str, filename: str = "") -> ParsedBareAct:
        """Parse bare act from text content with validation."""
        if not text or len(text.strip()) < 100:
            raise ParserError("Text content is too short or empty")
        
        lines = text.split('\n')
        self._log(f"Parsing {len(lines)} lines of text")
        
        # Extract metadata
        name, year, act_number = self._extract_metadata(text, filename)
        self._log(f"Act: {name} ({year})")
        
        # Extract preamble
        preamble = self._extract_preamble(lines)
        
        # Parse chapters and sections line by line
        chapters, sections = self._parse_structure(lines)
        self._log(f"Found {len(chapters)} chapters, {len(sections)} sections")
        
        # Extract schedules
        schedules = self._extract_schedules(text)
        
        return ParsedBareAct(
            name=name,
            year=year,
            act_number=act_number,
            preamble=preamble,
            chapters=chapters,
            sections=sections,
            schedules=schedules,
            metadata={
                "source_file": filename,
                "text_length": len(text),
                "line_count": len(lines),
                "parsed_at": str(__import__('datetime').datetime.now())
            }
        )
    
    def _extract_metadata(self, text: str, filename: str) -> Tuple[str, int, str]:
        """Extract act name, year, and act number with fallbacks."""
        name = ""
        year = 0
        act_number = ""
        
        search_text = text[:5000]  # Look in first 5000 chars
        
        # Try multiple patterns for act name and year
        patterns = [
            r'THE\s+([A-Z][A-Za-z\s\(\)&,\-]+?)\s+ACT,?\s*((?:19|20)\d{2})',
            r'THE\s+([A-Z][A-Za-z\s\(\)&,\-]+?)\s*,\s*((?:19|20)\d{2})',
            r'([A-Z][A-Za-z\s\(\)&,\-]+?)\s+ACT[,\s]+((?:19|20)\d{2})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                year = int(match.group(2))
                break
        
        # Fallback to filename
        if not name or not year:
            self._log("Using filename for metadata", "warning")
            name = name or filename.replace('.pdf', '').replace('_', ' ').title()
            if not year:
                year_match = re.search(r'((?:19|20)\d{2})', filename)
                year = int(year_match.group(1)) if year_match else 0
        
        # Find act number: "NO. 14 OF 1981"
        act_num_pattern = re.search(
            r'(?:ACT\s+)?NO\.?\s*(\d+)\s+OF\s+((?:19|20)\d{2})',
            search_text,
            re.IGNORECASE
        )
        if act_num_pattern:
            act_number = f"No. {act_num_pattern.group(1)} of {act_num_pattern.group(2)}"
        
        # Clean name
        name = re.sub(r'\s+', ' ', name).strip()
        if name.upper() == name:  # If all upper, title case it
            name = name.title()
        
        return name, year, act_number
    
    def _extract_preamble(self, lines: List[str]) -> str:
        """Extract the preamble text."""
        preamble_lines = []
        in_preamble = False
        
        for line in lines[:150]:  # Check first 150 lines
            line_upper = line.upper().strip()
            
            if 'BE IT ENACTED' in line_upper or 'WHEREAS' in line_upper:
                in_preamble = True
            
            if in_preamble:
                # Stop at chapter or section
                if self._is_chapter_header(line) or self._is_section_header(line):
                    break
                preamble_lines.append(line)
        
        preamble = '\n'.join(preamble_lines).strip()
        return preamble[:2000] if preamble else ""
    
    def _parse_structure(self, lines: List[str]) -> Tuple[List[ParsedChapter], List[ParsedSection]]:
        """Parse chapters and sections from lines with improved detection."""
        chapters = []
        sections = []
        
        current_chapter: Optional[ParsedChapter] = None
        current_section: Optional[ParsedSection] = None
        section_content_lines = []
        seen_section_numbers = set()
        
        # Find where actual content starts (skip table of contents)
        content_start = self._find_content_start(lines)
        self._log(f"Content starts at line {content_start}")
        
        i = content_start
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Skip empty lines for header detection
            if not stripped:
                if current_section:
                    section_content_lines.append("")  # Preserve paragraph breaks
                i += 1
                continue
            
            # Check for chapter header
            chapter_num = self._is_chapter_header(stripped)
            if chapter_num:
                # Save current section if any
                if current_section:
                    current_section.content = self._clean_content('\n'.join(section_content_lines))
                    sections.append(current_section)
                    current_section = None
                    section_content_lines = []
                
                # Get chapter title from next line(s)
                chapter_title = self._get_chapter_title(lines, i)
                
                current_chapter = ParsedChapter(
                    number=chapter_num,
                    title=chapter_title
                )
                chapters.append(current_chapter)
                
                if self.debug:
                    print(f"Found chapter {chapter_num}: {chapter_title[:50]}")
                
                i += 1
                continue
            
            # Check for section header
            section_info = self._is_section_header(stripped)
            if section_info:
                sec_num, sec_title = section_info
                
                # Skip duplicates (from table of contents)
                if sec_num in seen_section_numbers:
                    i += 1
                    continue
                
                # Save previous section
                if current_section:
                    current_section.content = self._clean_content('\n'.join(section_content_lines))
                    current_section.has_proviso = 'Provided that' in current_section.content
                    current_section.has_explanation = 'Explanation' in current_section.content
                    sections.append(current_section)
                
                seen_section_numbers.add(sec_num)
                section_content_lines = []
                
                current_section = ParsedSection(
                    number=sec_num,
                    title=sec_title,
                    content="",
                    chapter_number=current_chapter.number if current_chapter else "",
                    chapter_title=current_chapter.title if current_chapter else ""
                )
                
                if current_chapter:
                    current_chapter.section_numbers.append(sec_num)
                
                if self.debug:
                    print(f"Found section {sec_num}: {sec_title[:50]}")
                
                i += 1
                continue
            
            # Add to current section content
            if current_section and stripped and not self._is_footnote(stripped):
                section_content_lines.append(line)
            
            i += 1
        
        # Save last section
        if current_section:
            current_section.content = self._clean_content('\n'.join(section_content_lines))
            current_section.has_proviso = 'Provided that' in current_section.content
            current_section.has_explanation = 'Explanation' in current_section.content
            sections.append(current_section)
        
        return chapters, sections
    
    def _find_content_start(self, lines: List[str]) -> int:
        """Find where actual content starts (skip table of contents)."""
        chapter_occurrences = []
        
        for i, line in enumerate(lines):
            if self._is_chapter_header(line.strip()):
                chapter_occurrences.append(i)
        
        # If we find multiple CHAPTER headers, content likely starts at the second one
        # (first is in TOC)
        if len(chapter_occurrences) >= 2:
            return chapter_occurrences[1]
        elif len(chapter_occurrences) == 1:
            return chapter_occurrences[0]
        
        # Fallback: look for first section header
        for i, line in enumerate(lines):
            if self._is_section_header(line.strip()):
                # Check if this looks like content (has text following)
                if i + 2 < len(lines) and lines[i + 1].strip():
                    return max(0, i - 5)  # Start a few lines before
        
        return 0
    
    def _get_chapter_title(self, lines: List[str], chapter_line: int) -> str:
        """Get chapter title from lines following chapter header."""
        title_lines = []
        
        for j in range(chapter_line + 1, min(chapter_line + 5, len(lines))):
            next_line = lines[j].strip()
            
            if not next_line:
                continue
            
            if self._is_section_header(next_line):
                break
            
            if self._is_chapter_title(next_line):
                title_lines.append(next_line)
                break
            elif self._is_chapter_header(next_line):
                break
        
        return ' '.join(title_lines).strip()
    
    def _clean_content(self, content: str) -> str:
        """Clean and normalize section content."""
        if not content:
            return ""
        
        # Remove excessive whitespace
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
        content = re.sub(r' +', ' ', content)
        
        # Limit size
        return content.strip()[:5000]
    
    def _extract_schedules(self, text: str) -> List[Dict[str, Any]]:
        """Extract schedules from the document."""
        schedules = []
        
        schedule_pattern = re.compile(
            r'(?:THE\s+)?(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|\d+(?:ST|ND|RD|TH)?)\s+SCHEDULE|'
            r'THE\s+SCHEDULE|'
            r'SCHEDULE\s+([IVX]+|\d+|[A-Z])',
            re.IGNORECASE
        )
        
        matches = list(schedule_pattern.finditer(text))
        
        for i, match in enumerate(matches):
            try:
                schedule_id = match.group(1) or match.group(2) or "I"
                
                start_pos = match.start()
                end_pos = matches[i + 1].start() if i + 1 < len(matches) else min(start_pos + 5000, len(text))
                
                content = text[start_pos:end_pos].strip()
                
                schedules.append({
                    "number": schedule_id,
                    "content": content[:3000]
                })
            except Exception as e:
                self._log(f"Error extracting schedule: {e}", "warning")
        
        return schedules


def parse_bare_act(pdf_path: str, output_path: str = None) -> Dict[str, Any]:
    """Parse a bare act PDF and optionally save to JSON."""
    parser = BareActParser(debug=True)
    parsed = parser.parse_pdf(pdf_path)
    result = parsed.to_dict()
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Saved parsed output to: {output_path}")
    
    return result


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python bare_act_parser.py <pdf_path> [output_json_path]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        result = parse_bare_act(pdf_path, output_path)
        
        print(f"\n=== Parsed: {result['name']} ({result['year']}) ===")
        print(f"Act Number: {result['act_number']}")
        print(f"Chapters: {result['total_chapters']}")
        print(f"Sections: {result['total_sections']}")
        print(f"Schedules: {len(result['schedules'])}")
        
        if result['chapters']:
            print("\nChapters:")
            for ch in result['chapters'][:8]:
                print(f"  Chapter {ch['number']}: {ch['title']} ({len(ch['section_numbers'])} sections)")
        
        if result['sections']:
            print("\nFirst 10 sections:")
            for sec in result['sections'][:10]:
                print(f"  Section {sec['number']}: {sec['title'][:60]}")
                
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
