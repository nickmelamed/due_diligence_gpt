from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
    Image
)

from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle
)

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

from reportlab.lib.enums import (
    TA_CENTER,
    TA_LEFT
)

from reportlab.platypus.flowables import Flowable

from reportlab.lib.units import inch

from datetime import datetime

import pandas as pd
import re
import html
import io

from ddgpt.render.charts import collect_irr_figures, render_irr_reconciliation_chart

METRIC_FIELDS = ("aum", "net_irr", "tvpi", "target_irr", "mgmt_fee", "carry")

# Brand palette -- navy/gold institutional look, consistent with the dataviz
# skill's status/categorical colors used in render/charts.py so the embedded
# chart and the surrounding document read as one system.
NAVY = "#16304a"
GOLD = "#c9a227"
INK = "#0b0b0b"
INK_SECONDARY = "#3f3d38"
MUTED = "#898781"
HAIRLINE = "#d9d6cc"
TILE_BG = "#f7f5ef"

DECISION_COLORS = {
    "APPROVE": "#0ca30c",
    "INVESTIGATE": "#c98500",
    "PASS": "#d03b3b",
}

SEVERITY_ACCENT = {
    "RED": "#d03b3b",
    "YELLOW": "#c98500",
    "GREEN": "#0ca30c",
}

SEVERITY_TINT = {
    "RED": "#fbeceb",
    "YELLOW": "#fdf3df",
    "GREEN": "#eafaea",
}


def compute_data_quality(extracted) -> list[dict]:
    """Per-document extraction quality summary: how many of the six core
    metrics were found, their average confidence, and how evidence
    verification classified each (verbatim / fuzzy / not found) -- derived
    from the same `notes` that postprocess.verify_metric already writes."""
    rows = []
    for d in extracted:
        present = []
        for key in METRIC_FIELDS:
            metric = d.get(key, {})
            if metric.get("value") is not None:
                present.append(metric.get("confidence", 0.0))

        notes = d.get("notes", [])
        fuzzy = sum(1 for n in notes if "matched page fuzzily" in n)
        not_found = sum(1 for n in notes if "not found verbatim" in n)

        rows.append({
            "doc_name": d.get("doc_name", ""),
            "fields_found": len(present),
            "fields_total": len(METRIC_FIELDS),
            "avg_confidence": (sum(present) / len(present)) if present else None,
            "fuzzy_matches": fuzzy,
            "not_found": not_found,
            "missing_fields": len(d.get("missing_fields", [])),
        })
    return rows


def _confidence_tier(value):
    if value is None:
        return "N/A"
    if value >= 0.75:
        return "High"
    if value >= 0.5:
        return "Medium"
    return "Low"


def _fmt_cell(value) -> str:
    """str(value) renders a missing field as 'N/A' consistently -- a bare
    str() call turns a pandas NaN (which a facts_df column mixing real
    values and None across multiple documents coerces None into) into the
    literal text "nan", not the "N/A" a None alone would have produced."""
    if value is None or pd.isna(value):
        return "N/A"
    return str(value)


CONFIDENCE_COLORS = {
    "High": colors.HexColor("#0ca30c"),
    "Medium": colors.HexColor("#c98500"),
    "Low": colors.HexColor("#d03b3b"),
    "N/A": colors.HexColor(MUTED),
}


def strip_code_fences(text: str) -> str:
    """Remove fenced-code markers only, preserving markdown headers/bold/
    lists so the PDF renderer can format them properly instead of receiving
    already-flattened plain text."""
    text = re.sub(r"```(?:markdown)?", "", text)
    text = text.replace("```", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def format_inline(text: str) -> str:
    """Escape raw text for reportlab's mini-XML Paragraph markup, then
    reintroduce **bold**/*italic* as <b>/<i> tags."""
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", text)
    return text


def clean_memo_text(text: str) -> str:

    # Remove fenced markdown
    text = re.sub(
        r"```(?:markdown)?",
        "",
        text
    )

    text = text.replace(
        "```",
        ""
    )

    # Remove markdown headers
    text = re.sub(
        r"(?m)^#+\s*",
        "",
        text
    )

    # Remove horizontal rules
    text = re.sub(
        r"(?m)^---+$",
        "",
        text
    )

    # Remove bold markdown
    text = text.replace("**", "")

    # Normalize spacing
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    return text.strip()


# Page Chrome (header bar + footer, drawn on every page)

PAGE_WIDTH, PAGE_HEIGHT = letter
HEADER_BAR_HEIGHT = 34


def add_page_chrome(canvas, doc):

    canvas.saveState()

    # Top navy bar + gold rule
    canvas.setFillColor(colors.HexColor(NAVY))
    canvas.rect(0, PAGE_HEIGHT - HEADER_BAR_HEIGHT, PAGE_WIDTH, HEADER_BAR_HEIGHT, fill=1, stroke=0)

    canvas.setFillColor(colors.HexColor(GOLD))
    canvas.rect(0, PAGE_HEIGHT - HEADER_BAR_HEIGHT - 3, PAGE_WIDTH, 3, fill=1, stroke=0)

    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawString(48, PAGE_HEIGHT - HEADER_BAR_HEIGHT + 12, "DDGPT")

    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#c7d2e0"))
    canvas.drawString(48 + canvas.stringWidth("DDGPT ", "Helvetica-Bold", 12), PAGE_HEIGHT - HEADER_BAR_HEIGHT + 13, "Autonomous Diligence Workflows")

    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawRightString(PAGE_WIDTH - 48, PAGE_HEIGHT - HEADER_BAR_HEIGHT + 13, "CONFIDENTIAL")

    # Footer
    canvas.setFillColor(colors.HexColor(MUTED))
    canvas.setFont("Helvetica", 9)
    canvas.drawString(48, 24, "Generated by DDGPT  •  Confidential — institutional diligence use only")
    canvas.drawRightString(PAGE_WIDTH - 48, 24, f"Page {doc.page}")

    canvas.restoreState()


# Styles

def build_styles():

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="MemoTitle",
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=colors.HexColor(NAVY),
            spaceAfter=8
        )
    )

    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=20,
            textColor=colors.HexColor(NAVY),
            spaceBefore=18,
            spaceAfter=4
        )
    )

    styles.add(
        ParagraphStyle(
            name="SubHeading",
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            textColor=colors.HexColor(INK_SECONDARY),
            spaceBefore=10,
            spaceAfter=6
        )
    )

    styles.add(
        ParagraphStyle(
            name="Body",
            fontName="Helvetica",
            fontSize=11,
            leading=18,
            textColor=colors.HexColor(INK_SECONDARY),
            spaceAfter=10
        )
    )

    styles.add(
        ParagraphStyle(
            name="CustomBullet",
            fontName="Helvetica",
            fontSize=11,
            leading=18,
            leftIndent=18,
            spaceAfter=6
        )
    )

    styles.add(
        ParagraphStyle(
            name="TableCell",
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor(INK_SECONDARY)
        )
    )

    styles.add(
        ParagraphStyle(
            name="Small",
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor(MUTED)
        )
    )

    styles.add(
        ParagraphStyle(
            name="MetaLabel",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor(MUTED)
        )
    )

    styles.add(
        ParagraphStyle(
            name="MetaValue",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor(INK_SECONDARY)
        )
    )

    styles.add(
        ParagraphStyle(
            name="StatValue",
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor(INK)
        )
    )

    styles.add(
        ParagraphStyle(
            name="StatLabel",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor(MUTED)
        )
    )

    styles.add(
        ParagraphStyle(
            name="BadgeText",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
            textColor=colors.white
        )
    )

    return styles


def section_header(story, styles, number, title):
    story.append(Paragraph(f"{number}. {title.upper()}", styles["SectionTitle"]))
    story.append(HRFlowable(width="100%", thickness=1.4, color=colors.HexColor(GOLD), spaceBefore=2, spaceAfter=12))


# Title Block (page 1 header -- no separate cover page)

def build_title_block(
    story,
    styles,
    risk_score,
    facts_df=None,
    data_quality=None,
    recommendation=None
):

    story.append(Paragraph("Investment Committee Memorandum", styles["MemoTitle"]))

    meta_rows = [
        [Paragraph("Prepared", styles["MetaLabel"]), Paragraph(datetime.now().strftime("%B %d, %Y"), styles["MetaValue"])],
        [Paragraph("Prepared by", styles["MetaLabel"]), Paragraph("DDGPT Autonomous Diligence Engine", styles["MetaValue"])],
        [Paragraph("Reviewed by", styles["MetaLabel"]), Paragraph("Pending IC assignment", styles["MetaValue"])],
    ]
    meta_table = Table(meta_rows, colWidths=[1.1 * inch, 4.5 * inch])
    meta_table.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8))

    if facts_df is not None and len(facts_df):
        doc_names = ", ".join(str(n) for n in facts_df["doc_name"].tolist())
        story.append(
            Paragraph(
                f'<b>Documents analyzed ({len(facts_df)}):</b> {format_inline(doc_names)}',
                styles["Small"]
            )
        )
        story.append(Spacer(1, 12))

    build_stat_tiles(story, styles, risk_score, recommendation, data_quality)

    if data_quality:
        found = sum(r["fields_found"] for r in data_quality)
        total = sum(r["fields_total"] for r in data_quality)
        confidences = [r["avg_confidence"] for r in data_quality if r["avg_confidence"] is not None]
        avg_conf = sum(confidences) / len(confidences) if confidences else None
        conf_text = f"{avg_conf:.0%}" if avg_conf is not None else "N/A"
        n_docs = len(data_quality)

        story.append(Spacer(1, 8))
        story.append(
            Paragraph(
                f"Average extraction confidence {conf_text} across {found} fields spanning "
                f"{n_docs} source document{'s' if n_docs != 1 else ''}.",
                styles["Small"]
            )
        )

    story.append(Spacer(1, 20))


def build_stat_tiles(story, styles, risk_score, recommendation, data_quality):

    recommendation = recommendation or {}
    decision = recommendation.get("decision", "N/A")
    confidence = recommendation.get("confidence", 0.0)
    decision_color = DECISION_COLORS.get(decision, INK)

    found = sum(r["fields_found"] for r in data_quality) if data_quality else 0
    total = sum(r["fields_total"] for r in data_quality) if data_quality else 0

    def tile(value_text, label_text, color=None):
        value_style = styles["StatValue"]
        # A long recommendation word ("INVESTIGATE") wraps to two lines at
        # the base size and collides with the label beneath it -- shrink
        # just that tile's value rather than the whole row, so short values
        # (risk score, %, X/Y) keep the larger, more legible size.
        font_size = 13 if len(value_text) > 8 else value_style.fontSize
        if color or font_size != value_style.fontSize:
            value_style = value_style.clone("StatValueColored")
            if color:
                value_style.textColor = colors.HexColor(color)
            value_style.fontSize = font_size
            value_style.leading = font_size + 3

        # Two stacked rows (value, then label) in a single column -- NOT a
        # single row of two side-by-side cells, which previously squeezed
        # both onto one cramped line and caused text to overlap.
        cell = Table(
            [[Paragraph(value_text, value_style)], [Paragraph(label_text, styles["StatLabel"])]],
            colWidths=[1.55 * inch]
        )
        cell.setStyle(TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        return cell

    tile_col = Table(
        [
            [
                tile(f"{risk_score:.2f}", "RISK SCORE (0–1)"),
                tile(decision, "RECOMMENDATION", decision_color),
                tile(f"{confidence:.0%}", "CONFIDENCE"),
                tile(f"{found} / {total}", "FIELDS EXTRACTED"),
            ]
        ],
        colWidths=[1.55 * inch] * 4
    )

    tile_col.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(TILE_BG)),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor(HAIRLINE)),
        ("LINEAFTER", (0, 0), (-2, -1), 0.75, colors.HexColor(HAIRLINE)),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    story.append(tile_col)


# Risk Finding Cards

def build_flag_card(styles, flag):
    accent = SEVERITY_ACCENT.get(flag["severity"], "#60a5fa")
    tint = SEVERITY_TINT.get(flag["severity"], "#f3f4f6")

    badge = Table(
        [[Paragraph(flag["severity"], styles["BadgeText"])]],
        colWidths=[0.9 * inch]
    )
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(accent)),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    content = [
        [badge],
        [Paragraph(format_inline(flag["type"].replace("_", " ")), styles["SubHeading"])],
        [Paragraph(f'<b>Detail:</b> {format_inline(flag["detail"])}', styles["Body"])],
        [Paragraph(f'<b>Evidence:</b> {format_inline(flag["evidence"])}', styles["Body"])],
        [Paragraph(f'<b>Why It Matters:</b> {format_inline(flag["why_it_matters"])}', styles["Body"])],
        [Paragraph(f'<b>Question to Ask:</b> {format_inline(flag["question_to_ask"])}', styles["Body"])],
    ]

    card = Table(content, colWidths=[6.34 * inch])
    card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(tint)),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor(accent)),
        ("LINEBEFORE", (0, 0), (0, -1), 4, colors.HexColor(accent)),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (0, 0), 10),
    ]))

    return KeepTogether([card, Spacer(1, 14)])


def build_flags_section(story, styles, flags, section_number):

    section_header(story, styles, section_number, "Risk Findings")

    if not flags:
        story.append(Paragraph("No flags detected.", styles["Body"]))
        story.append(Spacer(1, 16))
        return

    for flag in flags:
        story.append(build_flag_card(styles, flag))


# IRR Reconciliation Chart

def build_irr_chart_section(story, styles, extracted):
    if not extracted:
        return

    figures = collect_irr_figures(extracted)
    png_bytes = render_irr_reconciliation_chart(figures)
    if png_bytes is None:
        return

    story.append(Image(io.BytesIO(png_bytes), width=6.34 * inch, height=3.17 * inch))

    has_conflict = any(f["status"] == "conflict" for f in figures)
    if has_conflict:
        caption = (
            "Figure. The IRR figures cited across the analyzed documents do not reconcile "
            "to a single governing number."
        )
    else:
        caption = "Figure. IRR figures extracted across the analyzed documents."

    story.append(Paragraph(caption, styles["Small"]))
    story.append(Spacer(1, 18))


# Evidence Table

def build_evidence_table(
    story,
    styles,
    facts_df,
    section_number
):

    section_header(story, styles, section_number, "Extracted Metrics")

    table_data = [[
        "Document",
        "Net IRR",
        "Target IRR",
        "TVPI",
        "Mgmt Fee",
        "Carry",
        "Confidence"
    ]]

    conf_cols = [c for c in ("aum_conf", "net_irr_conf", "mgmt_fee_conf", "carry_conf") if c in facts_df.columns]
    tier_by_row = []

    for _, row in facts_df.iterrows():

        confs = [row[c] for c in conf_cols if pd.notna(row[c])]
        avg_conf = (sum(confs) / len(confs)) if confs else None
        tier = _confidence_tier(avg_conf)
        tier_by_row.append(tier)

        table_data.append([
            Paragraph(html.escape(str(row["doc_name"]), quote=False), styles["TableCell"]),
            _fmt_cell(row["net_irr_pct"]),
            _fmt_cell(row["target_irr_pct"]),
            _fmt_cell(row["tvpi"]),
            _fmt_cell(row["mgmt_fee_pct"]),
            _fmt_cell(row["carry_pct"]),
            tier if avg_conf is None else f"{tier} ({avg_conf:.0%})"
        ])

    table = Table(
        table_data,
        colWidths=[
            2.1 * inch,
            0.8 * inch,
            0.9 * inch,
            0.7 * inch,
            0.8 * inch,
            0.7 * inch,
            1.1 * inch
        ]
    )

    style_commands = [

        (
            "BACKGROUND",
            (0, 0),
            (-1, 0),
            colors.HexColor(NAVY)
        ),

        (
            "TEXTCOLOR",
            (0, 0),
            (-1, 0),
            colors.white
        ),

        (
            "FONTNAME",
            (0, 0),
            (-1, 0),
            "Helvetica-Bold"
        ),

        (
            "GRID",
            (0, 0),
            (-1, -1),
            0.5,
            colors.HexColor(HAIRLINE)
        ),

        (
            "ROWBACKGROUNDS",
            (0, 1),
            (-1, -1),
            [
                colors.white,
                colors.HexColor("#f7f5ef")
            ]
        ),

        (
            "BOTTOMPADDING",
            (0, 0),
            (-1, 0),
            10
        ),

        (
            "TOPPADDING",
            (0, 0),
            (-1, -1),
            8
        ),

        (
            "BOTTOMPADDING",
            (0, 1),
            (-1, -1),
            8
        ),

        (
            "VALIGN",
            (0, 0),
            (-1, -1),
            "TOP"
        )

    ]

    # Confidence column (last column) gets its tier color as text, so a
    # reviewer can see data quality at a glance without opening the
    # Streamlit "Under the Hood" audit view.
    for row_idx, tier in enumerate(tier_by_row, start=1):
        style_commands.append(
            ("TEXTCOLOR", (-1, row_idx), (-1, row_idx), CONFIDENCE_COLORS[tier])
        )
        style_commands.append(
            ("FONTNAME", (-1, row_idx), (-1, row_idx), "Helvetica-Bold")
        )

    table.setStyle(TableStyle(style_commands))

    story.append(table)

    story.append(
        Spacer(1, 24)
    )


# Data Quality Section

def build_data_quality_section(
    story,
    styles,
    data_quality,
    section_number
):
    if not data_quality:
        return

    section_header(story, styles, section_number, "Data Quality & Evidence Verification")

    story.append(
        Paragraph(
            "How each metric's citation was checked against the source document: "
            "a verbatim match, a fuzzy match (OCR noise/hyphenation), or no match found.",
            styles["Small"]
        )
    )

    story.append(Spacer(1, 8))

    table_data = [[
        "Document",
        "Fields Found",
        "Avg Confidence",
        "Fuzzy Matches",
        "Not Found"
    ]]

    for row in data_quality:
        avg_conf = row["avg_confidence"]
        table_data.append([
            Paragraph(html.escape(str(row["doc_name"]), quote=False), styles["TableCell"]),
            f'{row["fields_found"]}/{row["fields_total"]}',
            "N/A" if avg_conf is None else f"{avg_conf:.0%}",
            str(row["fuzzy_matches"]),
            str(row["not_found"]),
        ])

    table = Table(
        table_data,
        colWidths=[2.6 * inch, 1.1 * inch, 1.2 * inch, 1.1 * inch, 1.0 * inch]
    )

    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(HAIRLINE)),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f5ef")]),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )

    story.append(table)
    story.append(Spacer(1, 24))


# Chart/Visual Extraction Section

def build_chart_section(
    story,
    styles,
    extracted,
    section_number
):
    if not extracted or not any(d.get("chart_extractions") for d in extracted):
        return

    section_header(story, styles, section_number, "Charts & Visual Data Detected")

    story.append(
        Paragraph(
            "Data read from charts/graphs on page images by a vision-capable model, "
            "not cited from extractable text -- verify against the source page before relying on these values.",
            styles["Small"]
        )
    )

    story.append(Spacer(1, 8))

    for doc in extracted:
        charts = doc.get("chart_extractions") or []
        if not charts:
            continue

        story.append(Paragraph(format_inline(doc.get("doc_name", "")), styles["SubHeading"]))

        for chart in charts:
            title = chart.get("title") or "(untitled chart)"
            chart_type = chart.get("chart_type") or "unknown type"
            story.append(
                Paragraph(format_inline(f"p.{chart.get('page')} — {chart_type}: {title}"), styles["Body"])
            )

            series = chart.get("series") or []
            if series:
                series_text = ", ".join(
                    f"{s.get('label')}: {s.get('value')}" if s.get("value") is not None else f"{s.get('label')}"
                    for s in series
                )
                story.append(Paragraph(f"• {format_inline(series_text)}", styles["CustomBullet"]))
            elif chart.get("summary"):
                story.append(Paragraph(f"• {format_inline(chart['summary'])}", styles["CustomBullet"]))

        story.append(Spacer(1, 8))

    story.append(Spacer(1, 16))


# Memo Body

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
BULLET_RE = re.compile(r"^[-*]\s+(.*)$")
NUMBERED_RE = re.compile(r"^\d+\.\s+(.*)$")
HR_RE = re.compile(r"^-{3,}$")


def build_memo_body(
    story,
    styles,
    memo,
    section_number
):

    section_header(story, styles, section_number, "Full IC Memorandum")

    memo = strip_code_fences(memo)
    lines = memo.split("\n")

    for line in lines:

        line = line.strip()

        if not line:
            story.append(Spacer(1, 8))
            continue

        if HR_RE.match(line):
            story.append(Spacer(1, 6))
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            text = format_inline(heading_match.group(2).strip())
            style = styles["SectionTitle"] if level <= 2 else styles["SubHeading"]
            story.append(Paragraph(text, style))
            continue

        bullet_match = BULLET_RE.match(line)
        if bullet_match:
            story.append(
                Paragraph(f"• {format_inline(bullet_match.group(1))}", styles["CustomBullet"])
            )
            continue

        numbered_match = NUMBERED_RE.match(line)
        if numbered_match:
            story.append(
                Paragraph(format_inline(line), styles["CustomBullet"])
            )
            continue

        story.append(
            Paragraph(format_inline(line), styles["Body"])
        )


# Main Render

def render_ic_pdf(
    output_path: str,
    memo: str,
    flags,
    facts_df,
    risk_score,
    extracted=None,
    recommendation=None
):
    data_quality = compute_data_quality(extracted) if extracted else None

    styles = build_styles()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=48,
        leftMargin=48,
        topMargin=64,
        bottomMargin=48
    )

    story = []

    build_title_block(
        story,
        styles,
        risk_score,
        facts_df=facts_df,
        data_quality=data_quality,
        recommendation=recommendation
    )

    build_flags_section(
        story,
        styles,
        flags,
        1
    )

    build_irr_chart_section(
        story,
        styles,
        extracted
    )

    build_evidence_table(
        story,
        styles,
        facts_df,
        2
    )

    build_data_quality_section(
        story,
        styles,
        data_quality,
        3
    )

    build_chart_section(
        story,
        styles,
        extracted,
        4
    )

    build_memo_body(
        story,
        styles,
        memo,
        5
    )

    doc.build(
        story,
        onFirstPage=add_page_chrome,
        onLaterPages=add_page_chrome
    )
