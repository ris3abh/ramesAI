"""
Automated Email QA Crew
=======================
Purpose: Main CrewAI crew implementation for email QA orchestration
Author: Rishabh Sharma
Date: 2024

This module implements the CrewAI crew that coordinates all QA agents
using a hierarchical process with a manager agent.

Metadata:
---------
Classes:
    AutomatedEmailQaCrew: Main crew class inheriting from CrewBase
    
Key Data Types:
    inputs (Dict[str, Any]): Input data for crew execution
        - client_name (str): Client identifier
        - campaign_name (str): Campaign identifier
        - email_type (str): Type of email (promotional, transactional)
        - document_type (str): Type of document (copy deck, brief)
        - industry (str): Client industry
        - document_content (str): Raw document content
        - email_content (str): Raw email HTML/EML
        - rules (str): JSON string of DynamicRulesEngine rules
        - brand_guidelines (str): JSON string of brand rules
        - compliance_rules (str): JSON string of compliance requirements
        
    crew_output (CrewOutput): Result from crew execution
        - raw (str): Raw output text
        - tasks_output (List[TaskOutput]): Individual task results
        - json_dict (Dict): Structured JSON output
        
Integration with previous files:
    - Uses UniversalDocumentParser for document extraction
    - Uses EmailParser for email analysis
    - Applies rules from DynamicRulesEngine
    - Coordinates with RobustQAWorkflow
    - Loads agent configs from agents.yaml
    - Loads task configs from tasks.yaml
"""

import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import BaseTool, FileReadTool

# Import custom components from previous files
from automated_email_qa.tools.universal_parser import UniversalDocumentParser
from automated_email_qa.tools.email_parser import EmailParser
from automated_email_qa.core.dynamic_rules import DynamicRulesEngine
from automated_email_qa.core.qa_workflow import RobustQAWorkflow

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DocumentParserTool(BaseTool):
    """
    Custom tool wrapping UniversalDocumentParser for CrewAI agents.
    
    Attributes:
        name (str): Tool identifier
        description (str): Tool purpose description
        parser (UniversalDocumentParser): Parser instance
    """
    name: str = "Document Parser"
    description: str = "Parse copy documents to extract email requirements"
    
    def __init__(self):
        super().__init__()
        self.parser = UniversalDocumentParser()
    
    def _run(self, document_content: str, filename: Optional[str] = None) -> str:
        """
        Execute document parsing.
        
        Args:
            document_content (str): Raw document content
            filename (Optional[str]): Original filename for format detection
            
        Returns:
            str: JSON string of extracted requirements
        """
        try:
            requirements = self.parser.parse_document(document_content, filename)
            return json.dumps(requirements, indent=2)
        except Exception as e:
            logger.error(f"Document parsing failed: {e}")
            return json.dumps({"error": str(e)})


class EmailParserTool(BaseTool):
    """
    Custom tool wrapping EmailParser for CrewAI agents.
    
    Attributes:
        name (str): Tool identifier
        description (str): Tool purpose description
        parser (EmailParser): Parser instance
    """
    name: str = "Email Parser"
    description: str = "Parse email content to extract components for validation"
    
    def __init__(self):
        super().__init__()
        self.parser = EmailParser()
    
    def _run(self, email_content: str) -> str:
        """
        Execute email parsing.
        
        Args:
            email_content (str): Raw email HTML/EML content
            
        Returns:
            str: JSON string of extracted email components
        """
        try:
            components = self.parser.parse_email(email_content)
            return json.dumps(components, indent=2)
        except Exception as e:
            logger.error(f"Email parsing failed: {e}")
            return json.dumps({"error": str(e)})


class LinkValidatorTool(BaseTool):
    """
    Tool for validating links and CTAs.
    
    Attributes:
        name (str): Tool identifier
        description (str): Tool purpose description
    """
    name: str = "Link Validator"
    description: str = "Validate links, CTAs, and UTM parameters"
    
    def _run(self, email_content: str, requirements: str) -> str:
        """
        Validate links in email.
        
        Args:
            email_content (str): Email HTML content
            requirements (str): JSON string of link requirements
            
        Returns:
            str: JSON string of validation results
        """
        try:
            from bs4 import BeautifulSoup
            import requests
            from urllib.parse import urlparse, parse_qs
            
            soup = BeautifulSoup(email_content, 'lxml')
            req_dict = json.loads(requirements) if isinstance(requirements, str) else requirements
            
            results = {
                'total_links': 0,
                'valid_links': 0,
                'broken_links': [],
                'cta_validation': [],
                'utm_issues': []
            }
            
            # Extract and validate links
            links = soup.find_all('a', href=True)
            results['total_links'] = len(links)
            
            for link in links:
                link_text = link.get_text(strip=True)
                link_url = link['href']
                
                # Check if link is accessible
                if link_url.startswith('http'):
                    try:
                        response = requests.head(link_url, timeout=5, allow_redirects=True)
                        if response.status_code < 400:
                            results['valid_links'] += 1
                        else:
                            results['broken_links'].append({
                                'url': link_url,
                                'status': response.status_code
                            })
                    except:
                        results['broken_links'].append({
                            'url': link_url,
                            'error': 'Connection failed'
                        })
                
                # Check UTM parameters
                parsed = urlparse(link_url)
                params = parse_qs(parsed.query)
                required_utms = ['utm_source', 'utm_medium', 'utm_campaign']
                missing_utms = [utm for utm in required_utms if utm not in params]
                if missing_utms:
                    results['utm_issues'].append({
                        'url': link_url,
                        'missing': missing_utms
                    })
            
            return json.dumps(results, indent=2)
            
        except Exception as e:
            logger.error(f"Link validation failed: {e}")
            return json.dumps({"error": str(e)})


@CrewBase
class AutomatedEmailQaCrew:
    """
    Main crew class for automated email QA system.
    
    Implements hierarchical process with specialized agents for
    comprehensive email validation.
    
    Attributes:
        agents_config (str): Path to agents YAML configuration
        tasks_config (str): Path to tasks YAML configuration
        rules_engine (DynamicRulesEngine): Rules management instance
        workflow (RobustQAWorkflow): Workflow orchestrator
    """
    
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'
    
    def __init__(self):
        """Initialize the crew with custom tools and components."""
        # Initialize custom tools
        self.document_parser_tool = DocumentParserTool()
        self.email_parser_tool = EmailParserTool()
        self.link_validator_tool = LinkValidatorTool()
        self.file_read_tool = FileReadTool()
        
        # Initialize core components
        self.rules_engine = DynamicRulesEngine()
        
        # Initialize workflow with config
        self.workflow_config = {
            'VISION_ENABLED': True,
            'require_validation': False,
            'text_model': 'gpt-4o',
            'vision_model': 'gpt-4o',
            'temperature': 0.1,
            'MAX_RETRIES': 3
        }
        self.workflow = RobustQAWorkflow(self.workflow_config)
        
        logger.info("Initialized AutomatedEmailQaCrew with all components")
    
    @agent
    def document_extractor(self) -> Agent:
        """
        Create document extractor agent.
        
        Returns:
            Agent: Configured document extractor with parsing tools
        """
        return Agent(
            config=self.agents_config['document_extractor'],
            tools=[self.document_parser_tool, self.file_read_tool],
            memory=True,
            verbose=True,
            max_iter=3,
            max_retry_limit=2,
            allow_delegation=False
        )
    
    @agent
    def email_analyzer(self) -> Agent:
        """
        Create email analyzer agent.
        
        Returns:
            Agent: Configured email analyzer with parsing tools
        """
        return Agent(
            config=self.agents_config['email_analyzer'],
            tools=[self.email_parser_tool],
            memory=True,
            verbose=True,
            max_iter=3,
            allow_delegation=False
        )
    
    @agent
    def link_validator(self) -> Agent:
        """
        Create link validator agent.
        
        Returns:
            Agent: Configured link validator with validation tools
        """
        return Agent(
            config=self.agents_config['link_validator'],
            tools=[self.link_validator_tool],
            memory=True,
            verbose=True,
            allow_delegation=False
        )
    
    @agent
    def visual_inspector(self) -> Agent:
        """
        Create visual inspector agent with multimodal capabilities.
        
        Returns:
            Agent: Configured visual inspector for image analysis
        """
        return Agent(
            config=self.agents_config['visual_inspector'],
            multimodal=True,  # Enable vision capabilities
            memory=True,
            verbose=True,
            allow_delegation=False
        )
    
    @agent
    def compliance_checker(self) -> Agent:
        """
        Create compliance checker agent.
        
        Returns:
            Agent: Configured compliance checker
        """
        return Agent(
            config=self.agents_config['compliance_checker'],
            memory=True,
            verbose=True,
            allow_delegation=False
        )
    
    @agent
    def qa_manager(self) -> Agent:
        """
        Create QA manager agent for orchestration.
        
        Returns:
            Agent: Configured manager with delegation capabilities
        """
        return Agent(
            config=self.agents_config['qa_manager'],
            memory=True,
            verbose=True,
            allow_delegation=True  # Manager can delegate tasks
        )
    
    @task
    def extract_requirements_task(self) -> Task:
        """
        Create requirements extraction task.
        
        Returns:
            Task: Configured extraction task
        """
        return Task(
            config=self.tasks_config['extract_requirements'],
            agent=self.document_extractor()
        )
    
    @task
    def analyze_email_task(self) -> Task:
        """
        Create email analysis task.
        
        Returns:
            Task: Configured analysis task with context dependency
        """
        return Task(
            config=self.tasks_config['analyze_email_content'],
            agent=self.email_analyzer(),
            context=[self.extract_requirements_task()]
        )
    
    @task
    def validate_links_task(self) -> Task:
        """
        Create link validation task.
        
        Returns:
            Task: Configured validation task with context
        """
        return Task(
            config=self.tasks_config['validate_links'],
            agent=self.link_validator(),
            context=[self.extract_requirements_task(), self.analyze_email_task()]
        )
    
    @task
    def visual_inspection_task(self) -> Task:
        """
        Create visual inspection task.
        
        Returns:
            Task: Configured visual inspection task
        """
        return Task(
            config=self.tasks_config['visual_inspection'],
            agent=self.visual_inspector(),
            context=[self.analyze_email_task()]
        )
    
    @task
    def compliance_check_task(self) -> Task:
        """
        Create compliance check task.
        
        Returns:
            Task: Configured compliance task with context
        """
        return Task(
            config=self.tasks_config['compliance_check'],
            agent=self.compliance_checker(),
            context=[self.analyze_email_task(), self.validate_links_task()]
        )
    
    @task
    def generate_report_task(self) -> Task:
        """
        Create final QA report generation task.
        
        Returns:
            Task: Configured report task with all context
        """
        return Task(
            config=self.tasks_config['generate_qa_report'],
            agent=self.qa_manager(),
            context=[
                self.extract_requirements_task(),
                self.analyze_email_task(),
                self.validate_links_task(),
                self.visual_inspection_task(),
                self.compliance_check_task()
            ],
            output_json=Dict[str, Any]  # Expect JSON output
        )
    
    @crew
    def crew(self) -> Crew:
        """
        Create the QA crew with hierarchical process.
        
        Returns:
            Crew: Configured crew with all agents and tasks
        """
        return Crew(
            agents=self.agents,  # Auto-collected from @agent decorators
            tasks=self.tasks,    # Auto-collected from @task decorators
            process=Process.hierarchical,  # Use hierarchical process
            manager_llm="gpt-4o",  # Manager uses GPT-4o for coordination
            verbose=True,
            memory=True,  # Enable memory for context retention
            cache=True,   # Cache results for efficiency
            max_rpm=10,   # Rate limiting
            share_crew=False,
            embedder={
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small"
                }
            }
        )
    
    def prepare_inputs(self, 
                      document_content: str,
                      email_content: str,
                      client_name: str = "Client",
                      campaign_name: str = "Campaign",
                      email_type: str = "promotional",
                      document_type: str = "copy document",
                      industry: str = "general",
                      rules: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Prepare inputs for crew execution.
        
        Args:
            document_content (str): Raw document content
            email_content (str): Raw email content
            client_name (str): Client identifier
            campaign_name (str): Campaign identifier
            email_type (str): Type of email
            document_type (str): Type of document
            industry (str): Industry vertical
            rules (Optional[Dict]): Validation rules
            
        Returns:
            Dict[str, Any]: Formatted inputs for crew
        """
        # Load or create rules
        if rules is None:
            rules = self.rules_engine.template
        
        # Extract brand guidelines and compliance rules from main rules
        brand_guidelines = rules.get('brand', {})
        compliance_rules = {
            'can_spam': True,
            'gdpr': False,
            'accessibility': True
        }
        
        # Parse document and email for initial requirements
        parsed_doc = self.document_parser_tool.parser.parse_document(document_content)
        
        return {
            'client_name': client_name,
            'campaign_name': campaign_name,
            'email_type': email_type,
            'document_type': document_type,
            'industry': industry,
            'document_content': document_content,
            'email_content': email_content,
            'requirements': json.dumps(parsed_doc),
            'rules': json.dumps(rules),
            'brand_guidelines': json.dumps(brand_guidelines),
            'compliance_rules': json.dumps(compliance_rules),
            'all_findings': '',  # Will be populated by crew
            'current_year': '2024'
        }
    
    def run_qa(self,
               document_content: str,
               email_content: str,
               client_name: str = "Client",
               rules: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute complete QA validation.
        
        Main entry point for QA validation using the crew.
        
        Args:
            document_content (str): Document to extract requirements from
            email_content (str): Email to validate
            client_name (str): Client identifier
            rules (Optional[Dict]): Validation rules
            
        Returns:
            Dict[str, Any]: Complete QA results
        """
        try:
            # Prepare inputs
            inputs = self.prepare_inputs(
                document_content=document_content,
                email_content=email_content,
                client_name=client_name,
                rules=rules
            )
            
            logger.info(f"Starting QA validation for {client_name}")
            
            # Execute crew
            result = self.crew().kickoff(inputs=inputs)
            
            # Parse result
            if hasattr(result, 'json_dict'):
                return result.json_dict
            elif hasattr(result, 'raw'):
                try:
                    return json.loads(result.raw)
                except json.JSONDecodeError:
                    return {'raw_output': result.raw}
            else:
                return {'result': str(result)}
                
        except Exception as e:
            logger.error(f"QA validation failed: {e}")
            return {
                'error': str(e),
                'status': 'FAILED'
            }