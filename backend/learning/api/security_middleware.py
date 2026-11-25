import time
import math

from collections import deque
from threading import Lock, BoundedSemaphore

from django.http import JsonResponse


# ==========================================================
# SECURITY CONFIGURATION
# ==========================================================

MAX_TRACKED_KEYS = 10000

CLEANUP_INTERVAL = 300

MAX_CONCURRENT_AI_JOBS = 2


# ==========================================================
# AUTHENTICATION RATE LIMITS
# ==========================================================

AUTH_LIMITS = {
    "register": (5, 3600),
    "login": (10, 900),
    "csrf": (120, 60),
}


# ==========================================================
# AI GENERATION RATE LIMITS
# ==========================================================

AI_LIMITS = {
    "generate_initial_assessment": (5, 3600),
    "evaluate_assessment": (5, 3600),
    "generate_roadmap": (3, 3600),
    "generate_lesson": (10, 3600),
    "generate_daily_assessment": (10, 3600),
    "evaluate_daily_attempt": (15, 3600),
    "adapt_roadmap": (10, 3600),
}


# ==========================================================
# GENERAL LEARNING API LIMITS
# ==========================================================

GENERAL_LIMITS = {
    "dashboard": (60, 60),
    "enrollments": (30, 60),
    "save_answers": (120, 60),
    "save_daily_answers": (120, 60),
    "start_assessment": (15, 3600),
    "start_daily_attempt": (30, 3600),
    "submit_assessment": (15, 3600),
    "submit_daily_attempt": (30, 3600),
}

DEFAULT_LIMIT = (120, 60)

GLOBAL_AI_LIMIT = (60, 3600)


# ==========================================================
# THREAD-SAFE SECURITY STATE
# ==========================================================

_rate_lock = Lock()

_request_history = {}

_last_cleanup = None

_ai_semaphore = BoundedSemaphore(
    MAX_CONCURRENT_AI_JOBS
)


# ==========================================================
# RATE LIMIT RESPONSE
# ==========================================================

def rate_limit_response(message, retry_after):

    retry_after = max(
        1,
        math.ceil(retry_after),
    )

    response = JsonResponse(
        {
            "success": False,
            "message": message,
            "data": None,
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
# CLIENT IDENTIFICATION
# ==========================================================

def get_client_ip(request):
    """
    Use the direct connection address.

    Forwarded headers must not be trusted until
    the reverse proxy configuration is verified.
    """

    return request.META.get(
        "REMOTE_ADDR",
        "unknown",
    )


# ==========================================================
# CLEAN EXPIRED RATE LIMIT RECORDS
# ==========================================================

def cleanup_rate_limits(now):

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

        _request_history.pop(key, None)

    _last_cleanup = now


# ==========================================================
# CHECK AND RECORD REQUESTS
# ==========================================================

def check_rate_limits(rules):
    """
    Check multiple limits atomically.

    Each rule contains:
        (key, maximum_requests, window_seconds)

    Returns:
        None if allowed.
        Retry delay if rejected.
    """

    with _rate_lock:

        now = time.monotonic()

        cleanup_rate_limits(now)

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

        # First check every rule.

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

        # Record requests only when all rules pass.

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
# PERSONALIZED LEARNING SECURITY MIDDLEWARE
# ==========================================================

class LearningSecurityMiddleware:
    """
    Protect Personalized Learning API endpoints.

    Existing authentication, CSRF validation and ownership
    checks remain the responsibility of Django and DRF.
    """

    def __init__(self, get_response):

        self.get_response = get_response

    def __call__(self, request):

        request._learning_ai_slot_acquired = False

        try:

            return self.get_response(request)

        finally:

            # Always release the AI slot, even when
            # the view raises an exception.

            if request._learning_ai_slot_acquired:

                request._learning_ai_slot_acquired = False

                _ai_semaphore.release()

    def process_view(
        self,
        request,
        view_func,
        view_args,
        view_kwargs,
    ):

        match = request.resolver_match

        if match is None:

            return None

        # Do not modify Repository Assistant behavior.

        if match.namespace != "learning":

            return None

        if request.method == "OPTIONS":

            return None

        action = match.url_name

        client_ip = get_client_ip(request)

        rules = []

        # ==============================================
        # AUTHENTICATION ENDPOINTS
        # ==============================================

        if action in AUTH_LIMITS:

            maximum, window = AUTH_LIMITS[action]

            rules.append((
                (
                    "learning_auth",
                    action,
                    client_ip,
                ),
                maximum,
                window,
            ))

            retry_after = check_rate_limits(rules)

            if retry_after is not None:

                return rate_limit_response(
                    "Too many requests. "
                    "Please try again later.",
                    retry_after,
                )

            return None

        # ==============================================
        # ANONYMOUS REQUEST PROTECTION
        # ==============================================

        user = getattr(request, "user", None)

        authenticated = bool(
            user
            and user.is_authenticated
            and user.is_active
        )

        if not authenticated:

            rules.append((
                (
                    "learning_anonymous",
                    client_ip,
                ),
                120,
                60,
            ))

            retry_after = check_rate_limits(rules)

            if retry_after is not None:

                return rate_limit_response(
                    "Too many requests. "
                    "Please try again later.",
                    retry_after,
                )

            # Existing authentication rules will decide
            # whether the endpoint is accessible.

            return None

        # ==============================================
        # AUTHENTICATED USER RATE LIMITS
        # ==============================================

        user_id = str(user.pk)

        is_ai_request = (
            request.method == "POST"
            and action in AI_LIMITS
        )

        if is_ai_request:

            maximum, window = AI_LIMITS[action]

        else:

            maximum, window = GENERAL_LIMITS.get(
                action,
                DEFAULT_LIMIT,
            )

        rules.append((
            (
                "learning_user",
                action,
                user_id,
            ),
            maximum,
            window,
        ))

        # ==============================================
        # GLOBAL AI REQUEST BUDGET
        # ==============================================

        if is_ai_request:

            global_maximum, global_window = (
                GLOBAL_AI_LIMIT
            )

            rules.append((
                (
                    "learning_global_ai",
                ),
                global_maximum,
                global_window,
            ))

        # ==============================================
        # CONCURRENT AI REQUEST PROTECTION
        # ==============================================

        if is_ai_request:

            acquired = _ai_semaphore.acquire(
                blocking=False
            )

            if not acquired:

                return rate_limit_response(
                    "Learning AI is currently processing "
                    "other requests. Please try again shortly.",
                    10,
                )

            request._learning_ai_slot_acquired = True

        # ==============================================
        # APPLY RATE LIMITS
        # ==============================================

        retry_after = check_rate_limits(rules)

        if retry_after is not None:

            return rate_limit_response(
                "You have reached the request limit. "
                "Please try again later.",
                retry_after,
            )

        return None