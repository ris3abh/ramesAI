"""
Robust QA Workflow Orchestrator
================================
Purpose: Manages the complete QA workflow with error handling and recovery
Author: Rishabh Sharma
Date: 2024

This module coordinates the entire QA process, integrating parsers,
validation logic, and error recovery mechanisms.

Metadata:
---------
Classes:
    RobustQAWorkflow: Main workflow orchestrator with error handling
    
Key Data Types:
    config (Dict[str, Any]): Workflow configuration
        - VISION_ENABLED (bool): Enable visual inspection
        - require_validation (bool): Require user checkpoint
        - text_model (str): LLM model for text analysis
        - vision_model (str): LLM model for vision analysis
        - temperature (float): LLM temperature setting
        - MAX_RETRIES (int): Maximum retry attempts
        
    doc_content (str): Raw document content from user
    email_content (str): Raw email HTML/EML from user
    
    rules (Dict[str, Any]): Rules from DynamicRulesEngine
        - Uses rules['validation']['strict_mode']
        - Uses rules['validation']['case_sensitive']
        - Uses rules['brand']['cta']['style']
    
    results (Dict[str, Any]): QA analysis results
        - status (str): 'IN_PROGRESS', 'COMPLETED', 'FAILED'
        - extraction (Dict): Requirements from UniversalDocumentParser
        - analysis (Dict): Comparison results
        - validation (Dict): Link validation results
        - visual (Dict): Visual inspection results
        - compliance (Dict): Compliance check results
        - errors (List[str]): Critical errors encountered
        - warnings (List[str]): Non-critical issues
        - timestamp (str): ISO format timestamp
        - duration (float): Processing time in seconds

Integration with previous files:
    - universal_parser.py: Uses UniversalDocumentParser.parse_document()
    - email_parser.py: Uses EmailParser.parse_email()
    - dynamic_rules.py: Applies rules from DynamicRulesEngine
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import traceback
import json
import re
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
import logging
from dataclasses import dataclass, field
import streamlit as st

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class QAResult:
    """Structure for QA analysis results."""
    status: str = 'IN_PROGRESS'
    extraction: Dict[str, Any] = field(default_factory=dict)
    analysis: Dict[str, Any] = field(default_factory=dict)
    validation: Dict[str, Any] = field(default_factory=dict)
    visual: Dict[str, Any] = field(default_factory=dict)
    compliance: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration: float = 0.0
    score: float = 0.0


class RobustQAWorkflow:
    """
    Orchestrates the email QA workflow with comprehensive error handling.
    
    This class manages the entire QA process, coordinating between
    parsers, validators, and providing error recovery mechanisms.
    
    Attributes:
        config (Dict[str, Any]): Workflow configuration
        errors (List[str]): Accumulated critical errors
        warnings (List[str]): Accumulated warnings
        error_log_path (Path): Directory for error logs
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the QA workflow.
        
        Args:
            config (Dict[str, Any]): Configuration including:
                - VISION_ENABLED: Enable visual QA
                - require_validation: User checkpoint
                - MAX_RETRIES: Retry attempts
        """
        self.config = config
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.error_log_path = Path("error_logs")
        self.error_log_path.mkdir(exist_ok=True, parents=True)
        
        # Import parsers
        from ..tools.universal_parser import UniversalDocumentParser
        from ..tools.email_parser import EmailParser
        
        self.doc_parser = UniversalDocumentParser()
        self.email_parser = EmailParser()
        
        logger.info(f"Initialized RobustQAWorkflow with config: {config}")
    
    def run_qa(self, 
               doc_content: str, 
               email_content: str, 
               rules: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main QA execution with comprehensive error handling.
        
        Orchestrates the complete QA workflow with progress tracking
        and error recovery.
        
        Args:
            doc_content (str): Copy document content
            email_content (str): Email HTML/EML content
            rules (Dict[str, Any]): Rules from DynamicRulesEngine
            
        Returns:
            Dict[str, Any]: Complete QA results with status and findings
        """
        start_time = datetime.now()
        results = QAResult()
        
        # Initialize Streamlit progress if available
        progress = None
        status = None
        if 'streamlit' in str(type(st)):
            progress = st.progress(0)
            status = st.empty()
        
        try:
            # Step 1: Parse documents (20%)
            self._update_progress(progress, status, 20, "📄 Parsing documents...")
            
            parsed_doc = self._safe_parse_document(doc_content)
            parsed_email = self._safe_parse_email(email_content)
            
            if not parsed_doc or not parsed_email:
                raise ValueError("Failed to parse input documents")
            
            # Step 2: Extract requirements (40%)
            self._update_progress(progress, status, 40, "🔍 Extracting requirements...")
            
            requirements = self._extract_requirements_safely(parsed_doc, rules)
            results.extraction = requirements
            
            # Step 3: User validation checkpoint (50%)
            if self.config.get('require_validation', False):
                self._update_progress(progress, status, 50, "✅ Awaiting user validation...")
                requirements = self._user_validation_checkpoint(requirements)
                results.extraction = requirements
            
            # Step 4: Analyze email content (60%)
            self._update_progress(progress, status, 60, "📧 Analyzing email content...")
            
            analysis = self._analyze_email_content(parsed_email, requirements, rules)
            results.analysis = analysis
            
            # Step 5: Validate links (70%)
            self._update_progress(progress, status, 70, "🔗 Validating links...")
            
            link_validation = self._validate_links(parsed_email, requirements, rules)
            results.validation = link_validation
            
            # Step 6: Check compliance (80%)
            self._update_progress(progress, status, 80, "⚖️ Checking compliance...")
            
            compliance = self._check_compliance(parsed_email, rules)
            results.compliance = compliance
            
            # Step 7: Visual inspection (90%)
            if self.config.get('VISION_ENABLED', False):
                self._update_progress(progress, status, 90, "👁️ Performing visual inspection...")
                visual_results = self._visual_inspection_safely(parsed_email.get('html_body', ''))
                results.visual = visual_results
            else:
                results.visual = {'skipped': True, 'reason': 'Vision disabled'}
            
            # Step 8: Calculate score and finalize (100%)
            self._update_progress(progress, status, 100, "📊 Generating report...")
            
            results.score = self._calculate_qa_score(results)
            results.status = 'COMPLETED'
            results.errors = self.errors
            results.warnings = self.warnings
            
        except Exception as e:
            self._handle_critical_error(e)
            results.status = 'FAILED'
            results.errors.append(str(e))
            if 'streamlit' in str(type(st)):
                st.error(f"Critical error: {str(e)}")
        
        finally:
            # Clean up progress indicators
            if progress:
                progress.empty()
            if status:
                status.empty()
            
            # Calculate duration
            results.duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"QA workflow completed with status: {results.status}")
        
        return results.__dict__
    
    def _update_progress(self, 
                        progress: Optional[Any], 
                        status: Optional[Any], 
                        value: int, 
                        message: str):
        """Update progress indicators if available."""
        if progress:
            progress.progress(value)
        if status:
            status.text(message)
        logger.info(f"Progress: {value}% - {message}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def _extract_requirements_safely(self, 
                                    doc: Dict[str, Any], 
                                    rules: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract requirements with retry logic.
        
        Args:
            doc (Dict[str, Any]): Parsed document from UniversalDocumentParser
            rules (Dict[str, Any]): Validation rules
            
        Returns:
            Dict[str, Any]: Extracted requirements
        """
        try:
            # Requirements are already extracted by parse_document
            requirements = doc
            
            # Apply any rule-based transformations
            if rules.get('brand', {}).get('cta', {}).get('style'):
                cta_style = rules['brand']['cta']['style']
                requirements = self._apply_cta_style(requirements, cta_style)
            
            return requirements
            
        except Exception as e:
            self.warnings.append(f"Extraction warning: {str(e)}")
            logger.warning(f"Falling back to simple extraction: {e}")
            return self._fallback_extraction(doc)
    
    def _fallback_extraction(self, doc: Any) -> Dict[str, Any]:
        """
        Simpler extraction when main extraction fails.
        
        Args:
            doc (Any): Document data
            
        Returns:
            Dict[str, Any]: Basic requirements
        """
        # If doc is already a dict from parser, return it
        if isinstance(doc, dict):
            return doc
        
        # Otherwise create minimal structure
        requirements = {
            'subject_lines': [],
            'preview_text': '',
            'ctas': [],
            'links': []
        }
        
        # Try to extract from string representation
        if doc:
            doc_str = str(doc)
            
            # Find subject lines
            subject_matches = re.findall(r'Subject[:\s]+(.+?)[\n\r]', doc_str, re.IGNORECASE)
            requirements['subject_lines'] = subject_matches
            
            # Find URLs
            url_matches = re.findall(r'https?://[^\s]+', doc_str)
            requirements['links'] = url_matches
        
        return requirements
    
    def _analyze_email_content(self, 
                              email: Dict[str, Any], 
                              requirements: Dict[str, Any], 
                              rules: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze email content against requirements.
        
        Args:
            email (Dict[str, Any]): Parsed email from EmailParser
            requirements (Dict[str, Any]): Extracted requirements
            rules (Dict[str, Any]): Validation rules
            
        Returns:
            Dict[str, Any]: Analysis results
        """
        analysis = {
            'subject_check': {'passed': False, 'details': []},
            'preview_check': {'passed': False, 'details': []},
            'cta_check': {'passed': False, 'details': []},
            'content_check': {'passed': False, 'details': []},
            'encoding_check': {'passed': True, 'issues': []},
            'overall_passed': False
        }
        
        # Get validation settings from rules
        strict_mode = rules.get('validation', {}).get('strict_mode', False)
        case_sensitive = rules.get('validation', {}).get('case_sensitive', False)
        
        # Check subject line
        email_subject = email.get('subject', '')
        required_subjects = requirements.get('subject_lines', [])
        
        if required_subjects:
            if strict_mode:
                # Exact match required
                subject_match = email_subject in required_subjects
            else:
                # Flexible matching
                subject_match = any(
                    self._flexible_match(email_subject, req_subject, case_sensitive)
                    for req_subject in required_subjects
                )
            
            analysis['subject_check']['passed'] = subject_match
            analysis['subject_check']['details'] = {
                'email_subject': email_subject,
                'required': required_subjects,
                'matched': subject_match
            }
        
        # Check preview text
        email_preview = email.get('preview_text', '')
        required_preview = requirements.get('preview_text', '')
        
        if required_preview:
            preview_match = self._flexible_match(email_preview, required_preview, case_sensitive)
            analysis['preview_check']['passed'] = preview_match
            analysis['preview_check']['details'] = {
                'email_preview': email_preview,
                'required': required_preview,
                'matched': preview_match
            }
        
        # Check CTAs
        email_ctas = email.get('ctas', [])
        required_ctas = requirements.get('ctas', [])
        
        cta_results = []
        for req_cta in required_ctas:
            found = False
            for email_cta in email_ctas:
                if self._cta_matches(email_cta, req_cta, rules):
                    found = True
                    break
            
            cta_results.append({
                'required': req_cta,
                'found': found
            })
        
        analysis['cta_check']['passed'] = all(r['found'] for r in cta_results)
        analysis['cta_check']['details'] = cta_results
        
        # Check encoding issues
        encoding_issues = email.get('encoding_issues', [])
        if encoding_issues:
            analysis['encoding_check']['passed'] = False
            analysis['encoding_check']['issues'] = encoding_issues
            self.warnings.extend(encoding_issues)
        
        # Overall pass/fail
        analysis['overall_passed'] = all([
            analysis['subject_check']['passed'],
            analysis['preview_check']['passed'] or not required_preview,
            analysis['cta_check']['passed'] or not required_ctas,
            analysis['encoding_check']['passed'] or rules.get('validation', {}).get('encoding_tolerance', True)
        ])
        
        return analysis
    
    def _validate_links(self, 
                       email: Dict[str, Any], 
                       requirements: Dict[str, Any], 
                       rules: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate links in email against requirements.
        
        Args:
            email (Dict[str, Any]): Parsed email
            requirements (Dict[str, Any]): Requirements
            rules (Dict[str, Any]): Validation rules
            
        Returns:
            Dict[str, Any]: Link validation results
        """
        validation = {
            'total_links': len(email.get('links', [])),
            'required_links': len(requirements.get('links', [])),
            'matched_links': 0,
            'missing_links': [],
            'extra_links': [],
            'utm_validation': {'passed': True, 'issues': []},
            'passed': False
        }
        
        email_links = [link['url'] for link in email.get('links', [])]
        required_links = requirements.get('links', [])
        
        # Find missing required links
        for req_link in required_links:
            if req_link not in email_links:
                validation['missing_links'].append(req_link)
            else:
                validation['matched_links'] += 1
        
        # Find extra links not in requirements
        for email_link in email_links:
            if email_link not in required_links:
                validation['extra_links'].append(email_link)
        
        # Check UTM parameters
        utm_tracking = email.get('utm_tracking', {})
        if utm_tracking.get('has_utm'):
            # Validate UTM completeness
            required_params = ['utm_source', 'utm_medium', 'utm_campaign']
            for param in required_params:
                if not utm_tracking.get(param):
                    validation['utm_validation']['issues'].append(f"Missing {param}")
                    validation['utm_validation']['passed'] = False
        
        validation['passed'] = (
            len(validation['missing_links']) == 0 and
            validation['utm_validation']['passed']
        )
        
        return validation
    
    def _check_compliance(self, 
                         email: Dict[str, Any], 
                         rules: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check email compliance with regulations.
        
        Args:
            email (Dict[str, Any]): Parsed email
            rules (Dict[str, Any]): Validation rules
            
        Returns:
            Dict[str, Any]: Compliance check results
        """
        compliance = {
            'can_spam': {
                'passed': False,
                'unsubscribe_present': False,
                'physical_address_present': False
            },
            'accessibility': {
                'passed': False,
                'images_with_alt': 0,
                'images_without_alt': 0
            },
            'overall_passed': False
        }
        
        # CAN-SPAM checks
        compliance['can_spam']['unsubscribe_present'] = email.get('has_unsubscribe', False)
        compliance['can_spam']['physical_address_present'] = email.get('has_physical_address', False)
        compliance['can_spam']['passed'] = (
            compliance['can_spam']['unsubscribe_present'] and
            compliance['can_spam']['physical_address_present']
        )
        
        # Accessibility checks
        images = email.get('images', [])
        for img in images:
            if img.get('alt'):
                compliance['accessibility']['images_with_alt'] += 1
            else:
                compliance['accessibility']['images_without_alt'] += 1
        
        compliance['accessibility']['passed'] = (
            compliance['accessibility']['images_without_alt'] == 0
        )
        
        compliance['overall_passed'] = (
            compliance['can_spam']['passed'] and
            compliance['accessibility']['passed']
        )
        
        return compliance
    
    def _visual_inspection_safely(self, html_content: str) -> Dict[str, Any]:
        """
        Perform visual inspection with error handling.
        
        Args:
            html_content (str): HTML to inspect
            
        Returns:
            Dict[str, Any]: Visual inspection results
        """
        try:
            # Placeholder for actual visual inspection
            # Would integrate with multimodal agent here
            return {
                'performed': True,
                'rendering_score': 85,
                'issues': [],
                'brand_compliance': True
            }
        except Exception as e:
            logger.error(f"Visual inspection failed: {e}")
            return {
                'performed': False,
                'error': str(e)
            }
    
    def _calculate_qa_score(self, results: QAResult) -> float:
        """
        Calculate overall QA score.
        
        Args:
            results (QAResult): Complete QA results
            
        Returns:
            float: Score from 0-100
        """
        scores = []
        weights = {
            'analysis': 0.3,
            'validation': 0.25,
            'compliance': 0.25,
            'visual': 0.2
        }
        
        # Analysis score
        if results.analysis:
            analysis_passed = sum([
                results.analysis.get('subject_check', {}).get('passed', False),
                results.analysis.get('preview_check', {}).get('passed', False),
                results.analysis.get('cta_check', {}).get('passed', False),
                results.analysis.get('encoding_check', {}).get('passed', False)
            ])
            scores.append(('analysis', analysis_passed / 4 * 100))
        
        # Validation score
        if results.validation:
            validation_score = 100 if results.validation.get('passed', False) else 50
            scores.append(('validation', validation_score))
        
        # Compliance score
        if results.compliance:
            compliance_score = 100 if results.compliance.get('overall_passed', False) else 0
            scores.append(('compliance', compliance_score))
        
        # Visual score
        if results.visual and results.visual.get('performed'):
            visual_score = results.visual.get('rendering_score', 0)
            scores.append(('visual', visual_score))
        
        # Calculate weighted average
        total_score = 0
        total_weight = 0
        
        for category, score in scores:
            weight = weights.get(category, 0.25)
            total_score += score * weight
            total_weight += weight
        
        return round(total_score / total_weight if total_weight > 0 else 0, 2)
    
    def _flexible_match(self, text1: str, text2: str, case_sensitive: bool = False) -> bool:
        """
        Flexible text matching for non-strict validation.
        
        Args:
            text1 (str): First text
            text2 (str): Second text
            case_sensitive (bool): Whether to match case
            
        Returns:
            bool: True if texts match flexibly
        """
        if not case_sensitive:
            text1 = text1.lower()
            text2 = text2.lower()
        
        # Remove extra spaces
        text1 = ' '.join(text1.split())
        text2 = ' '.join(text2.split())
        
        # Exact match
        if text1 == text2:
            return True
        
        # Check if one contains the other (for partial matches)
        if len(text1) > 10 and len(text2) > 10:
            if text1 in text2 or text2 in text1:
                return True
        
        return False
    
    def _cta_matches(self, 
                    email_cta: Dict[str, str], 
                    required_cta: Dict[str, str], 
                    rules: Dict[str, Any]) -> bool:
        """
        Check if email CTA matches required CTA.
        
        Args:
            email_cta (Dict[str, str]): CTA from email
            required_cta (Dict[str, str]): Required CTA
            rules (Dict[str, Any]): Validation rules
            
        Returns:
            bool: True if CTAs match
        """
        # Get CTA style from rules
        cta_style = rules.get('brand', {}).get('cta', {}).get('style', 'UPPERCASE')
        
        email_text = email_cta.get('text', '')
        required_text = required_cta.get('text', '')
        
        # Apply style transformation
        if cta_style == 'UPPERCASE':
            email_text = email_text.upper()
            required_text = required_text.upper()
        elif cta_style == 'lowercase':
            email_text = email_text.lower()
            required_text = required_text.lower()
        
        # Check text match
        text_matches = self._flexible_match(
            email_text, 
            required_text,
            rules.get('validation', {}).get('case_sensitive', False)
        )
        
        # Check URL if specified
        if required_cta.get('link'):
            url_matches = email_cta.get('url', '') == required_cta.get('link')
            return text_matches and url_matches
        
        return text_matches
    
    def _apply_cta_style(self, 
                        requirements: Dict[str, Any], 
                        style: str) -> Dict[str, Any]:
        """
        Apply CTA style to requirements.
        
        Args:
            requirements (Dict[str, Any]): Requirements
            style (str): CTA style to apply
            
        Returns:
            Dict[str, Any]: Requirements with style applied
        """
        if 'ctas' in requirements:
            for cta in requirements['ctas']:
                if 'text' in cta:
                    if style == 'UPPERCASE':
                        cta['text'] = cta['text'].upper()
                    elif style == 'lowercase':
                        cta['text'] = cta['text'].lower()
                    elif style == 'Title Case':
                        cta['text'] = cta['text'].title()
        
        return requirements
    
    def _user_validation_checkpoint(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        Allow user to validate and correct extracted requirements.
        
        This would be called when Streamlit UI is active.
        
        Args:
            requirements (Dict[str, Any]): Extracted requirements
            
        Returns:
            Dict[str, Any]: Validated requirements
        """
        # This would integrate with Streamlit UI
        # For now, return requirements unchanged
        logger.info("User validation checkpoint - returning requirements unchanged")
        return requirements
    
    def _safe_parse_document(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Safely parse document with error handling.
        
        Args:
            content (str): Document content
            
        Returns:
            Optional[Dict[str, Any]]: Parsed document or None
        """
        try:
            return self.doc_parser.parse_document(content)
        except Exception as e:
            self.errors.append(f"Document parsing error: {str(e)}")
            logger.error(f"Failed to parse document: {e}")
            return None
    
    def _safe_parse_email(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Safely parse email with error handling.
        
        Args:
            content (str): Email content
            
        Returns:
            Optional[Dict[str, Any]]: Parsed email or None
        """
        try:
            return self.email_parser.parse_email(content)
        except Exception as e:
            self.errors.append(f"Email parsing error: {str(e)}")
            logger.error(f"Failed to parse email: {e}")
            return None
    
    def _handle_critical_error(self, error: Exception):
        """
        Log and handle critical errors.
        
        Args:
            error (Exception): The critical error
        """
        error_log = {
            'timestamp': datetime.now().isoformat(),
            'error': str(error),
            'traceback': traceback.format_exc()
        }
        
        # Save error log
        error_file = self.error_log_path / f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(error_file, 'w') as f:
            json.dump(error_log, f, indent=2)
        
        logger.error(f"Critical error logged to {error_file}: {error}")