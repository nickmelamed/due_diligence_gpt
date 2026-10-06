# Progress

Current phase and remaining work. CLAUDE.md does not track status.

## Now

Agent tooling is on `chore/agent-standards`, stacked on `wip/open-metrics`.
Nothing is pushed.
The gate (style, ruff, mypy, pytest) passes. 223 tests pass, 1 skipped.

- [ ] Review and merge `wip/open-metrics`, then `chore/agent-standards`.
- [ ] Fix bug 1: `postprocess.temporal_weight` returns 0.5 for any date
  without a timezone. A naive datetime minus an aware `now` raises
  `TypeError`, which `except Exception` swallows. Pinned by
  `test_temporal_weight_ignores_plain_dates_known_bug`. `RegexExtractor` reads
  `As-of Date: YYYY-MM-DD`, which is exactly the affected form, so the
  recency term is wrong whenever that date is found.
- [ ] Fix bug 2: `PDFPlumberTableExtractor` raises when a header cell is
  `None`, and `EnsembleTableExtractor` swallows it, so every pdfplumber table
  in that PDF is lost with only a printed message. Pinned in
  `tests/test_pdfplumber_tables.py`. The `type: ignore` on that line marks it.
  Short rows (`row[i]`) are a related risk.

## Next

- [ ] Update `eval/scenarios/scenario_01/expected_flags.json`. It expects
  `(MGMT_FEE_MISMATCH, RED)`, but `NumericMismatchRule` now emits
  `PERCENT_MISMATCH` with `metric=mgmt_fee`. The severity still matches
  (mgmt_fee is RED in the registry). Run `ddgpt eval` with Cohere and Ollama off to
  confirm it fails first. Make `eval` exit non-zero on FAIL.
- [ ] Define "data completeness" (SPEC section 8). Recommended: share of the
  seven core metrics present per document.
- [ ] Confirm which tolerances are judgments and which are tuning values
  (SPEC section 7).
- [ ] Enable the project-checks step in `.github/workflows/agent-checks.yml`
  once `make setup && make ci` works on a clean runner. CI needs system
  packages (tesseract, ghostscript, java) that the workflow does not install.
- [ ] Fix `requires-python` in `pyproject.toml`. The code uses
  `datetime.UTC`, so it needs 3.11 or newer, not 3.9.
- [ ] Update the README "Repo Structure" section. It lists directories that
  no longer match `src/ddgpt/`.
- [ ] Untrack `ic_memo.pdf` at the repo root (generated output).
- [ ] Replace `.dict()` with `.model_dump()` (pydantic deprecation warnings).
- [ ] The guard hook blocks any command whose text mentions `.env`, even
  inside a heredoc.

## Done

- [x] Open-metric migration committed from stash (`wip/open-metrics`).
- [x] SPEC.md and DECISIONS.md drafted from the code. Items marked
  [INFERRED] or [OPEN] need the owner's confirmation.
- [x] Agent tooling installed, hooks smoke-tested, four repo skills added.
- [x] Repo-wide style cleanup, ruff and mypy clean, gate widened.
- [x] Characterization and property tests for the numeric core.
- [x] Removed the unused `scoring.temporal_weight`.

## Open questions for the owner

- Should the lower-authority-never-overrides rule (SPEC rule 6) be stronger
  than confidence weighting? Nothing ranks documents against each other today.
- Is `rules/` too broad in `.claude/protected-paths`?
- Are the `sample_docs` and `ic_memo.pdf` fixtures what you want tracked?
