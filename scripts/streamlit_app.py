import streamlit as st
import tempfile
import warnings
from dotenv import load_dotenv
import pandas as pd

from ddgpt.pipeline.builders import (
    build_extractors,
    build_rules
)

from ddgpt.pipeline.orchestrator import (
    DiligencePipeline
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

warnings.filterwarnings(
    "ignore",
    message="CropBox missing from /Page"
)

st.set_page_config(
    page_title="DDGPT",
    layout="wide"
)

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

# Pipeline

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

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".pdf"
                ) as tmp:

                    tmp.write(f.read())

                    tmp.flush()

                    docs.append(
                        load_document(tmp.name)
                    )

            cfg = Config()

            extractors = build_extractors(cfg)

            rules = build_rules(cfg)

            pipeline = DiligencePipeline(
                extractors,
                rules
            )

            result = pipeline.run(docs)

            facts_df = to_facts_table(
                result["extracted"]
            )

            render_ic_pdf(
                output_path="ic_memo.pdf",
                memo=result["ic_memo"],
                flags=result["flags"],
                facts_df=facts_df,
                risk_score=result["risk_score"]
            )

            with open(
                "ic_memo.pdf",
                "rb"
            ) as f:
                pdf_bytes = f.read()

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

    recommendation = "INVESTIGATE"

    if result["risk_score"] < 0.3:
        recommendation = "PROCEED"

    elif result["risk_score"] > 0.7:
        recommendation = "HIGH RISK"

    with col2:
        st.metric(
            "Recommendation",
            recommendation
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