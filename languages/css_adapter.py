"""Playwright command selection for static CSS workspaces."""

from .base import BaseLanguageAdapter
from .html_adapter import _playwright_test_command


class CSSAdapter(BaseLanguageAdapter):
    """Use the shared browser test tooling for CSS verification."""

    def get_test_command(self, workspace_path: str) -> list[str]:
        """Return an installed Playwright command, or no command."""
        return _playwright_test_command(workspace_path)

    def get_run_command(self, workspace_path: str) -> list[str]:
        """Static CSS has no standalone execution command."""
        return []

    def get_language_image(self) -> str:
        """Return the shared browser sandbox image tag."""
        return "yuktic-orex-browser:latest"
