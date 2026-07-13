from __future__ import annotations
from typing import List, Dict, Any, Optional
from ddgpt.copilot.recommendation_engine import determine_recommendation

def _fmt_money(x):
    if x is None:
        return "N/A"
    if abs(x) >= 1e9:
        return f"${x/1e9:.2f}B"
    if abs(x) >= 1e6:
        return f"${x/1e6:.2f}M"
    return f"${x:,.0f}"

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

    total_fields = 0
    present_confidences = []
    for d in extracted:
        for key in ("aum", "net_irr", "tvpi", "target_irr", "mgmt_fee", "carry"):
            total_fields += 1
            metric = d[key]
            if metric["value"] is not None:
                present_confidences.append(metric["confidence"])
    conf_text = f"{(sum(present_confidences) / len(present_confidences)):.0%}" if present_confidences else "N/A"
    lines.append(
        f"- Data completeness: **{len(present_confidences)}/{total_fields}** core fields extracted "
        f"(avg confidence **{conf_text}**)"
    )

    if recommendation is None:
        recommendation = determine_recommendation(flags)
    lines.append(
        f'- Recommendation: **{recommendation["decision"]}** '
        f'(confidence {recommendation["confidence"]:.2f})'
    )
    lines.append("")

    lines.append("## Key Metrics by Source")
    lines.append("| Source | As-of | AUM | Net IRR | TVPI | Target IRR | Mgmt Fee | Carry |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for d in extracted:
        asof = d.get("doc_date") or "N/A"
        aum = _fmt_money(d["aum"]["value"])
        nir = "N/A" if d["net_irr"]["value"] is None else f'{d["net_irr"]["value"]:.1f}%'
        tv = "N/A" if d["tvpi"]["value"] is None else f'{d["tvpi"]["value"]:.2f}x'
        tirr = "N/A" if d["target_irr"]["value"] is None else f'{d["target_irr"]["value"]:.1f}%'
        fee = "N/A" if d["mgmt_fee"]["value"] is None else f'{d["mgmt_fee"]["value"]:.2f}%'
        carry = "N/A"
        if d["carry"]["value"] is not None and d["carry"]["hurdle"] is not None:
            carry = f'{d["carry"]["value"]:.0f}% over {d["carry"]["hurdle"]:.0f}%'
        elif d["carry"]["value"] is not None:
            carry = f'{d["carry"]["value"]:.0f}%'
        lines.append(f'| {d["doc_name"]} | {asof} | {aum} | {nir} | {tv} | {tirr} | {fee} | {carry} |')
    lines.append("")

    lines.append("## Evidence")
    for d in extracted:
        lines.append(f'### {d["doc_name"]}')
        lines.append(f'- AUM: p.{d["aum"]["evidence"]["page"]} — "{d["aum"]["evidence"]["snippet"]}"')
        lines.append(f'- Mgmt Fee: p.{d["mgmt_fee"]["evidence"]["page"]} — "{d["mgmt_fee"]["evidence"]["snippet"]}"')
        if d["net_irr"]["value"] is not None:
            lines.append(f'- Net IRR: p.{d["net_irr"]["evidence"]["page"]} — "{d["net_irr"]["evidence"]["snippet"]}"')
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
