# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Ingest documents into the vector database (run before first use or when adding new docs)
python ingest.py

# Start the Streamlit web app
streamlit run app.py

# Run all tests
pytest test.py -v

# Run a single test by name
pytest test.py -v -k "test_name"
```

## Environment Setup

Requires a `.env` file with:
- `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION`
- `AZURE_OPENAI_CHAT_DEPLOYMENT` (chat model), `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` (embedding model)
- `CORPUS_DIR` (source documents, default `data/raw`), `CHROMA_DIR` (vector DB path, default `./chroma_db2`)
- `COLLECTION` (ChromaDB collection name), `CHUNK_SIZE` (512), `CHUNK_OVERLAP` (64), `TOP_K` (5)

## Architecture

This is a RAG (Retrieval-Augmented Generation) application with Azure OpenAI and ChromaDB, structured in four layers:

**`ingest.py`** — One-time pipeline: loads `.pdf`/`.txt`/`.md` from `CORPUS_DIR`, chunks by token count via tiktoken, embeds with Azure OpenAI, stores in ChromaDB.

**`agent.py`** — Core logic. `retrieve(query)` embeds the query and searches ChromaDB for top-K chunks. `chat(message, history)` runs the agent loop: injects retrieved context into the system prompt, calls Azure OpenAI, and handles tool calls for up to 3 iterations. Returns `(reply, updated_history)`.

**`tools.py`** — Tool implementations. Currently has `get_epa_facilities()`, which queries the EPA Facility Registry Service (FRS) API by ZIP code and program type (SEMS/RCRAINFO/ICIS-AIR/NPDES/TRIS).

**`app.py`** — Streamlit UI. Manages `st.session_state` for conversation history, calls `agent.chat()`, and renders the chat interface.

### Data flow
```
User input → agent.chat()
  → retrieve(): embed query → ChromaDB search → top-K chunks
  → Azure OpenAI (system prompt + context + history + tool schema)
  → [optional] tool_call → get_epa_facilities() → second OpenAI call
  → reply displayed in Streamlit
```

### Tests (`test.py`)
9 test cases using `unittest.mock` to mock AzureOpenAI, ChromaDB, and tiktoken. Tests cover EPA tool execution, retrieval formatting, chat loop with tool calls, and embedding batching.

## Key Design Decisions

- **Token-based chunking**: `ingest.py` uses tiktoken to enforce `CHUNK_SIZE` token limits (not character limits) with `CHUNK_OVERLAP` token overlap between adjacent chunks.
- **Context injection**: Retrieved chunks are formatted and prepended to the system prompt at query time — not stored in the message history.
- **Tool-call loop**: `agent.chat()` loops up to 3 times to handle sequential tool calls before returning a final response.
- **Multiple ChromaDB dirs**: `chroma_db/`, `chroma_db1/`, `chroma_db2/` exist from iterative development. The active one is set by `CHROMA_DIR` in `.env`.
