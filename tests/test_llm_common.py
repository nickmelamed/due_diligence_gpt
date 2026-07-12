from ddgpt.io.loaders import Page
from ddgpt.extract.schemas import ExtractedDoc, Metric
from ddgpt.extract.llm_common import chunk_pages, sanitize_extraction, merge_chunk_docs


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
