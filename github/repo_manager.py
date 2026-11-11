
"""
YuktiC-oreX - GitHub Repository Manager

Responsibilities:
- Validate repository URLs.
- Clone repositories.
- Record original commit SHA and default branch.
- Create isolated Git worktree for repairs.
- Commit and push verified changes to a repair branch.

Public functions:
    clone_repository(repo_url, task_id)
    create_working_copy(repository_path, task_id)
    commit_and_push(workspace_path, task_id, commit_message)

Requires:
    Git CLI installed and available in PATH.
    GITHUB_TOKEN environment variable for private repositories
    and pushing to GitHub.
"""

import base64
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import requests


GITHUB_API = "https://api.github.com"
REQUEST_TIMEOUT = 30

# Keep generated repositories outside the source-code folders.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACES_ROOT = PROJECT_ROOT / "workspaces"


class RepositoryError(Exception):
    """Raised when a repository operation fails."""


def _error(code, message, details, stage):
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": str(details),
            "stage": stage,
        },
    }


def _validate_task_id(task_id):
    if not isinstance(task_id, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,80}", task_id
    ):
        raise ValueError("Invalid task_id.")

    return task_id


def _parse_repo_url(repo_url):
    if not isinstance(repo_url, str) or not repo_url.strip():
        raise ValueError("repo_url is required.")

    parsed = urlparse(repo_url.strip())

    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise ValueError("Only HTTPS GitHub repository URLs are supported.")

    parts = [part for part in parsed.path.strip("/").split("/") if part]

    if len(parts) != 2:
        raise ValueError("Expected URL format: https://github.com/owner/repo")

    owner, repo = parts
    repo = re.sub(r"\.git$", "", repo)

    pattern = r"^[A-Za-z0-9_.-]+$"

    if not re.fullmatch(pattern, owner) or not re.fullmatch(pattern, repo):
        raise ValueError("Invalid GitHub repository owner or name.")

    if owner in {".", ".."} or repo in {".", ".."}:
        raise ValueError("Invalid repository path.")

    return owner, repo, f"https://github.com/{owner}/{repo}.git"


def _api_headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "YuktiC-oreX",
    }

    token = os.getenv("GITHUB_TOKEN")

    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers


def _run_git(args, cwd=None, timeout=120, token=None):
    """
    Run Git without placing credentials in the repository's
    persistent remote URL or Git configuration.
    """

    command = ["git"]

    if token:
        credential = base64.b64encode(
            f"x-access-token:{token}".encode("utf-8")
        ).decode("ascii")

        command.extend([
            "-c",
            f"http.extraheader=AUTHORIZATION: basic {credential}",
        ])

    command.extend(args)

    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )

    if result.returncode != 0:
        # Never return the credential-bearing command.
        raise RepositoryError(
            result.stderr.strip() or "Git command failed."
        )

    return result.stdout.strip()


def _get_repository_metadata(owner, repo):
    url = f"{GITHUB_API}/repos/{owner}/{repo}"

    response = requests.get(
        url,
        headers=_api_headers(),
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code == 404:
        raise RepositoryError(
            "Repository not found or access is not permitted."
        )

    if response.status_code in (401, 403):
        raise RepositoryError(
            f"GitHub access denied: HTTP {response.status_code}."
        )

    response.raise_for_status()

    data = response.json()

    default_branch = data.get("default_branch")

    if not default_branch:
        raise RepositoryError("GitHub did not provide a default branch.")

    return {
        "default_branch": default_branch,
        "full_name": data.get("full_name"),
        "private": data.get("private", False),
        "html_url": data.get("html_url"),
    }


def clone_repository(repo_url: str, task_id: str) -> dict:
    """
    Clone a GitHub repository into a task-specific source folder.

    Returns:
        {
            "success": True,
            "repository_path": str,
            "default_branch": str,
            "original_commit_sha": str,
            "repository": str
        }
    """

    try:
        task_id = _validate_task_id(task_id)
        owner, repo, clone_url = _parse_repo_url(repo_url)

        metadata = _get_repository_metadata(owner, repo)

        task_root = WORKSPACES_ROOT / task_id
        source_path = task_root / "source"

        task_root.mkdir(parents=True, exist_ok=True)

        if source_path.exists():
            raise RepositoryError(
                "Source directory already exists for this task."
            )

        token = os.getenv("GITHUB_TOKEN")

        _run_git(
            [
                "clone",
                "--",
                clone_url,
                str(source_path),
            ],
            timeout=180,
            token=token,
        )

        original_commit_sha = _run_git(
            ["rev-parse", "HEAD"],
            cwd=source_path,
        )

        cloned_branch = _run_git(
            ["branch", "--show-current"],
            cwd=source_path,
        )

        if cloned_branch != metadata["default_branch"]:
            _run_git(
                ["checkout", metadata["default_branch"]],
                cwd=source_path,
            )

            original_commit_sha = _run_git(
                ["rev-parse", "HEAD"],
                cwd=source_path,
            )

        return {
            "success": True,
            "repository_path": str(source_path.resolve()),
            "default_branch": metadata["default_branch"],
            "original_commit_sha": original_commit_sha,
            "repository": metadata["full_name"],
        }

    except ValueError as exc:
        return _error(
            "INVALID_INPUT",
            "Invalid repository clone request.",
            exc,
            "cloning_repository",
        )

    except requests.RequestException as exc:
        return _error(
            "GITHUB_CONNECTION_FAILED",
            "Could not retrieve repository information.",
            exc,
            "cloning_repository",
        )

    except (RepositoryError, OSError, subprocess.TimeoutExpired) as exc:
        return _error(
            "REPOSITORY_CLONE_FAILED",
            "Repository could not be cloned.",
            exc,
            "cloning_repository",
        )


def create_working_copy(
    repository_path: str,
    task_id: str
) -> dict:
    """
    Create a separate Git worktree and repair branch.

    The original cloned repository remains unchanged.

    Returns:
        {
            "success": True,
            "workspace_path": str,
            "source_branch": str,
            "base_commit_sha": str
        }
    """

    try:
        task_id = _validate_task_id(task_id)

        if not isinstance(repository_path, str) or not repository_path.strip():
            raise ValueError("repository_path is required.")

        source_path = Path(repository_path).resolve(strict=True)

        if not source_path.is_dir():
            raise ValueError("repository_path must be a directory.")

        # Confirm this is a Git repository.
        _run_git(
            ["rev-parse", "--show-toplevel"],
            cwd=source_path,
        )

        base_commit_sha = _run_git(
            ["rev-parse", "HEAD"],
            cwd=source_path,
        )

        source_branch = f"yukticorex/repair-{task_id}"
        workspace_path = WORKSPACES_ROOT / task_id / "repair"

        if workspace_path.exists():
            raise RepositoryError(
                "Repair workspace already exists for this task."
            )

        workspace_path.parent.mkdir(parents=True, exist_ok=True)

        _run_git(
            [
                "worktree",
                "add",
                "-b",
                source_branch,
                str(workspace_path),
                base_commit_sha,
            ],
            cwd=source_path,
        )

        return {
            "success": True,
            "workspace_path": str(workspace_path.resolve()),
            "source_branch": source_branch,
            "base_commit_sha": base_commit_sha,
        }

    except ValueError as exc:
        return _error(
            "INVALID_INPUT",
            "Invalid working-copy request.",
            exc,
            "cloning_repository",
        )

    except (RepositoryError, OSError, subprocess.TimeoutExpired) as exc:
        return _error(
            "REPOSITORY_CLONE_FAILED",
            "Separate repair workspace could not be created.",
            exc,
            "cloning_repository",
        )


def commit_and_push(
    workspace_path: str,
    task_id: str,
    commit_message: str = "Fix: automated repair by YuktiC-oreX",
) -> dict:
    """
    Commit changes in the repair worktree and push its branch.

    This must only be called after successful verification
    and explicit user approval.

    Returns:
        {
            "success": True,
            "source_branch": str,
            "commit_sha": str,
            "message": str
        }
    """

    try:
        task_id = _validate_task_id(task_id)

        if not isinstance(workspace_path, str) or not workspace_path.strip():
            raise ValueError("workspace_path is required.")

        if (
            not isinstance(commit_message, str)
            or not commit_message.strip()
        ):
            raise ValueError("commit_message is required.")

        workspace = Path(workspace_path).resolve(strict=True)

        if not workspace.is_dir():
            raise ValueError("workspace_path must be a directory.")

        branch = _run_git(
            ["branch", "--show-current"],
            cwd=workspace,
        )

        expected_branch = f"yukticorex/repair-{task_id}"

        if branch != expected_branch:
            raise RepositoryError(
                f"Unexpected repair branch: {branch}"
            )

        status = _run_git(
            ["status", "--porcelain"],
            cwd=workspace,
        )

        if not status:
            raise RepositoryError("No changes are available to commit.")

        # Stage changes from the repair workspace only.
        _run_git(
            ["add", "-A"],
            cwd=workspace,
        )

        _run_git(
            [
                "-c", "user.name=YuktiC-oreX",
                "-c", "user.email=yukticorex[bot]@users.noreply.github.com",
                "commit",
                "-m",
                commit_message,
            ],
            cwd=workspace,
        )

        commit_sha = _run_git(
            ["rev-parse", "HEAD"],
            cwd=workspace,
        )

        token = os.getenv("GITHUB_TOKEN")

        if not token:
            raise RepositoryError(
                "GITHUB_TOKEN is required to push the repair branch."
            )

        _run_git(
            [
                "push",
                "origin",
                f"HEAD:refs/heads/{expected_branch}",
            ],
            cwd=workspace,
            timeout=120,
            token=token,
        )

        return {
            "success": True,
            "source_branch": expected_branch,
            "commit_sha": commit_sha,
            "message": "Verified repair branch pushed successfully.",
        }

    except ValueError as exc:
        return _error(
            "INVALID_INPUT",
            "Invalid commit and push request.",
            exc,
            "creating_pull_request",
        )

    except (RepositoryError, OSError, subprocess.TimeoutExpired) as exc:
        return _error(
            "GITHUB_PUSH_FAILED",
            "Repair branch could not be committed or pushed.",
            exc,
            "creating_pull_request",
        )
