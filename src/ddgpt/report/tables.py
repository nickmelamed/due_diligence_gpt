from __future__ import annotations
from typing import List, Dict, Any
import pandas as pd

from ddgpt.extract.metric_registry import category_for, display_label


def to_facts_table(extracted: List[Dict[str, Any]]) -> pd.DataFrame:
    """Long format: one row per (document, metric) pair -- doc_name/
    doc_date/category/metric_name/display_label/unit/value/confidence/
    is_custom/page/snippet, plus one doc-level row's worth of
    missing_fields/notes repeated per metric row for convenience.

    Replaces the old wide format (one row per document, a fixed column per
    of the six legacy metrics) which only worked because there were exactly
    six known columns -- an open, per-document-variable metric set has no
    fixed column list to pivot on, so long format is the only shape that
    scales to it without either a sparse wide table or silently dropping
    anything beyond the original six.
    """
    rows = []
    for d in extracted:
        doc_name = d["doc_name"]
        doc_date = d.get("doc_date")
        missing_fields = ", ".join(d.get("missing_fields", []))
        notes = " | ".join(d.get("notes", []))

        for m in d.get("metrics", []):
            evidence = m.get("evidence") or {}
            rows.append({
                "doc_name": doc_name,
                "doc_date": doc_date,
                "category": category_for(m["name"]),
                "metric_name": m["name"],
                "display_label": display_label(m["name"]),
                "unit": m.get("unit"),
                "value": m.get("value"),
                "confidence": m.get("confidence"),
                "is_custom": m.get("is_custom", False),
                "page": evidence.get("page"),
                "snippet": evidence.get("snippet"),
                "missing_fields": missing_fields,
                "notes": notes,
            })

    columns = [
        "doc_name", "doc_date", "category", "metric_name", "display_label", "unit",
        "value", "confidence", "is_custom", "page", "snippet", "missing_fields", "notes",
    ]
    return pd.DataFrame(rows, columns=columns)
