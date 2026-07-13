from ddgpt.io.loaders import Page
from ddgpt.layout.irr_mentions import find_irr_mentions


def test_finds_labeled_net_irr_with_basis():
    pages = [Page(page_num=1, text="Net IRR: 16.8%")]
    mentions = find_irr_mentions(pages)
    assert len(mentions) == 1
    assert mentions[0]["value"] == 16.8
    assert mentions[0]["basis"] == "net"


def test_finds_target_irr_with_no_basis():
    pages = [Page(page_num=1, text="Target IRR: 18%")]
    mentions = find_irr_mentions(pages)
    assert len(mentions) == 1
    assert mentions[0]["value"] == 18.0
    assert mentions[0]["basis"] is None


def test_finds_value_first_phrasing_with_basis():
    pages = [Page(page_num=1, text="the fund is targeting a 20% gross IRR going forward")]
    mentions = find_irr_mentions(pages)
    assert len(mentions) == 1
    assert mentions[0]["value"] == 20.0
    assert mentions[0]["basis"] == "gross"


def test_does_not_associate_irr_with_a_distant_unrelated_percentage():
    text = "Net IRR\nand has implemented a revised management fee structure of 2.25% for new commitments"
    pages = [Page(page_num=1, text=text)]
    mentions = find_irr_mentions(pages)
    assert mentions == []


def test_realistic_document_finds_all_three_distinct_claims():
    text = (
        "Net IRR: 16.8%\n"
        "Target IRR: 18%\n"
        "The Q4 2025 investor update notes that the fund is targeting a 20% gross IRR "
        "and has implemented a revised 2.25% management fee structure for new LP "
        "commitments beginning in 2026.\n"
    )
    pages = [Page(page_num=2, text=text)]
    mentions = find_irr_mentions(pages)

    values = sorted(m["value"] for m in mentions)
    assert values == [16.8, 18.0, 20.0]

    gross_mentions = [m for m in mentions if m["basis"] == "gross"]
    assert len(gross_mentions) == 1
    assert gross_mentions[0]["value"] == 20.0
    assert gross_mentions[0]["page"] == 2


def test_no_false_positive_on_moic_or_fee_percentages():
    pages = [Page(page_num=1, text="Gross MOIC: 2.10x. Management Fee: 2.00%.")]
    mentions = find_irr_mentions(pages)
    assert mentions == []
