

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, TextLoader, UnstructuredHTMLLoader
from langchain_community.vectorstores import Chroma
from langchain_openai import AzureOpenAIEmbeddings
from langchain_text_splitters import TokenTextSplitter

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

CORPUS_DIR = Path("data/raw")
CHROMA_DIR = "./chroma_db"
COLLECTION = "ecolab_corpus"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64
EMBEDDING_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")

# ── LangChain Embeddings ──────────────────────────────────────────────────────

embeddings = AzureOpenAIEmbeddings(
    azure_deployment=EMBEDDING_MODEL,
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "https://cds-ds-openai-001-x.openai.azure.com/"),
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
)

# ── Text Splitter ─────────────────────────────────────────────────────────────

splitter = TokenTextSplitter(
    encoding_name="cl100k_base",
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
)

# ── Document Loading ──────────────────────────────────────────────────────────

LOADER_MAP = {
    ".pdf":  PyPDFLoader,
    ".html": UnstructuredHTMLLoader,
    ".htm":  UnstructuredHTMLLoader,
    ".txt":  TextLoader,
    ".md":   TextLoader,
}


def load_file(path: Path):
    """Load a file using the appropriate LangChain loader."""
    loader_cls = LOADER_MAP.get(path.suffix)
    if loader_cls is None:
        print(f"  Skipping unsupported file: {path.name}")
        return []
    loader = loader_cls(str(path))
    return loader.load()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    files = [f for f in sorted(CORPUS_DIR.glob("**/*")) if f.suffix in LOADER_MAP]

    if not files:
        print(f"No documents found in {CORPUS_DIR}. Add .pdf / .html / .txt files.")
        return

    print(f"Found {len(files)} file(s). Loading and chunking...")

    all_chunks = []
    for path in files:
        docs = load_file(path)
        if not docs:
            continue

        # Ensure source metadata is set to filename
        for doc in docs:
            doc.metadata["source"] = path.name

        chunks = splitter.split_documents(docs)
        all_chunks.extend(chunks)
        print(f"  {path.name} → {len(chunks)} chunk(s)")

    if not all_chunks:
        print("No chunks produced. Exiting.")
        return

    print(f"\nEmbedding {len(all_chunks)} chunk(s) and storing in ChromaDB...")

    Chroma.from_documents(
        documents=all_chunks,
        embedding=embeddings,
        collection_name=COLLECTION,
        persist_directory=CHROMA_DIR,
        collection_metadata={"hnsw:space": "cosine"},
    )

    print(f"Done. {len(all_chunks)} chunk(s) stored in {CHROMA_DIR!r}.")


if __name__ == "__main__":
    main()