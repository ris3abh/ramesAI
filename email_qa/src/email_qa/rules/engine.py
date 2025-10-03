"""
Dynamic Rules Engine for Email QA System
=========================================
Loads and applies client-specific validation rules from JSON files.

This allows different clients to have different requirements without
changing code. Rules are stored in JSON files under rules/clients/

Author: Rishabh Sharma
Date: 2025
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class DynamicRulesEngine:
    """
    Load and apply client-specific email QA rules.
    
    Rules can include:
    - Segmentation requirements (Prospects vs Owners, different audiences)
    - Required modules per campaign/segment
    - Required CTAs per segment
    - UTM parameter requirements
    - Brand guidelines (phone, social handles, colors, fonts)
    - Dos and Don'ts for copywriting
    - Compliance requirements
    
    Usage:
        engine = DynamicRulesEngine()
        rules = engine.load_rules("yanmar")
        results = engine.validate_against_rules(email_data, "yanmar", "prospects")
    """
    
    def __init__(self, rules_dir: Optional[str] = None):
        """
        Initialize rules engine.
        
        Args:
            rules_dir: Directory containing client rule JSON files.
                      Defaults to 'rules/clients' relative to this file.
        """
        if rules_dir is None:
            # Default to rules/clients/ in the project
            current_file = Path(__file__).resolve()
            self.rules_dir = current_file.parent / "clients"
        else:
            self.rules_dir = Path(rules_dir)
        
        # Create rules directory if it doesn't exist
        self.rules_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache loaded rules to avoid re-reading files
        self.loaded_rules: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"DynamicRulesEngine initialized with rules_dir: {self.rules_dir}")
    
    def load_rules(self, client_name: str) -> Dict[str, Any]:
        """
        Load rules for a specific client.
        
        Args:
            client_name: Client name (e.g., "yanmar", "welltower", "dr_berg")
            
        Returns:
            Dict of rules for the client
            
        Raises:
            FileNotFoundError: If client rules file doesn't exist
        """
        # Normalize client name (lowercase, underscores)
        client_key = client_name.lower().replace(" ", "_").replace("-", "_")
        
        # Check cache first
        if client_key in self.loaded_rules:
            logger.debug(f"Using cached rules for {client_name}")
            return self.loaded_rules[client_key]
        
        # Load from file
        rules_file = self.rules_dir / f"{client_key}.json"
        
        if not rules_file.exists():
            logger.error(f"Rules file not found: {rules_file}")
            raise FileNotFoundError(
                f"No rules file found for client '{client_name}' at {rules_file}. "
                f"Create a JSON rules file at that location."
            )
        
        try:
            with open(rules_file, 'r', encoding='utf-8') as f:
                rules = json.load(f)
            
            # Validate rules structure
            self._validate_rules_structure(rules, client_name)
            
            logger.info(f"Loaded rules for {client_name} from {rules_file}")
            self.loaded_rules[client_key] = rules
            return rules
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in rules file {rules_file}: {e}")
            raise ValueError(f"Invalid JSON in rules file for {client_name}: {e}")
        except Exception as e:
            logger.error(f"Failed to load rules for {client_name}: {e}")
            raise
    
    def _validate_rules_structure(self, rules: Dict[str, Any], client_name: str):
        """Validate that rules have expected structure."""
        required_keys = ["client_name"]
        optional_keys = [
            "segmentation", "modules", "ctas", "utm_requirements",
            "brand", "dos_and_donts", "compliance"
        ]
        
        # Check required keys
        for key in required_keys:
            if key not in rules:
                raise ValueError(
                    f"Rules for {client_name} missing required key: '{key}'"
                )
        
        # Log what sections are present
        present_sections = [k for k in optional_keys if k in rules]
        logger.debug(f"Rules for {client_name} contain sections: {present_sections}")
    
    def validate_against_rules(
        self,
        email_data: Dict[str, Any],
        client_name: str,
        segment: Optional[str] = None,
        campaign: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate email data against client rules.
        
        Args:
            email_data: Parsed email data from email_parser
            client_name: Client name
            segment: Segment type (e.g., "prospects", "owners")
            campaign: Campaign identifier (e.g., "august_field_notes")
            
        Returns:
            Validation results with issues, warnings, and detailed checks
        """
        try:
            rules = self.load_rules(client_name)
        except FileNotFoundError:
            return {
                "client": client_name,
                "segment": segment,
                "campaign": campaign,
                "passed": False,
                "error": f"No rules file found for client '{client_name}'",
                "issues": [f"No rules configured for client '{client_name}'"],
                "warnings": [],
                "validations": {}
            }
        
        results = {
            "client": client_name,
            "segment": segment,
            "campaign": campaign,
            "passed": True,
            "issues": [],
            "warnings": [],
            "validations": {}
        }
        
        # Run each validation section
        if "segmentation" in rules and segment:
            seg_result = self._validate_segmentation(
                email_data, rules["segmentation"], segment
            )
            results["validations"]["segmentation"] = seg_result
            results["issues"].extend(seg_result.get("issues", []))
            results["warnings"].extend(seg_result.get("warnings", []))
        
        if "modules" in rules:
            mod_result = self._validate_modules(
                email_data, rules["modules"], segment, campaign
            )
            results["validations"]["modules"] = mod_result
            results["issues"].extend(mod_result.get("issues", []))
            results["warnings"].extend(mod_result.get("warnings", []))
        
        if "brand" in rules:
            brand_result = self._validate_brand(
                email_data, rules["brand"]
            )
            results["validations"]["brand"] = brand_result
            results["warnings"].extend(brand_result.get("warnings", []))
        
        if "dos_and_donts" in rules:
            copy_result = self._check_dos_and_donts(
                email_data, rules["dos_and_donts"]
            )
            results["validations"]["copywriting"] = copy_result
            results["warnings"].extend(copy_result.get("warnings", []))
        
        # AFTER (add the warnings line):
        if "compliance" in rules:
            compliance_result = self._validate_compliance(
                email_data, rules["compliance"]
            )
            results["validations"]["compliance"] = compliance_result
            results["issues"].extend(compliance_result.get("issues", []))
            results["warnings"].extend(compliance_result.get("warnings", []))
        
        # Overall pass/fail
        if results["issues"]:
            results["passed"] = False
        
        logger.info(
            f"Validation complete for {client_name} ({segment}): "
            f"{len(results['issues'])} issues, {len(results['warnings'])} warnings"
        )
        
        return results
    
    def _validate_segmentation(
        self,
        email_data: Dict[str, Any],
        segmentation_rules: Dict[str, Any],
        segment: str
    ) -> Dict[str, Any]:
        """Validate segmentation requirements."""
        result = {
            "segment": segment,
            "checks": {},
            "issues": [],
            "warnings": []
        }
        
        # Get segment rules
        segment_rules = segmentation_rules.get(segment, {})
        if not segment_rules:
            result["warnings"].append(
                f"No segmentation rules defined for segment '{segment}'"
            )
            return result
        
        # Check subject line keywords
        if "required_subject_keywords" in segment_rules:
            subject = email_data.get("subject", "").lower()
            keywords = segment_rules["required_subject_keywords"]
            
            found_keywords = [kw for kw in keywords if kw.lower() in subject]
            missing_keywords = [kw for kw in keywords if kw.lower() not in subject]
            
            result["checks"]["subject_keywords"] = {
                "required": keywords,
                "found": found_keywords,
                "missing": missing_keywords
            }
            
            if missing_keywords:
                result["warnings"].append(
                    f"Subject line missing keywords for {segment} segment: {missing_keywords}"
                )
        
        # Check preview text keywords
        if "required_preview_keywords" in segment_rules:
            preview = email_data.get("preview_text", "").lower()
            keywords = segment_rules["required_preview_keywords"]
            
            found_keywords = [kw for kw in keywords if kw.lower() in preview]
            missing_keywords = [kw for kw in keywords if kw.lower() not in preview]
            
            result["checks"]["preview_keywords"] = {
                "required": keywords,
                "found": found_keywords,
                "missing": missing_keywords
            }
            
            if missing_keywords:
                result["warnings"].append(
                    f"Preview text missing keywords for {segment} segment: {missing_keywords}"
                )
        
        return result
    
    def _validate_modules(
        self,
        email_data: Dict[str, Any],
        module_rules: Dict[str, Any],
        segment: Optional[str],
        campaign: Optional[str]
    ) -> Dict[str, Any]:
        """Validate required modules/sections are present."""
        result = {
            "required_modules": [],
            "found_modules": [],
            "missing_modules": [],
            "issues": [],
            "warnings": []
        }
        
        # Determine which modules to check
        required_modules = []
        
        # Add segment-specific modules
        if segment and segment in module_rules:
            required_modules.extend(module_rules[segment])
        
        # Add campaign-specific modules
        if campaign and campaign in module_rules:
            required_modules.extend(module_rules[campaign])
        
        # Add universal modules
        if "all" in module_rules:
            required_modules.extend(module_rules["all"])
        
        if not required_modules:
            result["warnings"].append(
                "No module requirements defined"
            )
            return result
        
        result["required_modules"] = [m.get("name", "Unknown") for m in required_modules]
        
        # Check for module presence
        email_html = email_data.get("html_body", "").lower()
        email_text = email_data.get("text_body", "").lower()
        full_content = f"{email_html} {email_text}"
        
        for module in required_modules:
            module_name = module.get("name", "")
            module_keywords = module.get("keywords", [])
            is_required = module.get("required", True)
            
            # Check if any keywords present
            found = any(
                keyword.lower() in full_content
                for keyword in module_keywords
            )
            
            if found:
                result["found_modules"].append(module_name)
            else:
                result["missing_modules"].append(module_name)
                if is_required:
                    result["issues"].append(
                        f"Required module missing: {module_name}"
                    )
                else:
                    result["warnings"].append(
                        f"Optional module missing: {module_name}"
                    )
        
        return result
    
    def _validate_brand(
        self,
        email_data: Dict[str, Any],
        brand_rules: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate brand guidelines."""
        result = {
            "brand_checks": {},
            "warnings": []
        }
        
        # Check phone number
        if "phone" in brand_rules:
            required_phone = brand_rules["phone"]
            phone_links = [
                link for link in email_data.get("links", [])
                if link.get("url", "").startswith("tel:")
            ]
            
            phone_found = any(
                required_phone.replace("-", "").replace(" ", "").replace("(", "").replace(")", "") in
                link["url"].replace("tel:", "").replace("-", "").replace(" ", "").replace("+", "")
                for link in phone_links
            )
            
            result["brand_checks"]["phone"] = phone_found
            if not phone_found:
                result["warnings"].append(
                    f"Brand phone number not found: {required_phone}"
                )
        
        # Check social handles
        if "social_handles" in brand_rules:
            for platform, handle in brand_rules["social_handles"].items():
                handle_lower = handle.lower().strip("@")
                
                # Check in links and text
                found = any(
                    handle_lower in link.get("url", "").lower() or
                    handle_lower in link.get("text", "").lower()
                    for link in email_data.get("links", [])
                )
                
                result["brand_checks"][f"{platform}_handle"] = found
                if not found:
                    result["warnings"].append(
                        f"{platform.title()} handle not found: @{handle}"
                    )
        
        # Check company info
        if "company_info" in brand_rules:
            html = email_data.get("html_body", "")
            for key, value in brand_rules["company_info"].items():
                if value and value not in html:
                    result["warnings"].append(
                        f"Company {key} not found in email: {value}"
                    )
        
        # Check from name/email
        if "from_name" in brand_rules:
            actual_from = email_data.get("from_name", "")
            if actual_from != brand_rules["from_name"]:
                result["warnings"].append(
                    f"From name mismatch: expected '{brand_rules['from_name']}', got '{actual_from}'"
                )
        
        if "from_email" in brand_rules:
            actual_email = email_data.get("from_email", "")
            if actual_email != brand_rules["from_email"]:
                result["warnings"].append(
                    f"From email mismatch: expected '{brand_rules['from_email']}', got '{actual_email}'"
                )
        
        return result
    
    def _check_dos_and_donts(
        self,
        email_data: Dict[str, Any],
        dos_and_donts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check copy against Dos and Don'ts."""
        result = {
            "dos_violations": [],
            "donts_violations": [],
            "warnings": []
        }
        
        # Get all text content
        html = email_data.get("html_body", "").lower()
        text = email_data.get("text_body", "").lower()
        subject = email_data.get("subject", "").lower()
        preview = email_data.get("preview_text", "").lower()
        
        full_text = f"{subject} {preview} {html} {text}"
        
        # Check DON'Ts (forbidden phrases/patterns)
        donts = dos_and_donts.get("donts", [])
        for dont in donts:
            phrase = dont.get("phrase", "").lower()
            reason = dont.get("reason", "")
            severity = dont.get("severity", "warning")  # "error" or "warning"
            
            if phrase in full_text:
                violation = {
                    "phrase": phrase,
                    "reason": reason,
                    "severity": severity
                }
                result["donts_violations"].append(violation)
                result["warnings"].append(
                    f"DON'T violation ({severity}): Found '{phrase}' - {reason}"
                )
        
        # Check DO's (recommended practices - informational)
        dos = dos_and_donts.get("dos", [])
        for do in dos:
            phrase = do.get("phrase", "").lower()
            context = do.get("context", "")
            check_presence = do.get("check_presence", False)
            
            if check_presence and phrase and phrase not in full_text:
                result["warnings"].append(
                    f"DO recommendation: Consider including '{phrase}' - {context}"
                )
        
        return result
    
    def _validate_compliance(
        self,
        email_data: Dict[str, Any],
        compliance_rules: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate compliance requirements."""
        result = {
            "compliance_checks": {},
            "issues": [],
            "warnings": []
        }
        
        # Check required elements
        required_elements = compliance_rules.get("required_elements", [])
        for element in required_elements:
            if element == "unsubscribe_link":
                has_unsub = email_data.get("has_unsubscribe", False)
                result["compliance_checks"]["unsubscribe"] = has_unsub
                if not has_unsub:
                    result["issues"].append(
                        "Missing required unsubscribe link (CAN-SPAM violation)"
                    )
            
            elif element == "physical_address":
                html = email_data.get("html_body", "")
                # Basic check for address pattern (can be enhanced)
                has_address = bool(
                    "street" in html.lower() or "pkwy" in html.lower() or
                    "avenue" in html.lower() or "road" in html.lower()
                )
                result["compliance_checks"]["physical_address"] = has_address
                if not has_address:
                    result["warnings"].append(
                        "Physical address may be missing (CAN-SPAM requires it)"
                    )
            
            elif element == "company_name":
                html = email_data.get("html_body", "")
                from_name = email_data.get("from_name", "")
                # Check if company name appears
                has_company = bool(from_name)
                result["compliance_checks"]["company_name"] = has_company
                if not has_company:
                    result["warnings"].append(
                        "Company name should be clearly visible"
                    )
        
        # Check CTA style requirements
        if "cta_style" in compliance_rules:
            cta_style = compliance_rules["cta_style"]
            required_case = cta_style.get("case", "")
            
            if required_case:
                ctas = email_data.get("ctas", [])
                for cta in ctas:
                    cta_text = cta.get("text", "")
                    if required_case == "UPPERCASE" and cta_text != cta_text.upper():
                        result["warnings"].append(
                            f"CTA not uppercase: '{cta_text}'"
                        )
                    elif required_case == "Title Case" and not cta_text.istitle():
                        result["warnings"].append(
                            f"CTA not title case: '{cta_text}'"
                        )
        
        return result
    
    def get_required_ctas(
        self,
        client_name: str,
        segment: Optional[str] = None
    ) -> List[str]:
        """
        Get list of required CTAs for client and segment.
        
        Args:
            client_name: Client name
            segment: Segment (e.g., "prospects", "owners")
            
        Returns:
            List of required CTA texts
        """
        try:
            rules = self.load_rules(client_name)
        except FileNotFoundError:
            return []
        
        if "ctas" not in rules:
            return []
        
        ctas = rules["ctas"]
        
        # Get segment-specific CTAs
        if segment and segment in ctas:
            return ctas[segment]
        # Fallback to "all" CTAs
        elif "all" in ctas:
            return ctas["all"]
        else:
            return []
    
    def get_utm_requirements(self, client_name: str) -> Dict[str, Any]:
        """
        Get UTM parameter requirements for client.
        
        Args:
            client_name: Client name
            
        Returns:
            Dict with UTM requirements
        """
        try:
            rules = self.load_rules(client_name)
        except FileNotFoundError:
            return {}
        
        return rules.get("utm_requirements", {})


# Standalone function for direct use
def validate_email(
    email_data: Dict[str, Any],
    client_name: str,
    segment: Optional[str] = None,
    campaign: Optional[str] = None,
    rules_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Direct function to validate email without instantiating engine.
    
    Args:
        email_data: Parsed email data
        client_name: Client name
        segment: Segment identifier
        campaign: Campaign identifier
        rules_dir: Optional custom rules directory
        
    Returns:
        Validation results
    """
    engine = DynamicRulesEngine(rules_dir)
    return engine.validate_against_rules(email_data, client_name, segment, campaign)