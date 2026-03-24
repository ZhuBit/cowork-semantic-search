# cowork-semantic-search

**Local semantic search for your documents. No API keys. No cloud. No frozen knowledge.**

A Claude Code MCP plugin that indexes your local files into a lightweight vector database and lets Claude search them using natural language — instantly, offline, and in any language.

---

## The Problem

LLMs are powerful, but they have blind spots:

- **Frozen knowledge** — training data has a cutoff. Your latest reports, notes, and contracts don't exist in the model's world.
- **Context window limits** — you can't paste 500 documents into a prompt. Even if you could, it's slow and expensive.
- **Local files are invisible** — Claude can read one file at a time, but can't search across your entire document library for the relevant pieces.

If you work with lots of local documents — project specs, research papers, meeting notes, contracts, reports — you need a way to bridge the gap between what's on your disk and what the LLM can reason about.

## The Solution

**cowork-semantic-search** creates a small, fast local database from your documents. When you ask Claude a question, it searches that database and retrieves only the relevant pieces — so Claude can answer with your actual data, not just its training knowledge.

```
Your documents → chunked → embedded → stored in local vector DB
                                            ↓
              Your question → embedded → similarity search → relevant chunks → Claude answers
```

### What makes it different

- **Fully offline** — runs locally after a one-time model download (~120MB). No API calls, no data leaves your machine.
- **Incremental** — only re-processes files that changed. Re-indexing a folder with 1000 files where 3 changed takes seconds, not minutes.
- **Multilingual** — the embedding model handles German, English, and 50+ other languages natively. Search in one language, find results in another.
- **Hybrid search** — combines semantic similarity (meaning) with full-text search (keywords) via Reciprocal Rank Fusion. Catches what pure vector search misses.
- **Zero config** — install, point at a folder, search. No YAML files, no infrastructure, no databases to manage.

## Supported Formats

| Format | Extension | Details |
|--------|-----------|---------|
| Plain text | `.txt` | UTF-8 with fallback |
| Markdown | `.md` | Raw text preserved |
| PDF | `.pdf` | Page-level extraction with metadata |
| Word | `.docx` | Full paragraph extraction |
| PowerPoint | `.pptx` | Slide-level extraction with metadata |
| CSV | `.csv` | Row-based text extraction |

## Quick Start

### Prerequisites

- Python 3.11+
- Claude Code

### Install

```bash
git clone https://github.com/ZhuBit/cowork-semantic-search.git
cd cowork-semantic-search
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[all,dev]"
```

### Configure Claude Code

Add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "semantic-search": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["-m", "server.main"],
      "cwd": "/absolute/path/to/cowork-semantic-search",
      "env": {
        "PYTHONPATH": "/absolute/path/to/cowork-semantic-search"
      }
    }
  }
}
```

### Use

Restart Claude Code. Then just talk naturally:

> "Index all documents in ~/Documents/projects"

> "Search for 'quarterly revenue report'"

> "Find anything about authentication in my notes, use hybrid search"

> "What files are currently indexed?"

> "Re-index the updated proposal.pdf"

## Tools

| Tool | Description |
|------|-------------|
| `index_folder` | Index or re-index all documents in a folder. Incremental — skips unchanged files. |
| `semantic_search` | Search indexed documents using natural language. Supports `vector` and `hybrid` modes. |
| `get_index_status` | Show total chunks, file count, and list of indexed files. |
| `reindex_file` | Force re-index a single file, bypassing the hash cache. |

## How It Works

1. **Parse** — extract text from each document, preserving structure (pages, slides)
2. **Chunk** — split into ~400 character overlapping pieces for precise retrieval
3. **Embed** — convert each chunk into a 384-dimensional vector using `paraphrase-multilingual-MiniLM-L12-v2`
4. **Store** — save chunks + vectors in a LanceDB database (a local file, no server needed)
5. **Search** — embed your query, find nearest chunks by cosine similarity, optionally combine with full-text keyword search via RRF

## Use as a Python Library

```python
from server.indexer import index_folder
from server.search import semantic_search

# Index a folder
result = index_folder("/path/to/docs")
print(f"{result['files_indexed']} files → {result['total_chunks']} chunks")

# Search
results = semantic_search("project deadline", mode="hybrid")
for r in results["results"]:
    print(f"  {r['file_name']}: {r['text'][:100]}...")
```

## Architecture

```
server/
  ├── main.py       # MCP server + tool definitions
  ├── parsers.py    # Per-format text extraction
  ├── chunker.py    # Text splitting with metadata
  ├── indexer.py    # Discovery, hashing, embedding pipeline
  ├── store.py      # LanceDB vector store + FTS + hybrid search
  └── search.py     # Query embedding + search orchestration
```

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| MCP framework | FastMCP | Clean tool definitions, async support |
| Embeddings | sentence-transformers | Offline, multilingual, fast |
| Vector DB | LanceDB | Serverless, embedded, FTS built-in |
| Chunking | langchain-text-splitters | Battle-tested recursive splitting |
| PDF | PyMuPDF | Fast, accurate extraction |
| DOCX | python-docx | Lightweight, no system deps |
| PPTX | python-pptx | Slide-level extraction |

## Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

56 tests covering parsers, chunking, indexing, search, and MCP tool integration.

## License

MIT
