import pytest
from pydantic import ValidationError

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


def test_empty_header_cell_raises_known_bug(monkeypatch):
    # Known bug, to be fixed after the standards work (see PROGRESS.md).
    # pdfplumber reports an empty header cell as None, but
    # ExtractedTable.headers is List[str], so the whole extractor raises.
    # When this is fixed, the table should be returned, so flip this test.
    _patch_pdf(monkeypatch, [[[["Fund", None], ["Atlas", "18%"]]]])

    with pytest.raises(ValidationError):
        PDFPlumberTableExtractor().extract("fake.pdf")


def test_ensemble_swallows_the_failure_and_drops_every_pdfplumber_table(monkeypatch, capsys):
    # Known bug, same cause as above. One bad table on page 2 also loses the
    # good table on page 1, and the only signal is a printed message.
    good = [["Fund", "IRR"], ["Atlas", "18%"]]
    bad = [["Fund", None], ["Atlas", "18%"]]
    _patch_pdf(monkeypatch, [[good], [bad]])

    ensemble = EnsembleTableExtractor()
    ensemble.extractors = [PDFPlumberTableExtractor()]

    assert ensemble.extract("fake.pdf") == []
    assert "table extractor failed" in capsys.readouterr().out
