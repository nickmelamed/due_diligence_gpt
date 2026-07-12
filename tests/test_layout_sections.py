from ddgpt.layout.section_parser import parse_sections_from_text
from ddgpt.layout.footnote_linker import attach_footnotes_to_tables
from ddgpt.layout.definitions import infer_irr_basis
from ddgpt.layout.models import DocumentLayout
from ddgpt.extract.tables.table_models import ExtractedTable


def test_canonical_sections_detected_in_plain_text():
    text = (
        "Fund Overview\n"
        "Some intro text.\n"
        "\n"
        "Performance Summary\n"
        "Net IRR (since inception): 16.9%\n"
        "\n"
        "Terms\n"
        "Management Fee: 2.0%\n"
        "\n"
        "Risk Factors\n"
        "Illiquidity and concentration risk.\n"
    )
    sections, _ = parse_sections_from_text(text, page_num=1)
    canonical_types = [s.canonical_type for s in sections if s.canonical_type]

    assert "performance_summary" in canonical_types
    assert "terms" in canonical_types
    assert "risk_factors" in canonical_types


def test_footnote_detected_and_attached_to_same_page_table():
    text = (
        "Terms\n"
        "Management Fee: 2.0%*\n"
        "\n"
        "1 Reduced to 1.5% for commitments over $50M.\n"
    )
    _, footnotes = parse_sections_from_text(text, page_num=1)
    assert len(footnotes) == 1

    table = ExtractedTable(table_id="t1", page=1, headers=["Fee"], rows=[{"Fee": "2.0%"}], raw_text="Fee: 2.0%")
    linked = attach_footnotes_to_tables([table], footnotes)

    assert linked[0].footnotes == [footnotes[0].text]


def test_footnote_not_attached_to_table_on_different_page():
    text = "1 Some footnote text on page 2.\n"
    _, footnotes = parse_sections_from_text(text, page_num=2)

    table = ExtractedTable(table_id="t1", page=1, headers=["Fee"], rows=[{"Fee": "2.0%"}], raw_text="Fee: 2.0%")
    linked = attach_footnotes_to_tables([table], footnotes)

    assert linked[0].footnotes == []


def test_infer_irr_basis_prioritizes_definitions_section_over_number_page():
    from ddgpt.io.loaders import Page
    from ddgpt.layout.models import Section

    pages = [Page(page_num=1, text="Net IRR: 14.0%")]
    layout = DocumentLayout(sections=[
        Section(title="Performance Summary", canonical_type="performance_summary",
                page_start=1, page_end=1, text="Net IRR: 14.0%"),
        Section(title="Definitions", canonical_type="definitions",
                page_start=2, page_end=2, text="IRR figures herein are presented gross of fees."),
    ])

    context = infer_irr_basis(pages, layout)
    assert context["basis"] == "gross"
    assert context["section"] == "Definitions"


def test_infer_irr_basis_falls_back_to_whole_document_scan_without_sections():
    from ddgpt.io.loaders import Page

    pages = [Page(page_num=1, text="Net IRR (since inception): 16.9%")]
    context = infer_irr_basis(pages, layout=None)

    assert context["basis"] == "net"
    assert context["page"] == 1
