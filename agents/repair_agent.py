
import json

from pydantic import BaseModel, Field, ValidationError

from utils.ai_client import generate_text
from agents.prompts import REPAIR_AGENT_PROMPT


class RepairProposal(BaseModel):
    root_cause: str
    explanation: str
    patch: str
    changed_files: list[str] = Field(default_factory=list)
    potential_risks: list[str] = Field(default_factory=list)


def generate_repair(
    issue_analysis: str,
    bug_location: str,
    repository_code: str,
) -> RepairProposal:
    """
    Generate a proposed unified diff patch.
    Does not modify repository files.
    """

    if not issue_analysis.strip():
        raise ValueError("Issue analysis cannot be empty.")

    if not bug_location.strip():
        raise ValueError("Bug location cannot be empty.")

    if not repository_code.strip():
        raise ValueError("Repository code cannot be empty.")

    prompt = f"""
Analyze the reported bug and propose a minimal code repair.

Return ONLY valid JSON with these exact fields:
{{
    "root_cause": "string",
    "explanation": "string",
    "patch": "unified diff patch as a string",
    "changed_files": ["string"],
    "potential_risks": ["string"]
}}

IMPORTANT:
- Use only the supplied repository code.
- Generate a unified diff patch.
- Do not claim that the patch has been applied or tested.
- Do not modify unrelated code.
- If a safe patch cannot be generated, explain why.
- Do not invent file paths.

ISSUE ANALYSIS:
{issue_analysis}

BUG LOCATION:
{bug_location}

REPOSITORY CODE:
{repository_code}
"""

    response = generate_text(
        prompt=prompt,
        system_instruction=REPAIR_AGENT_PROMPT,
        temperature=0.1,
    )

    cleaned_response = response.strip()

    if cleaned_response.startswith("```"):
        cleaned_response = cleaned_response.split("\n", 1)[1]
        cleaned_response = cleaned_response.rsplit("```", 1)[0].strip()

    try:
        data = json.loads(cleaned_response)
        return RepairProposal.model_validate(data)

    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(
            f"Repair Agent returned invalid structured output: {exc}"
        ) from exc

def propose_fix_for_backend(bug_location, issue_analysis, repository_data):
    """
    Generate a complete repaired file for the backend workflow.

    original_code: buggy code fragment identified by Bug Locator.
    repository_code: complete original target file.
    modified_code: complete repaired target file.
    """

    file_path = bug_location["file_path"]
    original_code = bug_location["original_code"]

    files = repository_data.get("files", [])

    target_file = next(
        (item for item in files if item["file_path"] == file_path),
        None
    )

    if target_file is None:
        raise ValueError(f"Target file not found: {file_path}")

    repository_code = target_file["content"]

    if original_code not in repository_code:
        raise ValueError("Original code does not match repository content.")

    prompt = f"""
Repair the identified bug with the smallest safe change.

Return ONLY valid JSON:
{{
    "modified_code": "complete updated file content"
}}

IMPORTANT:
- modified_code MUST contain the ENTIRE updated file.
- Do not return only the replacement fragment.
- Preserve all unrelated functions, classes, imports and comments.
- Change only what is necessary to fix the reported issue.
- Do not return a unified diff.
- Do not change the file path.
- Do not claim the code has been tested.

ISSUE ANALYSIS:
{json.dumps(issue_analysis, indent=2)}

BUG LOCATION:
{json.dumps(bug_location, indent=2)}

TARGET FILE:
{file_path}

ORIGINAL BUGGY CODE:
{original_code}

COMPLETE ORIGINAL FILE:
{repository_code}
"""

    response = generate_text(
        prompt=prompt,
        system_instruction=(
            "You are a careful software repair engineer. "
            "Return valid JSON containing the complete repaired file."
        ),
        temperature=0.1,
    )

    cleaned = response.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Repair Agent returned invalid JSON: {exc}"
        ) from exc

    modified_code = data.get("modified_code")

    if not isinstance(modified_code, str) or not modified_code.strip():
        raise ValueError("Repair Agent returned an empty modification.")

    return {
        "file_path": file_path,
        "original_code": original_code,
        "repository_code": repository_code,
        "modified_code": modified_code
    }
