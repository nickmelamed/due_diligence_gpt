---
name: setup-vision
description: Pull the qwen2.5vl:7b Ollama model and enable the chart vision extractor in a config file.
disable-model-invocation: true
---

Set up chart extraction.

1. Check that Ollama is reachable at `http://localhost:11434`. If not, stop
   and tell the owner.
2. Show the model size and ask before running `ollama pull qwen2.5vl:7b`.
3. Write a config such as `outputs/vision_config.json` with
   `{"vision": {"enabled": true}}`. Do not edit code defaults.
4. Run `./due_gpt/bin/python -m ddgpt run --input sample_docs --out outputs/vision_demo --config outputs/vision_config.json`.
5. Report any `chart_extractions` found. Treat them as leads to verify, not
   facts.
6. Do not use `llama3.2-vision`. It fails on current Ollama versions.
