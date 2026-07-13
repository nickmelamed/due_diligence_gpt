from __future__ import annotations
from typing import List
from ddgpt.rules.base import Rule, Flag


class IRRMentionConflictRule(Rule):
    """Catches a document stating a different IRR figure elsewhere in its
    text than the one that got extracted into target_irr/net_irr -- e.g. a
    Fund Performance table saying "Target IRR: 18%" while a Quarterly
    Investor Update paragraph elsewhere says "targeting a 20% gross IRR".

    Structured extraction only reliably captures the primary, cleanly
    labeled figure per field; a secondary claim buried in prose has
    nowhere to land except an LLM's free-text notes, where no rule can see
    it. This scans every IRR-shaped mention in the document (see
    ddgpt.layout.irr_mentions) and flags ones that don't reconcile with
    whatever was actually extracted.
    """

    def __init__(self, tolerance_pct_points: float = 1.0):
        self.tolerance_pct_points = tolerance_pct_points

    def apply(self, extracted: List[dict]) -> List[Flag]:
        flags: List[Flag] = []

        for doc in extracted:
            mentions = doc.get("irr_mentions") or []
            if not mentions:
                continue

            known_values = [
                v for v in (
                    (doc.get("target_irr") or {}).get("value"),
                    (doc.get("net_irr") or {}).get("value"),
                )
                if v is not None
            ]

            seen = set()

            for mention in mentions:
                value = mention.get("value")
                if value is None:
                    continue

                if any(abs(value - known) <= self.tolerance_pct_points for known in known_values):
                    continue  # restates an already-extracted figure, not a new claim

                dedup_key = (round(value, 1), mention.get("basis"))
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                basis_desc = f"{mention['basis']} " if mention.get("basis") else ""
                target_val = (doc.get("target_irr") or {}).get("value")
                net_val = (doc.get("net_irr") or {}).get("value")

                flags.append(Flag(
                    severity="YELLOW",
                    type="IRR_MENTION_CONFLICT",
                    docs=doc["doc_name"],
                    detail=(
                        f'Document also states a {basis_desc}IRR of {value}% elsewhere, which does not '
                        f'match the extracted Target IRR ({target_val}%) or Net IRR ({net_val}%).'
                    ),
                    evidence=f'p.{mention.get("page")}: "{mention.get("snippet")}"',
                    why_it_matters=(
                        "A document citing multiple, differently labeled IRR figures for what "
                        "reads as the same underlying claim is a red flag for underwriting "
                        "consistency and may indicate marketing language diverging from the "
                        "governing performance figures."
                    ),
                    question_to_ask=(
                        f'Confirm which IRR figure actually governs ({basis_desc}{value}% vs. the '
                        f'extracted figures) and reconcile the discrepancy.'
                    ),
                ))

        return flags
