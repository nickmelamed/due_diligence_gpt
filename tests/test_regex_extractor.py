from ddgpt.extract.regex_extractor import RegexExtractor
from ddgpt.io.loaders import Page


def test_mgmt_fee_extracted_when_label_and_value_on_separate_lines():
    # Regression test: fitz extracts each PDF table cell as its own line
    # (e.g. "Management Fee\n2.00% on committed capital"), which the old
    # ".*?" pattern (no DOTALL) could not bridge, silently dropping the fee
    # to missing_fields even though it was present in the document.
    text = "FUND TERMS\nTerm\nValue\nManagement Fee\n2.00% on committed capital\nGP Commitment\n$35M"
    pages = [Page(page_num=1, text=text)]

    doc = RegexExtractor().extract("doc.pdf", pages)

    assert doc.mgmt_fee.value == 2.00
    assert "mgmt_fee.value" not in doc.missing_fields


def test_mgmt_fee_still_extracted_on_single_line():
    text = "Management Fee: 2.00% on committed capital"
    pages = [Page(page_num=1, text=text)]

    doc = RegexExtractor().extract("doc.pdf", pages)

    assert doc.mgmt_fee.value == 2.00


def test_mgmt_fee_label_does_not_pair_with_far_away_unrelated_percent():
    # The label/value gap is bounded so "Management Fee" doesn't accidentally
    # pair with an unrelated percentage much further down the page.
    filler = "x" * 200
    text = f"Management Fee is described below.\n{filler}\nSome other rate: 9.99%"
    pages = [Page(page_num=1, text=text)]

    doc = RegexExtractor().extract("doc.pdf", pages)

    assert doc.mgmt_fee.value is None
    assert "mgmt_fee.value" in doc.missing_fields


def test_net_irr_extracted_without_colon_on_separate_line():
    text = "Net IRR\n16.80%"
    pages = [Page(page_num=1, text=text)]

    doc = RegexExtractor().extract("doc.pdf", pages)

    assert doc.net_irr.value == 16.80


def test_dual_writes_into_open_metrics_list():
    # Every legacy field this extractor finds should also land in the new
    # open-ended `metrics` list, so it participates in the dynamic-metric
    # migration without waiting on the legacy attribute to be read.
    text = (
        "Management Fee: 2.00% on committed capital\n"
        "Net IRR: 16.80%\n"
        "TVPI: 1.62x\n"
        "Carried Interest: 20% over an 8% preferred return"
    )
    pages = [Page(page_num=1, text=text)]

    doc = RegexExtractor().extract("doc.pdf", pages)

    by_name = {m.name: m for m in doc.metrics}
    assert by_name["mgmt_fee"].value == 2.00
    assert by_name["mgmt_fee"].unit == "percent"
    assert by_name["mgmt_fee"].is_custom is False
    assert by_name["net_irr"].value == 16.80
    assert by_name["tvpi"].value == 1.62
    assert by_name["tvpi"].unit == "multiple"
    assert by_name["carry"].value == 20.0
    assert by_name["hurdle_rate"].value == 8.0
    assert by_name["hurdle_rate"].unit == "percent"


def test_metrics_list_empty_when_nothing_found():
    doc = RegexExtractor().extract("doc.pdf", [Page(page_num=1, text="no financial data here")])
    assert doc.metrics == []
