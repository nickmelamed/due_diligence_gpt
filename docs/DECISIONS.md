# Design decisions

Drafted from the code and its comments. Written plainly so they can be edited
into your own words. Each entry says what was chosen, why the code suggests it,
and what it costs. Entries are **[INFERRED]** unless noted.

## D-001: Ensemble of regex and LLMs, not one extractor
Regex is deterministic and trusted most (0.95). Cohere (0.70) and a local Ollama
model (0.60) add recall on prose. Fusion picks one winner per metric and keeps
every candidate. Cost: disagreements need a flag, and trust weights are guesses
that live in config.

## D-002: Open metric set instead of six fixed fields
The original schema had six named fields. It now holds a list of metrics with a
registry of known names and free slugs for the rest. Comparison keys off the
unit type, so unseen metrics still get a tolerance. Cost: legacy fields stay in
sync through `sync_legacy_fields`, and one rule (InternalInconsistency) still reads
them.

## D-003: Evidence is mandatory and checked against the page
Every value cites doc, page, and snippet. Snippets are matched verbatim, then
fuzzily (0.80), and the result scales confidence. The same function is used
at extraction retry, fusion ranking, and final scoring so the three layers
agree. Cost: OCR noise shows up as fuzzy matches and lowers scores.

## D-004: Retry an LLM call once if evidence fails
When a registry metric's snippet does not hold up, the whole call is repeated
once. Cost: up to double the LLM calls for those chunks. Configurable off.

## D-005: Missing means absent
No defaults. Missing core metrics are listed in `missing_fields`, and the memo
prompt tells the LLM not to invent metrics.

## D-006: Flags are surfaced, not resolved
Contradictions across documents, between extractors, and between gross and net
conventions each get a flag. Fusion still picks a winner for the report, but the
discarded value is recorded and a flag asks a human to check it.

## D-007: Recommendation is deterministic and the LLM only writes the memo
Decision thresholds are in code (2 RED = PASS, and so on). The prompt tells the LLM
to restate the decision and to base risks only on flags. The `confidence` shown
is extraction quality, not decision confidence. This was changed after APPROVE
used to show the lowest confidence of the three tiers.

## D-008: Risk score saturates and is de-emphasized
`1 - exp(-w/2)` rises with flag count and severity, so ten RED flags differ from
one. It is shown less prominently than the flag list in the report.

## D-009: Authority from filename substrings
The document type is guessed from keywords in the file name (lpa, audited,
deck, ...). Cheap and transparent. Cost: a misnamed file gets the wrong weight.

## D-010: Table values are a last resort
Camelot/pdfplumber output fills only metric names that no extractor found. It
never competes on score. Footnotes linked to the table are copied into notes.

## D-011: Chart reading is opt-in, local, and capped
A vision model reads chart images, off by default because of cost (one call per
page, 20 pages max). Confidence is capped at 0.60. It is skipped when
redaction is on. `qwen2.5vl:7b` was chosen after `llava` misread a test chart
and `llama3.2-vision` stopped working on current Ollama (per README and config
comments).

## D-012: Disk cache keyed on a schema fingerprint
Pickle cache entries are keyed on extractor, model, prompt, content, and a
hash of every model field name. After a stale pickle crashed the pipeline when
a field was added, any schema change now misses old entries. Cost: a model added
to a cached object must also be added to the fingerprint list.

## D-013: Redaction is narrow and off by default
Only emails, SSNs, phones, and account numbers are masked, so redaction cannot
touch the figures being extracted. Off by default because it may hurt extraction.

## D-014: Audit manifest per run
Each run records code commit, versions, models, input and output hashes, and
timings, so an output file can later be checked against the run that made it.

## D-015: Graceful degradation
Missing API key, no Ollama server, or no vision model means that extractor is
skipped and logged, not a crash. The memo falls back to a template without
Cohere.

## D-016: Package under `src/`, Typer CLI, Streamlit UI
Standard setuptools src layout, `python -m ddgpt`, and a separate Streamlit app
in `scripts/`.
