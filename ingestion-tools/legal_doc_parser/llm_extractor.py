"""
LLM-based Legal Document Extractor
Uses LLM to extract structured data from legal documents with high accuracy.
"""

import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import openai
from openai import OpenAI


@dataclass
class LLMExtractionResult:
    """Result from LLM extraction."""
    sections: List[Dict[str, Any]]
    authorities: List[Dict[str, Any]]
    penalties: List[Dict[str, Any]]
    definitions: List[Dict[str, Any]]
    cross_references: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class LLMLegalExtractor:
    """
    LLM-based extractor for legal documents.
    Provides much higher accuracy than regex-based extraction.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.debug = config.get("debug_mode", False)

        # Initialize OpenAI client
        self.client = OpenAI()
        self.model = config.get("llm_model", "gpt-4o-mini")  # Cost-effective model

    def extract_from_document(self, text: str, filename: str) -> LLMExtractionResult:
        """
        Extract all structured data from a legal document using LLM.

        Args:
            text: Raw legal document text
            filename: Document filename for metadata

        Returns:
            LLMExtractionResult with all extracted data
        """
        if self.debug:
            print(f"Starting LLM extraction for {filename}")

        # Extract document metadata first
        metadata = self._extract_metadata(text, filename)

        # Extract sections with full content
        sections = self._extract_sections(text)

        # Extract entities from the sections
        authorities = self._extract_authorities(sections, text)
        penalties = self._extract_penalties(sections, text)
        definitions = self._extract_definitions(sections, text)
        cross_references = self._extract_cross_references(sections, text)

        return LLMExtractionResult(
            sections=sections,
            authorities=authorities,
            penalties=penalties,
            definitions=definitions,
            cross_references=cross_references,
            metadata=metadata
        )

    def _extract_metadata(self, text: str, filename: str) -> Dict[str, Any]:
        """Extract document metadata using LLM."""
        prompt = f"""Extract metadata from this legal document:

Document text:
{text[:1000]}...

Extract and return as JSON:
{{
    "act_name": "Full act name",
    "act_year": year as integer,
    "act_number": "act number as string",
    "preamble": "the preamble text"
}}

Be precise with the act name and year."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a legal document analyzer. Extract metadata accurately and return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )

            metadata = json.loads(response.choices[0].message.content.strip())
            metadata["filename"] = filename
            return metadata

        except Exception as e:
            if self.debug:
                print(f"Metadata extraction error: {e}")
            return {
                "filename": filename,
                "act_name": "Unknown",
                "act_year": None,
                "act_number": "Unknown",
                "preamble": ""
            }

    def _extract_sections(self, text: str) -> List[Dict[str, Any]]:
        """Extract all sections with complete content using LLM."""
        prompt = f"""Extract all sections from this legal document with their complete content.

Document text:
{text}

For each section, extract:
1. Section number
2. Section title
3. Complete section content (including all subsections, clauses, and text)
4. Chapter (if mentioned)

Return as JSON array:
[
    {{
        "number": "1",
        "title": "Short title and commencement",
        "content": "Complete section content including all subsections and clauses...",
        "chapter": "I" or null,
        "subsections": [
            {{
                "number": "1",
                "content": "subsection content...",
                "clauses": [
                    {{
                        "letter": "a",
                        "content": "clause content..."
                    }}
                ]
            }}
        ]
    }}
]

Include ALL content for each section. Do not truncate."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a legal document parser. Extract ALL sections with COMPLETE content. Be thorough and precise."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )

            sections = json.loads(response.choices[0].message.content.strip())

            # Add position metadata
            for i, section in enumerate(sections):
                section["start_position"] = i * 100  # Placeholder
                section["end_position"] = (i + 1) * 100
                section["full_text"] = f"{section['number']}. {section['title']}.—{section['content']}"

                # Ensure subsections exist
                if "subsections" not in section:
                    section["subsections"] = []

            return sections

        except Exception as e:
            if self.debug:
                print(f"Section extraction error: {e}")
            return []

    def _extract_authorities(self, sections: List[Dict[str, Any]], text: str) -> List[Dict[str, Any]]:
        """Extract authorities using LLM."""
        authorities_text = "\n\n".join([
            f"Section {s['number']}: {s['title']}\n{s['content']}"
            for s in sections
        ])

        prompt = f"""Extract all authorities, boards, courts, and government bodies from this legal text:

{authorities_text}

For each authority, extract:
1. Name of the authority
2. Type (board, court, government, authority, tribunal, commission, other)
3. Mentioned in which section
4. Powers mentioned
5. Functions mentioned
6. Jurisdiction (Central, State, District, etc.)

Return as JSON array:
[
    {{
        "name": "Central Pollution Control Board",
        "type": "board",
        "mentioned_in_section": "3",
        "powers": ["list of powers"],
        "functions": ["list of functions"],
        "jurisdiction": "Central"
    }}
]"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a legal expert. Extract all authorities, boards, and government bodies mentioned in legal documents."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )

            return json.loads(response.choices[0].message.content.strip())

        except Exception as e:
            if self.debug:
                print(f"Authority extraction error: {e}")
            return []

    def _extract_penalties(self, sections: List[Dict[str, Any]], text: str) -> List[Dict[str, Any]]:
        """Extract penalties using LLM."""
        # Focus on sections likely to contain penalties
        penalty_sections = [
            s for s in sections
            if any(keyword in s.get('title', '').lower() + s.get('content', '').lower()
                   for keyword in ['penalty', 'punishment', 'fine', 'imprisonment', 'punishable'])
        ]

        if not penalty_sections:
            return []

        penalties_text = "\n\n".join([
            f"Section {s['number']}: {s['title']}\n{s['content']}"
            for s in penalty_sections
        ])

        prompt = f"""Extract all penalties and punishments from this legal text:

{penalties_text}

For each penalty, extract:
1. Type (imprisonment, fine, both)
2. Amount or term
3. Section number
4. Offense description
5. Raw text of the penalty

Return as JSON array:
[
    {{
        "type": "imprisonment",
        "term": "one year and six months to six years",
        "section": "37",
        "offense": "Failure to comply with the provisions",
        "raw_text": "shall be punishable with imprisonment..."
    }},
    {{
        "type": "fine",
        "amount": "ten thousand rupees",
        "section": "38",
        "offense": "Destroying property",
        "raw_text": "with fine which may extend to ten thousand rupees"
    }}
]"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a legal expert. Extract all penalties, fines, and punishments from legal text."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )

            return json.loads(response.choices[0].message.content.strip())

        except Exception as e:
            if self.debug:
                print(f"Penalty extraction error: {e}")
            return []

    def _extract_definitions(self, sections: List[Dict[str, Any]], text: str) -> List[Dict[str, Any]]:
        """Extract definitions using LLM."""
        # Focus on sections with definitions
        def_sections = [
            s for s in sections
            if 'definition' in s.get('title', '').lower() or 'means' in s.get('content', '').lower()
        ]

        if not def_sections:
            return []

        definitions_text = "\n\n".join([
            f"Section {s['number']}: {s['title']}\n{s['content']}"
            for s in def_sections
        ])

        prompt = f"""Extract all definitions from this legal text:

{definitions_text}

For each definition, extract:
1. Term being defined
2. Definition text
3. Section number
4. Context (formal_definition, inline_definition)

Return as JSON array:
[
    {{
        "term": "air pollutant",
        "definition": "any solid, liquid or gaseous substance present in the atmosphere...",
        "section": "2",
        "context": "formal_definition"
    }}
]"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a legal expert. Extract all definitions from legal text where terms are defined."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )

            return json.loads(response.choices[0].message.content.strip())

        except Exception as e:
            if self.debug:
                print(f"Definition extraction error: {e}")
            return []

    def _extract_cross_references(self, sections: List[Dict[str, Any]], text: str) -> List[Dict[str, Any]]:
        """Extract cross-references using LLM."""
        all_text = "\n\n".join([
            f"Section {s['number']}: {s['title']}\n{s['content']}"
            for s in sections
        ])

        prompt = f"""Extract all cross-references between sections in this legal text:

{all_text}

Find references like "section 3", "sub-section (2)", "clause (a)" etc.

Return as JSON array:
[
    {{
        "source_section": "3",
        "source_chapter": null,
        "reference_text": "section 3",
        "target_reference": "3",
        "context": "surrounding text explaining the reference"
    }}
]"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a legal expert. Extract cross-references between sections in legal documents."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )

            return json.loads(response.choices[0].message.content.strip())

        except Exception as e:
            if self.debug:
                print(f"Cross-reference extraction error: {e}")
            return []