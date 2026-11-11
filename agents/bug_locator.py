
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
{json.dumps(issue_analysis, indent=2) if isinstance(issue_analysis, dict) else issue_analysis}

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
def locate_bug_for_backend(issue_analysis, repository_data, language):
    """
    Adapter for the main backend workflow.
    Returns the structure expected by core.workflow.
    """

    files = repository_data.get("files", [])

    repository_code = "\n\n".join(
        f"FILE: {item['file_path']}\n{item['content']}"
        for item in files
    )

    if not repository_code.strip():
        raise ValueError("Repository contains no readable source code.")

    prompt = f"""
Identify the exact bug in the supplied repository.

Return ONLY valid JSON:
{{
    "found": true,
    "file_path": "exact relative file path",
    "function_name": "function name",
    "original_code": "exact existing code block",
    "reason": "why this code causes the reported bug"
}}

If no bug can be identified, return found=false and explain why.

LANGUAGE:
{language}

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

    cleaned = response.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()

    data = json.loads(cleaned)

    required = ["found", "file_path", "function_name", "original_code", "reason"]

    if not all(field in data for field in required):
        raise ValueError("Bug Locator returned incomplete backend data.")

    return data