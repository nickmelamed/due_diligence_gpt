from ddgpt.extract.tables import pdfplumber_extractor
from ddgpt.extract.tables.ensemble_tables import EnsembleTableExtractor
from ddgpt.extract.tables.pdfplumber_extractor import PDFPlumberTableExtractor


class _FakePage:
    def __init__(self, tables):
        self._tables = tables

    def extract_tables(self):
        return self._tables


class _FakePdf:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _patch_pdf(monkeypatch, tables_per_page):
    pdf = _FakePdf([_FakePage(t) for t in tables_per_page])
    monkeypatch.setattr(pdfplumber_extractor.pdfplumber, "open", lambda path: pdf)


def test_extracts_a_table_with_complete_headers(monkeypatch):
    _patch_pdf(monkeypatch, [[[["Fund", "IRR"], ["Atlas", "18%"]]]])

    tables = PDFPlumberTableExtractor().extract("fake.pdf")

    assert len(tables) == 1
    assert tables[0].headers == ["Fund", "IRR"]
    assert tables[0].rows == [{"Fund": "Atlas", "IRR": "18%"}]
    assert tables[0].page == 1
    assert tables[0].confidence == 0.75


def test_empty_header_cell_gets_a_numbered_placeholder(monkeypatch):
    _patch_pdf(monkeypatch, [[[["Fund", None, ""], ["Atlas", "x", "y"]]]])

    tables = PDFPlumberTableExtractor().extract("fake.pdf")

    assert tables[0].headers == ["Fund", "column_2", "column_3"]
    assert tables[0].rows == [{"Fund": "Atlas", "column_2": "x", "column_3": "y"}]


def test_short_rows_and_empty_cells_become_empty_strings(monkeypatch):
    _patch_pdf(monkeypatch, [[[["Fund", "IRR", "TVPI"], ["Atlas", None], ["Beta"]]]])

    tables = PDFPlumberTableExtractor().extract("fake.pdf")

    assert tables[0].rows == [
        {"Fund": "Atlas", "IRR": "", "TVPI": ""},
        {"Fund": "Beta", "IRR": "", "TVPI": ""},
    ]


def test_one_table_with_an_empty_header_no_longer_drops_the_others(monkeypatch):
    good = [["Fund", "IRR"], ["Atlas", "18%"]]
    gap = [["Fund", None], ["Atlas", "18%"]]
    _patch_pdf(monkeypatch, [[good], [gap]])

    ensemble = EnsembleTableExtractor()
    ensemble.extractors = [PDFPlumberTableExtractor()]

    assert [t.page for t in ensemble.extract("fake.pdf")] == [1, 2]
