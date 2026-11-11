"""Workspace boundaries and Docker CLI defaults for sandbox execution."""

import os
from contextlib import contextmanager
from pathlib import Path
import shutil
import stat
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACES_ROOT = PROJECT_ROOT / "workspaces"


def _excluded_name(name: str) -> bool:
    """Names that must never enter a task mount, regardless of case."""
    name = name.lower()
    return (
        name.startswith((".env", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "private_key", "private-key", "service-account"))
        or name in {
            ".git", ".git-credentials", ".aws", ".ssh", ".azure", ".gcp", "gcloud",
            ".npmrc", ".pypirc", ".netrc", "_netrc", "credentials",
            "credentials.json", "credentials.ini", "credentials.yml", "credentials.yaml",
            "service_account.json", "secrets.json", "secrets.yml", "secrets.yaml",
        }
        or name.endswith((".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".kdbx"))
    )


def _plain_info(path: Path):
    """Reject links, Windows reparse points (including junctions), and devices."""
    info = path.lstat()
    if (
        stat.S_ISLNK(info.st_mode)
        or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode))
        or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)
    ):
        raise ValueError(f"Unsafe workspace entry: {path.name}")
    return info


def _workspace_directory(workspace_path: str) -> Path:
    if not isinstance(workspace_path, str) or not workspace_path.strip():
        raise ValueError("Workspace path must be a nonempty string.")
    supplied = Path(workspace_path)
    if ".." in supplied.parts:
        raise ValueError("Workspace parent traversal is not allowed.")
    root = WORKSPACES_ROOT.resolve(strict=True)
    if root != WORKSPACES_ROOT or not stat.S_ISDIR(_plain_info(root).st_mode):
        raise ValueError("Unsafe workspaces root.")
    candidate = supplied if supplied.is_absolute() else PROJECT_ROOT / supplied
    # Check lexical ancestors before resolving, so an in-boundary junction is
    # rejected too, rather than silently accepting its resolved target.
    relative = candidate.relative_to(root)
    if not relative.parts or any(_excluded_name(part) or part.startswith(".yuktic-task-") for part in relative.parts):
        raise ValueError("Expected an original task directory below workspaces/.")
    current = root
    for part in relative.parts:
        current /= part
        if not stat.S_ISDIR(_plain_info(current).st_mode):
            raise ValueError("Workspace must be an existing directory.")
    resolved = candidate.resolve(strict=True)
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError("Workspace is outside workspaces/.")
    return resolved


def _check_copy_path(path: Path, root: Path):
    """Recheck all ancestors before opening an entry during the copy."""
    current = root
    _plain_info(current)
    for part in path.relative_to(root).parts:
        current /= part
        _plain_info(current)
    if not path.resolve(strict=True).is_relative_to(root):
        raise ValueError("Workspace entry escaped its source directory.")
    return _plain_info(path)


def _copy_sanitized(source: Path, destination: Path, root: Path):
    _check_copy_path(source, root)
    with os.scandir(source) as entries:
        names = sorted(entry.name for entry in entries)
    for name in names:
        entry = source / name
        info = _check_copy_path(entry, root)
        if _excluded_name(name):
            continue
        target = destination / name
        if stat.S_ISDIR(info.st_mode):
            target.mkdir(mode=0o700)
            _copy_sanitized(entry, target, root)
        else:
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
            with os.fdopen(os.open(entry, flags), "rb") as incoming:
                opened = os.fstat(incoming.fileno())
                if (
                    not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                    or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)
                ):
                    raise ValueError("Workspace file changed while opening it.")
                _check_copy_path(entry, root)
                with target.open("xb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing, length=64 * 1024)
                after = _check_copy_path(entry, root)
                if (after.st_dev, after.st_ino) != (opened.st_dev, opened.st_ino):
                    raise ValueError("Workspace file changed during the copy.")
            target.chmod((stat.S_IMODE(info.st_mode) & 0o777) | 0o600)


@contextmanager
def sanitized_workspace(workspace_path: str):
    """Yield a private writable task copy on the project drive, then delete it.

    The original is only read. Copies use fresh files, never links. The project
    workspaces parent must be trusted against concurrent host-user replacement;
    this is not an isolation boundary against a hostile host administrator.
    """
    source = _workspace_directory(workspace_path)
    task = Path(tempfile.mkdtemp(prefix=".yuktic-task-", dir=WORKSPACES_ROOT))
    expected = task.absolute()
    allocated = _plain_info(task)
    try:
        task.chmod(0o700)
        _copy_sanitized(source, task, source)
        if not validate_workspace_path(str(task)):
            raise ValueError("Sanitized task workspace failed validation.")
        yield task
    finally:
        # Only the exact directory allocated above is eligible for deletion.
        # Refuse cleanup if its root was replaced by a link/junction.
        if task.exists() or task.is_symlink():
            current = _plain_info(task)
            if (
                task.resolve(strict=True) != expected or task.parent != WORKSPACES_ROOT
                or (current.st_dev, current.st_ino) != (allocated.st_dev, allocated.st_ino)
            ):
                raise ValueError("Refusing cleanup of a replaced task directory.")
            shutil.rmtree(task)


def validate_workspace_path(workspace_path: str) -> bool:
    """Accept an existing, safe directory strictly below project workspaces.

    Relative paths are interpreted relative to the project root. Explicit parent
    traversal is rejected, even when it would resolve back inside workspaces.
    This validates a sanitized tree, not permission to mount an original tree.
    All links, junctions, hard-linked files, and recognized secrets are rejected.
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
        current = root
        for part in candidate.relative_to(root).parts:
            current /= part
            _plain_info(current)
        resolved = candidate.resolve(strict=True)
        if not resolved.is_dir() or resolved == root or not resolved.is_relative_to(root):
            return False
        if any(_excluded_name(part) for part in resolved.relative_to(root).parts):
            return False

        def reject_walk_error(error):
            raise error

        for directory, directories, files in os.walk(
            resolved, followlinks=False, onerror=reject_walk_error
        ):
            for name in directories + files:
                entry = Path(directory) / name
                _plain_info(entry)
                target = entry.resolve(strict=True)
                if _excluded_name(name) or _excluded_name(target.name):
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
