
import streamlit as st

from core.workflow import get_task_results


# --------------------------------------------------
# CODE DISPLAY
# --------------------------------------------------

def _display_code(title: str, code: str, language: str) -> None:

    st.markdown(f"**{title}**")

    if code:
        st.code(code, language=language)
    else:
        st.caption("No code provided by the workflow.")


# --------------------------------------------------
# TEST RESULT DISPLAY
# --------------------------------------------------

def _display_test_result(title: str, result: dict) -> None:

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
        st.info(f"Test status: {test_status}")

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


# --------------------------------------------------
# ERROR DISPLAY
# --------------------------------------------------

def _display_error(error):

    if isinstance(error, dict):

        st.error(
            error.get(
                "message",
                "The debugging workflow failed."
            )
        )

        details = error.get("details")

        if details:

            with st.expander("Error Details"):
                st.write(details)

    elif error:
        st.error(str(error))

    else:
        st.error("The debugging workflow failed.")


# --------------------------------------------------
# RESULTS DASHBOARD
# --------------------------------------------------

def render_results(task_id: str) -> dict | None:

    st.subheader("Debugging Results")

    # --------------------------------------------------
    # TASK ID
    # --------------------------------------------------

    if not task_id:

        task_id = st.session_state.get("task_id")

    if not task_id:

        st.info(
            "No debugging task selected. "
            "Please submit a GitHub issue first."
        )

        return None

    st.write(f"**Task ID:** `{task_id}`")

    # --------------------------------------------------
    # REFRESH CONTROL
    # --------------------------------------------------

    if st.button(
        "Refresh Results",
        key=f"refresh_results_{task_id}"
    ):
        st.rerun()

    # --------------------------------------------------
    # GET RESULTS DIRECTLY FROM PYTHON WORKFLOW
    # --------------------------------------------------

    try:

        results = get_task_results(task_id)

        if not isinstance(results, dict):

            st.error(
                "Invalid results response from Python workflow."
            )

            return None

        # --------------------------------------------------
        # HANDLE ERRORS
        # --------------------------------------------------

        error = results.get("error")

        if error:

            _display_error(error)
            return results

        # --------------------------------------------------
        # TASK STATUS
        # --------------------------------------------------

        status = results.get("status", "pending")

        st.divider()

        st.markdown("### Task Information")

        col1, col2 = st.columns(2)

        with col1:

            st.write("**Task ID**")
            st.code(results.get("task_id", task_id))

        with col2:

            st.write("**Status**")
            st.code(status)

        # --------------------------------------------------
        # RUNNING TASK
        # --------------------------------------------------

        if status in ("pending", "running"):

            st.info(
                results.get(
                    "message",
                    "Debugging is still running."
                )
            )

            st.caption(
                "Visit the Progress page to monitor workflow execution."
            )

            return results

        # --------------------------------------------------
        # FAILED TASK
        # --------------------------------------------------

        if status == "failed":

            st.error("The debugging workflow failed.")

            if results.get("message"):
                st.write(results["message"])

            _display_error(results.get("error"))

            return results

        # --------------------------------------------------
        # RESULTS AVAILABILITY
        # --------------------------------------------------

        if status not in ("awaiting_approval", "approved"):

            st.info(
                f"Results are not ready. Current status: {status}"
            )

            return results

        # --------------------------------------------------
        # IDENTIFIED BUG
        # --------------------------------------------------

        st.markdown("### Identified Bug")

        st.write(
            f"**Programming Language:** "
            f"{results.get('language') or 'Not available'}"
        )

        st.write(
            f"**Affected File:** "
            f"{results.get('bug_file') or 'Not available'}"
        )

        st.write(
            f"**Bug Location:** "
            f"{results.get('bug_location') or 'Not available'}"
        )

        st.write(
            f"**Explanation:** "
            f"{results.get('bug_explanation') or 'Not available'}"
        )

        language = results.get("language") or "text"

        # --------------------------------------------------
        # CODE COMPARISON
        # --------------------------------------------------

        st.markdown("### Code Comparison")

        col1, col2 = st.columns(2)

        with col1:

            _display_code(
                "Original Code",
                results.get("original_code") or "",
                language
            )

        with col2:

            _display_code(
                "Modified Code",
                results.get("modified_code") or "",
                language
            )

        # --------------------------------------------------
        # CODE DIFFERENCE
        # --------------------------------------------------

        st.markdown("### Code Difference")

        diff = results.get("diff")

        if diff:
            st.code(diff, language="diff")
        else:
            st.caption("No code difference available.")

        # --------------------------------------------------
        # FIX CHALLENGER REVIEW
        # --------------------------------------------------

        st.markdown("### Fix Challenger Review")

        challenger = results.get("challenger_review") or {}

        if isinstance(challenger, dict) and challenger:

            st.write(
                f"**Approved by Challenger:** "
                f"{challenger.get('approved')}"
            )

            st.write(
                f"**Risk Level:** "
                f"{challenger.get('risk_level', 'Not available')}"
            )

            st.write(
                f"**Summary:** "
                f"{challenger.get('summary', 'Not available')}"
            )

            findings = challenger.get("findings") or []

            if findings:

                st.write("**Findings:**")

                for finding in findings:
                    st.write(f"- {finding}")

            else:
                st.write("No findings reported.")

        else:

            st.caption(
                "Challenger review is not available."
            )

        # --------------------------------------------------
        # VERIFICATION RESULTS
        # --------------------------------------------------

        st.markdown("### Verification Results")

        verification = results.get("verification") or {}

        if isinstance(verification, dict) and verification:

            col1, col2 = st.columns(2)

            with col1:

                _display_test_result(
                    "Baseline Tests",
                    verification.get("baseline")
                )

            with col2:

                _display_test_result(
                    "Regression Tests",
                    verification.get("regression")
                )

            if "passed" in verification:

                st.write(
                    f"**Final Verification Passed:** "
                    f"{verification['passed']}"
                )

            if verification.get("summary"):

                st.info(verification["summary"])

        else:

            st.caption(
                "Verification results are not available."
            )

        # --------------------------------------------------
        # GITHUB PULL REQUEST
        # --------------------------------------------------

        pull_request_url = results.get("pull_request_url")

        if pull_request_url:

            st.markdown("### GitHub Pull Request")

            st.markdown(
                f"[Open Pull Request]({pull_request_url})"
            )

        # --------------------------------------------------
        # APPROVAL STATUS
        # --------------------------------------------------

        if status == "awaiting_approval":

            st.warning(
                "The proposed fix is waiting for your approval."
            )

        elif status == "approved":

            st.success(
                "The proposed fix has been approved."
            )

        return results

    except Exception as exc:

        st.error(
            f"Could not retrieve debugging results: {exc}"
        )

        return None
