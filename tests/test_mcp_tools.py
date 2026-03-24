"""Integration tests for FastMCP tool definitions."""

from unittest.mock import patch

import numpy as np
import pytest
from fastmcp import Client

from server.main import mcp


def _fake_embed(texts):
    results = []
    for t in texts:
        rng = np.random.RandomState(hash(t) % 2**32)
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        results.append(vec)
    return np.array(results)


@pytest.fixture
def mock_model():
    model = type("MockModel", (), {"encode": lambda self, texts, **kw: _fake_embed(texts)})()
    with patch("server.indexer.get_model", return_value=model), \
         patch("server.search.get_model", return_value=model):
        yield model


@pytest.fixture
def docs_dir(tmp_path):
    (tmp_path / "readme.md").write_text("# Revenue Report\n\nQ3 revenue grew 23% to 4.2M.")
    (tmp_path / "notes.txt").write_text("Meeting notes about the product launch.")
    return tmp_path


@pytest.mark.anyio
async def test_mcp_lists_tools():
    """MCP server exposes both tools."""
    async with Client(mcp) as client:
        tools = await client.list_tools()
        tool_names = {t.name for t in tools}
        assert "index_folder" in tool_names
        assert "semantic_search" in tool_names


@pytest.mark.anyio
async def test_mcp_index_folder(mock_model, docs_dir, tmp_path):
    """index_folder tool returns expected result format."""
    import os
    os.environ["LANCEDB_PATH"] = str(tmp_path / "testdb")

    async with Client(mcp) as client:
        result = await client.call_tool("index_folder", {"folder_path": str(docs_dir)})
        assert not result.is_error
        assert len(result.content) > 0
        text = result.content[0].text
        assert "completed" in text


@pytest.mark.anyio
async def test_mcp_semantic_search(mock_model, docs_dir, tmp_path):
    """semantic_search tool returns results after indexing."""
    import os
    db_path = str(tmp_path / "testdb")
    os.environ["LANCEDB_PATH"] = db_path

    from server.indexer import index_folder as _index_folder
    _index_folder(str(docs_dir), db_path=db_path)

    async with Client(mcp) as client:
        result = await client.call_tool("semantic_search", {"query": "revenue growth"})
        assert not result.is_error
        assert len(result.content) > 0
        text = result.content[0].text
        assert "results" in text


@pytest.mark.anyio
async def test_mcp_semantic_search_hybrid(mock_model, docs_dir, tmp_path):
    """semantic_search tool supports hybrid mode."""
    import os
    db_path = str(tmp_path / "testdb")
    os.environ["LANCEDB_PATH"] = db_path

    from server.indexer import index_folder as _index_folder
    _index_folder(str(docs_dir), db_path=db_path)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "semantic_search", {"query": "revenue", "mode": "hybrid"}
        )
        assert not result.is_error
        text = result.content[0].text
        assert "hybrid" in text


@pytest.mark.anyio
async def test_mcp_lists_all_tools():
    """MCP server exposes all four tools."""
    async with Client(mcp) as client:
        tools = await client.list_tools()
        tool_names = {t.name for t in tools}
        assert "index_folder" in tool_names
        assert "semantic_search" in tool_names
        assert "get_index_status" in tool_names
        assert "reindex_file" in tool_names


@pytest.mark.anyio
async def test_mcp_get_index_status(mock_model, docs_dir, tmp_path):
    """get_index_status returns stats after indexing."""
    import os
    db_path = str(tmp_path / "testdb")
    os.environ["LANCEDB_PATH"] = db_path

    from server.indexer import index_folder as _index_folder
    _index_folder(str(docs_dir), db_path=db_path)

    async with Client(mcp) as client:
        result = await client.call_tool("get_index_status", {"db_path": db_path})
        assert not result.is_error
        text = result.content[0].text
        assert "total_chunks" in text
        assert "indexed_files" in text


@pytest.mark.anyio
async def test_mcp_get_index_status_empty(tmp_path):
    """get_index_status works on empty/nonexistent db."""
    db_path = str(tmp_path / "emptydb")
    async with Client(mcp) as client:
        result = await client.call_tool("get_index_status", {"db_path": db_path})
        assert not result.is_error
        text = result.content[0].text
        assert "total_chunks" in text


@pytest.mark.anyio
async def test_mcp_reindex_file(mock_model, docs_dir, tmp_path):
    """reindex_file forces re-indexing of a single file."""
    import os
    db_path = str(tmp_path / "testdb")
    os.environ["LANCEDB_PATH"] = db_path

    from server.indexer import index_folder as _index_folder
    _index_folder(str(docs_dir), db_path=db_path)

    file_path = str(docs_dir / "readme.md")
    async with Client(mcp) as client:
        result = await client.call_tool("reindex_file", {"file_path": file_path})
        assert not result.is_error
        text = result.content[0].text
        assert "reindexed" in text.lower() or "completed" in text.lower()
