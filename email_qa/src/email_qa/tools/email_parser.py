"""
Email Parser Tool for Email QA System
======================================
Parses .eml and .html email files to extract structured data.

Author: Rishabh Sharma
Date: 2025
"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, List, Dict, Any, Optional
from email import policy
from email.parser import BytesParser
from bs4 import BeautifulSoup
from pathlib import Path
import json
import logging
import re

logger = logging.getLogger(__name__)


class EmailParserInput(BaseModel):
    """Input schema for Email Parser Tool."""
    email_path: str = Field(
        ...,
        description="Path to the .eml or .html email file to parse"
    )


class EmailParserTool(BaseTool):
    """
    Parse email files (.eml or .html) to extract structured data.
    
    Extracts subject, from address, preview text, links, CTAs, and HTML body.
    Handles both .eml format (full email message) and standalone .html files.
    """
    
    name: str = "Email Parser"
    description: str = (
        "Parses email files (.eml or .html) to extract subject line, sender info, "
        "preview text, all links, CTAs, and HTML body content. Use this tool to "
        "analyze email files for QA validation against copy document requirements."
    )
    args_schema: Type[BaseModel] = EmailParserInput
    
    def _run(self, email_path: str) -> str:
        """
        Parse email file and extract components.
        
        Args:
            email_path: Path to .eml or .html file
            
        Returns:
            JSON string with extracted email components
        """
        try:
            # Validate file path
            email_file = Path(email_path)
            if not email_file.exists():
                return json.dumps({
                    "error": f"Email file not found: {email_path}",
                    "success": False
                })
            
            # Determine file type and parse accordingly
            if email_file.suffix.lower() == '.eml':
                result = self._parse_eml_file(email_file)
            elif email_file.suffix.lower() in ['.html', '.htm']:
                result = self._parse_html_file(email_file)
            else:
                return json.dumps({
                    "error": f"Unsupported file type: {email_file.suffix}. Use .eml or .html",
                    "success": False
                })
            
            result["success"] = True
            result["source_file"] = str(email_file.name)
            
            logger.info(
                f"Parsed {email_file.name}: "
                f"{len(result.get('links', []))} links, "
                f"{len(result.get('ctas', []))} CTAs"
            )
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Email parsing failed: {e}", exc_info=True)
            return json.dumps({
                "error": str(e),
                "success": False
            })
    
    def _parse_eml_file(self, email_file: Path) -> Dict[str, Any]:
        """
        Parse .eml email file format.
        
        Args:
            email_file: Path to .eml file
            
        Returns:
            Dict with parsed email components
        """
        with open(email_file, 'rb') as f:
            msg = BytesParser(policy=policy.default).parse(f)
        
        # Extract headers
        subject = msg.get('subject', '')
        from_header = msg.get('from', '')
        to_header = msg.get('to', '')
        
        # Parse from header for name and email
        from_name, from_email = self._parse_from_header(from_header)
        
        # Get HTML body
        html_body = None
        plain_body = None
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == 'text/html':
                    html_body = part.get_content()
                elif content_type == 'text/plain' and plain_body is None:
                    plain_body = part.get_content()
        else:
            content_type = msg.get_content_type()
            if content_type == 'text/html':
                html_body = msg.get_content()
            elif content_type == 'text/plain':
                plain_body = msg.get_content()
        
        # Use HTML body if available, otherwise plain text
        body_to_parse = html_body if html_body else plain_body
        
        # Parse the HTML body for links, CTAs, preview text
        parsed_html = self._parse_html_content(body_to_parse) if body_to_parse else {}
        
        return {
            "subject": subject,
            "from_name": from_name,
            "from_email": from_email,
            "to": to_header,
            "preview_text": parsed_html.get("preview_text", ""),
            "html_body": html_body or "",
            "plain_body": plain_body or "",
            "links": parsed_html.get("links", []),
            "ctas": parsed_html.get("ctas", []),
            "images": parsed_html.get("images", []),
            "has_unsubscribe": parsed_html.get("has_unsubscribe", False)
        }
    
    def _parse_html_file(self, email_file: Path) -> Dict[str, Any]:
        """
        Parse standalone .html email file.
        
        Args:
            email_file: Path to .html file
            
        Returns:
            Dict with parsed email components
        """
        with open(email_file, 'r', encoding='utf-8', errors='replace') as f:
            html_content = f.read()
        
        parsed = self._parse_html_content(html_content)
        
        return {
            "subject": "",  # Not available in standalone HTML
            "from_name": "",
            "from_email": "",
            "to": "",
            "preview_text": parsed.get("preview_text", ""),
            "html_body": html_content,
            "plain_body": "",
            "links": parsed.get("links", []),
            "ctas": parsed.get("ctas", []),
            "images": parsed.get("images", []),
            "has_unsubscribe": parsed.get("has_unsubscribe", False)
        }
    
    def _parse_html_content(self, html: str) -> Dict[str, Any]:
        """
        Parse HTML content to extract links, CTAs, images, preview text.
        
        Args:
            html: HTML string
            
        Returns:
            Dict with parsed components
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # Extract preview text (hidden preheader)
        preview_text = self._extract_preview_text(soup)
        
        # Extract all links
        links = self._extract_links(soup)
        
        # Identify CTAs (buttons/prominent links)
        ctas = self._identify_ctas(soup, links)
        
        # Extract images
        images = self._extract_images(soup)
        
        # Check for unsubscribe link
        has_unsubscribe = self._has_unsubscribe_link(links)
        
        return {
            "preview_text": preview_text,
            "links": links,
            "ctas": ctas,
            "images": images,
            "has_unsubscribe": has_unsubscribe
        }
    
    def _extract_preview_text(self, soup: BeautifulSoup) -> str:
        """
        Extract preview/preheader text (usually hidden with display:none or font-size:0).
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            Preview text string
        """
        # Look for common preview text patterns
        preview_patterns = [
            {'style': re.compile(r'display:\s*none', re.I)},
            {'style': re.compile(r'font-size:\s*0', re.I)},
            {'style': re.compile(r'visibility:\s*hidden', re.I)},
            {'class': re.compile(r'preheader|preview', re.I)},
        ]
        
        for pattern in preview_patterns:
            elements = soup.find_all(attrs=pattern)
            for elem in elements:
                text = elem.get_text(strip=True)
                if text and len(text) > 10:  # Reasonable preview text length
                    return text
        
        return ""
    
    def _extract_links(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract all links from HTML.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            List of dicts with link info
        """
        links = []
        
        for a_tag in soup.find_all('a', href=True):
            url = a_tag['href']
            text = a_tag.get_text(strip=True)
            
            # Parse UTM parameters
            utm_params = self._extract_utm_params(url)
            
            links.append({
                "url": url,
                "text": text,
                "utm_params": utm_params,
                "title": a_tag.get('title', ''),
                "is_tracking_link": self._is_tracking_link(url)
            })
        
        return links
    
    def _identify_ctas(
        self,
        soup: BeautifulSoup,
        links: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Identify CTA buttons from links.
        
        CTAs are typically:
        - Links with button-like styling
        - Links in table cells with button classes
        - Links with specific CTA keywords
        
        Args:
            soup: BeautifulSoup object
            links: List of all links
            
        Returns:
            List of identified CTAs
        """
        ctas = []
        cta_keywords = [
            'button', 'btn', 'cta', 'call-to-action',
            'shop', 'buy', 'get', 'start', 'learn', 'explore'
        ]
        
        for a_tag in soup.find_all('a', href=True):
            # Check if link looks like a CTA
            is_cta = False
            
            # Check classes
            classes = a_tag.get('class', [])
            if any(keyword in ' '.join(classes).lower() for keyword in cta_keywords[:4]):
                is_cta = True
            
            # Check parent elements (buttons often wrapped in tables)
            parent = a_tag.parent
            if parent and parent.name in ['td', 'th']:
                parent_classes = parent.get('class', [])
                if any(keyword in ' '.join(parent_classes).lower() for keyword in cta_keywords[:4]):
                    is_cta = True
            
            # Check link text
            text = a_tag.get_text(strip=True)
            if any(keyword in text.lower() for keyword in cta_keywords[4:]):
                is_cta = True
            
            if is_cta:
                ctas.append({
                    "text": text,
                    "url": a_tag['href'],
                    "style": a_tag.get('style', ''),
                    "classes": ' '.join(classes)
                })
        
        return ctas
    
    def _extract_images(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        Extract image information.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            List of image dicts
        """
        images = []
        
        for img in soup.find_all('img'):
            images.append({
                "src": img.get('src', ''),
                "alt": img.get('alt', ''),
                "width": img.get('width', ''),
                "height": img.get('height', ''),
                "title": img.get('title', '')
            })
        
        return images
    
    def _extract_utm_params(self, url: str) -> Dict[str, str]:
        """
        Extract UTM parameters from URL.
        
        Args:
            url: URL string
            
        Returns:
            Dict of UTM parameters
        """
        utm_params = {}
        
        # Match UTM parameters
        utm_pattern = r'utm_(source|medium|campaign|term|content)=([^&]*)'
        matches = re.findall(utm_pattern, url, re.I)
        
        for key, value in matches:
            utm_params[f'utm_{key.lower()}'] = value
        
        return utm_params
    
    def _is_tracking_link(self, url: str) -> bool:
        """
        Check if URL is a tracking/redirect link.
        
        Args:
            url: URL string
            
        Returns:
            True if tracking link
        """
        tracking_domains = [
            'click.e.', 'link.', 'track.', 'redirect.',
            'r.', 'go.', 'links.', 'clicks.'
        ]
        
        return any(domain in url.lower() for domain in tracking_domains)
    
    def _has_unsubscribe_link(self, links: List[Dict[str, Any]]) -> bool:
        """
        Check if email has unsubscribe link.
        
        Args:
            links: List of link dicts
            
        Returns:
            True if unsubscribe link found
        """
        unsubscribe_keywords = ['unsubscribe', 'opt-out', 'opt out', 'remove']
        
        for link in links:
            text = link.get('text', '').lower()
            url = link.get('url', '').lower()
            if any(keyword in text or keyword in url for keyword in unsubscribe_keywords):
                return True
        
        return False
    
    def _parse_from_header(self, from_header: str) -> tuple[str, str]:
        """
        Parse 'From' header to extract name and email.
        
        Args:
            from_header: From header string (e.g., "Yanmar <info@yanmar.com>")
            
        Returns:
            Tuple of (name, email)
        """
        # Pattern: "Name <email@domain.com>" or just "email@domain.com"
        match = re.match(r'(.+?)\s*<(.+?)>', from_header)
        if match:
            return match.group(1).strip().strip('"'), match.group(2).strip()
        else:
            # Just email address
            return "", from_header.strip()


# Standalone function for direct use
def parse_email_file(email_path: str) -> dict:
    """
    Direct function to parse email without CrewAI wrapper.
    
    Args:
        email_path: Path to .eml or .html file
        
    Returns:
        Dict with parsed email components
        
    Example:
        >>> result = parse_email_file("email.eml")
        >>> print(result['subject'])
        >>> print(f"Found {len(result['links'])} links")
    """
    tool = EmailParserTool()
    result_json = tool._run(email_path)
    return json.loads(result_json)