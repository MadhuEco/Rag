import json
import os
from datetime import date, timedelta

import chromadb
import requests
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()


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
            "name": "get_epa_facilities",
            "description": (
                "Fetch EPA-regulated facility information from the EPA Facility Registry "
                "Service (FRS) for a given US ZIP code. Use when the user asks about "
                "nearby EPA facilities, Superfund sites, or regulated locations at a "
                "specific ZIP code. Do NOT call for general conceptual questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "zip_code": {
                        "type": "string",
                        "description": "US ZIP code to search, e.g. '60085', '77001'.",
                    },
                    "pgm_sys_acrnm": {
                        "type": "string",
                        "description": (
                            "EPA program system acronym to filter by. "
                            "Common values: 'SEMS' (Superfund, default), "
                            "'RCRAINFO' (hazardous waste), 'ICIS-AIR' (air emissions), "
                            "'NPDES' (water discharge permits), 'TRIS' (toxic release inventory)."
                        ),
                    },
                    "program_output": {
                        "type": "string",
                        "description": "Include linked EPA program details. 'yes' or 'no'. Defaults to 'yes'.",
                    },
                },
                "required": ["zip_code"],
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

EPA_FRS_URL = "https://frs-public.epa.gov/ords/frs_public2/frs_rest_services.get_facilities"
def get_epa_facilities(
    zip_code: str,
    pgm_sys_acrnm: str = "SEMS",
    program_output: str = "yes",
) -> str:
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
        name        = fac.get("FacilityName") 
        registry_id = fac.get("RegistryId")   
        address     = fac.get("LocationAddress") 
        city        = fac.get("CityName")     
        state       = fac.get("StateAbbr")    
        lat         = fac.get("Latitude83")  
        lon         = fac.get("Longitude83") 

        # Linked program details (present when program_output='yes')
        programs = fac.get("ProgramFacilities")
        prog_summary = ""
        if programs:
            prog_names = [
                p.get("ProgramSystemAcronym")
                for p in programs[:3]
            ]
            prog_summary = f" | Linked programs: {', '.join(filter(None, prog_names))}"

        lines.append(
            f"{i}. {name} (Registry ID: {registry_id})\n"
            f"   Address : {address}, {city}, {state}\n"
            f"   Coords  : {lat}, {lon}{prog_summary}"
        )

    return "\n".join(lines)

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
