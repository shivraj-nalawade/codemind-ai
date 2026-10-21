
import json
import uuid
import zipfile

from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.exceptions import ValidationError


MAX_ARCHIVE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_TOTAL_UNCOMPRESSED = 30 * 1024 * 1024  # 30 MB
MAX_FILES = 500
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB per file

ALLOWED_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".json", ".html", ".css", ".md", ".txt", ".yml",
}

IGNORED_PARTS = {
    ".git", ".venv", "venv", "__pycache__",
    "node_modules", "dist", "build", ".idea",
    ".vscode", "coverage",
}

SENSITIVE_NAMES = {
    ".env", "id_rsa", "id_ed25519",
    "credentials.json", "secrets.json",
}


def safe_extract_repository(uploaded_file):
    if uploaded_file.size > MAX_ARCHIVE_SIZE:
        raise ValidationError("ZIP file must be 10 MB or smaller.")

    repository_id = str(uuid.uuid4())

    base_dir = Path(settings.MEDIA_ROOT).resolve()
    repository_dir = base_dir / "repositories" / repository_id
    repository_dir.mkdir(parents=True, exist_ok=False)

    accepted_files = []
    skipped_files = []
    total_size = 0
    seen_paths = set()

    try:
        with zipfile.ZipFile(uploaded_file) as archive:
            entries = archive.infolist()

            if len(entries) > MAX_FILES:
                raise ValidationError("ZIP contains too many entries.")

            # Validate all entries before extracting any content.
            for entry in entries:
                path = PurePosixPath(entry.filename)

                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or "\\" in entry.filename
                    or "\x00" in entry.filename
                ):
                    raise ValidationError(
                        "ZIP contains an unsafe file path."
                    )

                unix_mode = (entry.external_attr >> 16) & 0o170000
                if unix_mode == 0o120000:
                    raise ValidationError(
                        "Symbolic links are not permitted."
                    )

                if entry.flag_bits & 0x1:
                    raise ValidationError(
                        "Encrypted ZIP entries are not supported."
                    )

                if entry.is_dir():
                    continue

                relative_path = path.as_posix()

                if relative_path in seen_paths:
                    raise ValidationError(
                        "ZIP contains duplicate file paths."
                    )
                seen_paths.add(relative_path)

                if entry.file_size > MAX_FILE_SIZE:
                    skipped_files.append({
                        "path": relative_path,
                        "reason": "File exceeds 2 MB limit",
                    })
                    continue

                total_size += entry.file_size
                if total_size > MAX_TOTAL_UNCOMPRESSED:
                    raise ValidationError(
                        "Extracted content would exceed 30 MB."
                    )

                if (
                    any(part.lower() in IGNORED_PARTS
                        for part in path.parts)
                    or path.name.lower() in SENSITIVE_NAMES
                    or path.name.lower().startswith(".env")
                ):
                    skipped_files.append({
                        "path": relative_path,
                        "reason": "Ignored folder or sensitive filename",
                    })
                    continue

                if path.suffix.lower() not in ALLOWED_EXTENSIONS:
                    skipped_files.append({
                        "path": relative_path,
                        "reason": "Unsupported file type",
                    })
                    continue

                accepted_files.append(relative_path)

            if not accepted_files:
                raise ValidationError(
                    "No supported source or text files were found."
                )

            # Read individual accepted files. Never call extractall().
            for relative_path in accepted_files:
                info = next(
                    item for item in entries
                    if PurePosixPath(item.filename).as_posix()
                    == relative_path
                )

                destination = (
                    repository_dir / Path(*PurePosixPath(relative_path).parts)
                ).resolve()

                if not destination.is_relative_to(repository_dir):
                    raise ValidationError("Unsafe destination path.")

                destination.parent.mkdir(parents=True, exist_ok=True)

                with archive.open(info) as source:
                    with destination.open("xb") as target:
                        while True:
                            block = source.read(64 * 1024)
                            if not block:
                                break
                            target.write(block)

                try:
                    destination.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    destination.unlink(missing_ok=True)
                    skipped_files.append({
                        "path": relative_path,
                        "reason": "File is not valid UTF-8 text",
                    })

            accepted_files = [
                path for path in accepted_files
                if (repository_dir / Path(*PurePosixPath(path).parts)).is_file()
            ]

            metadata = {
                "repository_id": repository_id,
                "files": accepted_files,
                "skipped_files": skipped_files,
            }

            (repository_dir / "metadata.json").write_text(
                json.dumps(metadata, indent=2),
                encoding="utf-8",
            )

        return metadata

    except (zipfile.BadZipFile, OSError, RuntimeError, ValueError) as exc:
        import shutil
        shutil.rmtree(repository_dir, ignore_errors=True)
        raise ValidationError(
            "Could not process this ZIP file safely."
        ) from exc

    except Exception:
        import shutil
        shutil.rmtree(repository_dir, ignore_errors=True)
        raise
