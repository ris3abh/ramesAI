"""
Tests for Email Parser Tool
============================
Tests email parsing for .eml and .html formats.

Run with: pytest tests/test_email_parser.py -v
"""

import pytest
import json
from pathlib import Path
import tempfile

from email_qa.tools.email_parser import EmailParserTool, parse_email_file


@pytest.fixture
def temp_output_dir():
    """Create temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_eml_file(temp_output_dir):
    """Create a sample .eml file for testing."""
    eml_content = """From: Yanmar <info@yanmar.com>
To: customer@example.com
Subject: Explore What Yanmar Can Do
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="boundary123"

--boundary123
Content-Type: text/plain; charset="utf-8"

Explore What Yanmar Can Do

Learn about attachments and techniques pros use.

GET STARTED: https://yanmar.com/tractors

--boundary123
Content-Type: text/html; charset="utf-8"

<html>
<head></head>
<body>
<div style="display:none;font-size:0">Learn about attachments and techniques pros use.</div>
<h1>Explore What Yanmar Can Do</h1>
<p>Discover the power of Yanmar tractors.</p>
<table>
<tr>
<td class="cta-button">
<a href="https://yanmar.com/tractors?utm_campaign=august&utm_source=email" class="btn">GET STARTED</a>
</td>
</tr>
</table>
<p><a href="https://yanmar.com/shop">SHOP NOW</a></p>
<img src="https://yanmar.com/images/tractor.jpg" alt="Yanmar Tractor" width="600" height="400">
<p><a href="https://yanmar.com/unsubscribe">Unsubscribe</a></p>
</body>
</html>

--boundary123--
"""
    
    eml_path = temp_output_dir / "test_email.eml"
    eml_path.write_text(eml_content)
    return eml_path


@pytest.fixture
def sample_html_file(temp_output_dir):
    """Create a sample .html email file for testing."""
    html_content = """<!DOCTYPE html>
<html>
<head>
<title>Yanmar Newsletter</title>
</head>
<body>
<div style="display:none">Your path to more efficient land management.</div>
<table width="600">
<tr>
<td>
<h1>Tractor Projects That Pay Off</h1>
<p>Start these projects before it's too late!</p>
<table>
<tr>
<td class="button-cell">
<a href="https://click.e.yanmar.com/redirect?url=https://yanmar.com/parts" class="cta-button">SHOP PARTS</a>
</td>
</tr>
</table>
<p>Learn more about <a href="https://yanmar.com/resources">Yanmar resources</a>.</p>
<img src="https://yanmar.com/images/field.jpg" alt="Field Work" width="600">
<p style="font-size:10px"><a href="https://yanmar.com/unsubscribe">Unsubscribe</a></p>
</td>
</tr>
</table>
</body>
</html>
"""
    
    html_path = temp_output_dir / "test_email.html"
    html_path.write_text(html_content)
    return html_path


class TestEmailParserTool:
    """Tests for EmailParserTool class."""
    
    def test_tool_initialization(self):
        """Test tool initializes correctly."""
        tool = EmailParserTool()
        
        assert tool.name == "Email Parser"
        assert "email" in tool.description.lower()
        assert tool.args_schema is not None
    
    def test_parse_nonexistent_file(self, temp_output_dir):
        """Test handling of nonexistent file."""
        tool = EmailParserTool()
        
        result_json = tool._run(email_path="nonexistent.eml")
        result = json.loads(result_json)
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()
    
    def test_parse_unsupported_format(self, temp_output_dir):
        """Test handling of unsupported file format."""
        tool = EmailParserTool()
        
        # Create a .txt file
        txt_file = temp_output_dir / "test.txt"
        txt_file.write_text("test")
        
        result_json = tool._run(email_path=str(txt_file))
        result = json.loads(result_json)
        
        assert result["success"] is False
        assert "unsupported" in result["error"].lower()


class TestEMLParsing:
    """Tests for .eml file parsing."""
    
    def test_parse_eml_success(self, sample_eml_file):
        """Test successful .eml parsing."""
        tool = EmailParserTool()
        
        result_json = tool._run(email_path=str(sample_eml_file))
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert "subject" in result
        assert "from_email" in result
    
    def test_extract_subject(self, sample_eml_file):
        """Test subject line extraction."""
        tool = EmailParserTool()
        
        result_json = tool._run(email_path=str(sample_eml_file))
        result = json.loads(result_json)
        
        assert result["subject"] == "Explore What Yanmar Can Do"
    
    def test_extract_from_header(self, sample_eml_file):
        """Test from name and email extraction."""
        tool = EmailParserTool()
        
        result_json = tool._run(email_path=str(sample_eml_file))
        result = json.loads(result_json)
        
        assert result["from_name"] == "Yanmar"
        assert result["from_email"] == "info@yanmar.com"
    
    def test_extract_preview_text(self, sample_eml_file):
        """Test preview text extraction."""
        tool = EmailParserTool()
        
        result_json = tool._run(email_path=str(sample_eml_file))
        result = json.loads(result_json)
        
        assert "attachments" in result["preview_text"].lower()
    
    def test_extract_links(self, sample_eml_file):
        """Test link extraction."""
        tool = EmailParserTool()
        
        result_json = tool._run(email_path=str(sample_eml_file))
        result = json.loads(result_json)
        
        assert len(result["links"]) > 0
        assert any("yanmar.com" in link["url"] for link in result["links"])
    
    def test_extract_utm_parameters(self, sample_eml_file):
        """Test UTM parameter extraction."""
        tool = EmailParserTool()
        
        result_json = tool._run(email_path=str(sample_eml_file))
        result = json.loads(result_json)
        
        # Find link with UTM params
        utm_link = next(
            (link for link in result["links"] if link["utm_params"]),
            None
        )
        
        assert utm_link is not None
        assert "utm_campaign" in utm_link["utm_params"]
    
    def test_identify_ctas(self, sample_eml_file):
        """Test CTA identification."""
        tool = EmailParserTool()
        
        result_json = tool._run(email_path=str(sample_eml_file))
        result = json.loads(result_json)
        
        assert len(result["ctas"]) > 0
        assert any("GET STARTED" in cta["text"] for cta in result["ctas"])
    
    def test_extract_images(self, sample_eml_file):
        """Test image extraction."""
        tool = EmailParserTool()
        
        result_json = tool._run(email_path=str(sample_eml_file))
        result = json.loads(result_json)
        
        assert len(result["images"]) > 0
        assert any("tractor.jpg" in img["src"] for img in result["images"])
    
    def test_detect_unsubscribe(self, sample_eml_file):
        """Test unsubscribe link detection."""
        tool = EmailParserTool()
        
        result_json = tool._run(email_path=str(sample_eml_file))
        result = json.loads(result_json)
        
        assert result["has_unsubscribe"] is True


class TestHTMLParsing:
    """Tests for .html file parsing."""
    
    def test_parse_html_success(self, sample_html_file):
        """Test successful .html parsing."""
        tool = EmailParserTool()
        
        result_json = tool._run(email_path=str(sample_html_file))
        result = json.loads(result_json)
        
        assert result["success"] is True
    
    def test_html_no_subject(self, sample_html_file):
        """Test that standalone HTML has no subject."""
        tool = EmailParserTool()
        
        result_json = tool._run(email_path=str(sample_html_file))
        result = json.loads(result_json)
        
        # Standalone HTML doesn't have email headers
        assert result["subject"] == ""
        assert result["from_email"] == ""
    
    def test_html_extract_preview_text(self, sample_html_file):
        """Test preview text from HTML."""
        tool = EmailParserTool()
        
        result_json = tool._run(email_path=str(sample_html_file))
        result = json.loads(result_json)
        
        assert "efficient land management" in result["preview_text"].lower()
    
    def test_html_extract_links(self, sample_html_file):
        """Test link extraction from HTML."""
        tool = EmailParserTool()
        
        result_json = tool._run(email_path=str(sample_html_file))
        result = json.loads(result_json)
        
        assert len(result["links"]) > 0
    
    def test_html_identify_tracking_links(self, sample_html_file):
        """Test tracking link identification."""
        tool = EmailParserTool()
        
        result_json = tool._run(email_path=str(sample_html_file))
        result = json.loads(result_json)
        
        # Find tracking link
        tracking_link = next(
            (link for link in result["links"] if link["is_tracking_link"]),
            None
        )
        
        assert tracking_link is not None
        assert "click.e.yanmar" in tracking_link["url"]
    
    def test_html_extract_ctas(self, sample_html_file):
        """Test CTA extraction from HTML."""
        tool = EmailParserTool()
        
        result_json = tool._run(email_path=str(sample_html_file))
        result = json.loads(result_json)
        
        assert len(result["ctas"]) > 0
        assert any("SHOP PARTS" in cta["text"] for cta in result["ctas"])


class TestStandaloneFunction:
    """Tests for standalone parse_email_file function."""
    
    def test_standalone_with_eml(self, sample_eml_file):
        """Test standalone function with .eml file."""
        result = parse_email_file(str(sample_eml_file))
        
        assert result["success"] is True
        assert result["subject"] == "Explore What Yanmar Can Do"
    
    def test_standalone_with_html(self, sample_html_file):
        """Test standalone function with .html file."""
        result = parse_email_file(str(sample_html_file))
        
        assert result["success"] is True
        assert len(result["links"]) > 0
    
    def test_standalone_returns_dict(self, sample_eml_file):
        """Test standalone function returns dict."""
        result = parse_email_file(str(sample_eml_file))
        
        assert isinstance(result, dict)
        assert isinstance(result["subject"], str)
        assert isinstance(result["links"], list)


class TestCTADetection:
    """Tests for CTA detection logic."""
    
    def test_uppercase_cta_text(self, sample_eml_file):
        """Test that CTAs with UPPERCASE text are detected."""
        tool = EmailParserTool()
        
        result_json = tool._run(email_path=str(sample_eml_file))
        result = json.loads(result_json)
        
        cta_texts = [cta["text"] for cta in result["ctas"]]
        assert any(text.isupper() for text in cta_texts if text)
    
    def test_cta_with_button_class(self, sample_html_file):
        """Test CTAs identified by button classes."""
        tool = EmailParserTool()
        
        result_json = tool._run(email_path=str(sample_html_file))
        result = json.loads(result_json)
        
        assert len(result["ctas"]) > 0


class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_empty_html(self, temp_output_dir):
        """Test handling of empty HTML."""
        html_file = temp_output_dir / "empty.html"
        html_file.write_text("<html><body></body></html>")
        
        tool = EmailParserTool()
        result_json = tool._run(email_path=str(html_file))
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert len(result["links"]) == 0
    
    def test_no_preview_text(self, temp_output_dir):
        """Test email without preview text."""
        html_file = temp_output_dir / "no_preview.html"
        html_file.write_text("<html><body><p>Content</p></body></html>")
        
        tool = EmailParserTool()
        result_json = tool._run(email_path=str(html_file))
        result = json.loads(result_json)
        
        assert result["preview_text"] == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])