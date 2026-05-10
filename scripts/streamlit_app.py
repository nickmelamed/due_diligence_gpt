import streamlit as st
import tempfile
import warnings
from dotenv import load_dotenv

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
    render_ic_pdf
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

st.title("Due Diligence GPT")

uploaded = st.file_uploader(
    "Upload PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

# SESSION STATE INIT

if "result" not in st.session_state:
    st.session_state.result = None

if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None

if "last_upload_hash" not in st.session_state:
    st.session_state.last_upload_hash = None

# HELPER

def files_hash(files):
    return tuple(
        (f.name, f.size)
        for f in files
    )

# PIPELINE EXECUTION

if uploaded:

    current_hash = files_hash(uploaded)

    should_rerun = (
        st.session_state.result is None
        or current_hash != st.session_state.last_upload_hash
    )

    if should_rerun:

        docs = []

        with st.spinner(
            "Running diligence pipeline..."
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

            render_ic_pdf(
                "ic_memo.pdf",
                result["ic_memo"]
            )

            with open(
                "ic_memo.pdf",
                "rb"
            ) as f:
                pdf_bytes = f.read()

            st.session_state.result = result

            st.session_state.pdf_bytes = pdf_bytes

            st.session_state.last_upload_hash = (
                current_hash
            )

# DISPLAY RESULTS

if st.session_state.result:

    result = st.session_state.result

    st.success("Pipeline complete")

    st.subheader("Risk Score")

    st.metric(
        "Risk Score",
        f"{result['risk_score']:.2f}"
    )

    st.subheader("Flags")

    st.json(result["flags"])

    st.subheader("IC Memo")

    st.markdown(result["ic_memo"])

    st.download_button(
        "Download IC Memo PDF",
        data=st.session_state.pdf_bytes,
        file_name="ic_memo.pdf",
        mime="application/pdf"
    )