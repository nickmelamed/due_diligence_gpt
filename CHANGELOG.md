# Changelog

All notable changes to this project are recorded here. The format follows
Keep a Changelog, and versions follow Semantic Versioning.

## Unreleased

### Added

- Characterization and property tests for the numeric core, and pinned
  known-bug tests for plain-date recency and empty pdfplumber headers.
- Ruff and mypy configuration, with ruff, mypy, and pytest in the Stop gate.

- Core metric coverage (found of seven) in the memo and PDF data-quality table.
- Offline tests for `ddgpt eval`.

### Changed

- Removed the unused `pipeline.scoring.temporal_weight`.
- Rewrapped long lines and tightened comments, docstrings, and README prose.
- `ddgpt eval` exits 1 on FAIL, and the scenario fixture expects `PERCENT_MISMATCH`.
- `requires-python` is `>=3.11`, and deprecated `.dict()` calls use `.model_dump()`.
- `ic_memo.pdf` is no longer tracked.

### Fixed

- Plain `YYYY-MM-DD` document dates now get a real recency weight instead of 0.5.
- pdfplumber tables with empty header cells are no longer dropped for the whole PDF.
