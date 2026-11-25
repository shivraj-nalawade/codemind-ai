
import os
import time
import json
import logging

from pathlib import Path
from functools import lru_cache
from dotenv import load_dotenv

from groq import (
    Groq,
    APIConnectionError,
    APITimeoutError,
    APIStatusError,
)

from .groq_limits import (
    protected_groq_call,
    GroqResourceLimitError,
)

# =====================================================
# CONFIGURATION
# =====================================================

BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")

MODEL = os.getenv(
    "LEARNING_MODEL",
    "openai/gpt-oss-120b"
)

MAX_ATTEMPTS = 3
RETRY_DELAY = 2
MAX_COMPLETION_TOKENS = 8192

logger = logging.getLogger(__name__)


# =====================================================
# CUSTOM EXCEPTION
# =====================================================

class LearningAIError(Exception):
    pass


# =====================================================
# GROQ CLIENT
# =====================================================

@lru_cache(maxsize=1)
def get_client():

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise LearningAIError(
            "GROQ_API_KEY not found in .env"
        )

    return Groq(
        api_key=api_key,
        timeout=60.0,
        max_retries=0
    )


# =====================================================
# EXTRACT GROQ ERROR CODE
# =====================================================

def get_error_code(error):

    error_body = getattr(error, "body", None)

    if isinstance(error_body, dict):

        error_details = error_body.get(
            "error",
            error_body
        )

        if isinstance(error_details, dict):
            return error_details.get("code")

    return None


# =====================================================
# AI RESPONSE GENERATION
# =====================================================

def generate_response(
    system_prompt,
    user_prompt,
    json_mode=False
):

    client = get_client()

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):

        delay = RETRY_DELAY

        try:

            logger.info(
                "Groq API attempt %s/%s",
                attempt,
                MAX_ATTEMPTS
            )

            parameters = {
                "model": MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                "temperature": 0.2,
                "max_completion_tokens": MAX_COMPLETION_TOKENS
            }

            if json_mode:

                parameters["response_format"] = {
                    "type": "json_object"
                }

            # =============================================
            # PROTECTED GROQ API CALL
            # =============================================

            with protected_groq_call():

                response = client.chat.completions.create(
                    **parameters
                )

            # Check whether a response was returned

            if not response.choices:
                raise ValueError(
                    "AI returned no response choices"
                )

            choice = response.choices[0]

            # Detect incomplete responses

            if choice.finish_reason == "length":
                raise ValueError(
                    "AI response exceeded the output token limit"
                )

            content = choice.message.content

            if not content or not content.strip():
                raise ValueError(
                    "Empty AI response"
                )

            # Validate JSON responses

            if json_mode:

                data = json.loads(content)

                if not isinstance(data, dict):
                    raise ValueError(
                        "AI response must be a JSON object"
                    )

                logger.info(
                    "Groq JSON response generated successfully"
                )

                return data

            logger.info(
                "Groq text response generated successfully"
            )

            return content

        # =============================================
        # GROQ RESOURCE LIMIT ERRORS
        # =============================================

        except GroqResourceLimitError as error:

            logger.warning(
                "Learning AI resource limit reached: %s",
                str(error)
            )

            # Do not retry when application resource
            # limits have been reached.

            raise LearningAIError(
                str(error)
            ) from None

        # =============================================
        # CONNECTION AND RESPONSE VALIDATION ERRORS
        # =============================================

        except (
            APIConnectionError,
            APITimeoutError,
            ValueError
        ) as error:

            last_error = error

            logger.warning(
                "Temporary AI failure: %s",
                type(error).__name__
            )

        # =============================================
        # GROQ HTTP ERRORS
        # =============================================

        except APIStatusError as error:

            last_error = error

            status = error.status_code

            error_code = get_error_code(error)

            # HTTP 400 caused by invalid generated JSON
            # can be retried.

            json_generation_failed = (
                status == 400
                and error_code == "json_validate_failed"
            )

            retryable = (
                status in (408, 409, 429)
                or status >= 500
                or json_generation_failed
            )

            # Permanent API errors should not be retried.

            if not retryable:

                logger.error(
                    "Groq API request rejected. "
                    "Status: %s, Code: %s",
                    status,
                    error_code
                )

                raise LearningAIError(
                    f"Groq API request rejected: {status}"
                ) from None

            if json_generation_failed:

                logger.warning(
                    "Groq generated invalid or incomplete JSON. "
                    "Retrying generation."
                )

            else:

                logger.warning(
                    "Groq API temporary error: %s, Code: %s",
                    status,
                    error_code
                )

            # Respect API rate-limit waiting periods.

            retry_after = error.response.headers.get(
                "Retry-After"
            )

            if retry_after:

                try:

                    delay = max(
                        RETRY_DELAY,
                        float(retry_after)
                    )

                except ValueError:
                    pass

        # =============================================
        # RETRY DELAY
        # =============================================

        if attempt < MAX_ATTEMPTS:

            logger.warning(
                "Retrying after %s seconds...",
                delay
            )

            time.sleep(delay)

    # =================================================
    # ALL ATTEMPTS FAILED
    # =================================================

    logger.error(
        "Groq generation failed after %s attempts. "
        "Last error type: %s",
        MAX_ATTEMPTS,
        type(last_error).__name__
    )

    raise LearningAIError(
        "Learning AI is temporarily unavailable. "
        "Please try again later."
    ) from None