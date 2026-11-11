
import json
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from utils.ai_client import generate_text
from agents.prompts import FIX_CHALLENGER_PROMPT


class ChallengeReview(BaseModel):
    verdict: Literal["APPROVE", "REJECT"]
    findings: list[str] = Field(default_factory=list)
    potential_regressions: list[str] = Field(default_factory=list)
    required_corrections: list[str] = Field(default_factory=list)
    explanation: str


def challenge_fix(
    issue_analysis: str,
    bug_location: str,
    repository_code: str,
    proposed_patch: str,
) -> ChallengeReview:
    """
    Independently review a proposed patch.
    Does not apply or execute the patch.
    """

    inputs = {
        "issue analysis": issue_analysis,
        "bug location": bug_location,
        "repository code": repository_code,
        "proposed patch": proposed_patch,
    }

    for name, value in inputs.items():
        if not value or not value.strip():
            raise ValueError(f"{name.capitalize()} cannot be empty.")

    prompt = f"""
Independently review the proposed code patch.

Return ONLY valid JSON with these exact fields:
{{
    "verdict": "APPROVE or REJECT",
    "findings": ["string"],
    "potential_regressions": ["string"],
    "required_corrections": ["string"],
    "explanation": "string"
}}

Review the patch critically:
- Does it solve the reported issue?
- Is it consistent with the supplied code?
- Could it introduce regressions?
- Are edge cases handled?
- Is it minimal?

Do not claim that tests were executed.
Do not approve without sufficient evidence.

ISSUE ANALYSIS:
{issue_analysis}

BUG LOCATION:
{bug_location}

ORIGINAL REPOSITORY CODE:
{repository_code}

PROPOSED PATCH:
{proposed_patch}
"""

    response = generate_text(
        prompt=prompt,
        system_instruction=FIX_CHALLENGER_PROMPT,
        temperature=0.1,
    )

    cleaned_response = response.strip()

    if cleaned_response.startswith("```"):
        cleaned_response = cleaned_response.split("\n", 1)[1]
        cleaned_response = cleaned_response.rsplit("```", 1)[0].strip()

    try:
        data = json.loads(cleaned_response)
        return ChallengeReview.model_validate(data)

    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(
            f"Fix Challenger returned invalid structured output: {exc}"
        ) from exc
