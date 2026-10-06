# Progress

Current phase and remaining work. CLAUDE.md does not track status.

## Now

Known issues are fixed on `fix/known-issues`, stacked on `chore/agent-standards`.
Nothing on this branch is pushed. `make ci` passes: 233 tests, 1 skipped.

- [ ] Review PRs #1 (migration), #2 (standards), then the fixes PR. Merge in
  that order and retarget each stacked PR to `main` after its base merges.
- [ ] Watch the first CI run. The project-checks step is new and installs
  tesseract, ghostscript and a headless JRE. It has not run on a clean runner.

## Next

- [ ] Confirm the tolerance split in SPEC section 7 (judgments versus tuning).
- [ ] Confirm the SPEC items tagged INFERRED, and the summary in section 1.
- [ ] Decide whether SPEC rule 6 (authority ordering) needs enforcement beyond
  the confidence weight. Nothing ranks documents against each other today.
- [ ] The guard hook blocks any command whose text mentions `.env`, even
  inside a heredoc.

## Done

- [x] Open-metric migration committed from stash (`wip/open-metrics`).
- [x] SPEC.md and DECISIONS.md drafted from the code.
- [x] Agent tooling installed, hooks smoke-tested, four repo skills added.
- [x] Repo-wide style cleanup, ruff and mypy clean, gate on `make agent-check`.
- [x] Characterization and property tests for the numeric core.
- [x] `temporal_weight` treats plain dates as UTC. Tests now assert the fix.
- [x] pdfplumber tables with empty header cells are kept. Short rows and empty
  cells become empty strings, and empty headers get `column_N` placeholders.
- [x] Eval fixture updated to `(PERCENT_MISMATCH, RED)`. `eval` exits 1 on
  FAIL and is covered by an offline test.
- [x] Core metric coverage (found of seven) added to the memo and PDF.
- [x] `requires-python` is `>=3.11`.
- [x] `.dict()` replaced with `.model_dump()`.
- [x] `ic_memo.pdf` untracked and ignored.
- [x] README repo structure rewritten. CI project checks enabled.
