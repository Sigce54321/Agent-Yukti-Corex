"""Workspace boundaries and Docker CLI defaults for sandbox execution."""

import os
from pathlib import Path
import stat


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACES_ROOT = PROJECT_ROOT / "workspaces"


def validate_workspace_path(workspace_path: str) -> bool:
    """Accept an existing, safe directory strictly below project workspaces.

    Relative paths are interpreted relative to the project root. Explicit parent
    traversal is rejected, even when it would resolve back inside workspaces.
    Inspect descendants as well so mounting the directory cannot expose secrets,
    host sockets, or links to unrelated host files. This is a point-in-time check;
    callers must prevent workspace mutation between validation and mounting.
    """
    if not isinstance(workspace_path, str) or not workspace_path.strip():
        return False
    try:
        supplied = Path(workspace_path)
        if ".." in supplied.parts:
            return False
        root = WORKSPACES_ROOT.resolve(strict=True)
        # Do not permit the workspaces boundary itself to redirect elsewhere.
        if root != WORKSPACES_ROOT or not root.is_dir():
            return False
        candidate = supplied if supplied.is_absolute() else PROJECT_ROOT / supplied
        resolved = candidate.resolve(strict=True)
        if not resolved.is_dir() or resolved == root or not resolved.is_relative_to(root):
            return False
        if any(part.lower() == ".env" for part in resolved.relative_to(root).parts):
            return False

        def reject_walk_error(error):
            raise error

        for directory, directories, files in os.walk(
            resolved, followlinks=False, onerror=reject_walk_error
        ):
            for name in directories + files:
                entry = Path(directory) / name
                target = entry.resolve(strict=True)
                if name.lower() == ".env" or target.name.lower() == ".env":
                    return False
                if not target.is_relative_to(resolved):
                    return False
                mode = target.stat().st_mode
                if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                    return False
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def get_container_security_options() -> dict:
    """Return fresh arguments to insert before the image in ``docker run``.

    No host mounts, environment files, or Docker socket access are added here.
    The runner must validate its workspace, mount only that directory, and apply
    timeout_seconds to subprocess execution (Docker has no run timeout flag).
    Do not append flags that weaken these restrictions.
    """
    return {
        "docker_args": [
            "--network=none",
            "--privileged=false",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--cpus=1",
            "--memory=512m",
            "--memory-swap=512m",
            "--pids-limit=128",
            "--read-only",
            "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777",
        ],
        "timeout_seconds": 120,
    }
