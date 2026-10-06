---
name: run-demo
description: Run the pipeline on sample_docs and summarize the flags, recommendation, and artifacts. Calls Cohere when CO_API_KEY is set.
disable-model-invocation: true
---

1. Run `./due_gpt/bin/python -m ddgpt run --input sample_docs --out outputs/run_demo`.
2. Show which extractors were active (`extractor_availability` in
   `run_summary.json`). If Cohere or Ollama was skipped, say why.
3. Summarize the flags by severity, the recommendation and its confidence,
   and the metrics found per document.
4. List the artifacts written to `outputs/run_demo`, including
   `audit_manifest.json`.
5. Do not edit any file under `eval/` or `sample_docs/`.
