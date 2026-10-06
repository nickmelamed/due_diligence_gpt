# Progress

Current phase and remaining work. CLAUDE.md does not track status.

## Now

Open items are resolved on `chore/resolve-open-items`. Nothing on this branch
is pushed. `make agent-check` passes.

- [ ] Review the PR for this branch.

## Next

Nothing is queued.

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
- [x] SPEC tolerance split, authority rule, and tags confirmed by the owner.
  Rule 6 now says authority only scales confidence, and `tests/test_authority.py`
  checks that conflicts become flags without overwriting a value.
- [x] Standards upgraded to v2.0.1. The guard hook no longer blocks heredoc
  text for `cat` or `tee` that names the environment file.
