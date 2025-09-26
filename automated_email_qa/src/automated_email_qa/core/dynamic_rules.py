"""
Dynamic Rules Engine for Email QA System
=========================================
Purpose: Allows complete customization of QA rules without code changes
Author: Rishabh Sharma
Date: 2024

This module implements the rules configuration system that enables users to:
- Define brand guidelines and tone
- Configure audience segments
- Set link validation rules
- Specify content modules
- Save and load client-specific rules

Metadata:
---------
Classes:
    DynamicRulesEngine: Main rules management class
    
Key Data Types:
    rules (Dict[str, Any]): Complete rules configuration
        - brand (Dict): Brand guidelines
            - tone (Dict): Tone specifications
                - description (str): Brand tone description
                - examples (List[str]): Example copy
                - keywords (List[str]): Key brand terms
            - cta (Dict): CTA preferences
                - style (str): Text casing style
                - preferred_verbs (List[str]): Action verbs
                - avoided_phrases (List[str]): Phrases to avoid
            - dos (List[str]): Brand requirements
            - donts (List[str]): Brand restrictions
        - segments (Dict[str, Dict]): Audience segment rules
        - links (Dict[str, Dict]): Link validation rules
        - modules (Dict[str, List]): Content module requirements
        - validation (Dict): Validation settings
    
    client_name (str): Name identifier for saved rules
    template (Dict): Default rule template structure
"""

from typing import Dict, List, Any, Optional
import json
from pathlib import Path
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DynamicRulesEngine:
    """
    Manages dynamic QA rules configuration for email validation.
    
    This class provides methods to create, save, load, and validate
    rules configurations that define how emails should be checked
    against requirements.
    
    Attributes:
        rules (Dict[str, Any]): Current active rules configuration
        rules_dir (Path): Directory for storing saved rules
        template (Dict[str, Any]): Default template structure
    """
    
    def __init__(self, rules_dir: str = "saved_rules"):
        """
        Initialize the Dynamic Rules Engine.
        
        Args:
            rules_dir (str): Directory path for saving rules files
                            Default: "saved_rules"
        """
        self.rules: Dict[str, Any] = {}
        self.rules_dir = Path(rules_dir)
        self.rules_dir.mkdir(exist_ok=True, parents=True)
        self.template: Dict[str, Any] = self._create_default_template()
        
        logger.info(f"Initialized DynamicRulesEngine with rules directory: {self.rules_dir}")
    
    def _create_default_template(self) -> Dict[str, Any]:
        """
        Create the default rules template structure.
        
        This template serves as a guide for users and ensures
        all necessary fields are present in the configuration.
        
        Returns:
            Dict[str, Any]: Default template with all rule categories
        """
        return {
            'brand': {
                'tone': {
                    'description': '',  # str: Brand tone description
                    'examples': [],     # List[str]: Good copy examples
                    'keywords': []      # List[str]: Brand keywords
                },
                'cta': {
                    'style': 'UPPERCASE',  # str: CTA text casing
                    'preferred_verbs': [],  # List[str]: Action verbs
                    'avoided_phrases': []   # List[str]: Phrases to avoid
                },
                'dos': [],    # List[str]: Brand requirements
                'donts': []   # List[str]: Brand restrictions
            },
            'segments': {
                # Dict[str, Dict]: Audience segment configurations
                # Example: 'prospects': {'required_modules': ['hero', 'cta']}
            },
            'links': {
                # Dict[str, Dict]: Link validation rules
                # Example: 'primary_cta': {'text': 'LEARN MORE', 'destination': '/products'}
            },
            'modules': {
                # Dict[str, List]: Required content modules per segment
                # Example: 'header': ['logo', 'navigation']
            },
            'validation': {
                'strict_mode': False,        # bool: Enforce exact matching
                'allow_variations': True,    # bool: Allow text variations
                'encoding_tolerance': True,  # bool: Handle encoding issues
                'case_sensitive': False      # bool: Case-sensitive matching
            },
            'metadata': {
                'created_at': datetime.now().isoformat(),  # str: Creation timestamp
                'updated_at': datetime.now().isoformat(),  # str: Last update
                'version': '1.0.0'  # str: Rules version
            }
        }
    
    def create_rules(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new rules configuration from provided data.
        
        Args:
            config (Dict[str, Any]): Configuration data containing:
                - brand_tone (str): Brand tone description
                - cta_style (str): CTA text style
                - preferred_verbs (List[str]): Preferred action verbs
                - dos (List[str]): Brand do's
                - donts (List[str]): Brand don'ts
                - segments (Dict): Segment configurations
                - links (Dict): Link rules
                
        Returns:
            Dict[str, Any]: Complete rules configuration
        """
        rules = self.template.copy()
        
        # Update brand guidelines
        if 'brand_tone' in config:
            rules['brand']['tone']['description'] = config['brand_tone']
        
        if 'cta_style' in config:
            rules['brand']['cta']['style'] = config['cta_style']
            
        if 'preferred_verbs' in config:
            rules['brand']['cta']['preferred_verbs'] = config['preferred_verbs']
        
        if 'dos' in config:
            rules['brand']['dos'] = config['dos']
            
        if 'donts' in config:
            rules['brand']['donts'] = config['donts']
        
        # Update segments
        if 'segments' in config:
            rules['segments'] = config['segments']
        
        # Update links
        if 'links' in config:
            rules['links'] = config['links']
        
        # Update metadata
        rules['metadata']['updated_at'] = datetime.now().isoformat()
        
        self.rules = rules
        logger.info("Created new rules configuration")
        
        return rules
    
    def save_rules(self, client_name: str, rules: Optional[Dict[str, Any]] = None) -> Path:
        """
        Save rules configuration to a JSON file.
        
        Args:
            client_name (str): Client identifier for the rules file
            rules (Optional[Dict[str, Any]]): Rules to save (uses self.rules if None)
            
        Returns:
            Path: Path to the saved rules file
            
        Raises:
            ValueError: If no rules are available to save
        """
        if rules is None:
            rules = self.rules
            
        if not rules:
            raise ValueError("No rules available to save")
        
        # Sanitize client name for filename
        safe_name = "".join(c for c in client_name if c.isalnum() or c in ('-', '_'))
        filepath = self.rules_dir / f"{safe_name}.json"
        
        # Update metadata before saving
        rules['metadata']['updated_at'] = datetime.now().isoformat()
        rules['metadata']['client'] = client_name
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(rules, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved rules for client '{client_name}' to {filepath}")
        return filepath
    
    def load_rules(self, client_name: str) -> Dict[str, Any]:
        """
        Load rules configuration from a saved file.
        
        Args:
            client_name (str): Client identifier to load rules for
            
        Returns:
            Dict[str, Any]: Loaded rules configuration
            
        Raises:
            FileNotFoundError: If rules file doesn't exist
        """
        safe_name = "".join(c for c in client_name if c.isalnum() or c in ('-', '_'))
        filepath = self.rules_dir / f"{safe_name}.json"
        
        if not filepath.exists():
            logger.warning(f"No rules found for client '{client_name}'")
            raise FileNotFoundError(f"No rules found for client '{client_name}'")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            rules = json.load(f)
        
        self.rules = rules
        logger.info(f"Loaded rules for client '{client_name}' from {filepath}")
        
        return rules
    
    def get_available_clients(self) -> List[str]:
        """
        Get list of all clients with saved rules.
        
        Returns:
            List[str]: List of client names with saved rules
        """
        clients = []
        
        for filepath in self.rules_dir.glob("*.json"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    rules = json.load(f)
                    client = rules.get('metadata', {}).get('client', filepath.stem)
                    clients.append(client)
            except (json.JSONDecodeError, KeyError):
                # Use filename if metadata is invalid
                clients.append(filepath.stem)
        
        return sorted(clients)
    
    def validate_rules(self, rules: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Validate rules configuration for completeness and correctness.
        
        Args:
            rules (Dict[str, Any]): Rules configuration to validate
            
        Returns:
            Dict[str, List[str]]: Validation results with warnings and errors
                - errors (List[str]): Critical issues that must be fixed
                - warnings (List[str]): Non-critical issues or suggestions
        """
        errors: List[str] = []
        warnings: List[str] = []
        
        # Check required fields
        if not rules.get('brand'):
            errors.append("Missing 'brand' configuration")
        
        # Check brand configuration
        if rules.get('brand'):
            if not rules['brand'].get('tone', {}).get('description'):
                warnings.append("No brand tone description provided")
            
            if not rules['brand'].get('cta', {}).get('preferred_verbs'):
                warnings.append("No preferred CTA verbs defined")
        
        # Check segments
        if not rules.get('segments'):
            warnings.append("No audience segments defined")
        
        # Check validation settings
        if rules.get('validation', {}).get('strict_mode') and \
           rules.get('validation', {}).get('allow_variations'):
            warnings.append("Strict mode enabled but variations allowed - may conflict")
        
        return {
            'errors': errors,
            'warnings': warnings
        }