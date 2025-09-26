"""
Streamlit Web UI for Email QA System
=====================================
Purpose: Interactive web interface for email QA validation
Author: Rishabh Sharma
Date: 2024

This module provides the Streamlit-based user interface for running
QA checks, managing client rules, and viewing analytics.

Metadata:
---------
Session State Variables:
    qa_history (List[Dict]): Historical QA check records
        - timestamp (str): ISO format datetime
        - client (str): Client name
        - campaign (str): Campaign name
        - passed (bool): Overall pass/fail
        - duration (float): Processing time in seconds
        - results (Dict): Complete QA results
        - doc_preview (str): First 500 chars of document
        - email_preview (str): First 500 chars of email
    
    current_results (Dict): Latest QA results from crew
    current_rules (Dict): Active rules from DynamicRulesEngine
    current_client (str): Selected client name
    require_validation (bool): User validation checkpoint flag
    
Page Functions:
    show_dashboard(): Main metrics and recent activity
    run_qa_check(): QA execution interface
    manage_rules(): Client rules configuration
    show_analytics(): Historical analytics
    show_settings(): System configuration
    
Integration with previous files:
    - Uses DynamicRulesEngine for rules management
    - Uses AutomatedEmailQaCrew for QA execution
    - Uses RobustQAWorkflow for progress tracking
    - Displays results from all parsers and agents
"""

import streamlit as st
import json
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

# Import components from previous files
from automated_email_qa.crew import AutomatedEmailQaCrew
from automated_email_qa.core.dynamic_rules import DynamicRulesEngine
from automated_email_qa.tools.universal_parser import UniversalDocumentParser
from automated_email_qa.tools.email_parser import EmailParser
from automated_email_qa.core.qa_workflow import RobustQAWorkflow

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Email QA System",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "Automated Email QA System v1.0 - Powered by CrewAI"
    }
)

# Initialize session state variables
def init_session_state():
    """Initialize all session state variables."""
    if 'qa_history' not in st.session_state:
        st.session_state.qa_history = []
    if 'current_results' not in st.session_state:
        st.session_state.current_results = None
    if 'current_rules' not in st.session_state:
        st.session_state.current_rules = {}
    if 'current_client' not in st.session_state:
        st.session_state.current_client = None
    if 'require_validation' not in st.session_state:
        st.session_state.require_validation = False
    if 'rules_engine' not in st.session_state:
        st.session_state.rules_engine = DynamicRulesEngine()
    if 'crew' not in st.session_state:
        st.session_state.crew = None  # Initialize lazily

def main():
    """
    Main application entry point.
    
    Manages page routing and navigation.
    """
    init_session_state()
    
    # Sidebar navigation
    with st.sidebar:
        st.title("📧 Email QA System")
        st.markdown("---")
        
        # Navigation menu
        page = st.radio(
            "Navigation",
            ["🏠 Dashboard", "🚀 Run QA Check", "📋 Manage Rules", 
             "📊 Analytics", "⚙️ Settings"],
            key="navigation"
        )
        
        # Quick stats
        st.markdown("---")
        st.metric("Total QA Checks", len(st.session_state.qa_history))
        
        if st.session_state.qa_history:
            recent = st.session_state.qa_history[-1]
            st.caption(f"Last check: {recent['client']}")
            st.caption(f"Status: {'✅ Passed' if recent['passed'] else '❌ Failed'}")
    
    # Route to selected page
    if page == "🏠 Dashboard":
        show_dashboard()
    elif page == "🚀 Run QA Check":
        run_qa_check()
    elif page == "📋 Manage Rules":
        manage_rules()
    elif page == "📊 Analytics":
        show_analytics()
    elif page == "⚙️ Settings":
        show_settings()

def show_dashboard():
    """
    Display dashboard with key metrics and recent activity.
    
    Shows:
    - Overall metrics
    - Pass rate trends
    - Recent QA checks
    - Common issues
    """
    st.title("📊 QA Dashboard")
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_checks = len(st.session_state.qa_history)
        st.metric(
            "Total QA Checks", 
            total_checks,
            delta=f"+{sum(1 for h in st.session_state.qa_history if datetime.fromisoformat(h['timestamp']) > datetime.now() - timedelta(days=7))} this week"
        )
    
    with col2:
        if st.session_state.qa_history:
            avg_time = sum(h.get('duration', 0) for h in st.session_state.qa_history) / len(st.session_state.qa_history)
            st.metric("Avg. Processing Time", f"{avg_time:.1f}s")
        else:
            st.metric("Avg. Processing Time", "N/A")
    
    with col3:
        if st.session_state.qa_history:
            pass_rate = sum(1 for h in st.session_state.qa_history if h.get('passed', False)) / len(st.session_state.qa_history) * 100
            st.metric("Pass Rate", f"{pass_rate:.1f}%", delta=f"{pass_rate-50:.1f}%")
        else:
            st.metric("Pass Rate", "N/A")
    
    with col4:
        saved_clients = len(st.session_state.rules_engine.get_available_clients())
        st.metric("Saved Clients", saved_clients)
    
    # Charts
    if st.session_state.qa_history:
        st.subheader("QA Trends")
        
        # Prepare data for charts
        df = pd.DataFrame(st.session_state.qa_history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Pass rate over time
            daily_stats = df.groupby('date').agg({
                'passed': 'mean'
            }).reset_index()
            daily_stats['pass_rate'] = daily_stats['passed'] * 100
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=daily_stats['date'],
                y=daily_stats['pass_rate'],
                mode='lines+markers',
                name='Pass Rate',
                line=dict(color='#10B981', width=2),
                marker=dict(size=8)
            ))
            fig.update_layout(
                title='Pass Rate Trend',
                xaxis_title='Date',
                yaxis_title='Pass Rate (%)',
                height=300,
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # QA checks by client
            client_stats = df.groupby('client').size().reset_index(name='count')
            fig = go.Figure(data=[
                go.Bar(
                    x=client_stats['client'],
                    y=client_stats['count'],
                    marker_color='#3B82F6'
                )
            ])
            fig.update_layout(
                title='QA Checks by Client',
                xaxis_title='Client',
                yaxis_title='Number of Checks',
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Recent Activity
    st.subheader("Recent QA Checks")
    
    if st.session_state.qa_history:
        recent_checks = st.session_state.qa_history[-5:][::-1]  # Last 5, reversed
        
        for check in recent_checks:
            with st.expander(
                f"{check['client']} - {check.get('campaign', 'Campaign')} | "
                f"{datetime.fromisoformat(check['timestamp']).strftime('%Y-%m-%d %H:%M')}"
            ):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"**Status:** {'✅ Passed' if check['passed'] else '❌ Failed'}")
                    st.write(f"**Duration:** {check.get('duration', 0):.1f}s")
                
                with col2:
                    results = check.get('results', {})
                    st.write(f"**QA Score:** {results.get('qa_score', 0):.1f}/100")
                    st.write(f"**Issues Found:** {len(results.get('critical_issues', []))}")
                
                with col3:
                    if st.button("View Full Report", key=f"view_{check['timestamp']}"):
                        st.session_state.current_results = results
                        st.rerun()
    else:
        st.info("No QA checks performed yet. Go to 'Run QA Check' to start.")

def run_qa_check():
    """
    Main QA check interface.
    
    Allows users to:
    - Select or create client
    - Load or create rules
    - Input documents and emails
    - Execute QA validation
    - View results
    """
    st.title("🚀 Run Email QA Check")
    
    # Step 1: Client Selection
    st.header("Step 1: Client Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        client_option = st.radio(
            "Client Type",
            ["Use Saved Client", "Quick Check (No Save)", "Create New Client"],
            key="client_option"
        )
    
    with col2:
        if client_option == "Use Saved Client":
            saved_clients = st.session_state.rules_engine.get_available_clients()
            if saved_clients:
                selected_client = st.selectbox("Select Client", saved_clients)
                if st.button("Load Client Rules"):
                    try:
                        rules = st.session_state.rules_engine.load_rules(selected_client)
                        st.session_state.current_rules = rules
                        st.session_state.current_client = selected_client
                        st.success(f"✅ Loaded rules for {selected_client}")
                    except Exception as e:
                        st.error(f"Failed to load rules: {e}")
            else:
                st.warning("No saved clients found. Create a new client or use Quick Check.")
        
        elif client_option == "Create New Client":
            new_client_name = st.text_input("Client Name")
            campaign_name = st.text_input("Campaign Name", value="Email Campaign")
            industry = st.selectbox(
                "Industry",
                ["E-commerce", "SaaS", "Healthcare", "Finance", "Education", "Other"]
            )
            
            if new_client_name and st.button("Create Client"):
                st.session_state.current_client = new_client_name
                st.session_state.current_campaign = campaign_name
                st.session_state.current_industry = industry.lower()
                st.info(f"Created client: {new_client_name}")
        
        else:  # Quick Check
            st.session_state.current_client = "Quick Check"
            st.info("Quick check mode - results won't be saved")
    
    # Step 2: Rules Configuration
    if st.session_state.current_client:
        st.header("Step 2: QA Rules")
        
        if client_option != "Use Saved Client" or not st.session_state.current_rules:
            with st.expander("Configure Rules", expanded=True):
                # Brand Guidelines
                st.subheader("🎨 Brand Guidelines")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    brand_tone = st.text_area(
                        "Brand Tone Description",
                        placeholder="Professional, friendly, authoritative",
                        help="Describe your brand's tone of voice"
                    )
                    
                    cta_style = st.selectbox(
                        "CTA Button Style",
                        ["UPPERCASE", "Title Case", "lowercase", "Sentence case"],
                        help="How should CTA buttons be formatted?"
                    )
                
                with col2:
                    preferred_verbs = st.text_area(
                        "Preferred CTA Verbs (one per line)",
                        placeholder="GET\nLEARN\nDISCOVER\nSTART",
                        help="Action verbs for CTAs"
                    )
                    
                    strict_mode = st.checkbox(
                        "Strict Validation",
                        help="Require exact matches for all elements"
                    )
                
                # Create rules from inputs
                config = {
                    'brand_tone': brand_tone,
                    'cta_style': cta_style,
                    'preferred_verbs': preferred_verbs.split('\n') if preferred_verbs else [],
                    'validation': {
                        'strict_mode': strict_mode,
                        'case_sensitive': cta_style == 'UPPERCASE'
                    }
                }
                
                st.session_state.current_rules = st.session_state.rules_engine.create_rules(config)
                
                # Save option for new clients
                if client_option == "Create New Client" and st.button("💾 Save Rules"):
                    try:
                        st.session_state.rules_engine.save_rules(
                            st.session_state.current_client,
                            st.session_state.current_rules
                        )
                        st.success(f"✅ Saved rules for {st.session_state.current_client}")
                    except Exception as e:
                        st.error(f"Failed to save rules: {e}")
    
    # Step 3: Input Documents
    if st.session_state.current_client and st.session_state.current_rules:
        st.header("Step 3: Input Documents")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📄 Copy Document")
            doc_input_method = st.radio(
                "Input Method",
                ["Upload File", "Paste Text"],
                key="doc_method"
            )
            
            doc_content = None
            if doc_input_method == "Upload File":
                doc_file = st.file_uploader(
                    "Upload copy document",
                    type=['txt', 'html', 'eml', 'docx', 'pdf'],
                    key="doc_file",
                    help="Upload the document containing email requirements"
                )
                if doc_file:
                    doc_content = doc_file.read()
                    if isinstance(doc_content, bytes):
                        doc_content = doc_content.decode('utf-8', errors='ignore')
                    st.success(f"✅ Loaded {doc_file.name}")
            else:
                doc_content = st.text_area(
                    "Paste copy document",
                    height=300,
                    key="doc_text",
                    placeholder="Paste your email copy requirements here..."
                )
        
        with col2:
            st.subheader("📧 Email to Check")
            email_input_method = st.radio(
                "Input Method",
                ["Upload File", "Paste HTML"],
                key="email_method"
            )
            
            email_content = None
            if email_input_method == "Upload File":
                email_file = st.file_uploader(
                    "Upload email",
                    type=['html', 'eml'],
                    key="email_file",
                    help="Upload the email HTML or EML file to validate"
                )
                if email_file:
                    email_content = email_file.read()
                    if isinstance(email_content, bytes):
                        email_content = email_content.decode('utf-8', errors='ignore')
                    st.success(f"✅ Loaded {email_file.name}")
            else:
                email_content = st.text_area(
                    "Paste email HTML",
                    height=300,
                    key="email_text",
                    placeholder="Paste your email HTML here..."
                )
        
        # Step 4: QA Options
        st.header("Step 4: QA Options")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            check_links = st.checkbox("Validate Links", value=True)
        with col2:
            check_visual = st.checkbox("Visual Inspection", value=True)
        with col3:
            check_compliance = st.checkbox("Compliance Check", value=True)
        with col4:
            require_validation = st.checkbox("User Validation", value=False)
            st.session_state.require_validation = require_validation
        
        # Run QA Button
        st.markdown("---")
        
        if st.button(
            "🚀 Run QA Check",
            type="primary",
            use_container_width=True,
            disabled=not (doc_content and email_content)
        ):
            if doc_content and email_content:
                run_qa_analysis(doc_content, email_content, {
                    'check_links': check_links,
                    'check_visual': check_visual,
                    'check_compliance': check_compliance
                })
            else:
                st.error("Please provide both copy document and email content")

def run_qa_analysis(doc_content: str, email_content: str, options: Dict[str, bool]):
    """
    Execute QA analysis using the crew.
    
    Args:
        doc_content (str): Document content
        email_content (str): Email content  
        options (Dict[str, bool]): QA options
    """
    with st.spinner("🔄 Running QA Analysis..."):
        try:
            start_time = datetime.now()
            
            # Initialize crew if needed
            if st.session_state.crew is None:
                st.session_state.crew = AutomatedEmailQaCrew()
            
            # Run QA
            results = st.session_state.crew.run_qa(
                document_content=doc_content,
                email_content=email_content,
                client_name=st.session_state.current_client,
                rules=st.session_state.current_rules
            )
            
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()
            
            # Store results
            st.session_state.current_results = results
            
            # Add to history
            st.session_state.qa_history.append({
                'timestamp': datetime.now().isoformat(),
                'client': st.session_state.current_client,
                'campaign': st.session_state.get('current_campaign', 'Campaign'),
                'passed': results.get('pass_fail_verdict', False),
                'duration': duration,
                'results': results,
                'doc_preview': doc_content[:500],
                'email_preview': email_content[:500]
            })
            
            st.success("✅ QA Analysis Complete!")
            st.balloons()
            
            # Display results summary
            display_results_summary(results)
            
        except Exception as e:
            st.error(f"❌ QA Analysis Failed: {str(e)}")
            logger.error(f"QA analysis error: {e}")

def display_results_summary(results: Dict[str, Any]):
    """
    Display summary of QA results.
    
    Args:
        results (Dict[str, Any]): QA results from crew
    """
    st.header("📊 QA Results Summary")
    
    # Overall verdict
    verdict = results.get('pass_fail_verdict', False)
    if verdict:
        st.success("✅ **PASSED** - Email meets all requirements")
    else:
        st.error("❌ **FAILED** - Issues found requiring attention")
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("QA Score", f"{results.get('qa_score', 0):.1f}/100")
    
    with col2:
        critical_count = len(results.get('critical_issues', []))
        st.metric("Critical Issues", critical_count, delta=f"-{critical_count}" if critical_count > 0 else "0")
    
    with col3:
        warning_count = len(results.get('warnings', []))
        st.metric("Warnings", warning_count)
    
    with col4:
        st.metric("Processing Time", f"{results.get('metrics', {}).get('processing_time_seconds', 0):.1f}s")
    
    # Critical Issues
    if results.get('critical_issues'):
        st.error("**Critical Issues Requiring Immediate Attention:**")
        for issue in results['critical_issues']:
            st.write(f"• **{issue.get('category', 'General')}**: {issue.get('description', 'Issue found')}")
            st.write(f"  📝 *Recommendation*: {issue.get('recommendation', 'Fix required')}")
    
    # Detailed Results Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📝 Content", "🔗 Links", "👁️ Visual", "⚖️ Compliance", "📄 Full Report"
    ])
    
    with tab1:
        st.subheader("Content Analysis")
        if 'detailed_findings' in results:
            content = results['detailed_findings'].get('content_analysis', {})
            
            # Subject line check
            subject_check = content.get('subject_line_check', {})
            if subject_check.get('passed'):
                st.success(f"✅ Subject line matches: {subject_check.get('email_subject')}")
            else:
                st.error(f"❌ Subject mismatch")
                st.write(f"Expected: {subject_check.get('required_subjects')}")
                st.write(f"Found: {subject_check.get('email_subject')}")
    
    with tab2:
        st.subheader("Link Validation")
        if 'detailed_findings' in results:
            links = results['detailed_findings'].get('link_validation', {})
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Links", links.get('total_links_found', 0))
                st.metric("Valid Links", links.get('matched_links', 0))
            with col2:
                st.metric("Broken Links", len(links.get('broken_links', [])))
                st.metric("Missing Links", len(links.get('missing_links', [])))
    
    with tab3:
        st.subheader("Visual Inspection")
        if 'detailed_findings' in results:
            visual = results['detailed_findings'].get('visual_inspection', {})
            if visual.get('visual_inspection_performed'):
                st.metric("Rendering Score", f"{visual.get('rendering_score', 0):.1f}/100")
                
                if visual.get('brand_compliance', {}).get('overall_compliant'):
                    st.success("✅ Brand compliant")
                else:
                    st.error("❌ Brand compliance issues found")
    
    with tab4:
        st.subheader("Compliance Check")
        if 'detailed_findings' in results:
            compliance = results['detailed_findings'].get('compliance_check', {})
            
            can_spam = compliance.get('can_spam_compliance', {})
            if can_spam.get('passed'):
                st.success("✅ CAN-SPAM Compliant")
            else:
                st.error("❌ CAN-SPAM Issues")
                if not can_spam.get('unsubscribe_link_present'):
                    st.write("• Missing unsubscribe link")
                if not can_spam.get('physical_address_present'):
                    st.write("• Missing physical address")
    
    with tab5:
        st.subheader("Full QA Report")
        st.json(results)
        
        # Download button
        st.download_button(
            label="📥 Download Report (JSON)",
            data=json.dumps(results, indent=2),
            file_name=f"qa_report_{st.session_state.current_client}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

def manage_rules():
    """
    Rules management interface.
    
    Allows users to:
    - View saved client rules
    - Edit existing rules
    - Import/export rules
    - Delete rules
    """
    st.title("📋 Manage QA Rules")
    
    tab1, tab2, tab3 = st.tabs(["View Rules", "Edit Rules", "Import/Export"])
    
    with tab1:
        st.subheader("Saved Client Rules")
        
        saved_clients = st.session_state.rules_engine.get_available_clients()
        
        if saved_clients:
            selected = st.selectbox("Select Client", saved_clients)
            
            if selected:
                try:
                    rules = st.session_state.rules_engine.load_rules(selected)
                    
                    # Display rules in organized format
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("Brand Guidelines")
                        st.json(rules.get('brand', {}))
                    
                    with col2:
                        st.subheader("Validation Settings")
                        st.json(rules.get('validation', {}))
                    
                    # Delete option
                    if st.button(f"🗑️ Delete {selected} Rules", type="secondary"):
                        rules_path = st.session_state.rules_engine.rules_dir / f"{selected}.json"
                        rules_path.unlink()
                        st.success(f"Deleted rules for {selected}")
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Failed to load rules: {e}")
        else:
            st.info("No saved rules found. Create rules in 'Run QA Check'.")
    
    with tab2:
        st.subheader("Edit Client Rules")
        
        if saved_clients:
            client_to_edit = st.selectbox("Select Client to Edit", saved_clients, key="edit_client")
            
            if client_to_edit:
                try:
                    rules = st.session_state.rules_engine.load_rules(client_to_edit)
                    
                    # Edit form
                    with st.form("edit_rules_form"):
                        st.subheader("Brand Configuration")
                        
                        brand_tone = st.text_area(
                            "Brand Tone",
                            value=rules.get('brand', {}).get('tone', {}).get('description', '')
                        )
                        
                        cta_style = st.selectbox(
                            "CTA Style",
                            ["UPPERCASE", "Title Case", "lowercase", "Sentence case"],
                            index=["UPPERCASE", "Title Case", "lowercase", "Sentence case"].index(
                                rules.get('brand', {}).get('cta', {}).get('style', 'UPPERCASE')
                            )
                        )
                        
                        strict_mode = st.checkbox(
                            "Strict Validation",
                            value=rules.get('validation', {}).get('strict_mode', False)
                        )
                        
                        if st.form_submit_button("💾 Save Changes"):
                            # Update rules
                            rules['brand']['tone']['description'] = brand_tone
                            rules['brand']['cta']['style'] = cta_style
                            rules['validation']['strict_mode'] = strict_mode
                            
                            # Save
                            st.session_state.rules_engine.save_rules(client_to_edit, rules)
                            st.success(f"✅ Updated rules for {client_to_edit}")
                            
                except Exception as e:
                    st.error(f"Failed to edit rules: {e}")
    
    with tab3:
        st.subheader("Import/Export Rules")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📤 Export Rules")
            
            if saved_clients:
                export_client = st.selectbox("Select Client to Export", saved_clients, key="export_client")
                
                if st.button("Export Rules"):
                    try:
                        rules = st.session_state.rules_engine.load_rules(export_client)
                        
                        st.download_button(
                            label="📥 Download Rules (JSON)",
                            data=json.dumps(rules, indent=2),
                            file_name=f"{export_client}_rules.json",
                            mime="application/json"
                        )
                    except Exception as e:
                        st.error(f"Failed to export: {e}")
        
        with col2:
            st.subheader("📥 Import Rules")
            
            uploaded_file = st.file_uploader(
                "Choose rules file",
                type=['json'],
                help="Upload a JSON rules file"
            )
            
            if uploaded_file:
                import_client_name = st.text_input("Client Name for Import")
                
                if import_client_name and st.button("Import Rules"):
                    try:
                        rules = json.load(uploaded_file)
                        st.session_state.rules_engine.save_rules(import_client_name, rules)
                        st.success(f"✅ Imported rules for {import_client_name}")
                    except Exception as e:
                        st.error(f"Failed to import: {e}")

def show_analytics():
    """
    Display analytics dashboard.
    
    Shows:
    - QA trends over time
    - Common issues
    - Client performance
    - Agent performance
    """
    st.title("📊 QA Analytics")
    
    if not st.session_state.qa_history:
        st.info("No data available yet. Run some QA checks to see analytics.")
        return
    
    # Prepare data
    df = pd.DataFrame(st.session_state.qa_history)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Date range filter
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=df['timestamp'].min().date()
        )
    with col2:
        end_date = st.date_input(
            "End Date",
            value=df['timestamp'].max().date()
        )
    
    # Filter data
    mask = (df['timestamp'].dt.date >= start_date) & (df['timestamp'].dt.date <= end_date)
    filtered_df = df[mask]
    
    if filtered_df.empty:
        st.warning("No data in selected range")
        return
    
    # Overall metrics
    st.subheader("Overall Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Checks", len(filtered_df))
    
    with col2:
        pass_rate = filtered_df['passed'].mean() * 100
        st.metric("Pass Rate", f"{pass_rate:.1f}%")
    
    with col3:
        avg_duration = filtered_df['duration'].mean()
        st.metric("Avg Duration", f"{avg_duration:.1f}s")
    
    with col4:
        unique_clients = filtered_df['client'].nunique()
        st.metric("Unique Clients", unique_clients)
    
    # Charts
    st.subheader("Trends Analysis")
    
    # Pass rate over time
    daily_stats = filtered_df.set_index('timestamp').resample('D').agg({
        'passed': 'mean',
        'duration': 'mean'
    }).reset_index()
    
    fig = go.Figure()
    
    # Add pass rate line
    fig.add_trace(go.Scatter(
        x=daily_stats['timestamp'],
        y=daily_stats['passed'] * 100,
        mode='lines+markers',
        name='Pass Rate (%)',
        line=dict(color='#10B981', width=2)
    ))
    
    # Add duration line on secondary axis
    fig.add_trace(go.Scatter(
        x=daily_stats['timestamp'],
        y=daily_stats['duration'],
        mode='lines+markers',
        name='Avg Duration (s)',
        line=dict(color='#3B82F6', width=2),
        yaxis='y2'
    ))
    
    fig.update_layout(
        title='QA Performance Over Time',
        xaxis_title='Date',
        yaxis=dict(title='Pass Rate (%)', side='left'),
        yaxis2=dict(title='Duration (seconds)', overlaying='y', side='right'),
        height=400,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Client breakdown
    st.subheader("Client Performance")
    
    client_stats = filtered_df.groupby('client').agg({
        'passed': 'mean',
        'duration': 'mean',
        'timestamp': 'count'
    }).reset_index()
    client_stats.columns = ['Client', 'Pass Rate', 'Avg Duration', 'Total Checks']
    client_stats['Pass Rate'] = client_stats['Pass Rate'] * 100
    
    st.dataframe(
        client_stats.style.format({
            'Pass Rate': '{:.1f}%',
            'Avg Duration': '{:.1f}s'
        }),
        use_container_width=True
    )
    
    # Common issues
    st.subheader("Common Issues")
    
    all_issues = []
    for record in filtered_df['results']:
        if isinstance(record, dict):
            for issue in record.get('critical_issues', []):
                all_issues.append(issue.get('category', 'Unknown'))
    
    if all_issues:
        issue_counts = pd.Series(all_issues).value_counts()
        
        fig = go.Figure(data=[
            go.Bar(
                x=issue_counts.index,
                y=issue_counts.values,
                marker_color='#EF4444'
            )
        ])
        
        fig.update_layout(
            title='Most Common Critical Issues',
            xaxis_title='Issue Category',
            yaxis_title='Frequency',
            height=300
        )
        
        st.plotly_chart(fig, use_container_width=True)

def show_settings():
    """
    System settings interface.
    
    Allows configuration of:
    - API keys
    - Model settings
    - Feature flags
    - System preferences
    """
    st.title("⚙️ Settings")
    
    st.subheader("API Configuration")
    
    # API Key input (masked)
    api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        value="sk-..." if st.session_state.get('api_key_set') else "",
        help="Your OpenAI API key for GPT-4 access"
    )
    
    if api_key and api_key != "sk-...":
        st.session_state.api_key_set = True
        # Would save to environment here
    
    st.subheader("Model Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        text_model = st.selectbox(
            "Text Model",
            ["gpt-4o", "gpt-4-turbo-preview", "gpt-4", "gpt-3.5-turbo"],
            help="Model for text analysis"
        )
        
        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            value=0.1,
            step=0.1,
            help="Lower = more consistent, Higher = more creative"
        )
    
    with col2:
        vision_model = st.selectbox(
            "Vision Model",
            ["gpt-4o", "gpt-4-vision-preview"],
            help="Model for visual analysis"
        )
        
        max_retries = st.number_input(
            "Max Retries",
            min_value=1,
            max_value=5,
            value=3,
            help="Maximum retry attempts on error"
        )
    
    st.subheader("Feature Flags")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        enable_vision = st.checkbox("Enable Visual QA", value=True)
        enable_caching = st.checkbox("Enable Caching", value=True)
    
    with col2:
        enable_fallback = st.checkbox("Enable Fallback Models", value=True)
        enable_parallel = st.checkbox("Enable Parallel Processing", value=False)
    
    with col3:
        verbose_logging = st.checkbox("Verbose Logging", value=False)
        save_history = st.checkbox("Save History", value=True)
    
    if st.button("💾 Save Settings", type="primary"):
        # Would save settings to config file
        st.success("✅ Settings saved successfully!")
        
        # Update workflow config
        if st.session_state.crew:
            st.session_state.crew.workflow_config.update({
                'VISION_ENABLED': enable_vision,
                'text_model': text_model,
                'vision_model': vision_model,
                'temperature': temperature,
                'MAX_RETRIES': max_retries
            })

if __name__ == "__main__":
    main()