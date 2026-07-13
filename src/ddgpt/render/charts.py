from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Tolerance for treating two IRR-shaped figures as "the same claim restated"
# rather than a conflict -- mirrors IRRMentionConflictRule's default so the
# chart and the flag that motivated it agree on what counts as a discrepancy.
RECONCILE_TOLERANCE_PCT_POINTS = 1.0

# Reserved status colors (see dataviz skill's palette.md) -- not a categorical
# hue cycle. "Extracted" bars use the default categorical blue slot 1 since
# they're all the same status (a normal, structurally-extracted figure);
# "conflicting" bars use the fixed warning status color. Both always carry a
# direct value label, satisfying the accessibility requirement that a status
# color never carries meaning alone.
COLOR_EXTRACTED = "#2a78d6"
COLOR_CONFLICT = "#fab219"
COLOR_INK = "#0b0b0b"
COLOR_INK_SECONDARY = "#52514e"
COLOR_MUTED = "#898781"
COLOR_NAVY = "#16304a"


def collect_irr_figures(extracted: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every distinct IRR-shaped figure across all documents, labeled by
    whether it's one of the six structurally-extracted metrics ("extracted")
    or a prose-mentioned figure that doesn't reconcile with any extracted
    value ("conflict") -- the same distinction IRRMentionConflictRule draws,
    recomputed directly from `extracted` rather than parsed back out of flag
    text, so the chart can't drift from what the rule actually found.

    Returns a list of {label, doc_name, value, status} dicts, deduplicated
    by rounded value so restating the same figure twice doesn't double-plot.
    """
    figures: List[Dict[str, Any]] = []
    known_values: List[float] = []

    for doc in extracted:
        doc_name = doc.get("doc_name", "")

        net_irr = (doc.get("net_irr") or {}).get("value")
        if net_irr is not None:
            figures.append({"label": "Net IRR", "doc_name": doc_name, "value": net_irr, "status": "extracted"})
            known_values.append(net_irr)

        target_irr = (doc.get("target_irr") or {}).get("value")
        if target_irr is not None:
            figures.append({"label": "Target IRR", "doc_name": doc_name, "value": target_irr, "status": "extracted"})
            known_values.append(target_irr)

    seen_conflicts = set()
    for doc in extracted:
        doc_name = doc.get("doc_name", "")
        for mention in doc.get("irr_mentions") or []:
            value = mention.get("value")
            if value is None:
                continue
            if any(abs(value - known) <= RECONCILE_TOLERANCE_PCT_POINTS for known in known_values):
                continue

            dedup_key = (round(value, 1), mention.get("basis"))
            if dedup_key in seen_conflicts:
                continue
            seen_conflicts.add(dedup_key)

            basis = mention.get("basis")
            label = f"{basis.title()} IRR (quoted)" if basis else "IRR (quoted)"
            figures.append({"label": label, "doc_name": doc_name, "value": value, "status": "conflict"})

    return figures


def render_irr_reconciliation_chart(figures: List[Dict[str, Any]]) -> Optional[bytes]:
    """Bar chart comparing every distinct IRR-shaped figure across the
    analyzed documents. Returns PNG bytes, or None if there's nothing worth
    plotting (fewer than 2 distinct figures)."""
    if len(figures) < 2:
        return None

    plt.rcParams["font.family"] = "sans-serif"

    fig, ax = plt.subplots(figsize=(6.4, 3.2), dpi=200)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    labels = [f'{f["label"]}\n({f["doc_name"]})' for f in figures]
    values = [f["value"] for f in figures]
    colors = [COLOR_CONFLICT if f["status"] == "conflict" else COLOR_EXTRACTED for f in figures]

    x = range(len(figures))
    bars = ax.bar(x, values, color=colors, width=0.55, zorder=3)

    for rect, value in zip(bars, values):
        ax.text(
            rect.get_x() + rect.get_width() / 2,
            rect.get_height() + max(values) * 0.03,
            f"{value:.1f}%",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
            color=COLOR_INK,
        )

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=8, color=COLOR_INK_SECONDARY)
    ax.set_ylim(0, max(values) * 1.25)

    ax.set_yticks([])
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(COLOR_MUTED)
    ax.tick_params(axis="x", length=0)

    has_conflict = any(f["status"] == "conflict" for f in figures)
    title = "IRR Figures Across Source Documents" if not has_conflict else "Unreconciled IRR Figures Across Source Documents"
    ax.set_title(title, fontsize=11, fontweight="bold", color=COLOR_NAVY, pad=14)

    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()
