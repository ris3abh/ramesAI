"""
Integration Tests for Link Validator Tool
==========================================
Tests link validation using real Yanmar email and copy doc.

Run with: pytest tests/test_link_validator_real.py -v
"""

import pytest
import json
from pathlib import Path
from email_qa.tools.email_parser import parse_email_file
from email_qa.tools.pdf_parser import parse_pdf_file
from email_qa.tools.link_validator import validate_links


# Update these paths to match your actual file locations
# Update these lines at the top of the file (around line 14-15):
EMAIL_FILE = "../uploads/[Test]_Explore What Yanmar Can Do (1).eml"
COPY_DOC_FILE = "../uploads/Yanmar_August_Copy_Doc.pdf"


@pytest.fixture
def yanmar_email_data():
    """Parse the real Yanmar email."""
    email_path = Path(EMAIL_FILE)
    
    if not email_path.exists():
        pytest.skip(f"Email file not found: {EMAIL_FILE}")
    
    result = parse_email_file(str(email_path))
    
    if not result.get("success"):
        pytest.skip(f"Failed to parse email: {result.get('error')}")
    
    return result


@pytest.fixture
def yanmar_copy_requirements():
    """
    Extract requirements from Yanmar copy doc.
    For now, we'll manually define expected requirements.
    Later, you can build a parser for the copy doc.
    """
    return {
        "required_ctas": [
            "LEARN MORE",
            "GET STARTED",
            "JOIN THE COMMUNITY",
            "EXPLORE OFFERS",
            "BUILD MY TRACTOR",
            "SEND EMAIL",
            "CALL 770-637-0441"
        ],
        "required_phone": "770-637-0441",
        "required_social": {
            "instagram": "yanmartractorsamerica"
        },
        "utm_requirements": {
            "required_params": ["source", "medium"],
            "expected_values": {}
        }
    }


class TestYanmarEmailValidation:
    """Test link validation on real Yanmar email."""
    
    def test_parse_yanmar_email(self, yanmar_email_data):
        """Test that we can parse the Yanmar email."""
        assert yanmar_email_data["success"] is True
        assert yanmar_email_data["subject"] == "The UTV choice that could save you money long-term"
        assert len(yanmar_email_data["links"]) > 0
        assert len(yanmar_email_data["ctas"]) > 0
    
    def test_yanmar_ctas(self, yanmar_email_data, yanmar_copy_requirements):
        """Test CTA validation on real Yanmar email."""
        email_links = json.dumps(yanmar_email_data)
        required_links = json.dumps(yanmar_copy_requirements)
        
        result = validate_links(email_links, required_links, check_http_status=False)
        
        print("\n" + "="*60)
        print("CTA VALIDATION RESULTS")
        print("="*60)
        print(f"Found CTAs: {result['cta_validation']['found_ctas']}")
        print(f"Required CTAs: {result['cta_validation']['required_ctas']}")
        print(f"Missing CTAs: {result['cta_validation']['missing_ctas']}")
        print(f"Issues: {len(result['issues'])}")
        for issue in result["issues"]:
            print(f"  - {issue}")
        print(f"Warnings: {len(result['warnings'])}")
        for warning in result["warnings"]:
            print(f"  - {warning}")
        print("="*60 + "\n")
        
        # The test will show what's missing, but won't fail
        # This is informational for now
        assert isinstance(result["cta_validation"]["found_ctas"], list)
    
    def test_yanmar_phone(self, yanmar_email_data, yanmar_copy_requirements):
        """Test phone number validation on real Yanmar email."""
        email_links = json.dumps(yanmar_email_data)
        required_links = json.dumps(yanmar_copy_requirements)
        
        result = validate_links(email_links, required_links, check_http_status=False)
        
        print("\n" + "="*60)
        print("PHONE VALIDATION RESULTS")
        print("="*60)
        print(f"Phone links found: {len(result['phone_validation']['phone_links'])}")
        for phone in result['phone_validation']['phone_links']:
            print(f"  - {phone['text']}: {phone['phone']}")
        print(f"Required phone: {yanmar_copy_requirements['required_phone']}")
        if result['phone_validation']['issues']:
            print("Issues:")
            for issue in result['phone_validation']['issues']:
                print(f"  - {issue}")
        print("="*60 + "\n")
        
        # Should find the phone number
        assert len(result['phone_validation']['phone_links']) > 0
    
    def test_yanmar_social(self, yanmar_email_data, yanmar_copy_requirements):
        """Test social media handle validation on real Yanmar email."""
        email_links = json.dumps(yanmar_email_data)
        required_links = json.dumps(yanmar_copy_requirements)
        
        result = validate_links(email_links, required_links, check_http_status=False)
        
        print("\n" + "="*60)
        print("SOCIAL MEDIA VALIDATION RESULTS")
        print("="*60)
        print(f"Social links found: {len(result['social_validation']['social_links'])}")
        for social in result['social_validation']['social_links']:
            print(f"  - {social['platform']}: @{social['handle']}")
        print(f"Required: {yanmar_copy_requirements['required_social']}")
        if result['social_validation']['issues']:
            print("Issues:")
            for issue in result['social_validation']['issues']:
                print(f"  - {issue}")
        print("="*60 + "\n")
        
        # Should find Instagram handle
        instagram_links = [
            s for s in result['social_validation']['social_links']
            if s['platform'] == 'instagram'
        ]
        assert len(instagram_links) > 0
    
    def test_yanmar_tracking_links(self, yanmar_email_data):
        """Test that tracking links are identified."""
        tracking_links = [
            link for link in yanmar_email_data["links"]
            if link.get("is_tracking_link") is True
        ]
        
        print("\n" + "="*60)
        print("TRACKING LINKS")
        print("="*60)
        print(f"Total links: {len(yanmar_email_data['links'])}")
        print(f"Tracking links: {len(tracking_links)}")
        print("\nSample tracking links:")
        for link in tracking_links[:3]:
            print(f"  - {link['text'][:40]}")
            print(f"    URL: {link['url'][:80]}...")
        print("="*60 + "\n")
        
        # Yanmar uses click.e.yanmartractor.com tracking
        assert len(tracking_links) > 0
        assert any("click.e.yanmartractor" in link["url"] for link in tracking_links)
    
    def test_yanmar_full_validation_report(self, yanmar_email_data, yanmar_copy_requirements):
        """Generate full validation report for Yanmar email."""
        email_links = json.dumps(yanmar_email_data)
        required_links = json.dumps(yanmar_copy_requirements)
        
        # Run validation without HTTP checks (faster)
        result = validate_links(email_links, required_links, check_http_status=False)
        
        print("\n" + "="*80)
        print("FULL YANMAR EMAIL VALIDATION REPORT")
        print("="*80)
        print(f"Email: {yanmar_email_data['subject']}")
        print(f"From: {yanmar_email_data['from_name']} <{yanmar_email_data['from_email']}>")
        print(f"Preview: {yanmar_email_data['preview_text'][:60]}...")
        print()
        print(f"Overall Status: {'✅ PASS' if result['success'] else '❌ FAIL'}")
        print(f"Total Issues: {len(result['issues'])}")
        print(f"Total Warnings: {len(result['warnings'])}")
        print()
        
        print("📊 STATISTICS")
        print(f"  Total Links: {len(yanmar_email_data['links'])}")
        print(f"  Total CTAs: {len(yanmar_email_data['ctas'])}")
        print(f"  Images: {len(yanmar_email_data['images'])}")
        print(f"  Has Unsubscribe: {'✅' if yanmar_email_data['has_unsubscribe'] else '❌'}")
        print()
        
        if result['issues']:
            print("❌ ISSUES:")
            for i, issue in enumerate(result['issues'], 1):
                print(f"  {i}. {issue}")
            print()
        
        if result['warnings']:
            print("⚠️  WARNINGS:")
            for i, warning in enumerate(result['warnings'], 1):
                print(f"  {i}. {warning}")
            print()
        
        print("="*80 + "\n")
        
        # Always pass - this is informational
        assert isinstance(result, dict)


class TestYanmarWithHTTPChecks:
    """Test with actual HTTP status checks (slower)."""
    
    @pytest.mark.slow
    def test_yanmar_link_status(self, yanmar_email_data):
        """
        Test HTTP status of links in Yanmar email.
        This is marked as slow because it makes real HTTP requests.
        
        Run with: pytest tests/test_link_validator_real.py -v -m slow
        """
        email_links = json.dumps(yanmar_email_data)
        required_links = json.dumps({"required_ctas": []})
        
        # Run with HTTP checks
        result = validate_links(email_links, required_links, check_http_status=True)
        
        print("\n" + "="*60)
        print("HTTP STATUS CHECK RESULTS")
        print("="*60)
        print(f"Working links: {len(result['link_status']['working_links'])}")
        print(f"Broken links: {len(result['link_status']['broken_links'])}")
        
        if result['link_status']['broken_links']:
            print("\nBroken Links:")
            for link in result['link_status']['broken_links']:
                print(f"  - {link['text']}: {link.get('status', link.get('error'))}")
        
        print("="*60 + "\n")
        
        # Informational - won't fail the test
        assert isinstance(result['link_status'], dict)


if __name__ == "__main__":
    # Run with: python tests/test_link_validator_real.py
    pytest.main([__file__, "-v", "-s"])