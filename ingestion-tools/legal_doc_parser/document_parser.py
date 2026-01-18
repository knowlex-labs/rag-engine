"""
Main Document Parser
Orchestrates the parsing of legal documents into structured data.
"""

import re
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class ParsedDocument:
    """Container for parsed legal document data."""
    act_name: str
    act_year: int
    act_number: str
    preamble: str
    chapters: List[Dict[str, Any]]
    sections: List[Dict[str, Any]]
    definitions: List[Dict[str, Any]]
    authorities: List[Dict[str, Any]]
    penalties: List[Dict[str, Any]]
    cross_references: List[Dict[str, Any]]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class LegalDocumentParser:
    """
    Main parser class that coordinates all parsing operations.
    Designed to be flexible and extensible for different document types.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.parsing_stats = {
            "total_sections": 0,
            "extracted_authorities": 0,
            "extracted_penalties": 0,
            "cross_references": 0,
            "errors": []
        }

    def _default_config(self) -> Dict[str, Any]:
        """Default configuration for parsing."""
        return {
            "preserve_formatting": True,
            "extract_cross_refs": True,
            "validate_structure": True,
            "debug_mode": False,
            "use_llm_extraction": True,  # Enable LLM extraction by default
            "llm_model": "gpt-4o-mini"  # Cost-effective model
        }

    def parse_document(self, text: str, filename: str = "") -> ParsedDocument:
        """
        Main entry point for parsing a legal document.

        Args:
            text: Raw text content of the document
            filename: Optional filename for metadata

        Returns:
            ParsedDocument containing all extracted information
        """
        # Reset stats for new document
        self.parsing_stats = {
            "total_sections": 0,
            "extracted_authorities": 0,
            "extracted_penalties": 0,
            "cross_references": 0,
            "errors": []
        }

        try:
            # Use LLM extraction if enabled and API key is available
            if self.config.get("use_llm_extraction", True):
                try:
                    return self._parse_with_llm(text, filename)
                except Exception as llm_error:
                    if "api_key" in str(llm_error).lower():
                        print("⚠️  OpenAI API key not found. Falling back to regex extraction.")
                        print("   Set OPENAI_API_KEY environment variable for LLM extraction.")
                    else:
                        print(f"⚠️  LLM extraction failed: {llm_error}")
                        print("   Falling back to regex extraction.")
                    # Continue with regex extraction below

            # Step 1: Extract basic document metadata
            metadata = self._extract_document_metadata(text, filename)

            # Step 2: Parse document structure (chapters, sections)
            structure = self._parse_document_structure(text)

            # Step 3: Extract entities (authorities, penalties, definitions)
            entities = self._extract_entities(text, structure)

            # Step 4: Find cross-references
            cross_refs = self._extract_cross_references(text, structure)

            # Step 5: Create parsed document object
            parsed_doc = ParsedDocument(
                act_name=metadata.get("act_name", ""),
                act_year=metadata.get("act_year", 0),
                act_number=metadata.get("act_number", ""),
                preamble=metadata.get("preamble", ""),
                chapters=structure.get("chapters", []),
                sections=structure.get("sections", []),
                definitions=entities.get("definitions", []),
                authorities=entities.get("authorities", []),
                penalties=entities.get("penalties", []),
                cross_references=cross_refs,
                metadata={
                    **metadata,
                    "parsing_stats": self.parsing_stats,
                    "filename": filename
                }
            )

            # Step 6: Validate parsed content if enabled
            if self.config.get("validate_structure", True):
                self._validate_parsed_content(parsed_doc, text)

            return parsed_doc

        except Exception as e:
            self.parsing_stats["errors"].append(f"Critical parsing error: {str(e)}")
            raise Exception(f"Failed to parse document: {str(e)}") from e

    def _parse_with_llm(self, text: str, filename: str) -> ParsedDocument:
        """Parse document using LLM extraction for higher accuracy."""
        from .llm_extractor import LLMLegalExtractor

        if self.config.get("debug_mode", False):
            print("Using LLM extraction for higher accuracy...")

        # Initialize LLM extractor
        llm_extractor = LLMLegalExtractor(self.config)

        # Extract all data using LLM
        extraction_result = llm_extractor.extract_from_document(text, filename)

        # Update parsing stats
        self.parsing_stats["total_sections"] = len(extraction_result.sections)
        self.parsing_stats["extracted_authorities"] = len(extraction_result.authorities)
        self.parsing_stats["extracted_penalties"] = len(extraction_result.penalties)
        self.parsing_stats["cross_references"] = len(extraction_result.cross_references)

        # Extract chapters from sections (LLM provides flat sections, we need to group by chapters)
        chapters = self._group_sections_into_chapters(extraction_result.sections)

        # Create parsed document
        parsed_doc = ParsedDocument(
            act_name=extraction_result.metadata.get("act_name", ""),
            act_year=extraction_result.metadata.get("act_year", 0),
            act_number=extraction_result.metadata.get("act_number", ""),
            preamble=extraction_result.metadata.get("preamble", ""),
            chapters=chapters,
            sections=extraction_result.sections,
            definitions=extraction_result.definitions,
            authorities=extraction_result.authorities,
            penalties=extraction_result.penalties,
            cross_references=extraction_result.cross_references,
            metadata={
                **extraction_result.metadata,
                "parsing_stats": self.parsing_stats,
                "filename": filename,
                "extraction_method": "llm"
            }
        )

        # Validate if enabled
        if self.config.get("validate_structure", True):
            self._validate_parsed_content(parsed_doc, text)

        return parsed_doc

    def _group_sections_into_chapters(self, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group sections into chapters based on chapter information."""
        chapters = {}

        for section in sections:
            chapter_num = section.get("chapter")
            if chapter_num:
                if chapter_num not in chapters:
                    chapters[chapter_num] = {
                        "number": chapter_num,
                        "title": f"CHAPTER {chapter_num}",
                        "content": "",
                        "start_position": section.get("start_position", 0),
                        "end_position": section.get("end_position", 0),
                        "sections": []
                    }
                chapters[chapter_num]["sections"].append(section["number"])

        return list(chapters.values())

    def _extract_document_metadata(self, text: str, filename: str) -> Dict[str, Any]:
        """Extract basic document information (title, year, etc.)."""
        metadata = {"filename": filename}

        # Extract act name and year from title
        # Pattern: "THE [NAME] ACT, YEAR" or "[NAME] ACT, YEAR"
        title_pattern = r"(?:THE\s+)?(.+?)\s+ACT,?\s+(\d{4})"
        title_match = re.search(title_pattern, text[:1000], re.IGNORECASE)

        if title_match:
            metadata["act_name"] = title_match.group(1).strip().title()
            metadata["act_year"] = int(title_match.group(2))

        # Extract act number if present
        # Pattern: "NO. XX OF YEAR" or "ACT NO. XX OF YEAR"
        number_pattern = r"(?:ACT\s+)?NO\.?\s+(\d+)\s+OF\s+(\d{4})"
        number_match = re.search(number_pattern, text[:1000], re.IGNORECASE)

        if number_match:
            metadata["act_number"] = number_match.group(1)
            if "act_year" not in metadata:
                metadata["act_year"] = int(number_match.group(2))

        # Extract preamble (usually starts with "An Act to" or "WHEREAS")
        preamble_pattern = r"((?:An Act to|WHEREAS).+?(?=CHAPTER|BE it enacted))"
        preamble_match = re.search(preamble_pattern, text, re.DOTALL | re.IGNORECASE)

        if preamble_match:
            metadata["preamble"] = self._clean_text(preamble_match.group(1))

        return metadata

    def _parse_document_structure(self, text: str) -> Dict[str, Any]:
        """Parse the hierarchical structure of the document."""
        from .structure_parser import DocumentStructureParser

        parser = DocumentStructureParser(self.config)
        structure = parser.parse_structure(text)

        # Update stats
        self.parsing_stats["total_sections"] = len(structure.get("sections", []))

        return structure

    def _extract_entities(self, text: str, structure: Dict[str, Any]) -> Dict[str, Any]:
        """Extract legal entities from the document."""
        from .entity_parser import EntityParser

        parser = EntityParser(self.config)
        entities = parser.extract_entities(text, structure)

        # Update stats
        self.parsing_stats["extracted_authorities"] = len(entities.get("authorities", []))
        self.parsing_stats["extracted_penalties"] = len(entities.get("penalties", []))

        return entities

    def _extract_cross_references(self, text: str, structure: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract cross-references between sections."""
        if not self.config.get("extract_cross_refs", True):
            return []

        cross_refs = []

        # Pattern for section references: "section X", "sub-section (Y)", etc.
        ref_pattern = r"\b(?:section|sub-section|clause)\s+([A-Z0-9\(\)]+)\b"

        for section in structure.get("sections", []):
            section_text = section.get("content", "")
            matches = re.finditer(ref_pattern, section_text, re.IGNORECASE)

            for match in matches:
                cross_refs.append({
                    "source_section": section.get("number"),
                    "source_chapter": section.get("chapter"),
                    "reference_text": match.group(0),
                    "target_reference": match.group(1),
                    "context": self._extract_context(section_text, match.start(), match.end())
                })

        # Update stats
        self.parsing_stats["cross_references"] = len(cross_refs)

        return cross_refs

    def _validate_parsed_content(self, parsed_doc: ParsedDocument, original_text: str) -> None:
        """Validate that parsing captured content correctly."""
        from .validation import ParsingValidator

        validator = ParsingValidator()
        validation_results = validator.validate(parsed_doc, original_text)

        if validation_results.get("errors"):
            self.parsing_stats["errors"].extend(validation_results["errors"])

        if self.config.get("debug_mode", False):
            print("Validation Results:", validation_results)

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove page numbers and headers/footers
        text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
        return text.strip()

    def _extract_context(self, text: str, start: int, end: int, context_size: int = 50) -> str:
        """Extract context around a match for cross-references."""
        context_start = max(0, start - context_size)
        context_end = min(len(text), end + context_size)
        return text[context_start:context_end].strip()

    def get_parsing_stats(self) -> Dict[str, Any]:
        """Get statistics about the last parsing operation."""
        return self.parsing_stats.copy()

    def save_parsed_document(self, parsed_doc: ParsedDocument, output_path: str) -> None:
        """Save parsed document to JSON file."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(parsed_doc.to_dict(), f, indent=2, ensure_ascii=False)

    def load_parsed_document(self, input_path: str) -> ParsedDocument:
        """Load parsed document from JSON file."""
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return ParsedDocument(**data)