"""Docker CLI helpers for YuktiC-oreX language sandboxes.

Containers eligible for cleanup must carry the label
``yuktic-orex.managed=true``. Container creators must set this label explicitly.
"""

import json
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANAGED_LABEL = "yuktic-orex.managed"
CLI_TIMEOUT = 30
BUILD_TIMEOUT = 600
LANGUAGE_IMAGES = {
    "python": "python",
    "java": "java",
    "javascript": "javascript",
    "html": "browser",
    "css": "browser",
}


def _run(arguments, timeout=CLI_TIMEOUT):
    """Run Docker without a shell, preserving diagnostic output."""
    return subprocess.run(
        ["docker", *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def _logs(result):
    return "\n".join(
        output.strip() for output in (result.stdout, result.stderr) if output.strip()
    )


def _error(error):
    if isinstance(error, subprocess.TimeoutExpired):
        output = []
        for value in (error.stdout, error.stderr):
            if isinstance(value, bytes):
                value = value.decode("utf-8", errors="replace")
            if value:
                output.append(value.strip())
        return "\n".join([f"Docker command timed out after {error.timeout} seconds.", *output])
    if isinstance(error, FileNotFoundError):
        return "Docker CLI was not found. Install Docker and ensure it is on PATH."
    return f"Unable to execute Docker CLI: {error}"


def check_docker_connection() -> bool:
    """Return whether the Docker CLI can contact the daemon."""
    try:
        return _run(["info", "--format", "{{.ServerVersion}}"]).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def build_language_image(language: str) -> dict:
    """Reuse a local language image or build it from the project's Dockerfile."""
    image_type = LANGUAGE_IMAGES.get(language.strip().lower()) if isinstance(language, str) else None
    if image_type is None:
        return {
            "success": False,
            "image_name": None,
            "logs": "Unsupported language. Expected python, java, javascript, html, or css.",
        }

    image_name = f"yuktic-orex-{image_type}:latest"
    result = {"success": False, "image_name": image_name, "logs": ""}
    try:
        inspection = _run(["image", "inspect", image_name])
        if inspection.returncode == 0:
            result.update(success=True, logs=f"Reusing existing image {image_name}.")
            return result

        # An inspect failure can also indicate an unavailable daemon.
        connection = _run(["info", "--format", "{{.ServerVersion}}"])
        if connection.returncode != 0:
            result["logs"] = "Docker daemon is unavailable.\n" + _logs(connection)
            return result

        dockerfile = PROJECT_ROOT / "docker" / f"{image_type}.Dockerfile"
        if not dockerfile.is_file() or dockerfile.stat().st_size == 0:
            result["logs"] = f"Dockerfile is missing or empty: {dockerfile}"
            return result

        build = _run(
            ["build", "--file", str(dockerfile), "--tag", image_name, str(PROJECT_ROOT)],
            timeout=BUILD_TIMEOUT,
        )
        result.update(
            success=build.returncode == 0,
            logs=_logs(build) or f"Docker build exited with status {build.returncode}.",
        )
    except (OSError, subprocess.SubprocessError) as error:
        result["logs"] = _error(error)
    return result


def stop_and_remove_container(container_id: str) -> bool:
    """Remove only an explicitly managed container, resolving its immutable ID first.

    Return False for missing containers, ownership mismatches, malformed metadata,
    or CLI failures. Forced removal also stops a running container.
    """
    if not isinstance(container_id, str) or not container_id.strip() or container_id.startswith("-"):
        return False
    try:
        inspection = _run(["container", "inspect", "--", container_id])
        if inspection.returncode != 0:
            return False
        containers = json.loads(inspection.stdout)
        if not isinstance(containers, list) or len(containers) != 1:
            return False
        container = containers[0]
        labels = container.get("Config", {}).get("Labels") or {}
        if labels.get(MANAGED_LABEL) != "true":
            return False
        resolved_id = container.get("Id", "")
        if len(resolved_id) != 64 or any(character not in "0123456789abcdef" for character in resolved_id):
            return False
        return _run(["container", "rm", "--force", resolved_id]).returncode == 0
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError):
        return False
