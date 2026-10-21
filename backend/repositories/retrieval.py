
import json
import re
from pathlib import Path

from rank_bm25 import BM25Okapi


def tokenize(text):
    """Convert code and queries into searchable tokens."""
    return re.findall(r"[a-zA-Z_][a-zA-Z_0-9]*|\d+", text.lower())


def load_chunks(repository_dir):
    """Load chunks created by the Day 4 parser."""
    chunks_path = Path(repository_dir) / "chunks.json"

    if not chunks_path.is_file():
        raise FileNotFoundError(
            "Parsed chunks not found. Parse the repository first."
        )

    with chunks_path.open("r", encoding="utf-8") as file:
        chunks = json.load(file)

    if not isinstance(chunks, list):
        raise ValueError("Invalid chunks.json format.")

    return chunks


def search_chunks(chunks, query, top_k=5):
    """Return the most relevant code chunks using BM25."""
    if not query or not query.strip():
        return []

    if not chunks:
        return []

    tokenized_documents = [
        tokenize(
            chunk.get("name", "") + " "
            + chunk.get("file_path", "") + " "
            + chunk.get("content", "")
        )
        for chunk in chunks
    ]

    # Ignore empty documents so BM25 receives valid tokens.
    valid_indices = [
        index for index, tokens in enumerate(tokenized_documents)
        if tokens
    ]

    if not valid_indices:
        return []

    valid_documents = [
        tokenized_documents[index] for index in valid_indices
    ]

    bm25 = BM25Okapi(valid_documents)
    query_tokens = tokenize(query)

    if not query_tokens:
        return []

    scores = bm25.get_scores(query_tokens)
    ranked_indices = sorted(
        range(len(scores)),
        key=lambda index: scores[index],
        reverse=True,
    )

    results = []

    for index in ranked_indices:
        score = float(scores[index])

        # BM25 can return zero when there is no useful term match.
        if score <= 0:
            continue

        chunk = chunks[valid_indices[index]]

        results.append({
            "file_path": chunk.get("file_path"),
            "chunk_type": chunk.get("chunk_type"),
            "name": chunk.get("name"),
            "start_line": chunk.get("start_line"),
            "end_line": chunk.get("end_line"),
            "content": chunk.get("content"),
            "score": round(score, 4),
        })

        if len(results) >= max(1, min(int(top_k), 10)):
            break

    return results
