"""FastMCP server entry point with tool definitions."""

import os
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP("Semantic Search")


@mcp.tool(
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True}
)
def index_folder(
    folder_path: Annotated[str, Field(description="Absolute path to the folder to index")],
    file_types: Annotated[
        list[str] | None,
        Field(
            description="File extensions to index, e.g. ['.pdf', '.md']. "
                        "Defaults to all supported types: .txt, .md, .pdf, .docx, .pptx, .csv",
            default=None,
        ),
    ] = None,
    recursive: Annotated[
        bool,
        Field(description="Whether to index subdirectories recursively", default=True),
    ] = True,
) -> dict:
    """Index or re-index all documents in a folder for semantic search.

    Scans the folder for supported document types (.txt, .md, .pdf, .docx,
    .pptx, .csv), extracts text, splits into chunks, computes embeddings,
    and stores them in a local vector database.
    Only processes files that have changed since the last indexing run.
    Safe to call multiple times — unchanged files are skipped automatically.
    """
    from server.indexer import index_folder as _index_folder

    return _index_folder(
        folder_path=folder_path,
        file_types=file_types,
        recursive=recursive,
    )


@mcp.tool(
    annotations={"readOnlyHint": True}
)
def semantic_search(
    query: Annotated[str, Field(description="Natural language search query")],
    folder_path: Annotated[
        str | None,
        Field(
            description="Limit search to a specific indexed folder. "
                        "If omitted, searches all indexed folders.",
            default=None,
        ),
    ] = None,
    top_k: Annotated[
        int,
        Field(description="Number of results to return", default=10, ge=1, le=50),
    ] = 10,
    file_type: Annotated[
        str | None,
        Field(
            description="Filter results by file extension, e.g. '.pdf'",
            default=None,
        ),
    ] = None,
    mode: Annotated[
        str,
        Field(
            description="Search mode: 'vector' (default) or 'hybrid' (vector + full-text via RRF)",
            default="vector",
        ),
    ] = "vector",
) -> dict:
    """Search indexed documents using natural language.

    Finds the most relevant document chunks matching the query using
    semantic similarity. Returns ranked results with source file paths
    and relevance scores.

    Use mode='hybrid' to combine vector search with full-text search
    via Reciprocal Rank Fusion for better keyword + semantic matching.

    The folder must be indexed first with index_folder.
    """
    from server.search import semantic_search as _semantic_search

    return _semantic_search(
        query=query,
        folder_path=folder_path,
        top_k=top_k,
        file_type=file_type,
        mode=mode,
    )


@mcp.tool(
    annotations={"readOnlyHint": True}
)
def get_index_status(
    db_path: Annotated[
        str | None,
        Field(
            description="Path to the LanceDB database. Uses LANCEDB_PATH env var if omitted.",
            default=None,
        ),
    ] = None,
) -> dict:
    """Get status information about the current search index.

    Returns total chunks, list of indexed files with chunk counts,
    and file type distribution.
    """
    from server.store import VectorStore

    if db_path is None:
        db_path = os.environ.get("LANCEDB_PATH", "./lancedb")

    store = VectorStore(db_path)
    total_chunks = store.count_chunks()
    indexed_files = store.get_all_files()

    return {
        "total_chunks": total_chunks,
        "total_files": len(indexed_files),
        "indexed_files": sorted(indexed_files),
    }


@mcp.tool(
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True}
)
def reindex_file(
    file_path: Annotated[str, Field(description="Absolute path to the file to re-index")],
    db_path: Annotated[
        str | None,
        Field(
            description="Path to the LanceDB database. Uses LANCEDB_PATH env var if omitted.",
            default=None,
        ),
    ] = None,
) -> dict:
    """Force re-index a single file, ignoring the content hash cache.

    Deletes existing chunks for this file, re-parses, re-chunks,
    re-embeds, and stores new chunks. Useful when you know a file
    has changed or when parsing was updated.
    """
    from pathlib import Path
    from server.parsers import extract_text
    from server.chunker import chunk_document
    from server.indexer import embed_chunks, compute_file_hash
    from server.store import VectorStore

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if db_path is None:
        db_path = os.environ.get("LANCEDB_PATH", "./lancedb")

    store = VectorStore(db_path)
    store.delete_by_file(str(path))

    parts = extract_text(path)
    chunks = chunk_document(parts, path)
    file_hash = compute_file_hash(path)

    if chunks:
        chunks = embed_chunks(chunks)
        for c in chunks:
            c["content_hash"] = file_hash
        store.add_chunks(chunks)

    return {
        "status": "reindexed",
        "file_path": file_path,
        "chunks_created": len(chunks),
    }


def run():
    mcp.run()


if __name__ == "__main__":
    run()
