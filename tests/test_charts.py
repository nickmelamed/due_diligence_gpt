from ddgpt.render.charts import (
    collect_metric_figures,
    docs_flagged_for_metric,
    render_metric_reconciliation_chart,
)


def _doc(doc_name, metrics):
    return {"doc_name": doc_name, "metrics": metrics}


def _metric(name, value, unit="multiple", raw_label=None):
    return {"name": name, "value": value, "unit": unit, "raw_label": raw_label or name}


def test_collect_metric_figures_gathers_every_document_with_that_metric():
    extracted = [
        _doc("A.pdf", [_metric("dpi", 0.40)]),
        _doc("B.pdf", [_metric("dpi", 0.90)]),
        _doc("C.pdf", [_metric("tvpi", 1.5)]),  # different metric, excluded
    ]

    figures = collect_metric_figures(extracted, "dpi")

    assert len(figures) == 2
    assert {f["doc_name"] for f in figures} == {"A.pdf", "B.pdf"}
    assert all(f["status"] == "extracted" for f in figures)


def test_collect_metric_figures_marks_conflicting_docs():
    extracted = [
        _doc("A.pdf", [_metric("dpi", 0.40)]),
        _doc("B.pdf", [_metric("dpi", 0.90)]),
    ]

    figures = collect_metric_figures(extracted, "dpi", conflicting_doc_names={"B.pdf"})

    by_doc = {f["doc_name"]: f for f in figures}
    assert by_doc["A.pdf"]["status"] == "extracted"
    assert by_doc["B.pdf"]["status"] == "conflict"


def test_collect_metric_figures_skips_null_values():
    extracted = [_doc("A.pdf", [_metric("dpi", None)])]
    assert collect_metric_figures(extracted, "dpi") == []


def test_docs_flagged_for_metric_parses_docs_vs_docs():
    flags = [
        {"metric": "dpi", "docs": "A.pdf vs B.pdf"},
        {"metric": "aum", "docs": "A.pdf vs C.pdf"},
    ]
    assert docs_flagged_for_metric(flags, "dpi") == {"A.pdf", "B.pdf"}
    assert docs_flagged_for_metric(flags, "aum") == {"A.pdf", "C.pdf"}
    assert docs_flagged_for_metric(flags, "tvpi") == set()


def test_render_metric_reconciliation_chart_returns_none_below_two_figures():
    figures = [{"label": "DPI", "doc_name": "A.pdf", "value": 0.4, "unit": "multiple", "status": "extracted"}]
    assert render_metric_reconciliation_chart(figures) is None


def test_render_metric_reconciliation_chart_returns_png_bytes_for_two_or_more():
    figures = [
        {"label": "DPI", "doc_name": "A.pdf", "value": 0.4, "unit": "multiple", "status": "extracted"},
        {"label": "DPI", "doc_name": "B.pdf", "value": 0.9, "unit": "multiple", "status": "conflict"},
    ]
    png_bytes = render_metric_reconciliation_chart(figures)
    assert png_bytes is not None
    assert png_bytes.startswith(b"\x89PNG")
