import ast
import hashlib
from uuid import UUID
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import CodeChunk, RepositoryFile

MAX_CHUNK_LINES = 60
MAX_CHUNK_CHARS = 2200
OVERLAP_LINES = 8


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_line_range(
    lines: list[str],
    start_line_1idx: int,
    end_line_1idx: int,
    symbol_name: str | None,
    chunk_type: str,
) -> list[dict]:
    """Split a 1-indexed line range into size-bounded chunks preserving exact line numbers."""
    results: list[dict] = []
    cur = start_line_1idx

    while cur <= end_line_1idx:
        end = cur
        char_count = 0
        while end <= end_line_1idx:
            line_text = lines[end - 1]
            if end > cur and (
                (end - cur + 1) > MAX_CHUNK_LINES or (char_count + len(line_text) + 1) > MAX_CHUNK_CHARS
            ):
                end -= 1
                break
            char_count += len(line_text) + 1
            if end == end_line_1idx:
                break
            end += 1

        chunk_text = "\n".join(lines[cur - 1 : end]).strip("\n")
        if chunk_text.strip():
            results.append(
                {
                    "start_line": cur,
                    "end_line": end,
                    "symbol_name": symbol_name,
                    "chunk_type": chunk_type,
                    "content": chunk_text,
                    "token_count": len(chunk_text.split()),
                    "content_hash": _hash_text(chunk_text),
                }
            )

        if end >= end_line_1idx:
            break
        next_cur = max(cur + 1, end - OVERLAP_LINES + 1)
        cur = next_cur

    return results


def chunk_python_source(content: str) -> list[dict]:
    """Split Python source code along top-level AST definitions while preserving line numbers."""
    lines = content.splitlines()
    if not lines:
        return []

    try:
        tree = ast.parse(content)
    except (SyntaxError, ValueError):
        return _split_line_range(lines, 1, len(lines), None, "block")

    top_defs = [
        node
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    if not top_defs:
        return _split_line_range(lines, 1, len(lines), None, "module")

    chunks: list[dict] = []
    cursor = 1

    for node in top_defs:
        node_start = node.lineno
        node_end = getattr(node, "end_lineno", node.lineno)

        if cursor < node_start:
            gap_type = "module_header" if cursor == 1 else "module_block"
            chunks.extend(_split_line_range(lines, cursor, node_start - 1, None, gap_type))

        kind = "class" if isinstance(node, ast.ClassDef) else "function"
        chunks.extend(_split_line_range(lines, node_start, node_end, node.name, kind))
        cursor = node_end + 1

    if cursor <= len(lines):
        chunks.extend(_split_line_range(lines, cursor, len(lines), None, "module_block"))

    return chunks


def chunk_generic_source(content: str) -> list[dict]:
    """Split non-Python text files into overlapping line-bounded chunks."""
    lines = content.splitlines()
    if not lines:
        return []
    return _split_line_range(lines, 1, len(lines), None, "block")


def create_or_update_repository_chunks(db: Session, repository_id: UUID) -> dict:
    """Chunk all supported files with content for a repository and persist CodeChunk rows."""
    files = db.execute(
        select(RepositoryFile)
        .where(
            RepositoryFile.repository_id == repository_id,
            RepositoryFile.is_supported.is_(True),
            RepositoryFile.content.is_not(None),
        )
        .order_by(RepositoryFile.file_path.asc())
    ).scalars().all()

    all_existing_chunks = db.execute(
        select(CodeChunk.file_id, CodeChunk.content_hash)
        .where(CodeChunk.repository_id == repository_id)
        .order_by(CodeChunk.file_id.asc(), CodeChunk.chunk_index.asc())
    ).all()

    existing_hashes_by_file: dict[UUID, list[str | None]] = {}
    for file_id, content_hash in all_existing_chunks:
        existing_hashes_by_file.setdefault(file_id, []).append(content_hash)

    total_chunks = 0
    unchanged_files = 0
    rechunked_files = 0
    stale_file_ids: list[UUID] = []
    new_chunks: list[CodeChunk] = []

    for f in files:
        if not f.content or not f.content.strip():
            continue

        raw_chunks = (
            chunk_python_source(f.content)
            if f.extension == ".py"
            else chunk_generic_source(f.content)
        )
        if not raw_chunks:
            continue

        existing_hashes = existing_hashes_by_file.get(f.id, [])
        new_hashes = [c["content_hash"] for c in raw_chunks]

        if existing_hashes and existing_hashes == new_hashes:
            unchanged_files += 1
            total_chunks += len(existing_hashes)
            continue

        if existing_hashes:
            stale_file_ids.append(f.id)

        for idx, ch in enumerate(raw_chunks):
            new_chunks.append(
                CodeChunk(
                    repository_id=repository_id,
                    file_id=f.id,
                    file_path=f.file_path,
                    chunk_index=idx,
                    start_line=ch["start_line"],
                    end_line=ch["end_line"],
                    symbol_name=ch["symbol_name"],
                    chunk_type=ch["chunk_type"],
                    content=ch["content"],
                    token_count=ch["token_count"],
                    content_hash=ch["content_hash"],
                )
            )
        rechunked_files += 1
        total_chunks += len(raw_chunks)

    if stale_file_ids:
        db.execute(delete(CodeChunk).where(CodeChunk.file_id.in_(stale_file_ids)))
        db.flush()
    if new_chunks:
        db.add_all(new_chunks)

    db.commit()
    return {
        "files_processed": len(files),
        "rechunked_files": rechunked_files,
        "unchanged_files": unchanged_files,
        "total_chunks": total_chunks,
    }
