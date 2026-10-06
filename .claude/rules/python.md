---
paths:
  - "src/**/*.py"
  - "scripts/**/*.py"
---

# Python

- Python 3.12 in the project venv (`due_gpt/`). Run tools through it, for
  example `./due_gpt/bin/pytest`.
- Lint is `ruff check` and types are `mypy`. Fix the cause of a finding. Do
  not add `noqa` or `type: ignore` without saying why on the same line.
- Rules and reports read `model.dict()` output, so a new model field must
  work in both forms.
- A field added to a model nested in `ExtractedDoc` also goes in
  `SCHEMA_FINGERPRINT` (`extract/schemas.py`), so stale cache entries miss.
- Tests must not call Cohere or Ollama. Stub the extractor with a small
  synthetic document.
