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

# Load environment variables
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

# Model configuration
MODEL = os.getenv(
    "LEARNING_MODEL",
    "openai/gpt-oss-120b"
)

MAX_ATTEMPTS = 3
RETRY_DELAY = 2

logger = logging.getLogger(__name__)


class LearningAIError(Exception):
    pass


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


def generate_response(
    system_prompt,
    user_prompt,
    json_mode=False
):

    client = get_client()

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
                "temperature": 0.2
            }

            if json_mode:
                parameters["response_format"] = {
                    "type": "json_object"
                }

            response = client.chat.completions.create(
                **parameters
            )

            content = response.choices[0].message.content

            if not content:
                raise ValueError("Empty AI response")

            if json_mode:
                return json.loads(content)

            return content

        except (
            APIConnectionError,
            APITimeoutError,
            ValueError
        ) as error:

            logger.warning(
                "Temporary AI failure: %s",
                type(error).__name__
            )

        except APIStatusError as error:

            status = error.status_code

            retryable = (
                status in (408, 409, 429)
                or status >= 500
            )

            if not retryable:
                raise LearningAIError(
                    f"Groq API request rejected: {status}"
                ) from error

            logger.warning(
                "Groq API temporary error: %s",
                status
            )

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

        if attempt < MAX_ATTEMPTS:

            logger.warning(
                "Retrying after %s seconds...",
                delay
            )

            time.sleep(delay)

    raise LearningAIError(
        "Learning AI is temporarily unavailable. "
        "Please try again later."
    )