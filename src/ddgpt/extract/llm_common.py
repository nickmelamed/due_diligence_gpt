from __future__ import annotations
import logging
from typing import Callable, Dict, List, Optional

from ddgpt.io.loaders import Page
from ddgpt.extract.schemas import ExtractedDoc, MetricEntry
from ddgpt.extract.metric_registry import (
    all_metrics,
    get as get_metric_def,
    normalize_metric_name,
)
from ddgpt.extract.evidence import get_page_text, classify_evidence_match

logger = logging.getLogger("ddgpt")

# Shared between every LLM-backed extractor (Cohere, Ollama, ...)

# Legacy six named fields -- still the only thing rules/reports read as of
# the open-metric migration's Phase 1. Populated by _backfill_legacy_fields
# from the model's open `metrics` array rather than asked of the model
# directly (see prompts/extract_v1.txt), so the model has one shape to
# produce, not two redundant ones.
METRIC_FIELDS = ["aum", "net_irr", "tvpi", "target_irr", "mgmt_fee", "carry"]

ALLOWED_UNITS = {"usd", "percent", "multiple", "count", "year", "other"}


def chunk_pages(pages: List[Page], max_chars: int) -> List[List[Page]]:
    chunks: List[List[Page]] = []
    current: List[Page] = []
    current_len = 0

    for page in pages:
        page_len = len(page.text or "")
        if current and current_len + page_len > max_chars:
            chunks.append(current)
            current = []
            current_len = 0
        current.append(page)
        current_len += page_len

    if current:
        chunks.append(current)

    return chunks or [pages]


def build_known_metrics_hint() -> str:
    """Vocabulary list given to the model so it uses a canonical registry
    name (e.g. "dpi") when a metric matches one, rather than inventing a
    new name for something already well-known."""
    lines = [
        "KNOWN METRIC NAMES (use one of these exact canonical names when a "
        "metric matches; otherwise invent a short, clear snake_case name):"
    ]
    for metric_def in all_metrics():
        lines.append(f"- {metric_def.name} ({metric_def.unit}): {metric_def.display_label}")
    return "\n".join(lines)


def build_schema_hint(doc_name: str) -> dict:
    return {
        "doc_name": doc_name,
        "doc_date": None,
        "metrics": [
            {
                "name": "net_irr",
                "raw_label": "Net IRR",
                "unit": "percent",
                "value": 16.83,
                "confidence": 0.9,
                "evidence": {"doc_name": doc_name, "page": 1, "snippet": ""}
            },
            {
                "name": "aum",
                "raw_label": "Assets Under Management",
                "unit": "usd",
                "value": 1200000000,
                "confidence": 0.9,
                "evidence": {"doc_name": doc_name, "page": 1, "snippet": ""}
            },
            {
                "name": "dpi",
                "raw_label": "DPI",
                "unit": "multiple",
                "value": 0.45,
                "confidence": 0.8,
                "evidence": {"doc_name": doc_name, "page": 2, "snippet": ""}
            }
        ],
        "notes": [],
        "missing_fields": []
    }


def _clean_metric_entry(raw: dict, notes: List[str]) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None

    value = raw.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None  # no guessed/null-value entries -- see extract_v1.txt

    raw_label = raw.get("raw_label") or str(raw.get("name") or "")
    name, is_custom = normalize_metric_name(raw_label)

    metric_def = None if is_custom else get_metric_def(name)
    # A known registry metric's unit is authoritative (curated), overriding
    # whatever the model said, so the same canonical metric is never split
    # across two units depending on which call produced it.
    unit = metric_def.unit if metric_def else raw.get("unit")
    if unit not in ALLOWED_UNITS:
        unit = "other"

    confidence = raw.get("confidence", 0.0)
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        confidence = 0.0

    evidence = raw.get("evidence")
    if not isinstance(evidence, dict):
        evidence = {"doc_name": "", "page": None, "snippet": ""}

    value = float(value)
    if unit == "percent" and 0 < value < 1:
        corrected = value * 100
        notes.append(
            f"{name}: model returned {value} (looked like a fraction, not a percent) -- "
            f"auto-corrected to {corrected} per this schema's percent-number convention."
        )
        value = corrected

    return {
        "name": name,
        "raw_label": raw_label,
        "unit": unit,
        "value": value,
        "basis": raw.get("basis"),
        "confidence": float(confidence),
        "is_custom": is_custom,
        "evidence": evidence,
    }


def _clean_metrics(data: dict) -> None:
    raw_metrics = data.get("metrics")
    if not isinstance(raw_metrics, list):
        raw_metrics = []

    notes = data.setdefault("notes", [])
    cleaned: List[dict] = []
    for raw in raw_metrics:
        entry = _clean_metric_entry(raw, notes)
        if entry is not None:
            cleaned.append(entry)

    data["metrics"] = cleaned


def _backfill_legacy_fields(data: dict) -> None:
    """Derives the six legacy top-level fields from the open `metrics`
    array (highest-confidence entry per name wins) -- the model is only
    ever asked for `metrics` now (see extract_v1.txt), so rules/reports
    that still read `aum`/`net_irr`/etc. directly (everything, as of Phase
    1 of the open-metric migration) keep working without the model needing
    to produce both shapes."""
    by_name: Dict[str, dict] = {}
    for m in data.get("metrics", []):
        name = m.get("name")
        if not name:
            continue
        if name not in by_name or (m.get("confidence") or 0) > (by_name[name].get("confidence") or 0):
            by_name[name] = m

    def _metric_dict(name: str) -> Optional[dict]:
        m = by_name.get(name)
        if not m:
            return None
        return {
            "value": m.get("value"),
            "confidence": m.get("confidence", 0.0),
            "evidence": m.get("evidence") or {"doc_name": "", "page": None, "snippet": ""},
        }

    for field in ("aum", "net_irr", "tvpi", "target_irr"):
        derived = _metric_dict(field)
        if derived:
            data[field] = derived

    mgmt_fee = _metric_dict("mgmt_fee")
    if mgmt_fee:
        mgmt_fee["basis"] = by_name["mgmt_fee"].get("basis")
        data["mgmt_fee"] = mgmt_fee

    carry = _metric_dict("carry")
    if carry:
        hurdle_entry = by_name.get("hurdle_rate")
        carry["hurdle"] = hurdle_entry.get("value") if hurdle_entry else None
        data["carry"] = carry


def sanitize_extraction(data: dict) -> dict:
    defaults = {
        "notes": [],
        "missing_fields": []
    }

    for k, v in defaults.items():
        if k not in data or data[k] is None:
            data[k] = v

    if isinstance(data.get("doc_date"), dict):
        data["doc_date"] = data["doc_date"].get("value")

    cleaned_notes = []
    for n in data.get("notes", []):
        if isinstance(n, str):
            cleaned_notes.append(n)
        elif isinstance(n, dict):
            cleaned_notes.append(n.get("text", str(n)))
        else:
            cleaned_notes.append(str(n))
    data["notes"] = cleaned_notes

    data["missing_fields"] = [str(x) for x in data.get("missing_fields", [])]

    _clean_metrics(data)
    _backfill_legacy_fields(data)

    metric_fields = ["aum", "net_irr", "tvpi", "target_irr"]

    for field in metric_fields:
        if field not in data or not isinstance(data[field], dict):
            data[field] = {}

        data[field].setdefault("value", None)
        data[field].setdefault("confidence", 0.0)
        data[field].setdefault("evidence", {
            "doc_name": "",
            "page": None,
            "snippet": ""
        })

    if "mgmt_fee" not in data or not isinstance(data["mgmt_fee"], dict):
        data["mgmt_fee"] = {}

    data["mgmt_fee"].setdefault("value", None)
    data["mgmt_fee"].setdefault("basis", None)
    data["mgmt_fee"].setdefault("confidence", 0.0)
    data["mgmt_fee"].setdefault("evidence", {
        "doc_name": "",
        "page": None,
        "snippet": ""
    })

    if "carry" not in data or not isinstance(data["carry"], dict):
        data["carry"] = {}

    data["carry"].setdefault("value", None)
    data["carry"].setdefault("hurdle", None)
    data["carry"].setdefault("confidence", 0.0)
    data["carry"].setdefault("evidence", {
        "doc_name": "",
        "page": None,
        "snippet": ""
    })

    _normalize_percent_like(data, "net_irr", "value")
    _normalize_percent_like(data, "target_irr", "value")
    _normalize_percent_like(data, "mgmt_fee", "value")
    _normalize_percent_like(data, "carry", "value")
    _normalize_percent_like(data, "carry", "hurdle")

    return data


def _normalize_percent_like(data: dict, field: str, subfield: str) -> None:
    """Despite the prompt's explicit "16.83 for 16.83%" convention, smaller/
    weaker LLMs occasionally return the fraction form instead (0.02 for a 2%
    management fee) while reporting full confidence -- observed in practice
    with a local model. Institutional fee/IRR/carry/hurdle rates are
    essentially never below 1 in the percent-number convention this schema
    uses, so a value in (0, 1) is corrected to its x100 equivalent and
    flagged in notes for auditability rather than silently altered.

    Kept as a safety net on top of _clean_metric_entry's equivalent check
    (which runs on the same data before _backfill_legacy_fields derives
    these fields) -- idempotent if the value's already been corrected."""
    obj = data.get(field)
    if not isinstance(obj, dict):
        return

    value = obj.get(subfield)
    if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 < value < 1:
        corrected = value * 100
        obj[subfield] = corrected
        data.setdefault("notes", []).append(
            f"{field}.{subfield}: model returned {value} (looked like a fraction, not a "
            f"percent) -- auto-corrected to {corrected} per this schema's percent-number convention."
        )


def merge_chunk_docs(doc_name: str, chunk_docs: List[ExtractedDoc], source_label: str) -> ExtractedDoc:
    merged = ExtractedDoc(doc_name=doc_name)

    for doc in chunk_docs:
        if doc.doc_date:
            merged.doc_date = doc.doc_date
            break

    for metric_name in METRIC_FIELDS:
        best = None
        for doc in chunk_docs:
            metric = getattr(doc, metric_name)
            if metric.value is None:
                continue
            if best is None or metric.confidence > best.confidence:
                best = metric
        if best is not None:
            setattr(merged, metric_name, best)

    # Open-ended metrics: merge by name across chunks, highest confidence
    # wins per name -- same policy as the legacy fields above, over a
    # dynamic name set discovered from the chunks themselves.
    best_by_name: Dict[str, MetricEntry] = {}
    for doc in chunk_docs:
        for metric in doc.metrics:
            existing = best_by_name.get(metric.name)
            if existing is None or metric.confidence > existing.confidence:
                best_by_name[metric.name] = metric
    merged.metrics = list(best_by_name.values())

    notes: List[str] = []
    for doc in chunk_docs:
        for n in doc.notes:
            if n not in notes:
                notes.append(n)
    notes.append(f"Document processed in {len(chunk_docs)} chunks due to length ({source_label}).")
    merged.notes = notes

    missing: List[str] = []
    for metric_name in METRIC_FIELDS:
        if getattr(merged, metric_name).value is None:
            missing.append(f"{metric_name}.value")
    if merged.carry.hurdle is None:
        missing.append("carry.hurdle")
    merged.missing_fields = missing

    return merged


def _registry_metric_evidence_ok(metric: MetricEntry, pages: List[Page]) -> bool:
    """Custom (non-registry) metrics never trigger a retry -- they're
    inherently ad-hoc, one-off labels a model happened to notice, not the
    well-known figures the rest of the system (rules, cross-doc comparison)
    actually depends on."""
    if metric.is_custom:
        return True
    page_text = get_page_text(pages, metric.evidence.page)
    return classify_evidence_match(metric.evidence.snippet, page_text).label in ("verbatim", "fuzzy")


def _count_unverified_registry_metrics(doc: ExtractedDoc, pages: List[Page]) -> int:
    return sum(1 for m in doc.metrics if not _registry_metric_evidence_ok(m, pages))


def extract_with_evidence_retry(
    pages: List[Page],
    attempt_fn: Callable[[], ExtractedDoc],
    enable_retry: bool = True,
    doc_name: str = "",
) -> ExtractedDoc:
    """Calls `attempt_fn()` (one full extraction attempt -- including its
    own transport-level retries and regex fallback -- returning an
    ExtractedDoc) once. If any registry-recognized metric's evidence
    doesn't hold up against the real source page text, tries once more and
    keeps whichever attempt has fewer such failures (the first attempt
    wins a tie, since a second call isn't guaranteed to be better and
    shouldn't be preferred without evidence that it actually is). Every
    metric on the chosen attempt is stamped `needed_retry=True` whenever a
    second attempt was made at all -- postprocess.verify_metric applies a
    small extra confidence discount for that, since a call that needed two
    tries is a slightly weaker signal even when it ultimately produced a
    clean citation."""
    first = attempt_fn()

    if not enable_retry:
        return first

    first_failures = _count_unverified_registry_metrics(first, pages)
    if first_failures == 0:
        return first

    logger.info(
        f"evidence_retry doc={doc_name} first_pass_failures={first_failures} retrying_once"
    )
    second = attempt_fn()
    second_failures = _count_unverified_registry_metrics(second, pages)

    chosen = second if second_failures < first_failures else first

    logger.info(
        f"evidence_retry doc={doc_name} first_pass_failures={first_failures} "
        f"retry_failures={second_failures} chose={'retry' if chosen is second else 'first_pass'}"
    )

    for m in chosen.metrics:
        m.needed_retry = True
    chosen.notes.append(
        f"Evidence validation triggered a retry for this chunk ({first_failures} registry "
        f"metric(s) initially missing/unmatched citations)."
    )

    return chosen
