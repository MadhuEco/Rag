"""
ingest.py
---------
Load documents from data/raw/, chunk them, embed with Azure OpenAI,
and store in ChromaDB.

Run once before starting the app:
    python ingest.py
"""

import os
import re
from pathlib import Path

import chromadb
import tiktoken
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
CORPUS_DIR = Path("data/raw")
CHROMA_DIR = "./chroma_db"
COLLECTION = "ecolab_corpus"
CHUNK_SIZE = 512    # tokens
CHUNK_OVERLAP = 64  # tokens
EMBEDDING_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")

client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "https://cds-ds-openai-001-x.openai.azure.com/"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
)

enc = tiktoken.get_encoding("cl100k_base")


# ── Document loading ──────────────────────────────────────────────────────────

def load_file(path: Path) -> str:
    if path.suffix == ".pdf":
        from pypdf import PdfReader
        pages = [p.extract_text() or "" for p in PdfReader(str(path)).pages]
        return "\n\n".join(pages)

    # if path.suffix in (".html", ".htm"):
    #     from bs4 import BeautifulSoup
    #     soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    #     for tag in soup(["script", "style", "nav", "footer"]):
    #         tag.decompose()
    #     text = soup.get_text(separator="\n")
    #     return re.sub(r"\n{3,}", "\n\n", text).strip()

    return path.read_text(encoding="utf-8", errors="replace")


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_text(text: str) -> list[str]:
    tokens = enc.encode(text)
    step = CHUNK_SIZE - CHUNK_OVERLAP
    chunks = []
    for start in range(0, len(tokens), step):
        chunk = enc.decode(tokens[start : start + CHUNK_SIZE])
        chunks.append(chunk)
        if start + CHUNK_SIZE >= len(tokens):
            break
    return chunks


# ── Embedding ─────────────────────────────────────────────────────────────────

def embed(texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    supported = {".pdf", ".html", ".htm", ".txt", ".md"}
    files = [f for f in sorted(CORPUS_DIR.glob("**/*")) if f.suffix in supported]

    if not files:
        print(f"No documents found in {CORPUS_DIR}. Add .pdf / .html / .txt files.")
        return

    print(f"Found {len(files)} file(s). Loading and chunking...")

    all_chunks, all_ids, all_meta = [], [], []
    for path in files:
        text = load_file(path)
        chunks = chunk_text(text)
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_ids.append(f"{path.name}::chunk{i}")
            all_meta.append({"source": path.name})
        print(f"  {path.name} → {len(chunks)} chunk(s)")

    print(f"\nEmbedding {len(all_chunks)} chunk(s)...")
    embeddings = embed(all_chunks)

    print(f"Storing in ChromaDB at {CHROMA_DIR}...")
    db = chromadb.PersistentClient(path=CHROMA_DIR)
    col = db.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
    col.upsert(ids=all_ids, embeddings=embeddings, documents=all_chunks, metadatas=all_meta)

    print(f"Done. Collection has {col.count()} chunk(s) total.")


if __name__ == "__main__":
    main()
