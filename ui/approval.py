
import os
import requests
import streamlit as st


API_BASE_URL = os.getenv(
    "YUKTICOREX_API_URL",
    "http://127.0.0.1:8000"
).rstrip("/")


def _get_error_message(response):
    """Extract a readable backend error message."""

    try:
        data = response.json()
        error = data.get("error")

        if isinstance(error, dict):
            return error.get("message", response.text)

        if error:
            return str(error)

        return data.get("message", response.text)

    except (ValueError, AttributeError):
        return response.text or "Backend request failed."


def show_approval(task_id: str | None = None) -> dict | None:
    """
    Display proposed fix and handle user approval or rejection.

    Args:
        task_id: Unique debugging task ID.

    Returns:
        dict: Backend response.
        None: If task or results are unavailable.
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

    # Fetch latest debugging results.
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/results/{task_id}",
            timeout=30
        )

        if response.status_code != 200:
            st.error(_get_error_message(response))
            return None

        results = response.json()

    except requests.RequestException as exc:
        st.error(f"Backend connection failed: {exc}")
        return None

    except ValueError:
        st.error("Backend returned an invalid JSON response.")
        return None

    if not isinstance(results, dict):
        st.error("Invalid results response from backend.")
        return None

    # Task details
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

    # Bug information
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

    # Modified code
    st.markdown("### Modified Code")

    modified_code = results.get("modified_code", "")

    if modified_code:
        st.code(
            modified_code,
            language=results.get("language") or "text"
        )
    else:
        st.caption("Modified code is not available.")

    # Code difference
    st.markdown("### Code Difference")

    diff = results.get("diff")

    if diff:
        st.code(diff, language="diff")
    else:
        st.caption("Code difference is not available.")

    # Challenger review
    st.markdown("### Fix Challenger Review")

    challenger = results.get("challenger_review", {})

    if isinstance(challenger, dict) and challenger:

        st.write(
            "**Challenger Approved:**",
            challenger.get("approved")
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

    # Verification
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
                        "test_status", "not_run"
                    )

                    if test_status == "passed":
                        st.success("Tests passed")

                    elif test_status == "failed":
                        st.error("Tests failed")

                    elif test_status == "error":
                        st.error("Test execution error")

                    else:
                        st.info("Tests not run")

                    st.write("Passed:", test_result.get("passed"))
                    st.write("Exit Code:", test_result.get("exit_code"))

                    if test_result.get("logs"):
                        st.code(test_result["logs"])

    st.divider()

    # Approval options
    st.markdown("### Your Decision")

    create_pull_request = st.checkbox(
        "Create GitHub Pull Request after approval",
        value=True
    )

    approve_clicked = st.button(
        "Approve Fix",
        type="primary",
        use_container_width=True,
        key=f"approve_{task_id}"
    )

    if approve_clicked:

        try:
            approval_response = requests.post(
                f"{API_BASE_URL}/api/approve",
                json={
                    "task_id": task_id,
                    "create_pull_request": create_pull_request
                },
                timeout=60
            )

            if approval_response.status_code in (200, 202):

                try:
                    action_data = approval_response.json()
                except ValueError:
                    st.error("Invalid approval response from backend.")
                    return results

                st.session_state[action_key] = action_data
                st.rerun()

            else:
                st.error(
                    "Approval failed: "
                    + _get_error_message(approval_response)
                )

        except requests.RequestException as exc:
            st.error(f"Approval request failed: {exc}")

    # Rejection form
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
                reject_response = requests.post(
                    f"{API_BASE_URL}/api/reject",
                    json={
                        "task_id": task_id,
                        "reason": reason.strip() or None
                    },
                    timeout=30
                )

                if reject_response.status_code in (200, 202):

                    try:
                        action_data = reject_response.json()
                    except ValueError:
                        st.error("Invalid rejection response from backend.")
                        return results

                    st.session_state[action_key] = action_data
                    st.rerun()

                else:
                    st.error(
                        "Rejection failed: "
                        + _get_error_message(reject_response)
                    )

            except requests.RequestException as exc:
                st.error(f"Rejection request failed: {exc}")

    return results
