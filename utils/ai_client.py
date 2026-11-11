
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


# Load environment variables from the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

_client = None


class GeminiClientError(Exception):
    """Raised when Gemini configuration or API requests fail."""


def get_client():
    """Create and reuse the Gemini API client."""
    global _client

    if not API_KEY:
        raise GeminiClientError(
            "GEMINI_API_KEY is missing from the project .env file."
        )

    if _client is None:
        _client = genai.Client(api_key=API_KEY)

    return _client


def generate_text(
    prompt: str,
    system_instruction: str | None = None,
    temperature: float = 0.2,
) -> str:
    """Generate text with automatic retries for temporary API errors."""

    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    client = get_client()

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    system_instruction=system_instruction,
                ),
            )

            if not response.text:
                raise GeminiClientError(
                    "Gemini returned an empty response."
                )

            return response.text.strip()

        except GeminiClientError:
            raise

        except Exception as exc:
            error_text = str(exc).upper()

            is_temporary = any(
                code in error_text
                for code in [
                    "503",
                    "429",
                    "UNAVAILABLE",
                    "RESOURCE_EXHAUSTED",
                ]
            )

            if is_temporary and attempt < 2:
                wait_seconds = 2 ** (attempt + 1)
                print(
                    f"Gemini temporarily unavailable. "
                    f"Retrying in {wait_seconds} seconds..."
                )
                time.sleep(wait_seconds)
                continue

            raise GeminiClientError(
                f"Gemini API request failed: {exc}"
            ) from exc

    raise GeminiClientError("Gemini request failed after retries.")
