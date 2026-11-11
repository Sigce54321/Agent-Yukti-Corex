
import json

from agents.issue_analyzer import analyze_issue
from agents.bug_locator import locate_bug
from agents.repair_agent import generate_repair
from agents.fix_challenger import challenge_fix


def run_repair_workflow(issue_text: str, repository_code: str) -> dict:
    """
    Run all four AI agents in sequence.

    This workflow proposes and reviews a patch.
    It does not modify repository files or execute tests.
    """

    if not issue_text or not issue_text.strip():
        raise ValueError("Issue description cannot be empty.")

    if not repository_code or not repository_code.strip():
        raise ValueError("Repository code cannot be empty.")

    # Agent 1: Analyze the issue
    issue_result = analyze_issue(issue_text)
    issue_data = json.dumps(issue_result.model_dump(), indent=2)

    # Agent 2: Locate the bug
    location_result = locate_bug(
        issue_analysis=issue_data,
        repository_code=repository_code,
    )
    location_data = json.dumps(location_result.model_dump(), indent=2)

    # Agent 3: Generate a repair proposal
    repair_result = generate_repair(
        issue_analysis=issue_data,
        bug_location=location_data,
        repository_code=repository_code,
    )
    repair_data = json.dumps(repair_result.model_dump(), indent=2)

    # Agent 4: Challenge and review the proposed repair
    challenge_result = challenge_fix(
        issue_analysis=issue_data,
        bug_location=location_data,
        repository_code=repository_code,
        proposed_patch=repair_result.patch,
    )

    return {
        "issue_analysis": issue_result.model_dump(),
        "bug_location": location_result.model_dump(),
        "repair_proposal": repair_result.model_dump(),
        "challenge_review": challenge_result.model_dump(),
        "status": (
            "READY_FOR_HUMAN_REVIEW"
            if challenge_result.verdict == "APPROVE"
            else "REPAIR_REJECTED"
        ),
    }
