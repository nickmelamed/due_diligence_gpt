from ddgpt.rules.definition_drift import DefinitionDriftRule


def _doc(name, snippet, basis, section):
    return {
        "doc_name": name,
        "net_irr": {"value": 15.0, "evidence": {"page": 3, "snippet": snippet}},
        "net_irr_basis": {"basis": basis, "snippet": basis, "page": 3, "section": section},
    }


def test_cross_document_drift_flagged_when_conventions_differ():
    doc_a = _doc("deck.pdf", "Gross IRR: 15.0%", "gross", "Performance Summary")
    doc_b = _doc("lpa.pdf", "Net IRR: 13.0%", "net", "Definitions")

    flags = DefinitionDriftRule().apply([doc_a, doc_b])

    assert len(flags) == 1
    assert flags[0].type == "IRR_DEFINITION_DRIFT"


def test_no_cross_document_flag_when_conventions_match():
    doc_a = _doc("deck.pdf", "Net IRR: 15.0%", "net", "Performance Summary")
    doc_b = _doc("lpa.pdf", "Net IRR: 13.0%", "net", "Definitions")

    flags = DefinitionDriftRule().apply([doc_a, doc_b])

    assert flags == []


def test_within_document_drift_when_number_caption_contradicts_stated_convention():
    doc = _doc("ambiguous.pdf", "Net IRR: 14.0%", "gross", "Definitions")

    flags = DefinitionDriftRule().apply([doc])

    assert len(flags) == 1
    assert flags[0].type == "IRR_DEFINITION_DRIFT_INTERNAL"


def test_no_within_document_flag_when_caption_matches_stated_convention():
    doc = _doc("consistent.pdf", "Net IRR: 14.0%", "net", "Definitions")

    flags = DefinitionDriftRule().apply([doc])

    assert flags == []
