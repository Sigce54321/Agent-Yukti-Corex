import re
import streamlit as st


def render_issue_form() -> dict | None:
    """
    Display the GitHub repository and issue input form.

    Returns:
        dict: repo_url and issue_number when valid.
        None: If the form is not submitted or input is invalid.
    """

    st.subheader("Start a Debugging Task")

    with st.form("issue_submission_form"):
        repo_url = st.text_input(
            "GitHub Repository URL",
            placeholder="https://github.com/Sigce54321/Agent-Yukti-Corex.git"
        )

        issue_number = st.number_input(
            "GitHub Issue Number",
            min_value=1,
            step=1,
            value=1
        )

        submitted = st.form_submit_button(
            "Start Debugging",
            type="primary",
            use_container_width=True
        )

    if not submitted:
        return None

    repo_url = repo_url.strip().rstrip("/")

    pattern = r"^https://github\.com/[^/\s]+/[^/\s]+$"

    if not re.match(pattern, repo_url):
        st.error(
            "Enter a valid GitHub repository URL."
        )
        return None

    return {
        "repo_url": repo_url,
        "issue_number": int(issue_number)
    }