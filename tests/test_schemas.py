from pydantic import BaseModel
from ddgpt.extract.schemas import ExtractedDoc, MetricEntry, sync_legacy_fields, SCHEMA_FINGERPRINT, _model_fingerprint
from ddgpt.provenance.evidence import Evidence


def test_sync_legacy_fields_populates_four_simple_metrics():
    doc = ExtractedDoc(doc_name="x")
    evidence = Evidence(doc_name="x", page=1, snippet="Net IRR: 16.8%")
    doc.metrics = [
        MetricEntry(name="net_irr", raw_label="Net IRR", unit="percent", value=16.8, confidence=0.9,
                    agreement=0.95, evidence=evidence),
        MetricEntry(name="aum", raw_label="AUM", unit="usd", value=1.2e9, confidence=0.8),
        MetricEntry(name="tvpi", raw_label="TVPI", unit="multiple", value=1.6, confidence=0.7),
        MetricEntry(name="target_irr", raw_label="Target IRR", unit="percent", value=18.0, confidence=0.85),
    ]

    sync_legacy_fields(doc)

    assert doc.net_irr.value == 16.8
    assert doc.net_irr.confidence == 0.9
    assert doc.net_irr.agreement == 0.95
    assert doc.net_irr.evidence.snippet == "Net IRR: 16.8%"
    assert doc.aum.value == 1.2e9
    assert doc.tvpi.value == 1.6
    assert doc.target_irr.value == 18.0


def test_sync_legacy_fields_populates_mgmt_fee_basis():
    doc = ExtractedDoc(doc_name="x")
    doc.metrics = [
        MetricEntry(name="mgmt_fee", raw_label="Management Fee", unit="percent", value=2.0,
                    confidence=0.9, basis="committed capital"),
    ]

    sync_legacy_fields(doc)

    assert doc.mgmt_fee.value == 2.0
    assert doc.mgmt_fee.basis == "committed capital"


def test_sync_legacy_fields_populates_carry_and_hurdle_from_separate_entries():
    # hurdle_rate is its own MetricEntry, not a compound attribute of carry
    # -- sync_legacy_fields is responsible for stitching it back onto
    # carry.hurdle for the legacy shim.
    doc = ExtractedDoc(doc_name="x")
    doc.metrics = [
        MetricEntry(name="carry", raw_label="Carried Interest", unit="percent", value=20.0, confidence=0.9),
        MetricEntry(name="hurdle_rate", raw_label="Hurdle Rate", unit="percent", value=8.0, confidence=0.85),
    ]

    sync_legacy_fields(doc)

    assert doc.carry.value == 20.0
    assert doc.carry.hurdle == 8.0


def test_sync_legacy_fields_leaves_field_untouched_when_no_matching_entry():
    doc = ExtractedDoc(doc_name="x")
    doc.metrics = [MetricEntry(name="dpi", raw_label="DPI", unit="multiple", value=0.45, confidence=0.8)]

    sync_legacy_fields(doc)

    assert doc.aum.value is None
    assert doc.net_irr.value is None


def test_sync_legacy_fields_ignores_custom_metrics():
    doc = ExtractedDoc(doc_name="x")
    doc.metrics = [
        MetricEntry(name="portfolio_company_count", raw_label="Portfolio Company Count",
                    unit="count", value=4, confidence=0.5, is_custom=True),
    ]

    sync_legacy_fields(doc)

    assert doc.aum.value is None
    assert doc.net_irr.value is None


# SCHEMA_FINGERPRINT -- disk-cache invalidation on schema change (see
# fusion_extractor._extract_with_cache). A stale pickle from before a field
# existed raises AttributeError the first time something reads that field
# (pickle restores __dict__ directly, bypassing validators/defaults) --
# confirmed by a real crash during this project's own development.

def test_schema_fingerprint_is_stable_and_nonempty():
    assert len(SCHEMA_FINGERPRINT) > 0
    # Recomputing from the same model list twice yields the same value.
    assert _model_fingerprint([ExtractedDoc, MetricEntry]) == _model_fingerprint([ExtractedDoc, MetricEntry])


def test_model_fingerprint_differs_for_different_model_names():
    class A(BaseModel):
        x: int = 0
        y: str = ""

    class B(BaseModel):
        x: int = 0
        y: str = ""

    assert _model_fingerprint([A]) != _model_fingerprint([B])  # different model name


def test_model_fingerprint_changes_when_a_field_is_added():
    class Before(BaseModel):
        x: int = 0

    class After(BaseModel):
        x: int = 0
        y: int = 0  # a field added -- the exact class of change that broke a stale pickle

    assert _model_fingerprint([Before]) != _model_fingerprint([After])


def test_model_fingerprint_insensitive_to_field_declaration_order():
    ModelA = type("SameName", (BaseModel,), {"__annotations__": {"a": int, "b": int}, "a": 0, "b": 0})
    ModelB = type("SameName", (BaseModel,), {"__annotations__": {"b": int, "a": int}, "b": 0, "a": 0})

    assert _model_fingerprint([ModelA]) == _model_fingerprint([ModelB])
