from __future__ import annotations

from typing import List

from ddgpt.layout.models import Footnote
from ddgpt.extract.tables.table_models import ExtractedTable


def attach_footnotes_to_tables(
    tables: List[ExtractedTable],
    footnotes: List[Footnote],
) -> List[ExtractedTable]:
    """Associate footnotes with the tables on the same page.

    Table extraction (Camelot/pdfplumber) and footnote detection run as
    separate passes over the PDF; this links them back together so a
    footnote qualifying a figure in a fee/performance table travels with
    that table instead of being silently dropped.
    """
    if not footnotes:
        return tables

    by_page: dict[int, List[str]] = {}
    for fn in footnotes:
        by_page.setdefault(fn.page_num, []).append(fn.text)

    linked = []
    for table in tables:
        page_footnotes = by_page.get(table.page, [])
        if page_footnotes:
            linked.append(table.model_copy(update={"footnotes": page_footnotes}))
        else:
            linked.append(table)

    return linked
