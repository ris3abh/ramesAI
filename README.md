# Automated Email QA System

An intelligent email quality assurance system powered by CrewAI that validates marketing emails against requirements using specialized AI agents.

## Features

- **Automated Requirement Extraction**: Parse copy documents to extract all email requirements
- **Comprehensive Validation**: Check subject lines, CTAs, links, content, and compliance
- **Visual Inspection**: Multimodal analysis of email rendering
- **Dynamic Rules Engine**: Client-specific validation rules without code changes
- **Hierarchical AI Orchestration**: Specialized agents working together
- **Web Interface**: User-friendly Streamlit UI
- **CLI Support**: Command-line interface for automation

## Architecture

The system uses CrewAI's hierarchical process with specialized agents:

- **Document Extractor**: Extracts requirements from copy documents
- **Email Analyzer**: Validates email content against requirements
- **Link Validator**: Checks all links and CTAs
- **Visual Inspector**: Analyzes visual rendering (multimodal)
- **Compliance Checker**: Verifies CAN-SPAM and brand compliance
- **QA Manager**: Orchestrates and compiles reports

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/automated_email_qa.git
cd automated_email_qa
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
uv pip install -r requirements.txt
```

4. Set environment variables:
```bash
export OPENAI_API_KEY='your_openai_api_key'
```

## Usage:

### Streamlit Web Interface
```bash
python src/automated_email_qa/main.py ui
```

### Command-Line Interface
```bash
python src/automated_email_qa/main.py cli \
  --document copy.txt \
  --email email.html \
  --client "Client Name" \
  --output results.json
```

### Python API
```python
from automated_email_qa.crew import AutomatedEmailQaCrew

crew = AutomatedEmailQaCrew()
results = crew.run_qa(
    document_content="...",
    email_content="...",
    client_name="Client"
)

