
import json

from pydantic import BaseModel, Field, ValidationError

from utils.ai_client import generate_text
from agents.prompts import ISSUE_ANALYZER_PROMPT


class IssueAnalysis(BaseModel):
    problem_summary: str = Field(description="Short description of the bug")
    expected_behavior: str
    actual_behavior: str
    error_messages: list[str] = Field(default_factory=list)
    reproduction_steps: list[str] = Field(default_factory=list)
    suspected_files: list[str] = Field(default_factory=list)
    suspected_functions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


def analyze_issue(issue_text: str) -> IssueAnalysis:
    """
    Analyze a GitHub issue and return validated structured information.
    """

    if not issue_text or not issue_text.strip():
        raise ValueError("Issue description cannot be empty.")

    prompt = f"""
Analyze this GitHub issue.

Return ONLY valid JSON with these exact fields:
{{
    "problem_summary": "string",
    "expected_behavior": "string",
    "actual_behavior": "string",
    "error_messages": ["string"],
    "reproduction_steps": ["string"],
    "suspected_files": ["string"],
    "suspected_functions": ["string"],
    "missing_information": ["string"]
}}

If information is unavailable, use "Not provided" for string fields
and an empty list for list fields.

GITHUB ISSUE:
{issue_text}
"""

    response = generate_text(
        prompt=prompt,
        system_instruction=ISSUE_ANALYZER_PROMPT,
        temperature=0.1,
    )

    # Remove Markdown code fences if the model adds them.
    cleaned_response = response.strip()

    if cleaned_response.startswith("```"):
        cleaned_response = cleaned_response.split("\n", 1)[1]
        cleaned_response = cleaned_response.rsplit("```", 1)[0].strip()

    try:
        data = json.loads(cleaned_response)
        return IssueAnalysis.model_validate(data)

    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(
            f"Issue Analyzer returned invalid structured output: {exc}"
        ) from exc
def analyze_issue_for_backend(issue, repository_summary):
    """
    Compatibility adapter for the main backend workflow.
    """

    issue_text = f"""
    TITLE: {issue.get('title', '')}

    DESCRIPTION: {issue.get('body', '')}

    REPOSITORY SUMMARY:
    {repository_summary}
    """

    result = analyze_issue(issue_text)

    return result.model_dump()