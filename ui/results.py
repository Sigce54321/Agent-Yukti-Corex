
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
