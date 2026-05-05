"""Generates architecture.png — clean, simple, no overlapping boxes."""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

# ── Canvas ────────────────────────────────────────────────────────────────────
FIG_W, FIG_H = 14, 18
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
ax.set_xlim(0, FIG_W)
ax.set_ylim(0, FIG_H)
ax.axis("off")
fig.patch.set_facecolor("#F5F7FA")

# ── Palette ───────────────────────────────────────────────────────────────────
BLUE_FC,   BLUE_EC   = "#D6E8FF", "#2563A8"
TEAL_FC,   TEAL_EC   = "#CCF0F3", "#0E7C86"
PURPLE_FC, PURPLE_EC = "#EDE0FF", "#5B21B6"
ORANGE_FC, ORANGE_EC = "#FFE8CC", "#C2610F"
RED_FC,    RED_EC    = "#FFE0E0", "#B91C1C"
GREEN_FC,  GREEN_EC  = "#D4F0E0", "#166534"
GRAY_FC,   GRAY_EC   = "#EFEFEF", "#777777"
ARROW_CLR  = "#444444"

# ── Helpers ───────────────────────────────────────────────────────────────────
def draw_box(cx, cy, w, h, fc, ec, title, subtitle=""):
    """Draw a rounded box centred at (cx, cy)."""
    x, y = cx - w / 2, cy - h / 2
    rect = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0,rounding_size=0.25",
        linewidth=2, edgecolor=ec, facecolor=fc, zorder=3,
    )
    ax.add_patch(rect)
    if subtitle:
        ax.text(cx, cy + 0.18, title, fontsize=11, weight="bold",
                color=ec, ha="center", va="center", zorder=4)
        ax.text(cx, cy - 0.22, subtitle, fontsize=8.5,
                color="#555555", ha="center", va="center", zorder=4)
    else:
        ax.text(cx, cy, title, fontsize=11, weight="bold",
                color=ec, ha="center", va="center", zorder=4)


def draw_arrow(x1, y1, x2, y2, lbl="", lbl_dx=0.15, lbl_dy=0, color=ARROW_CLR, rad=0.0):
    ax.annotate(
        "", xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(
            arrowstyle="-|>", color=color, lw=1.5,
            mutation_scale=14,
            connectionstyle=f"arc3,rad={rad}",
        ),
        zorder=2,
    )
    if lbl:
        mx = (x1 + x2) / 2 + lbl_dx
        my = (y1 + y2) / 2 + lbl_dy
        ax.text(mx, my, lbl, fontsize=7.5, color=color,
                ha="left", va="center", zorder=5,
                bbox=dict(boxstyle="round,pad=0.18", fc="#F5F7FA",
                          ec="none", alpha=0.9))

# ══════════════════════════════════════════════════════════════════════════════
# BOXES  (cx, cy, w, h)
# ══════════════════════════════════════════════════════════════════════════════

# Row 1 — User
USER_CX, USER_CY = 7, 16.8
draw_box(USER_CX, USER_CY, 3.6, 0.9, BLUE_FC, BLUE_EC,
         "User (Browser)", "http://localhost:8501")

# Row 2 — Streamlit
STRL_CX, STRL_CY = 7, 15.0
draw_box(STRL_CX, STRL_CY, 5.2, 0.9, BLUE_FC, BLUE_EC,
         "Streamlit UI", "app.py")

# Row 3 — Agent  (wide)
AGNT_CX, AGNT_CY = 7, 13.0
draw_box(AGNT_CX, AGNT_CY, 9.0, 1.0, "#E8F0FE", BLUE_EC,
         "Agent", "agent.py")

# Row 4 — three side-by-side nodes
AZ_CX,  AZ_CY  = 2.4,  10.8    # Azure OpenAI
VDB_CX, VDB_CY = 7.0,  10.8    # Vector Database
EPA_CX, EPA_CY = 11.6, 10.8    # EPA Tool

draw_box(AZ_CX,  AZ_CY,  4.0, 0.9, PURPLE_FC, PURPLE_EC, "Azure OpenAI",      "Chat + Embeddings")
draw_box(VDB_CX, VDB_CY, 4.0, 0.9, TEAL_FC,   TEAL_EC,   "Vector Database",   "ChromaDB")
draw_box(EPA_CX, EPA_CY, 4.0, 0.9, ORANGE_FC, ORANGE_EC, "EPA Tool",          "tools.py")

# Row 5 — Ingestion Pipeline  (left-centre) + EPA FRS API (right)
ING_CX,  ING_CY  = 4.7,  8.5
EFRS_CX, EFRS_CY = 11.6, 8.5

draw_box(ING_CX,  ING_CY,  6.0, 0.9, GREEN_FC, GREEN_EC, "Ingestion Pipeline", "ingest.py")
draw_box(EFRS_CX, EFRS_CY, 4.0, 0.9, RED_FC,   RED_EC,   "EPA FRS REST API",   "frs-public.epa.gov")

# Row 6 — Source Documents
SRC_CX, SRC_CY = 4.7, 6.5
draw_box(SRC_CX, SRC_CY, 5.0, 0.9, GRAY_FC, GRAY_EC, "Source Documents", "data/raw/  (.pdf · .txt · .md)")

# ══════════════════════════════════════════════════════════════════════════════
# ARROWS
# ══════════════════════════════════════════════════════════════════════════════

# User → Streamlit
draw_arrow(USER_CX, USER_CY - 0.45, STRL_CX, STRL_CY + 0.45,
           "HTTP / port 8501", lbl_dx=0.12)

# Streamlit ↔ Agent  (down arrow + up arrow for response)
draw_arrow(STRL_CX - 0.15, STRL_CY - 0.45, AGNT_CX - 0.15, AGNT_CY + 0.5,
           "chat(message, history)", lbl_dx=0.12)
draw_arrow(AGNT_CX + 0.15, AGNT_CY + 0.5, STRL_CX + 0.15, STRL_CY - 0.45,
           "(reply, history)", lbl_dx=0.12, color="#888888")

# Agent → Azure OpenAI
draw_arrow(AGNT_CX - 3.2, AGNT_CY - 0.5, AZ_CX + 0.3, AZ_CY + 0.45,
           "completions\n+ embed query", lbl_dx=0.1, lbl_dy=0.1)

# Agent → Vector Database
draw_arrow(AGNT_CX, AGNT_CY - 0.5, VDB_CX, VDB_CY + 0.45,
           "cosine search", lbl_dx=0.12)

# Agent → EPA Tool
draw_arrow(AGNT_CX + 3.2, AGNT_CY - 0.5, EPA_CX - 0.3, EPA_CY + 0.45,
           "tool_call", lbl_dx=0.1, lbl_dy=0.1)

# EPA Tool → EPA FRS API
draw_arrow(EPA_CX, EPA_CY - 0.45, EFRS_CX, EFRS_CY + 0.45,
           "HTTP GET", lbl_dx=0.12)

# EPA FRS API → Agent  (curved back)
draw_arrow(EFRS_CX + 1.6, EFRS_CY + 0.0,
           AGNT_CX + 4.5, AGNT_CY - 0.5,
           "JSON result", lbl_dx=0.12, color="#B45309", rad=-0.35)

# Ingestion → Azure OpenAI  (embed chunks)
draw_arrow(ING_CX - 2.0, ING_CY + 0.45, AZ_CX + 0.5, AZ_CY - 0.45,
           "embed chunks", lbl_dx=0.1, lbl_dy=-0.15)

# Ingestion → Vector Database  (upsert)
draw_arrow(ING_CX + 1.5, ING_CY + 0.45, VDB_CX - 0.5, VDB_CY - 0.45,
           "upsert vectors", lbl_dx=0.12)

# Ingestion → Source Documents
draw_arrow(ING_CX, ING_CY - 0.45, SRC_CX, SRC_CY + 0.45,
           "load files", lbl_dx=0.12)

# ══════════════════════════════════════════════════════════════════════════════
# TITLE & LEGEND
# ══════════════════════════════════════════════════════════════════════════════

ax.text(FIG_W / 2, 17.75, "Ecolab RAG Agent — System Architecture",
        fontsize=15, weight="bold", color="#1A3C5E",
        ha="center", va="center", zorder=4)

# Legend
legend_items = [
    (BLUE_FC,   BLUE_EC,   "UI Layer"),
    ("#E8F0FE", BLUE_EC,   "Agent"),
    (PURPLE_FC, PURPLE_EC, "Azure OpenAI"),
    (TEAL_FC,   TEAL_EC,   "Vector Store"),
    (ORANGE_FC, ORANGE_EC, "EPA Tool"),
    (RED_FC,    RED_EC,    "External API"),
    (GREEN_FC,  GREEN_EC,  "Ingestion"),
    (GRAY_FC,   GRAY_EC,   "Data Source"),
]

leg_y = 5.4
ax.text(9.5, leg_y + 0.55, "Legend", fontsize=9, color="#555",
        weight="bold", ha="left", va="center")

for i, (fc, ec, txt) in enumerate(legend_items):
    col = i % 2
    row = i // 2
    lx = 9.5 + col * 2.2
    ly = leg_y - row * 0.55
    rect = FancyBboxPatch(
        (lx, ly - 0.16), 0.38, 0.32,
        boxstyle="round,pad=0,rounding_size=0.06",
        linewidth=1.4, edgecolor=ec, facecolor=fc, zorder=3,
    )
    ax.add_patch(rect)
    ax.text(lx + 0.5, ly + 0.0, txt, fontsize=8, color="#333",
            ha="left", va="center", zorder=4)

# ── Save ──────────────────────────────────────────────────────────────────────
plt.tight_layout(pad=0.4)
plt.savefig("architecture.png", dpi=150, bbox_inches="tight",
            facecolor=fig.get_facecolor())
print("Saved architecture.png")
