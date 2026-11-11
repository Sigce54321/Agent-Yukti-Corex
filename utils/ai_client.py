
from google import genai
from google.genai import types

from utils.config import get_settings
from utils.logger import get_logger


logger = get_logger("yukticorex.ai_client")


class AIClientError(Exception):
    """Custom exception for Gemini API errors."""

    def __init__(
        self,
        code: str,
        message: str,
        details: str = ""
    ):
        super().__init__(message)

        self.code = code
        self.message = message
        self.details = details

    def to_error_response(
        self,
        task_id: str = None,
        stage: str = None
    ) -> dict:
        """
        Convert the exception into the common error format.
        """

        return {
            "status": "failed",
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
                "stage": stage
            },
            "task_id": task_id
        }


def _sanitize_details(details: str, api_key: str) -> str:
    """Prevent API keys from appearing in error details."""

    if api_key:
        details = details.replace(api_key, "[REDACTED]")

    return details[:500]


def generate_ai_response(
    prompt: str,
    response_schema: dict = None
) -> str:
    """
    Generate a response using the shared Gemini API client.

    Args:
        prompt (str):
            Input prompt from an AI agent.

        response_schema (dict | None):
            Optional JSON response schema.

    Returns:
        str: Gemini model response.

    Raises:
        AIClientError: If the API request fails or response is invalid.
    """

    # Validate prompt
    if not isinstance(prompt, str) or not prompt.strip():
        raise AIClientError(
            code="INVALID_INPUT",
            message="AI prompt cannot be empty.",
            details="A non-empty prompt string is required."
        )

    # Validate response schema
    if response_schema is not None and not isinstance(
        response_schema, dict
    ):
        raise AIClientError(
            code="INVALID_INPUT",
            message="Invalid response schema.",
            details="response_schema must be a dictionary or None."
        )

    settings = get_settings()

    # Check API key
    if not settings.gemini_api_key:
        raise AIClientError(
            code="AI_REQUEST_FAILED",
            message="Gemini API key is not configured.",
            details="Set GEMINI_API_KEY in the project .env file."
        )

    try:
        # Initialize Gemini client
        client = genai.Client(
            api_key=settings.gemini_api_key
        )

        generation_config = None

        # Enable structured JSON output when a schema is provided
        if response_schema is not None:
            generation_config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema
            )

        # Send request to Gemini
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=generation_config
        )

        # Extract generated text
        response_text = getattr(response, "text", None)

        if not isinstance(response_text, str) or not response_text.strip():
            raise AIClientError(
                code="AI_INVALID_RESPONSE",
                message="Gemini returned an empty response.",
                details="The model response did not contain usable text."
            )

        logger.info("Gemini response generated successfully.")

        return response_text.strip()

    except AIClientError:
        raise

    except Exception as exc:
        details = _sanitize_details(
            f"{type(exc).__name__}: {exc}",
            settings.gemini_api_key
        )

        logger.error(
            "Gemini API request failed: %s",
            details
        )

        raise AIClientError(
            code="AI_REQUEST_FAILED",
            message="Gemini API request failed.",
            details=details
        ) from exc
