---
name: run-demo
description: Run the pipeline on sample_docs and summarize the flags, recommendation, and artifacts. Calls Cohere when CO_API_KEY is set.
disable-model-invocation: true
---

Run the demo pipeline and report what it produced.

1. Run `./due_gpt/bin/python -m ddgpt run --input sample_docs --out outputs/run_demo`.
2. Never print the API key or open the environment file.
3. Show which extractors were active (`extractor_availability` in
   `run_summary.json`). If Cohere or Ollama was skipped, say why.
4. Summarize the flags by severity, the recommendation and its confidence,
   and the metrics found per document.
5. List the artifacts written to `outputs/run_demo` and confirm
   `audit_manifest.json` exists.
6. Do not edit any file under `eval/` or `sample_docs/`.
