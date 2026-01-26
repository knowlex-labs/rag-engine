"""
Entity Parser
Extracts legal entities (authorities, penalties, definitions) from legal documents.
"""

import re
from typing import Dict, List, Any, Optional, Set


class EntityParser:
    """
    Parser for extracting legal entities from document content.
    Focuses on authorities, penalties, definitions, and other key legal concepts.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.debug = config.get("debug_mode", False)

        # Pre-compiled patterns for efficiency
        self._authority_patterns = self._compile_authority_patterns()
        self._penalty_patterns = self._compile_penalty_patterns()
        self._definition_patterns = self._compile_definition_patterns()

    def extract_entities(self, text: str, structure: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract all types of entities from the document.

        Args:
            text: Full document text
            structure: Parsed document structure (chapters, sections)

        Returns:
            Dict containing lists of extracted entities
        """
        sections = structure.get("sections", [])

        # Extract different types of entities
        authorities = self._extract_authorities(text, sections)
        penalties = self._extract_penalties(text, sections)
        definitions = self._extract_definitions(text, sections)
        procedures = self._extract_procedures(text, sections)

        return {
            "authorities": authorities,
            "penalties": penalties,
            "definitions": definitions,
            "procedures": procedures
        }

    def _compile_authority_patterns(self) -> List[re.Pattern]:
        """Compile regex patterns for identifying authorities."""
        patterns = [
            r'\b([A-Z][a-z]+\s+(?:Board|Authority|Commission|Committee|Tribunal|Government))\b',
            r'\b(Central\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
            r'\b(State\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
            r'\b([A-Z][a-z]+\s+Pollution\s+Control\s+Board)\b',
            r'\b(Appellate\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
            r'\b(High\s+Court|Supreme\s+Court)\b'
        ]

        return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]

    def _compile_penalty_patterns(self) -> List[re.Pattern]:
        """Compile regex patterns for identifying penalties."""
        patterns = [
            r'imprisonment\s+for\s+a?\s*term\s+(?:which\s+)?(?:may\s+)?(?:extend\s+to\s+)?([^,\.]+)',
            r'fine\s+(?:which\s+)?(?:may\s+)?(?:extend\s+to\s+)?(?:rupees\s+)?([^,\.]+)',
            r'punishable\s+with\s+([^,\.]+)',
            r'penalty\s+of\s+(?:rupees\s+)?([^,\.]+)',
            r'₹\s*(\d+(?:,\d+)*)',
            r'rupees\s+(\d+(?:,\d+)*)',
        ]

        return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]

    def _compile_definition_patterns(self) -> List[re.Pattern]:
        """Compile regex patterns for identifying definitions."""
        patterns = [
            r'"([^"]+)"\s+means\s+([^;]+)',
            r'\(([a-z]+)\)\s+"([^"]+)"\s+means\s+([^;]+)',
            r'Definitions\.\s*—?\s*In\s+this\s+Act',
            r'\b([A-Za-z\s]+)\s+means\s+([^;\.]+)'
        ]

        return [re.compile(pattern, re.IGNORECASE | re.DOTALL) for pattern in patterns]

    def _extract_authorities(self, text: str, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract authority entities from the document."""
        authorities = []
        seen_authorities = set()

        # Search through each section for authorities
        for section in sections:
            section_content = section.get("content", "")
            section_number = section.get("number", "")

            # Find authorities mentioned in this section
            for pattern in self._authority_patterns:
                matches = pattern.finditer(section_content)

                for match in matches:
                    authority_name = self._normalize_authority_name(match.group(1))

                    # Skip if normalization returned None (invalid authority name)
                    if authority_name and authority_name not in seen_authorities:
                        seen_authorities.add(authority_name)

                        # Extract additional information about this authority
                        authority_info = self._extract_authority_details(
                            authority_name, section_content, section_number
                        )

                        authorities.append(authority_info)

        return authorities

    def _extract_penalties(self, text: str, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract penalty information from the document."""
        penalties = []

        # Look specifically in penalty/punishment sections
        penalty_sections = [s for s in sections if self._is_penalty_section(s)]

        for section in penalty_sections:
            section_content = section.get("content", "")
            section_number = section.get("number", "")
            section_title = section.get("title", "")

            # Extract penalty details
            penalty_info = self._parse_penalty_section(section_content, section_number, section_title)
            if penalty_info:
                penalties.extend(penalty_info)

        return penalties

    def _extract_definitions(self, text: str, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract definitions from the document."""
        definitions = []

        # Look for definitions section
        definitions_section = None
        for section in sections:
            if "definition" in section.get("title", "").lower():
                definitions_section = section
                break

        if definitions_section:
            definitions.extend(self._parse_definitions_section(definitions_section))

        # Also look for inline definitions throughout the document
        definitions.extend(self._extract_inline_definitions(text, sections))

        return definitions

    def _extract_procedures(self, text: str, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract procedural information from the document."""
        procedures = []

        # Look for sections that describe procedures
        procedure_keywords = ["procedure", "process", "appeal", "application", "hearing"]

        for section in sections:
            section_title = section.get("title", "").lower()
            section_content = section.get("content", "")

            if any(keyword in section_title for keyword in procedure_keywords):
                procedure_info = self._parse_procedure_section(section)
                if procedure_info:
                    procedures.append(procedure_info)

        return procedures

    def _normalize_authority_name(self, name: str) -> str:
        """Normalize authority names for consistency."""
        # Remove extra whitespace
        name = re.sub(r'\s+', ' ', name.strip())

        # Skip if name is too long or contains common stopwords
        if len(name) > 100 or any(word in name.lower() for word in ['shall', 'may', 'improve', 'prevent', 'control']):
            return None

        # Standardize common variations
        name = re.sub(r'\bPollution Control Board\b', 'Board', name)
        name = re.sub(r'\bGovernment\b', 'Govt', name)

        # Clean up common parsing artifacts
        name = re.sub(r'\b(?:Under|Section|This|Act|For|The|And|To|Of)\b', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s+', ' ', name).strip()

        # Skip if name became too short or empty
        if len(name) < 3:
            return None

        return name.title()

    def _extract_authority_details(self, name: str, content: str, section_number: str) -> Dict[str, Any]:
        """Extract detailed information about an authority."""
        # Basic authority information
        authority_info = {
            "name": name,
            "type": self._classify_authority_type(name),
            "mentioned_in_section": section_number,
            "powers": [],
            "functions": [],
            "jurisdiction": ""
        }

        # Extract powers and functions mentioned in the same context
        context = self._extract_authority_context(name, content)

        if context:
            authority_info["powers"] = self._extract_powers_from_context(context)
            authority_info["functions"] = self._extract_functions_from_context(context)
            authority_info["jurisdiction"] = self._extract_jurisdiction_from_context(context)

        return authority_info

    def _classify_authority_type(self, name: str) -> str:
        """Classify the type of authority."""
        name_lower = name.lower()

        if "board" in name_lower:
            return "board"
        elif "court" in name_lower:
            return "court"
        elif "tribunal" in name_lower:
            return "tribunal"
        elif "government" in name_lower:
            return "government"
        elif "commission" in name_lower:
            return "commission"
        elif "authority" in name_lower:
            return "authority"
        else:
            return "other"

    def _is_penalty_section(self, section: Dict[str, Any]) -> bool:
        """Determine if a section contains penalty information."""
        title = section.get("title", "").lower()
        penalty_keywords = ["penalty", "punishment", "offence", "fine", "imprisonment"]

        return any(keyword in title for keyword in penalty_keywords)

    def _parse_penalty_section(self, content: str, section_number: str, section_title: str) -> List[Dict[str, Any]]:
        """Parse penalty details from a penalty section."""
        penalties = []

        # Check if this is actually a penalty section by looking for penalty keywords
        penalty_indicators = ["punishable", "imprisonment", "fine", "penalty"]
        if not any(indicator in content.lower() for indicator in penalty_indicators):
            return penalties

        # Extract imprisonment terms - improved patterns
        imprisonment_patterns = [
            r'imprisonment\s+for\s+a?\s*term\s+(?:which\s+)?(?:shall\s+not\s+be\s+less\s+than\s+([^,]+)\s+but\s+)?(?:which\s+)?(?:may\s+)?(?:extend\s+to\s+)?([^,\.]+)',
            r'imprisonment\s+for\s+a?\s*term\s+(?:which\s+)?(?:may\s+)?(?:extend\s+to\s+)?([^,\.]+)',
        ]

        for pattern in imprisonment_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                if match.lastindex == 2:  # Has both minimum and maximum
                    min_term = match.group(1).strip()
                    max_term = match.group(2).strip()
                    term = f"{min_term} to {max_term}"
                else:  # Has only one term
                    term = match.group(1).strip()

                penalties.append({
                    "type": "imprisonment",
                    "term": term,
                    "section": section_number,
                    "offense": section_title,
                    "raw_text": match.group(0)
                })

        # Extract fine amounts - improved patterns
        fine_patterns = [
            r'fine\s+(?:which\s+)?(?:may\s+)?(?:extend\s+to\s+)?(?:rupees\s+)?([^,\.]+)',
            r'with\s+fine(?:\s+of\s+(?:rupees\s+)?([^,\.]+))?',
            r'₹\s*(\d+(?:,\d+)*)',
            r'rupees\s+(\d+(?:,\d+)*)',
        ]

        for pattern in fine_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                if match.group(1):
                    amount = match.group(1).strip()
                else:
                    amount = "unspecified"

                penalties.append({
                    "type": "fine",
                    "amount": amount,
                    "section": section_number,
                    "offense": section_title,
                    "raw_text": match.group(0)
                })

        return penalties

    def _parse_definitions_section(self, section: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse definitions from the definitions section."""
        definitions = []
        content = section.get("content", "")

        # Pattern for definitions: "(a) "term" means definition;"
        definition_pattern = r'\([a-z]\)\s*"([^"]+)"\s+means\s+([^;]+);?'
        matches = re.finditer(definition_pattern, content, re.IGNORECASE | re.DOTALL)

        for match in matches:
            term = match.group(1).strip()
            definition = match.group(2).strip()

            definitions.append({
                "term": term,
                "definition": definition,
                "section": section.get("number", ""),
                "context": "formal_definition"
            })

        return definitions

    def _extract_inline_definitions(self, text: str, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract definitions found inline throughout the document."""
        definitions = []

        # Pattern for inline definitions: "X means Y"
        inline_pattern = r'\b([A-Za-z\s]+)\s+means\s+([^;\.]+)'
        matches = re.finditer(inline_pattern, text, re.IGNORECASE)

        for match in matches:
            term = match.group(1).strip()
            definition = match.group(2).strip()

            # Skip if term is too generic or too long
            if 3 <= len(term.split()) <= 5:
                definitions.append({
                    "term": term,
                    "definition": definition,
                    "section": "inline",
                    "context": "inline_definition"
                })

        return definitions

    def _parse_procedure_section(self, section: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse procedural information from a section."""
        content = section.get("content", "")
        title = section.get("title", "")

        if not content.strip():
            return None

        procedure_info = {
            "name": title,
            "section": section.get("number", ""),
            "description": content[:200] + "..." if len(content) > 200 else content,
            "steps": self._extract_procedure_steps(content),
            "timeline": self._extract_timeline(content),
            "requirements": self._extract_requirements(content)
        }

        return procedure_info

    def _extract_authority_context(self, name: str, content: str) -> str:
        """Extract the context around an authority mention."""
        # Find the sentence containing the authority name
        sentences = re.split(r'[.;]', content)

        for sentence in sentences:
            if name.lower() in sentence.lower():
                return sentence.strip()

        return ""

    def _extract_powers_from_context(self, context: str) -> List[str]:
        """Extract powers from authority context."""
        power_keywords = ["power", "authority", "may", "shall", "can"]
        powers = []

        if any(keyword in context.lower() for keyword in power_keywords):
            # Simple extraction - can be enhanced
            powers.append(context[:100] + "..." if len(context) > 100 else context)

        return powers

    def _extract_functions_from_context(self, context: str) -> List[str]:
        """Extract functions from authority context."""
        function_keywords = ["function", "duty", "responsibility", "shall"]
        functions = []

        if any(keyword in context.lower() for keyword in function_keywords):
            functions.append(context[:100] + "..." if len(context) > 100 else context)

        return functions

    def _extract_jurisdiction_from_context(self, context: str) -> str:
        """Extract jurisdiction information from context."""
        jurisdiction_keywords = ["state", "central", "union territory", "district"]

        for keyword in jurisdiction_keywords:
            if keyword in context.lower():
                return keyword.title()

        return "Unknown"

    def _extract_procedure_steps(self, content: str) -> List[str]:
        """Extract procedural steps from content."""
        # Look for numbered or bulleted steps
        step_pattern = r'(?:(?:\d+\.|\([a-z]\)|\([i]+\))\s+)([^\.]+\.)'
        matches = re.finditer(step_pattern, content, re.IGNORECASE)

        steps = [match.group(1).strip() for match in matches]
        return steps[:5]  # Limit to first 5 steps

    def _extract_timeline(self, content: str) -> Optional[str]:
        """Extract timeline information from content."""
        timeline_pattern = r'(?:within\s+)?(\d+\s+(?:days?|months?|years?))'
        match = re.search(timeline_pattern, content, re.IGNORECASE)

        return match.group(1) if match else None

    def _extract_requirements(self, content: str) -> List[str]:
        """Extract requirements from content."""
        requirement_keywords = ["require", "must", "shall", "necessary"]
        requirements = []

        sentences = re.split(r'[.;]', content)
        for sentence in sentences:
            if any(keyword in sentence.lower() for keyword in requirement_keywords):
                requirements.append(sentence.strip())

        return requirements[:3]  # Limit to first 3 requirements