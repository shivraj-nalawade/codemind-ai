import time

from collections import deque
from contextlib import contextmanager
from threading import Lock, BoundedSemaphore


# =====================================================
# RESOURCE LIMITS
# =====================================================

MAX_CONCURRENT_CALLS = 2

MAX_CALLS_PER_MINUTE = 20

MAX_CALLS_PER_HOUR = 120

MAX_CALLS_PER_DAY = 500


# =====================================================
# THREAD-SAFE STATE
# =====================================================

_call_semaphore = BoundedSemaphore(
    MAX_CONCURRENT_CALLS
)

_rate_lock = Lock()

_call_history = deque()


# =====================================================
# CUSTOM EXCEPTION
# =====================================================

class GroqResourceLimitError(Exception):
    pass


# =====================================================
# API CALL BUDGET
# =====================================================

def reserve_api_call():

    with _rate_lock:

        now = time.monotonic()

        # Remove records older than 24 hours.

        while (
            _call_history
            and now - _call_history[0] >= 86400
        ):

            _call_history.popleft()

        daily_calls = len(_call_history)

        hourly_calls = sum(
            1
            for timestamp in _call_history
            if now - timestamp < 3600
        )

        minute_calls = sum(
            1
            for timestamp in _call_history
            if now - timestamp < 60
        )

        if daily_calls >= MAX_CALLS_PER_DAY:

            raise GroqResourceLimitError(
                "The daily Learning AI usage limit "
                "has been reached. Please try again later."
            )

        if hourly_calls >= MAX_CALLS_PER_HOUR:

            raise GroqResourceLimitError(
                "The hourly Learning AI usage limit "
                "has been reached. Please try again later."
            )

        if minute_calls >= MAX_CALLS_PER_MINUTE:

            raise GroqResourceLimitError(
                "Learning AI is receiving too many "
                "requests. Please try again shortly."
            )

        # Count every outgoing API attempt,
        # including retries.

        _call_history.append(now)


# =====================================================
# CONCURRENT API CALL PROTECTION
# =====================================================

@contextmanager
def protected_groq_call():

    acquired = _call_semaphore.acquire(
        blocking=False
    )

    if not acquired:

        raise GroqResourceLimitError(
            "Learning AI is currently busy. "
            "Please try again shortly."
        )

    try:

        reserve_api_call()

        yield

    finally:

        _call_semaphore.release()