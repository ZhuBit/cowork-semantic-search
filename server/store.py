"""LanceDB vector store abstraction."""

from pathlib import Path

import lancedb
import pyarrow as pa

SCHEMA = pa.schema([
    pa.field("id", pa.string()),
    pa.field("text", pa.string()),
    pa.field("source_file", pa.string()),
    pa.field("file_name", pa.string()),
    pa.field("file_type", pa.string()),
    pa.field("folder_path", pa.string()),
    pa.field("chunk_index", pa.int32()),
    pa.field("content_hash", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), 384)),
])

TABLE_NAME = "chunks"


class VectorStore:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._db = lancedb.connect(db_path)
        self._table = None

    def _get_table(self):
        if self._table is None:
            try:
                self._table = self._db.open_table(TABLE_NAME)
            except Exception:
                return None
        return self._table

    def _ensure_table(self):
        table = self._get_table()
        if table is None:
            self._table = self._db.create_table(TABLE_NAME, schema=SCHEMA)
        return self._table

    def add_chunks(self, chunks: list[dict]) -> None:
        table = self._ensure_table()
        rows = []
        for c in chunks:
            rows.append({
                "id": c["id"],
                "text": c["text"],
                "source_file": c["source_file"],
                "file_name": c["file_name"],
                "file_type": c["file_type"],
                "folder_path": c["folder_path"],
                "chunk_index": c["chunk_index"],
                "content_hash": c["content_hash"],
                "vector": c["vector"],
            })
        table.add(rows)

    def count_chunks(self) -> int:
        table = self._get_table()
        if table is None:
            return 0
        return table.count_rows()

    def get_file_hash(self, source_file: str) -> str | None:
        table = self._get_table()
        if table is None:
            return None
        results = (
            table.search()
            .where(f"source_file = '{source_file}'", prefilter=True)
            .select(["content_hash"])
            .limit(1)
            .to_list()
        )
        if results:
            return results[0]["content_hash"]
        return None

    def delete_by_file(self, source_file: str) -> None:
        table = self._get_table()
        if table is None:
            return
        table.delete(f"source_file = '{source_file}'")

    def get_all_files(self) -> list[str]:
        table = self._get_table()
        if table is None:
            return []
        arrow_table = table.to_arrow().select(["source_file"])
        return list(set(arrow_table.column("source_file").to_pylist()))

    def create_fts_index(self) -> None:
        """Create or rebuild the full-text search index on the text column."""
        table = self._get_table()
        if table is None:
            return
        table.create_fts_index("text", replace=True)

    def fts_search(
        self,
        query_text: str,
        top_k: int = 10,
        folder_path: str | None = None,
        file_type: str | None = None,
    ) -> list[dict]:
        table = self._get_table()
        if table is None:
            return []
        if table.count_rows() == 0:
            return []

        try:
            query = table.search(query_text, query_type="fts").limit(top_k)
        except Exception:
            return []

        where_clauses = []
        if folder_path:
            where_clauses.append(f"folder_path = '{folder_path}'")
        if file_type:
            where_clauses.append(f"file_type = '{file_type}'")
        if where_clauses:
            query = query.where(" AND ".join(where_clauses), prefilter=True)

        results = query.to_list()
        return [
            {
                "text": r["text"],
                "source_file": r["source_file"],
                "file_name": r["file_name"],
                "file_type": r["file_type"],
                "folder_path": r["folder_path"],
                "chunk_index": r["chunk_index"],
                "score": r.get("_score", 0.0),
            }
            for r in results
        ]

    def hybrid_search(
        self,
        query_text: str,
        query_vector: list[float],
        top_k: int = 10,
        folder_path: str | None = None,
        file_type: str | None = None,
        rrf_k: int = 60,
    ) -> list[dict]:
        """Combine vector and FTS results using Reciprocal Rank Fusion."""
        vector_results = self.vector_search(
            query_vector, top_k=top_k * 2,
            folder_path=folder_path, file_type=file_type,
        )
        fts_results = self.fts_search(
            query_text, top_k=top_k * 2,
            folder_path=folder_path, file_type=file_type,
        )

        # Build RRF scores keyed by (source_file, chunk_index)
        scores: dict[tuple, float] = {}
        result_map: dict[tuple, dict] = {}

        for rank, r in enumerate(vector_results):
            key = (r["source_file"], r["chunk_index"])
            scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank + 1)
            result_map[key] = r

        for rank, r in enumerate(fts_results):
            key = (r["source_file"], r["chunk_index"])
            scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank + 1)
            if key not in result_map:
                result_map[key] = r

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [
            {**result_map[key], "rrf_score": score, "score": score}
            for key, score in ranked
        ]

    def vector_search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        folder_path: str | None = None,
        file_type: str | None = None,
    ) -> list[dict]:
        table = self._get_table()
        if table is None:
            return []
        if table.count_rows() == 0:
            return []

        query = table.search(query_vector).metric("cosine").limit(top_k)

        where_clauses = []
        if folder_path:
            where_clauses.append(f"folder_path = '{folder_path}'")
        if file_type:
            where_clauses.append(f"file_type = '{file_type}'")
        if where_clauses:
            query = query.where(" AND ".join(where_clauses), prefilter=True)

        results = query.to_list()
        return [
            {
                "text": r["text"],
                "source_file": r["source_file"],
                "file_name": r["file_name"],
                "file_type": r["file_type"],
                "folder_path": r["folder_path"],
                "chunk_index": r["chunk_index"],
                "score": r.get("_distance", 0.0),
            }
            for r in results
        ]
