"""Select JavaScript sandbox commands using filesystem inspection only."""

import json
import os
from pathlib import Path
import re

from .base import BaseLanguageAdapter


_IGNORED = {".git", "node_modules", "coverage", "build", "dist", ".next"}


def _workspace(workspace_path: str) -> Path | None:
    if not isinstance(workspace_path, str) or not workspace_path.strip():
        return None
    path = Path(workspace_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    path = path.resolve(strict=True)
    return path if path.is_dir() else None


def _safe_file(path: Path, root: Path) -> bool:
    return not path.is_symlink() and path.is_file() and path.resolve(strict=True).is_relative_to(root)


class JavaScriptAdapter(BaseLanguageAdapter):
    """Provide npm, Node test, and conventional entry-point commands."""

    def get_test_command(self, workspace_path: str) -> list[str]:
        """Prefer a real npm test script; otherwise detect Node test files."""
        try:
            root = _workspace(workspace_path)
            if root is None:
                return []
            manifest = root / "package.json"
            if _safe_file(manifest, root):
                try:
                    package = json.loads(manifest.read_text(encoding="utf-8-sig"))
                except (ValueError, UnicodeError):
                    return []
                if not isinstance(package, dict):
                    return []
                scripts = package.get("scripts", {})
                script = scripts.get("test") if isinstance(scripts, dict) else None
                if isinstance(script, str) and script.strip():
                    normalized = " ".join(script.lower().split())
                    placeholder = (
                        "no test specified" in normalized
                        or "no tests specified" in normalized
                        or re.fullmatch(r"(?:echo\b.*|exit\s+[01]|true|false|:)", normalized)
                    )
                    if not placeholder:
                        return ["npm", "test"]

            for directory, directories, files in os.walk(root, followlinks=False):
                parent = Path(directory)
                directories[:] = sorted(
                    name for name in directories
                    if name.lower() not in _IGNORED
                    and not (parent / name).is_symlink()
                    and (parent / name).resolve(strict=True).is_relative_to(root)
                )
                for name in sorted(files):
                    entry = parent / name
                    if entry.suffix not in {".js", ".cjs", ".mjs"} or not _safe_file(entry, root):
                        continue
                    # Match Node's default discovery, not Jest's *.spec.js.
                    if not (
                        entry.stem == "test" or entry.stem.startswith("test-")
                        or entry.stem.endswith((".test", "_test", "-test"))
                        or "test" in entry.relative_to(root).parts[:-1]
                    ):
                        continue
                    source = entry.read_text(encoding="utf-8-sig")
                    # Shared *.test.js names alone cannot establish Jest/Node
                    # compatibility. Avoid apparent framework globals unless
                    # the file explicitly references Node's built-in test API.
                    if "node:test" in source or not re.search(
                        r"\b(?:describe|it|test|expect|jest|beforeEach|afterEach)\s*[.(]", source
                    ):
                        return ["node", "--test"]
        except (OSError, RuntimeError, ValueError, UnicodeError):
            return []
        return []

    def get_run_command(self, workspace_path: str) -> list[str]:
        """Select index.js, app.js, then main.js from the workspace root."""
        try:
            root = _workspace(workspace_path)
            if root is not None:
                for filename in ("index.js", "app.js", "main.js"):
                    if _safe_file(root / filename, root):
                        return ["node", filename]
        except (OSError, RuntimeError, ValueError):
            return []
        return []

    def get_language_image(self) -> str:
        """Return the image tag shared with the sandbox runner."""
        return "yuktic-orex-javascript:latest"
