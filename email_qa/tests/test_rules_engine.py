"""
Tests for Dynamic Rules Engine
===============================
Tests rule loading and validation logic.

Run with: pytest tests/test_rules_engine.py -v
"""

import pytest
import json
from pathlib import Path
from email_qa.rules.engine import DynamicRulesEngine, validate_email


class TestRulesEngineInitialization:
    """Tests for engine initialization."""
    
    def test_engine_initialization_default_path(self):
        """Test engine initializes with default rules directory."""
        engine = DynamicRulesEngine()
        assert engine.rules_dir is not None
        assert engine.rules_dir.name == "clients"
    
    def test_engine_initialization_custom_path(self, tmp_path):
        """Test engine initializes with custom rules directory."""
        custom_dir = tmp_path / "custom_rules"
        engine = DynamicRulesEngine(rules_dir=str(custom_dir))
        assert engine.rules_dir == custom_dir
        assert custom_dir.exists()  # Should create directory
    
    def test_loaded_rules_cache(self):
        """Test rules are cached after first load."""
        engine = DynamicRulesEngine()
        assert len(engine.loaded_rules) == 0


class TestLoadRules:
    """Tests for loading rules from JSON files."""
    
    def test_load_yanmar_rules(self):
        """Test loading Yanmar rules file."""
        engine = DynamicRulesEngine()
        
        try:
            rules = engine.load_rules("yanmar")
            
            assert rules["client_name"] == "Yanmar"
            assert "brand" in rules
            assert "segmentation" in rules
            assert "modules" in rules
            assert "ctas" in rules
            
        except FileNotFoundError:
            pytest.skip("Yanmar rules file not yet created")
    
    def test_load_nonexistent_client(self):
        """Test loading rules for nonexistent client raises error."""
        engine = DynamicRulesEngine()
        
        with pytest.raises(FileNotFoundError):
            engine.load_rules("nonexistent_client_xyz")
    
    def test_rules_caching(self):
        """Test rules are cached after first load."""
        engine = DynamicRulesEngine()
        
        try:
            rules1 = engine.load_rules("yanmar")
            rules2 = engine.load_rules("yanmar")
            
            # Should be same object (cached)
            assert rules1 is rules2
            assert "yanmar" in engine.loaded_rules
            
        except FileNotFoundError:
            pytest.skip("Yanmar rules file not yet created")
    
    def test_client_name_normalization(self, tmp_path):
        """Test client names are normalized (lowercase, underscores)."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        
        # Create a test rules file
        test_rules = {"client_name": "Test Client"}
        rules_file = rules_dir / "test_client.json"
        with open(rules_file, 'w') as f:
            json.dump(test_rules, f)
        
        engine = DynamicRulesEngine(rules_dir=str(rules_dir))
        
        # Should load with various name formats
        rules1 = engine.load_rules("test_client")
        rules2 = engine.load_rules("Test Client")
        rules3 = engine.load_rules("TEST-CLIENT")
        
        assert rules1 == rules2 == rules3


class TestSegmentationValidation:
    """Tests for segmentation validation."""
    
    @pytest.fixture
    def sample_email_data(self):
        return {
            "subject": "Explore What Yanmar Can Do",
            "preview_text": "Learn about the attachments and techniques pros use",
            "html_body": "<html><body>Email content</body></html>",
            "text_body": "Email content"
        }
    
    def test_segmentation_validation_prospects(self, sample_email_data):
        """Test segmentation validation for prospects segment."""
        engine = DynamicRulesEngine()
        
        try:
            result = engine.validate_against_rules(
                sample_email_data,
                "yanmar",
                segment="prospects"
            )
            
            assert "segmentation" in result["validations"]
            seg_result = result["validations"]["segmentation"]
            assert seg_result["segment"] == "prospects"
            
        except FileNotFoundError:
            pytest.skip("Yanmar rules file not yet created")
    
    def test_segmentation_subject_keywords(self, sample_email_data):
        """Test subject line keyword checking."""
        engine = DynamicRulesEngine()
        
        try:
            result = engine.validate_against_rules(
                sample_email_data,
                "yanmar",
                segment="prospects"
            )
            
            seg_result = result["validations"]["segmentation"]
            assert "subject_keywords" in seg_result["checks"]
            
        except FileNotFoundError:
            pytest.skip("Yanmar rules file not yet created")


class TestModuleValidation:
    """Tests for module validation."""
    
    @pytest.fixture
    def email_with_modules(self):
        return {
            "subject": "Test Email",
            "preview_text": "Preview",
            "html_body": """
                <html>
                <body>
                    <h1>FIELD NOTES AUGUST 2025</h1>
                    <div>Explore Our Latest Exclusive Offers</div>
                    <div>Connect With Yanmar</div>
                    <div>770-637-0441</div>
                    <footer>Yanmar America Corporation</footer>
                    <footer>101 International Pkwy</footer>
                </body>
                </html>
            """,
            "text_body": "FIELD NOTES Exclusive Offers Connect With Yanmar"
        }
    
    def test_module_validation_all_segments(self, email_with_modules):
        """Test universal module validation."""
        engine = DynamicRulesEngine()
        
        try:
            result = engine.validate_against_rules(
                email_with_modules,
                "yanmar"
            )
            
            assert "modules" in result["validations"]
            mod_result = result["validations"]["modules"]
            
            # Should find universal modules
            assert len(mod_result["found_modules"]) > 0
            
        except FileNotFoundError:
            pytest.skip("Yanmar rules file not yet created")
    
    def test_missing_required_module(self):
        """Test detection of missing required modules."""
        engine = DynamicRulesEngine()
        
        # Email missing required content
        email_data = {
            "subject": "Test",
            "html_body": "<html><body>Minimal content</body></html>",
            "text_body": "Minimal"
        }
        
        try:
            result = engine.validate_against_rules(
                email_data,
                "yanmar"
            )
            
            # Should have issues for missing modules
            assert len(result["issues"]) > 0
            
        except FileNotFoundError:
            pytest.skip("Yanmar rules file not yet created")


class TestBrandValidation:
    """Tests for brand guideline validation."""
    
    @pytest.fixture
    def email_with_brand_elements(self):
        return {
            "subject": "Test Email",
            "from_name": "Yanmar Tractors",
            "from_email": "yanmartractors@e.yanmartractor.com",
            "html_body": """
                <html>
                <body>
                    <a href="tel:+17706370441">Call 770-637-0441</a>
                    <a href="https://instagram.com/yanmartractorsamerica">Instagram</a>
                    <footer>
                        Yanmar America Corporation<br>
                        101 International Pkwy<br>
                        Adairsville, GA 30103 US
                    </footer>
                </body>
                </html>
            """,
            "links": [
                {"url": "tel:+17706370441", "text": "Call 770-637-0441"},
                {"url": "https://instagram.com/yanmartractorsamerica", "text": "Instagram"}
            ]
        }
    
    def test_brand_phone_validation(self, email_with_brand_elements):
        """Test phone number brand validation."""
        engine = DynamicRulesEngine()
        
        try:
            result = engine.validate_against_rules(
                email_with_brand_elements,
                "yanmar"
            )
            
            assert "brand" in result["validations"]
            brand_result = result["validations"]["brand"]
            
            # Should find phone number
            assert brand_result["brand_checks"].get("phone") is True
            
        except FileNotFoundError:
            pytest.skip("Yanmar rules file not yet created")
    
    def test_brand_from_validation(self, email_with_brand_elements):
        """Test from name/email validation."""
        engine = DynamicRulesEngine()
        
        try:
            result = engine.validate_against_rules(
                email_with_brand_elements,
                "yanmar"
            )
            
            # Should pass with correct from fields
            brand_warnings = [
                w for w in result["warnings"]
                if "from" in w.lower()
            ]
            assert len(brand_warnings) == 0
            
        except FileNotFoundError:
            pytest.skip("Yanmar rules file not yet created")


class TestDosAndDonts:
    """Tests for dos and don'ts checking."""
    
    def test_detect_placeholder_phone(self):
        """Test detection of placeholder phone numbers."""
        engine = DynamicRulesEngine()
        
        email_data = {
            "subject": "Test Email",
            "html_body": "Call us at 555-555-5555 for more info"
        }
        
        try:
            result = engine.validate_against_rules(
                email_data,
                "yanmar"
            )
            
            # Should catch placeholder phone
            assert any(
                "555-555-5555" in str(warning)
                for warning in result["warnings"]
            )
            
        except FileNotFoundError:
            pytest.skip("Yanmar rules file not yet created")
    
    def test_detect_lorem_ipsum(self):
        """Test detection of lorem ipsum placeholder text."""
        engine = DynamicRulesEngine()
        
        email_data = {
            "subject": "Test Email",
            "html_body": "<p>Lorem ipsum dolor sit amet</p>"
        }
        
        try:
            result = engine.validate_against_rules(
                email_data,
                "yanmar"
            )
            
            # Should catch lorem ipsum
            assert any(
                "lorem ipsum" in str(warning).lower()
                for warning in result["warnings"]
            )
            
        except FileNotFoundError:
            pytest.skip("Yanmar rules file not yet created")
    
    def test_detect_click_here(self):
        """Test detection of 'click here' anti-pattern."""
        engine = DynamicRulesEngine()
        
        email_data = {
            "subject": "Test Email",
            "html_body": '<a href="#">click here</a> for more info'
        }
        
        try:
            result = engine.validate_against_rules(
                email_data,
                "yanmar"
            )
            
            # Should warn about click here
            assert any(
                "click here" in str(warning).lower()
                for warning in result["warnings"]
            )
            
        except FileNotFoundError:
            pytest.skip("Yanmar rules file not yet created")


class TestComplianceValidation:
    """Tests for compliance checking."""
    
    def test_missing_unsubscribe_link(self):
        """Test detection of missing unsubscribe link."""
        engine = DynamicRulesEngine()
        
        email_data = {
            "subject": "Test Email",
            "html_body": "<html><body>Content</body></html>",
            "has_unsubscribe": False
        }
        
        try:
            result = engine.validate_against_rules(
                email_data,
                "yanmar"
            )
            
            # Should flag missing unsubscribe
            assert any(
                "unsubscribe" in str(issue).lower()
                for issue in result["issues"]
            )
            
        except FileNotFoundError:
            pytest.skip("Yanmar rules file not yet created")
    
    def test_cta_uppercase_compliance(self):
        """Test CTA uppercase requirement."""
        engine = DynamicRulesEngine()
        
        email_data = {
            "subject": "Test Email",
            "html_body": "<html><body>Content</body></html>",
            "ctas": [
                {"text": "Click Here", "url": "#"},  # Not uppercase
                {"text": "LEARN MORE", "url": "#"}   # Correct
            ]
        }
        
        try:
            result = engine.validate_against_rules(
                email_data,
                "yanmar"
            )
            
            # Should warn about non-uppercase CTA
            assert any(
                "Click Here" in str(warning)
                for warning in result["warnings"]
            )
            
        except FileNotFoundError:
            pytest.skip("Yanmar rules file not yet created")


class TestHelperMethods:
    """Tests for helper methods."""
    
    def test_get_required_ctas_prospects(self):
        """Test getting required CTAs for prospects segment."""
        engine = DynamicRulesEngine()
        
        try:
            ctas = engine.get_required_ctas("yanmar", "prospects")
            
            assert isinstance(ctas, list)
            assert len(ctas) > 0
            # Should include prospects-specific CTAs
            assert any("JOIN THE COMMUNITY" in cta for cta in ctas)
            
        except FileNotFoundError:
            pytest.skip("Yanmar rules file not yet created")
    
    def test_get_required_ctas_owners(self):
        """Test getting required CTAs for owners segment."""
        engine = DynamicRulesEngine()
        
        try:
            ctas = engine.get_required_ctas("yanmar", "owners")
            
            assert isinstance(ctas, list)
            assert len(ctas) > 0
            # Should include owners-specific CTAs
            assert any("SHOP NOW" in cta for cta in ctas)
            
        except FileNotFoundError:
            pytest.skip("Yanmar rules file not yet created")
    
    def test_get_utm_requirements(self):
        """Test getting UTM requirements."""
        engine = DynamicRulesEngine()
        
        try:
            utm_reqs = engine.get_utm_requirements("yanmar")
            
            assert isinstance(utm_reqs, dict)
            
        except FileNotFoundError:
            pytest.skip("Yanmar rules file not yet created")


class TestStandaloneFunction:
    """Tests for standalone validate_email function."""
    
    def test_standalone_function(self):
        """Test standalone validation function."""
        email_data = {
            "subject": "Test Email",
            "html_body": "<html><body>Content</body></html>"
        }
        
        try:
            result = validate_email(email_data, "yanmar", "prospects")
            
            assert isinstance(result, dict)
            assert "client" in result
            assert result["client"] == "yanmar"
            assert "passed" in result
            
        except FileNotFoundError:
            pytest.skip("Yanmar rules file not yet created")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])