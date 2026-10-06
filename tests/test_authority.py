import copy

from ddgpt.config import ToleranceConfig, TrustConfig
from ddgpt.extract.postprocess import authority_weight
from ddgpt.rules.numeric_mismatch import NumericMismatchRule


def _doc(name, aum):
    return {
        "doc_name": name,
        "metrics": [{
            "name": "aum", "unit": "usd", "value": aum, "confidence": 0.9,
            "evidence": {"page": 1, "snippet": "AUM"},
        }],
    }


def test_authority_order_follows_the_configured_weights():
    trust = TrustConfig()
    weights = [
        authority_weight(name, trust.authority_weights, trust.authority_default_weight)
        for name in ("fund_lpa.pdf", "audited_statements.pdf", "quarterly_update.pdf", "marketing_deck.pdf")
    ]
    assert weights == sorted(weights, reverse=True)
    assert len(set(weights)) == 4


def test_a_conflict_between_a_deck_and_an_lpa_becomes_a_flag():
    lpa, deck = _doc("fund_lpa.pdf", 1.0e9), _doc("marketing_deck.pdf", 1.5e9)

    flags = NumericMismatchRule(ToleranceConfig()).apply([lpa, deck])

    assert len(flags) == 1
    assert flags[0].metric == "aum"
    assert "fund_lpa.pdf" in flags[0].docs and "marketing_deck.pdf" in flags[0].docs


def test_the_rule_never_overwrites_either_documents_value():
    lpa, deck = _doc("fund_lpa.pdf", 1.0e9), _doc("marketing_deck.pdf", 1.5e9)
    before = copy.deepcopy([lpa, deck])

    NumericMismatchRule(ToleranceConfig()).apply([lpa, deck])

    assert [lpa, deck] == before
