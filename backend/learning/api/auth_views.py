
import json
import logging

from django.contrib.auth import login, logout
from django.core.exceptions import RequestDataTooBig
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import (
    csrf_protect,
    ensure_csrf_cookie,
)
from django.views.decorators.http import (
    require_GET,
    require_POST,
)

from rest_framework.exceptions import ValidationError

from .serializers import (
    UserSerializer,
    RegisterSerializer,
    LoginSerializer,
)


logger = logging.getLogger(__name__)

MAX_REQUEST_SIZE = 16 * 1024


# ============================================================
# 1. RESPONSE HELPERS
# ============================================================

def success_response(message, data=None, status=200):
    """
    Return a consistent successful API response.
    """

    response_data = {
        "success": True,
        "message": message,
    }

    if data is not None:
        response_data["data"] = data

    return JsonResponse(
        response_data,
        status=status,
    )


def error_response(message, errors=None, status=400):
    """
    Return a consistent error API response.
    """

    response_data = {
        "success": False,
        "message": message,
    }

    if errors is not None:
        response_data["errors"] = errors

    return JsonResponse(
        response_data,
        status=status,
    )


# ============================================================
# 2. JSON REQUEST VALIDATION
# ============================================================

def parse_json_request(request):
    """
    Validate and parse a JSON request body.

    Returns:
        (parsed_data, error_response)
    """

    if request.content_type != "application/json":
        return None, error_response(
            message="Content-Type must be application/json.",
            status=415,
        )

    try:
        content_length = int(
            request.META.get("CONTENT_LENGTH") or 0
        )

    except (TypeError, ValueError):
        return None, error_response(
            message="Invalid request content length.",
            status=400,
        )

    if content_length < 0:
        return None, error_response(
            message="Invalid request content length.",
            status=400,
        )

    if content_length > MAX_REQUEST_SIZE:
        return None, error_response(
            message="Request body is too large.",
            status=413,
        )

    try:
        body = request.body

        if len(body) > MAX_REQUEST_SIZE:
            return None, error_response(
                message="Request body is too large.",
                status=413,
            )

        if not body:
            return None, error_response(
                message="Request body cannot be empty.",
                status=400,
            )

        data = json.loads(body.decode("utf-8"))

    except RequestDataTooBig:
        return None, error_response(
            message="Request body is too large.",
            status=413,
        )

    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, error_response(
            message="Invalid JSON request body.",
            status=400,
        )

    if not isinstance(data, dict):
        return None, error_response(
            message="Request body must be a JSON object.",
            status=400,
        )

    return data, None


# ============================================================
# 3. CSRF TOKEN ENDPOINT
# ============================================================

@never_cache
@require_GET
@ensure_csrf_cookie
def csrf_view(request):
    """
    Provide a CSRF token for frontend requests.

    GET /api/learning/auth/csrf/
    """

    csrf_token = get_token(request)

    return success_response(
        message="CSRF token generated successfully.",
        data={
            "csrf_token": csrf_token,
        },
    )


# ============================================================
# 4. USER REGISTRATION
# ============================================================

@never_cache
@require_POST
@csrf_protect
def register_view(request):
    """
    Register a new Personalized Learning user.

    POST /api/learning/auth/register/
    """

    if request.user.is_authenticated:
        return error_response(
            message="Please log out before registering another account.",
            status=409,
        )

    data, parsing_error = parse_json_request(request)

    if parsing_error is not None:
        return parsing_error

    serializer = RegisterSerializer(data=data)

    if not serializer.is_valid():
        return error_response(
            message="Registration validation failed.",
            errors=serializer.errors,
            status=400,
        )

    try:
        user = serializer.save()

    except ValidationError as exc:
        return error_response(
            message="Registration validation failed.",
            errors=exc.detail,
            status=400,
        )

    logger.info(
        "Learning user registered successfully. User ID: %s",
        user.pk,
    )

    return success_response(
        message="Registration successful. Please log in.",
        data={
            "user": UserSerializer(user).data,
        },
        status=201,
    )


# ============================================================
# 5. USER LOGIN
# ============================================================

@never_cache
@require_POST
@csrf_protect
def login_view(request):
    """
    Authenticate a user and create a Django session.

    POST /api/learning/auth/login/
    """

    if request.user.is_authenticated:
        return error_response(
            message="You are already logged in.",
            status=409,
        )

    data, parsing_error = parse_json_request(request)

    if parsing_error is not None:
        return parsing_error

    serializer = LoginSerializer(
        data=data,
        context={
            "request": request,
        },
    )

    if not serializer.is_valid():
        return error_response(
            message="Login failed.",
            errors=serializer.errors,
            status=400,
        )

    user = serializer.validated_data["user"]

    # Create an authenticated Django session.
    login(request, user)

    # Django rotates the CSRF secret during login.
    # Return a fresh token for subsequent requests.
    csrf_token = get_token(request)

    logger.info(
        "Learning user logged in successfully. User ID: %s",
        user.pk,
    )

    return success_response(
        message="Login successful.",
        data={
            "user": UserSerializer(user).data,
            "is_authenticated": True,
            "csrf_token": csrf_token,
        },
    )


# ============================================================
# 6. USER LOGOUT
# ============================================================

@never_cache
@require_POST
@csrf_protect
def logout_view(request):
    """
    Terminate the current authenticated session.

    POST /api/learning/auth/logout/
    """

    if not request.user.is_authenticated:
        return error_response(
            message="Authentication required.",
            status=401,
        )

    user_id = request.user.pk

    # Flush the authenticated session.
    logout(request)

    logger.info(
        "Learning user logged out successfully. User ID: %s",
        user_id,
    )

    return success_response(
        message="Logout successful.",
        data={
            "is_authenticated": False,
            "csrf_token": get_token(request),
        },
    )


# ============================================================
# 7. CURRENT AUTHENTICATED USER
# ============================================================

@never_cache
@require_GET
def current_user_view(request):
    """
    Retrieve the currently authenticated user.

    GET /api/learning/auth/me/
    """

    if not request.user.is_authenticated:
        return error_response(
            message="Authentication required.",
            status=401,
        )

    return success_response(
        message="Authenticated user retrieved successfully.",
        data={
            "user": UserSerializer(request.user).data,
            "is_authenticated": True,
        },
    )
