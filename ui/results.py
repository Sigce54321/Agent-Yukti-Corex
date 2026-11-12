
import streamlit as st
from ui import backend


def _display_code(title: str, code: str, language: str) -> None:
    """Display a code section safely."""

    st.markdown(f"**{title}**")

    if code:
        st.code(code, language=language)
    else:
        st.caption("No code provided by the backend.")


def _display_test_result(title: str, result: dict) -> None:
    """Display baseline or regression test evidence."""

    st.markdown(f"**{title}**")

    if not isinstance(result, dict):
        st.caption("Test result is not available.")
        return

    test_status = result.get("test_status", "not_run")
    passed = result.get("passed")
    exit_code = result.get("exit_code")
    logs = result.get("logs", "")

    if test_status == "passed":
        st.success("Test status: passed")
    elif test_status == "failed":
        st.error("Test status: failed")
    elif test_status == "error":
        st.error("Test status: error")
    else:
        st.info("Test status: not_run")

    st.write(f"**Passed:** {passed}")
    st.write(f"**Exit Code:** {exit_code}")

    execution_command = result.get("execution_command")

    if execution_command:
        st.write("**Execution Command:**")

        if isinstance(execution_command, list):
            command_text = " ".join(
                str(argument) for argument in execution_command
            )
        else:
            command_text = str(execution_command)

        st.code(command_text, language="bash")

    duration = result.get("duration_seconds")

    if duration is not None:
        st.write(f"**Duration:** {duration} seconds")

    if logs:
        with st.expander("View Test Logs"):
            st.code(logs, language="text")


def render_results(task_id: str) -> dict | None:
    """
    Fetch and display debugging results from the local workflow.

    Args:
        task_id: Unique debugging task ID.

    Returns:
        dict: Backend results response.
        None: If results are not available.
    """

    st.subheader("Debugging Results")

    if not task_id:
        st.info("No debugging task selected.")
        return None

    try:
        results = backend.get_task_results(task_id)

        if not isinstance(results, dict):
            st.error("Invalid results response from backend.")
            return None

        error = results.get("error")

        if error:
            if isinstance(error, dict):
                st.error(
                    error.get("message", "Unable to retrieve results.")
                )
            else:
                st.error(str(error))
            return results

        status = results.get("status", "pending")

        st.write(
            f"**Task ID:** `{results.get('task_id', task_id)}`"
        )
        st.write(f"**Status:** `{status}`")

        if status in ("pending", "running"):
            st.info(
                "Debugging is still running. "
                "Refresh progress to check again."
            )
            return results

        if status == "failed":
            st.error("The debugging workflow failed.")
            return results

        if status == "rejected":
            st.warning("This proposed fix has been rejected. The backend does not expose repair evidence for rejected tasks.")
            return results

        if status not in ("awaiting_approval", "approved"):
            st.info(results.get("message") or "Repair evidence is not available yet.")
            return results

        # Identified bug
        st.markdown("### Identified Bug")

        st.write(
            f"**Programming Language:** "
            f"{results.get('language', 'Not available')}"
        )

        st.write(
            f"**Affected File:** "
            f"{results.get('bug_file', 'Not available')}"
        )

        st.write(
            f"**Bug Location:** "
            f"{results.get('bug_location', 'Not available')}"
        )

        st.write(
            f"**Explanation:** "
            f"{results.get('bug_explanation', 'Not available')}"
        )

        language = results.get("language") or "text"

        # Code comparison
        st.markdown("### Code Comparison")

        col1, col2 = st.columns(2)

        with col1:
            _display_code(
                "Original Code",
                results.get("original_code", ""),
                language
            )

        with col2:
            _display_code(
                "Modified Code",
                results.get("modified_code", ""),
                language
            )

        # Code difference
        st.markdown("### Code Difference")

        diff = results.get("diff")

        if diff:
            st.code(diff, language="diff")
        else:
            st.caption("No code difference available.")

        # Fix Challenger review
        st.markdown("### Fix Challenger Review")

        challenger = results.get("challenger_review", {})

        if isinstance(challenger, dict) and challenger:

            st.write(
                f"**Verdict:** "
                f"{challenger.get('verdict') or 'Not available'}"
            )

            st.write(
                f"**Explanation:** "
                f"{challenger.get('explanation') or 'Not available'}"
            )

            for field, title in (
                ("findings", "Findings"),
                ("potential_regressions", "Potential Regressions"),
                ("required_corrections", "Required Corrections"),
            ):
                entries = challenger.get(field) or []
                if isinstance(entries, str):
                    entries = [entries]
                st.write(f"**{title}:**")
                if isinstance(entries, (list, tuple)) and entries:
                    for entry in entries:
                        st.write(f"- {entry}")
                else:
                    st.caption(f"No {title.lower()} reported.")

        else:
            st.caption("Challenger review is not available.")

        # Verification evidence
        st.markdown("### Verification Results")

        verification = results.get("verification", {})

        if isinstance(verification, dict) and verification:

            col1, col2 = st.columns(2)

            with col1:
                _display_test_result(
                    "Baseline Tests",
                    verification.get("baseline", {})
                )

            with col2:
                _display_test_result(
                    "Regression Tests",
                    verification.get("regression", {})
                )

            if "passed" in verification:
                st.write(
                    f"**Final Verification Passed:** "
                    f"{verification['passed']}"
                )

            if verification.get("summary"):
                st.info(verification["summary"])

        else:
            st.caption("Verification results are not available.")

        st.markdown("### Fix Passport")
        st.caption("The workflow generates a Fix Passport, but the current results interface does not expose its contents or a download. Preview and download are unavailable.")

        # GitHub Pull Request
        pull_request_url = results.get("pull_request_url")

        if pull_request_url:
            st.markdown("### GitHub Pull Request")
            st.markdown(
                f"[Open Pull Request]({pull_request_url})"
            )

        return results

    except backend.BackendError as exc:
        st.error(str(exc))
        return None


def render_evidence_grid(results):
    """Compact live-evidence columns matching the supplied repair workspace."""
    from ui.visuals import title, row, text, badge, status_tone, patch_counts
    location, patch, review = st.columns([1.02, 1.6, 1.16], gap="small")
    with location:
        with st.container(border=True, key="location_panel"):
            st.markdown(title("Bug Location & Result", "bug"), unsafe_allow_html=True)
            st.markdown(row("File", results.get("bug_file")) + row("Function", results.get("bug_location")) + row("Language", results.get("language")), unsafe_allow_html=True)
            reason = results.get("bug_explanation")
            st.markdown('<div class="result-callout"><b>◎ Analysis result</b><p>' + text(reason, "Bug location and explanation will appear after workflow analysis.") + '</p></div>', unsafe_allow_html=True)
    with patch:
        with st.container(border=True, key="patch_panel"):
            st.markdown(title("Patch Diff Preview", "code"), unsafe_allow_html=True)
            counts = patch_counts(results.get("diff"))
            st.markdown('<div class="patch-file">' + text(results.get("bug_file"), "Awaiting proposed patch") + (f'<span class="diff-count">+{counts[0]} −{counts[1]}</span>' if counts else '') + '</div>', unsafe_allow_html=True)
            if results.get("diff"):
                st.code(results["diff"], language="diff")
            else:
                st.markdown('<div class="empty-diff"><span>− original lines</span><span>+ proposed changes</span><p>No patch returned yet.</p></div>', unsafe_allow_html=True)
            with st.expander("Original / modified code"):
                language = results.get("language") or "text"
                _display_code("Original Code", results.get("original_code", ""), language)
                _display_code("Modified Code", results.get("modified_code", ""), language)
    with review:
        with st.container(border=True, key="challenger_panel"):
            st.markdown(title("Fix Challenger Review", "shield"), unsafe_allow_html=True)
            challenger = results.get("challenger_review") or {}
            if isinstance(challenger, dict) and challenger:
                st.markdown(badge(challenger.get("verdict", "Unavailable"), status_tone(challenger.get("verdict"))), unsafe_allow_html=True)
                st.write(challenger.get("explanation") or "Explanation unavailable.")
                with st.expander("Findings & corrections"):
                    for field, label in (("findings", "Findings"), ("potential_regressions", "Potential Regressions"), ("required_corrections", "Required Corrections")):
                        st.write(f"**{label}:**")
                        entries = challenger.get(field) or []
                        if isinstance(entries, str):
                            entries = [entries]
                        if isinstance(entries, (list, tuple)) and entries:
                            for entry in entries:
                                st.write(f"- {entry}")
                        else:
                            st.caption(f"No {label.lower()} reported.")
            else:
                st.markdown(badge("Awaiting review"), unsafe_allow_html=True)
                st.caption("Independent Challenger reasoning will appear here. No verdict available yet.")
        with st.container(border=True, key="verification_panel"):
            st.markdown(title("Regression Verification", "flask"), unsafe_allow_html=True)
            verification = results.get("verification") or {}
            for field, label in (("baseline", "Baseline tests"), ("regression", "Regression tests")):
                evidence = verification.get(field) or {}
                state = evidence.get("test_status", "not_run")
                st.markdown('<div class="test-row"><span>' + label + '</span>' + badge(state.replace("_", " "), status_tone(state)) + '</div>', unsafe_allow_html=True)
                if evidence:
                    with st.expander(label + " evidence"):
                        _display_test_result(label, evidence)
            st.caption("Docker execution evidence; test counts are shown only when supplied by the backend.")
