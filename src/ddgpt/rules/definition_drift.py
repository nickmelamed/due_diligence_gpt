from __future__ import annotations
from typing import List, Optional
from ddgpt.rules.base import Rule, Flag
from ddgpt.layout.definitions import NET_PATTERNS, GROSS_PATTERNS


def _local_basis(snippet: str) -> Optional[str]:
    for pattern in NET_PATTERNS:
        if pattern.search(snippet):
            return "net"
    for pattern in GROSS_PATTERNS:
        if pattern.search(snippet):
            return "gross"
    return None


class DefinitionDriftRule(Rule):
    """Flags gross-vs-net (and equivalent before/after-fee) convention drift.

    Two checks, because convention is often stated once per section rather
    than once per number:
    - cross-document: each document's *document-wide* inferred convention
      (from Definitions/Terms/Performance Summary sections when available,
      see ddgpt.layout.definitions) disagrees with another document's.
    - within-document: the wording immediately next to the reported number
      disagrees with the convention the same document states elsewhere.
    """

    def apply(self, extracted: List[dict]) -> List[Flag]:
        flags: List[Flag] = []

        for i in range(len(extracted)):
            for j in range(i + 1, len(extracted)):
                A = extracted[i]
                B = extracted[j]
                ctx_a = A.get("net_irr_basis")
                ctx_b = B.get("net_irr_basis")
                basis_a = (ctx_a or {}).get("basis")
                basis_b = (ctx_b or {}).get("basis")

                if not basis_a or not basis_b or basis_a == basis_b:
                    continue

                flags.append(Flag(
                    severity="YELLOW",
                    type="IRR_DEFINITION_DRIFT",
                    docs=f'{A["doc_name"]} vs {B["doc_name"]}',
                    detail=f'Documents state different IRR return conventions: "{basis_a}" vs "{basis_b}".',
                    evidence=(
                        f'{A["doc_name"]} (p.{ctx_a.get("page")}, {ctx_a.get("section") or "n/a"}): "{ctx_a.get("snippet")}" | '
                        f'{B["doc_name"]} (p.{ctx_b.get("page")}, {ctx_b.get("section") or "n/a"}): "{ctx_b.get("snippet")}"'
                    ),
                    why_it_matters="Definition drift can mislead IC comparisons and skew underwriting decisions.",
                    question_to_ask="Confirm whether IRR reported is net or gross and reconcile to a consistent definition."
                ))

        for doc in extracted:
            net_irr = doc.get("net_irr") or {}
            snippet = ((net_irr.get("evidence") or {}).get("snippet")) or ""
            local_basis = _local_basis(snippet)

            ctx = doc.get("net_irr_basis")
            doc_basis = (ctx or {}).get("basis")

            if not local_basis or not doc_basis or local_basis == doc_basis:
                continue

            flags.append(Flag(
                severity="YELLOW",
                type="IRR_DEFINITION_DRIFT_INTERNAL",
                docs=doc["doc_name"],
                detail=(
                    f'The reported IRR figure reads as "{local_basis}" but this document defines its '
                    f'convention as "{doc_basis}" elsewhere.'
                ),
                evidence=(
                    f'Figure (p.{net_irr.get("evidence", {}).get("page")}): "{snippet}" | '
                    f'Convention (p.{ctx.get("page")}, {ctx.get("section") or "n/a"}): "{ctx.get("snippet")}"'
                ),
                why_it_matters="Inconsistent gross/net language within a single document is a red flag for underwriting rigor and can misstate performance.",
                question_to_ask="Confirm which convention actually governs the reported Net IRR figure."
            ))

        return flags
