"""Abstract interface for language-specific execution adapters."""

from abc import ABC, abstractmethod


class BaseLanguageAdapter(ABC):
    """Provide command argument lists and a Docker image for a language."""

    @abstractmethod
    def get_test_command(self, workspace_path: str) -> list[str]:
        """Return test command arguments, never a shell string."""
        pass

    @abstractmethod
    def get_run_command(self, workspace_path: str) -> list[str]:
        """Return application command arguments, never a shell string."""
        pass

    @abstractmethod
    def get_language_image(self) -> str:
        """Return the language's Docker image name."""
        pass
