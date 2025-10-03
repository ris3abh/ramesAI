"""
Tests for Link Validator Tool
==============================
Tests link validation with mock data.

Run with: pytest tests/test_link_validator.py -v
"""

import pytest
import json
from email_qa.tools.link_validator import LinkValidatorTool, validate_links


class TestCTAValidation:
    """Tests for CTA validation."""
    
    def test_all_ctas_present(self):
        """Test when all required CTAs are present."""
        email_links = json.dumps({
            "ctas": [
                {"text": "LEARN MORE", "url": "https://example.com"},
                {"text": "GET STARTED", "url": "https://example.com"},
                {"text": "SHOP NOW", "url": "https://example.com"}
            ],
            "links": []
        })
        
        required_links = json.dumps({
            "required_ctas": ["LEARN MORE", "GET STARTED", "SHOP NOW"]
        })
        
        result = validate_links(email_links, required_links, check_http_status=False)
        
        assert result["success"] is True
        assert len(result["cta_validation"]["missing_ctas"]) == 0
        assert len(result["issues"]) == 0
    
    def test_missing_cta(self):
        """Test when a required CTA is missing."""
        email_links = json.dumps({
            "ctas": [
                {"text": "LEARN MORE", "url": "https://example.com"}
            ],
            "links": []
        })
        
        required_links = json.dumps({
            "required_ctas": ["LEARN MORE", "SHOP NOW"]
        })
        
        result = validate_links(email_links, required_links, check_http_status=False)
        
        assert result["success"] is False
        assert "SHOP NOW" in result["cta_validation"]["missing_ctas"]
        assert any("SHOP NOW" in issue for issue in result["issues"])
    
    def test_cta_case_insensitive(self):
        """Test CTA matching is case insensitive."""
        email_links = json.dumps({
            "ctas": [
                {"text": "Learn More", "url": "https://example.com"}
            ],
            "links": []
        })
        
        required_links = json.dumps({
            "required_ctas": ["LEARN MORE"]
        })
        
        result = validate_links(email_links, required_links, check_http_status=False)
        
        # Should match despite case difference
        assert len(result["cta_validation"]["missing_ctas"]) == 0
        # But should warn about non-uppercase
        assert any("not uppercase" in warning for warning in result["warnings"])


class TestPhoneValidation:
    """Tests for phone number validation."""
    
    def test_phone_present_and_correct(self):
        """Test when phone number is present and matches."""
        email_links = json.dumps({
            "ctas": [],
            "links": [
                {"text": "CALL 770-637-0441", "url": "tel:+17706370441"}
            ]
        })
        
        required_links = json.dumps({
            "required_phone": "770-637-0441"
        })
        
        result = validate_links(email_links, required_links, check_http_status=False)
        
        assert result["success"] is True
        assert len(result["phone_validation"]["phone_links"]) == 1
        assert len(result["phone_validation"]["issues"]) == 0
    
    def test_phone_mismatch(self):
        """Test when phone number doesn't match."""
        email_links = json.dumps({
            "ctas": [],
            "links": [
                {"text": "CALL 555-555-5555", "url": "tel:+15555555555"}
            ]
        })
        
        required_links = json.dumps({
            "required_phone": "770-637-0441"
        })
        
        result = validate_links(email_links, required_links, check_http_status=False)
        
        assert result["success"] is False
        assert any("mismatch" in issue.lower() for issue in result["issues"])
    
    def test_phone_missing(self):
        """Test when required phone is not found."""
        email_links = json.dumps({
            "ctas": [],
            "links": []
        })
        
        required_links = json.dumps({
            "required_phone": "770-637-0441"
        })
        
        result = validate_links(email_links, required_links, check_http_status=False)
        
        assert result["success"] is False
        assert any("not found" in issue for issue in result["issues"])


class TestSocialValidation:
    """Tests for social media handle validation."""
    
    def test_instagram_handle_correct(self):
        """Test Instagram handle validation."""
        email_links = json.dumps({
            "ctas": [],
            "links": [
                {
                    "text": "@yanmartractorsamerica",
                    "url": "https://instagram.com/yanmartractorsamerica"
                }
            ]
        })
        
        required_links = json.dumps({
            "required_social": {
                "instagram": "yanmartractorsamerica"
            }
        })
        
        result = validate_links(email_links, required_links, check_http_status=False)
        
        assert result["success"] is True
        assert len(result["social_validation"]["social_links"]) == 1
        assert result["social_validation"]["social_links"][0]["platform"] == "instagram"
    
    def test_social_handle_mismatch(self):
        """Test when social handle doesn't match."""
        email_links = json.dumps({
            "ctas": [],
            "links": [
                {
                    "text": "@wronghandle",
                    "url": "https://instagram.com/wronghandle"
                }
            ]
        })
        
        required_links = json.dumps({
            "required_social": {
                "instagram": "yanmartractorsamerica"
            }
        })
        
        result = validate_links(email_links, required_links, check_http_status=False)
        
        assert result["success"] is False
        assert any("mismatch" in issue.lower() for issue in result["issues"])
    
    def test_multiple_social_platforms(self):
        """Test validation across multiple social platforms."""
        email_links = json.dumps({
            "ctas": [],
            "links": [
                {"text": "Instagram", "url": "https://instagram.com/yanmartractorsamerica"},
                {"text": "Facebook", "url": "https://facebook.com/YanmarTractors"}
            ]
        })
        
        required_links = json.dumps({
            "required_social": {
                "instagram": "yanmartractorsamerica",
                "facebook": "YanmarTractors"
            }
        })
        
        result = validate_links(email_links, required_links, check_http_status=False)
        
        assert result["success"] is True
        assert len(result["social_validation"]["social_links"]) == 2


class TestUTMValidation:
    """Tests for UTM parameter validation."""
    
    def test_utm_params_present(self):
        """Test when required UTM params are present."""
        email_links = json.dumps({
            "ctas": [],
            "links": [
                {
                    "text": "Click Here",
                    "url": "https://example.com?utm_source=email&utm_medium=newsletter",
                    "utm_params": {
                        "utm_source": "email",
                        "utm_medium": "newsletter"
                    }
                }
            ]
        })
        
        required_links = json.dumps({
            "utm_requirements": {
                "required_params": ["source", "medium"]
            }
        })
        
        result = validate_links(email_links, required_links, check_http_status=False)
        
        assert result["success"] is True
        assert len(result["utm_validation"]["links_with_utm"]) == 1
    
    def test_utm_params_missing(self):
        """Test when required UTM params are missing."""
        email_links = json.dumps({
            "ctas": [],
            "links": [
                {
                    "text": "Click Here",
                    "url": "https://example.com",
                    "utm_params": {}
                }
            ]
        })
        
        required_links = json.dumps({
            "utm_requirements": {
                "required_params": ["source", "medium", "campaign"]
            }
        })
        
        result = validate_links(email_links, required_links, check_http_status=False)
        
        # Missing UTM is a warning, not a failure
        assert len(result["warnings"]) > 0
        assert len(result["utm_validation"]["links_missing_utm"]) == 1
    
    def test_utm_value_mismatch(self):
        """Test when UTM param value doesn't match expected."""
        email_links = json.dumps({
            "ctas": [],
            "links": [
                {
                    "text": "Click Here",
                    "url": "https://example.com?utm_source=facebook",
                    "utm_params": {
                        "utm_source": "facebook"
                    }
                }
            ]
        })
        
        required_links = json.dumps({
            "utm_requirements": {
                "required_params": ["source"],
                "expected_values": {
                    "source": "email"
                }
            }
        })
        
        result = validate_links(email_links, required_links, check_http_status=False)
        
        assert result["success"] is False
        assert len(result["utm_validation"]["utm_errors"]) == 1


class TestToolInitialization:
    """Tests for tool initialization."""
    
    def test_tool_initialization(self):
        """Test tool initializes correctly."""
        tool = LinkValidatorTool()
        
        assert tool.name == "Link Validator"
        assert "links" in tool.description.lower()
        assert tool.args_schema is not None
    
    def test_standalone_function(self):
        """Test standalone function works."""
        email_links = json.dumps({
            "ctas": [{"text": "CLICK HERE", "url": "https://example.com"}],
            "links": []
        })
        
        required_links = json.dumps({
            "required_ctas": ["CLICK HERE"]
        })
        
        result = validate_links(email_links, required_links, check_http_status=False)
        
        assert isinstance(result, dict)
        assert "success" in result
        assert "cta_validation" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])