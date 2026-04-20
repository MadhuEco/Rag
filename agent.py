"""
agent.py
--------
RAG retrieval, USGS tool definition, and the tool-call loop — all in one place.
Imported by app.py (Streamlit).
"""

import json
import os
from datetime import date, timedelta

import chromadb
import requests
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
CHROMA_DIR = "./chroma_db"
COLLECTION = "ecolab_corpus"
TOP_K = 5
CHAT_MODEL = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-5.4-nano")
EMBEDDING_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")

client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "https://cds-ds-openai-001-x.openai.azure.com/"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
)

# ChromaDB — opened once at import time
_db = chromadb.PersistentClient(path=CHROMA_DIR)
_col = _db.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})


# ── Retrieval ─────────────────────────────────────────────────────────────────

def retrieve(query: str) -> str:
    """Embed query, fetch top-k chunks, return formatted context string."""
    vector = client.embeddings.create(model=EMBEDDING_MODEL, input=query).data[0].embedding
    results = _col.query(query_embeddings=[vector], n_results=TOP_K, include=["documents", "metadatas"])

    parts = []
    for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0]), 1):
        parts.append(f"[Context {i} — {meta.get('source', 'unknown')}]\n{doc.strip()}")

    return "\n\n".join(parts) if parts else "No relevant context found."


# ── Tool: USGS Water Quality ──────────────────────────────────────────────────

TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_water_quality",
            "description": (
                "Fetch recent water quality measurements from the USGS Water Quality Portal "
                "for a US state. Use when the user asks for current/recent measured data at a "
                "specific US location. Do NOT call for general conceptual questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "state_code": {
                        "type": "string",
                        "description": "Two-letter US state abbreviation, e.g. 'TX', 'CA'.",
                    },
                    "characteristic_name": {
                        "type": "string",
                        "description": "Parameter to filter by, e.g. 'pH', 'Turbidity', 'Dissolved oxygen'. Optional.",
                    },
                },
                "required": ["state_code"],
            },
        },
    }
]


def get_water_quality(state_code: str, characteristic_name: str = "") -> str:
    since = (date.today() - timedelta(days=365)).strftime("%m-%d-%Y")
    params = {
        "statecode": f"US:{state_code.upper()}",
        "mimeType": "json",
        "sorted": "yes",
        "startDateLo": since,
        "dataProfile": "resultPhysChem",
        "pageSize": 5,
        "pageNumber": 1,
    }
    if characteristic_name:
        params["characteristicName"] = characteristic_name

    try:
        r = requests.get("https://www.waterqualitydata.us/data/Result/search", params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return f"Error fetching water quality data: {e}"

    if not data:
        return f"No results found for {state_code}" + (f" / {characteristic_name}" if characteristic_name else "") + "."

    lines = [f"USGS Water Quality — {state_code.upper()} ({characteristic_name or 'all parameters'})\n"]
    for i, row in enumerate(data[:5], 1):
        lines.append(
            f"{i}. [{row.get('ActivityStartDate', 'N/A')}] "
            f"{row.get('CharacteristicName', 'N/A')}: "
            f"{row.get('ResultMeasureValue', 'N/A')} "
            f"{row.get('ResultMeasure/MeasureUnitCode', '')}  "
            f"(site: {row.get('MonitoringLocationIdentifier', 'N/A')})"
        )
    return "\n".join(lines)


# ── Agent loop ────────────────────────────────────────────────────────────────

SYSTEM_BASE = """\
You are an expert assistant for Ecolab's domains: water treatment, hygiene, and sustainability.

You have two information sources:
1. Retrieved document context (injected below) — use for conceptual/factual questions.
2. get_water_quality tool — use ONLY when the user asks for current/recent measured data at a specific US location.


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
            result = get_water_quality(**args)
            messages.append({"role": "tool", "tool_call_id": tc.id, "name": tc.function.name, "content": result})

    reply = msg.content or ""
    updated = history + [{"role": "user", "content": user_message}, {"role": "assistant", "content": reply}]
    return reply, updated
