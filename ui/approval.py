
import streamlit as st
from ui import backend
from ui.visuals import row, patch_counts


def _decision_summary(results):
    challenger = results.get("challenger_review") or {}
    regression = (results.get("verification") or {}).get("regression") or {}
    counts = patch_counts(results.get("diff"))
    changes = f"+{counts[0]} / -{counts[1]}" if counts is not None else "Unavailable"
    st.markdown('<div class="decision-summary" style="display:grid !important;grid-template-columns:repeat(2,minmax(0,1fr)) !important;gap:14px !important;">' + row("Patch status", results.get("status", "No patch").replace("_", " ").title()) + row("Net change", changes) + row("Test result", regression.get("test_status", "Not run")) + row("Challenger", challenger.get("verdict", "Pending")) + '</div>', unsafe_allow_html=True)


def show_approval(task_id: str | None = None, *, compact: bool = False) -> dict | None:
    """
    Display proposed fix and handle user approval or rejection.

    Args:
        task_id: Unique debugging task ID.

    Returns:
        dict: Backend response.
        None: If task or results are unavailable.
    """

    st.subheader("Approval Decision" if compact else "Fix Approval")

    if not task_id:
        task_id = st.session_state.get("task_id")

    if not task_id:
        if compact:
            _decision_summary({})
        st.info("Submit an issue to begin. Approval becomes available after workflow verification.")
        return None

    # Display the result of the previous approval/rejection action.
    previous_action = backend.decision_status(st.session_state, task_id)

    if isinstance(previous_action, dict):
        if previous_action.get("error") or previous_action.get("status") == "failed":
            st.error(backend.error_message(previous_action))
        elif previous_action.get("status") == "running":
            st.info(previous_action["message"])
            st.button("Refresh decision", key=f"refresh_decision_{task_id}")
        else:
            st.success(previous_action.get("message", "Your decision was submitted."))

        previous_pr_url = previous_action.get("pull_request_url")

        if previous_pr_url:
            st.markdown(
                f"[Open GitHub Pull Request]({previous_pr_url})"
            )

    # Fetch latest debugging results.
    try:
        results = backend.get_task_results(task_id)
    except backend.BackendError as exc:
        st.error(str(exc))
        return None

    if not isinstance(results, dict):
        st.error("Invalid results response from backend.")
        return None

    if results.get("error"):
        st.error(backend.error_message(results))
        return results
    if previous_action is not None:
        # A stale backend read must never re-enable a decision already sent.
        results = {**results, **previous_action}
    st.session_state["task_status"] = results.get("status", "pending")
    if results.get("message"):
        st.session_state["task_message"] = results["message"]

    # Task details
    status = results.get("status", "pending")

    if compact:
        _decision_summary(results)
    else:
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

    if not compact:
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
                "**Verdict:**",
                challenger.get("verdict") or "Not available"
            )

            st.write(
                "**Explanation:**",
                challenger.get("explanation") or "Not available"
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
                    else:
                        st.caption("Test result is not available.")

        st.divider()

    # Approval options
    st.markdown("### Your Decision")

    create_pull_request = st.checkbox(
        "Create GitHub Pull Request after approval",
        value=False,
        key=f"create_pr_{task_id}"
    )

    st.caption("Approve only after reviewing the patch, Challenger review and Docker evidence. PR creation requires selecting the option above.")

    approve_clicked = st.button(
        "Approve Fix",
        type="primary",
        use_container_width=True,
        key=f"approve_{task_id}"
    )

    if approve_clicked:

        try:
            action_data = backend.submit_decision(
                st.session_state, task_id, "approve",
                create_pull_request=create_pull_request,
            )
        except backend.BackendError as exc:
            st.error(str(exc))
            return results
        st.session_state["task_status"] = action_data.get("status", "running")
        st.rerun()
        return action_data

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
                action_data = backend.submit_decision(
                    st.session_state, task_id, "reject", reason=reason.strip() or None,
                )
            except backend.BackendError as exc:
                st.error(str(exc))
                return results
            st.session_state["task_status"] = action_data.get("status", "running")
            st.rerun()
            return action_data

    return results
