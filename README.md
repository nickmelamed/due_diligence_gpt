# Due Diligence GPT

This repo is a proof-of-concept for AI-enabled investment due diligence workflows.

It emphasizes:
- Strict schemas (Pydantic)
- Evidence-first extraction (page + snippet)
- Deterministic confidence scoring + document authority weighting
- Contradiction rules (RED/YELLOW)
- Run artifacts + audit logs
- Caching (doc-hash keyed) to avoid repeated model calls
- CLI with reproducible runs
- Tests + a small evaluation harness

For a more comprehensive overview and motivation, check out the design doc [here](https://docs.google.com/document/d/1SKHU_lYtQejw2OVNPCbj42KtVMGRmEKW9S3xc7w0iU4/edit?tab=t.0#heading=h.lb5ydoxel954). 

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
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
- `ic_summary.md` (IC-ready memo)
- `run.log` (audit trail)

## CLI commands

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

## Trust & Guardrails

- **No hallucinations policy**: missing fields are null + listed in `missing_fields`.
- **Evidence required**: every field includes `{doc_name, page, snippet}`.
- **Evidence verification**: if snippet is not found verbatim on the cited page, confidence is reduced and a note is added.
- **Authority weighting**: e.g., LPA/Agreement > audited statements > quarterly letter > marketing deck.

## Tests
```bash
pytest -q
```
