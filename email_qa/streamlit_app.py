"""
Email QA Streamlit Application
==============================
Web interface for automated email marketing QA.
"""

import streamlit as st
from pathlib import Path
import json
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent / "src"))

from email_qa.crew import EmailQACrew

st.set_page_config(
    page_title="Email QA System",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stProgress > div > div > div > div {
        background-color: #00CC66;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #D4EDDA;
        border-left: 5px solid #28A745;
        margin: 1rem 0;
    }
    .error-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #F8D7DA;
        border-left: 5px solid #DC3545;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

def main():
    st.title("Email Marketing QA System")
    st.markdown("Automated QA for email campaigns with AI-powered validation")
    
    # Sidebar
    with st.sidebar:
        st.header("Configuration")
        
        client_name = st.text_input(
            "Client Name",
            value="",
            placeholder="e.g., acme-corp",
            help="Unique identifier for this client"
        )
        
        segment = st.selectbox(
            "Email Segment",
            ["prospects", "owners", "self", "loved_one", "all"],
            help="Target audience segment"
        )
        
        st.markdown("---")
        
        # Rules management
        st.subheader("Client Rules")
        
        rules_option = st.radio(
            "Rules Source",
            ["Use Existing Rules", "Upload Custom Rules", "Create New Rules"]
        )
        
        custom_rules_path = None
        
        if rules_option == "Use Existing Rules":
            existing_rules = list(Path("src/email_qa/rules/clients").glob("*.json"))
            if existing_rules:
                selected_rule = st.selectbox(
                    "Select Rules",
                    [r.stem for r in existing_rules]
                )
                custom_rules_path = Path("src/email_qa/rules/clients") / f"{selected_rule}.json"
            else:
                st.warning("No existing rules found. Create new rules below.")
        
        elif rules_option == "Upload Custom Rules":
            uploaded_rules = st.file_uploader(
                "Upload rules JSON",
                type=['json'],
                help="Upload client-specific validation rules"
            )
            if uploaded_rules:
                custom_rules_path = save_uploaded_rules(uploaded_rules, client_name)
                st.success("Rules uploaded successfully")
        
        elif rules_option == "Create New Rules":
            with st.expander("Rules Editor", expanded=True):
                rules_json = create_rules_editor()
                if st.button("Save Rules"):
                    custom_rules_path = save_custom_rules(rules_json, client_name)
                    st.success(f"Rules saved for {client_name}")
    
    # Main content
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Copy Document")
        copy_doc = st.file_uploader(
            "Upload copy document (PDF)",
            type=['pdf'],
            help="Original marketing copy with requirements"
        )
        
        if copy_doc:
            st.success(f"Uploaded: {copy_doc.name}")
    
    with col2:
        st.subheader("Email File")
        email_file = st.file_uploader(
            "Upload email (.eml or .html)",
            type=['eml', 'html', 'htm'],
            help="Final email to validate"
        )
        
        if email_file:
            st.success(f"Uploaded: {email_file.name}")
    
    # Run QA button
    st.markdown("---")
    
    can_run = all([copy_doc, email_file, client_name])
    
    if st.button("Run QA Analysis", type="primary", disabled=not can_run):
        run_qa_analysis(copy_doc, email_file, client_name, segment, custom_rules_path)
    
    if not can_run:
        missing = []
        if not copy_doc:
            missing.append("copy document")
        if not email_file:
            missing.append("email file")
        if not client_name:
            missing.append("client name")
        
        st.info(f"Please provide: {', '.join(missing)}")

def create_rules_editor():
    """Interactive rules editor."""
    
    st.markdown("### Basic Rules")
    
    col1, col2 = st.columns(2)
    
    with col1:
        phone = st.text_input("Phone Number", placeholder="555-123-4567")
        from_email = st.text_input("From Email", placeholder="info@client.com")
    
    with col2:
        from_name = st.text_input("From Name", placeholder="Company Name")
        required_address = st.text_input("Physical Address", placeholder="123 Main St, City, State ZIP")
    
    st.markdown("### Content Rules")
    
    cta_uppercase = st.checkbox("CTAs must be uppercase", value=True)
    
    st.markdown("### Segmentation Keywords")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Prospects Keywords**")
        prospects_keywords = st.text_area(
            "One per line",
            value="explore\ndiscover\nlearn",
            height=100,
            label_visibility="collapsed"
        )
    
    with col2:
        st.markdown("**Owners Keywords**")
        owners_keywords = st.text_area(
            "One per line",
            value="projects\nmaintenance\ntips",
            height=100,
            label_visibility="collapsed"
        )
    
    # Build rules JSON
    rules = {
        "client_name": "Custom Client",
        "description": "Custom validation rules",
        "brand": {
            "phone": phone,
            "from_email": from_email,
            "from_name": from_name,
            "required_address": required_address
        },
        "content_rules": {
            "cta_uppercase": cta_uppercase
        },
        "segmentation": {
            "prospects": {
                "required_subject_keywords": [k.strip() for k in prospects_keywords.split('\n') if k.strip()]
            },
            "owners": {
                "required_subject_keywords": [k.strip() for k in owners_keywords.split('\n') if k.strip()]
            }
        }
    }
    
    st.markdown("### Rules Preview")
    st.json(rules)
    
    return rules

def save_custom_rules(rules: dict, client_name: str) -> Path:
    """Save custom rules to file."""
    
    rules_dir = Path("src/email_qa/rules/clients")
    rules_dir.mkdir(parents=True, exist_ok=True)
    
    rules_path = rules_dir / f"{client_name}.json"
    
    with open(rules_path, 'w') as f:
        json.dump(rules, f, indent=2)
    
    return rules_path

def save_uploaded_rules(uploaded_file, client_name: str) -> Path:
    """Save uploaded rules file."""
    
    rules_dir = Path("src/email_qa/rules/clients")
    rules_dir.mkdir(parents=True, exist_ok=True)
    
    rules_path = rules_dir / f"{client_name}.json"
    
    with open(rules_path, 'wb') as f:
        f.write(uploaded_file.read())
    
    return rules_path

def run_qa_analysis(copy_doc, email_file, client_name, segment, rules_path):
    """Execute QA analysis with progress tracking."""
    
    # Save uploaded files
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    
    copy_doc_path = uploads_dir / copy_doc.name
    email_file_path = uploads_dir / email_file.name
    
    with open(copy_doc_path, "wb") as f:
        f.write(copy_doc.read())
    
    with open(email_file_path, "wb") as f:
        f.write(email_file.read())
    
    # Progress tracking
    st.markdown("### Analysis Progress")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Updated to 6 tasks
    task_names = [
        "Extracting copy requirements",
        "Analyzing email content",
        "Validating links and CTAs",
        "Inspecting visual elements",
        "Checking compliance",
        "Generating comprehensive report"  # NEW TASK 6
    ]
    
    # Create tabs for results - add A/B Test tab
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Executive Summary",
        "A/B Test Analysis",  # NEW TAB
        "Detailed Findings",
        "Compliance Report",
        "Raw Data"
    ])
    
    try:
        # Initialize crew
        crew = EmailQACrew(
            client_name=client_name,
            campaign_name=email_file.name.replace('.eml', '').replace('.html', ''),
            segment=segment,
            document_path=str(copy_doc_path),
            email_path=str(email_file_path)
        )
        
        # Simulate progress
        for i, task_name in enumerate(task_names):
            status_text.text(f"Task {i+1}/6: {task_name}...")  # Updated to /6
            progress_bar.progress((i + 1) / len(task_names))
        
        result = crew.kickoff()
        
        status_text.text("Analysis complete!")
        progress_bar.progress(1.0)
        
        # Display results
        display_results(result, tab1, tab2, tab3, tab4, tab5)
        
        # Save report
        report_path = save_report(result, client_name, email_file.name)
        
        st.success(f"QA report saved to: {report_path}")
        
        with open(report_path, 'r') as f:
            st.download_button(
                label="Download Report",
                data=f.read(),
                file_name=f"qa_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    
    except Exception as e:
        st.error(f"Analysis failed: {str(e)}")
        st.exception(e)


def display_results(result, tab1, tab2, tab3, tab4, tab5):
    """Display QA results in tabs."""
    
    result_str = str(result)
    
    # Tab 1: Executive Summary
    with tab1:
        st.subheader("Executive Summary")
        
        # Parse launch decision
        if "BLOCK" in result_str.upper() or "cannot launch" in result_str.lower():
            st.markdown('<div class="error-box"><h3>⛔ BLOCKED - Cannot Launch</h3></div>', unsafe_allow_html=True)
        elif "APPROVE WITH FIXES" in result_str.upper():
            st.markdown('<div class="warning-box"><h3>⚠️ APPROVE WITH FIXES</h3></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="success-box"><h3>✅ APPROVED - Ready to Launch</h3></div>', unsafe_allow_html=True)
        
        # Issue metrics
        col1, col2, col3 = st.columns(3)
        
        critical_count = result_str.upper().count("CRITICAL")
        high_count = result_str.upper().count("HIGH")
        medium_count = result_str.upper().count("MEDIUM")
        
        with col1:
            st.metric(
                "Critical Issues",
                critical_count,
                delta="Blocking" if critical_count > 0 else None,
                delta_color="inverse"
            )
        
        with col2:
            st.metric("High Priority", high_count)
        
        with col3:
            st.metric("Medium/Low", medium_count)
        
        # Extract executive summary section if present
        if "EXECUTIVE SUMMARY" in result_str.upper():
            st.markdown("---")
            st.markdown("### Key Findings")
            # Display first few lines of the report
            lines = result_str.split('\n')[:20]
            st.text('\n'.join(lines))
    
    # Tab 2: A/B Test Analysis (NEW)
    with tab2:
        st.subheader("A/B Test Analysis")
        
        if "variant" in result_str.lower() or "a/b" in result_str.lower():
            st.markdown("### Variant Comparison")
            
            # Look for A/B test sections
            if "variant a" in result_str.lower() and "variant b" in result_str.lower():
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### Variant A")
                    st.info("Analyzing Variant A compliance and performance...")
                
                with col2:
                    st.markdown("#### Variant B")
                    st.info("Analyzing Variant B compliance and performance...")
                
                st.markdown("---")
                st.markdown("### Recommendation")
                st.write("Based on QA findings, the recommended variant will be highlighted in the report.")
            else:
                st.info("No A/B test variants detected in this campaign.")
        else:
            st.info("This campaign does not appear to have A/B test variants.")
    
    # Tab 3: Detailed Findings
    with tab3:
        st.subheader("Detailed Findings")
        
        # Show blocking issues first
        if "BLOCKING" in result_str.upper() or "CRITICAL" in result_str.upper():
            st.markdown("### 🚨 Blocking Issues")
            st.error("The following issues must be fixed before launch:")
            
        st.markdown(result_str)
    
    # Tab 4: Compliance
    with tab4:
        st.subheader("Compliance Report")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("#### CAN-SPAM")
            if "unsubscribe" in result_str.lower():
                if "missing" in result_str.lower() or "not found" in result_str.lower():
                    st.error("❌ FAIL")
                else:
                    st.success("✅ PASS")
        
        with col2:
            st.markdown("#### Accessibility")
            if "alt text" in result_str.lower():
                if "missing" in result_str.lower() or "not found" in result_str.lower():
                    st.error("❌ FAIL")
                else:
                    st.success("✅ PASS")
        
        with col3:
            st.markdown("#### Links")
            if "broken" in result_str.lower() or "404" in result_str:
                st.error("❌ FAIL")
            else:
                st.success("✅ PASS")
        
        st.markdown("---")
        st.text_area("Full Compliance Details", result_str, height=300)
    
    # Tab 5: Raw Data
    with tab5:
        st.subheader("Raw Analysis Data")
        st.code(result_str, language="text")
        
        # Add copy button
        if st.button("Copy to Clipboard"):
            st.toast("Report copied to clipboard!")

def save_report(result, client_name, email_name):
    """Save QA report to file."""
    
    reports_dir = Path("qa_reports")
    reports_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{client_name}_{email_name.replace('.', '_')}_{timestamp}.json"
    report_path = reports_dir / filename
    
    report_data = {
        "client": client_name,
        "email": email_name,
        "timestamp": datetime.now().isoformat(),
        "result": str(result)
    }
    
    with open(report_path, 'w') as f:
        json.dump(report_data, f, indent=2)
    
    return report_path

if __name__ == "__main__":
    main()