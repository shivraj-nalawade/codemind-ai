import json
import re

from pathlib import Path
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .hybrid_search import hybrid_search
from .llm_service import generate_answer
from .parser import parse_repository, save_chunks
from .retrieval import load_chunks, search_chunks
from .semantic_search import build_semantic_index, semantic_search
from .services import safe_extract_repository

from .permissions import (
    register_repository_access,
    repository_access_required,
)

from .rate_limits import (
    rate_limit,
    limit_llm_requests,
    limit_indexing_requests,
)


# Keep this aligned with MAX_CHUNK_CONTENT in llm_service.py.
MAX_DIRECT_FILE_CHARS = 12000


# ==========================================================
# SPECIFIC FILE EVIDENCE
# ==========================================================

def get_requested_file_evidence(repository_dir, question):
    """
    Find a uniquely referenced repository file and read its complete
    contents with original line numbers.

    Returns None if:
    - No supported filename is mentioned.
    - The filename is ambiguous.
    - The file is outside the repository.
    - The file cannot be read.
    - The file exceeds the evidence size limit.
    """

    root = Path(repository_dir).resolve()
    metadata_path = root / "metadata.json"

    try:
        metadata = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None

    available_files = metadata.get("files", [])

    if not isinstance(available_files, list):
        return None

    filename_pattern = re.compile(
        r"(?<![\w.-])"
        r"([A-Za-z0-9_.-]+(?:[/\\][A-Za-z0-9_.-]+)*"
        r"\.(?:py|js|jsx|ts|tsx|html|css|json|md|java|cpp|c|h|cs|go|rs))"
        r"(?![\w.-])",
        re.IGNORECASE,
    )

    mentions = filename_pattern.findall(question)

    if not mentions:
        return None

    candidates = []

    for mention in mentions:

        normalized_mention = mention.replace("\\", "/").lower()

        matches = []

        for relative_path in available_files:

            if not isinstance(relative_path, str):
                continue

            normalized_path = (
                relative_path.replace("\\", "/").lower()
            )

            exact_match = normalized_path == normalized_mention

            basename_match = (
                Path(normalized_path).name
                == Path(normalized_mention).name
            )

            if exact_match or basename_match:
                matches.append(relative_path)

        # Only accept a filename when it identifies one file.
        if len(matches) == 1:
            candidates.append(matches[0])

    unique_candidates = list(dict.fromkeys(candidates))

    # Do not guess when multiple files are mentioned or matched.
    if len(unique_candidates) != 1:
        return None

    relative_path = unique_candidates[0]

    file_path = (root / relative_path).resolve()

    # Prevent reading files outside the repository directory.
    if not file_path.is_relative_to(root):
        return None

    if not file_path.is_file():
        return None

    try:
        source = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None

    # Do not label truncated content as complete-file evidence.
    if len(source) > MAX_DIRECT_FILE_CHARS:
        return None

    lines = source.splitlines()

    return {
        "file_path": relative_path.replace("\\", "/"),
        "chunk_type": "complete_file",
        "name": Path(relative_path).name,
        "start_line": 1,
        "end_line": len(lines),
        "content": source,
        "parent_class": None,
        "parent_function": None,
        "signature": "",
        "imports": [],
    }


# ==========================================================
# PROJECT OVERVIEW QUESTION DETECTION
# ==========================================================

def is_project_overview_question(question):
    """
    Identify broad questions that need evidence from multiple
    repository areas rather than only the top search results.
    """

    text = question.lower()

    overview_phrases = [
        "explain the project",
        "explain this project",
        "project overview",
        "describe the project",
        "how does this project work",
        "explain the application",
        "project architecture",
        "explain the repository",
        "overview of the project",
    ]

    return any(
        phrase in text
        for phrase in overview_phrases
    )


# ==========================================================
# PROJECT OVERVIEW EVIDENCE
# ==========================================================

def get_project_overview_evidence(repository_dir):
    """
    Collect relevant evidence from different repository areas.

    Supports:
    - Application source code
    - Frontend templates and source files
    - Training notebooks
    - Dependency manifests
    - Deployment configuration
    - Project documentation

    This function does not change hybrid-search ranking.
    """

    root = Path(repository_dir).resolve()
    metadata_path = root / "metadata.json"

    MAX_FILE_CHARS = 6000
    MAX_TOTAL_CHARS = 36000
    MAX_FILES = 8

    try:
        metadata = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return []

    available_files = metadata.get("files", [])

    if not isinstance(available_files, list):
        return []

    # Select files by their purpose, not by a particular project name.
    selected = []

    def add_file(relative_path, priority):

        if not isinstance(relative_path, str):
            return

        normalized = relative_path.replace("\\", "/")

        if (
            normalized.startswith("/")
            or ".." in Path(normalized).parts
        ):
            return

        selected.append((priority, normalized))

    for relative_path in available_files:

        if not isinstance(relative_path, str):
            continue

        path = Path(relative_path.replace("\\", "/"))

        name = path.name.lower()
        suffix = path.suffix.lower()
        parts = [part.lower() for part in path.parts]

        # Project documentation
        if name in {
            "readme.md",
            "readme.txt",
            "readme.rst",
        }:
            add_file(relative_path, 1)

        # Dependency declarations
        elif (
            name in {
                "requirements.txt",
                "pyproject.toml",
                "pipfile",
                "package.json",
                "cargo.toml",
                "go.mod",
                "pom.xml",
                "build.gradle",
                "composer.json",
            }
            or name.startswith("requirements-")
        ):
            add_file(relative_path, 2)

        # Deployment configuration
        elif (
            name in {
                "dockerfile",
                "docker-compose.yml",
                "docker-compose.yaml",
                "render.yaml",
                "render.yml",
                "vercel.json",
                "netlify.toml",
                "Procfile".lower(),
            }
            or name.startswith("docker-compose.")
            or name.startswith("compose.")
            or "deploy" in name
        ):
            add_file(relative_path, 3)

        # Model training notebooks
        elif suffix == ".ipynb":
            add_file(relative_path, 4)

        # Common application entry points
        elif name in {
            "app.py",
            "main.py",
            "manage.py",
            "server.py",
            "index.js",
            "server.js",
            "main.js",
            "app.js",
            "program.cs",
            "main.go",
            "main.rs",
        }:
            add_file(relative_path, 5)

        # Frontend templates and application pages
        elif (
            suffix in {
                ".html",
                ".jsx",
                ".tsx",
                ".vue",
                ".svelte",
            }
            and any(
                part in {
                    "templates",
                    "views",
                    "pages",
                    "src",
                }
                for part in parts[:-1]
            )
        ):
            add_file(relative_path, 6)

    # Remove duplicate paths and preserve priority.
    selected = sorted(
        set(selected),
        key=lambda item: (
            item[0],
            item[1].lower(),
        ),
    )

    evidence = []
    total_chars = 0

    for _, relative_path in selected:

        if len(evidence) >= MAX_FILES:
            break

        file_path = (root / relative_path).resolve()

        # Never read outside the repository.
        if not file_path.is_relative_to(root):
            continue

        if not file_path.is_file():
            continue

        try:
            raw_content = file_path.read_text(
                encoding="utf-8"
            )
        except (OSError, UnicodeError):
            continue

        # Convert notebook JSON into readable cell evidence.
        if file_path.suffix.lower() == ".ipynb":

            try:
                notebook = json.loads(raw_content)

                formatted_cells = []

                for cell_number, cell in enumerate(
                    notebook.get("cells", []),
                    start=1,
                ):

                    cell_type = cell.get(
                        "cell_type",
                        "unknown",
                    )

                    source = cell.get("source", [])

                    if isinstance(source, list):
                        source = "".join(source)

                    if (
                        not isinstance(source, str)
                        or not source.strip()
                    ):
                        continue

                    formatted_cells.append(
                        f"\n--- Notebook Cell {cell_number} "
                        f"({cell_type}) ---\n{source}"
                    )

                content = "".join(formatted_cells)

            except (ValueError, TypeError, AttributeError):
                continue

        else:
            content = raw_content

        remaining = MAX_TOTAL_CHARS - total_chars

        if remaining <= 0:
            break

        # Preserve the fact that evidence was truncated.
        if len(content) > MAX_FILE_CHARS:

            content = (
                content[:MAX_FILE_CHARS]
                + "\n\n[Evidence truncated: file exceeds the "
                "per-file evidence limit.]"
            )

        if len(content) > remaining:

            content = (
                content[:remaining]
                + "\n\n[Evidence truncated: total evidence limit reached.]"
            )

        if not content.strip():
            continue

        lines = content.splitlines()

        evidence.append({
            "file_path": relative_path,
            "chunk_type": "project_overview_file",
            "name": file_path.name,
            "start_line": 1,
            "end_line": len(lines),
            "content": content,
            "parent_class": None,
            "parent_function": None,
            "signature": "",
            "imports": [],
        })

        total_chars += len(content)

    return evidence


# ==========================================================
# REPOSITORY UPLOAD
# ==========================================================

@require_POST
@rate_limit(
    "upload",
    max_requests=5,
    window_seconds=3600,
)
def upload_repository(request):

    uploaded_file = request.FILES.get("file")

    if not uploaded_file:

        return JsonResponse(
            {
                "error": (
                    "Please upload a ZIP file using "
                    "the 'file' field."
                )
            },
            status=400,
        )

    if not uploaded_file.name.lower().endswith(".zip"):

        return JsonResponse(
            {
                "error": "Only ZIP files are supported."
            },
            status=400,
        )

    try:

        result = safe_extract_repository(uploaded_file)

        # Associate the repository with the current anonymous
        # browser session. No user login is required.
        register_repository_access(
            request,
            result["repository_id"],
        )

        return JsonResponse(
            {
                "message": "Repository uploaded successfully.",
                **result,
                "file_count": len(result["files"]),
            },
            status=201,
        )

    except ValidationError as exc:

        return JsonResponse(
            {
                "error": exc.messages,
            },
            status=400,
        )


# ==========================================================
# REPOSITORY PARSING
# ==========================================================

@require_POST
@repository_access_required
@rate_limit(
    "parse",
    max_requests=10,
    window_seconds=3600,
)
def parse_repository_view(request, repository_id):

    repository_dir = (
        Path(settings.MEDIA_ROOT)
        / "repositories"
        / str(repository_id)
    ).resolve()

    repositories_root = (
        Path(settings.MEDIA_ROOT)
        / "repositories"
    ).resolve()

    if not repository_dir.is_relative_to(repositories_root):

        return JsonResponse(
            {
                "error": "Invalid repository ID."
            },
            status=400,
        )

    metadata_path = repository_dir / "metadata.json"

    if (
        not repository_dir.is_dir()
        or not metadata_path.is_file()
    ):

        return JsonResponse(
            {
                "error": "Repository not found."
            },
            status=404,
        )

    try:

        metadata = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )

        chunks = parse_repository(
            repository_dir,
            metadata,
        )

        save_chunks(
            repository_dir,
            chunks,
        )

        return JsonResponse({
            "message": "Repository parsed successfully.",
            "repository_id": str(repository_id),
            "chunk_count": len(chunks),
            "chunks": chunks,
        })

    except (OSError, ValueError, KeyError, TypeError):

        return JsonResponse(
            {
                "error": "Could not parse this repository."
            },
            status=500,
        )


# ==========================================================
# BM25 KEYWORD SEARCH
# ==========================================================

@require_GET
@repository_access_required
@rate_limit(
    "search",
    max_requests=30,
    window_seconds=60,
)
def search_repository(request, repository_id):

    query = request.GET.get("q", "").strip()

    if not query:

        return JsonResponse(
            {
                "error": (
                    "Please provide a search query "
                    "using ?q=..."
                )
            },
            status=400,
        )

    if len(query) > 500:

        return JsonResponse(
            {
                "error": (
                    "Search query must be "
                    "500 characters or fewer."
                )
            },
            status=400,
        )

    try:

        top_k = int(
            request.GET.get("top_k", "5")
        )

    except ValueError:

        return JsonResponse(
            {
                "error": "top_k must be an integer."
            },
            status=400,
        )

    if not 1 <= top_k <= 10:

        return JsonResponse(
            {
                "error": "top_k must be between 1 and 10."
            },
            status=400,
        )

    repositories_root = (
        Path(settings.MEDIA_ROOT)
        / "repositories"
    ).resolve()

    try:

        safe_id = UUID(str(repository_id))

    except ValueError:

        return JsonResponse(
            {
                "error": "Invalid repository ID."
            },
            status=400,
        )

    repository_dir = (
        repositories_root / str(safe_id)
    ).resolve()

    if not repository_dir.is_relative_to(repositories_root):

        return JsonResponse(
            {
                "error": "Invalid repository ID."
            },
            status=400,
        )

    metadata_path = repository_dir / "metadata.json"

    if (
        not repository_dir.is_dir()
        or not metadata_path.is_file()
    ):

        return JsonResponse(
            {
                "error": "Repository not found."
            },
            status=404,
        )

    try:

        chunks = load_chunks(repository_dir)

        results = search_chunks(
            chunks,
            query,
            top_k,
        )

        # Do not delete the semantic index during BM25 search.

        return JsonResponse({
            "repository_id": str(safe_id),
            "query": query,
            "result_count": len(results),
            "results": results,
        })

    except FileNotFoundError:

        return JsonResponse(
            {
                "error": (
                    "Repository has not been parsed yet."
                )
            },
            status=409,
        )

    except (OSError, ValueError, TypeError):

        return JsonResponse(
            {
                "error": "Could not search this repository."
            },
            status=500,
        )


# ==========================================================
# SEMANTIC INDEX GENERATION
# ==========================================================

@require_POST
@repository_access_required
@rate_limit(
    "semantic_index",
    max_requests=10,
    window_seconds=3600,
)
@limit_indexing_requests
def build_semantic_index_view(request, repository_id):

    repositories_root = (
        Path(settings.MEDIA_ROOT)
        / "repositories"
    ).resolve()

    try:

        safe_id = UUID(str(repository_id))

    except ValueError:

        return JsonResponse(
            {
                "error": "Invalid repository ID."
            },
            status=400,
        )

    repository_dir = (
        repositories_root / str(safe_id)
    ).resolve()

    if not repository_dir.is_relative_to(repositories_root):

        return JsonResponse(
            {
                "error": "Invalid repository ID."
            },
            status=400,
        )

    if not (repository_dir / "metadata.json").is_file():

        return JsonResponse(
            {
                "error": "Repository not found."
            },
            status=404,
        )

    try:

        result = build_semantic_index(repository_dir)

        return JsonResponse({
            "message": "Semantic index created successfully.",
            "repository_id": str(safe_id),
            **result,
        })

    except FileNotFoundError as exc:

        return JsonResponse(
            {
                "error": str(exc)
            },
            status=409,
        )

    except (OSError, ValueError, RuntimeError):

        return JsonResponse(
            {
                "error": (
                    "Could not build the semantic index."
                )
            },
            status=500,
        )


# ==========================================================
# SEMANTIC SEARCH
# ==========================================================

@require_GET
@repository_access_required
@rate_limit(
    "semantic_search",
    max_requests=30,
    window_seconds=60,
)
def semantic_search_view(request, repository_id):

    query = request.GET.get("q", "").strip()

    if not query:

        return JsonResponse(
            {
                "error": "Provide a query using ?q=..."
            },
            status=400,
        )

    if len(query) > 500:

        return JsonResponse(
            {
                "error": (
                    "Query must be 500 characters or fewer."
                )
            },
            status=400,
        )

    try:

        top_k = int(
            request.GET.get("top_k", "5")
        )

    except ValueError:

        return JsonResponse(
            {
                "error": "top_k must be an integer."
            },
            status=400,
        )

    if not 1 <= top_k <= 10:

        return JsonResponse(
            {
                "error": "top_k must be between 1 and 10."
            },
            status=400,
        )

    repositories_root = (
        Path(settings.MEDIA_ROOT)
        / "repositories"
    ).resolve()

    try:

        safe_id = UUID(str(repository_id))

    except ValueError:

        return JsonResponse(
            {
                "error": "Invalid repository ID."
            },
            status=400,
        )

    repository_dir = (
        repositories_root / str(safe_id)
    ).resolve()

    if not repository_dir.is_relative_to(repositories_root):

        return JsonResponse(
            {
                "error": "Invalid repository ID."
            },
            status=400,
        )

    if not (repository_dir / "metadata.json").is_file():

        return JsonResponse(
            {
                "error": "Repository not found."
            },
            status=404,
        )

    try:

        results = semantic_search(
            repository_dir,
            query,
            top_k,
        )

        return JsonResponse({
            "repository_id": str(safe_id),
            "query": query,
            "result_count": len(results),
            "results": results,
        })

    except FileNotFoundError as exc:

        return JsonResponse(
            {
                "error": str(exc)
            },
            status=409,
        )

    except (OSError, ValueError, RuntimeError):

        return JsonResponse(
            {
                "error": "Could not run semantic search."
            },
            status=500,
        )


# ==========================================================
# HYBRID SEARCH
# ==========================================================

@require_GET
@repository_access_required
@rate_limit(
    "hybrid_search",
    max_requests=30,
    window_seconds=60,
)
def hybrid_search_view(request, repository_id):

    query = request.GET.get("q", "").strip()

    if not query:

        return JsonResponse(
            {
                "error": "Provide a query using ?q=..."
            },
            status=400,
        )

    if len(query) > 500:

        return JsonResponse(
            {
                "error": (
                    "Query must be 500 characters or fewer."
                )
            },
            status=400,
        )

    try:

        top_k = int(
            request.GET.get("top_k", "5")
        )

    except ValueError:

        return JsonResponse(
            {
                "error": "top_k must be an integer."
            },
            status=400,
        )

    if not 1 <= top_k <= 10:

        return JsonResponse(
            {
                "error": "top_k must be between 1 and 10."
            },
            status=400,
        )

    repositories_root = (
        Path(settings.MEDIA_ROOT)
        / "repositories"
    ).resolve()

    try:

        safe_id = UUID(str(repository_id))

    except ValueError:

        return JsonResponse(
            {
                "error": "Invalid repository ID."
            },
            status=400,
        )

    repository_dir = (
        repositories_root / str(safe_id)
    ).resolve()

    if not repository_dir.is_relative_to(repositories_root):

        return JsonResponse(
            {
                "error": "Invalid repository ID."
            },
            status=400,
        )

    if not (repository_dir / "metadata.json").is_file():

        return JsonResponse(
            {
                "error": "Repository not found."
            },
            status=404,
        )

    try:

        results = hybrid_search(
            repository_dir,
            query,
            top_k=top_k,
        )

        return JsonResponse({
            "repository_id": str(safe_id),
            "query": query,
            "result_count": len(results),
            "results": results,
        })

    except FileNotFoundError as exc:

        return JsonResponse(
            {
                "error": str(exc)
            },
            status=409,
        )

    except (
        OSError,
        ValueError,
        TypeError,
        RuntimeError,
    ):

        return JsonResponse(
            {
                "error": "Could not run hybrid search."
            },
            status=500,
        )


# ==========================================================
# REPOSITORY QUESTION ANSWERING
# ==========================================================

@require_POST
@repository_access_required
@rate_limit(
    "ask",
    max_requests=10,
    window_seconds=60,
)
@limit_llm_requests
def ask_repository(request, repository_id):
    """
    Answer questions using repository evidence.

    Repository access is restricted to the browser session
    that originally uploaded the repository.

    User authentication is not required.
    """

    try:

        body = json.loads(
            request.body.decode("utf-8")
        )

    except (json.JSONDecodeError, UnicodeDecodeError):

        return JsonResponse(
            {
                "error": (
                    "Request body must contain valid JSON."
                )
            },
            status=400,
        )

    if not isinstance(body, dict):

        return JsonResponse(
            {
                "error": (
                    "Request body must be a JSON object."
                )
            },
            status=400,
        )

    question = body.get("question", "")

    if (
        not isinstance(question, str)
        or not question.strip()
    ):

        return JsonResponse(
            {
                "error": (
                    "Provide a question as a non-empty string."
                )
            },
            status=400,
        )

    question = question.strip()

    if len(question) > 1000:

        return JsonResponse(
            {
                "error": (
                    "Question must be 1000 characters or fewer."
                )
            },
            status=400,
        )

    try:

        safe_id = UUID(str(repository_id))

    except ValueError:

        return JsonResponse(
            {
                "error": "Invalid repository ID."
            },
            status=400,
        )

    repositories_root = (
        Path(settings.MEDIA_ROOT)
        / "repositories"
    ).resolve()

    repository_dir = (
        repositories_root / str(safe_id)
    ).resolve()

    if not repository_dir.is_relative_to(repositories_root):

        return JsonResponse(
            {
                "error": "Invalid repository ID."
            },
            status=400,
        )

    if not (repository_dir / "metadata.json").is_file():

        return JsonResponse(
            {
                "error": "Repository not found."
            },
            status=404,
        )

    if not (repository_dir / "chunks.json").is_file():

        return JsonResponse(
            {
                "error": (
                    "Parse the repository before asking questions."
                )
            },
            status=409,
        )

    if not (repository_dir / "semantic_index.npz").is_file():

        return JsonResponse(
            {
                "error": (
                    "Build the semantic index before asking questions."
                )
            },
            status=409,
        )

    try:

        # Step 1: Run the existing hybrid search.

        hybrid_sources = hybrid_search(
            repository_dir,
            question,
            top_k=5,
        )

        # Step 2: Collect broader evidence for project
        # overview questions.

        if is_project_overview_question(question):

            overview_sources = get_project_overview_evidence(
                repository_dir
            )

            print(
                "\n========== PROJECT OVERVIEW FILES =========="
            )

            for source in overview_sources:

                print(
                    f"FILE: {source.get('file_path')} | "
                    f"TYPE: {source.get('chunk_type')} | "
                    f"LINES: {source.get('start_line')}-"
                    f"{source.get('end_line')}"
                )

            print(
                "============================================\n"
            )

            # Keep overview evidence first.
            # Add hybrid results that are not already represented.

            existing_paths = {
                item.get("file_path")
                for item in overview_sources
            }

            additional_sources = [
                item
                for item in hybrid_sources
                if item.get("file_path") not in existing_paths
            ]

            sources = [
                *overview_sources,
                *additional_sources[:3],
            ]

            print(
                "[ASK] Project overview evidence:",
                len(overview_sources),
                "repository files;",
                len(additional_sources[:3]),
                "additional hybrid results.",
            )

        else:

            # Step 3: Preserve existing specific-file behavior.

            sources = hybrid_sources

            complete_file = get_requested_file_evidence(
                repository_dir,
                question,
            )

            if complete_file:

                sources = [
                    complete_file,
                    *[
                        item
                        for item in sources
                        if item.get("file_path")
                        != complete_file["file_path"]
                    ][:4],
                ]

        # Step 4: Generate the answer.

        answer = generate_answer(
            question,
            sources,
        )

        # Step 5: Preserve source citations.

        citations = [
            {
                "file_path": item.get("file_path"),
                "name": item.get("name"),
                "chunk_type": item.get("chunk_type"),
                "start_line": item.get("start_line"),
                "end_line": item.get("end_line"),
                "parent_class": item.get("parent_class"),
                "parent_function": item.get("parent_function"),
                "signature": item.get("signature"),
                "imports": item.get("imports", []),
                "part": item.get("part"),
                "total_parts": item.get("total_parts"),
                "content": item.get("content"),
                "rrf_score": item.get("rrf_score"),
            }
            for item in sources
        ]

        return JsonResponse({
            "repository_id": str(safe_id),
            "question": question,
            "answer": answer,
            "sources": citations,
        })

    except FileNotFoundError as exc:

        print(f"[ASK ERROR] File not found: {exc}")

        return JsonResponse(
            {
                "error": (
                    "Required repository evidence was not found."
                )
            },
            status=409,
        )

    except Exception as exc:

        import traceback

        print(
            f"[ASK ERROR] {type(exc).__name__}: {exc}"
        )

        traceback.print_exc()

        return JsonResponse(
            {
                "error": (
                    "Could not generate an answer. "
                    "Check the backend logs."
                )
            },
            status=502,
        )


# ==========================================================
# REPOSITORY STATUS
# ==========================================================

@require_GET
@repository_access_required
@rate_limit(
    "status",
    max_requests=60,
    window_seconds=60,
)
def repository_status(request, repository_id):
    """
    Check repository availability and preparation status
    for the current browser session.
    """

    repositories_root = (
        Path(settings.MEDIA_ROOT) / "repositories"
    ).resolve()

    repository_dir = (
        repositories_root / str(repository_id)
    ).resolve()

    if not repository_dir.is_relative_to(repositories_root):

        return JsonResponse(
            {"error": "Invalid repository ID."},
            status=400,
        )

    if not (repository_dir / "metadata.json").is_file():

        return JsonResponse(
            {"error": "Repository not found."},
            status=404,
        )

    parsed = (repository_dir / "chunks.json").is_file()

    indexed = (
        repository_dir / "semantic_index.npz"
    ).is_file()

    return JsonResponse({
        "repository_id": str(repository_id),
        "parsed": parsed,
        "indexed": indexed,
        "ready": parsed and indexed,
    })