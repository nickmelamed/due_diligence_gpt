from __future__ import annotations
from typing import List, Dict, Any
import pandas as pd

def to_facts_table(extracted: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for d in extracted:
        rows.append({
            "doc_name": d["doc_name"],
            "doc_date": d.get("doc_date"),
            "aum_value_usd": d["aum"]["value"],
            "aum_conf": d["aum"]["confidence"],
            "aum_page": d["aum"]["evidence"]["page"],
            "aum_snippet": d["aum"]["evidence"]["snippet"],
            "net_irr_pct": d["net_irr"]["value"],
            "net_irr_conf": d["net_irr"]["confidence"],
            "tvpi": d["tvpi"]["value"],
            "target_irr_pct": d["target_irr"]["value"],
            "mgmt_fee_pct": d["mgmt_fee"]["value"],
            "mgmt_fee_conf": d["mgmt_fee"]["confidence"],
            "mgmt_fee_page": d["mgmt_fee"]["evidence"]["page"],
            "mgmt_fee_snippet": d["mgmt_fee"]["evidence"]["snippet"],
            "carry_pct": d["carry"]["value"],
            "carry_hurdle_pct": d["carry"]["hurdle"],
            "carry_conf": d["carry"]["confidence"],
            "missing_fields": ", ".join(d.get("missing_fields", [])),
            "notes": " | ".join(d.get("notes", [])),
        })
    return pd.DataFrame(rows)
