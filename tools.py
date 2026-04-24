import requests
import json


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

    data = json.dumps(data)
    return data