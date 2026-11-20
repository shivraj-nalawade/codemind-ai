
import ast
import json
from pathlib import Path


TEXT_CHUNK_LINES = 80

# Maximum size for an individual code chunk.
CODE_CHUNK_LINES = 120

# A small overlap helps retain context when large functions are split.
CODE_CHUNK_OVERLAP = 15


def extract_imports(tree):
    """Extract import statements from a Python AST."""
    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(f"import {alias.name}")

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = ", ".join(alias.name for alias in node.names)
            imports.append(f"from {module} import {names}")

    return sorted(set(imports))


def get_node_start(node):
    """Include decorators when calculating the starting line."""
    decorator_lines = [
        decorator.lineno for decorator in getattr(node, "decorator_list", [])
    ]

    return min([node.lineno] + decorator_lines)


def get_signature(node):
    """Generate a readable function or class signature."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
        arguments = ast.unparse(node.args)

        signature = f"{prefix}{node.name}({arguments})"

        if node.returns:
            signature += f" -> {ast.unparse(node.returns)}"

        return signature

    if isinstance(node, ast.ClassDef):
        bases = ", ".join(ast.unparse(base) for base in node.bases)
        return f"class {node.name}({bases})" if bases else f"class {node.name}"

    return ""


def create_chunks(
    source,
    relative_path,
    node,
    chunk_type,
    name,
    imports,
    parent_class=None,
    parent_function=None,
):
    """Create one or more chunks from a Python AST node."""
    lines = source.splitlines()

    start = get_node_start(node)
    end = getattr(node, "end_lineno", node.lineno)

    node_lines = lines[start - 1:end]

    if not node_lines:
        return []

    signature = get_signature(node)

    chunks = []

    # Keep smaller functions/classes as single chunks.
    if len(node_lines) <= CODE_CHUNK_LINES:
        sections = [node_lines]
    else:
        sections = []
        step = CODE_CHUNK_LINES - CODE_CHUNK_OVERLAP

        for index in range(0, len(node_lines), step):
            section = node_lines[index:index + CODE_CHUNK_LINES]

            if section:
                sections.append(section)

            if index + CODE_CHUNK_LINES >= len(node_lines):
                break

    current_line = start

    for part_index, section in enumerate(sections):
        section_start = current_line
        section_end = section_start + len(section) - 1

        chunk = {
            "file_path": relative_path,
            "chunk_type": chunk_type,
            "name": name,
            "start_line": section_start,
            "end_line": section_end,
            "content": "\n".join(section),

            # Additional metadata.
            "parent_class": parent_class,
            "parent_function": parent_function,
            "signature": signature,
            "imports": imports,
        }

        if len(sections) > 1:
            chunk["part"] = part_index + 1
            chunk["total_parts"] = len(sections)

        chunks.append(chunk)

        # Advance while retaining the configured overlap.
        current_line += len(section) - CODE_CHUNK_OVERLAP

    return chunks


def parse_python_file(file_path, relative_path):
    """Extract Python classes, functions, methods and module-level code."""
    source = file_path.read_text(encoding="utf-8")
    lines = source.splitlines()

    try:
        tree = ast.parse(source)

    except SyntaxError as exc:
        error_line = exc.lineno or 1

        return [{
            "file_path": relative_path,
            "chunk_type": "parse_error",
            "name": file_path.name,
            "start_line": error_line,
            "end_line": exc.end_lineno or error_line,
            "content": source,
            "error": "Python syntax error",
            "parent_class": None,
            "parent_function": None,
            "signature": "",
            "imports": [],
        }]

    imports = extract_imports(tree)
    chunks = []

    def visit_node(node, parent_class=None, parent_function=None):
        """Visit definitions while retaining their hierarchical context."""

        if isinstance(node, ast.ClassDef):
            chunks.extend(
                create_chunks(
                    source,
                    relative_path,
                    node,
                    "class",
                    node.name,
                    imports,
                    parent_class=parent_class,
                    parent_function=parent_function,
                )
            )

            for child in node.body:
                visit_node(
                    child,
                    parent_class=node.name,
                    parent_function=parent_function,
                )

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Check parent_function first so nested functions inside
            # class methods are not incorrectly classified as methods.
            if parent_function:
                chunk_type = "nested_function"
            elif parent_class:
                chunk_type = "method"
            else:
                chunk_type = "function"

            chunks.extend(
                create_chunks(
                    source,
                    relative_path,
                    node,
                    chunk_type,
                    node.name,
                    imports,
                    parent_class=parent_class,
                    parent_function=parent_function,
                )
            )

            for child in node.body:
                visit_node(
                    child,
                    parent_class=parent_class,
                    parent_function=node.name,
                )

        elif isinstance(node, ast.If):
            for child in node.body + node.orelse:
                visit_node(
                    child,
                    parent_class=parent_class,
                    parent_function=parent_function,
                )

        elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            for child in node.body + node.orelse:
                visit_node(
                    child,
                    parent_class=parent_class,
                    parent_function=parent_function,
                )

        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for child in node.body:
                visit_node(
                    child,
                    parent_class=parent_class,
                    parent_function=parent_function,
                )

        elif isinstance(node, ast.Try):
            for child in node.body + node.orelse + node.finalbody:
                visit_node(
                    child,
                    parent_class=parent_class,
                    parent_function=parent_function,
                )

            for handler in node.handlers:
                for child in handler.body:
                    visit_node(
                        child,
                        parent_class=parent_class,
                        parent_function=parent_function,
                    )

        elif isinstance(node, ast.Match):
            for case in node.cases:
                for child in case.body:
                    visit_node(
                        child,
                        parent_class=parent_class,
                        parent_function=parent_function,
                    )

    # Extract definitions recursively.
    for node in tree.body:
        if isinstance(
            node,
            (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            visit_node(node)

    # Preserve module-level statements such as constants and configuration.
    for node in tree.body:
        if isinstance(
            node,
            (
                ast.ClassDef,
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.Import,
                ast.ImportFrom,
            ),
        ):
            continue

        start = get_node_start(node)
        end = getattr(node, "end_lineno", node.lineno)
        content = "\n".join(lines[start - 1:end])

        if content.strip():
            chunks.append({
                "file_path": relative_path,
                "chunk_type": "module_statement",
                "name": f"module_statement_{start}",
                "start_line": start,
                "end_line": end,
                "content": content,
                "parent_class": None,
                "parent_function": None,
                "signature": "",
                "imports": imports,
            })

    # Handle empty or definition-free Python files.
    if not chunks and source.strip():
        chunks.append({
            "file_path": relative_path,
            "chunk_type": "module",
            "name": file_path.name,
            "start_line": 1,
            "end_line": len(lines),
            "content": source,
            "parent_class": None,
            "parent_function": None,
            "signature": "",
            "imports": imports,
        })

    return sorted(
        chunks,
        key=lambda chunk: (
            chunk["start_line"],
            chunk["end_line"],
            chunk["chunk_type"],
        ),
    )


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

        # Prevent reading files outside the repository.
        if not file_path.is_relative_to(root) or not file_path.is_file():
            continue

        try:
            if file_path.suffix.lower() == ".py":
                file_chunks = parse_python_file(file_path, relative_path)
            else:
                file_chunks = parse_text_file(file_path, relative_path)

            all_chunks.extend(file_chunks)

        except (OSError, UnicodeError):
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
