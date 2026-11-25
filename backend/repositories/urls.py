from django.urls import path

from .views import (
    upload_repository,
    parse_repository_view,
    search_repository,
    build_semantic_index_view,
    semantic_search_view,
    hybrid_search_view,
    ask_repository,
    repository_status,
)


urlpatterns = [
    path(
        "upload/",
        upload_repository,
        name="upload_repository",
    ),
    path(
        "<uuid:repository_id>/parse/",
        parse_repository_view,
        name="parse_repository",
    ),
    path(
        "<uuid:repository_id>/search/",
        search_repository,
        name="search_repository",
    ),
    path(
        "<uuid:repository_id>/semantic-index/",
        build_semantic_index_view,
        name="build_semantic_index",
    ),
    path(
        "<uuid:repository_id>/semantic-search/",
        semantic_search_view,
        name="semantic_search",
    ),
    path(
        "<uuid:repository_id>/hybrid-search/",
        hybrid_search_view,
        name="hybrid_search",
    ),
    path(
        "<uuid:repository_id>/ask/",
        ask_repository,
        name="ask_repository",
    ),
    path(
        "<uuid:repository_id>/status/",
        repository_status,
        name="repository_status",
    ),
]