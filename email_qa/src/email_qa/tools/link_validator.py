"""
Link Validator Tool for Email QA System
========================================
Validates links, CTAs, and UTM parameters with HTTP status checks.

Author: Rishabh Sharma
Date: 2025
"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, List, Dict, Any
import requests
import json
import logging
import re
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


class LinkValidatorInput(BaseModel):
    """Input schema for Link Validator Tool."""
    email_links: str = Field(
        ...,
        description="JSON string of links extracted from email"
    )
    required_links: str = Field(
        ...,
        description="JSON string of required links from copy doc"
    )
    check_http_status: bool = Field(
        default=True,
        description="Whether to check HTTP status of links (slower but thorough)"
    )


class LinkValidatorTool(BaseTool):
    """
    Validate email links against requirements.
    
    Checks:
    - All required CTAs are present
    - Links return 200 status (optional, slower)
    - UTM parameters are correct
    - Tracking links are properly formatted
    - Phone numbers match requirements
    - Social media handles match requirements
    """
    
    name: str = "Link Validator"
    description: str = (
        "Validates all links in email against copy document requirements. "
        "Checks CTA presence, link functionality, UTM parameters, and tracking links. "
        "Use this after parsing both the copy doc and email HTML."
    )
    args_schema: Type[BaseModel] = LinkValidatorInput
    
    def _run(
        self,
        email_links: str,
        required_links: str,
        check_http_status: bool = True
    ) -> str:
        """
        Validate links against requirements.
        
        Args:
            email_links: JSON string of links from email
            required_links: JSON string of required links from copy doc
            check_http_status: Whether to check HTTP status codes
            
        Returns:
            JSON string with validation results
        """
        try:
            # Parse inputs
            email_data = json.loads(email_links)
            required_data = json.loads(required_links)
            
            # ===== ADD THIS NORMALIZATION BLOCK =====
            # Normalize to expected format if agent sent arrays
            if isinstance(email_data, list):
                email_data = {"ctas": email_data, "links": email_data}
            if isinstance(required_data, list):
                required_data = {"required_ctas": required_data, "utm_requirements": {}}
            # ===== END NORMALIZATION BLOCK =====
            
            results = {
                "success": True,
                "cta_validation": {},
                "link_status": {},
                "utm_validation": {},
                "phone_validation": {},
                "social_validation": {},
                "issues": [],
                "warnings": []
            }
            
            # 1. Validate CTAs
            results["cta_validation"] = self._validate_ctas(
                email_data.get("ctas", []),
                required_data.get("required_ctas", [])
            )

            # 2. Check HTTP status (optional)
            if check_http_status:
                results["link_status"] = self._check_link_status(
                    email_data.get("links", [])
                )
            
            # 3. Validate UTM parameters
            results["utm_validation"] = self._validate_utm_params(
                email_data.get("links", []),
                required_data.get("utm_requirements", {})
            )
            
            # 4. Validate phone numbers
            results["phone_validation"] = self._validate_phone_numbers(
                email_data.get("links", []),
                required_data.get("required_phone", "")
            )
            
            # 5. Validate social media handles
            results["social_validation"] = self._validate_social_handles(
                email_data.get("links", []),
                required_data.get("required_social", {})
            )
            
            # Collect all issues
            for validation_type, validation_data in results.items():
                if isinstance(validation_data, dict) and "issues" in validation_data:
                    results["issues"].extend(validation_data["issues"])
                if isinstance(validation_data, dict) and "warnings" in validation_data:
                    results["warnings"].extend(validation_data["warnings"])
            
            # Overall success
            if results["issues"]:
                results["success"] = False
            
            logger.info(
                f"Link validation complete: "
                f"{len(results['issues'])} issues, "
                f"{len(results['warnings'])} warnings"
            )
            
            return json.dumps(results, indent=2)
            
        except Exception as e:
            logger.error(f"Link validation failed: {e}", exc_info=True)
            return json.dumps({
                "success": False,
                "error": str(e)
            })
    
    def _validate_ctas(
        self,
        email_ctas: List[Dict[str, Any]],
        required_ctas: List[str]
    ) -> Dict[str, Any]:
        """Validate that all required CTAs are present."""
        result = {
            "found_ctas": [cta["text"] for cta in email_ctas],
            "required_ctas": required_ctas,
            "missing_ctas": [],
            "issues": [],
            "warnings": []
        }
        
        # Normalize CTA text for comparison (uppercase, remove extra spaces)
        email_cta_texts = [
            cta["text"].strip().upper() 
            for cta in email_ctas
        ]
        
        # Check each required CTA
        for required_cta in required_ctas:
            required_normalized = required_cta.strip().upper()
            if required_normalized not in email_cta_texts:
                result["missing_ctas"].append(required_cta)
                result["issues"].append(
                    f"Missing required CTA: '{required_cta}'"
                )
        
        # Check if CTAs are uppercase (best practice)
        for cta in email_ctas:
            if cta["text"] != cta["text"].upper():
                result["warnings"].append(
                    f"CTA not uppercase: '{cta['text']}'"
                )
        
        return result
    
    def _check_link_status(
        self,
        links: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Check HTTP status of all links."""
        result = {
            "working_links": [],
            "broken_links": [],
            "issues": [],
            "warnings": []
        }
        
        for link in links:
            url = link.get("url", "")
            
            # Skip mailto and tel links
            if url.startswith(("mailto:", "tel:")):
                continue
            
            # Skip tracking links that redirect (check final destination instead)
            if self._is_tracking_link(url):
                final_url = self._extract_final_url(url)
                if final_url:
                    url = final_url
            
            try:
                # Use HEAD request first (faster)
                response = requests.head(
                    url,
                    timeout=5,
                    allow_redirects=True
                )
                
                # If HEAD fails, try GET
                if response.status_code >= 400:
                    response = requests.get(
                        url,
                        timeout=5,
                        allow_redirects=True
                    )
                
                if response.status_code == 200:
                    result["working_links"].append({
                        "url": link.get("url"),
                        "text": link.get("text"),
                        "status": 200
                    })
                else:
                    result["broken_links"].append({
                        "url": link.get("url"),
                        "text": link.get("text"),
                        "status": response.status_code
                    })
                    result["issues"].append(
                        f"Link returned {response.status_code}: {link.get('text')} -> {url}"
                    )
                    
            except requests.exceptions.Timeout:
                result["warnings"].append(
                    f"Link timed out: {link.get('text')} -> {url}"
                )
            except Exception as e:
                result["broken_links"].append({
                    "url": link.get("url"),
                    "text": link.get("text"),
                    "error": str(e)
                })
                result["issues"].append(
                    f"Link check failed: {link.get('text')} -> {str(e)}"
                )
        
        return result
    
    def _validate_utm_params(
        self,
        links: List[Dict[str, Any]],
        utm_requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate UTM parameters on links."""
        result = {
            "links_with_utm": [],
            "links_missing_utm": [],
            "utm_errors": [],
            "issues": [],
            "warnings": []
        }
        
        required_utm_params = utm_requirements.get("required_params", [])
        utm_values = utm_requirements.get("expected_values", {})
        
        for link in links:
            url = link.get("url", "")
            utm_params = link.get("utm_params", {})
            
            # Skip non-trackable links
            if url.startswith(("mailto:", "tel:", "#")):
                continue
            
            # Check if link should have UTM params
            if required_utm_params:
                # Check for required UTM params
                missing_params = [
                    param for param in required_utm_params
                    if f"utm_{param}" not in utm_params
                ]
                
                if missing_params:
                    result["links_missing_utm"].append({
                        "url": url,
                        "text": link.get("text"),
                        "missing": missing_params
                    })
                    result["warnings"].append(
                        f"Link missing UTM params {missing_params}: {link.get('text')}"
                    )
                else:
                    result["links_with_utm"].append({
                        "url": url,
                        "text": link.get("text"),
                        "params": utm_params
                    })
                
                # Validate UTM values if specified
                for param, expected_value in utm_values.items():
                    actual_value = utm_params.get(f"utm_{param}")
                    if actual_value and actual_value != expected_value:
                        result["utm_errors"].append({
                            "url": url,
                            "param": param,
                            "expected": expected_value,
                            "actual": actual_value
                        })
                        result["issues"].append(
                            f"UTM param mismatch on {link.get('text')}: "
                            f"utm_{param} should be '{expected_value}', got '{actual_value}'"
                        )
        
        return result
    
    def _validate_phone_numbers(
        self,
        links: List[Dict[str, Any]],
        required_phone: str
    ) -> Dict[str, Any]:
        """Validate phone numbers in links."""
        result = {
            "phone_links": [],
            "issues": [],
            "warnings": []
        }
        
        if not required_phone:
            return result
        
        # Normalize required phone (remove formatting, handle country code)
        required_normalized = self._normalize_phone(required_phone)
        
        # Find all phone links
        for link in links:
            url = link.get("url", "")
            text = link.get("text", "")
            
            if url.startswith("tel:"):
                # Extract phone from tel: link
                phone_raw = url.replace("tel:", "")
                phone_normalized = self._normalize_phone(phone_raw)
                
                result["phone_links"].append({
                    "text": text,
                    "phone": phone_normalized,
                    "url": url
                })
                
                # Check if it matches required phone
                if phone_normalized != required_normalized:
                    result["issues"].append(
                        f"Phone number mismatch: Expected {required_phone}, "
                        f"found {phone_raw} in '{text}'"
                    )
            
            # Also check text content for phone numbers
            phone_in_text = re.findall(r'\d{3}[-.]?\d{3}[-.]?\d{4}', text)
            if phone_in_text:
                for phone_match in phone_in_text:
                    phone_normalized = self._normalize_phone(phone_match)
                    if phone_normalized != required_normalized:
                        result["warnings"].append(
                            f"Phone in text doesn't match: {phone_match} vs {required_phone}"
                        )
        
        # Check if required phone is present
        if required_normalized:
            phone_numbers_found = [p["phone"] for p in result["phone_links"]]
            if required_normalized not in phone_numbers_found:
                result["issues"].append(
                    f"Required phone number not found: {required_phone}"
                )
        
        return result
    
    def _normalize_phone(self, phone: str) -> str:
        """
        Normalize phone number for comparison.
        
        Handles:
        - Removing all non-digit characters
        - Stripping US country code (1) if present
        - Returning 10-digit format
        
        Examples:
            "770-637-0441" -> "7706370441"
            "+1-770-637-0441" -> "7706370441"
            "tel:+17706370441" -> "7706370441"
            "1 (770) 637-0441" -> "7706370441"
        """
        # Remove all non-digit characters
        digits_only = re.sub(r'[^\d]', '', phone)
        
        # Strip leading "1" if present (US country code) and we have 11 digits
        if len(digits_only) == 11 and digits_only.startswith('1'):
            digits_only = digits_only[1:]
        
        return digits_only
    
    def _validate_social_handles(
        self,
        links: List[Dict[str, Any]],
        required_social: Dict[str, str]
    ) -> Dict[str, Any]:
        """Validate social media handles."""
        result = {
            "social_links": [],
            "issues": [],
            "warnings": []
        }
        
        # Social media domains
        social_domains = {
            "instagram": ["instagram.com"],
            "facebook": ["facebook.com"],
            "twitter": ["twitter.com", "x.com"],
            "linkedin": ["linkedin.com"],
            "youtube": ["youtube.com", "youtu.be"]
        }
        
        # Find all social links
        for link in links:
            url = link.get("url", "").lower()
            text = link.get("text", "").lower()
            
            for platform, domains in social_domains.items():
                if any(domain in url for domain in domains):
                    # Extract handle/username from URL or text
                    handle = self._extract_social_handle(url, text, platform)
                    result["social_links"].append({
                        "platform": platform,
                        "url": url,
                        "handle": handle,
                        "text": text
                    })
                    
                    # Check against required
                    if platform in required_social:
                        required_handle = required_social[platform].lower().strip("@")
                        if handle and required_handle not in handle:
                            result["issues"].append(
                                f"{platform.title()} handle mismatch: "
                                f"Expected @{required_handle}, found {handle}"
                            )
        
        # Check if all required social platforms are present
        for platform, required_handle in required_social.items():
            found_platforms = [s["platform"] for s in result["social_links"]]
            if platform not in found_platforms:
                result["warnings"].append(
                    f"Required {platform.title()} link not found (@{required_handle})"
                )
        
        return result
    
    def _is_tracking_link(self, url: str) -> bool:
        """Check if URL is a tracking/redirect link."""
        tracking_patterns = [
            'click.e.',
            'link.',
            'track.',
            'redirect.',
            'r.',
            'go.'
        ]
        return any(pattern in url.lower() for pattern in tracking_patterns)
    
    def _extract_final_url(self, tracking_url: str) -> str:
        """Extract final destination from tracking URL."""
        try:
            parsed = urlparse(tracking_url)
            params = parse_qs(parsed.query)
            
            # Common parameter names for destination URLs
            for param_name in ['url', 'dest', 'destination', 'link', 'target']:
                if param_name in params:
                    return params[param_name][0]
            
            return ""
        except:
            return ""
    
    def _extract_social_handle(
        self,
        url: str,
        text: str,
        platform: str
    ) -> str:
        """Extract social media handle from URL or text."""
        # Check text first (e.g., "@yanmartractorsamerica")
        if text.startswith("@"):
            return text.strip("@")
        
        # Extract from URL
        try:
            path = urlparse(url).path.strip("/")
            # Remove common prefixes
            for prefix in ["profile/", "user/", "channel/"]:
                if path.startswith(prefix):
                    path = path.replace(prefix, "")
            return path.split("/")[0] if path else ""
        except:
            return ""


# Standalone function for direct use
def validate_links(
    email_links: str,
    required_links: str,
    check_http_status: bool = True
) -> dict:
    """
    Direct function to validate links without CrewAI wrapper.
    
    Args:
        email_links: JSON string of links from email
        required_links: JSON string of required links
        check_http_status: Whether to check HTTP status
        
    Returns:
        Dict with validation results
    """
    tool = LinkValidatorTool()
    result_json = tool._run(email_links, required_links, check_http_status)
    return json.loads(result_json)