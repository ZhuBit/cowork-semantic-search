from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from server.search import semantic_search
from server.store import VectorStore


def _fake_embed(texts):
    results = []
    for t in texts:
        rng = np.random.RandomState(hash(t) % 2**32)
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        results.append(vec)
    return np.array(results)


def _seed_store(store: VectorStore, texts: list[str], source_file: str = "/fake/doc.txt"):
    chunks = []
    for i, text in enumerate(texts):
        vec = _fake_embed([text])[0]
        chunks.append({
            "id": f"chunk_{hash(text) % 10000}_{i}",
            "text": text,
            "source_file": source_file,
            "file_name": source_file.split("/")[-1],
            "file_type": ".txt",
            "folder_path": str(Path(source_file).parent),
            "chunk_index": i,
            "content_hash": "fakehash",
            "vector": vec.tolist(),
        })
    store.add_chunks(chunks)


@patch("server.search.get_model")
def test_semantic_search_returns_results(mock_get_model, tmp_path):
    mock_model = type("MockModel", (), {"encode": lambda self, texts, **kw: _fake_embed(texts)})()
    mock_get_model.return_value = mock_model

    db_path = str(tmp_path / "testdb")
    store = VectorStore(db_path)
    _seed_store(store, [
        "revenue grew 23% in Q3",
        "python is a programming language",
        "the weather is nice today",
    ])

    result = semantic_search("Q3 revenue growth", db_path=db_path, top_k=2)
    assert result["total_results"] <= 2
    assert len(result["results"]) > 0
    assert "text" in result["results"][0]
    assert "source_file" in result["results"][0]
    assert "score" in result["results"][0]


@patch("server.search.get_model")
def test_semantic_search_empty_store(mock_get_model, tmp_path):
    mock_model = type("MockModel", (), {"encode": lambda self, texts, **kw: _fake_embed(texts)})()
    mock_get_model.return_value = mock_model

    db_path = str(tmp_path / "testdb")
    result = semantic_search("anything", db_path=db_path)
    assert result["results"] == []
    assert result["total_results"] == 0


@patch("server.search.get_model")
def test_semantic_search_with_folder_filter(mock_get_model, tmp_path):
    mock_model = type("MockModel", (), {"encode": lambda self, texts, **kw: _fake_embed(texts)})()
    mock_get_model.return_value = mock_model

    db_path = str(tmp_path / "testdb")
    store = VectorStore(db_path)
    _seed_store(store, ["doc in folder a"], source_file="/folder_a/doc.txt")
    _seed_store(store, ["doc in folder b"], source_file="/folder_b/doc.txt")

    result = semantic_search("doc", db_path=db_path, folder_path="/folder_a")
    for r in result["results"]:
        assert "/folder_a" in r["source_file"]


@patch("server.search.get_model")
def test_semantic_search_hybrid_mode(mock_get_model, tmp_path):
    mock_model = type("MockModel", (), {"encode": lambda self, texts, **kw: _fake_embed(texts)})()
    mock_get_model.return_value = mock_model

    db_path = str(tmp_path / "testdb")
    store = VectorStore(db_path)
    _seed_store(store, [
        "revenue grew 23% in Q3",
        "python is a programming language",
        "the weather is nice today",
    ])

    result = semantic_search("revenue Q3", db_path=db_path, top_k=2, mode="hybrid")
    assert result["total_results"] >= 1
    assert result["mode"] == "hybrid"
    assert "score" in result["results"][0]
