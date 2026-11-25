import logging

from functools import wraps

from django.http import JsonResponse
from django.views.decorators.cache import never_cache

from .repository_lifecycle import (
    touch_repository,
    repository_in_use,
    cleanup_expired_repositories,
)


logger = logging.getLogger(__name__)


SESSION_REPOSITORIES_KEY = "anonymous_repositories"


# ==========================================================
# REGISTER REPOSITORY ACCESS
# ==========================================================

def register_repository_access(request, repository_id):

    repositories = request.session.get(
        SESSION_REPOSITORIES_KEY,
        [],
    )

    repository_id = str(repository_id)

    if repository_id not in repositories:

        repositories.append(repository_id)

    request.session[SESSION_REPOSITORIES_KEY] = (
        repositories
    )

    request.session.modified = True

    # Initialize repository activity.

    try:

        with repository_in_use(repository_id):

            touch_repository(repository_id)

    except (OSError, ValueError):

        logger.exception(
            "Could not initialize repository activity."
        )


# ==========================================================
# REMOVE EXPIRED SESSION ACCESS
# ==========================================================

def remove_repository_access(request, repository_id):

    repositories = request.session.get(
        SESSION_REPOSITORIES_KEY,
        [],
    )

    repository_id = str(repository_id)

    request.session[SESSION_REPOSITORIES_KEY] = [
        item
        for item in repositories
        if item != repository_id
    ]

    request.session.modified = True


# ==========================================================
# REPOSITORY ACCESS PROTECTION
# ==========================================================

def repository_access_required(view_func):

    @wraps(view_func)
    @never_cache
    def wrapper(
        request,
        repository_id,
        *args,
        **kwargs,
    ):

        repository_id_string = str(repository_id)

        repositories = request.session.get(
            SESSION_REPOSITORIES_KEY,
            [],
        )

        # Validate anonymous browser session access.

        if repository_id_string not in repositories:

            return JsonResponse(
                {
                    "error": (
                        "Repository not found or session expired. "
                        "Please upload your repository again."
                    )
                },
                status=404,
            )

        # Clean expired repositories before extending activity.

        try:

            cleanup_expired_repositories()

        except OSError:

            logger.exception(
                "Repository cleanup failed."
            )

        # Protect the repository throughout the request.

        with repository_in_use(repository_id_string):

            try:

                exists = touch_repository(
                    repository_id_string
                )

            except (OSError, ValueError):

                logger.exception(
                    "Could not update repository activity."
                )

                return JsonResponse(
                    {
                        "error": (
                            "Could not access this repository."
                        )
                    },
                    status=500,
                )

            if not exists:

                remove_repository_access(
                    request,
                    repository_id_string,
                )

                return JsonResponse(
                    {
                        "error": (
                            "Repository expired or was removed. "
                            "Please upload your repository again."
                        )
                    },
                    status=404,
                )

            try:

                return view_func(
                    request,
                    repository_id,
                    *args,
                    **kwargs,
                )

            finally:

                # Update activity when processing finishes.

                try:

                    touch_repository(
                        repository_id_string
                    )

                except (OSError, ValueError):

                    logger.exception(
                        "Could not update final repository activity."
                    )

    return wrapper