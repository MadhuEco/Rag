import os

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

# ── Config ────────────────────────────────────────────────────────────────────

CHROMA_DIR = "./chroma_db"
COLLECTION = "ecolab_corpus"
TOP_K = 5
CHAT_MODEL = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-5.4-nano")
EMBEDDING_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")

# ── LangChain clients ─────────────────────────────────────────────────────────

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


# ── Tool: EPA FRS Facilities ──────────────────────────────────────────────────

EPA_FRS_URL = "https://frs-public.epa.gov/ords/frs_public2/frs_rest_services.get_facilities"

@tool
def get_epa_facilities(
    zip_code: str,
    pgm_sys_acrnm: str = "SEMS",
    program_output: str = "yes",
) -> str:
    """
    Fetch EPA-regulated facility information from the EPA Facility Registry
    Service (FRS) for a given US ZIP code. Use when the user asks about
    nearby EPA facilities, Superfund sites, or regulated locations at a
    specific ZIP code. Do NOT call for general conceptual questions.

    Args:
        zip_code: US ZIP code to search, e.g. '60085', '77001'.
        pgm_sys_acrnm: EPA program system acronym to filter by.
                       Common values:
                         'SEMS'    — Superfund / hazardous waste sites (default)
                         'RCRAINFO'— Resource Conservation & Recovery Act
                         'ICIS-AIR'— Air emissions facilities
                         'NPDES'   — Water discharge permits
                         'TRIS'    — Toxic Release Inventory
        program_output: Include linked EPA program details ('yes' or 'no').
                        Defaults to 'yes'.
    """
    params = {
        "pgm_sys_acrnm": pgm_sys_acrnm.upper(),
        "zip_code": zip_code.strip(),
        "program_output": program_output,
        "output": "JSON",
    }

    try:
        r = requests.get(EPA_FRS_URL, params=params, timeout=30, verify=False)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return f"Error fetching EPA FRS data: {e}"

    # The API returns a dict with a list under various top-level keys
    facilities = (
        data.get("Results", {}).get("FRSFacility")          # common wrapper
        or data.get("Facilities")
        or (data if isinstance(data, list) else None)
    )

    if not facilities:
        return (
            f"No EPA facilities found for ZIP code {zip_code} "
            f"under program '{pgm_sys_acrnm}'."
        )

    lines = [
        f"EPA FRS Facilities — ZIP {zip_code} | Program: {pgm_sys_acrnm.upper()}\n"
    ]
    for i, fac in enumerate(facilities[:5], 1):
        name        = fac.get("FacilityName") or fac.get("PRIMARY_NAME", "N/A")
        registry_id = fac.get("RegistryId")   or fac.get("REGISTRY_ID", "N/A")
        address     = fac.get("LocationAddress") or fac.get("LOCATION_ADDRESS", "N/A")
        city        = fac.get("CityName")     or fac.get("CITY_NAME", "")
        state       = fac.get("StateCode")    or fac.get("STATE_CODE", "")
        lat         = fac.get("Latitude83")   or fac.get("LATITUDE83", "N/A")
        lon         = fac.get("Longitude83")  or fac.get("LONGITUDE83", "N/A")

        # Linked program details (present when program_output='yes')
        programs = fac.get("FRSPrograms") or fac.get("Programs") or []
        prog_summary = ""
        if programs:
            prog_names = [
                p.get("ProgramSystemAcronym") or p.get("PROGRAM_SYS_ACRNM", "")
                for p in programs[:3]
            ]
            prog_summary = f" | Linked programs: {', '.join(filter(None, prog_names))}"

        lines.append(
            f"{i}. {name} (Registry ID: {registry_id})\n"
            f"   Address : {address}, {city}, {state}\n"
            f"   Coords  : {lat}, {lon}{prog_summary}"
        )

    return "\n".join(lines)


# ── Agent setup ───────────────────────────────────────────────────────────────

TOOLS = [get_epa_facilities]

SYSTEM_TEMPLATE = """\
You are an expert assistant for Ecolab's domains: water treatment, hygiene, and sustainability.

You have two information sources:
1. Retrieved document context (injected below) — use for conceptual/factual questions.
2. get_epa_facilities tool — use ONLY when the user asks about EPA-regulated facilities,
   Superfund sites, or compliance locations at a specific US ZIP code.

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