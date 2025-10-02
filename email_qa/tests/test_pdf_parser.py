"""
Tests for PDF Parser Tool
==========================
Tests PDF parsing functionality with sample documents.

Run with: pytest tests/test_pdf_parser.py -v
"""

import pytest
import json
from pathlib import Path
import tempfile
import fitz  # PyMuPDF

from email_qa.tools.pdf_parser import PDFParserTool, parse_pdf_file


@pytest.fixture
def temp_output_dir():
    """Create temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_pdf(temp_output_dir):
    """Create a simple test PDF with email copy content."""
    doc = fitz.open()
    
    # Page 1: Email copy content
    page1 = doc.new_page(width=595, height=842)  # A4
    
    # Add title
    page1.insert_text(
        (50, 50),
        "Yanmar August Newsletter - Copy Document",
        fontsize=16,
        fontname="helv"
    )
    
    # Add subject lines
    content = """
Subject Line A (Prospects): Explore What Yanmar Can Do
Subject Line B (Prospects): Don't Miss What Yanmar Can Do for You

Subject Line A (Owners): Tractor Projects That Pay Off
Subject Line B (Owners): Start These Tractor Projects Before It's Too Late!

Preview Text:
- Prospects: Learn about the attachments and techniques pros use.
- Owners: Your path to more efficient land management.

From Name: Yanmar
From Email: info@yanmar.com

CTAs:
- GET STARTED → https://yanmar.com/tractors/signup
- SHOP NOW → https://yanmar.com/shop
- LEARN MORE → https://yanmar.com/resources

Content Modules:
1. Hero - Field Notes Main Image
2. UGC Section (different for Owners vs Prospects)
3. Exclusive Offers
4. Tractor Builder (Prospects only)
5. Parts Store (Owners only)
6. Connect with Yanmar

Special Instructions:
- Check dark mode rendering
- Verify phone numbers are not 555-555-5555
- All CTAs should be UPPERCASE
"""
    
    page1.insert_text((50, 100), content, fontsize=11)
    
    # Save to temp file
    pdf_path = temp_output_dir / "test_copy_doc.pdf"
    doc.save(pdf_path)
    doc.close()
    
    return pdf_path


class TestPDFParserTool:
    """Tests for PDFParserTool class."""
    
    def test_tool_initialization(self):
        """Test tool initializes correctly."""
        tool = PDFParserTool()
        
        assert tool.name == "PDF Parser"
        assert "PDF" in tool.description
        assert tool.args_schema is not None
    
    def test_parse_valid_pdf(self, sample_pdf, temp_output_dir):
        """Test parsing a valid PDF."""
        tool = PDFParserTool()
        
        result_json = tool._run(
            pdf_path=str(sample_pdf),
            extract_images=False,
            output_dir=str(temp_output_dir)
        )
        
        result = json.loads(result_json)
        
        # Check success
        assert result["success"] is True
        assert "markdown" in result
        assert "metadata" in result
        
        # Check content
        markdown = result["markdown"]
        assert "Yanmar" in markdown
        assert "Subject Line" in markdown
        assert "GET STARTED" in markdown
        
        # Check metadata
        metadata = result["metadata"]
        assert metadata["page_count"] == 1
        assert metadata["char_count"] > 0
        assert "test_copy_doc.pdf" in metadata["source_file"]
    
    def test_parse_nonexistent_pdf(self, temp_output_dir):
        """Test handling of nonexistent PDF."""
        tool = PDFParserTool()
        
        result_json = tool._run(
            pdf_path="nonexistent.pdf",
            output_dir=str(temp_output_dir)
        )
        
        result = json.loads(result_json)
        
        assert result["success"] is False
        assert "error" in result
        assert "not found" in result["error"].lower()
    
    def test_extract_subject_lines(self, sample_pdf, temp_output_dir):
        """Test that subject lines are extracted."""
        tool = PDFParserTool()
        
        result_json = tool._run(
            pdf_path=str(sample_pdf),
            extract_images=False,
            output_dir=str(temp_output_dir)
        )
        
        result = json.loads(result_json)
        markdown = result["markdown"]
        
        # Check for subject line content
        assert "Explore What Yanmar Can Do" in markdown
        assert "Tractor Projects That Pay Off" in markdown
    
    def test_extract_ctas(self, sample_pdf, temp_output_dir):
        """Test that CTAs are extracted."""
        tool = PDFParserTool()
        
        result_json = tool._run(
            pdf_path=str(sample_pdf),
            extract_images=False,
            output_dir=str(temp_output_dir)
        )
        
        result = json.loads(result_json)
        markdown = result["markdown"]
        
        # Check for CTAs
        assert "GET STARTED" in markdown
        assert "SHOP NOW" in markdown
        assert "https://yanmar.com" in markdown
    
    def test_extract_special_instructions(self, sample_pdf, temp_output_dir):
        """Test that special instructions are captured."""
        tool = PDFParserTool()
        
        result_json = tool._run(
            pdf_path=str(sample_pdf),
            extract_images=False,
            output_dir=str(temp_output_dir)
        )
        
        result = json.loads(result_json)
        markdown = result["markdown"]
        
        # Check for special instructions
        assert "dark mode" in markdown.lower()
        assert "UPPERCASE" in markdown


class TestStandaloneFunction:
    """Tests for standalone parse_pdf_file function."""
    
    def test_standalone_function(self, sample_pdf, temp_output_dir):
        """Test standalone function works."""
        result = parse_pdf_file(
            pdf_path=str(sample_pdf),
            extract_images=False,
            output_dir=str(temp_output_dir)
        )
        
        assert result["success"] is True
        assert "markdown" in result
        assert "Yanmar" in result["markdown"]
    
    def test_standalone_returns_dict(self, sample_pdf, temp_output_dir):
        """Test standalone function returns dict, not JSON string."""
        result = parse_pdf_file(
            pdf_path=str(sample_pdf),
            extract_images=False,
            output_dir=str(temp_output_dir)
        )
        
        assert isinstance(result, dict)
        assert isinstance(result["markdown"], str)
        assert isinstance(result["metadata"], dict)


class TestImageExtraction:
    """Tests for image extraction (when PDFs have images)."""
    
    def test_no_images_in_pdf(self, sample_pdf, temp_output_dir):
        """Test PDF with no images."""
        tool = PDFParserTool()
        
        result_json = tool._run(
            pdf_path=str(sample_pdf),
            extract_images=True,
            output_dir=str(temp_output_dir)
        )
        
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert len(result["images"]) == 0
        assert result["metadata"]["image_count"] == 0
    
    def test_extract_images_disabled(self, sample_pdf, temp_output_dir):
        """Test when image extraction is disabled."""
        tool = PDFParserTool()
        
        result_json = tool._run(
            pdf_path=str(sample_pdf),
            extract_images=False,
            output_dir=str(temp_output_dir)
        )
        
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert len(result["images"]) == 0


class TestMarkdownFormatting:
    """Tests for markdown output formatting."""
    
    def test_page_headers_included(self, sample_pdf, temp_output_dir):
        """Test that page headers are in markdown."""
        tool = PDFParserTool()
        
        result_json = tool._run(
            pdf_path=str(sample_pdf),
            extract_images=False,
            output_dir=str(temp_output_dir)
        )
        
        result = json.loads(result_json)
        markdown = result["markdown"]
        
        assert "## Page 1" in markdown
    
    def test_markdown_structure_preserved(self, sample_pdf, temp_output_dir):
        """Test that markdown structure is preserved."""
        tool = PDFParserTool()
        
        result_json = tool._run(
            pdf_path=str(sample_pdf),
            extract_images=False,
            output_dir=str(temp_output_dir)
        )
        
        result = json.loads(result_json)
        markdown = result["markdown"]
        
        # Check structure elements
        assert len(markdown) > 0
        assert "\n" in markdown  # Has line breaks


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])