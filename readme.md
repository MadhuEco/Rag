# Ecolab RAG Agent — Exercise 1

> **Name:** _Your Name_ &nbsp;|&nbsp; **Cohort:** _Your Cohort ID_

## Structure

```
├── ingest.py        # Load → chunk → embed → store in ChromaDB
├── agent.py         # Retrieval + USGS tool + agent loop
├── app.py           # Streamlit UI
├── data/raw/        # Drop your corpus documents here
├── pyproject.toml
├── .env.example
└── .gitignore
```

## Setup

```bash
# 1. Install dependencies
uv sync

# 2. Configure secrets
cp .env.example .env
# Edit .env and set AZURE_OPENAI_API_KEY

# 3. Add documents to data/raw/  (.pdf, .html, .txt, .md)
#    Suggested: EPA drinking water standards, WHO sanitation guidelines,
#    Ecolab sustainability report, USGS water quality overview

# 4. Ingest corpus (run once; safe to re-run)
uv run python ingest.py

# 5. Start the app
uv run streamlit run app.py
```

## How it works

**Ingestion** (`ingest.py`): Loads PDFs/HTML/TXT from `data/raw/`, splits into 512-token chunks (64-token overlap), embeds via Azure OpenAI `text-embedding-3-small`, and upserts into a local ChromaDB collection.

**Agent** (`agent.py`): On each user turn, embeds the query, retrieves the top-5 most relevant chunks, and injects them as context into the system prompt. The model then decides whether to answer from context or call the USGS Water Quality Portal tool for live data. A tool-call loop (max 3 iterations) handles multi-step tool use.

**UI** (`app.py`): Streamlit chat interface with session history and a reset button.

## Design decisions & trade-offs

See [`docs/writeup.md`](docs/writeup.md).
