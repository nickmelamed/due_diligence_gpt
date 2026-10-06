# Due Diligence GPT (ddgpt)

A proof-of-concept diligence copilot for institutional investors. It reads
investment documents (LPAs, quarterly updates, decks), extracts financial
metrics with regex and LLM extractors, reconciles them, flags contradictions
across and within documents, and writes an evidence-cited Investment Committee
memo. A human reads the output. "Good" means every number traces to a page and
snippet, and nothing is guessed.

See docs/SPEC.md for the design, docs/DECISIONS.md for the reasons behind it,
and PROGRESS.md for status. Read the relevant SPEC section before changing
what it covers.

## Non-negotiable rules

1. Never invent a value. A metric that is not found is absent and the core
   name goes in `missing_fields`. No defaults, no guesses.
2. Every metric carries evidence `{doc_name, page, snippet}`. Confidence must
   drop when the snippet is not on the cited page. The matching logic lives
   in `extract/evidence.py` only, so do not copy it elsewhere.
3. Contradictions become flags. Never average, drop, or silently resolve a
   disagreement between documents, extractors, or gross and net conventions.
4. Chart-derived values stay capped (`CHART_CONFIDENCE`) and are leads, not
   citations.
5. Runs stay reproducible. Cache keys include `SCHEMA_FINGERPRINT`, so add any
   new model nested in `ExtractedDoc` to that fingerprint list.
6. A lower-authority document must not silently override a higher one.
7. The recommendation comes from `determine_recommendation`. The memo restates
   it. Its confidence measures extraction quality.
8. Never weaken a test, lint rule, or check to make it pass.
9. Ask before changing anything in `.claude/protected-paths`, the evaluation
   design, dependencies, CI, or hooks.

## Commands

```bash
make setup        # install the package and dev tools
make test         # full test suite
make lint         # ruff
make typecheck    # mypy
make agent-check  # the fast checks the Stop hook runs
make ci           # exactly what CI runs
make run          # pipeline on sample_docs (needs CO_API_KEY or Ollama)
make eval         # compare flags to eval/scenarios/scenario_01
```

Use the project venv (`due_gpt/`). Never print or commit `.env`.

## Where things live

- `src/ddgpt/`: library code. `tests/`: tests with synthetic fixtures.
- `scripts/streamlit_app.py`: dashboard. `prompts/`: LLM prompts.
- `sample_docs/`: synthetic documents only. `eval/`: evaluation scenario.
- `docs/SPEC.md`: design spec. `docs/DECISIONS.md`: decision log.
- `.claude/rules/`: path-scoped rules that load when you touch those files.
- `.claude/skills/`: procedures (`/finish-phase`, `/release`).

## How to work here

- Plan before multi-file changes. Write the plan down and wait for approval
  when the task spans several modules or touches the spec.
- A task is done when the Stop hook's checks pass. Include the command output.
- Commit in small atomic Conventional Commits (`type(scope): subject`). Code
  and its tests go in the same commit.
- You may branch and commit locally. Ask before pushing, opening or merging
  pull requests, tagging, or changing dependencies.
- Do not call Cohere or Ollama from tests. Stub the extractor.
- If you repeat a multi-step procedure, or I give you the same instructions
  twice, propose a skill for it in `.claude/skills/` and wait for approval.
