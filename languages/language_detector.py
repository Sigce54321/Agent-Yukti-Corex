"""Detect a repository's primary language without executing its contents."""

import os
from pathlib import Path


_EXTENSIONS = {
    ".py": "python",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
}
_PROJECT_FILES = {
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "pom.xml": "java",
    "build.gradle": "java",
    "build.gradle.kts": "java",
    "package.json": "javascript",
}
_IGNORED_DIRECTORIES = {
    ".git", "node_modules", ".venv", "venv", "env", ".env",
    "virtualenv", ".virtualenv", ".virtualenvs", "__pycache__",
    "build", "dist", "distribution", "target", "out",
    ".tox", ".nox", ".pytest_cache", ".mypy_cache", ".next",
    "site-packages", "bower_components", "coverage",
}
# Final tie preference favors programming languages over markup and styles.
_LANGUAGES = ("python", "java", "javascript", "html", "css")


def detect_language(repository_path: str) -> str:
    """Rank source counts, then manifest counts, then a fixed language order.

    Manifests alone can identify a project without source files. Directory
    symlinks are skipped entirely; file symlinks are also excluded.
    """
    if not isinstance(repository_path, str) or not repository_path.strip():
        return "unknown"
    sources = dict.fromkeys(_LANGUAGES, 0)
    manifests = dict.fromkeys(_LANGUAGES, 0)
    try:
        root = Path(repository_path).resolve(strict=True)
        if not root.is_dir():
            return "unknown"

        def raise_walk_error(error):
            raise error

        for directory, directories, files in os.walk(
            root, followlinks=False, onerror=raise_walk_error
        ):
            parent = Path(directory)
            directories[:] = [
                name for name in directories
                if name.lower() not in _IGNORED_DIRECTORIES
                and not (parent / name).is_symlink()
                and (parent / name).resolve(strict=True).is_relative_to(root)
                and not (parent / name / "pyvenv.cfg").is_file()
            ]
            for name in files:
                entry = parent / name
                if entry.is_symlink() or not entry.is_file():
                    continue
                if not entry.resolve(strict=True).is_relative_to(root):
                    continue
                language = _EXTENSIONS.get(entry.suffix.lower())
                if language:
                    sources[language] += 1
                language = _PROJECT_FILES.get(name.lower())
                if language:
                    manifests[language] += 1
    except (OSError, RuntimeError, ValueError):
        return "unknown"

    if not any(sources.values()) and not any(manifests.values()):
        return "unknown"
    return max(_LANGUAGES, key=lambda language: (sources[language], manifests[language]))
