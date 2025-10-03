"""
Email QA Crew Configuration
===========================
Multi-agent system for email marketing QA.
"""

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
import logging
import os
from datetime import datetime, timezone

from crewai_tools import FileReadTool, ScrapeWebsiteTool

# Import our custom tools
from email_qa.tools.email_parser import EmailParserTool
from email_qa.tools.link_validator import LinkValidatorTool
from email_qa.tools.pdf_parser import PDFParserTool
from email_qa.rules.engine import DynamicRulesEngine

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / '.env')

if not os.getenv('OPENAI_API_KEY'):
    logger.warning("OPENAI_API_KEY not found in environment variables!")


@CrewBase
class EmailQACrew:
    """Email QA Crew for automated email validation workflow."""
    
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'
    
    def __init__(
        self,
        client_name: str = None,
        campaign_name: str = None,
        segment: str = None,
        document_path: str = None,
        email_path: str = None,
        rules_path: str = None
    ):
        """
        Initialize Email QA Crew.
        
        Args:
            client_name: Client identifier
            campaign_name: Campaign name
            segment: Email segment
            document_path: Path to copy document
            email_path: Path to email file
            rules_path: Path to custom rules (optional)
        """
        super().__init__()
        
        # Store parameters for kickoff
        self.client_name = client_name
        self.campaign_name = campaign_name
        self.segment = segment
        self.document_path = document_path
        self.email_path = email_path
        
        # Initialize custom tools
        self.email_parser_tool = EmailParserTool()
        self.link_validator_tool = LinkValidatorTool()
        self.pdf_parser_tool = PDFParserTool()
        
        # Initialize rules engine - it will load from default directory
        # Agents call it with client_name when needed
        self.rules_engine = DynamicRulesEngine()
        
        # Initialize built-in CrewAI tools
        self.file_read_tool = FileReadTool()
        self.scrape_website_tool = ScrapeWebsiteTool()
        
        logger.info("EmailQACrew initialized with custom tools and rules engine")
    
    def kickoff(self, inputs: Dict[str, Any] = None) -> str:
        """Execute the crew with inputs."""
        # Use provided inputs or fall back to init parameters
        if inputs is None:
            inputs = {
                'client_name': self.client_name or 'unknown',
                'campaign_name': self.campaign_name or 'unknown',
                'segment': self.segment or 'all',
                'document_content': self.document_path or '',
                'email_content': self.email_path or '',
                'screenshot_paths': []
            }
        
        return self.crew().kickoff(inputs=inputs)
    
    @agent
    def copy_document_extractor(self) -> Agent:
        return Agent(
            config=self.agents_config['copy_document_extractor'],
            tools=[self.file_read_tool, self.pdf_parser_tool],
            memory=True,
            verbose=True,
            allow_delegation=False
        )
    
    @agent
    def email_content_analyzer(self) -> Agent:
        # Create rules engine wrapper
        from crewai.tools import BaseTool
        from pydantic import BaseModel, Field
        
        class RulesEngineInput(BaseModel):
            client_name: str = Field(..., description="Client name")
            segment: str = Field(None, description="Segment")
            
        class RulesEngineTool(BaseTool):
            name: str = "Dynamic Rules Engine"
            description: str = "Load client-specific email QA rules"
            args_schema: type[BaseModel] = RulesEngineInput
            
            def _run(self, client_name: str, segment: str = None) -> str:
                engine = DynamicRulesEngine()
                try:
                    rules = engine.load_rules(client_name)
                    result = {"rules": rules}
                    return json.dumps(result, indent=2)
                except Exception as e:
                    return json.dumps({"error": str(e)})
        
        return Agent(
            config=self.agents_config['email_content_analyzer'],
            tools=[self.email_parser_tool, RulesEngineTool()],
            memory=True,
            verbose=True,
            allow_delegation=False
        )
    
    @agent
    def link_and_cta_validator(self) -> Agent:
        return Agent(
            config=self.agents_config['link_and_cta_validator'],
            tools=[self.link_validator_tool, self.scrape_website_tool],
            memory=True,
            verbose=True,
            allow_delegation=False
        )
    
    @agent
    def visual_qa_inspector(self) -> Agent:
        return Agent(
            config=self.agents_config['visual_qa_inspector'],
            tools=[self.email_parser_tool],
            memory=True,
            verbose=True,
            allow_delegation=False,
            multimodal=False
        )
    
    @agent
    def compliance_and_metadata_checker(self) -> Agent:
        return Agent(
            config=self.agents_config['compliance_and_metadata_checker'],
            tools=[self.email_parser_tool],
            memory=True,
            verbose=True,
            allow_delegation=False
        )
    
    @agent
    def report_generator(self) -> Agent:
        """Generate comprehensive final report with A/B test analysis."""
        return Agent(
            config=self.agents_config['report_generator'],
            tools=[],  # No tools needed, just synthesizes previous outputs
            memory=True,
            verbose=True,
            allow_delegation=False
        )
    
    @task
    def extract_copy_requirements(self) -> Task:
        return Task(
            config=self.tasks_config['extract_copy_requirements'],
            agent=self.copy_document_extractor()
        )
    
    @task
    def analyze_email_content(self) -> Task:
        return Task(
            config=self.tasks_config['analyze_email_content'],
            agent=self.email_content_analyzer(),
            context=[self.extract_copy_requirements()]
        )
    
    @task
    def validate_links_and_ctas(self) -> Task:
        return Task(
            config=self.tasks_config['validate_links_and_ctas'],
            agent=self.link_and_cta_validator(),
            context=[
                self.extract_copy_requirements(),
                self.analyze_email_content()
            ]
        )
    
    @task
    def visual_qa_inspection(self) -> Task:
        return Task(
            config=self.tasks_config['visual_qa_inspection'],
            agent=self.visual_qa_inspector(),
            context=[
                self.extract_copy_requirements(),
                self.analyze_email_content(),
                self.validate_links_and_ctas()
            ]
        )
    
    @task
    def final_compliance_check(self) -> Task:
        return Task(
            config=self.tasks_config['final_compliance_check'],
            agent=self.compliance_and_metadata_checker(),
            context=[
                self.extract_copy_requirements(),
                self.analyze_email_content(),
                self.validate_links_and_ctas(),
                self.visual_qa_inspection()
            ]
        )
    
    @task
    def generate_comprehensive_report(self) -> Task:
        """Task 6: Generate final comprehensive report."""
        return Task(
            config=self.tasks_config['generate_comprehensive_report'],
            agent=self.report_generator(),
            context=[
                self.extract_copy_requirements(),
                self.analyze_email_content(),
                self.validate_links_and_ctas(),
                self.visual_qa_inspection(),
                self.final_compliance_check()
            ]
        )
    
    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            memory=True,
            verbose=True,
            cache=True
        )


# Standalone execution functions (keep your existing ones)
def run_email_qa_from_files(
    client_name: str,
    copy_doc_path: str,
    email_path: str,
    segment: Optional[str] = None
) -> Dict[str, Any]:
    """Run QA from file paths."""
    campaign_name = Path(email_path).stem
    
    log_dir = Path("qa_logs")
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"{client_name}_{campaign_name.replace(' ', '_')}_{timestamp}.log"
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    
    logger.info(f"Starting Email QA for {client_name} - {campaign_name}")
    logger.info(f"Crew execution log: {log_file}")
    
    crew = EmailQACrew(
        client_name=client_name,
        campaign_name=campaign_name,
        segment=segment,
        document_path=copy_doc_path,
        email_path=email_path
    )
    
    try:
        result = crew.kickoff()
        logger.info("Email QA completed successfully")
        logger.info(f"Full execution log saved to: {log_file}")
        
        return {
            'client': client_name,
            'campaign': campaign_name,
            'segment': segment,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'crew_output': result,
            'status': 'completed',
            'log_file': str(log_file)
        }
    except Exception as e:
        logger.error(f"Email QA failed: {str(e)}", exc_info=True)
        return {
            'client': client_name,
            'campaign': campaign_name,
            'segment': segment,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'failed',
            'error': str(e),
            'log_file': str(log_file)
        }
    finally:
        root_logger.removeHandler(file_handler)
        file_handler.close()


def save_qa_report(qa_results: Dict[str, Any], output_dir: str = "qa_reports") -> str:
    """Save QA results to JSON."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    client = qa_results.get('client', 'unknown')
    campaign = qa_results.get('campaign', 'unknown').replace(' ', '_')
    segment = qa_results.get('segment', 'all')
    
    filename = f"{client}_{campaign}_{segment}_{timestamp}.json"
    filepath = output_path / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(qa_results, f, indent=2, default=str)
    
    logger.info(f"QA report saved to: {filepath}")
    return str(filepath)


if __name__ == "__main__":
    print("="*80)
    print("EMAIL QA CREW - EXAMPLE EXECUTION")
    print("="*80)
    
    results = run_email_qa_from_files(
        client_name="yanmar",
        copy_doc_path="uploads/August 2025 Field Notes.pdf",
        email_path="uploads/[Test]_Explore What Yanmar Can Do (1).eml",
        segment="prospects"
    )
    
    report_path = save_qa_report(results)
    
    print(f"\nClient: {results['client']}")
    print(f"Status: {results['status']}")
    print(f"Report: {report_path}")
    print("="*80)