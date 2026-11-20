import json
from pathlib import Path

from repositories.retrieval import load_chunks, search_chunks
from repositories.semantic_search import semantic_search
from repositories.hybrid_search import hybrid_search


REPOSITORY_DIR = Path(
    "media/repositories/0af5df46-c93b-4179-b788-31a94fe2b415"
)

TOP_K = 5


# Manually verified relevant chunk IDs for each question.
BENCHMARK = [
    {
        "id": "Q1",
        "question": "Explain how load_artifacts loads the trained pipeline and label encoder.",
        "relevant": [12, 15],
    },
    {
        "id": "Q2",
        "question": "How does the application generate disease predictions and probabilities?",
        "relevant": [14, 27],
    },
    {
        "id": "Q3",
        "question": "How does the application handle missing or mismatched input features before prediction?",
        "relevant": [13, 14],
    },
    {
        "id": "Q4",
        "question": "How does the application identify the expected input columns for the trained model?",
        "relevant": [13],
    },
    {
        "id": "Q5",
        "question": "How does the application load CSS and the background image into its interface?",
        "relevant": [9, 29, 30, 31, 32],
    },
    {
        "id": "Q6",
        "question": "How does the application locate the trained pipeline and label encoder files?",
        "relevant": [5, 6, 12],
    },
    {
        "id": "Q7",
        "question": "Which machine learning libraries and technologies are used in this project?",
        "relevant": [1, 28],
    },
    {
        "id": "Q8",
        "question": "What is the purpose of the trained machine learning pipeline in the disease prediction application?",
        "relevant": [0, 12, 14, 27],
    },
    {
        "id": "Q9",
        "question": "How does the application convert predicted class values into disease names?",
        "relevant": [14],
    },
    {
        "id": "Q10",
        "question": "How does the application display prediction results to the user?",
        "relevant": [0, 27],
    },
]


def get_chunk_key(chunk):
    """Create a stable key for matching retrieved results to source chunks."""
    return (
        chunk.get("file_path"),
        chunk.get("chunk_type"),
        chunk.get("name"),
        chunk.get("start_line"),
        chunk.get("end_line"),
    )


def precision_at_k(retrieved_ids, relevant_ids, k=5):
    top_results = retrieved_ids[:k]

    if not top_results:
        return 0.0

    relevant_found = sum(
        1 for chunk_id in top_results
        if chunk_id in relevant_ids
    )

    return relevant_found / k


def recall_at_k(retrieved_ids, relevant_ids, k=5):
    if not relevant_ids:
        return 0.0

    relevant_found = sum(
        1 for chunk_id in retrieved_ids[:k]
        if chunk_id in relevant_ids
    )

    return relevant_found / len(relevant_ids)


def reciprocal_rank(retrieved_ids, relevant_ids):
    for rank, chunk_id in enumerate(retrieved_ids, start=1):
        if chunk_id in relevant_ids:
            return 1.0 / rank

    return 0.0


def evaluate_method(chunks, question, method):
    if method == "BM25":
        results = search_chunks(chunks, question, top_k=TOP_K)

    elif method == "Semantic":
        results = semantic_search(
            REPOSITORY_DIR, question, top_k=TOP_K
        )

    elif method == "Hybrid":
        results = hybrid_search(
            REPOSITORY_DIR, question, top_k=TOP_K
        )

    else:
        raise ValueError(f"Unknown method: {method}")

    # Map retrieved chunks back to their original chunk IDs.
    key_to_id = {
        get_chunk_key(chunk): index
        for index, chunk in enumerate(chunks)
    }

    retrieved_ids = []

    for result in results:
        chunk_id = key_to_id.get(get_chunk_key(result))

        if chunk_id is not None:
            retrieved_ids.append(chunk_id)

    return retrieved_ids, results


def main():
    chunks = load_chunks(REPOSITORY_DIR)

    print("=" * 90)
    print("CODEMIND AI - RETRIEVAL EVALUATION")
    print("=" * 90)
    print("Repository chunks:", len(chunks))
    print("Benchmark questions:", len(BENCHMARK))
    print("Evaluation cutoff: Top", TOP_K)

    methods = ["BM25", "Semantic", "Hybrid"]

    totals = {
        method: {
            "precision": 0.0,
            "recall": 0.0,
            "mrr": 0.0,
        }
        for method in methods
    }

    detailed_results = []

    for test in BENCHMARK:
        print("\n" + "-" * 90)
        print(test["id"] + ":", test["question"])
        print("Expected relevant chunks:", test["relevant"])

        relevant_ids = set(test["relevant"])

        for method in methods:
            retrieved_ids, results = evaluate_method(
                chunks, test["question"], method
            )

            precision = precision_at_k(
                retrieved_ids, relevant_ids, TOP_K
            )

            recall = recall_at_k(
                retrieved_ids, relevant_ids, TOP_K
            )

            mrr = reciprocal_rank(
                retrieved_ids, relevant_ids
            )

            totals[method]["precision"] += precision
            totals[method]["recall"] += recall
            totals[method]["mrr"] += mrr

            print(f"\n{method}")
            print("Retrieved chunk IDs:", retrieved_ids)
            print(
                f"Precision@5: {precision:.3f} | "
                f"Recall@5: {recall:.3f} | "
                f"RR: {mrr:.3f}"
            )

            for rank, result in enumerate(results, start=1):
                chunk_id = retrieved_ids[rank - 1] if rank <= len(retrieved_ids) else None

                print(
                    f"  Rank {rank}: Chunk {chunk_id} | "
                    f"{result.get('file_path')} | "
                    f"{result.get('name')} | "
                    f"Lines {result.get('start_line')}-"
                    f"{result.get('end_line')}"
                )

            detailed_results.append({
                "question_id": test["id"],
                "method": method,
                "retrieved_chunk_ids": retrieved_ids,
                "relevant_chunk_ids": sorted(relevant_ids),
                "precision_at_5": precision,
                "recall_at_5": recall,
                "reciprocal_rank": mrr,
            })

    question_count = len(BENCHMARK)

    print("\n" + "=" * 90)
    print("FINAL COMPARISON")
    print("=" * 90)

    summary = {}

    for method in methods:
        averages = {
            metric: value / question_count
            for metric, value in totals[method].items()
        }

        summary[method] = averages

        print(
            f"{method:10} | "
            f"Precision@5: {averages['precision']:.3f} | "
            f"Recall@5: {averages['recall']:.3f} | "
            f"MRR: {averages['mrr']:.3f}"
        )

    output = {
        "repository": str(REPOSITORY_DIR),
        "total_chunks": len(chunks),
        "top_k": TOP_K,
        "summary": summary,
        "details": detailed_results,
    }

    output_path = Path("evaluation_results.json")

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=4)

    print("\nDetailed results saved to:", output_path)


if __name__ == "__main__":
    main()
