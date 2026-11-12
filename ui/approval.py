
import streamlit as st

from core.workflow import (
    get_task_results,
    approve_fix,
    reject_fix,
)


def _get_error_message(response):
    """Extract a readable error message from a workflow response."""

    if not isinstance(response, dict):
        return "Invalid response from the Python backend."

    error = response.get("error")

    if isinstance(error, dict):
        return error.get("message", "An operation failed.")

    if error:
        return str(error)

    return response.get("message", "An operation failed.")


def _is_error_response(response):
    """Check whether a workflow operation returned an error."""

    if not isinstance(response, dict):
        return True

    return (
        response.get("success") is False
        or response.get("status") == "failed"
        or bool(response.get("error"))
    )


def show_approval(task_id: str | None = None) -> dict | None:
    """
    Display proposed fix and handle user approval or rejection.

    Uses direct Python function calls.
    No separate API server is required.
    """

    st.subheader("Fix Approval")

    if not task_id:
        task_id = st.session_state.get("task_id")

    if not task_id:
        st.info("Please start a debugging task first.")
        return None

    # Display the result of the previous approval/rejection action.
    action_key = f"approval_response_{task_id}"
    previous_action = st.session_state.pop(action_key, None)

    if isinstance(previous_action, dict):

        if _is_error_response(previous_action):
            st.error(_get_error_message(previous_action))
        else:
            st.success(
                previous_action.get(
                    "message",
                    "Your decision was submitted."
                )
            )

            previous_pr_url = previous_action.get("pull_request_url")

            if previous_pr_url:
                st.markdown(
                    f"[Open GitHub Pull Request]({previous_pr_url})"
                )

    # Fetch latest debugging results directly.
    try:
        results = get_task_results(task_id)

    except Exception as exc:
        st.error(f"Unable to fetch debugging results: {exc}")
        return None

    if not isinstance(results, dict):
        st.error("Invalid results response from the Python backend.")
        return None

    if _is_error_response(results):
        st.error(_get_error_message(results))
        return results

    # Task details.
    status = results.get("status", "pending")

    st.write(f"**Task ID:** `{task_id}`")
    st.write(f"**Current Status:** `{status}`")

    st.divider()

    # Only awaiting_approval tasks can be approved or rejected.
    if status != "awaiting_approval":

        if status == "approved":
            st.success("This fix has already been approved.")

        elif status == "rejected":
            st.warning("This proposed fix has been rejected.")

        elif status == "failed":
            st.error("The debugging task failed.")

        else:
            st.info(
                "Approval is available only when task status "
                "is awaiting_approval."
            )

        pull_request_url = results.get("pull_request_url")

        if pull_request_url:
            st.markdown(
                f"[Open GitHub Pull Request]({pull_request_url})"
            )

        return results

    # Bug information.
    st.markdown("### Proposed Fix")

    st.write(
        "**Programming Language:**",
        results.get("language", "Not available")
    )

    st.write(
        "**Affected File:**",
        results.get("bug_file", "Not available")
    )

    st.write(
        "**Bug Location:**",
        results.get("bug_location", "Not available")
    )

    st.write(
        "**Explanation:**",
        results.get("bug_explanation", "Not available")
    )

    # Modified code.
    st.markdown("### Modified Code")

    modified_code = results.get("modified_code", "")

    if modified_code:
        st.code(
            modified_code,
            language=results.get("language") or "text"
        )
    else:
        st.caption("Modified code is not available.")

    # Code difference.
    st.markdown("### Code Difference")

    diff = results.get("diff")

    if diff:
        st.code(diff, language="diff")
    else:
        st.caption("Code difference is not available.")

    # Challenger review.
    st.markdown("### Fix Challenger Review")

    challenger = results.get("challenger_review", {})

    if isinstance(challenger, dict) and challenger:

        st.write(
            "**Challenger Approved:**",
            challenger.get("approved", "Not available")
        )

        st.write(
            "**Risk Level:**",
            challenger.get("risk_level", "Not available")
        )

        st.write(
            "**Summary:**",
            challenger.get("summary", "Not available")
        )

        findings = challenger.get("findings", [])

        if findings:
            st.write("**Findings:**")

            for finding in findings:
                st.write(f"- {finding}")

    else:
        st.caption("Challenger review is not available.")

    # Verification results.
    st.markdown("### Verification Results")

    verification = results.get("verification", {})

    if isinstance(verification, dict):

        for key, title in [
            ("baseline", "Baseline Testing"),
            ("regression", "Regression Testing")
        ]:

            test_result = verification.get(key, {})

            with st.expander(title):

                if isinstance(test_result, dict):

                    test_status = test_result.get(
                        "test_status",
                        "not_run"
                    )

                    if test_status == "passed":
                        st.success("Tests passed")

                    elif test_status == "failed":
                        st.error("Tests failed")

                    elif test_status == "error":
                        st.error("Test execution error")

                    else:
                        st.info("Tests not run")

                    st.write(
                        "Passed:",
                        test_result.get("passed")
                    )

                    st.write(
                        "Exit Code:",
                        test_result.get("exit_code")
                    )

                    if test_result.get("logs"):
                        st.code(test_result["logs"])

                else:
                    st.caption("Test results are not available.")

    st.divider()

    # Approval options.
    st.markdown("### Your Decision")

    create_pull_request = st.checkbox(
        "Create GitHub Pull Request after approval",
        value=True,
        key=f"create_pr_{task_id}"
    )

    approve_clicked = st.button(
        "Approve Fix",
        type="primary",
        use_container_width=True,
        key=f"approve_{task_id}"
    )

    if approve_clicked:

        try:
            with st.spinner("Approving fix..."):

                approval_response = approve_fix(
                    task_id,
                    create_pull_request=create_pull_request
                )

            if not isinstance(approval_response, dict):
                st.error("Invalid approval response.")
                return results

            if _is_error_response(approval_response):
                st.error(_get_error_message(approval_response))

            else:
                st.session_state[action_key] = approval_response
                st.rerun()

        except Exception as exc:
            st.error(f"Approval failed: {exc}")

    # Rejection form.
    with st.form(key=f"reject_form_{task_id}"):

        st.markdown("### Reject Proposed Fix")

        reason = st.text_area(
            "Reason for rejection",
            placeholder="Explain why the proposed fix is rejected."
        )

        reject_clicked = st.form_submit_button(
            "Reject Fix"
        )

        if reject_clicked:

            try:
                with st.spinner("Rejecting proposed fix..."):

                    rejection_response = reject_fix(
                        task_id,
                        reason.strip() or None
                    )

                if not isinstance(rejection_response, dict):
                    st.error("Invalid rejection response.")

                elif _is_error_response(rejection_response):
                    st.error(_get_error_message(rejection_response))

                else:
                    st.session_state[action_key] = rejection_response
                    st.rerun()

            except Exception as exc:
                st.error(f"Rejection failed: {exc}")

    return results
