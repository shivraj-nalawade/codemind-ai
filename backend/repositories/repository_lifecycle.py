import logging
import shutil
import time

from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from uuid import UUID

from django.conf import settings


logger = logging.getLogger(__name__)


# ==========================================================
# CLEANUP CONFIGURATION
# ==========================================================

REPOSITORY_RETENTION_SECONDS = 24 * 60 * 60

CLEANUP_INTERVAL_SECONDS = 60 * 60

ACTIVITY_FILENAME = ".last_activity"


# ==========================================================
# THREAD-SAFE LIFECYCLE STATE
# ==========================================================

_lifecycle_lock = RLock()

_active_repositories = {}

_last_cleanup = None


# ==========================================================
# REPOSITORY DIRECTORY
# ==========================================================

def get_repositories_root():

    return (
        Path(settings.MEDIA_ROOT)
        / "repositories"
    ).resolve()


def get_repository_directory(repository_id):

    safe_id = str(UUID(str(repository_id)))

    root = get_repositories_root()

    directory = root / safe_id

    if directory.is_symlink():

        raise ValueError(
            "Symbolic repository paths are not permitted."
        )

    directory = directory.resolve()

    if not directory.is_relative_to(root):

        raise ValueError(
            "Invalid repository directory."
        )

    return directory


# ==========================================================
# UPDATE REPOSITORY ACTIVITY
# ==========================================================

def touch_repository(repository_id):
    """
    Update the last activity timestamp of a repository.
    """

    with _lifecycle_lock:

        directory = get_repository_directory(
            repository_id
        )

        if not directory.is_dir():

            return False

        if not (
            directory / "metadata.json"
        ).is_file():

            return False

        activity_file = (
            directory / ACTIVITY_FILENAME
        )

        if activity_file.is_symlink():

            raise ValueError(
                "Invalid repository activity file."
            )

        activity_file.touch(exist_ok=True)

        return True


# ==========================================================
# GET LAST ACTIVITY
# ==========================================================

def get_last_activity(directory):

    activity_file = (
        directory / ACTIVITY_FILENAME
    )

    if (
        activity_file.is_file()
        and not activity_file.is_symlink()
    ):

        return activity_file.stat().st_mtime

    metadata_file = (
        directory / "metadata.json"
    )

    if metadata_file.is_file():

        return metadata_file.stat().st_mtime

    return directory.stat().st_mtime


# ==========================================================
# PROTECT ACTIVE REPOSITORIES
# ==========================================================

@contextmanager
def repository_in_use(repository_id):
    """
    Prevent cleanup while a repository request is running.
    """

    safe_id = str(UUID(str(repository_id)))

    with _lifecycle_lock:

        _active_repositories[safe_id] = (
            _active_repositories.get(safe_id, 0) + 1
        )

    try:

        yield

    finally:

        with _lifecycle_lock:

            remaining = (
                _active_repositories.get(safe_id, 1) - 1
            )

            if remaining <= 0:

                _active_repositories.pop(
                    safe_id,
                    None,
                )

            else:

                _active_repositories[safe_id] = (
                    remaining
                )


# ==========================================================
# CLEANUP EXPIRED REPOSITORIES
# ==========================================================

def cleanup_expired_repositories(force=False):
    """
    Delete expired repositories that are not currently in use.

    Cleanup is performed at most once per hour unless forced.
    """

    global _last_cleanup

    with _lifecycle_lock:

        monotonic_now = time.monotonic()

        if (
            not force
            and _last_cleanup is not None
            and monotonic_now - _last_cleanup
            < CLEANUP_INTERVAL_SECONDS
        ):

            return {
                "deleted": 0,
                "active_skipped": 0,
                "failed": 0,
                "cleanup_skipped": True,
            }

        _last_cleanup = monotonic_now

        root = get_repositories_root()

        result = {
            "deleted": 0,
            "active_skipped": 0,
            "failed": 0,
            "cleanup_skipped": False,
        }

        if not root.exists():

            return result

        current_time = time.time()

        for directory in root.iterdir():

            if directory.is_symlink():

                continue

            if not directory.is_dir():

                continue

            # Only process UUID-named repository directories.

            try:

                repository_id = str(
                    UUID(directory.name)
                )

            except ValueError:

                continue

            if directory.name != repository_id:

                continue

            # Never delete repositories currently in use.

            if repository_id in _active_repositories:

                result["active_skipped"] += 1

                continue

            try:

                # Ignore incomplete uploads. They are handled
                # by the ZIP extraction service.

                if not (
                    directory / "metadata.json"
                ).is_file():

                    continue

                last_activity = get_last_activity(
                    directory
                )

                inactive_seconds = (
                    current_time - last_activity
                )

                if (
                    inactive_seconds
                    < REPOSITORY_RETENTION_SECONDS
                ):

                    continue

                # Final directory containment check.

                safe_directory = (
                    get_repository_directory(
                        repository_id
                    )
                )

                shutil.rmtree(safe_directory)

                result["deleted"] += 1

                logger.info(
                    "Deleted expired repository: %s",
                    repository_id,
                )

            except (OSError, ValueError):

                result["failed"] += 1

                logger.exception(
                    "Could not clean repository: %s",
                    repository_id,
                )

        return result