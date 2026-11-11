"""Playwright command selection for static HTML workspaces."""

import os
from pathlib import Path
import re

from .base import BaseLanguageAdapter


_IGNORED = {
    ".git", "node_modules", ".venv", "venv", "__pycache__",
    "build", "dist", "coverage", "playwright-report", "test-results",
}
_PLAYWRIGHT_IMPORT = re.compile(
    r'''(?:\bfrom\s*|\brequire\s*\(\s*|\bimport\s*)['"](?:@playwright/test|playwright/test)['"]'''
)


def _playwright_test_command(workspace_path: str) -> list[str]:
    """Find conventional test files importing the Playwright test runner."""
    if not isinstance(workspace_path, str) or not workspace_path.strip():
        return []
    try:
        root = Path(workspace_path)
        if not root.is_absolute():
            root = Path(__file__).resolve().parents[1] / root
        root = root.resolve(strict=True)
        if not root.is_dir():
            return []
        tests = []

        def raise_walk_error(error):
            raise error

        for directory, directories, files in os.walk(
            root, followlinks=False, onerror=raise_walk_error
        ):
            parent = Path(directory)
            directories[:] = sorted(
                name for name in directories
                if name.lower() not in _IGNORED
                and not (parent / name).is_symlink()
                and (parent / name).resolve(strict=True).is_relative_to(root)
            )
            for name in sorted(files):
                if not name.endswith((".spec.js", ".spec.ts", ".test.js", ".test.ts")):
                    continue
                entry = parent / name
                if (
                    entry.is_symlink() or not entry.is_file()
                    or not entry.resolve(strict=True).is_relative_to(root)
                ):
                    continue
                if _PLAYWRIGHT_IMPORT.search(entry.read_text(encoding="utf-8-sig")):
                    tests.append(re.escape(entry.relative_to(root).as_posix()) + "$")
        if tests:
            # Invoke tooling already on the browser image's PATH. No npx/npm
            # installation or browser download is attempted. File filters are
            # regexes in Playwright, so escape repository-controlled filenames.
            return [
                "playwright", "test", "--reporter=line", "--workers=1",
                "--output=/tmp/playwright-results", *sorted(tests),
            ]
    except (OSError, RuntimeError, ValueError, UnicodeError):
        return []
    return []


class HTMLAdapter(BaseLanguageAdapter):
    """Provide browser tests without inventing a static-asset run command."""

    def get_test_command(self, workspace_path: str) -> list[str]:
        """Return an installed Playwright command, or no command."""
        return _playwright_test_command(workspace_path)

    def get_run_command(self, workspace_path: str) -> list[str]:
        """Static HTML has no standalone execution command."""
        return []

    def get_language_image(self) -> str:
        """Return the shared browser sandbox image tag."""
        return "yuktic-orex-browser:latest"
