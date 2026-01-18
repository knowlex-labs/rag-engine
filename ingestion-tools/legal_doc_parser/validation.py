"""
Parsing Validation
Validates that parsed content accurately represents the source document.
"""

import re
from typing import Dict, List, Any, Set
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Container for validation results."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    stats: Dict[str, Any]


class ParsingValidator:
    """
    Validator to ensure parsing accuracy and completeness.
    Focuses on structural integrity and content preservation.
    """

    def __init__(self):
        self.validation_rules = {
            "structure": True,
            "content_preservation": True,
            "cross_references": True,
            "entity_extraction": True
        }

    def validate(self, parsed_doc, original_text: str) -> Dict[str, Any]:
        """
        Comprehensive validation of parsed document against original text.

        Args:
            parsed_doc: ParsedDocument object
            original_text: Original document text

        Returns:
            Dict containing validation results
        """
        errors = []
        warnings = []

        # Run different validation checks
        structure_result = self._validate_structure(parsed_doc, original_text)
        content_result = self._validate_content_preservation(parsed_doc, original_text)
        entity_result = self._validate_entity_extraction(parsed_doc, original_text)
        reference_result = self._validate_cross_references(parsed_doc, original_text)

        # Collect all errors and warnings
        errors.extend(structure_result.errors)
        errors.extend(content_result.errors)
        errors.extend(entity_result.errors)
        errors.extend(reference_result.errors)

        warnings.extend(structure_result.warnings)
        warnings.extend(content_result.warnings)
        warnings.extend(entity_result.warnings)
        warnings.extend(reference_result.warnings)

        # Calculate overall validation stats
        stats = {
            "total_errors": len(errors),
            "total_warnings": len(warnings),
            "structure_validity": structure_result.is_valid,
            "content_preservation": content_result.is_valid,
            "entity_extraction": entity_result.is_valid,
            "cross_reference_accuracy": reference_result.is_valid,
            "overall_score": self._calculate_validation_score([
                structure_result, content_result, entity_result, reference_result
            ])
        }

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "stats": stats
        }

    def _validate_structure(self, parsed_doc, original_text: str) -> ValidationResult:
        """Validate that document structure is correctly parsed."""
        errors = []
        warnings = []

        # Check if we found the expected number of chapters and sections
        original_chapters = self._count_chapters_in_text(original_text)
        original_sections = self._count_sections_in_text(original_text)

        parsed_chapters = len(parsed_doc.chapters)
        parsed_sections = len(parsed_doc.sections)

        # Validate chapter count
        if original_chapters > 0 and parsed_chapters != original_chapters:
            errors.append(
                f"Chapter count mismatch: found {parsed_chapters}, expected {original_chapters}"
            )

        # Validate section count (allow some tolerance for complex numbering)
        section_diff = abs(parsed_sections - original_sections)
        if section_diff > 2:  # Allow small variance
            errors.append(
                f"Section count mismatch: found {parsed_sections}, expected {original_sections}"
            )
        elif section_diff > 0:
            warnings.append(
                f"Minor section count difference: found {parsed_sections}, expected {original_sections}"
            )

        # Validate that all sections have content
        empty_sections = [s for s in parsed_doc.sections if not s.get("content", "").strip()]
        if empty_sections:
            errors.append(f"Found {len(empty_sections)} sections with no content")

        # Validate section numbering sequence
        section_numbers = [int(s["number"]) for s in parsed_doc.sections if s["number"].isdigit()]
        if section_numbers and section_numbers != list(range(min(section_numbers), max(section_numbers) + 1)):
            warnings.append("Section numbering sequence appears to have gaps")

        is_valid = len(errors) == 0

        return ValidationResult(is_valid, errors, warnings, {
            "original_chapters": original_chapters,
            "parsed_chapters": parsed_chapters,
            "original_sections": original_sections,
            "parsed_sections": parsed_sections
        })

    def _validate_content_preservation(self, parsed_doc, original_text: str) -> ValidationResult:
        """Validate that content is preserved during parsing."""
        errors = []
        warnings = []

        # Calculate content preservation percentage
        original_word_count = len(original_text.split())
        parsed_word_count = 0

        # Count words in all parsed content
        for section in parsed_doc.sections:
            parsed_word_count += len(section.get("content", "").split())

        # Add words from chapters
        for chapter in parsed_doc.chapters:
            parsed_word_count += len(chapter.get("content", "").split())

        # Calculate preservation ratio
        if original_word_count > 0:
            preservation_ratio = parsed_word_count / original_word_count
        else:
            preservation_ratio = 0

        # Check preservation threshold
        if preservation_ratio < 0.8:  # Less than 80% preserved
            errors.append(
                f"Low content preservation: only {preservation_ratio:.1%} of content preserved"
            )
        elif preservation_ratio < 0.9:  # Less than 90% preserved
            warnings.append(
                f"Moderate content loss: {preservation_ratio:.1%} of content preserved"
            )

        # Check for critical content loss (key sections missing)
        critical_keywords = ["penalty", "definition", "authority", "board", "power"]
        missing_keywords = []

        for keyword in critical_keywords:
            if keyword in original_text.lower():
                # Check if keyword appears in parsed content
                found_in_parsed = any(
                    keyword in section.get("content", "").lower()
                    for section in parsed_doc.sections
                )
                if not found_in_parsed:
                    missing_keywords.append(keyword)

        if missing_keywords:
            errors.append(f"Critical content missing: {', '.join(missing_keywords)}")

        is_valid = len(errors) == 0

        return ValidationResult(is_valid, errors, warnings, {
            "original_word_count": original_word_count,
            "parsed_word_count": parsed_word_count,
            "preservation_ratio": preservation_ratio,
            "missing_keywords": missing_keywords
        })

    def _validate_entity_extraction(self, parsed_doc, original_text: str) -> ValidationResult:
        """Validate that entities are correctly extracted."""
        errors = []
        warnings = []

        # Check for expected authorities in legal documents
        expected_authorities = self._find_expected_authorities(original_text)
        extracted_authorities = [auth["name"] for auth in parsed_doc.authorities]

        missing_authorities = []
        for expected_auth in expected_authorities:
            if not any(expected_auth.lower() in extracted.lower() for extracted in extracted_authorities):
                missing_authorities.append(expected_auth)

        if missing_authorities:
            warnings.append(f"Potentially missing authorities: {', '.join(missing_authorities)}")

        # Check for penalty extraction if penalty sections exist
        if self._has_penalty_sections(original_text) and not parsed_doc.penalties:
            errors.append("Document contains penalty sections but no penalties were extracted")

        # Check for definition extraction if definitions section exists
        if self._has_definitions_section(original_text) and not parsed_doc.definitions:
            errors.append("Document contains definitions section but no definitions were extracted")

        is_valid = len(errors) == 0

        return ValidationResult(is_valid, errors, warnings, {
            "expected_authorities": expected_authorities,
            "extracted_authorities": len(extracted_authorities),
            "extracted_penalties": len(parsed_doc.penalties),
            "extracted_definitions": len(parsed_doc.definitions)
        })

    def _validate_cross_references(self, parsed_doc, original_text: str) -> ValidationResult:
        """Validate cross-reference extraction and accuracy."""
        errors = []
        warnings = []

        # Count cross-references in original text
        original_refs = self._count_cross_references(original_text)
        extracted_refs = len(parsed_doc.cross_references)

        # Check if we extracted a reasonable number of cross-references
        if original_refs > 0 and extracted_refs == 0:
            errors.append("Document contains cross-references but none were extracted")
        elif original_refs > 0 and extracted_refs < original_refs * 0.5:
            warnings.append(
                f"Low cross-reference extraction: found {extracted_refs}, expected around {original_refs}"
            )

        # Validate that referenced sections exist in the parsed document
        section_numbers = set(section["number"] for section in parsed_doc.sections)

        invalid_refs = []
        for ref in parsed_doc.cross_references:
            target_ref = ref.get("target_reference", "")
            # Simple check for numeric section references
            if target_ref.isdigit() and target_ref not in section_numbers:
                invalid_refs.append(target_ref)

        if invalid_refs:
            errors.append(f"Cross-references to non-existent sections: {', '.join(invalid_refs)}")

        is_valid = len(errors) == 0

        return ValidationResult(is_valid, errors, warnings, {
            "original_cross_references": original_refs,
            "extracted_cross_references": extracted_refs,
            "invalid_references": len(invalid_refs)
        })

    def _count_chapters_in_text(self, text: str) -> int:
        """Count chapters in the original text."""
        chapter_pattern = r'\bCHAPTER\s+(?:[IVX]+|[A-Z]+|\d+)\b'
        return len(re.findall(chapter_pattern, text, re.IGNORECASE))

    def _count_sections_in_text(self, text: str) -> int:
        """Count sections in the original text."""
        # Pattern for section headers at start of line
        section_pattern = r'^\d+\.\s+'
        return len(re.findall(section_pattern, text, re.MULTILINE))

    def _find_expected_authorities(self, text: str) -> List[str]:
        """Find expected authorities that should be extracted."""
        authority_patterns = [
            r'Central\s+(?:Pollution\s+Control\s+)?Board',
            r'State\s+(?:Pollution\s+Control\s+)?Board',
            r'Central\s+Government',
            r'State\s+Government',
            r'High\s+Court',
            r'Supreme\s+Court'
        ]

        expected = set()
        for pattern in authority_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                expected.add(match.group(0))

        return list(expected)

    def _has_penalty_sections(self, text: str) -> bool:
        """Check if document contains penalty sections."""
        penalty_keywords = ["penalty", "punishment", "offence", "fine", "imprisonment"]
        return any(keyword in text.lower() for keyword in penalty_keywords)

    def _has_definitions_section(self, text: str) -> bool:
        """Check if document contains a definitions section."""
        return "definitions" in text.lower() and "means" in text.lower()

    def _count_cross_references(self, text: str) -> int:
        """Count cross-references in the original text."""
        ref_patterns = [
            r'\bsection\s+\d+',
            r'\bsub-section\s+\(\d+\)',
            r'\bclause\s+\([a-z]+\)',
        ]

        total_refs = 0
        for pattern in ref_patterns:
            total_refs += len(re.findall(pattern, text, re.IGNORECASE))

        return total_refs

    def _calculate_validation_score(self, results: List[ValidationResult]) -> float:
        """Calculate an overall validation score."""
        if not results:
            return 0.0

        valid_count = sum(1 for result in results if result.is_valid)
        return valid_count / len(results)

    def generate_validation_report(self, validation_result: Dict[str, Any]) -> str:
        """Generate a human-readable validation report."""
        report_lines = []

        report_lines.append("=== PARSING VALIDATION REPORT ===")
        report_lines.append(f"Overall Status: {'PASS' if validation_result['is_valid'] else 'FAIL'}")
        report_lines.append(f"Validation Score: {validation_result['stats']['overall_score']:.1%}")
        report_lines.append("")

        if validation_result["errors"]:
            report_lines.append("ERRORS:")
            for error in validation_result["errors"]:
                report_lines.append(f"  ❌ {error}")
            report_lines.append("")

        if validation_result["warnings"]:
            report_lines.append("WARNINGS:")
            for warning in validation_result["warnings"]:
                report_lines.append(f"  ⚠️  {warning}")
            report_lines.append("")

        # Add stats summary
        stats = validation_result["stats"]
        report_lines.append("STATISTICS:")
        report_lines.append(f"  Structure Validity: {'✓' if stats['structure_validity'] else '✗'}")
        report_lines.append(f"  Content Preservation: {'✓' if stats['content_preservation'] else '✗'}")
        report_lines.append(f"  Entity Extraction: {'✓' if stats['entity_extraction'] else '✗'}")
        report_lines.append(f"  Cross-Reference Accuracy: {'✓' if stats['cross_reference_accuracy'] else '✗'}")

        return "\n".join(report_lines)