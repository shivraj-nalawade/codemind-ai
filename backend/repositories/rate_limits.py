import time
import math

from collections import deque
from functools import wraps
from threading import Lock, BoundedSemaphore

from django.http import JsonResponse


# ==========================================================
# RATE LIMIT CONFIGURATION
# ==========================================================

CLEANUP_INTERVAL = 300

MAX_TRACKED_KEYS = 10000


# ==========================================================
# GLOBAL REQUEST LIMITS
# ==========================================================

GLOBAL_LIMITS = {
    "upload": (20, 3600),
    "parse": (30, 3600),
    "semantic_index": (20, 3600),
    "ask": (20, 60),
    "search": (120, 60),
    "semantic_search": (60, 60),
    "hybrid_search": (60, 60),
    "status": (300, 60),
}


# ==========================================================
# THREAD-SAFE RATE LIMIT STORAGE
# ==========================================================

_rate_limit_lock = Lock()

_request_history = {}

_last_cleanup = None


# ==========================================================
# SHARED HEAVY RESOURCE PROTECTION
# ==========================================================

_heavy_processing_semaphore = BoundedSemaphore(1)


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


def get_client_identity(request):
    """
    Identify existing anonymous browser sessions.

    Requests without an existing session share an
    IP-based fallback quota.

    Do not create a new database session solely
    for rate limiting.
    """

    session_key = request.session.session_key

    if session_key:

        return (
            "session",
            session_key,
        )

    return (
        "ip",
        get_client_ip(request),
    )


# ==========================================================
# RATE LIMIT RESPONSE
# ==========================================================

def rate_limit_response(
    message,
    retry_after,
):

    retry_after = max(
        1,
        math.ceil(retry_after),
    )

    response = JsonResponse(
        {
            "error": message,
            "retry_after": retry_after,
        },
        status=429,
    )

    response["Retry-After"] = str(
        retry_after
    )

    response["Cache-Control"] = "no-store"

    return response


# ==========================================================
# CLEAN EXPIRED REQUEST HISTORY
# ==========================================================

def cleanup_expired_requests(now):

    global _last_cleanup

    if (
        _last_cleanup is not None
        and now - _last_cleanup < CLEANUP_INTERVAL
    ):

        return

    expired_keys = []

    for key, entry in _request_history.items():

        timestamps = entry["timestamps"]

        window = entry["window"]

        while (
            timestamps
            and now - timestamps[0] >= window
        ):

            timestamps.popleft()

        if not timestamps:

            expired_keys.append(key)

    for key in expired_keys:

        _request_history.pop(
            key,
            None,
        )

    _last_cleanup = now


# ==========================================================
# ATOMIC RATE LIMIT VALIDATION
# ==========================================================

def check_rate_limits(rules):
    """
    Validate all applicable request limits atomically.

    Returns None when allowed, otherwise the number
    of seconds before another request can be attempted.
    """

    with _rate_limit_lock:

        now = time.monotonic()

        cleanup_expired_requests(now)

        new_keys = {
            key
            for key, _, _ in rules
            if key not in _request_history
        }

        if (
            len(_request_history) + len(new_keys)
            > MAX_TRACKED_KEYS
        ):

            return CLEANUP_INTERVAL

        retry_after = 0

        # Check all applicable limits before recording
        # the request.

        for key, maximum, window in rules:

            entry = _request_history.get(key)

            if entry is None:

                continue

            timestamps = entry["timestamps"]

            while (
                timestamps
                and now - timestamps[0] >= window
            ):

                timestamps.popleft()

            if len(timestamps) >= maximum:

                remaining = (
                    window
                    - (now - timestamps[0])
                )

                retry_after = max(
                    retry_after,
                    remaining,
                )

        if retry_after > 0:

            return retry_after

        # Record the request only when every limit passes.

        for key, maximum, window in rules:

            if key not in _request_history:

                _request_history[key] = {
                    "timestamps": deque(),
                    "window": window,
                }

            _request_history[key][
                "timestamps"
            ].append(now)

        return None


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

            client_identity = get_client_identity(
                request
            )

            # Individual session or fallback IP limit.

            rules = [
                (
                    (
                        "repository_client",
                        action,
                        client_identity,
                    ),
                    max_requests,
                    window_seconds,
                )
            ]

            # Global protection across all visitors.

            global_limit = GLOBAL_LIMITS.get(
                action
            )

            if global_limit:

                global_maximum, global_window = (
                    global_limit
                )

                rules.append(
                    (
                        (
                            "repository_global",
                            action,
                        ),
                        global_maximum,
                        global_window,
                    )
                )

            retry_after = check_rate_limits(
                rules
            )

            if retry_after is not None:

                retry_after = max(
                    1,
                    math.ceil(retry_after),
                )

                return rate_limit_response(
                    (
                        "Too many requests. "
                        f"Please try again in "
                        f"{retry_after} seconds."
                    ),
                    retry_after,
                )

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

def resource_limit(
    semaphore,
    error_message,
):

    def decorator(view_func):

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            acquired = semaphore.acquire(
                blocking=False
            )

            if not acquired:

                return rate_limit_response(
                    error_message,
                    10,
                )

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
    _heavy_processing_semaphore,
    (
        "The server is currently processing "
        "another AI or indexing request. "
        "Please try again shortly."
    ),
)


# ==========================================================
# SEMANTIC INDEXING PROTECTION
# ==========================================================

limit_indexing_requests = resource_limit(
    _heavy_processing_semaphore,
    (
        "The server is currently processing "
        "another AI or indexing request. "
        "Please try again shortly."
    ),
)