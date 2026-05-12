# Due Diligence GPT

This repo is a proof-of-concept for AI-enabled investment due diligence workflows.

For a more comprehensive overview and motivation, check out the design doc [here](https://docs.google.com/document/d/1SKHU_lYtQejw2OVNPCbj42KtVMGRmEKW9S3xc7w0iU4/edit?tab=t.0#heading=h.lb5ydoxel954). 

## Overview

DDGPT is designed as an evidence-centric diligence copilot for institutional investment workflows. The system ingests investment documents (LPAs, quarterly reports, audited statements, decks, etc.), extracts structured metrics, detects inconsistencies across documents, and generates IC-ready diligence summaries with evidence provenance.

The architecture emphasizes:
- structured extraction
- contradiction detection
- evidence-backed reasoning
- confidence scoring
- authority-aware reconciliation
- auditability and traceability

## Features

- PDF upload + OCR fallback support
- Ensemble extraction pipeline (LLM + deterministic regex extraction)
- Cross-document contradiction detection
- Evidence provenance (`doc_name`, `page`, `snippet`)
- Confidence scoring + authority weighting
- Table extraction from PDFs
- Structured IC memo generation
- Professional PDF report export
- Streamlit dashboard for interactive workflows
- Audit manifests + reproducibility artifacts

---

# Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# system dependencies
brew install tesseract
brew install ghostscript
brew install java

cp .env.example .env

# edit .env to set COHERE_API_KEY

pip install -e .

python -m ddgpt run --input sample_docs --out outputs/run_demo

# Alternative without editable install:
# PYTHONPATH=src python -m ddgpt run --input sample_docs --out outputs/run_demo
```

Artifacts are written to `--out`:
- `config.json` (effective config)
- `inputs.json` (file list + hashes)
- `extracted.json` (structured extraction)
- `flags.json` (contradictions)
- `facts_table.csv` (tabular view)
- `ic_memo.md` (IC-ready memo)
- `ic_memo.pdf` (professional PDF export)
- `run.log` (audit trail)

---

# Streamlit Dashboard

Launch the interactive diligence dashboard:

```bash
streamlit run scripts/streamlit_app.py
```

The dashboard supports:
- multi-PDF upload
- OCR fallback
- table extraction
- contradiction analysis
- evidence inspection
- IC memo rendering
- downloadable PDF reports

I've included a `test_packet.pdf` for you to use for trying out the interface. 

---

# Pipeline Architecture

```text
PDF Upload
    ↓
PDF Parsing / OCR
    ↓
Text + Table Extraction
    ↓
Ensemble Extraction
    ├── Regex Extractor
    └── Cohere Extractor
    ↓
Fusion / Reconciliation
    ↓
Evidence Verification
    ↓
Risk Rules Engine
    ↓
Recommendation Engine
    ↓
IC Memo Generation
    ↓
Markdown + PDF Outputs
```

---

# CLI Commands

- `run` : end-to-end pipeline
- `extract` : extraction only
- `flag` : rules only
- `report` : memo + CSV generation
- `eval` : run a scenario and compare to expected flag types

Example:

```bash
python -m ddgpt.cli extract --input sample_docs --out outputs/extract_only

python -m ddgpt.cli flag --out outputs/extract_only

python -m ddgpt.cli report --out outputs/extract_only
```

---

# Extraction System

DDGPT uses an ensemble extraction architecture:

## Regex Extractor
Deterministic extraction for:
- AUM
- IRR
- TVPI
- management fees
- carry structures

## LLM Extractor
Schema-constrained extraction using Cohere.

## Fusion Layer
Extractor outputs are reconciled using:
- confidence weighting
- extractor trust priors
- authority weighting
- evidence verification

---

# Table Extraction

The system supports table extraction using:
- Camelot
- PDFPlumber

Extracted tables are parsed for:
- fee schedules
- performance metrics
- capital structures
- IRR / TVPI tables
- AUM disclosures

---

# Trust & Guardrails

- **No hallucinations policy**: missing fields are null + listed in `missing_fields`.
- **Evidence required**: every field includes `{doc_name, page, snippet}`.
- **Evidence verification**: if snippet is not found verbatim on the cited page, confidence is reduced and a note is added.
- **Authority weighting**: e.g., LPA/Agreement > audited statements > quarterly letter > marketing deck.
- **Cross-document validation**: inconsistencies trigger rule-based flags.
- **Auditability**: outputs are reproducible via config + input manifests.

---

# Current Rules

## Numeric Mismatch
Flags inconsistencies across:
- AUM
- management fees
- target IRR

## Definition Drift
Detects semantic inconsistencies such as:
- gross vs net IRR definitions

---

# Repo Structure

```text
src/
  copilot/
  extract/
    tables/
  ingestion/
  io/
  pipeline/
  provenance/
  render/
  report/
  risk/
  rules/
  utils/
```

---

# Outputs

The pipeline currently produces:
- structured extraction JSON
- contradiction flags
- tabular fact views
- IC-ready markdown memos
- professional PDF reports
- audit logs

---

# Future Work

Planned upgrades include:
- layout-aware semantic parsing
- section hierarchy reconstruction
- footnote linking
- contradiction graphs
- citation IDs
- uncertainty propagation
- benchmark/eval harness expansion
- institutional memo templates

---

# Tests

```bash
pytest -q
```

