# DDGPT specification

Drafted from the code on `wip/open-metrics` plus the owner's answers.
Status tags: CONFIRMED means the owner stated it, INFERRED means it was read
from the code or README, and OPEN needs an answer. Correct anything wrong.

## 1. Purpose  [INFERRED, owner has not confirmed the summary]

DDGPT is a proof-of-concept diligence copilot for institutional investors. It
reads investment documents (LPAs, quarterly updates, decks, statements),
extracts financial metrics with an ensemble of a regex extractor and one or two
LLMs, reconciles them with trust and authority weights, flags contradictions
within and across documents, and writes an evidence-cited Investment Committee
(IC) memo as markdown and PDF. A human reviewer reads the output. The tool never
makes the decision.

## 2. Integrity rules  [CONFIRMED]

Breaking any of these makes the project wrong or dishonest.

1. No invented values. A metric that is not found is absent, and its core name
   is listed in `missing_fields`. Never fill a default or guess.
2. Every value has evidence. Each metric carries `{doc_name, page, snippet}`. A
   snippet that is not on the cited page lowers confidence and adds a note.
3. Contradictions are flagged, not resolved. Cross-document mismatches,
   extractor disagreements, and gross/net drift surface as flags. They are never
   averaged away or hidden.
4. Chart values are leads, not citations. Vision-extracted chart data is capped
   at confidence 0.60 and presented as something to verify.
5. Runs are reproducible and auditable. Each run records config, input hashes,
   git commit, model names, and output hashes. Cache keys include a schema
   fingerprint so an old cache entry cannot serve a stale shape.
6. A lower-authority document (for example a deck) must not silently override a
   higher one (LPA, audited statements). Today this is enforced only through
   the authority weight on confidence (section 5.4). Nothing ranks documents
   against each other, and conflicts become flags. No test covers it.

Not a rule: "no real data in the repo". The sample documents are synthetic
(section 9).

## 3. Reported results  [CONFIRMED]

These outputs must be honest, since a reader acts on them.

- The IC memo recommendation (APPROVE, INVESTIGATE or PASS) and its confidence
  value (section 6).
- Risk flags and the risk score (section 7).
- Metrics found and data completeness per document (section 8).

## 4. Pipeline  [INFERRED]

```text
PDF/TXT -> load (+OCR fallback, tables, layout) -> extractors per document
 -> fusion (per-metric winner) -> table fallback -> evidence verification
 -> risk rules -> recommendation -> IC memo (Cohere, or template fallback)
 -> markdown / PDF / JSON / audit manifest
```

CLI: `run`, `extract`, `flag`, `report`, `eval` (`src/ddgpt/cli.py`).
Streamlit app: `scripts/streamlit_app.py`.

## 5. Extraction  [INFERRED]

### 5.1 Open metrics
A document yields a list of `MetricEntry` (name, raw_label, unit, value, basis,
confidence, agreement, is_custom, needed_retry, evidence). Names come from a
canonical registry (`metric_registry.py`: AUM, net/gross/target IRR, TVPI, DPI,
fees, carry, and others) or are a slug of whatever label was found
(`is_custom=True`). Units: usd, percent, multiple, count, year, other.
Six legacy named fields (aum, net_irr, tvpi, target_irr, mgmt_fee, carry) are
kept in sync from `metrics` by `sync_legacy_fields` because some rules still
read them.

### 5.2 Extractors
- `RegexExtractor`: deterministic, always on, trust 0.95.
- `CohereExtractor`: needs `CO_API_KEY`, trust 0.70.
- `OllamaExtractor`: local, on if a server answers, trust 0.60.
- An unavailable extractor is skipped and recorded in `extractor_availability`.
- LLM extraction retries once when a registry metric's evidence does not hold
  up (`enable_evidence_retry`). A retried entry gets `needed_retry` and a 0.9
  penalty.
- The optional vision extractor reads charts from page images and is off by
  default. It is skipped when `redact_before_llm` is on, since images cannot be
  redacted.

### 5.3 Fusion
Per metric name, each extractor's candidate scores
`confidence x extractor_weight x evidence_discount`. The highest score wins.
Evidence discount: verbatim 1.0, fuzzy (0.80 match or better) 0.75, missing
snippet 0.50, not found 0.40. All candidates are kept in
`extraction_candidates`.
Table-parsed values are a last resort, used only for metric names no extractor
produced (candidate confidence 0.85).
An extractor that does not report a metric is not a candidate for it.
When distinct values have agreement below 0.85, an `extractor_disagreements`
entry is raised.

### 5.4 Confidence
After fusion, each winner's final confidence is
`(0.35 extraction + 0.25 authority + 0.20 agreement + 0.20 recency) x
evidence_score`, with the retry penalty applied to the evidence score.
Authority comes from the first substring of the lowercased filename found in
`TrustConfig.authority_weights` (lpa 0.98 down to deck 0.55, default 0.50).
Recency decays linearly over ten years (floor 0.30, 0.50 with no date).
`postprocess.temporal_weight` has a known bug that gives plain `YYYY-MM-DD`
dates the neutral 0.50 (see PROGRESS.md).

## 6. Recommendation  [INFERRED]
- 2 or more RED flags: PASS. 1 RED, or 3 or more YELLOW: INVESTIGATE. Otherwise
  APPROVE.
- `confidence` is the mean confidence of every extracted metric that has a
  value. It measures data quality, not decision correctness, and is 0.0 when
  nothing was extracted. The memo calls it "data confidence".
- The recommendation is decided by this deterministic function. The LLM memo is
  instructed to restate it, not to change it.

## 7. Flags and risk score  [INFERRED]

Rules in `src/ddgpt/rules/`:

| Rule | Flag type | Severity |
|---|---|---|
| NumericMismatch (per metric, any two docs) | USD/PERCENT/MULTIPLE/COUNT/YEAR/METRIC_MISMATCH | registry default: RED for aum, mgmt_fee, carry, hurdle_rate, else YELLOW |
| DefinitionDrift (gross vs net, cross-doc and within-doc) | IRR_DEFINITION_DRIFT(_INTERNAL) | YELLOW |
| InternalInconsistency (net IRR < target IRR) | UNDER_TARGET_PERFORMANCE | YELLOW |
| ExtractorDisagreement | EXTRACTOR_DISAGREEMENT | YELLOW |
| IRRMentionConflict (other IRR in prose) | IRR_MENTION_CONFLICT | YELLOW |

Default tolerances: USD 3% relative, percent 2.0 points, multiples 5% relative,
counts 1, years exact. Management fee uses 0.25 points.
Risk score is `1 - exp(-sum(weights)/2)` with RED 1.0 and YELLOW 0.5. It
saturates toward 1.0 and is meant to be de-emphasized next to the flag list.
Open: which of these tolerances are deliberate judgments to pin, and which are
tuning defaults?

## 8. Data quality in the report  [INFERRED]
"Metrics found" counts the metrics present per document, not a fixed six.
Average confidence uses the same helper as the recommendation
(`extract/quality.py`), so the two agree. Open: define "data completeness". The
code reports counts and a mean, not a ratio against an expected set.

## 9. Privacy and cost controls  [INFERRED]
- `redact_before_llm` (default off) masks emails, SSNs, phones, and account
  numbers in text sent to LLMs. Evidence is checked against unredacted pages.
- Disk cache (`.cache/`, pickle, keyed on extractor, model, prompt, schema
  fingerprint, and content). Pickle is read from the local cache only.
- Only synthetic documents live in `sample_docs/` (CONFIRMED).

## 10. Evaluation  [INFERRED]
`ddgpt eval` runs `eval/scenarios/scenario_01` and compares sorted
`(type, severity)` pairs to `expected_flags.json`, logging PASS or FAIL. It
exits 0 either way.
Open: the fixture expects `(MGMT_FEE_MISMATCH, RED)`, but `NumericMismatchRule`
now emits `PERCENT_MISMATCH` with `metric=mgmt_fee`, so the type no longer
matches and the eval likely fails. The severity still matches. Not run, since
it calls LLMs.

## 11. Checks  [CONFIRMED]
The Stop gate runs `check_style.py --changed`, `ruff check`, `mypy` (configured
for `src`), and `pytest -x -q`. Current status is in PROGRESS.md.

## 12. Non-goals and known limits  [INFERRED]
- Not an investment decision tool, and not citation-grade for chart values.
- Cohere and Ollama are the only providers.
- The README repo-structure section is out of date.
