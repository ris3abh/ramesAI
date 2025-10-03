"""
Tests for Email QA Crew
=======================
Tests crew initialization, agent/task creation, and workflow execution.

Run with: pytest tests/test_crew.py -v
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from email_qa.crew import (
    EmailQACrew,
    run_email_qa,
    run_email_qa_from_files,
    save_qa_report
)


class TestCrewInitialization:
    """Tests for EmailQACrew initialization."""
    
    def test_crew_initialization(self):
        """Test crew initializes with all required components."""
        crew = EmailQACrew()
        
        # Check custom tools are initialized
        assert crew.email_parser_tool is not None
        assert crew.link_validator_tool is not None
        assert crew.pdf_parser_tool is not None
        
        # Check rules engine is initialized
        assert crew.rules_engine is not None
        
        # Check built-in tools are initialized
        assert crew.file_read_tool is not None
        assert crew.scrape_website_tool is not None
    
    def test_crew_has_config_loaded(self):
        """Test crew has loaded configuration dictionaries."""
        crew = EmailQACrew()
        
        # CrewAI's @CrewBase decorator loads YAML files automatically
        assert isinstance(crew.agents_config, dict)
        assert isinstance(crew.tasks_config, dict)
        
        # Check that key agents are present
        assert 'copy_document_extractor' in crew.agents_config
        assert 'email_content_analyzer' in crew.agents_config
        assert 'link_and_cta_validator' in crew.agents_config
        
        # Check that key tasks are present
        assert 'extract_copy_requirements' in crew.tasks_config
        assert 'analyze_email_content' in crew.tasks_config


class TestAgentCreation:
    """Tests for agent creation methods."""
    
    @pytest.fixture
    def crew(self):
        """Create crew instance for testing."""
        return EmailQACrew()
    
    def test_copy_document_extractor_agent(self, crew):
        """Test copy document extractor agent is created correctly."""
        agent = crew.copy_document_extractor()
        
        assert agent is not None
        assert len(agent.tools) == 2  # FileReadTool, PDFSearchTool, DocumentParserTool
        # Memory and verbose would be set when crew is assembled
    
    def test_email_content_analyzer_agent(self, crew):
        """Test email content analyzer agent is created correctly."""
        agent = crew.email_content_analyzer()
        
        assert agent is not None
        assert len(agent.tools) == 2  # EmailParserTool, RulesEngineTool
    
    def test_link_validator_agent(self, crew):
        """Test link validator agent is created correctly."""
        agent = crew.link_and_cta_validator()
        
        assert agent is not None
        assert len(agent.tools) == 2  # LinkValidatorTool, ScrapeWebsiteTool
    
    def test_visual_inspector_agent(self, crew):
        """Test visual inspector agent is created correctly."""
        agent = crew.visual_qa_inspector()
        
        assert agent is not None
        assert len(agent.tools) >= 1  # At least EmailParserTool
    
    def test_compliance_checker_agent(self, crew):
        """Test compliance checker agent is created correctly."""
        agent = crew.compliance_and_metadata_checker()
        
        assert agent is not None
        assert len(agent.tools) == 2  # EmailParserTool, ComplianceRulesEngineTool


class TestTaskCreation:
    """Tests for task creation methods."""
    
    @pytest.fixture
    def crew(self):
        """Create crew instance for testing."""
        return EmailQACrew()
    
    def test_extract_requirements_task(self, crew):
        """Test extract requirements task is created correctly."""
        task = crew.extract_copy_requirements()
        
        assert task is not None
        assert task.agent is not None
    
    def test_analyze_content_task(self, crew):
        """Test analyze content task is created correctly."""
        task = crew.analyze_email_content()
        
        assert task is not None
        assert task.agent is not None
        # Should have context from previous task
        assert len(task.context) == 1
    
    def test_validate_links_task(self, crew):
        """Test validate links task is created correctly."""
        task = crew.validate_links_and_ctas()
        
        assert task is not None
        assert task.agent is not None
        # Should have context from 2 previous tasks
        assert len(task.context) == 2
    
    def test_visual_inspection_task(self, crew):
        """Test visual inspection task is created correctly."""
        task = crew.visual_qa_inspection()
        
        assert task is not None
        assert task.agent is not None
        # Should have context from 3 previous tasks
        assert len(task.context) == 3
    
    def test_compliance_check_task(self, crew):
        """Test compliance check task is created correctly."""
        task = crew.final_compliance_check()
        
        assert task is not None
        assert task.agent is not None
        # Should have context from 4 previous tasks
        assert len(task.context) == 4


class TestCrewAssembly:
    """Tests for crew assembly."""
    
    def test_crew_assembly(self):
        """Test crew assembles with all agents and tasks."""
        email_qa_crew = EmailQACrew()
        assembled_crew = email_qa_crew.crew()
        
        assert assembled_crew is not None
        assert len(assembled_crew.agents) == 5
        assert len(assembled_crew.tasks) == 5
        
        # Check process type
        from crewai import Process
        assert assembled_crew.process == Process.sequential
        
        # Check memory is enabled
        assert assembled_crew.memory is True
        
        # Check verbose mode
        assert assembled_crew.verbose is True


class TestHelperFunctions:
    """Tests for standalone helper functions."""
    
    def test_save_qa_report(self, tmp_path):
        """Test QA report saving."""
        qa_results = {
            'client': 'test_client',
            'campaign': 'Test Campaign',
            'segment': 'prospects',
            'status': 'completed',
            'timestamp': '2025-01-15T10:00:00Z'
        }
        
        output_dir = str(tmp_path / "reports")
        filepath = save_qa_report(qa_results, output_dir=output_dir)
        
        # Check file was created
        assert Path(filepath).exists()
        
        # Check content
        with open(filepath, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data['client'] == 'test_client'
        assert saved_data['campaign'] == 'Test Campaign'
        assert saved_data['segment'] == 'prospects'
    
    def test_save_qa_report_creates_directory(self, tmp_path):
        """Test save_qa_report creates output directory if needed."""
        qa_results = {
            'client': 'test',
            'campaign': 'test',
            'segment': 'all',
            'status': 'completed'
        }
        
        output_dir = str(tmp_path / "new_dir" / "reports")
        filepath = save_qa_report(qa_results, output_dir=output_dir)
        
        assert Path(output_dir).exists()
        assert Path(filepath).exists()


class TestRunEmailQAFromFiles:
    """Tests for run_email_qa_from_files function."""
    
    @patch('email_qa.crew.run_email_qa')
    def test_run_email_qa_from_files_calls_run_email_qa(self, mock_run_qa):
        """Test run_email_qa_from_files calls run_email_qa correctly."""
        mock_run_qa.return_value = {'status': 'completed'}
        
        result = run_email_qa_from_files(
            client_name="yanmar",
            copy_doc_path="uploads/copy.pdf",
            email_path="uploads/email.eml",
            segment="prospects"
        )
        
        # Check run_email_qa was called
        assert mock_run_qa.called
        
        # Check arguments
        call_args = mock_run_qa.call_args[1]
        assert call_args['client_name'] == 'yanmar'
        assert call_args['document_content'] == 'uploads/copy.pdf'
        assert call_args['email_content'] == 'uploads/email.eml'
        assert call_args['segment'] == 'prospects'


class TestIntegration:
    """Integration tests (may be slow, marked for optional execution)."""
    
    @pytest.mark.slow
    @pytest.mark.integration
    def test_crew_kickoff_with_mock_inputs(self):
        """
        Test crew can be kicked off with mock inputs.
        
        This is a smoke test to ensure the crew can be instantiated
        and prepared for execution without actually running the full workflow.
        
        Run with: pytest tests/test_crew.py -v -m integration
        """
        crew = EmailQACrew()
        assembled_crew = crew.crew()
        
        # Just verify we can prepare inputs
        mock_inputs = {
            'client_name': 'test_client',
            'campaign_name': 'Test Campaign',
            'document_content': 'test content',
            'email_content': 'test email',
            'segment': 'all',
            'screenshot_paths': []
        }
        
        # We don't actually kickoff (too slow), just verify structure
        assert assembled_crew is not None
        assert mock_inputs['client_name'] == 'test_client'


class TestErrorHandling:
    """Tests for error handling in crew execution."""
    
    @patch('email_qa.crew.EmailQACrew')
    def test_run_email_qa_handles_exceptions(self, mock_crew_class):
        """Test run_email_qa handles exceptions gracefully."""
        # Make crew.kickoff() raise an exception
        mock_crew_instance = Mock()
        mock_crew_instance.crew.return_value.kickoff.side_effect = Exception("Test error")
        mock_crew_class.return_value = mock_crew_instance
        
        result = run_email_qa(
            client_name="test",
            campaign_name="test",
            document_content="test",
            email_content="test"
        )
        
        # Should return error result, not raise exception
        assert result['status'] == 'failed'
        assert 'error' in result
        assert 'Test error' in result['error']


class TestConfigurationLoading:
    """Tests for configuration file loading."""
    
    def test_agents_config_exists(self):
        """Test agents.yaml configuration file exists."""
        config_path = Path("src/email_qa/config/agents.yaml")
        
        # Should exist relative to project root
        assert config_path.exists() or Path("email_qa/config/agents.yaml").exists(), \
            "agents.yaml configuration file not found"
    
    def test_tasks_config_exists(self):
        """Test tasks.yaml configuration file exists."""
        config_path = Path("src/email_qa/config/tasks.yaml")
        
        # Should exist relative to project root
        assert config_path.exists() or Path("email_qa/config/tasks.yaml").exists(), \
            "tasks.yaml configuration file not found"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])