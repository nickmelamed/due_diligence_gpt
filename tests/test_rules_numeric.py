from ddgpt.rules.numeric_mismatch import NumericMismatchRule

def test_fee_mismatch_triggers_red():
    extracted = [
        {
            "doc_name": "Manager.pdf",
            "aum": {"value": 1200000000, "confidence": 0.7, "evidence": {"doc_name":"Manager.pdf","page":1,"snippet":"AUM: $1.20B"}},
            "mgmt_fee": {"value": 2.0, "confidence": 0.7, "basis": None, "evidence": {"doc_name":"Manager.pdf","page":1,"snippet":"Management Fee: 2.0%"}},
            "target_irr": {"value": 18.0, "confidence": 0.7, "evidence": {"doc_name":"Manager.pdf","page":1,"snippet":"Target IRR: 18%"}},
        },
        {
            "doc_name": "LPA.pdf",
            "aum": {"value": 1200000000, "confidence": 0.9, "evidence": {"doc_name":"LPA.pdf","page":1,"snippet":"AUM: $1.20B"}},
            "mgmt_fee": {"value": 1.75, "confidence": 0.9, "basis": None, "evidence": {"doc_name":"LPA.pdf","page":1,"snippet":"Management Fee shall be 1.75%"}},
            "target_irr": {"value": 18.0, "confidence": 0.9, "evidence": {"doc_name":"LPA.pdf","page":1,"snippet":"Target IRR: 18%"}},
        },
    ]
    rule = NumericMismatchRule(aum_tol_pct=0.03, fee_abs_pct=0.10, target_irr_abs=2.0)
    flags = rule.apply(extracted)
    assert any(f.type == "MGMT_FEE_MISMATCH" and f.severity == "RED" for f in flags)
