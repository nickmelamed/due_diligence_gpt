from ddgpt.io.loaders import Page
from ddgpt.extract.schemas import ExtractedDoc, Metric, MetricEntry
from ddgpt.extract.llm_common import chunk_pages, sanitize_extraction, merge_chunk_docs, extract_with_evidence_retry


def test_chunk_pages_splits_when_over_budget():
    pages = [Page(page_num=i, text="x" * 100) for i in range(1, 6)]
    chunks = chunk_pages(pages, max_chars=250)

    assert len(chunks) > 1
    # every page appears exactly once across all chunks
    all_page_nums = [p.page_num for chunk in chunks for p in chunk]
    assert sorted(all_page_nums) == [1, 2, 3, 4, 5]


def test_chunk_pages_single_chunk_when_under_budget():
    pages = [Page(page_num=1, text="short")]
    chunks = chunk_pages(pages, max_chars=10_000)
    assert len(chunks) == 1


def test_sanitize_extraction_fills_missing_metric_structure():
    data = {"doc_name": "x.pdf"}
    sanitized = sanitize_extraction(data)

    assert sanitized["aum"]["value"] is None
    assert sanitized["mgmt_fee"]["basis"] is None
    assert sanitized["carry"]["hurdle"] is None
    assert sanitized["notes"] == []
    assert sanitized["missing_fields"] == []


def test_sanitize_extraction_normalizes_dict_notes():
    data = {"notes": [{"text": "a note"}, "plain note"]}
    sanitized = sanitize_extraction(data)
    assert sanitized["notes"] == ["a note", "plain note"]


def test_merge_chunk_docs_picks_highest_confidence_per_field():
    doc1 = ExtractedDoc(doc_name="x")
    doc1.aum = Metric(value=1.0e9, confidence=0.4)

    doc2 = ExtractedDoc(doc_name="x")
    doc2.aum = Metric(value=2.0e9, confidence=0.9)

    merged = merge_chunk_docs("x", [doc1, doc2], source_label="test")

    assert merged.aum.value == 2.0e9
    assert "chunks" in merged.notes[-1]


def test_merge_chunk_docs_reports_missing_fields_when_all_chunks_null():
    doc1 = ExtractedDoc(doc_name="x")
    doc2 = ExtractedDoc(doc_name="x")

    merged = merge_chunk_docs("x", [doc1, doc2], source_label="test")

    assert "aum.value" in merged.missing_fields
    assert "carry.hurdle" in merged.missing_fields


def test_sanitize_extraction_corrects_fraction_returned_for_mgmt_fee():
    # A 2% management fee returned as a fraction (0.02) instead of this
    # schema's percent-number convention (2.0) -- observed in practice from
    # a local model despite the prompt's explicit instruction.
    data = {"mgmt_fee": {"value": 0.02, "confidence": 1.0}}
    sanitized = sanitize_extraction(data)

    assert sanitized["mgmt_fee"]["value"] == 2.0
    assert any("auto-corrected" in n for n in sanitized["notes"])


def test_sanitize_extraction_leaves_normal_percent_values_untouched():
    data = {"mgmt_fee": {"value": 2.0, "confidence": 1.0}, "net_irr": {"value": 16.83}}
    sanitized = sanitize_extraction(data)

    assert sanitized["mgmt_fee"]["value"] == 2.0
    assert sanitized["net_irr"]["value"] == 16.83
    assert sanitized["notes"] == []


def test_sanitize_extraction_leaves_null_and_zero_values_untouched():
    data = {"mgmt_fee": {"value": None}, "carry": {"value": 0, "hurdle": None}}
    sanitized = sanitize_extraction(data)

    assert sanitized["mgmt_fee"]["value"] is None
    assert sanitized["carry"]["value"] == 0
    assert sanitized["notes"] == []


# Open-ended `metrics` array (schema_hint no longer asks for the six legacy
# top-level keys directly -- see prompts/extract_v1.txt / build_schema_hint)

def test_sanitize_extraction_backfills_legacy_field_from_open_metrics():
    data = {
        "metrics": [
            {"name": "net_irr", "raw_label": "Net IRR", "unit": "percent", "value": 16.83, "confidence": 0.9},
        ]
    }
    sanitized = sanitize_extraction(data)

    assert sanitized["net_irr"]["value"] == 16.83
    assert sanitized["net_irr"]["confidence"] == 0.9
    assert len(sanitized["metrics"]) == 1
    assert sanitized["metrics"][0]["name"] == "net_irr"


def test_sanitize_extraction_backfills_mgmt_fee_basis_and_carry_hurdle():
    data = {
        "metrics": [
            {"name": "mgmt_fee", "raw_label": "Management Fee", "unit": "percent", "value": 2.0,
             "confidence": 0.9, "basis": "committed capital"},
            {"name": "carry", "raw_label": "Carried Interest", "unit": "percent", "value": 20.0, "confidence": 0.9},
            {"name": "hurdle_rate", "raw_label": "Hurdle Rate", "unit": "percent", "value": 8.0, "confidence": 0.9},
        ]
    }
    sanitized = sanitize_extraction(data)

    assert sanitized["mgmt_fee"]["value"] == 2.0
    assert sanitized["mgmt_fee"]["basis"] == "committed capital"
    assert sanitized["carry"]["value"] == 20.0
    assert sanitized["carry"]["hurdle"] == 8.0


def test_sanitize_extraction_corrects_fraction_within_open_metric_entry():
    data = {
        "metrics": [
            {"name": "mgmt_fee", "raw_label": "Management Fee", "unit": "percent", "value": 0.02, "confidence": 1.0},
        ]
    }
    sanitized = sanitize_extraction(data)

    assert sanitized["metrics"][0]["value"] == 2.0
    assert sanitized["mgmt_fee"]["value"] == 2.0
    assert any("auto-corrected" in n for n in sanitized["notes"])


def test_sanitize_extraction_normalizes_name_by_raw_label_not_model_provided_name():
    # The model might not use the exact canonical string even when it
    # recognizes the metric -- normalization is keyed off raw_label so the
    # canonical name is still correct regardless of what "name" it guessed.
    data = {
        "metrics": [
            {"name": "distributions_to_paid_in_capital", "raw_label": "Distributions to Paid-In",
             "unit": "multiple", "value": 0.45, "confidence": 0.8},
        ]
    }
    sanitized = sanitize_extraction(data)

    assert sanitized["metrics"][0]["name"] == "dpi"
    assert sanitized["metrics"][0]["is_custom"] is False


def test_sanitize_extraction_keeps_unknown_metric_as_custom():
    data = {
        "metrics": [
            {"name": "x", "raw_label": "Portfolio Company Count", "unit": "count", "value": 4, "confidence": 0.7},
        ]
    }
    sanitized = sanitize_extraction(data)

    entry = sanitized["metrics"][0]
    assert entry["name"] == "portfolio_company_count"
    assert entry["is_custom"] is True
    assert entry["unit"] == "count"


def test_sanitize_extraction_drops_malformed_metric_entries():
    data = {
        "metrics": [
            {"name": "net_irr", "raw_label": "Net IRR", "unit": "percent", "value": None},  # no value -> dropped
            # non-numeric value, dropped
            {"name": "tvpi", "raw_label": "TVPI", "unit": "multiple", "value": "not a number"},
            "not even a dict",  # dropped
            {"name": "aum", "raw_label": "AUM", "unit": "usd", "value": 1.2e9, "confidence": 0.9},  # kept
        ]
    }
    sanitized = sanitize_extraction(data)

    assert len(sanitized["metrics"]) == 1
    assert sanitized["metrics"][0]["name"] == "aum"


def test_sanitize_extraction_known_metric_unit_overrides_model_provided_unit():
    # net_irr is registry-known as "percent" -- trust the registry over
    # whatever unit the model reported, so the same canonical metric is
    # never split across two units.
    data = {
        "metrics": [
            {"name": "net_irr", "raw_label": "Net IRR", "unit": "usd", "value": 16.83, "confidence": 0.9},
        ]
    }
    sanitized = sanitize_extraction(data)

    assert sanitized["metrics"][0]["unit"] == "percent"


def test_merge_chunk_docs_merges_open_metrics_by_name_highest_confidence_wins():
    doc1 = ExtractedDoc(doc_name="x")
    doc1.metrics = [MetricEntry(name="dpi", raw_label="DPI", unit="multiple", value=0.40, confidence=0.5)]

    doc2 = ExtractedDoc(doc_name="x")
    doc2.metrics = [
        MetricEntry(name="dpi", raw_label="DPI", unit="multiple", value=0.45, confidence=0.9),
        MetricEntry(name="rvpi", raw_label="RVPI", unit="multiple", value=1.10, confidence=0.8),
    ]

    merged = merge_chunk_docs("x", [doc1, doc2], source_label="test")

    by_name = {m.name: m for m in merged.metrics}
    assert by_name["dpi"].value == 0.45  # higher-confidence chunk wins
    assert by_name["rvpi"].value == 1.10


# extract_with_evidence_retry -- extraction-time evidence validation/retry

def _doc_with_aum_evidence(snippet, page=1, is_custom=False):
    doc = ExtractedDoc(doc_name="x.pdf")
    doc.metrics = [MetricEntry(
        name="aum", raw_label="AUM", unit="usd", value=1.2e9, confidence=0.9, is_custom=is_custom,
        evidence={"doc_name": "x.pdf", "page": page, "snippet": snippet},
    )]
    return doc


def test_no_retry_when_first_attempt_evidence_is_clean():
    pages = [Page(page_num=1, text="Assets Under Management (AUM): $1.20B")]
    calls = []

    def attempt():
        calls.append(1)
        return _doc_with_aum_evidence("Assets Under Management (AUM): $1.20B")

    result = extract_with_evidence_retry(pages, attempt, enable_retry=True, doc_name="x.pdf")

    assert len(calls) == 1  # never retried
    assert result.metrics[0].needed_retry is False


def test_retries_once_when_registry_metric_evidence_missing():
    pages = [Page(page_num=1, text="Assets Under Management (AUM): $1.20B")]
    calls = []

    def attempt():
        calls.append(1)
        if len(calls) == 1:
            return _doc_with_aum_evidence("")  # first attempt: no citation at all
        return _doc_with_aum_evidence("Assets Under Management (AUM): $1.20B")  # retry: clean

    result = extract_with_evidence_retry(pages, attempt, enable_retry=True, doc_name="x.pdf")

    assert len(calls) == 2  # retried exactly once
    assert result.metrics[0].evidence.snippet != ""
    assert result.metrics[0].needed_retry is True
    assert any("retry" in n.lower() for n in result.notes)


def test_keeps_first_attempt_when_retry_is_not_better():
    pages = [Page(page_num=1, text="Assets Under Management (AUM): $1.20B")]
    calls = []

    def attempt():
        calls.append(1)
        return _doc_with_aum_evidence("")  # every attempt is uncited

    result = extract_with_evidence_retry(pages, attempt, enable_retry=True, doc_name="x.pdf")

    assert len(calls) == 2  # still retried once (first attempt had a failure)
    assert result.metrics[0].needed_retry is True  # a retry was attempted regardless of outcome


def test_custom_metrics_never_trigger_a_retry():
    pages = [Page(page_num=1, text="Some page text.")]
    calls = []

    def attempt():
        calls.append(1)
        return _doc_with_aum_evidence("", is_custom=True)  # uncited, but not registry-recognized

    result = extract_with_evidence_retry(pages, attempt, enable_retry=True, doc_name="x.pdf")

    assert len(calls) == 1  # never retried
    assert result.metrics[0].needed_retry is False


def test_enable_retry_false_skips_validation_entirely():
    pages = [Page(page_num=1, text="Assets Under Management (AUM): $1.20B")]
    calls = []

    def attempt():
        calls.append(1)
        return _doc_with_aum_evidence("")  # uncited

    result = extract_with_evidence_retry(pages, attempt, enable_retry=False, doc_name="x.pdf")

    assert len(calls) == 1  # config-gated off -- never retries
    assert result.metrics[0].needed_retry is False
