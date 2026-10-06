from __future__ import annotations
from typing import List, Dict, Any, Optional
from ddgpt.copilot.recommendation_engine import determine_recommendation
from ddgpt.extract.metric_registry import CATEGORY_ORDER, category_for, display_label, format_metric_value
from ddgpt.extract.quality import metric_confidences


def generate_ic_summary(
    extracted: List[Dict[str, Any]],
    flags: List[Dict[str, Any]],
    memo_prompt: str | None = None,
    recommendation: Optional[Dict[str, Any]] = None,
) -> str:
    lines = []
    lines.append("# IC Diligence Summary")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("- Generated from extracted fields only.")
    lines.append(f"- Documents analyzed: **{len(extracted)}**")
    red = sum(1 for f in flags if f["severity"] == "RED")
    yellow = sum(1 for f in flags if f["severity"] == "YELLOW")
    lines.append(f"- Flags detected: **{red} RED**, **{yellow} YELLOW**")

    confidences = metric_confidences(extracted)
    conf_text = f"{(sum(confidences) / len(confidences)):.0%}" if confidences else "N/A"
    lines.append(
        f"- Data completeness: **{len(confidences)}** metrics extracted across all documents "
        f"(avg confidence **{conf_text}**)"
    )

    if recommendation is None:
        recommendation = determine_recommendation(flags, extracted)
    lines.append(
        f'- Recommendation: **{recommendation["decision"]}** '
        f'(data confidence {recommendation["confidence"]:.2f})'
    )
    lines.append("")

    lines.append("## Key Metrics by Source")
    for d in extracted:
        lines.append(f'### {d["doc_name"]}')
        asof = d.get("doc_date") or "N/A"
        lines.append(f"- As-of: {asof}")

        by_category: Dict[str, list] = {}
        for m in d.get("metrics", []):
            if m.get("value") is None:
                continue
            by_category.setdefault(category_for(m["name"]), []).append(m)

        for category in CATEGORY_ORDER:
            metrics = by_category.get(category)
            if not metrics:
                continue
            for m in sorted(metrics, key=lambda x: display_label(x["name"])):
                value_text = format_metric_value(m["value"], m.get("unit", "other"))
                lines.append(f"- {display_label(m['name'])}: {value_text}")

        if not d.get("metrics"):
            lines.append("- No metrics extracted.")

        lines.append("")

    lines.append("## Evidence")
    for d in extracted:
        lines.append(f'### {d["doc_name"]}')
        has_evidence = False
        for m in d.get("metrics", []):
            if m.get("value") is None:
                continue
            has_evidence = True
            evidence = m.get("evidence") or {}
            lines.append(f'- {display_label(m["name"])}: p.{evidence.get("page")} — "{evidence.get("snippet")}"')
        if not has_evidence:
            lines.append("- No evidence-backed metrics for this document.")
        lines.append("")

    lines.append("## Flags Queue")
    if not flags:
        lines.append("No flags detected.")
    else:
        for f in flags:
            lines.append(f'### {f["severity"]}: {f["type"]}')
            lines.append(f'- Docs: {f["docs"]}')
            lines.append(f'- Detail: {f["detail"]}')
            lines.append(f'- Evidence: {f["evidence"]}')
            lines.append(f'- Why it Matters: {f["why_it_matters"]}')
            lines.append(f'- Question to Ask: {f["question_to_ask"]}')
            lines.append("")
    return "\n".join(lines)
