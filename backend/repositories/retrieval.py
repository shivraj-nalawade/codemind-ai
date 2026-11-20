
import json
import re
from pathlib import Path

from rank_bm25 import BM25Okapi


def tokenize(text):
    """Convert code and queries into searchable tokens."""
    return re.findall(r"[a-zA-Z_][a-zA-Z_0-9]*|\d+", text.lower())


def load_chunks(repository_dir):
    """Load chunks created by the repository parser."""
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


def build_searchable_text(chunk):
    """Combine source code and metadata for keyword retrieval."""

    imports = chunk.get("imports", [])

    if isinstance(imports, list):
        imports_text = " ".join(imports)
    else:
        imports_text = str(imports)

    return " ".join([
        str(chunk.get("name") or ""),
        str(chunk.get("file_path") or ""),
        str(chunk.get("chunk_type") or ""),
        str(chunk.get("parent_class") or ""),
        str(chunk.get("parent_function") or ""),
        str(chunk.get("signature") or ""),
        imports_text,
        str(chunk.get("part") or ""),
        str(chunk.get("total_parts") or ""),
        str(chunk.get("content") or ""),
    ])


def search_chunks(chunks, query, top_k=5):
    """Return the most relevant code chunks using metadata-aware BM25."""

    if not query or not query.strip():
        return []

    if not chunks:
        return []

    # Include metadata along with source code in the BM25 corpus.
    tokenized_documents = [
        tokenize(build_searchable_text(chunk))
        for chunk in chunks
    ]

    # Ignore empty documents.
    valid_indices = [
        index
        for index, tokens in enumerate(tokenized_documents)
        if tokens
    ]

    if not valid_indices:
        return []

    valid_documents = [
        tokenized_documents[index]
        for index in valid_indices
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
    result_limit = max(1, min(int(top_k), 15))

    for index in ranked_indices:
        score = float(scores[index])

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
            "parent_class": chunk.get("parent_class"),
            "parent_function": chunk.get("parent_function"),
            "signature": chunk.get("signature"),
            "imports": chunk.get("imports", []),
            "part": chunk.get("part"),
            "total_parts": chunk.get("total_parts"),
            "score": round(score, 4),
        })

        if len(results) >= result_limit:
            break

    return results
