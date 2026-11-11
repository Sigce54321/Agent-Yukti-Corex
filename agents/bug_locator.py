
import json

from pydantic import BaseModel, Field, ValidationError

from utils.ai_client import generate_text
from agents.prompts import BUG_LOCATOR_PROMPT


class BugLocation(BaseModel):
    suspected_files: list[str] = Field(default_factory=list)
    relevant_functions: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    defect_explanation: str
    confidence: str


def locate_bug(issue_analysis: str, repository_code: str) -> BugLocation:
    """
    Identify likely bug locations using issue details and supplied code.
    """

    if not issue_analysis.strip():
        raise ValueError("Issue analysis cannot be empty.")

    if not repository_code.strip():
        raise ValueError("Repository code cannot be empty.")

    prompt = f"""
Analyze the issue and repository code.

Return ONLY valid JSON with these exact fields:
{{
    "suspected_files": ["string"],
    "relevant_functions": ["string"],
    "evidence": ["string"],
    "defect_explanation": "string",
    "confidence": "High, Medium, or Low"
}}

Use only the supplied information. Do not invent file paths,
functions, or code.

ISSUE ANALYSIS:
{issue_analysis}

REPOSITORY CODE:
{repository_code}
"""

    response = generate_text(
        prompt=prompt,
        system_instruction=BUG_LOCATOR_PROMPT,
        temperature=0.1,
    )

    cleaned_response = response.strip()

    if cleaned_response.startswith("```"):
        cleaned_response = cleaned_response.split("\n", 1)[1]
        cleaned_response = cleaned_response.rsplit("```", 1)[0].strip()

    try:
        data = json.loads(cleaned_response)
        return BugLocation.model_validate(data)

    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(
            f"Bug Locator returned invalid structured output: {exc}"
        ) from exc
