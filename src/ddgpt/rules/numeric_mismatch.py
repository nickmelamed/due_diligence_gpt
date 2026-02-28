from __future__ import annotations
from typing import List
from ddgpt.rules.base import Rule, Flag

def pct_delta(a: float, b: float) -> float:
    denom = (abs(a) + abs(b)) / 2.0
    if denom == 0:
        return 0.0
    return abs(a - b) / denom

class NumericMismatchRule(Rule):
    def __init__(self, aum_tol_pct: float, fee_abs_pct: float, target_irr_abs: float):
        self.aum_tol_pct = aum_tol_pct
        self.fee_abs_pct = fee_abs_pct
        self.target_irr_abs = target_irr_abs

    def apply(self, extracted: List[dict]) -> List[Flag]:
        flags: List[Flag] = []
        for i in range(len(extracted)):
            for j in range(i+1, len(extracted)):
                A = extracted[i]; B = extracted[j]
                docA = A["doc_name"]; docB = B["doc_name"]

                aumA = A["aum"]["value"]; aumB = B["aum"]["value"]
                if aumA is not None and aumB is not None:
                    d = pct_delta(aumA, aumB)
                    if d > self.aum_tol_pct:
                        flags.append(Flag(
                            severity="RED",
                            type="AUM_MISMATCH",
                            docs=f"{docA} vs {docB}",
                            detail=f"AUM differs by {d*100:.1f}%",
                            evidence=f'{docA} (p.{A["aum"]["evidence"]["page"]}): {A["aum"]["evidence"]["snippet"]} | {docB} (p.{B["aum"]["evidence"]["page"]}): {B["aum"]["evidence"]["snippet"]}',
                            why_it_matters="AUM impacts scale, fees, and benchmarking; mismatches require reconciliation.",
                            question_to_ask="Which document is authoritative for AUM as-of date? Provide supporting statement/capital account detail."
                        ))

                feeA = A["mgmt_fee"]["value"]; feeB = B["mgmt_fee"]["value"]
                if feeA is not None and feeB is not None:
                    if abs(feeA - feeB) > self.fee_abs_pct:
                        flags.append(Flag(
                            severity="RED",
                            type="MGMT_FEE_MISMATCH",
                            docs=f"{docA} vs {docB}",
                            detail=f"Management fee differs: {feeA:.2f}% vs {feeB:.2f}%",
                            evidence=f'{docA} (p.{A["mgmt_fee"]["evidence"]["page"]}): {A["mgmt_fee"]["evidence"]["snippet"]} | {docB} (p.{B["mgmt_fee"]["evidence"]["page"]}): {B["mgmt_fee"]["evidence"]["snippet"]}',
                            why_it_matters="Fee terms directly affect net returns and legal obligations; LPA typically governs.",
                            question_to_ask="Confirm the controlling fee schedule and whether any side-letter modifies the base fee."
                        ))

                tA = A["target_irr"]["value"]; tB = B["target_irr"]["value"]
                if tA is not None and tB is not None and abs(tA - tB) > self.target_irr_abs:
                    flags.append(Flag(
                        severity="YELLOW",
                        type="TARGET_IRR_DRIFT",
                        docs=f"{docA} vs {docB}",
                        detail=f"Target IRR differs: {tA:.1f}% vs {tB:.1f}%",
                        evidence=f'{docA} (p.{A["target_irr"]["evidence"]["page"]}): {A["target_irr"]["evidence"]["snippet"]} | {docB} (p.{B["target_irr"]["evidence"]["page"]}): {B["target_irr"]["evidence"]["snippet"]}',
                        why_it_matters="Different stated targets can reflect marketing vs underwriting assumptions.",
                        question_to_ask="Is one target marketing and the other underwriting base-case? Which governs IC decision-making?"
                    ))
        return flags
