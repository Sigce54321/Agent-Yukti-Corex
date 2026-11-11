
"""
YuktiC-oreX - GitHub Issue Reader

Reads GitHub issue information using GitHub REST API.

Public function:
    read_github_issue(repo_url, issue_number)

Authentication:
    GITHUB_TOKEN environment variable (optional for public repos).
"""

import os
import re
from urllib.parse import urlparse

import requests


GITHUB_API = "https://api.github.com"
REQUEST_TIMEOUT = 20


class GitHubIssueError(Exception):
    """Raised when a GitHub issue cannot be retrieved."""


def _error(code, message, details):
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": str(details),
            "stage": "reading_issue",
        },
    }


def _parse_repo_url(repo_url):
    if not isinstance(repo_url, str) or not repo_url.strip():
        raise ValueError("repo_url is required.")

    parsed = urlparse(repo_url.strip())

    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise ValueError("Only HTTPS GitHub repository URLs are supported.")

    parts = [p for p in parsed.path.strip("/").split("/") if p]

    if len(parts) != 2:
        raise ValueError("Expected URL format: https://github.com/owner/repo")

    owner, repo = parts
    repo = re.sub(r"\.git$", "", repo)

    pattern = r"^[A-Za-z0-9_.-]+$"

    if not re.fullmatch(pattern, owner) or not re.fullmatch(pattern, repo):
        raise ValueError("Invalid GitHub owner or repository name.")

    if owner in {".", ".."} or repo in {".", ".."}:
        raise ValueError("Invalid GitHub repository path.")

    return owner, repo


def _headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "YuktiC-oreX",
    }

    token = os.getenv("GITHUB_TOKEN")

    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers


def read_github_issue(repo_url: str, issue_number: int) -> dict:
    """
    Read one GitHub issue.

    Args:
        repo_url: HTTPS GitHub repository URL.
        issue_number: Positive GitHub issue number.

    Returns on success:
        {
            "success": True,
            "number": int,
            "title": str,
            "body": str,
            "issue_url": str,
            "state": str,
            "labels": list,
            "user": str,
            "created_at": str,
            "updated_at": str
        }

    Returns on failure:
        {
            "success": False,
            "error": {
                "code": str,
                "message": str,
                "details": str,
                "stage": "reading_issue"
            }
        }
    """

    try:
        owner, repo = _parse_repo_url(repo_url)

        if (
            isinstance(issue_number, bool)
            or not isinstance(issue_number, int)
            or issue_number <= 0
        ):
            raise ValueError("issue_number must be a positive integer.")

        url = (
            f"{GITHUB_API}/repos/{owner}/{repo}"
            f"/issues/{issue_number}"
        )

        response = requests.get(
            url,
            headers=_headers(),
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 404:
            return _error(
                "ISSUE_NOT_FOUND",
                "GitHub issue was not found.",
                "Check the repository URL, issue number, and access permissions.",
            )

        if response.status_code == 401:
            return _error(
                "GITHUB_AUTH_FAILED",
                "GitHub authentication failed.",
                "Check the GITHUB_TOKEN environment variable.",
            )

        if response.status_code == 403:
            return _error(
                "GITHUB_ACCESS_DENIED",
                "GitHub denied access to the issue.",
                response.text,
            )

        response.raise_for_status()
        data = response.json()

        # GitHub's Issues endpoint also returns pull requests.
        if "pull_request" in data:
            return _error(
                "INVALID_ISSUE",
                "The supplied number identifies a Pull Request, not an issue.",
                "Provide a regular GitHub issue number.",
            )

        labels = [
            label.get("name", "")
            for label in data.get("labels", [])
            if isinstance(label, dict)
        ]

        return {
            "success": True,
            "number": data.get("number"),
            "title": data.get("title", ""),
            "body": data.get("body") or "",
            "issue_url": data.get("html_url", ""),
            "state": data.get("state", ""),
            "labels": labels,
            "user": (data.get("user") or {}).get("login", ""),
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
        }

    except ValueError as exc:
        return _error(
            "INVALID_INPUT",
            "Invalid GitHub issue request.",
            exc,
        )

    except requests.Timeout:
        return _error(
            "GITHUB_TIMEOUT",
            "GitHub issue request timed out.",
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

    except (KeyError, TypeError, ValueError) as exc:
        return _error(
            "GITHUB_INVALID_RESPONSE",
            "GitHub returned an unexpected response.",
            exc,
        )
