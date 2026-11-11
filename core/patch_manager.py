import difflib
import os
import subprocess
import tempfile

from pathlib import Path, PureWindowsPath
MAX_REPAIR_RETRIES = 2


def _error(code, message, details, file_path=None):
    return {
        "success": False,
        "file_path": file_path,
        "diff": "",
        "error": {
            "code": code,
            "message": message,
            "details": str(details),
            "stage": "applying_patch"
        }
    }


def _resolve_file_path(workspace_path, file_path):
    """
    Resolve a relative file path and ensure it remains inside
    the supplied workspace.
    """

    if not isinstance(workspace_path, str) or not workspace_path.strip():
        raise ValueError("Invalid workspace path.")

    if not isinstance(file_path, str) or not file_path.strip():
        raise ValueError("File path must be a non-empty string.")

    if "\x00" in file_path:
        raise ValueError("Null characters are not allowed in file paths.")

    normalized = file_path.replace("\\", "/")
    windows_path = PureWindowsPath(file_path)

    if normalized.startswith("/") or windows_path.is_absolute() or windows_path.drive:
        raise ValueError("Absolute file paths are not allowed.")

    parts = normalized.split("/")

    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("Invalid or unsafe relative file path.")

    root = Path(workspace_path).resolve(strict=True)

    if not root.is_dir():
        raise ValueError("Workspace path is not a directory.")

    target = root.joinpath(*parts).resolve(strict=True)

    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError("Target file is outside the workspace.")

    if not target.is_file():
        raise ValueError("Target path is not a regular file.")

    return root, target, "/".join(parts)


def _make_diff(file_path, original_code, modified_code):
    return "".join(
        difflib.unified_diff(
            original_code.splitlines(keepends=True),
            modified_code.splitlines(keepends=True),
            fromfile="a/" + file_path,
            tofile="b/" + file_path,
            lineterm="\n"
        )
    )


def create_patch(
    workspace_path: str,
    file_path: str,
    modified_code: str
) -> dict:
    """
    Create a patch proposal.

    This function does not modify the file.
    """

    try:
        if not isinstance(modified_code, str):
            return _error(
                "PATCH_INVALID",
                "Modified code must be a string.",
                "modified_code must contain source code text.",
                file_path
            )

        _, target, relative_path = _resolve_file_path(
            workspace_path,
            file_path
        )

        original_code = target.read_bytes().decode("utf-8")

        if original_code == modified_code:
            return _error(
                "PATCH_INVALID",
                "No changes detected.",
                "Original and modified code are identical.",
                relative_path
            )

        diff = _make_diff(
            relative_path,
            original_code,
            modified_code
        )

        return {
            "success": True,
            "file_path": relative_path,
            "original_code": original_code,
            "modified_code": modified_code,
            "diff": diff,
            "error": None
        }

    except UnicodeDecodeError as exc:
        return _error(
            "PATCH_INVALID",
            "Target file is not valid UTF-8 text.",
            exc,
            file_path
        )

    except FileNotFoundError as exc:
        return _error(
            "PATCH_INVALID",
            "Target file was not found.",
            exc,
            file_path
        )

    except Exception as exc:
        return _error(
            "PATCH_INVALID",
            "Could not create patch.",
            exc,
            file_path
        )


def apply_patch(
    workspace_path: str,
    patch: dict
) -> dict:
    """
    Apply a previously created patch to the working copy only.

    The current file must still match the original snapshot.
    """

    file_path = None

    try:
        if not isinstance(patch, dict):
            return _error(
                "PATCH_INVALID",
                "Invalid patch format.",
                "Patch must be a dictionary."
            )

        required_fields = (
            "file_path",
            "original_code",
            "modified_code"
        )

        for field in required_fields:
            if field not in patch:
                return _error(
                    "PATCH_INVALID",
                    "Patch is missing a required field.",
                    "Missing field: " + field
                )

        file_path = patch["file_path"]
        original_code = patch["original_code"]
        modified_code = patch["modified_code"]

        if not isinstance(original_code, str):
            return _error(
                "PATCH_INVALID",
                "Invalid original code.",
                "original_code must be a string.",
                file_path
            )

        if not isinstance(modified_code, str):
            return _error(
                "PATCH_INVALID",
                "Invalid modified code.",
                "modified_code must be a string.",
                file_path
            )

        if original_code == modified_code:
            return _error(
                "PATCH_INVALID",
                "No changes detected.",
                "Original and modified code are identical.",
                file_path
            )

        _, target, relative_path = _resolve_file_path(
            workspace_path,
            file_path
        )

        current_code = target.read_bytes().decode("utf-8")

        # Prevent overwriting changes made after patch creation.
        if current_code != original_code:
            return _error(
                "PATCH_INVALID",
                "Original file has changed.",
                "The current file does not match the original_code snapshot.",
                relative_path
            )

        actual_diff = _make_diff(
            relative_path,
            current_code,
            modified_code
        )

        # Write to a temporary file in the same directory.
        # os.replace makes the final replacement atomic.
        file_descriptor = None
        temporary_path = None

        try:
            file_descriptor, temporary_path = tempfile.mkstemp(
                prefix=".yukticorex_",
                suffix=".tmp",
                dir=str(target.parent)
            )

            with os.fdopen(file_descriptor, "wb") as temporary_file:
                file_descriptor = None
                temporary_file.write(modified_code.encode("utf-8"))
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            os.chmod(temporary_path, target.stat().st_mode)
            os.replace(temporary_path, str(target))
            temporary_path = None

        finally:
            if file_descriptor is not None:
                os.close(file_descriptor)

            if temporary_path and os.path.exists(temporary_path):
                os.remove(temporary_path)

        return {
            "success": True,
            "file_path": relative_path,
            "diff": actual_diff,
            "error": None
        }

    except Exception as exc:
        return _error(
            "PATCH_APPLY_FAILED",
            "Could not apply patch to the working copy.",
            exc,
            file_path
        )


def get_file_diff(
    workspace_path: str,
    file_path: str
) -> dict:
    """
    Return the actual difference between HEAD and the current
    working-copy file.
    """

    try:
        root, target, relative_path = _resolve_file_path(
            workspace_path,
            file_path
        )

        # Read the original committed version.
        baseline = subprocess.run(
            [
                "git",
                "show",
                "HEAD:" + relative_path
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False
        )

        if baseline.returncode == 0:
            original_code = baseline.stdout
        else:
            # The file may be new and not tracked in HEAD.
            tracked = subprocess.run(
                [
                    "git",
                    "ls-files",
                    "--error-unmatch",
                    relative_path
                ],
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                check=False
            )

            if tracked.returncode == 0:
                return _error(
                    "PATCH_INVALID",
                    "Could not read the committed original file.",
                    baseline.stderr,
                    relative_path
                )

            original_code = ""

        modified_code = target.read_bytes().decode("utf-8")

        actual_diff = _make_diff(
            relative_path,
            original_code,
            modified_code
        )

        return {
            "success": True,
            "file_path": relative_path,
            "diff": actual_diff,
            "error": None
        }

    except subprocess.TimeoutExpired as exc:
        return _error(
            "PATCH_INVALID",
            "Git diff operation timed out.",
            exc,
            file_path
        )

    except Exception as exc:
        return _error(
            "PATCH_INVALID",
            "Could not generate file difference.",
            exc,
            file_path
        )