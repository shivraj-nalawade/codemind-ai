
import ast
import json
from pathlib import Path

TEXT_CHUNK_LINES = 80


def parse_python_file(file_path, relative_path):
    """Extract Python functions, classes, and their line numbers."""
    source = file_path.read_text(encoding="utf-8")
    lines = source.splitlines()

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [{
            "file_path": relative_path,
            "chunk_type": "parse_error",
            "name": file_path.name,
            "start_line": exc.lineno or 1,
            "end_line": exc.end_lineno or exc.lineno or 1,
            "content": source,
            "error": "Python syntax error",
        }]

    chunks = []

    def add_chunk(node, chunk_type, name):
        start = node.lineno
        end = getattr(node, "end_lineno", start)
        content = "\n".join(lines[start - 1:end])

        chunks.append({
            "file_path": relative_path,
            "chunk_type": chunk_type,
            "name": name,
            "start_line": start,
            "end_line": end,
            "content": content,
        })

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add_chunk(node, "function", node.name)
        elif isinstance(node, ast.ClassDef):
            add_chunk(node, "class", node.name)

    # Preserve useful module-level code when no definitions exist.
    if not chunks and source.strip():
        chunks.append({
            "file_path": relative_path,
            "chunk_type": "module",
            "name": file_path.name,
            "start_line": 1,
            "end_line": len(lines),
            "content": source,
        })

    return chunks


def parse_text_file(file_path, relative_path):
    """Split Markdown and other supported text files into line-based chunks."""
    lines = file_path.read_text(encoding="utf-8").splitlines()
    chunks = []

    for start_index in range(0, len(lines), TEXT_CHUNK_LINES):
        section = lines[start_index:start_index + TEXT_CHUNK_LINES]
        content = "\n".join(section)

        if not content.strip():
            continue

        start_line = start_index + 1
        end_line = start_index + len(section)

        chunks.append({
            "file_path": relative_path,
            "chunk_type": "text",
            "name": f"{file_path.name} lines {start_line}-{end_line}",
            "start_line": start_line,
            "end_line": end_line,
            "content": content,
        })

    return chunks


def parse_repository(repository_dir, metadata):
    """Parse all accepted files listed in the repository metadata."""
    root = Path(repository_dir).resolve()
    all_chunks = []

    for relative_path in metadata["files"]:
        file_path = (root / relative_path).resolve()

        # Do not read a path outside this repository.
        if not file_path.is_relative_to(root) or not file_path.is_file():
            continue

        try:
            if file_path.suffix.lower() == ".py":
                file_chunks = parse_python_file(file_path, relative_path)
            else:
                file_chunks = parse_text_file(file_path, relative_path)

            all_chunks.extend(file_chunks)
        except (OSError, UnicodeError):
            # Skip files that cannot be read as text.
            continue

    return all_chunks


def save_chunks(repository_dir, chunks):
    """Save parsed chunks as JSON for the next pipeline stage."""
    output_path = Path(repository_dir) / "chunks.json"
    output_path.write_text(
        json.dumps(chunks, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path
