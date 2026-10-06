from __future__ import annotations

import io
from typing import Any, Dict, List, Optional, Set

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ddgpt.extract.metric_registry import format_metric_value

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
    title = (
        "IRR Figures Across Source Documents"
        if not has_conflict
        else "Unreconciled IRR Figures Across Source Documents"
    )
    ax.set_title(title, fontsize=11, fontweight="bold", color=COLOR_NAVY, pad=14)

    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# Generic (non-IRR-specific) reconciliation chart, for any metric with
# values across 2+ documents. Unlike collect_irr_figures/
# render_irr_reconciliation_chart above, there's no prose-mention scan for
# an arbitrary metric (that's a much bigger, IRR-specific NER-style feature
# -- see layout/irr_mentions.py), so "conflict" here means "a
# NumericMismatchRule flag actually named this metric for this document",
# not a reconciled-vs-prose-mention distinction.

def docs_flagged_for_metric(flags: List[Dict[str, Any]], metric_name: str) -> Set[str]:
    """Which documents a NumericMismatchRule flag named for this metric --
    so a chart's "conflict" coloring can never drift from what a real flag
    actually found, the same principle collect_irr_figures already applies
    for IRR mention conflicts."""
    names: Set[str] = set()
    for f in flags:
        if f.get("metric") != metric_name:
            continue
        for part in (f.get("docs") or "").split(" vs "):
            part = part.strip()
            if part:
                names.add(part)
    return names


def collect_metric_figures(
    extracted: List[Dict[str, Any]],
    metric_name: str,
    conflicting_doc_names: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """Every document's value for a given metric name -- the generic
    counterpart to collect_irr_figures, for any metric the registry knows
    about or any custom one an extractor found."""
    conflicting_doc_names = conflicting_doc_names or set()
    figures: List[Dict[str, Any]] = []

    for doc in extracted:
        doc_name = doc.get("doc_name", "")
        for m in doc.get("metrics") or []:
            if m.get("name") != metric_name or m.get("value") is None:
                continue
            figures.append({
                "label": m.get("raw_label") or metric_name,
                "doc_name": doc_name,
                "value": m["value"],
                "unit": m.get("unit", "other"),
                "status": "conflict" if doc_name in conflicting_doc_names else "extracted",
            })

    return figures


def render_metric_reconciliation_chart(figures: List[Dict[str, Any]], title: Optional[str] = None) -> Optional[bytes]:
    """Generic counterpart to render_irr_reconciliation_chart: bar chart for
    any metric's values across documents, value-labels formatted per the
    metric's unit. Returns None if there's nothing worth plotting (fewer
    than 2 distinct figures)."""
    if len(figures) < 2:
        return None

    plt.rcParams["font.family"] = "sans-serif"

    fig, ax = plt.subplots(figsize=(6.4, 3.2), dpi=200)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    labels = [f'{f["label"]}\n({f["doc_name"]})' for f in figures]
    values = [f["value"] for f in figures]
    units = [f.get("unit", "other") for f in figures]
    colors = [COLOR_CONFLICT if f["status"] == "conflict" else COLOR_EXTRACTED for f in figures]

    x = range(len(figures))
    bars = ax.bar(x, values, color=colors, width=0.55, zorder=3)

    value_range = max(values) - min(0, min(values)) or 1
    for rect, value, unit in zip(bars, values, units):
        ax.text(
            rect.get_x() + rect.get_width() / 2,
            rect.get_height() + value_range * 0.03,
            format_metric_value(value, unit),
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
            color=COLOR_INK,
        )

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=8, color=COLOR_INK_SECONDARY)
    ax.set_ylim(0, max(values) * 1.25 if max(values) > 0 else 1)

    ax.set_yticks([])
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(COLOR_MUTED)
    ax.tick_params(axis="x", length=0)

    has_conflict = any(f["status"] == "conflict" for f in figures)
    default_label = figures[0]["label"]
    if title is None:
        title = (
            f"Unreconciled {default_label} Across Source Documents" if has_conflict
            else f"{default_label} Across Source Documents"
        )
    ax.set_title(title, fontsize=11, fontweight="bold", color=COLOR_NAVY, pad=14)

    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()
