"""Search logic: embed query, vector/hybrid search, format results."""

import os

from server.store import VectorStore
from server.indexer import get_model


def semantic_search(
    query: str,
    db_path: str | None = None,
    folder_path: str | None = None,
    top_k: int = 10,
    file_type: str | None = None,
    mode: str = "vector",
) -> dict:
    if db_path is None:
        db_path = os.environ.get("LANCEDB_PATH", "./lancedb")

    store = VectorStore(db_path)

    model = get_model()
    query_embedding = model.encode([query], normalize_embeddings=True)[0].tolist()

    if mode == "hybrid":
        store.create_fts_index()
        results = store.hybrid_search(
            query_text=query,
            query_vector=query_embedding,
            top_k=top_k,
            folder_path=folder_path,
            file_type=file_type,
        )
    else:
        results = store.vector_search(
            query_vector=query_embedding,
            top_k=top_k,
            folder_path=folder_path,
            file_type=file_type,
        )

    return {
        "query": query,
        "mode": mode,
        "results": results,
        "total_results": len(results),
    }
