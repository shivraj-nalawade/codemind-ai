import time

from collections import deque
from functools import wraps
from threading import Lock, BoundedSemaphore

from django.http import JsonResponse


# ==========================================================
# RATE LIMIT STORAGE
# ==========================================================

_rate_limit_lock = Lock()

_request_history = {}

_last_cleanup = 0

CLEANUP_INTERVAL = 300

MAX_TRACKED_KEYS = 10000


# ==========================================================
# CONCURRENT RESOURCE LIMITS
# ==========================================================

_llm_semaphore = BoundedSemaphore(1)

_indexing_semaphore = BoundedSemaphore(1)


# ==========================================================
# CLIENT IDENTIFICATION
# ==========================================================

def get_client_ip(request):
    """
    Use the direct connection address.

    Do not trust arbitrary forwarded headers.
    """

    return request.META.get(
        "REMOTE_ADDR",
        "unknown",
    )


# ==========================================================
# RATE LIMIT CLEANUP
# ==========================================================

def cleanup_expired_requests(now):

    global _last_cleanup

    if now - _last_cleanup < CLEANUP_INTERVAL:
        return

    expired_keys = []

    for key, entry in _request_history.items():

        timestamps = entry["timestamps"]

        window = entry["window"]

        while timestamps and now - timestamps[0] >= window:
            timestamps.popleft()

        if not timestamps:
            expired_keys.append(key)

    for key in expired_keys:
        _request_history.pop(key, None)

    _last_cleanup = now


# ==========================================================
# RATE LIMIT DECORATOR
# ==========================================================

def rate_limit(
    action,
    max_requests,
    window_seconds,
):

    def decorator(view_func):

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            client_ip = get_client_ip(request)

            key = (action, client_ip)

            now = time.monotonic()

            with _rate_limit_lock:

                cleanup_expired_requests(now)

                if key not in _request_history:

                    if len(_request_history) >= MAX_TRACKED_KEYS:

                        response = JsonResponse(
                            {
                                "error": (
                                    "Server is temporarily busy. "
                                    "Please try again later."
                                )
                            },
                            status=429,
                        )

                        response["Retry-After"] = "300"

                        return response

                    _request_history[key] = {
                        "timestamps": deque(),
                        "window": window_seconds,
                    }

                timestamps = (
                    _request_history[key]["timestamps"]
                )

                # Remove requests outside the current window.

                while (
                    timestamps
                    and now - timestamps[0] >= window_seconds
                ):

                    timestamps.popleft()

                # Reject requests exceeding the limit.

                if len(timestamps) >= max_requests:

                    retry_after = max(
                        1,
                        int(
                            window_seconds
                            - (now - timestamps[0])
                        ) + 1,
                    )

                    response = JsonResponse(
                        {
                            "error": (
                                "Too many requests. "
                                f"Please try again in "
                                f"{retry_after} seconds."
                            ),
                            "retry_after": retry_after,
                        },
                        status=429,
                    )

                    response["Retry-After"] = str(
                        retry_after
                    )

                    return response

                timestamps.append(now)

            return view_func(
                request,
                *args,
                **kwargs,
            )

        return wrapper

    return decorator


# ==========================================================
# CONCURRENT RESOURCE PROTECTION
# ==========================================================

def resource_limit(semaphore, error_message):

    def decorator(view_func):

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            acquired = semaphore.acquire(
                blocking=False
            )

            if not acquired:

                response = JsonResponse(
                    {
                        "error": error_message,
                        "retry_after": 10,
                    },
                    status=429,
                )

                response["Retry-After"] = "10"

                return response

            try:

                return view_func(
                    request,
                    *args,
                    **kwargs,
                )

            finally:

                semaphore.release()

        return wrapper

    return decorator


# ==========================================================
# QWEN INFERENCE PROTECTION
# ==========================================================

limit_llm_requests = resource_limit(
    _llm_semaphore,
    (
        "The AI assistant is currently processing "
        "another request. Please try again shortly."
    ),
)


# ==========================================================
# SEMANTIC INDEXING PROTECTION
# ==========================================================

limit_indexing_requests = resource_limit(
    _indexing_semaphore,
    (
        "Another repository is currently being indexed. "
        "Please try again shortly."
    ),
)