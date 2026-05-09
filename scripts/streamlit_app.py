import streamlit as st
import tempfile
import json

from ddgpt.pipeline.builders import build_extractors, build_rules
from ddgpt.pipeline.orchestrator import DiligencePipeline
from ddgpt.config import Config
from ddgpt.io.loaders import load_document
from ddgpt.render.pdf_report import render_ic_pdf

st.set_page_config(
    page_title="DDGPT",
    layout="wide"
)

st.title("Due Diligence GPT")

uploaded = st.file_uploader(
    "Upload PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded:
    docs = []

    for f in uploaded:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(f.read())
            tmp.flush()

            docs.append(
                load_document(tmp.name)
            )

    cfg = Config()

    extractors = build_extractors(cfg)
    rules = build_rules(cfg)

    pipeline = DiligencePipeline(extractors, rules)

    with st.spinner("Running diligence pipeline..."):
        result = pipeline.run(docs)

    st.success("Pipeline complete")

    st.subheader("Risk Score")
    st.metric("Risk Score", f"{result['risk_score']:.2f}")

    st.subheader("Flags")

    st.json(result["flags"])

    st.subheader("IC Memo")

    st.markdown(result["ic_memo"])

    render_ic_pdf(
        "ic_memo.pdf",
        result["ic_memo"]
    )

    with open("ic_memo.pdf", "rb") as f:
        st.download_button(
            "Download IC Memo PDF",
            f,
            file_name="ic_memo.pdf"
        )