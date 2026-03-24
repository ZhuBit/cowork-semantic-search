import numpy as np
import pytest

from server.store import VectorStore


@pytest.fixture
def store(tmp_path):
    return VectorStore(str(tmp_path / "testdb"))


def _make_chunks(texts: list[str], source_file: str = "/fake/doc.txt", file_hash: str = "abc123"):
    """Helper to create chunk dicts with random embeddings."""
    chunks = []
    for i, text in enumerate(texts):
        rng = np.random.RandomState(hash(text) % 2**32)
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        chunks.append({
            "id": f"chunk_{i}",
            "text": text,
            "source_file": source_file,
            "file_name": source_file.split("/")[-1],
            "file_type": ".txt",
            "folder_path": "/fake",
            "chunk_index": i,
            "content_hash": file_hash,
            "vector": vec.tolist(),
        })
    return chunks


def test_add_and_count(store):
    chunks = _make_chunks(["hello world", "foo bar"])
    store.add_chunks(chunks)
    assert store.count_chunks() == 2


def test_get_file_hash(store):
    chunks = _make_chunks(["text"], source_file="/fake/a.txt", file_hash="hash_abc")
    store.add_chunks(chunks)
    assert store.get_file_hash("/fake/a.txt") == "hash_abc"


def test_get_file_hash_missing(store):
    assert store.get_file_hash("/nonexistent.txt") is None


def test_delete_by_file(store):
    chunks_a = _make_chunks(["chunk a"], source_file="/fake/a.txt")
    chunks_b = _make_chunks(["chunk b"], source_file="/fake/b.txt")
    # Give unique IDs
    chunks_b[0]["id"] = "chunk_b_0"
    store.add_chunks(chunks_a)
    store.add_chunks(chunks_b)
    assert store.count_chunks() == 2

    store.delete_by_file("/fake/a.txt")
    assert store.count_chunks() == 1
    assert store.get_file_hash("/fake/a.txt") is None
    assert store.get_file_hash("/fake/b.txt") is not None


def test_get_all_files(store):
    chunks_a = _make_chunks(["a"], source_file="/fake/a.txt")
    chunks_b = _make_chunks(["b"], source_file="/fake/b.txt")
    chunks_b[0]["id"] = "chunk_b_0"
    store.add_chunks(chunks_a)
    store.add_chunks(chunks_b)
    files = store.get_all_files()
    assert set(files) == {"/fake/a.txt", "/fake/b.txt"}


def test_vector_search(store):
    chunks = _make_chunks(
        ["the cat sat on the mat", "revenue grew 23%", "python programming"],
        source_file="/fake/doc.txt",
    )
    store.add_chunks(chunks)

    # Search with the vector of the first chunk — should return it as top result
    results = store.vector_search(chunks[0]["vector"], top_k=2)
    assert len(results) <= 2
    assert results[0]["text"] == "the cat sat on the mat"


def test_vector_search_empty_store(store):
    results = store.vector_search([0.0] * 384, top_k=5)
    assert results == []


def test_vector_search_with_folder_filter(store):
    chunks_a = _make_chunks(["hello from folder a"], source_file="/folder_a/doc.txt")
    chunks_a[0]["folder_path"] = "/folder_a"
    chunks_b = _make_chunks(["hello from folder b"], source_file="/folder_b/doc.txt")
    chunks_b[0]["id"] = "chunk_b_0"
    chunks_b[0]["folder_path"] = "/folder_b"

    store.add_chunks(chunks_a)
    store.add_chunks(chunks_b)

    results = store.vector_search(
        chunks_a[0]["vector"], top_k=10, folder_path="/folder_a"
    )
    assert len(results) == 1
    assert results[0]["folder_path"] == "/folder_a"


def test_fts_search(store):
    chunks = _make_chunks(
        ["revenue grew 23% in Q3", "the cat sat on the mat", "python programming"],
    )
    store.add_chunks(chunks)
    store.create_fts_index()
    results = store.fts_search("revenue Q3", top_k=2)
    assert len(results) >= 1
    assert "revenue" in results[0]["text"]


def test_fts_search_empty_store(store):
    results = store.fts_search("anything", top_k=5)
    assert results == []


def test_hybrid_search(store):
    chunks = _make_chunks(
        ["revenue grew 23% in Q3", "the cat sat on the mat", "python programming"],
    )
    store.add_chunks(chunks)
    store.create_fts_index()
    # Use the vector of the first chunk and a matching text query
    results = store.hybrid_search(
        query_text="revenue Q3",
        query_vector=chunks[0]["vector"],
        top_k=2,
    )
    assert len(results) >= 1
    assert "revenue" in results[0]["text"]
    assert "rrf_score" in results[0]
