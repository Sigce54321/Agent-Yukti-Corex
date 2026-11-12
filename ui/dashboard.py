"""Compose the screenshot-inspired workspace around existing guarded UI modules."""
import streamlit as st
from ui import backend
from ui.issue_form import show_issue_form
from ui.progress import show_progress, render_timeline, render_agents
from ui.results import render_results, render_evidence_grid
from ui.approval import show_approval
from ui.visuals import icon, text, badge, row, title, status_tone


def initialize_session():
    for key, value in {"task_id": None, "task_status": "pending", "task_stage": "queued", "task_message": "", "repo_url": "", "issue_number": None}.items():
        st.session_state.setdefault(key, value)


def check_backend():
    return backend.local_status()


def display_metrics(results=None):
    results = results or {}
    challenger = results.get("challenger_review") or {}
    verification = results.get("verification") or {}
    regression = verification.get("regression") or {}
    duration = regression.get("duration_seconds")
    duration_label = f"{duration:.1f} s" if isinstance(duration, (int, float)) and not isinstance(duration, bool) else "Unavailable"
    task = st.session_state.get("task_id")
    cards = [
        ("bug", "Repair Status", st.session_state.get("task_status", "pending").replace("_", " ").title() if task else "Not started", "Current task", "cyan"),
        ("check", "Challenger Verdict", challenger.get("verdict") or "Pending", "Independent review", "cyan"),
        ("flask", "Regression Tests", regression.get("test_status", "not_run").replace("_", " ").title(), "Docker evidence", "purple"),
        ("clock", "Verification Time", duration_label, "Regression duration", "cyan"),
    ]
    html = '<div class="summary-grid">'
    for symbol, label, value, hint, tone in cards:
        html += f'<div class="summary-card {tone}"><div class="metric-icon">{icon(symbol, 30)}</div><div class="summary-content"><div class="metric-label">{label}</div><div class="metric-value">{text(value)}</div><small>{hint}</small></div></div>'
    st.markdown(html + '</div>', unsafe_allow_html=True)


def display_current_task(results=None):
    results = results or {}
    st.markdown(title("Issue Summary"), unsafe_allow_html=True)
    task = st.session_state.get("task_id")
    issue = st.session_state.get("issue_number")
    if not task:
        st.markdown('<div class="empty-symbol">' + icon("file", 32) + '</div>', unsafe_allow_html=True)
        st.caption("Your issue context will appear here once a task is submitted.")
        return
    st.markdown(f'<div class="issue-number">Issue #{text(issue)}</div>' + badge(st.session_state.get("task_status", "pending").replace("_", " "), status_tone(results.get("status"))), unsafe_allow_html=True)
    st.write(results.get("bug_explanation") or st.session_state.get("task_message") or "Waiting for issue analysis.")
    st.markdown(row("Affected file", results.get("bug_file")) + row("Function", results.get("bug_location")) + row("Language", results.get("language")), unsafe_allow_html=True)
    with st.expander("Task details"):
        st.code(task, language="text")
        st.write(st.session_state.get("repo_url") or "Repository unavailable")
    st.caption("Issue title and full description are not exposed by the current results interface.")


def display_workflow():
    render_timeline(st.session_state.get("task_stage") if st.session_state.get("task_id") else None, st.session_state.get("task_status"))


def render_dashboard():
    initialize_session()
    st.sidebar.markdown('<div class="side-logo">' + icon("code", 26) + '<span>Yukti<span class="violet">C-oreX</span></span></div>', unsafe_allow_html=True)
    st.sidebar.caption("REPAIR CONTROL CENTER")
    labels = {"Dashboard": "⌂  Dashboard", "Report Issue": "⚒  Issue Repair", "Progress": "◷  Workflow", "Results": "▤  Repair Evidence", "Approval": "◇  Human Approval"}
    page = st.sidebar.radio("Workspace", list(labels), format_func=lambda item: labels[item], key="dashboard_navigation", label_visibility="collapsed")
    st.sidebar.markdown('<div class="circuit-art"><div class="circuit-line a"></div><div class="circuit-line b"></div><div class="circuit-core">&lt;/&gt;</div></div>', unsafe_allow_html=True)
    health = check_backend()
    st.sidebar.markdown('<div class="system-card">' + badge("Workflow connected" if health else "Workflow unavailable", "good" if health else "bad") + '<small>Human-controlled release</small></div>', unsafe_allow_html=True)
    st.sidebar.caption("Docker availability is checked during a repair.")
    st.markdown('<div class="topbar"><div class="wordmark">' + icon("code", 32) + '<span>Yukti<span class="violet">C-oreX</span></span><span class="product-tag">Automated Bug Repair System</span></div><div class="topbar-note">EVIDENCE FIRST <span class="avatar">YC</span></div></div>', unsafe_allow_html=True)

    task = st.session_state.get("task_id")
    results = {}
    if task:
        try:
            progress = backend.get_task_progress(task)
            for field, key in (("status", "task_status"), ("stage", "task_stage"), ("message", "task_message")):
                if progress.get(field) is not None:
                    st.session_state[key] = progress[field]
            if progress.get("error"):
                st.error(backend.error_message(progress))
            results = backend.get_task_results(task)
            if results.get("error"):
                st.error(backend.error_message(results))
        except backend.BackendError as exc:
            st.warning(str(exc))
    display_metrics(results)
    if page == "Dashboard":
        with st.container(key="dashboard_grid"):
            left, center, right = st.columns([1.05, 2.7, 1.35], gap="medium")
        with left:
            with st.container(border=True, key="repository_panel"):
                show_issue_form(compact=True)
            with st.container(border=True, key="issue_panel"):
                display_current_task(results)
        with center:
            with st.container(border=True, key="agents_panel"):
                render_agents(st.session_state.get("task_stage") if task else None, st.session_state.get("task_status"))
            with st.container(border=True, key="timeline_panel"):
                display_workflow()
            with st.container(key="evidence_grid"):
                render_evidence_grid(results)
            st.button("Refresh workspace", key="refresh_workspace", use_container_width=True)
        with right:
            with st.container(border=True, key="decision_panel"):
                show_approval(task, compact=True)
            with st.container(border=True, key="passport_panel"):
                st.markdown(title("Fix Passport", "shield"), unsafe_allow_html=True)
                st.caption("Preview and download unavailable: the current results interface does not expose the generated report.")
    elif page == "Report Issue":
        with st.container(border=True):
            show_issue_form()
    elif page == "Progress":
        with st.container(border=True):
            if task:
                show_progress(task)
            else:
                render_empty_page("Workflow", "No repair is running", "Submit a repository and GitHub issue from Issue Repair. Workflow stages and progress will appear here once a task starts.", "branch")
        if task:
            display_workflow()
            render_agents(st.session_state.get("task_stage"), st.session_state.get("task_status"))
    elif page == "Results":
        with st.container(border=True):
            if task:
                render_results(task)
            else:
                render_empty_page("Repair Evidence", "Evidence will appear after analysis", "Start a repair from Issue Repair. This page will show the bug location, patch diff, independent Challenger review and Docker verification returned by the workflow.", "file")
    elif page == "Approval":
        with st.container(border=True):
            if task:
                show_approval(task)
            else:
                render_empty_page("Human Approval", "No patch is ready for review", "Submit an issue and wait for verification. Approval and rejection controls appear only when the workflow is awaiting your decision. Pull request creation remains optional.", "shield")
    st.caption("YuktiC-oreX  /  Verified evidence. Independent review. Human decisions.")


def render_empty_page(label, heading, message, symbol):
    st.markdown('<section class="workspace-empty"><div class="empty-page-icon">' + icon(symbol, 32) + '</div><div class="empty-page-label">' + text(label) + '</div><h2>' + text(heading) + '</h2><p>' + text(message) + '</p><span class="status-badge">No active task</span></section>', unsafe_allow_html=True)
