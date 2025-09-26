"""
Main Entry Point for Automated Email QA System
===============================================
Purpose: CLI interface and main execution orchestrator
Author: Rishabh Sharma
Date: 2024

This module provides the main entry points for running the email QA system
through CLI commands or programmatically.

Metadata:
---------
Functions:
    run(): Default execution with example data
    train(): Train the crew with iterations
    replay(): Replay from specific task
    test(): Test crew with sample data
    run_ui(): Launch Streamlit interface
    run_cli(): CLI-based QA execution
    
CLI Arguments:
    --mode (str): Execution mode ['ui', 'cli', 'run', 'train', 'replay', 'test']
    --document (str): Path to document file
    --email (str): Path to email file
    --client (str): Client name
    --rules (str): Path to rules JSON file
    --output (str): Output file path for results
    --iterations (int): Training iterations (for train mode)
    --task-id (str): Task ID for replay mode
    
Environment Variables:
    OPENAI_API_KEY (str): OpenAI API key for LLM access
    LOG_LEVEL (str): Logging level (DEBUG, INFO, WARNING, ERROR)
    
Integration with previous files:
    - Uses AutomatedEmailQaCrew from crew.py for all QA operations
    - Can launch Streamlit UI from streamlit_app.py
    - Uses DynamicRulesEngine for rules management
    - All parsers and workflow components accessed through crew
"""

#!/usr/bin/env python
import sys
import os
import json
import argparse
import warnings
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from datetime import datetime

# Suppress syntax warnings
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# Configure logging
log_level = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import project components
from automated_email_qa.crew import AutomatedEmailQaCrew
from automated_email_qa.core.dynamic_rules import DynamicRulesEngine
from automated_email_qa.tools.universal_parser import UniversalDocumentParser
from automated_email_qa.tools.email_parser import EmailParser


def run():
    """
    Default run function for CrewAI.
    
    Executes the crew with example inputs for demonstration.
    This is the standard entry point when running 'crewai run'.
    """
    logger.info("Starting default QA run with example data")
    
    # Example inputs for demonstration
    inputs = {
        'client_name': 'Example Client',
        'campaign_name': 'Demo Campaign',
        'email_type': 'promotional',
        'document_type': 'copy document',
        'industry': 'e-commerce',
        'document_content': '''
        Subject Line A: Get 50% Off Your First Order - Limited Time!
        Subject Line B: Welcome! Your Exclusive 50% Discount Awaits
        
        Preview Text: Shop our best sellers with an exclusive first-time buyer discount
        
        From Name: Example Store
        From Email: hello@example.com
        
        Main CTA: SHOP NOW
        Link: https://example.com/shop?utm_source=email&utm_medium=promotional&utm_campaign=welcome50
        
        Secondary CTA: LEARN MORE
        Link: https://example.com/about
        
        Required Modules:
        - Header with logo
        - Hero section with offer
        - Product showcase (3 products)
        - Footer with unsubscribe
        ''',
        'email_content': '''
        <html>
        <head><title>Welcome Email</title></head>
        <body>
            <div style="display:none;">Shop our best sellers with an exclusive first-time buyer discount</div>
            <h1>Welcome to Example Store!</h1>
            <p>Get 50% off your first order</p>
            <a href="https://example.com/shop?utm_source=email&utm_medium=promotional&utm_campaign=welcome50">SHOP NOW</a>
            <a href="https://example.com/about">LEARN MORE</a>
            <p>123 Main St, City, State 12345</p>
            <a href="https://example.com/unsubscribe">Unsubscribe</a>
        </body>
        </html>
        ''',
        'rules': json.dumps({}),  # Will use default rules
        'brand_guidelines': json.dumps({}),
        'compliance_rules': json.dumps({'can_spam': True}),
        'all_findings': '',
        'current_year': str(datetime.now().year)
    }
    
    try:
        # Initialize and run crew
        crew = AutomatedEmailQaCrew()
        result = crew.crew().kickoff(inputs=inputs)
        
        logger.info("QA run completed successfully")
        print("\n" + "="*50)
        print("QA RESULTS")
        print("="*50)
        
        if hasattr(result, 'raw'):
            print(result.raw)
        else:
            print(json.dumps(result, indent=2))
            
    except Exception as e:
        logger.error(f"QA run failed: {e}")
        raise


def train():
    """
    Train the crew for a given number of iterations.
    
    Uses the CrewAI training functionality to improve agent performance
    through repeated execution with feedback.
    """
    n_iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    filename = sys.argv[2] if len(sys.argv) > 2 else None
    
    logger.info(f"Starting crew training with {n_iterations} iterations")
    
    inputs = {
        'client_name': 'Training Client',
        'campaign_name': 'Training Campaign',
        'email_type': 'promotional',
        'document_type': 'copy document',
        'industry': 'general',
        'document_content': 'Training document content',
        'email_content': '<html><body>Training email</body></html>',
        'rules': json.dumps({}),
        'brand_guidelines': json.dumps({}),
        'compliance_rules': json.dumps({}),
        'all_findings': '',
        'current_year': str(datetime.now().year)
    }
    
    try:
        crew = AutomatedEmailQaCrew()
        crew.crew().train(
            n_iterations=n_iterations,
            filename=filename,
            inputs=inputs
        )
        logger.info(f"Training completed: {n_iterations} iterations")
        
    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise Exception(f"An error occurred while training the crew: {e}")


def replay():
    """
    Replay the crew execution from a specific task.
    
    Useful for debugging and re-running from a checkpoint.
    """
    task_id = sys.argv[1] if len(sys.argv) > 1 else None
    
    if not task_id:
        logger.error("Task ID required for replay")
        print("Usage: automated_email_qa replay <task_id>")
        sys.exit(1)
    
    logger.info(f"Replaying crew from task: {task_id}")
    
    try:
        crew = AutomatedEmailQaCrew()
        crew.crew().replay(task_id=task_id)
        logger.info("Replay completed successfully")
        
    except Exception as e:
        logger.error(f"Replay failed: {e}")
        raise Exception(f"An error occurred while replaying the crew: {e}")


def test():
    """
    Test the crew with sample data.
    
    Runs multiple test iterations to validate crew performance.
    """
    n_iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    openai_model_name = sys.argv[2] if len(sys.argv) > 2 else "gpt-4o"
    
    logger.info(f"Testing crew with {n_iterations} iterations using {openai_model_name}")
    
    inputs = {
        'client_name': 'Test Client',
        'campaign_name': 'Test Campaign',
        'email_type': 'test',
        'document_type': 'test document',
        'industry': 'test',
        'document_content': 'Test requirements document',
        'email_content': '<html><body>Test email content</body></html>',
        'rules': json.dumps({}),
        'brand_guidelines': json.dumps({}),
        'compliance_rules': json.dumps({}),
        'all_findings': '',
        'current_year': str(datetime.now().year)
    }
    
    try:
        crew = AutomatedEmailQaCrew()
        crew.crew().test(
            n_iterations=n_iterations,
            openai_model_name=openai_model_name,
            inputs=inputs
        )
        logger.info(f"Testing completed: {n_iterations} iterations")
        
    except Exception as e:
        logger.error(f"Testing failed: {e}")
        raise Exception(f"An error occurred while testing the crew: {e}")


def run_ui():
    """
    Launch the Streamlit web UI.
    
    Starts the Streamlit server for the web interface.
    """
    logger.info("Launching Streamlit UI")
    
    try:
        import subprocess
        import sys
        
        # Get the path to streamlit_app.py
        app_path = Path(__file__).parent / "streamlit_app.py"
        
        # Launch Streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            str(app_path),
            "--server.port", "8501",
            "--server.address", "localhost"
        ])
        
    except Exception as e:
        logger.error(f"Failed to launch UI: {e}")
        print(f"Error: Could not launch Streamlit UI: {e}")
        print("Make sure Streamlit is installed: pip install streamlit")
        sys.exit(1)


def run_cli():
    """
    Run QA check from command line with file inputs.
    
    Provides a CLI interface for QA validation without the web UI.
    """
    parser = argparse.ArgumentParser(
        description='Automated Email QA System - CLI Interface'
    )
    
    parser.add_argument(
        '--document', '-d',
        type=str,
        required=True,
        help='Path to copy document file'
    )
    
    parser.add_argument(
        '--email', '-e',
        type=str,
        required=True,
        help='Path to email HTML/EML file'
    )
    
    parser.add_argument(
        '--client', '-c',
        type=str,
        default='CLI Client',
        help='Client name (default: CLI Client)'
    )
    
    parser.add_argument(
        '--rules', '-r',
        type=str,
        help='Path to rules JSON file (optional)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output file path for results (optional)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info(f"Running CLI QA check for client: {args.client}")
    
    try:
        # Read document content
        doc_path = Path(args.document)
        if not doc_path.exists():
            raise FileNotFoundError(f"Document not found: {args.document}")
        
        with open(doc_path, 'r', encoding='utf-8') as f:
            doc_content = f.read()
        
        # Read email content
        email_path = Path(args.email)
        if not email_path.exists():
            raise FileNotFoundError(f"Email not found: {args.email}")
        
        with open(email_path, 'r', encoding='utf-8') as f:
            email_content = f.read()
        
        # Load rules if provided
        rules = None
        if args.rules:
            rules_path = Path(args.rules)
            if rules_path.exists():
                with open(rules_path, 'r') as f:
                    rules = json.load(f)
                logger.info(f"Loaded rules from: {args.rules}")
        
        # Initialize crew and run QA
        crew = AutomatedEmailQaCrew()
        
        print("\n" + "="*50)
        print(f"Running QA Check for {args.client}")
        print("="*50)
        print(f"Document: {doc_path.name}")
        print(f"Email: {email_path.name}")
        if rules:
            print(f"Rules: {args.rules}")
        print("="*50 + "\n")
        
        # Run QA
        results = crew.run_qa(
            document_content=doc_content,
            email_content=email_content,
            client_name=args.client,
            rules=rules
        )
        
        # Display results
        print("\n" + "="*50)
        print("QA RESULTS")
        print("="*50)
        
        # Summary
        verdict = results.get('pass_fail_verdict', False)
        print(f"Status: {'✅ PASSED' if verdict else '❌ FAILED'}")
        print(f"QA Score: {results.get('qa_score', 0):.1f}/100")
        
        # Critical issues
        critical_issues = results.get('critical_issues', [])
        if critical_issues:
            print(f"\nCritical Issues ({len(critical_issues)}):")
            for i, issue in enumerate(critical_issues, 1):
                print(f"  {i}. {issue.get('description', 'Issue found')}")
                print(f"     Recommendation: {issue.get('recommendation', 'Fix required')}")
        
        # Save results if output path provided
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2)
            
            print(f"\nResults saved to: {args.output}")
        
        # Exit code based on pass/fail
        sys.exit(0 if verdict else 1)
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        print(f"Error: {e}")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"CLI execution failed: {e}")
        print(f"Error: {e}")
        sys.exit(1)


def main():
    """
    Main entry point with mode selection.
    
    Determines which mode to run based on command line arguments.
    """
    # Check for environment variables
    if not os.getenv('OPENAI_API_KEY'):
        logger.warning("OPENAI_API_KEY not set in environment")
        print("Warning: OPENAI_API_KEY environment variable not set")
        print("Set it using: export OPENAI_API_KEY='your-key-here'")
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        
        if mode == 'ui':
            run_ui()
        elif mode == 'cli':
            # Remove 'cli' from argv for argparse
            sys.argv.pop(1)
            run_cli()
        elif mode == 'train':
            train()
        elif mode == 'replay':
            replay()
        elif mode == 'test':
            test()
        elif mode == 'run':
            run()
        elif mode in ['-h', '--help', 'help']:
            print_help()
        else:
            print(f"Unknown mode: {mode}")
            print_help()
            sys.exit(1)
    else:
        # Default to run mode
        run()


def print_help():
    """Print help information."""
    help_text = """
Automated Email QA System
=========================

Usage: automated_email_qa [mode] [options]

Modes:
    run         Run with example data (default)
    ui          Launch Streamlit web interface
    cli         Run from command line with files
    train       Train the crew with iterations
    replay      Replay from specific task
    test        Test crew performance
    help        Show this help message

CLI Mode Options:
    --document, -d  Path to copy document file (required)
    --email, -e     Path to email HTML/EML file (required)
    --client, -c    Client name (default: CLI Client)
    --rules, -r     Path to rules JSON file (optional)
    --output, -o    Output file path for results (optional)
    --verbose, -v   Enable verbose output

Examples:
    # Run with example data
    automated_email_qa run
    
    # Launch web UI
    automated_email_qa ui
    
    # CLI with files
    automated_email_qa cli -d copy.txt -e email.html -c "Client Name"
    
    # CLI with rules and output
    automated_email_qa cli -d copy.txt -e email.html -r rules.json -o results.json
    
    # Train crew
    automated_email_qa train 5
    
    # Replay task
    automated_email_qa replay task_123

Environment Variables:
    OPENAI_API_KEY  OpenAI API key (required)
    LOG_LEVEL       Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    print(help_text)


if __name__ == "__main__":
    main()