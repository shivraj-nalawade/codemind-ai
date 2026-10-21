
from django.urls import path

from .views import (
    upload_repository,
    parse_repository_view,
    search_repository,
    build_semantic_index_view,
    semantic_search_view,
    hybrid_search_view,
)

urlpatterns = [
    # Upload a repository ZIP file
    path(
        "upload/",
        upload_repository,
        name="upload_repository",
    ),

    # Parse repository files into code chunks
    path(
        "<uuid:repository_id>/parse/",
        parse_repository_view,
        name="parse_repository",
    ),

    # Search using BM25 keyword retrieval
    path(
        "<uuid:repository_id>/search/",
        search_repository,
        name="search_repository",
    ),

    # Build the Transformer embedding index
    path(
        "<uuid:repository_id>/semantic-index/",
        build_semantic_index_view,
        name="build_semantic_index",
    ),

    # Search using Transformer embeddings
    path(
        "<uuid:repository_id>/semantic-search/",
        semantic_search_view,
        name="semantic_search",
    ),

    # Search using combined BM25 and semantic retrieval
    path(
        "<uuid:repository_id>/hybrid-search/",
        hybrid_search_view,
        name="hybrid_search",
    ),
]
