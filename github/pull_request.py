
"""
YuktiC-oreX - GitHub Pull Request Manager

Creates a Pull Request using GitHub REST API.

Public function:
    create_pull_request(
        repo_url,
        source_branch,
        target_branch,
        title,
        body
    )

Important:
- Source branch must already be pushed.
- Fix must have passed verification.
- User approval must happen before this function is called.
- This module never merges a Pull Request.
"""

import os
import re
from urllib.parse import urlparse

import requests


GITHUB_API = "https://api.github.com"
REQUEST_TIMEOUT = 30


def _error(code, message, details):
    return {
        "created": False,
        "error": {
            "code": code,
            "message": message,
            "details": str(details),
            "stage": "creating_pull_request",
        },
    }


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

    return owner, repo


def _validate_branch(branch, field_name):
    if not isinstance(branch, str) or not branch.strip():
        raise ValueError(f"{field_name} is required.")

    if (
        branch.startswith("-")
        or branch.startswith("/")
        or branch.endswith("/")
        or ".." in branch
        or "//" in branch
        or " " in branch
        or branch.endswith(".")
        or "@{" in branch
        or any(char in branch for char in ("~", "^", ":", "?", "*", "[", "\\"))
        or any(ord(char) < 32 for char in branch)
    ):
        raise ValueError(f"Invalid {field_name}.")

    if branch.endswith(".lock"):
        raise ValueError(f"Invalid {field_name}.")

    return branch


def _headers():
    token = os.getenv("GITHUB_TOKEN")

    if not token:
        raise ValueError(
            "GITHUB_TOKEN is required to create a Pull Request."
        )

    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "YuktiC-oreX",
    }


def create_pull_request(
    repo_url: str,
    source_branch: str,
    target_branch: str,
    title: str,
    body: str,
) -> dict:
    """
    Create a Pull Request from an existing pushed branch.

    Args:
        repo_url: GitHub repository HTTPS URL.
        source_branch: Pushed repair branch.
        target_branch: Repository default/base branch.
        title: Pull Request title.
        body: Pull Request description.

    Success response:
        {
            "created": True,
            "pull_request_number": int,
            "pull_request_url": str,
            "source_branch": str,
            "target_branch": str,
            "state": str
        }
    """

    try:
        owner, repo = _parse_repo_url(repo_url)

        source_branch = _validate_branch(
            source_branch, "source_branch"
        )

        target_branch = _validate_branch(
            target_branch, "target_branch"
        )

        if source_branch == target_branch:
            raise ValueError(
                "Source branch and target branch cannot be the same."
            )

        if not isinstance(title, str) or not title.strip():
            raise ValueError("Pull Request title is required.")

        if not isinstance(body, str):
            raise ValueError("Pull Request body must be a string.")

        headers = _headers()

        # Confirm the target branch exists.
        base_url = f"{GITHUB_API}/repos/{owner}/{repo}/branches"

        for branch_name in (target_branch, source_branch):
            branch_response = requests.get(
                f"{base_url}/{requests.utils.quote(branch_name, safe='')}",
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )

            if branch_response.status_code == 404:
                return _error(
                    "GITHUB_BRANCH_NOT_FOUND",
                    f"Branch '{branch_name}' was not found.",
                    "Confirm the branch exists and has been pushed.",
                )

            branch_response.raise_for_status()

        # Create the Pull Request.
        url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls"

        payload = {
            "title": title.strip(),
            "head": source_branch,
            "base": target_branch,
            "body": body,
            "draft": False,
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 422:
            return _error(
                "PULL_REQUEST_VALIDATION_FAILED",
                "GitHub could not create the Pull Request.",
                response.text,
            )

        if response.status_code == 404:
            return _error(
                "GITHUB_REPOSITORY_NOT_FOUND",
                "Repository was not found or access was denied.",
                response.text,
            )

        if response.status_code in (401, 403):
            return _error(
                "GITHUB_ACCESS_DENIED",
                "GitHub denied Pull Request creation.",
                response.text,
            )

        response.raise_for_status()

        data = response.json()

        return {
            "created": True,
            "pull_request_number": data.get("number"),
            "pull_request_url": data.get("html_url"),
            "source_branch": source_branch,
            "target_branch": target_branch,
            "state": data.get("state"),
        }

    except ValueError as exc:
        return _error(
            "INVALID_INPUT",
            "Invalid Pull Request request.",
            exc,
        )

    except requests.Timeout:
        return _error(
            "GITHUB_TIMEOUT",
            "Pull Request request timed out.",
            "GitHub did not respond within the configured timeout.",
        )

    except requests.HTTPError as exc:
        return _error(
            "GITHUB_API_ERROR",
            "GitHub API returned an HTTP error.",
            exc,
        )

    except requests.RequestException as exc:
        return _error(
            "GITHUB_CONNECTION_FAILED",
            "Could not connect to GitHub.",
            exc,
        )
