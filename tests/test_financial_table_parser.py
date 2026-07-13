from ddgpt.extract.tables.financial_table_parser import FinancialTableParser
from ddgpt.extract.tables.table_models import ExtractedTable


def _table(table_id, page, rows):
    return ExtractedTable(table_id=table_id, page=page, rows=rows, raw_text="")


def test_unrelated_percent_in_other_row_is_not_read_as_irr():
    # Regression test: a "Fund Terms" table with a Management Fee row (2.00%)
    # but no IRR row at all was previously misread as an IRR of 2.0, because
    # the old parser searched the whole table's raw text for *any* decimal
    # percentage rather than requiring the row itself to mention IRR.
    table = _table("t1", 1, rows=[
        {"Term": "Management Fee", "Value": "2.00% on committed capital"},
        {"Term": "Carried Interest", "Value": "20% over an 8% preferred return"},
        {"Term": "Fund Term", "Value": "10 years + 2 one-year extensions"},
    ])

    metrics = FinancialTableParser().parse_metrics([table])

    assert "irr" not in metrics


def test_irr_is_read_when_row_actually_labeled_irr():
    table = _table("t1", 1, rows=[
        {"Metric": "Net IRR", "Current": "16.80%"},
        {"Metric": "TVPI", "Current": "1.62x"},
    ])

    metrics = FinancialTableParser().parse_metrics([table])

    assert metrics["irr"]["value"] == 16.80
    assert metrics["tvpi"]["value"] == 1.62


def test_moic_row_is_not_confused_with_tvpi():
    # A "Gross MOIC: 2.10x" row satisfies the same "N.Nx" value pattern as
    # TVPI but is a different metric -- must not be picked up as TVPI just
    # because it appears in the same table.
    table = _table("t1", 1, rows=[
        {"Metric": "Gross MOIC", "Current": "2.10x"},
        {"Metric": "TVPI", "Current": "1.62x"},
    ])

    metrics = FinancialTableParser().parse_metrics([table])

    assert metrics["tvpi"]["value"] == 1.62


def test_aum_requires_aum_label_in_row():
    table = _table("t1", 1, rows=[
        {"Term": "GP Commitment", "Value": "$35M"},
        {"Metric": "AUM", "Current": "$1.25B"},
    ])

    metrics = FinancialTableParser().parse_metrics([table])

    assert metrics["aum"]["value"] == 1.25e9
