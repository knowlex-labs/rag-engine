"""
Document Structure Parser
Handles the hierarchical parsing of legal documents (chapters, sections, subsections, clauses).
"""

import re
from typing import Dict, List, Any, Tuple, Optional


class DocumentStructureParser:
    """
    Parser for the hierarchical structure of legal documents.
    Designed to handle various numbering schemes and document formats.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.debug = config.get("debug_mode", False)

    def parse_structure(self, text: str) -> Dict[str, Any]:
        """
        Parse the complete hierarchical structure of a legal document.

        Returns:
            Dict containing chapters and sections with their content and metadata
        """
        # Clean the text for better parsing
        cleaned_text = self._preprocess_text(text)

        # Extract chapters first
        chapters = self._extract_chapters(cleaned_text)

        # Extract sections (both within and outside chapters)
        sections = self._extract_sections(cleaned_text, chapters)

        # Build hierarchical relationships
        self._build_hierarchy(chapters, sections)

        return {
            "chapters": chapters,
            "sections": sections,
            "structure_metadata": {
                "total_chapters": len(chapters),
                "total_sections": len(sections),
                "has_chapter_structure": len(chapters) > 0
            }
        }

    def _preprocess_text(self, text: str) -> str:
        """Clean and prepare text for parsing."""
        # Normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        # Remove excessive whitespace while preserving structure
        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            # Keep empty lines that might indicate structure breaks
            if line.strip():
                cleaned_lines.append(line.rstrip())
            elif cleaned_lines and cleaned_lines[-1]:  # Add single empty line
                cleaned_lines.append('')

        return '\n'.join(cleaned_lines)

    def _extract_chapters(self, text: str) -> List[Dict[str, Any]]:
        """Extract chapters from the document."""
        chapters = []

        # Pattern for chapters: "CHAPTER I", "CHAPTER II", etc.
        chapter_pattern = r'^(CHAPTER\s+(?:[IVX]+|[A-Z]+|\d+))\s*\n(.*?)(?=\n\n|\nCHAPTER|\Z)'

        matches = re.finditer(chapter_pattern, text, re.MULTILINE | re.DOTALL | re.IGNORECASE)

        for i, match in enumerate(matches):
            chapter_header = match.group(1).strip()
            chapter_content = match.group(2).strip()

            # Extract chapter number
            number_match = re.search(r'CHAPTER\s+((?:[IVX]+|[A-Z]+|\d+))', chapter_header, re.IGNORECASE)
            chapter_number = number_match.group(1) if number_match else str(i + 1)

            # Extract chapter title (usually follows the chapter number)
            title_lines = chapter_content.split('\n')[:3]  # Check first few lines for title
            chapter_title = ""

            for line in title_lines:
                line = line.strip()
                if line and not re.match(r'^\d+\.', line):  # Not a section start
                    chapter_title = line
                    break

            chapters.append({
                "number": chapter_number,
                "title": chapter_title,
                "content": chapter_content,
                "start_position": match.start(),
                "end_position": match.end(),
                "sections": []  # Will be populated later
            })

        return chapters

    def _extract_sections(self, text: str, chapters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract sections from the document."""
        sections = []

        # Improved pattern that captures the full section content until the next section
        section_pattern = r'^(\d+)\.\s+([^—\n]+)(?:—|\.)?\s*(.*?)(?=^\d+\.\s|$)'

        matches = list(re.finditer(section_pattern, text, re.MULTILINE | re.DOTALL))

        for i, match in enumerate(matches):
            section_number = match.group(1)
            section_title = self._clean_section_title(match.group(2))
            section_content = match.group(3).strip()

            # If content is empty or very short, try to get more content
            if len(section_content) < 50:
                # Look for content after the title until next section or chapter
                next_section_start = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                full_section_text = text[match.start():next_section_start]

                # Extract content after the title line, but be more comprehensive
                lines = full_section_text.split('\n')
                if len(lines) > 1:
                    # Skip the title line and capture everything until next section/chapter
                    content_lines = lines[1:]
                    section_content = '\n'.join(content_lines).strip()

                    # Remove any trailing chapter headers that got captured
                    section_content = re.sub(r'\n\nCHAPTER\s+[IVX]+.*?$', '', section_content, flags=re.DOTALL).strip()

            # Determine which chapter this section belongs to
            chapter_number = self._find_section_chapter(match.start(), chapters)

            # Parse subsections and clauses
            subsections = self._extract_subsections(section_content)

            sections.append({
                "number": section_number,
                "title": section_title,
                "content": section_content,
                "chapter": chapter_number,
                "start_position": match.start(),
                "end_position": match.end(),
                "subsections": subsections,
                "full_text": match.group(0)
            })

        return sorted(sections, key=lambda x: int(x["number"]) if x["number"].isdigit() else 999)

    def _extract_subsections(self, section_content: str) -> List[Dict[str, Any]]:
        """Extract subsections from section content."""
        subsections = []

        # Pattern for subsections: "(1)", "(2)", etc.
        subsection_pattern = r'\((\d+)\)\s+(.*?)(?=\(\d+\)|$)'

        matches = re.finditer(subsection_pattern, section_content, re.DOTALL)

        for match in matches:
            subsection_number = match.group(1)
            subsection_content = match.group(2).strip()

            # Extract clauses within this subsection
            clauses = self._extract_clauses(subsection_content)

            subsections.append({
                "number": subsection_number,
                "content": subsection_content,
                "clauses": clauses
            })

        return subsections

    def _extract_clauses(self, subsection_content: str) -> List[Dict[str, Any]]:
        """Extract clauses from subsection content."""
        clauses = []

        # Pattern for clauses: "(a)", "(b)", etc.
        clause_pattern = r'\(([a-z]+)\)\s+(.*?)(?=\([a-z]+\)|$)'

        matches = re.finditer(clause_pattern, subsection_content, re.DOTALL)

        for match in matches:
            clause_letter = match.group(1)
            clause_content = match.group(2).strip()

            # Extract sub-clauses if present
            sub_clauses = self._extract_sub_clauses(clause_content)

            clauses.append({
                "letter": clause_letter,
                "content": clause_content,
                "sub_clauses": sub_clauses
            })

        return clauses

    def _extract_sub_clauses(self, clause_content: str) -> List[Dict[str, Any]]:
        """Extract sub-clauses from clause content."""
        sub_clauses = []

        # Pattern for sub-clauses: "(i)", "(ii)", etc.
        sub_clause_pattern = r'\(([ivx]+)\)\s+(.*?)(?=\([ivx]+\)|$)'

        matches = re.finditer(sub_clause_pattern, clause_content, re.DOTALL)

        for match in matches:
            sub_clause_number = match.group(1)
            sub_clause_content = match.group(2).strip()

            sub_clauses.append({
                "number": sub_clause_number,
                "content": sub_clause_content
            })

        return sub_clauses

    def _clean_section_title(self, title: str) -> str:
        """Clean and format section title."""
        # Remove common suffixes and clean up
        title = re.sub(r'[.—]+$', '', title.strip())
        title = re.sub(r'\s+', ' ', title)
        return title.strip()

    def _split_title_content(self, text: str) -> Tuple[str, str]:
        """Split combined title and content."""
        # Look for common patterns that separate title from content
        separators = ['.—', '.', ':', '—']

        for sep in separators:
            if sep in text:
                parts = text.split(sep, 1)
                if len(parts) == 2:
                    return parts[0].strip(), parts[1].strip()

        # If no separator found, treat first sentence as title
        sentences = text.split('. ')
        if len(sentences) > 1:
            return sentences[0].strip(), '. '.join(sentences[1:]).strip()

        # Fallback: no clear title
        return "", text.strip()

    def _find_section_chapter(self, section_position: int, chapters: List[Dict[str, Any]]) -> Optional[str]:
        """Determine which chapter a section belongs to based on position."""
        for chapter in chapters:
            if (chapter["start_position"] <= section_position <= chapter["end_position"]):
                return chapter["number"]

        return None  # Section is outside any chapter

    def _build_hierarchy(self, chapters: List[Dict[str, Any]], sections: List[Dict[str, Any]]) -> None:
        """Build the hierarchical relationships between chapters and sections."""
        # Group sections by chapter
        for section in sections:
            chapter_number = section.get("chapter")
            if chapter_number:
                # Find the corresponding chapter and add this section
                for chapter in chapters:
                    if chapter["number"] == chapter_number:
                        chapter["sections"].append(section["number"])
                        break

    def get_structure_summary(self, structure: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a summary of the document structure."""
        chapters = structure.get("chapters", [])
        sections = structure.get("sections", [])

        summary = {
            "total_chapters": len(chapters),
            "total_sections": len(sections),
            "sections_with_subsections": sum(1 for s in sections if s.get("subsections")),
            "chapter_titles": [c.get("title", "") for c in chapters],
            "section_distribution": {}
        }

        # Count sections per chapter
        for chapter in chapters:
            chapter_sections = len(chapter.get("sections", []))
            summary["section_distribution"][chapter["number"]] = chapter_sections

        return summary