"""
Email Parser for QA System
==========================
Purpose: Parse and analyze email content for QA validation
Author: Rishabh Sharma
Date: 2024

This module extracts structured components from email content (HTML/EML)
for validation against requirements extracted by UniversalDocumentParser.

Metadata:
---------
Classes:
    EmailParser: Main parser for email content analysis
    
Key Data Types:
    email_content (str): Raw email content
        - HTML format: Direct HTML string
        - EML format: Email message format with headers
    
    parsed_components (Dict[str, Any]): Extracted email components
        - subject (str): Email subject line
        - from (str): Sender email address
        - from_name (str): Sender display name
        - preview_text (str): Hidden preview/preheader text
        - html_body (str): Full HTML body content
        - plain_body (str): Plain text body content
        - links (List[Dict[str, Any]]): All links found
            - text (str): Link display text
            - url (str): Link destination
            - is_cta (bool): Whether link is a CTA button
            - utm_params (Dict[str, str]): UTM tracking parameters
        - ctas (List[Dict[str, Any]]): Identified CTA buttons
        - images (List[Dict[str, str]]): Image elements
            - src (str): Image source URL
            - alt (str): Alt text for accessibility
            - width (str): Image width
            - height (str): Image height
        - headers (Dict[str, str]): Email headers
        - unsubscribe_link (str): Unsubscribe URL
        - has_physical_address (bool): CAN-SPAM compliance check
        - encoding_issues (List[str]): Found encoding problems

Integration with previous files:
    - universal_parser.py: Parsed components are compared with extracted requirements
        - subject matches requirements['subject_lines']
        - CTAs match requirements['ctas']
        - Links match requirements['links']
    - dynamic_rules.py: Validation behavior controlled by rules
        - rules['validation']['strict_mode'] affects comparison
        - rules['validation']['case_sensitive'] affects text matching
        - rules['brand']['cta']['style'] validates CTA formatting
"""

import email
from email import policy
from email.parser import Parser
from bs4 import BeautifulSoup, Tag
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs
import re
import logging
from dataclasses import dataclass, field

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class LinkData:
    """Data structure for link information."""
    text: str
    url: str
    is_cta: bool = False
    utm_params: Dict[str, str] = field(default_factory=dict)
    attributes: Dict[str, str] = field(default_factory=dict)
    parent_classes: List[str] = field(default_factory=list)


class EmailParser:
    """
    Parse and analyze email content for QA validation.
    
    This class extracts structured components from emails that can be
    validated against requirements from UniversalDocumentParser and
    rules from DynamicRulesEngine.
    """
    
    # Patterns for compliance checks
    PHYSICAL_ADDRESS_PATTERNS = [
        r'\d+\s+[\w\s]+(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|court|ct|plaza|pl)',
        r'(?:p\.?o\.?\s*box|po\s*box)\s+\d+',
        r'\d{5}(?:-\d{4})?',  # ZIP code
        r'suite\s+\d+|ste\s+\d+|apt\s+\d+',  # Suite/Apt numbers
    ]
    
    # CTA identification patterns
    CTA_INDICATORS = [
        'button', 'btn', 'cta', 'call-to-action', 
        'action', 'primary', 'secondary'
    ]
    
    def __init__(self):
        """Initialize the Email Parser."""
        self.encoding_issues: List[str] = []
        logger.info("Initialized EmailParser")
    
    def parse_email(self, email_content: str) -> Dict[str, Any]:
        """
        Parse email content to extract all components for QA validation.
        
        Main entry point that detects format and extracts components.
        
        Args:
            email_content (str): Email content (HTML or EML format)
            
        Returns:
            Dict[str, Any]: Extracted email components including:
                - Headers (subject, from)
                - Content (HTML, plain text, preview)
                - Links and CTAs
                - Compliance elements
        """
        # Reset tracking
        self.encoding_issues = []
        
        # Initialize components structure
        components: Dict[str, Any] = {
            'subject': '',
            'from': '',
            'from_name': '',
            'preview_text': '',
            'html_body': '',
            'plain_body': '',
            'links': [],
            'ctas': [],
            'images': [],
            'headers': {},
            'unsubscribe_link': '',
            'has_physical_address': False,
            'has_unsubscribe': False,
            'encoding_issues': [],
            'utm_tracking': {
                'has_utm': False,
                'utm_source': [],
                'utm_medium': [],
                'utm_campaign': []
            }
        }
        
        # Check format and parse accordingly
        if self._is_eml_format(email_content):
            components = self._parse_eml_format(email_content, components)
        else:
            # Assume HTML format
            components['html_body'] = email_content
            components = self._parse_html_content(email_content, components)
        
        # Fix encoding issues (using same fixes as universal_parser.py)
        components = self._fix_encoding_in_components(components)
        
        # Perform compliance checks
        components = self._check_compliance_elements(components)
        
        # Set encoding issues
        components['encoding_issues'] = self.encoding_issues
        
        return components
    
    def _is_eml_format(self, content: str) -> bool:
        """
        Check if content is in EML email format.
        
        Args:
            content (str): Content to check
            
        Returns:
            bool: True if content is EML format
        """
        eml_headers = ['Content-Type:', 'MIME-Version:', 'Subject:', 'From:', 'To:']
        header_count = sum(1 for header in eml_headers if header in content[:1000])
        return header_count >= 3
    
    def _parse_eml_format(self, eml_content: str, components: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse EML format email to extract components.
        
        Args:
            eml_content (str): EML formatted email content
            components (Dict[str, Any]): Components dict to populate
            
        Returns:
            Dict[str, Any]: Updated components dictionary
        """
        try:
            msg = email.message_from_string(eml_content, policy=policy.default)
            
            # Extract headers
            components['subject'] = msg.get('Subject', '')
            components['from'] = msg.get('From', '')
            
            # Parse From header for name and email
            from_header = components['from']
            from_match = re.match(r'(.+?)\s*<(.+?)>', from_header)
            if from_match:
                components['from_name'] = from_match.group(1).strip().strip('"')
                components['from'] = from_match.group(2).strip()
            
            # Store all headers
            for key, value in msg.items():
                components['headers'][key] = value
            
            # Extract body parts
            for part in msg.walk():
                content_type = part.get_content_type()
                
                if content_type == 'text/html':
                    html_payload = part.get_payload(decode=True)
                    if html_payload:
                        components['html_body'] = html_payload.decode('utf-8', errors='replace')
                        # Parse HTML content for links and CTAs
                        components = self._parse_html_content(components['html_body'], components)
                
                elif content_type == 'text/plain':
                    text_payload = part.get_payload(decode=True)
                    if text_payload:
                        components['plain_body'] = text_payload.decode('utf-8', errors='replace')
        
        except Exception as e:
            logger.error(f"Error parsing EML format: {e}")
            self.encoding_issues.append(f"EML parsing error: {str(e)}")
        
        return components
    
    def _parse_html_content(self, html: str, components: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract information from HTML content.
        
        Parses HTML to find preview text, links, CTAs, images, and compliance elements.
        
        Args:
            html (str): HTML content to parse
            components (Dict[str, Any]): Components dict to populate
            
        Returns:
            Dict[str, Any]: Updated components with HTML-extracted data
        """
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # Extract preview text (hidden divs/spans)
            preview_elements = soup.find_all(
                ['div', 'span'],
                style=lambda x: x and any(
                    indicator in x.lower() 
                    for indicator in ['display:none', 'display: none', 'hidden', 'visibility:hidden']
                )
            )
            
            if preview_elements:
                # Take the first hidden element as preview text
                components['preview_text'] = preview_elements[0].get_text(strip=True)
                logger.debug(f"Found preview text: {components['preview_text'][:50]}...")
            
            # Extract all links with comprehensive data
            all_links = []
            for link in soup.find_all('a', href=True):
                link_data = self._extract_link_data(link)
                all_links.append(link_data)
                
                # Identify CTAs
                if self._is_cta(link_data, link):
                    components['ctas'].append({
                        'text': link_data.text,
                        'url': link_data.url,
                        'utm_params': link_data.utm_params
                    })
                
                # Check for unsubscribe link
                if self._is_unsubscribe_link(link_data):
                    components['unsubscribe_link'] = link_data.url
                    components['has_unsubscribe'] = True
                
                # Track UTM parameters
                if link_data.utm_params:
                    components['utm_tracking']['has_utm'] = True
                    for param, value in link_data.utm_params.items():
                        if param in ['utm_source', 'utm_medium', 'utm_campaign']:
                            if value not in components['utm_tracking'][param]:
                                components['utm_tracking'][param].append(value)
            
            components['links'] = [
                {
                    'text': link.text,
                    'url': link.url,
                    'is_cta': link.is_cta,
                    'utm_params': link.utm_params
                }
                for link in all_links
            ]
            
            # Extract images
            for img in soup.find_all('img'):
                img_data = {
                    'src': img.get('src', ''),
                    'alt': img.get('alt', ''),
                    'width': img.get('width', ''),
                    'height': img.get('height', ''),
                    'title': img.get('title', '')
                }
                components['images'].append(img_data)
                
                # Check for missing alt text (accessibility)
                if not img_data['alt']:
                    self.encoding_issues.append(f"Missing alt text for image: {img_data['src'][:50]}")
            
        except Exception as e:
            logger.error(f"Error parsing HTML content: {e}")
            self.encoding_issues.append(f"HTML parsing error: {str(e)}")
        
        return components
    
    def _extract_link_data(self, link_element: Tag) -> LinkData:
        """
        Extract comprehensive data from a link element.
        
        Args:
            link_element (Tag): BeautifulSoup link element
            
        Returns:
            LinkData: Structured link information
        """
        link_data = LinkData(
            text=link_element.get_text(strip=True),
            url=link_element.get('href', ''),
            attributes={k: v for k, v in link_element.attrs.items()}
        )
        
        # Extract parent classes for CTA identification
        parent = link_element.parent
        if parent:
            parent_classes = parent.get('class', [])
            link_data.parent_classes = parent_classes if isinstance(parent_classes, list) else [parent_classes]
        
        # Parse UTM parameters
        try:
            parsed_url = urlparse(link_data.url)
            utm_params = parse_qs(parsed_url.query)
            link_data.utm_params = {
                k: v[0] for k, v in utm_params.items() 
                if k.startswith('utm_')
            }
        except Exception:
            pass
        
        return link_data
    
    def _is_cta(self, link_data: LinkData, link_element: Tag) -> bool:
        """
        Determine if a link is a CTA button.
        
        Uses multiple heuristics:
        - Parent element classes
        - Link text formatting (uppercase)
        - Button-related attributes
        - Link positioning and styling
        
        Args:
            link_data (LinkData): Extracted link data
            link_element (Tag): Original link element
            
        Returns:
            bool: True if link appears to be a CTA
        """
        # Check parent classes for CTA indicators
        parent_class_text = ' '.join(link_data.parent_classes).lower()
        if any(indicator in parent_class_text for indicator in self.CTA_INDICATORS):
            return True
        
        # Check link's own classes
        link_classes = link_element.get('class', [])
        link_class_text = ' '.join(link_classes) if isinstance(link_classes, list) else link_classes
        if any(indicator in link_class_text.lower() for indicator in self.CTA_INDICATORS):
            return True
        
        # Check if text is all uppercase (common CTA pattern from requirements)
        if link_data.text and link_data.text.isupper() and len(link_data.text.split()) <= 4:
            return True
        
        # Check for button role attribute
        if link_element.get('role') == 'button':
            return True
        
        # Check inline styles for button-like styling
        style = link_element.get('style', '')
        if any(prop in style.lower() for prop in ['background-color', 'padding', 'border-radius']):
            return True
        
        return False
    
    def _is_unsubscribe_link(self, link_data: LinkData) -> bool:
        """
        Check if a link is an unsubscribe link.
        
        Args:
            link_data (LinkData): Link data to check
            
        Returns:
            bool: True if link is unsubscribe link
        """
        unsubscribe_indicators = [
            'unsubscribe', 'opt-out', 'opt out', 'remove', 
            'preferences', 'manage subscription', 'email preferences'
        ]
        
        text_lower = link_data.text.lower()
        url_lower = link_data.url.lower()
        
        return any(
            indicator in text_lower or indicator in url_lower 
            for indicator in unsubscribe_indicators
        )
    
    def _check_compliance_elements(self, components: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check for compliance elements (CAN-SPAM, GDPR).
        
        Args:
            components (Dict[str, Any]): Email components
            
        Returns:
            Dict[str, Any]: Components with compliance flags updated
        """
        # Check for physical address (CAN-SPAM requirement)
        full_text = components['html_body'] + ' ' + components['plain_body']
        full_text_lower = full_text.lower()
        
        for pattern in self.PHYSICAL_ADDRESS_PATTERNS:
            if re.search(pattern, full_text, re.IGNORECASE):
                components['has_physical_address'] = True
                logger.debug(f"Found physical address pattern: {pattern}")
                break
        
        # Additional compliance checks
        if not components['has_unsubscribe']:
            self.encoding_issues.append("Missing unsubscribe link (CAN-SPAM requirement)")
        
        if not components['has_physical_address']:
            self.encoding_issues.append("Missing physical address (CAN-SPAM requirement)")
        
        return components
    
    def _fix_encoding_in_components(self, components: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fix encoding issues in all text fields.
        
        Uses the same encoding fixes as UniversalDocumentParser for consistency.
        
        Args:
            components (Dict[str, Any]): Components with potential encoding issues
            
        Returns:
            Dict[str, Any]: Components with encoding fixed
        """
        # Import encoding fixes from universal_parser
        from .universal_parser import UniversalDocumentParser
        
        encoding_fixes = UniversalDocumentParser.ENCODING_FIXES
        
        # Apply fixes to all string fields
        for key, value in components.items():
            if isinstance(value, str):
                original = value
                for broken, fixed in encoding_fixes.items():
                    if broken in value:
                        value = value.replace(broken, fixed)
                        self.encoding_issues.append(f"Fixed '{broken}' in {key}")
                components[key] = value
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                # Fix encoding in list of dicts (like links, ctas)
                for item in value:
                    for item_key, item_value in item.items():
                        if isinstance(item_value, str):
                            for broken, fixed in encoding_fixes.items():
                                if broken in item_value:
                                    item[item_key] = item_value.replace(broken, fixed)
        
        return components