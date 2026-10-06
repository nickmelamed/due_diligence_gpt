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


# parse_metrics_open -- the open-ended counterpart

def test_open_captures_known_registry_metric_with_correct_unit():
    table = _table("t1", 1, rows=[{"Metric": "Net IRR", "Current": "16.80%"}])

    entries = FinancialTableParser().parse_metrics_open([table])

    assert len(entries) == 1
    assert entries[0]["name"] == "net_irr"
    assert entries[0]["value"] == 16.80
    assert entries[0]["unit"] == "percent"
    assert entries[0]["is_custom"] is False
    assert entries[0]["confidence"] == 0.85


def test_open_captures_moic_and_tvpi_as_distinct_metrics():
    # A capability parse_metrics() never had: MOIC and TVPI both satisfy the
    # same "N.Nx" value pattern but are different metrics -- the open path
    # should capture both, not just one at the other's expense.
    table = _table("t1", 1, rows=[
        {"Metric": "Gross MOIC", "Current": "2.10x"},
        {"Metric": "TVPI", "Current": "1.62x"},
    ])

    entries = FinancialTableParser().parse_metrics_open([table])
    by_name = {e["name"]: e for e in entries}

    assert by_name["moic"]["value"] == 2.10
    assert by_name["tvpi"]["value"] == 1.62


def test_open_captures_unrecognized_row_as_lower_confidence_custom_entry():
    table = _table("t1", 1, rows=[{"Term": "Portfolio Company Count", "Value": "4 companies"}])

    entries = FinancialTableParser().parse_metrics_open([table])

    # "4 companies" has no $/%/x-shaped value, so nothing should be captured
    # here -- see the next test for a custom row that does have one.
    assert entries == []


def test_open_captures_custom_row_with_percent_value():
    table = _table("t1", 1, rows=[{"Term": "Revenue Growth (YoY)", "Value": "84%"}])

    entries = FinancialTableParser().parse_metrics_open([table])

    assert len(entries) == 1
    assert entries[0]["name"] == "revenue_growth_yoy"
    assert entries[0]["value"] == 84.0
    assert entries[0]["unit"] == "percent"
    assert entries[0]["is_custom"] is True
    assert entries[0]["confidence"] == 0.50


def test_open_handles_whole_number_percent_without_decimal():
    table = _table("t1", 1, rows=[{"Term": "Carried Interest", "Value": "20% over an 8% preferred return"}])

    entries = FinancialTableParser().parse_metrics_open([table])

    assert len(entries) == 1
    assert entries[0]["name"] == "carry"
    assert entries[0]["value"] == 20.0


def test_open_handles_usd_values_in_millions_not_just_billions():
    table = _table("t1", 1, rows=[{"Term": "GP Commitment", "Value": "$35M"}])

    entries = FinancialTableParser().parse_metrics_open([table])

    assert len(entries) == 1
    assert entries[0]["name"] == "gp_commitment"
    assert entries[0]["value"] == 35e6
    assert entries[0]["unit"] == "usd"


def test_open_first_match_wins_across_tables():
    table1 = _table("t1", 1, rows=[{"Metric": "Net IRR", "Current": "16.80%"}])
    table2 = _table("t2", 2, rows=[{"Metric": "Net IRR", "Current": "99.00%"}])

    entries = FinancialTableParser().parse_metrics_open([table1, table2])

    assert len(entries) == 1
    assert entries[0]["value"] == 16.80
