from __future__ import annotations
from typing import List
from ddgpt.rules.base import Rule, Flag

class DefinitionDriftRule(Rule):
    def apply(self, extracted: List[dict]) -> List[Flag]:
        flags: List[Flag] = []
        for i in range(len(extracted)):
            for j in range(i+1, len(extracted)):
                A = extracted[i]; B = extracted[j]
                docA = A["doc_name"]; docB = B["doc_name"]
                snA = (A["net_irr"]["evidence"]["snippet"] or "").lower()
                snB = (B["net_irr"]["evidence"]["snippet"] or "").lower()
                if not snA or not snB:
                    continue
                a_gross = "gross" in snA
                a_net = "net" in snA
                b_gross = "gross" in snB
                b_net = "net" in snB
                if (a_gross and b_net) or (a_net and b_gross):
                    flags.append(Flag(
                        severity="YELLOW",
                        type="IRR_DEFINITION_DRIFT",
                        docs=f"{docA} vs {docB}",
                        detail="IRR definition language differs (gross vs net).",
                        evidence=f'{docA} (p.{A["net_irr"]["evidence"]["page"]}): {A["net_irr"]["evidence"]["snippet"]} | {docB} (p.{B["net_irr"]["evidence"]["page"]}): {B["net_irr"]["evidence"]["snippet"]}',
                        why_it_matters="Definition drift can mislead IC comparisons and skew underwriting decisions.",
                        question_to_ask="Confirm whether IRR reported is net or gross and reconcile to a consistent definition."
                    ))
        return flags
