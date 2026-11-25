import json
import uuid
import zipfile
import shutil
import stat

from pathlib import Path, PurePosixPath
from threading import Lock

from django.conf import settings
from django.core.exceptions import ValidationError

from .repository_lifecycle import (
    cleanup_expired_repositories,
)


# ==========================================================
# RESOURCE LIMITS
# ==========================================================

MAX_ARCHIVE_SIZE = 50 * 1024 * 1024

MAX_TOTAL_UNCOMPRESSED = 200 * 1024 * 1024

MAX_FILES = 1000

MAX_FILE_SIZE = 5 * 1024 * 1024

MAX_REPOSITORY_STORAGE = 2 * 1024 * 1024 * 1024

MIN_FREE_DISK_SPACE = 1024 * 1024 * 1024

MAX_PATH_LENGTH = 240

READ_BLOCK_SIZE = 64 * 1024


# ==========================================================
# CONCURRENT EXTRACTION PROTECTION
# ==========================================================

_upload_lock = Lock()


# ==========================================================
# SUPPORTED FILE EXTENSIONS
# ==========================================================

ALLOWED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".html",
    ".css",
    ".md",
    ".txt",
    ".yml",
}


# ==========================================================
# IGNORED DIRECTORIES
# ==========================================================

IGNORED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".idea",
    ".vscode",
    "coverage",
    ".ssh",
    ".aws",
    ".gnupg",
}


# ==========================================================
# SENSITIVE FILES
# ==========================================================

SENSITIVE_NAMES = {
    ".env",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "secrets.json",
    "service_account.json",
    "service-account.json",
    "client_secret.json",
    "token.json",
    ".npmrc",
    ".pypirc",
    ".netrc",
}


# ==========================================================
# INTERNAL REPOSITORY FILES
# ==========================================================

RESERVED_INTERNAL_NAMES = {
    "metadata.json",
    "chunks.json",
    "semantic_index.npz",
}


# ==========================================================
# WINDOWS RESERVED FILE NAMES
# ==========================================================

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "CONIN$",
    "CONOUT$",
    *{f"COM{i}" for i in range(1, 10)},
    *{f"LPT{i}" for i in range(1, 10)},
    "COM¹",
    "COM²",
    "COM³",
    "LPT¹",
    "LPT²",
    "LPT³",
}

WINDOWS_INVALID_CHARACTERS = set(
    '<>:"|?*'
)


# ==========================================================
# STORAGE USAGE
# ==========================================================

def get_repository_storage_usage(repositories_root):
    """
    Calculate the current repository storage usage,
    including extracted files and generated artifacts.
    """

    total_size = 0

    if not repositories_root.exists():
        return total_size

    for path in repositories_root.rglob("*"):

        if path.is_symlink():
            continue

        if path.is_file():

            try:

                total_size += path.stat().st_size

            except FileNotFoundError:

                # File may have been removed concurrently.
                continue

    return total_size


# ==========================================================
# STORAGE AVAILABILITY VALIDATION
# ==========================================================

def validate_storage_capacity(
    repositories_root,
    required_bytes,
):
    """
    Prevent new uploads from consuming excessive storage.
    """

    current_usage = get_repository_storage_usage(
        repositories_root
    )

    if (
        current_usage + required_bytes
        > MAX_REPOSITORY_STORAGE
    ):

        raise ValidationError(
            "Repository storage limit has been reached. "
            "Please contact the administrator."
        )

    disk_usage = shutil.disk_usage(
        repositories_root
    )

    if (
        disk_usage.free - required_bytes
        < MIN_FREE_DISK_SPACE
    ):

        raise ValidationError(
            "The server has insufficient available "
            "disk space to process this repository."
        )


# ==========================================================
# WINDOWS PATH VALIDATION
# ==========================================================

def validate_windows_path(path):
    """
    Reject filenames that are unsafe or invalid on Windows.
    """

    for part in path.parts:

        if part.endswith((" ", ".")):

            raise ValidationError(
                "ZIP contains an unsafe filename "
                "ending with a space or period."
            )

        if any(
            character in WINDOWS_INVALID_CHARACTERS
            for character in part
        ):

            raise ValidationError(
                "ZIP contains invalid filename characters."
            )

        if any(
            ord(character) < 32
            for character in part
        ):

            raise ValidationError(
                "ZIP contains invalid control characters."
            )

        base_name = (
            part.split(".", 1)[0]
            .rstrip(" ")
            .upper()
        )

        if base_name in WINDOWS_RESERVED_NAMES:

            raise ValidationError(
                "ZIP contains a reserved Windows filename."
            )


# ==========================================================
# ARCHIVE PATH VALIDATION
# ==========================================================

def validate_archive_path(filename):
    """
    Validate ZIP entry paths before extracting files.
    """

    if not filename:

        raise ValidationError(
            "ZIP contains an empty filename."
        )

    if "\x00" in filename or "\\" in filename:

        raise ValidationError(
            "ZIP contains an unsafe file path."
        )

    path = PurePosixPath(filename)

    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.parts
    ):

        raise ValidationError(
            "ZIP contains an unsafe file path."
        )

    if len(path.as_posix()) > MAX_PATH_LENGTH:

        raise ValidationError(
            "ZIP contains an excessively long file path."
        )

    validate_windows_path(path)

    return path


# ==========================================================
# SENSITIVE FILE DETECTION
# ==========================================================

def is_sensitive_file(path):

    name = path.name.lower()

    if name in SENSITIVE_NAMES:
        return True

    if name.startswith(".env"):
        return True

    if name.startswith("client_secret"):
        return True

    if name.startswith("service_account"):
        return True

    if path.suffix.lower() in {
        ".pem",
        ".key",
        ".p12",
        ".pfx",
    }:

        return True

    return False


# ==========================================================
# IGNORED DIRECTORY DETECTION
# ==========================================================

def is_ignored_path(path):

    return any(
        part.lower() in IGNORED_PARTS
        for part in path.parts
    )


# ==========================================================
# INTERNAL FILE COLLISION DETECTION
# ==========================================================

def is_reserved_internal_path(path):
    """
    Protect generated repository artifacts at the root
    of the extracted repository.

    Nested project files with these names remain supported.
    """

    return (
        bool(path.parts)
        and path.parts[0].lower()
        in RESERVED_INTERNAL_NAMES
    )


# ==========================================================
# ZIP ENTRY TYPE VALIDATION
# ==========================================================

def validate_entry_type(entry):
    """
    Reject symbolic links, special files and encrypted entries.
    """

    unix_mode = (
        entry.external_attr >> 16
    ) & 0o170000

    if unix_mode == stat.S_IFLNK:

        raise ValidationError(
            "Symbolic links are not permitted."
        )

    if unix_mode not in {
        0,
        stat.S_IFREG,
        stat.S_IFDIR,
    }:

        raise ValidationError(
            "ZIP contains an unsupported special file."
        )

    if entry.flag_bits & 0x1:

        raise ValidationError(
            "Encrypted ZIP entries are not supported."
        )


# ==========================================================
# SAFE REPOSITORY EXTRACTION
# ==========================================================

def safe_extract_repository(uploaded_file):
    """
    Validate and safely extract an uploaded repository ZIP.

    Returns:
        {
            "repository_id": "...",
            "files": [...],
            "skipped_files": [...]
        }

    No uploaded source code is executed.
    """

    if uploaded_file.size <= 0:

        raise ValidationError(
            "The uploaded ZIP file is empty."
        )

    if uploaded_file.size > MAX_ARCHIVE_SIZE:

        raise ValidationError(
            "ZIP file must be 50 MB or smaller."
        )

    acquired = _upload_lock.acquire(
        blocking=False
    )

    if not acquired:

        raise ValidationError(
            "Another repository is currently being "
            "extracted. Please try again shortly."
        )

    try:

        # Remove expired repositories before checking
        # storage capacity and extracting a new upload.

        cleanup_expired_repositories()

        return _extract_repository(uploaded_file)

    finally:

        _upload_lock.release()


# ==========================================================
# INTERNAL EXTRACTION IMPLEMENTATION
# ==========================================================

def _extract_repository(uploaded_file):

    repository_id = str(uuid.uuid4())

    base_dir = Path(
        settings.MEDIA_ROOT
    ).resolve()

    repositories_root = (
        base_dir / "repositories"
    ).resolve()

    repositories_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    repository_dir = (
        repositories_root / repository_id
    ).resolve()

    accepted_files = []

    skipped_files = []

    accepted_entries = []

    seen_paths = set()

    file_paths = set()

    directory_paths = set()

    total_declared_size = 0

    total_accepted_size = 0

    total_actual_size = 0

    repository_created = False

    try:

        with zipfile.ZipFile(uploaded_file) as archive:

            entries = archive.infolist()

            # ==============================================
            # VALIDATE ENTRY COUNT
            # ==============================================

            if len(entries) > MAX_FILES:

                raise ValidationError(
                    "ZIP contains too many entries. "
                    "Maximum allowed: 1000."
                )

            # ==============================================
            # VALIDATE EVERY ARCHIVE ENTRY
            # ==============================================

            for entry in entries:

                path = validate_archive_path(
                    entry.orig_filename
                )

                validate_entry_type(entry)

                relative_path = path.as_posix()

                normalized_path = (
                    relative_path.casefold()
                )

                # Prevent duplicate paths on Windows.

                if normalized_path in seen_paths:

                    raise ValidationError(
                        "ZIP contains duplicate or "
                        "case-conflicting file paths."
                    )

                seen_paths.add(normalized_path)

                # Prevent file/directory path conflicts.

                parent_paths = {
                    parent.as_posix().casefold()
                    for parent in path.parents
                    if parent.as_posix() != "."
                }

                if parent_paths & file_paths:

                    raise ValidationError(
                        "ZIP contains conflicting "
                        "file and directory paths."
                    )

                directory_paths.update(
                    parent_paths
                )

                if entry.is_dir():

                    if normalized_path in file_paths:

                        raise ValidationError(
                            "ZIP contains conflicting "
                            "file and directory paths."
                        )

                    directory_paths.add(
                        normalized_path
                    )

                    continue

                if normalized_path in directory_paths:

                    raise ValidationError(
                        "ZIP contains conflicting "
                        "file and directory paths."
                    )

                file_paths.add(normalized_path)

                # ==========================================
                # VALIDATE DECLARED UNCOMPRESSED SIZE
                # ==========================================

                total_declared_size += entry.file_size

                if (
                    total_declared_size
                    > MAX_TOTAL_UNCOMPRESSED
                ):

                    raise ValidationError(
                        "Extracted content would exceed "
                        "the 200 MB limit."
                    )

                # ==========================================
                # INDIVIDUAL FILE SIZE
                # ==========================================

                if entry.file_size > MAX_FILE_SIZE:

                    skipped_files.append({
                        "path": relative_path,
                        "reason": (
                            "File exceeds 5 MB limit"
                        ),
                    })

                    continue

                # ==========================================
                # PROTECT INTERNAL ARTIFACTS
                # ==========================================

                if is_reserved_internal_path(path):

                    skipped_files.append({
                        "path": relative_path,
                        "reason": (
                            "Reserved repository filename"
                        ),
                    })

                    continue

                # ==========================================
                # IGNORE SENSITIVE FILES AND DIRECTORIES
                # ==========================================

                if (
                    is_ignored_path(path)
                    or is_sensitive_file(path)
                ):

                    skipped_files.append({
                        "path": relative_path,
                        "reason": (
                            "Ignored folder or "
                            "sensitive filename"
                        ),
                    })

                    continue

                # ==========================================
                # VALIDATE FILE EXTENSION
                # ==========================================

                if (
                    path.suffix.lower()
                    not in ALLOWED_EXTENSIONS
                ):

                    skipped_files.append({
                        "path": relative_path,
                        "reason": (
                            "Unsupported file type"
                        ),
                    })

                    continue

                accepted_entries.append(
                    (entry, path)
                )

                total_accepted_size += (
                    entry.file_size
                )

            # ==============================================
            # VERIFY SUPPORTED FILES EXIST
            # ==============================================

            if not accepted_entries:

                raise ValidationError(
                    "No supported source or text "
                    "files were found."
                )

            # ==============================================
            # CHECK AVAILABLE STORAGE
            # ==============================================

            validate_storage_capacity(
                repositories_root,
                total_accepted_size,
            )

            # ==============================================
            # CREATE REPOSITORY DIRECTORY
            # ==============================================

            repository_dir.mkdir(
                parents=True,
                exist_ok=False,
            )

            repository_created = True

            # ==============================================
            # EXTRACT ACCEPTED FILES
            # ==============================================

            for entry, path in accepted_entries:

                relative_path = path.as_posix()

                destination = (
                    repository_dir
                    / Path(*path.parts)
                ).resolve()

                if not destination.is_relative_to(
                    repository_dir
                ):

                    raise ValidationError(
                        "Unsafe destination path."
                    )

                destination.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                actual_file_size = 0

                with archive.open(entry) as source:

                    with destination.open("xb") as target:

                        while True:

                            block = source.read(
                                READ_BLOCK_SIZE
                            )

                            if not block:
                                break

                            block_size = len(block)

                            actual_file_size += block_size

                            total_actual_size += block_size

                            # Validate actual bytes instead
                            # of trusting ZIP metadata alone.

                            if (
                                actual_file_size
                                > MAX_FILE_SIZE
                            ):

                                raise ValidationError(
                                    "Extracted file exceeds "
                                    "the 5 MB limit."
                                )

                            if (
                                total_actual_size
                                > MAX_TOTAL_UNCOMPRESSED
                            ):

                                raise ValidationError(
                                    "Extracted repository "
                                    "exceeds the 200 MB limit."
                                )

                            if (
                                actual_file_size
                                > entry.file_size
                            ):

                                raise ValidationError(
                                    "ZIP contains inconsistent "
                                    "file size information."
                                )

                            target.write(block)

                # ==========================================
                # VERIFY EXTRACTED FILE SIZE
                # ==========================================

                if actual_file_size != entry.file_size:

                    raise ValidationError(
                        "ZIP contains inconsistent "
                        "file size information."
                    )

                # ==========================================
                # VERIFY UTF-8 TEXT CONTENT
                # ==========================================

                try:

                    destination.read_text(
                        encoding="utf-8"
                    )

                except UnicodeDecodeError:

                    destination.unlink(
                        missing_ok=True
                    )

                    skipped_files.append({
                        "path": relative_path,
                        "reason": (
                            "File is not valid UTF-8 text"
                        ),
                    })

                    continue

                accepted_files.append(
                    relative_path
                )

            # ==============================================
            # VERIFY VALID SOURCE FILES REMAIN
            # ==============================================

            if not accepted_files:

                raise ValidationError(
                    "No valid UTF-8 source or text "
                    "files were found."
                )

            # ==============================================
            # CREATE REPOSITORY METADATA
            # ==============================================

            metadata = {
                "repository_id": repository_id,
                "files": accepted_files,
                "skipped_files": skipped_files,
            }

            metadata_path = (
                repository_dir / "metadata.json"
            )

            with metadata_path.open(
                "x",
                encoding="utf-8",
            ) as metadata_file:

                json.dump(
                    metadata,
                    metadata_file,
                    indent=2,
                )

        return metadata

    # ======================================================
    # ERROR HANDLING AND CLEANUP
    # ======================================================

    except ValidationError:

        if repository_created:

            shutil.rmtree(
                repository_dir,
                ignore_errors=True,
            )

        raise

    except (
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        OSError,
        RuntimeError,
        ValueError,
        NotImplementedError,
    ) as exc:

        if repository_created:

            shutil.rmtree(
                repository_dir,
                ignore_errors=True,
            )

        raise ValidationError(
            "Could not process this ZIP file safely."
        ) from exc

    except Exception:

        if repository_created:

            shutil.rmtree(
                repository_dir,
                ignore_errors=True,
            )

        raise