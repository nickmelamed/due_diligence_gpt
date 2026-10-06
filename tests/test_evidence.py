from ddgpt.extract.evidence import (
    classify_evidence_match,
    fuzzy_match_ratio,
    normalize,
    get_page_text,
    EVIDENCE_SCORE_BY_MATCH,
)


class _Page:
    def __init__(self, page_num, text):
        self.page_num = page_num
        self.text = text


def test_classify_missing_when_snippet_empty():
    match = classify_evidence_match("", "Some page text.")
    assert match.label == "missing"
    assert EVIDENCE_SCORE_BY_MATCH[match.label] < 1.0


def test_classify_verbatim_for_exact_substring():
    match = classify_evidence_match("Net IRR: 16.8%", "Fund overview. Net IRR: 16.8% as of Q4.")
    assert match.label == "verbatim"
    assert match.ratio == 1.0


def test_classify_fuzzy_for_close_but_not_exact_match():
    # Hyphenation/OCR-noise-like near match, not a clean substring.
    snippet = normalize("Management Fee 2.00% on committed capital")
    page = normalize("Management Fee: 2.00% on committed capi-tal, payable quarterly.")
    match = classify_evidence_match(snippet, page)
    assert match.label in ("verbatim", "fuzzy")


def test_classify_not_found_for_unrelated_text():
    match = classify_evidence_match("Carried Interest 20%", "This page discusses something else entirely.")
    assert match.label == "not_found"


def test_get_page_text_returns_empty_for_missing_page_num():
    assert get_page_text([_Page(1, "hello")], None) == ""
    assert get_page_text([_Page(1, "hello")], 5) == ""


def test_get_page_text_finds_matching_page():
    pages = [_Page(1, "first"), _Page(2, "second")]
    assert get_page_text(pages, 2) == "second"


def test_fuzzy_match_ratio_exact_substring_is_one():
    assert fuzzy_match_ratio("abc", "xxabcxx") == 1.0


def test_fuzzy_match_ratio_empty_snippet_is_zero():
    assert fuzzy_match_ratio("", "some text") == 0.0
