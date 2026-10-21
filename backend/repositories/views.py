import json
from pathlib import Path
from uuid import UUID
from django.conf import settings
from django.views.decorators.http import require_GET
from .retrieval import load_chunks, search_chunks
from .hybrid_search import hybrid_search
from .parser import parse_repository, save_chunks
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .hybrid_search import hybrid_search
from .llm_service import generate_answer

from .services import safe_extract_repository
from .semantic_search import build_semantic_index, semantic_search


@csrf_exempt  # Local prototype only; replace with proper CSRF/auth controls.
@require_POST
def upload_repository(request):
    uploaded_file = request.FILES.get("file")

    if not uploaded_file:
        return JsonResponse(
            {"error": "Please upload a ZIP file using the 'file' field."},
            status=400,
        )

    if not uploaded_file.name.lower().endswith(".zip"):
        return JsonResponse(
            {"error": "Only ZIP files are supported."},
            status=400,
        )

    try:
        result = safe_extract_repository(uploaded_file)

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
            {"error": exc.messages},
            status=400,
        )



@require_GET
def parse_repository_view(request, repository_id):
    repository_dir = (
        Path(settings.MEDIA_ROOT) / "repositories" / str(repository_id)
    ).resolve()

    # Confirm that the requested repository exists.
    if not repository_dir.is_relative_to(
        (Path(settings.MEDIA_ROOT) / "repositories").resolve()
    ):
        return JsonResponse({"error": "Invalid repository ID."}, status=400)

    metadata_path = repository_dir / "metadata.json"

    if not repository_dir.is_dir() or not metadata_path.is_file():
        return JsonResponse({"error": "Repository not found."}, status=404)

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        chunks = parse_repository(repository_dir, metadata)
        save_chunks(repository_dir, chunks)

        return JsonResponse({
            "message": "Repository parsed successfully.",
            "repository_id": str(repository_id),
            "chunk_count": len(chunks),
            "chunks": chunks,
        })
    except (OSError, ValueError, KeyError, TypeError):
        return JsonResponse(
            {"error": "Could not parse this repository."},
            status=500,
        )


@require_GET
def search_repository(request, repository_id):
    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse(
            {"error": "Please provide a search query using ?q=..."},
            status=400,
        )

    if len(query) > 500:
        return JsonResponse(
            {"error": "Search query must be 500 characters or fewer."},
            status=400,
        )

    try:
        top_k = int(request.GET.get("top_k", "5"))
    except ValueError:
        return JsonResponse(
            {"error": "top_k must be an integer."},
            status=400,
        )

    if not 1 <= top_k <= 10:
        return JsonResponse(
            {"error": "top_k must be between 1 and 10."},
            status=400,
        )

    repositories_root = (
        Path(settings.MEDIA_ROOT) / "repositories"
    ).resolve()

    repository_dir = (
        repositories_root / str(UUID(str(repository_id)))
    ).resolve()

    if not repository_dir.is_relative_to(repositories_root):
        return JsonResponse({"error": "Invalid repository ID."}, status=400)

    metadata_path = repository_dir / "metadata.json"

    if not repository_dir.is_dir() or not metadata_path.is_file():
        return JsonResponse({"error": "Repository not found."}, status=404)

    try:
        chunks = load_chunks(repository_dir)
        results = search_chunks(chunks, query, top_k)

        return JsonResponse({
            "repository_id": str(repository_id),
            "query": query,
            "result_count": len(results),
            "results": results,
        })

    except FileNotFoundError:
        return JsonResponse(
            {"error": "Repository has not been parsed yet."},
            status=409,
        )
    except (OSError, ValueError, TypeError):
        return JsonResponse(
            {"error": "Could not search this repository."},
            status=500,
        )


@csrf_exempt
@require_POST
def build_semantic_index_view(request, repository_id):
    repositories_root = (
        Path(settings.MEDIA_ROOT) / "repositories"
    ).resolve()

    try:
        safe_id = UUID(str(repository_id))
    except ValueError:
        return JsonResponse({"error": "Invalid repository ID."}, status=400)

    repository_dir = (repositories_root / str(safe_id)).resolve()

    if not repository_dir.is_relative_to(repositories_root):
        return JsonResponse({"error": "Invalid repository ID."}, status=400)

    if not (repository_dir / "metadata.json").is_file():
        return JsonResponse({"error": "Repository not found."}, status=404)

    try:
        result = build_semantic_index(repository_dir)

        return JsonResponse({
            "message": "Semantic index created successfully.",
            "repository_id": str(safe_id),
            **result,
        })

    except FileNotFoundError as exc:
        return JsonResponse({"error": str(exc)}, status=409)
    except (OSError, ValueError, RuntimeError) as exc:
        return JsonResponse(
            {"error": f"Could not build semantic index: {exc}"},
            status=500,
        )


@require_GET
def semantic_search_view(request, repository_id):
    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse({"error": "Provide a query using ?q=..."}, status=400)

    if len(query) > 500:
        return JsonResponse({"error": "Query must be 500 characters or fewer."}, status=400)

    try:
        top_k = int(request.GET.get("top_k", "5"))
    except ValueError:
        return JsonResponse({"error": "top_k must be an integer."}, status=400)

    if not 1 <= top_k <= 10:
        return JsonResponse({"error": "top_k must be between 1 and 10."}, status=400)

    repositories_root = (
        Path(settings.MEDIA_ROOT) / "repositories"
    ).resolve()

    try:
        safe_id = UUID(str(repository_id))
    except ValueError:
        return JsonResponse({"error": "Invalid repository ID."}, status=400)

    repository_dir = (repositories_root / str(safe_id)).resolve()

    if not repository_dir.is_relative_to(repositories_root):
        return JsonResponse({"error": "Invalid repository ID."}, status=400)

    if not (repository_dir / "metadata.json").is_file():
        return JsonResponse({"error": "Repository not found."}, status=404)

    try:
        results = semantic_search(repository_dir, query, top_k)

        return JsonResponse({
            "repository_id": str(safe_id),
            "query": query,
            "result_count": len(results),
            "results": results,
        })

    except FileNotFoundError as exc:
        return JsonResponse({"error": str(exc)}, status=409)
    except (OSError, ValueError, RuntimeError) as exc:
        return JsonResponse(
            {"error": f"Could not run semantic search: {exc}"},
            status=500,
        )



@require_GET
def hybrid_search_view(request, repository_id):
    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse(
            {"error": "Provide a query using ?q=..."},
            status=400,
        )

    if len(query) > 500:
        return JsonResponse(
            {"error": "Query must be 500 characters or fewer."},
            status=400,
        )

    try:
        top_k = int(request.GET.get("top_k", "5"))
    except ValueError:
        return JsonResponse(
            {"error": "top_k must be an integer."},
            status=400,
        )

    if not 1 <= top_k <= 10:
        return JsonResponse(
            {"error": "top_k must be between 1 and 10."},
            status=400,
        )

    repositories_root = (
        Path(settings.MEDIA_ROOT) / "repositories"
    ).resolve()

    try:
        safe_id = UUID(str(repository_id))
    except ValueError:
        return JsonResponse(
            {"error": "Invalid repository ID."},
            status=400,
        )

    repository_dir = (
        repositories_root / str(safe_id)
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

    try:
        results = hybrid_search(
            repository_dir, query, top_k=top_k
        )

        return JsonResponse({
            "repository_id": str(safe_id),
            "query": query,
            "result_count": len(results),
            "results": results,
        })

    except FileNotFoundError as exc:
        return JsonResponse({"error": str(exc)}, status=409)
    except (OSError, ValueError, TypeError, RuntimeError):
        return JsonResponse(
            {"error": "Could not run hybrid search."},
            status=500,
        )



@csrf_exempt  # Local prototype only; secure before deployment.
@require_POST
def ask_repository(request, repository_id):
    """Answer a question using retrieved repository evidence."""

    try:
        body = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "Request body must contain valid JSON."},
            status=400,
        )

    question = body.get("question", "")

    if not isinstance(question, str) or not question.strip():
        return JsonResponse(
            {"error": "Provide a question as a non-empty string."},
            status=400,
        )

    question = question.strip()

    if len(question) > 1000:
        return JsonResponse(
            {"error": "Question must be 1000 characters or fewer."},
            status=400,
        )

    try:
        safe_id = UUID(str(repository_id))
    except ValueError:
        return JsonResponse(
            {"error": "Invalid repository ID."},
            status=400,
        )

    repositories_root = (
        Path(settings.MEDIA_ROOT) / "repositories"
    ).resolve()

    repository_dir = (
        repositories_root / str(safe_id)
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

    if not (repository_dir / "chunks.json").is_file():
        return JsonResponse(
            {"error": "Parse the repository before asking questions."},
            status=409,
        )

    if not (repository_dir / "semantic_index.npz").is_file():
        return JsonResponse(
            {"error": "Build the semantic index before asking questions."},
            status=409,
        )

    try:
        sources = hybrid_search(
            repository_dir,
            question,
            top_k=5,
        )

        answer = generate_answer(question, sources)

        citations = [
            {
                "file_path": item.get("file_path"),
                "name": item.get("name"),
                "start_line": item.get("start_line"),
                "end_line": item.get("end_line"),
                "content": item.get("content"),
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
        return JsonResponse({"error": str(exc)}, status=409)
    except (OSError, RuntimeError, ValueError, TypeError):
        return JsonResponse(
            {"error": "Could not generate an answer. Check the Django and Ollama logs."},
            status=502,
        )
