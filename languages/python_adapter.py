"""Python command selection for Docker execution."""

from pathlib import Path

from .base import BaseLanguageAdapter


class PythonAdapter(BaseLanguageAdapter):
    """Provide Python commands without executing workspace code."""

    def get_test_command(self, workspace_path: str) -> list[str]:
        """Return pytest arguments for execution inside /workspace."""
        return ["python", "-m", "pytest", "-q"]

    def get_run_command(self, workspace_path: str) -> list[str]:
        """Select main.py, then app.py, from the workspace root."""
        if not isinstance(workspace_path, str) or not workspace_path.strip():
            return []
        try:
            workspace = Path(workspace_path)
            if not workspace.is_absolute():
                workspace = Path(__file__).resolve().parents[1] / workspace
            workspace = workspace.resolve(strict=True)
            if not workspace.is_dir():
                return []
            for filename in ("main.py", "app.py"):
                entry = workspace / filename
                if entry.is_file() and entry.resolve(strict=True).is_relative_to(workspace):
                    return ["python", filename]
        except (OSError, RuntimeError, ValueError):
            return []
        return []

    def get_language_image(self) -> str:
        """Return the project's Python sandbox image tag."""
        return "yuktic-orex-python:latest"
