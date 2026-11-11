
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Load environment variables from the project .env file
load_dotenv(PROJECT_ROOT / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model: str

    github_token: str

    log_level: str
    log_file: Path

    github_api_timeout: int

    workspaces_dir: Path
    generated_reports_dir: Path


def _get_integer(name: str, default: int) -> int:
    """Read an integer environment variable safely."""

    value = os.getenv(name, str(default))

    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def get_settings() -> Settings:
    """
    Load and return application settings.

    Returns:
        Settings: Application configuration.
    """

    log_file = Path(
        os.getenv("LOG_FILE", "logs/yukticorex.log")
    )

    if not log_file.is_absolute():
        log_file = PROJECT_ROOT / log_file

    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),

        gemini_model=os.getenv(
            "GEMINI_MODEL",
            "gemini-2.5-flash"
        ).strip(),

        github_token=os.getenv("GITHUB_TOKEN", "").strip(),

        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),

        log_file=log_file,

        github_api_timeout=_get_integer(
            "GITHUB_API_TIMEOUT", 20
        ),

        workspaces_dir=PROJECT_ROOT / "workspaces",

        generated_reports_dir=PROJECT_ROOT / "generated_reports"
    )


def ensure_runtime_directories() -> None:
    """Create required runtime directories."""

    settings = get_settings()

    settings.workspaces_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    settings.generated_reports_dir.mkdir(
        parents=True,
        exist_ok=True
    )
