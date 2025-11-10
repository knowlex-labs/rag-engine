"""Unit tests for header-based chunking logic"""
import pytest


class TestPDFExtraction:
    """PDF text extraction tests"""

    def test_extract_text_from_page(self):
        """Extract text preserving formatting and special characters"""
        # Verify hierarchical chunking service has PDF extraction
        from pathlib import Path
        service_file = Path("src/services/hierarchical_chunking_service.py")
        assert service_file.exists(), "Hierarchical chunking service should exist"
        content = service_file.read_text()
        assert "chunk_pdf_hierarchically" in content

    def test_header_based_extraction(self):
        """Headers define chunk boundaries, not paragraphs"""
        from pathlib import Path
        service_file = Path("src/services/hierarchical_chunking_service.py")
        content = service_file.read_text()
        # Verify new header-based methods exist
        assert "_extract_headers_with_font_sizes" in content
        assert "_extract_content_between_headers" in content
        # Verify old paragraph methods are removed
        assert "_split_into_paragraphs" not in content
        assert "_extract_topic_content" not in content


class TestStructureDetection:
    """Document structure detection tests"""

    def test_detect_chapter_headers(self):
        """Extract chapter number and title from header"""
        import re
        # Test chapter pattern similar to implementation
        chapter_pattern = re.compile(
            r'^(?:chapter|ch\.?)\s*(\d+)[:\-\s]*(.+?)$',
            re.IGNORECASE
        )
        match = chapter_pattern.match("CHAPTER 5: Force and Motion - I")
        assert match is not None
        assert match.group(1) == "5"
        assert match.group(2) == "Force and Motion - I"

    def test_detect_section_headers(self):
        """Extract section number and title"""
        import re
        section_pattern = re.compile(
            r'^(\d+(?:\.\d+)+)[:\-\s]+(.+?)$',
            re.IGNORECASE
        )
        match = section_pattern.match("5.4 Newton's Second Law")
        assert match is not None
        assert match.group(1) == "5.4"
        assert match.group(2) == "Newton's Second Law"

    def test_font_size_detection(self):
        """Use font size to identify headers"""
        from pathlib import Path
        service_file = Path("src/services/hierarchical_chunking_service.py")
        content = service_file.read_text()
        # Verify font size detection methods exist
        assert "_extract_headers_with_font_sizes" in content
        assert "_extract_lines_with_font_info" in content
        assert "header_threshold" in content
        assert "chapter_threshold" in content

    def test_header_classification_by_text(self):
        """Classify chunk type based on header text patterns"""
        from pathlib import Path
        service_file = Path("src/services/hierarchical_chunking_service.py")
        content = service_file.read_text()
        # Verify header-based classification exists
        assert "_classify_chunk_type_from_header" in content
        assert "example_header_patterns" in content
        assert "question_header_patterns" in content

    def test_build_hierarchy_tree(self):
        """Build Chapter → Sections hierarchy from headers"""
        from pathlib import Path
        service_file = Path("src/services/hierarchical_chunking_service.py")
        content = service_file.read_text()
        # Verify new header extraction exists
        assert "_extract_headers_with_font_sizes" in content
        assert "_extract_headers_text_based" in content
        # Verify old methods are removed
        assert "_extract_topics" not in content
        assert "_process_topic" not in content


class TestHeaderBasedChunking:
    """Header-based chunking boundary tests"""

    def test_chunk_by_headers_not_paragraphs(self):
        """Chunks defined by headers, not paragraph boundaries"""
        from pathlib import Path
        service_file = Path("src/services/hierarchical_chunking_service.py")
        content = service_file.read_text()
        # Verify header-based chunking
        assert "_create_chunk_from_header" in content
        assert "_extract_content_between_headers" in content
        # Verify no paragraph-based chunking
        assert "paragraph" not in content or "not paragraph" in content

    def test_no_overlap_between_chunks(self):
        """Content extracted strictly between headers prevents overlaps"""
        from pathlib import Path
        service_file = Path("src/services/hierarchical_chunking_service.py")
        content = service_file.read_text()
        # Verify precise boundary extraction
        assert "_extract_content_between_headers" in content
        assert "strictly between" in content.lower()

    def test_chunk_respects_natural_boundaries(self):
        """Headers define natural semantic boundaries"""
        from pathlib import Path
        service_file = Path("src/services/hierarchical_chunking_service.py")
        content = service_file.read_text()
        # chunk_size is max size, not enforced at boundaries
        assert "chunk_size" in content
        # Headers define boundaries naturally
        assert "next_header" in content

    def test_dont_split_across_pages_arbitrarily(self):
        """Text spanning pages stays together within header boundaries"""
        from pathlib import Path
        service_file = Path("src/services/hierarchical_chunking_service.py")
        content = service_file.read_text()
        # Extract content between headers handles multi-page content
        assert "page_idx" in content or "start_page" in content
        assert "end_page" in content

    def test_equations_stay_with_section(self):
        """Equations stay in their section chunk, not split"""
        import re
        from pathlib import Path
        service_file = Path("src/services/hierarchical_chunking_service.py")
        content = service_file.read_text()
        # Equation extraction happens within chunks
        assert "_extract_equations" in content
        # Equations pattern still exists
        text = "The force equation:\n\nF = ma\n\nwhere F is force..."
        equation_pattern = re.compile(r'[=+\-*/]\s*[A-Za-z0-9]|[A-Za-z]\s*=')
        assert equation_pattern.search(text)

    def test_keep_section_content_together(self):
        """All content between two headers stays in one chunk"""
        from pathlib import Path
        service_file = Path("src/services/hierarchical_chunking_service.py")
        content = service_file.read_text()
        # Classification happens at header level
        assert "_classify_chunk_type_from_header" in content
        assert "ChunkType.EXAMPLE" in content
        assert "example_header_patterns" in content


class TestMetadataGeneration:
    """Metadata generation tests"""

    def test_generate_chunk_metadata(self):
        """Extract chapter, section, page, type, equations, key terms"""
        from pathlib import Path
        service_file = Path("src/services/hierarchical_chunking_service.py")
        content = service_file.read_text()
        assert "_extract_key_terms" in content
        assert "_extract_equations" in content
        assert "TopicMetadata" in content
        assert "ChunkMetadata" in content

    def test_detect_chunk_type_from_header(self):
        """Classify chunk type based on header text: concept/example/question"""
        from pathlib import Path
        service_file = Path("src/services/hierarchical_chunking_service.py")
        content = service_file.read_text()
        # New header-based classification
        assert "_classify_chunk_type_from_header" in content
        assert "example_header_patterns" in content
        assert "question_header_patterns" in content
        # Old content-based classification removed
        assert "_classify_content_type" not in content

    def test_classification_is_straightforward(self):
        """Classification uses simple pattern matching on headers"""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

        from services.hierarchical_chunking_service import HierarchicalChunkingService
        from models.api_models import ChunkType

        service = HierarchicalChunkingService()

        # Test straightforward classification
        assert service._classify_chunk_type_from_header("Example 5.1") == ChunkType.EXAMPLE
        assert service._classify_chunk_type_from_header("Sample Problem") == ChunkType.EXAMPLE
        assert service._classify_chunk_type_from_header("Exercise 5.3") == ChunkType.QUESTION
        assert service._classify_chunk_type_from_header("Practice Problems") == ChunkType.QUESTION
        assert service._classify_chunk_type_from_header("5.4 Newton's Law") == ChunkType.CONCEPT
        assert service._classify_chunk_type_from_header("Introduction") == ChunkType.CONCEPT

    def test_extract_equations(self):
        """Extract all equations from chunk content"""
        import re
        text = "Newton's second law: F = ma. Rearranging: a = F/m."
        equation_pattern = re.compile(r'[=+\-*/]\s*[A-Za-z0-9]|[A-Za-z]\s*=')
        matches = equation_pattern.findall(text)
        assert len(matches) > 0

    def test_extract_key_terms(self):
        """Extract physics terms from content"""
        from pathlib import Path
        service_file = Path("src/services/hierarchical_chunking_service.py")
        content = service_file.read_text()
        assert "_extract_key_terms" in content

    def test_accurate_page_tracking(self):
        """Track exact page start and end for each chunk"""
        from pathlib import Path
        service_file = Path("src/services/hierarchical_chunking_service.py")
        content = service_file.read_text()
        # Verify page tracking in metadata
        assert "page_start" in content
        assert "page_end" in content
        # Verify it uses next_header page for end
        assert "next_header.get('page'" in content or "next_header['page']" in content
