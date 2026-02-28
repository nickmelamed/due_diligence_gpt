#!/usr/bin/env bash
set -euo pipefail
# Demo runner (no editable install needed)
PYTHONPATH=src python -m ddgpt run --input sample_docs --out outputs/run_demo
