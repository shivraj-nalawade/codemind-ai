
from .retrieval import load_chunks, search_chunks
from .semantic_search import semantic_search


def hybrid_search(
    repository_dir,
    query,
    top_k=5,
    rrf_k=60,
    bm25_weight=1.2,
    semantic_weight=1.0,
):
    """
    Combine BM25 and semantic rankings using
    Weighted Reciprocal Rank Fusion.
    """

    chunks = load_chunks(repository_dir)

    if not chunks or not query.strip():
        return []

    candidate_count = min(len(chunks), 50)

    bm25_results = search_chunks(
        chunks, query, top_k=candidate_count
    )

    semantic_results = semantic_search(
        repository_dir, query, top_k=candidate_count
    )

    def chunk_key(item):
        return (
            item.get("file_path"),
            item.get("chunk_type"),
            item.get("name"),
            item.get("start_line"),
            item.get("end_line"),
        )

    fused = {}

    rankings = [
        (bm25_results, bm25_weight, "bm25_rank"),
        (semantic_results, semantic_weight, "semantic_rank"),
    ]

    for ranking, weight, rank_field in rankings:
        for rank, item in enumerate(ranking, start=1):
            key = chunk_key(item)

            if key not in fused:
                fused[key] = {
                    **item,
                    "rrf_score": 0.0,
                    "bm25_rank": None,
                    "semantic_rank": None,
                }

            fused[key]["rrf_score"] += (
                weight / (rrf_k + rank)
            )

            fused[key][rank_field] = rank

    ranked = sorted(
        fused.values(),
        key=lambda item: item["rrf_score"],
        reverse=True,
    )

    results = []

    for item in ranked[:max(1, min(int(top_k), 10))]:
        item["rrf_score"] = round(
            item["rrf_score"], 6
        )
        results.append(item)

    return results
