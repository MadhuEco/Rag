
import json
import os
from datetime import date, timedelta

import chromadb
import requests
from dotenv import load_dotenv
from langchain.tools import tool
from langchain_community.vectorstores import Chroma
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent

load_dotenv()



CHROMA_DIR = "./chroma_db"
COLLECTION = "ecolab_corpus"
TOP_K = 5
CHAT_MODEL = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-5.4-nano")
EMBEDDING_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")

# ── LangChain clients

llm = AzureChatOpenAI(
    azure_deployment=CHAT_MODEL,
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "https://cds-ds-openai-001-x.openai.azure.com/"),
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    temperature=0,
)

embeddings = AzureOpenAIEmbeddings(
    azure_deployment=EMBEDDING_MODEL,
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "https://cds-ds-openai-001-x.openai.azure.com/"),
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
)

# ── ChromaDB via LangChain ────────────────────────────────────────────────────

_chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)

vectorstore = Chroma(
    client=_chroma_client,
    collection_name=COLLECTION,
    embedding_function=embeddings,
    collection_metadata={"hnsw:space": "cosine"},
)

retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K})


# ── Retrieval helper ──────────────────────────────────────────────────────────

def retrieve(query: str) -> str:
    """Embed query, fetch top-k chunks, return formatted context string."""
    docs = retriever.invoke(query)
    if not docs:
        return "No relevant context found."
    parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        parts.append(f"[Context {i} — {source}]\n{doc.page_content.strip()}")
    return "\n\n".join(parts)


# ── Tool: USGS Water Quality ──────────────────────────────────────────────────

@tool
def get_water_quality(state_code: str, characteristic_name: str = "") -> str:
    """
    Fetch recent water quality measurements from the USGS Water Quality Portal
    for a US state. Use when the user asks for current/recent measured data at a
    specific US location. Do NOT call for general conceptual questions.

    Args:
        state_code: Two-letter US state abbreviation, e.g. 'TX', 'CA'.
        characteristic_name: Parameter to filter by, e.g. 'pH', 'Turbidity',
                             'Dissolved oxygen'. Optional.
    """
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
        r = requests.get(
            "https://www.waterqualitydata.us/data/Result/search",
            params=params,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return f"Error fetching water quality data: {e}"

    if not data:
        label = f"{state_code}" + (f" / {characteristic_name}" if characteristic_name else "")
        return f"No results found for {label}."

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


# ── Agent setup ───────────────────────────────────────────────────────────────

TOOLS = [get_water_quality]

SYSTEM_TEMPLATE = """\
You are an expert assistant for Ecolab's domains: water treatment, hygiene, and sustainability.

You have two information sources:
1. Retrieved document context (injected below) — use for conceptual/factual questions.
2. get_water_quality tool — use ONLY when the user asks for current/recent measured \
data at a specific US location.

Always cite which source you used. Be concise and factual.

---
Retrieved context:

{context}
"""

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_TEMPLATE),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ]
)

agent = create_tool_calling_agent(llm=llm, tools=TOOLS, prompt=prompt)

agent_executor = AgentExecutor(
    agent=agent,
    tools=TOOLS,
    max_iterations=3,
    verbose=False,
    return_intermediate_steps=False,
)


# ── Public chat function (matches app.py contract) ────────────────────────────

def _to_lc_messages(history: list[dict]) -> list:
    """Convert simple {role, content} dicts to LangChain message objects."""
    mapping = {"user": HumanMessage, "assistant": AIMessage}
    return [mapping[m["role"]](content=m["content"]) for m in history if m["role"] in mapping]


def chat(user_message: str, history: list[dict]) -> tuple[str, list[dict]]:
    """
    One agent turn.

    Args:
        user_message: The latest user input.
        history: List of {role, content} dicts (no system message).

    Returns:
        (reply, updated_history)
    """
    context = retrieve(user_message)
    lc_history = _to_lc_messages(history)

    result = agent_executor.invoke(
        {
            "input": user_message,
            "context": context,
            "chat_history": lc_history,
        }
    )

    reply = result.get("output", "")
    updated = history + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": reply},
    ]
    return reply, updated
