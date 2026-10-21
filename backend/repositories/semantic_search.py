
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_model():
    """Load the embedding model once per Python process."""
    return SentenceTransformer(MODEL_NAME)


def load_chunks(repository_dir):
    """Read chunks created by the existing parser."""
    path = Path(repository_dir) / "chunks.json"

    if not path.is_file():
        raise FileNotFoundError(
            "chunks.json not found. Parse the repository first."
        )

    with path.open("r", encoding="utf-8") as file:
        chunks = json.load(file)

    if not isinstance(chunks, list):
        raise ValueError("Invalid chunks.json format.")

    return chunks


def chunk_text(chunk):
    """Build searchable text while retaining source information separately."""
    return (
        f"File: {chunk.get('file_path', '')}\n"
        f"Type: {chunk.get('chunk_type', '')}\n"
        f"Name: {chunk.get('name', '')}\n"
        f"Code or documentation:\n{chunk.get('content', '')}"
    )


def build_semantic_index(repository_dir):
    """Create and save embeddings for every code chunk."""
    repository_dir = Path(repository_dir)
    chunks = load_chunks(repository_dir)

    if not chunks:
        raise ValueError("No chunks available to index.")

    model = get_model()
    texts = [chunk_text(chunk) for chunk in chunks]

    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    index_path = repository_dir / "semantic_index.npz"

    np.savez_compressed(
        index_path,
        embeddings=embeddings.astype(np.float32),
    )

    return {
        "chunk_count": len(chunks),
        "embedding_dimensions": int(embeddings.shape[1]),
        "index_file": index_path.name,
    }


def semantic_search(repository_dir, query, top_k=5):
    """Retrieve chunks by semantic similarity."""
    repository_dir = Path(repository_dir)
    chunks = load_chunks(repository_dir)
    index_path = repository_dir / "semantic_index.npz"

    if not index_path.is_file():
        raise FileNotFoundError(
            "Semantic index not found. Build the index first."
        )

    if not chunks:
        return []

    model = get_model()

    with np.load(index_path, allow_pickle=False) as data:
        embeddings = data["embeddings"]

    if len(embeddings) != len(chunks):
        raise ValueError(
            "The index does not match chunks.json. Rebuild the index."
        )

    query_embedding = model.encode(
        [query],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )[0]

    # Normalized vectors make the dot product equal cosine similarity.
    scores = embeddings @ query_embedding

    ranked_indices = np.argsort(scores)[::-1][:top_k]
    results = []

    for index in ranked_indices:
        chunk = chunks[int(index)]

        results.append({
            "file_path": chunk.get("file_path"),
            "chunk_type": chunk.get("chunk_type"),
            "name": chunk.get("name"),
            "start_line": chunk.get("start_line"),
            "end_line": chunk.get("end_line"),
            "content": chunk.get("content"),
            "score": round(float(scores[index]), 4),
        })

    return results
