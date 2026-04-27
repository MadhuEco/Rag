import json
import os
from datetime import date, timedelta

import chromadb
from dotenv import load_dotenv
from openai import AzureOpenAI
from tools import TOOL_SCHEMA, get_epa_facilities


load_dotenv()



CHAT_MODEL = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-5.4-nano")
EMBEDDING_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")

client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "https://cds-ds-openai-001-x.openai.azure.com/"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
)

# ChromaDB — opened once at import time
db = chromadb.PersistentClient(path=os.environ["CHROMA_DIR"])
col = db.get_or_create_collection(os.environ["COLLECTION"], metadata={"hnsw:space": "cosine"})


# ── Retrieval ─────────────────────────────────────────────────────────────────

def retrieve(query: str) -> str:
    """Embed query, fetch top-k chunks, return formatted context string."""
    vector = client.embeddings.create(model=EMBEDDING_MODEL, input=query).data[0].embedding
    results = col.query(query_embeddings=[vector], n_results=int(os.environ["TOP_K"]), include=["documents", "metadatas"])

    parts = []
    for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0]), 1):
        parts.append(f"[Context {i} — {meta.get('source', 'unknown')}]\n{doc.strip()}")

    return "\n\n".join(parts) if parts else "No relevant context found."





# ── Agent loop ────────────────────────────────────────────────────────────────

SYSTEM_BASE = """\
You are an expert assistant for Ecolab's domains: water treatment, hygiene, and sustainability.
You should never answer question apart from these information.

You have two information sources:
1. Retrieved document context (injected below) — use for conceptual/factual questions.
2. get_epa_facilities tool — use ONLY when the user asks about EPA-regulated facilities,
   Superfund sites, or regulated locations at a specific US ZIP code.


Always cite which source you used. Be concise and factual.
"""


def chat(user_message: str, history: list[dict]) -> tuple[str, list[dict]]:
    """
    One agent turn.
    history: list of {role, content} dicts (no system message).
    Returns (reply, updated_history).
    """
    context = retrieve(user_message)
    system = SYSTEM_BASE + "\n\n---\nRetrieved context:\n\n" + context

    messages = [{"role": "system", "content": system}] + history + [{"role": "user", "content": user_message}]

    # Tool-call loop (max 3 iterations)
    for _ in range(3):
        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            tools=TOOL_SCHEMA,
            tool_choice="auto",
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            break

        # Execute tool calls
        messages.append(msg.model_dump(exclude_unset=True))
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            result = get_epa_facilities(**args)
            messages.append({"role": "tool", "tool_call_id": tc.id, "name": tc.function.name, "content": result})

    reply = msg.content or ""
    updated = history + [{"role": "user", "content": user_message}, {"role": "assistant", "content": reply}]
    return reply, updated
