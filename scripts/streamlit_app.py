import streamlit as st
import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd

from ddgpt.pipeline.builders import (
    build_extractors,
    build_rules,
    build_pipeline,
    build_chart_extractor,
    extractor_availability
)

from ddgpt.config import Config

from ddgpt.io.loaders import load_document

from ddgpt.render.pdf_report import (
    render_ic_pdf,
    clean_memo_text
)

from ddgpt.report.tables import (
    to_facts_table
)

load_dotenv()



# Cohere client + extractor/rule/pipeline construction is expensive and
# stateless across uploads -- build it once per server process
@st.cache_resource(show_spinner=False)
def _get_pipeline():
    cfg = Config()
    extractors = build_extractors(cfg)
    rules = build_rules(cfg)
    chart_extractor = build_chart_extractor(cfg)
    return cfg, build_pipeline(cfg, extractors, rules, chart_extractor=chart_extractor)

# PDF parsing, OCR, and table extraction (Camelot/pdfplumber) are all CPU-heavy
# and deterministic for a given file's bytes -- cache on content, not on the
# throwaway temp-file path
@st.cache_data(show_spinner=False)
def _load_document_cached(file_bytes: bytes, file_name: str, ocr_enabled: bool, ocr_dpi: int):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        loaded = load_document(tmp.name, ocr_enabled=ocr_enabled, ocr_dpi=ocr_dpi)

    # load_document derives doc_name from the temp path
    return loaded.model_copy(update={"doc_name": file_name})

st.set_page_config(
    page_title="DDGPT",
    layout="wide"
)

# Access Gate
#
# Streamlit has no built-in auth, and this dashboard handles confidential
# diligence documents. If DDGPT_DASHBOARD_PASSWORD is set, gate the whole
# app behind it; if unset, behave exactly as before (local/dev use).

_dashboard_password = os.getenv("DDGPT_DASHBOARD_PASSWORD")

if _dashboard_password:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("Due Diligence GPT")
        st.caption("This dashboard handles confidential diligence documents. Sign in to continue.")

        entered_password = st.text_input("Password", type="password")

        if st.button("Sign in"):
            if entered_password == _dashboard_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")

        st.stop()

# Custom CSS

st.markdown("""
<style>

.main {
    background-color: #020617;
}

.stMetric {
    background-color: #111827;
    border: 1px solid #1f2937;
    padding: 1rem;
    border-radius: 14px;
}

.flag-card {
    background-color: #111827;
    border-radius: 16px;
    padding: 1.4rem;
    margin-bottom: 1rem;
    border: 1px solid #1f2937;
}

.preview-box {
    background-color: #111827;
    border-radius: 16px;
    padding: 1.5rem;
    border: 1px solid #1f2937;
    line-height: 1.8;
}

.small-label {
    color: #9ca3af;
    font-size: 0.85rem;
    font-weight: 600;
    text-transform: uppercase;
}

.metric-header {
    font-size: 1.4rem;
    font-weight: 700;
}

</style>
""", unsafe_allow_html=True)

# Title 

st.title("Due Diligence GPT")

st.caption(
    "Institutional-grade AI diligence workflows for investment analysis."
)

# File Upload 

uploaded = st.file_uploader(
    "Upload PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

# Session State

if "result" not in st.session_state:
    st.session_state.result = None

if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None

if "last_upload_hash" not in st.session_state:
    st.session_state.last_upload_hash = None

# Helpers

def files_hash(files):
    return tuple(
        (f.name, f.size)
        for f in files
    )

AUDIT_FIELD_LABELS = {
    "aum": "AUM",
    "net_irr": "Net IRR",
    "tvpi": "TVPI",
    "target_irr": "Target IRR",
    "mgmt_fee": "Management Fee",
    "carry": "Carry",
}

def candidates_dataframe(candidates):
    rows = []
    for c in candidates:
        rows.append({
            "Extractor": c["extractor"],
            "Value": c["value"],
            "Confidence": c["confidence"],
            "Trust Weight": c["weight"],
            "Score": c["score"],
            "Selected": "✓" if c["winner"] else "",
        })
    return pd.DataFrame(rows)

# Pipeline

cfg, pipeline = _get_pipeline()

if uploaded:

    current_hash = files_hash(uploaded)

    should_rerun = (
        st.session_state.result is None
        or current_hash != st.session_state.last_upload_hash
    )

    if should_rerun:

        docs = []

        with st.spinner(
            "Running institutional diligence pipeline..."
        ):

            for f in uploaded:
                docs.append(
                    _load_document_cached(
                        f.getvalue(),
                        f.name,
                        cfg.ocr.enabled,
                        cfg.ocr.dpi,
                    )
                )

            result = pipeline.run(docs)

            facts_df = to_facts_table(
                result["extracted"]
            )

            # Write to a temp path, not a relative "ic_memo.pdf" 
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as pdf_tmp:
                render_ic_pdf(
                    output_path=pdf_tmp.name,
                    memo=result["ic_memo"],
                    flags=result["flags"],
                    facts_df=facts_df,
                    risk_score=result["risk_score"],
                    extracted=result["extracted"],
                    recommendation=result["recommendation"]
                )

                pdf_tmp.seek(0)
                pdf_bytes = Path(pdf_tmp.name).read_bytes()

            st.session_state.result = result
            st.session_state.pdf_bytes = pdf_bytes
            st.session_state.last_upload_hash = current_hash

# Display 

if st.session_state.result:

    result = st.session_state.result

    st.success("Pipeline complete")

    # Executive Metrics

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Risk Score",
            f"{result['risk_score']:.2f}"
        )


    recommendation = result["recommendation"]["decision"]

    with col2:
        st.metric(
            "Recommendation",
            recommendation,
            help=f'Confidence: {result["recommendation"]["confidence"]:.2f}'
        )

    with col3:
        st.metric(
            "Documents",
            len(uploaded)
        )

    with col4:
        st.metric(
            "Flags",
            len(result["flags"])
        )

    st.divider()

    # Flag Summary + Expandable Drilldown 

    st.subheader("Key Findings")

    severity_colors = {
        "RED": "#ef4444",
        "YELLOW": "#fbbf24",
        "GREEN": "#34d399"
    }

    for flag in result["flags"]:

        color = severity_colors.get(
            flag["severity"],
            "#60a5fa"
        )

        with st.container():

            st.markdown(
                f"""
                <div style="
                    background-color: {color};
                    color: black;
                    display: inline-block;
                    padding: 0.3rem 0.7rem;
                    border-radius: 999px;
                    font-weight: 700;
                    font-size: 0.75rem;
                    margin-bottom: 0.75rem;
                ">
                {flag["severity"]}
                </div>
                """,
                unsafe_allow_html=True
            )

            st.markdown(
                f"""
                ### {flag["type"].replace("_", " ")}
                """
            )

            st.write(
                flag["detail"]
            )

            st.caption(
                f"Evidence: {flag['evidence']}"
            )

            st.divider()

            with st.expander(
                f"View Detailed Analysis — {flag['type']}"
            ):

                st.markdown(
                    f"""
                    #### Why This Matters

                    {flag["why_it_matters"]}

                    #### Recommended Follow-Up

                    {flag["question_to_ask"]}

                    #### Supporting Evidence

                    `{flag["evidence"]}`

                    #### Source Document

                    `{flag["docs"]}`
                    """
                )
       

    st.divider()

    # Evidence Table

    st.subheader("Extracted Metrics")

    facts_df = to_facts_table(
        result["extracted"]
    )

    display_cols = [
        "doc_name",
        "net_irr_pct",
        "target_irr_pct",
        "tvpi",
        "mgmt_fee_pct",
        "carry_pct"
    ]

    st.dataframe(
        facts_df[display_cols],
        use_container_width=True
    )

    st.divider()

    # Under the Hood - Extraction Audit Trail


    st.subheader("Under the Hood — Extraction Audit Trail")
    st.caption(
        "Every extractor's raw output per field, which one was selected and why, "
        "and any cross-extractor disagreement."
    )

    availability = extractor_availability(cfg)
    status_line = " · ".join(f"{name}: {status}" for name, status in availability.items())
    skipped = {name: status for name, status in availability.items() if status.startswith("skipped")}

    st.caption(f"Extractor status — {status_line}")
    if skipped:
        st.info(
            "Some configured extractors were skipped for this run and did not "
            "contribute any candidates below: "
            + "; ".join(f"{name} ({status})" for name, status in skipped.items())
        )

    for doc in result["extracted"]:
        with st.expander(doc["doc_name"]):

            disagreement_fields = {
                d["field"] for d in doc.get("extractor_disagreements", [])
            }

            any_candidates = False

            for field_key, label in AUDIT_FIELD_LABELS.items():
                candidates = doc.get("extraction_candidates", {}).get(field_key, [])
                if not candidates:
                    continue

                any_candidates = True
                st.markdown(f"**{label}**")

                if field_key in disagreement_fields:
                    st.warning(
                        f"Extractors disagreed on {label} — the selected value "
                        f"may be wrong. Verify manually."
                    )

                st.dataframe(
                    candidates_dataframe(candidates),
                    use_container_width=True,
                    hide_index=True
                )

            if not any_candidates:
                st.caption("No extraction candidates recorded for this document.")

            sections_detected = doc.get("sections_detected")
            if sections_detected:
                st.markdown(f"**Sections detected:** {', '.join(sections_detected)}")

            chart_extractions = doc.get("chart_extractions", [])
            if chart_extractions:
                st.markdown(f"**Charts/graphs detected:** {len(chart_extractions)}")
                for chart in chart_extractions:
                    title = chart.get("title") or "(untitled chart)"
                    chart_type = chart.get("chart_type") or "unknown type"
                    st.caption(f"p.{chart.get('page')} — {chart_type}: {title}")
                    if chart.get("series"):
                        st.dataframe(
                            pd.DataFrame(chart["series"]),
                            use_container_width=True,
                            hide_index=True
                        )
                    elif chart.get("summary"):
                        st.caption(chart["summary"])

            basis = doc.get("net_irr_basis")
            if basis and basis.get("basis"):
                st.markdown(
                    f"**IRR convention:** {basis['basis']} "
                    f"(p.{basis.get('page')}, {basis.get('section') or 'n/a'} — "
                    f"\"{basis.get('snippet')}\")"
                )

            notes = doc.get("notes")
            if notes:
                st.markdown("**Notes:**")
                for note in notes:
                    st.caption(f"- {note}")

    st.divider()

    # Memo Preview

    st.subheader("IC Memo Preview")

    cleaned_memo = clean_memo_text(result['ic_memo'])
    preview = cleaned_memo[:1800]

    preview = (
        preview
        .replace("#", "")
        .replace("*", "")
    )

    st.markdown(
        f"""
        <div class="preview-box">
        {preview}...
        </div>
        """,
        unsafe_allow_html=True
    )

    st.divider()

    # Download

    st.download_button(
        "Download Institutional IC Memo",
        data=st.session_state.pdf_bytes,
        file_name="ic_memo.pdf",
        mime="application/pdf"
    )