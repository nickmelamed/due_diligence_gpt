from ddgpt.rules.base import Rule, Flag

class InternalInconsistencyRule(Rule):
    def apply(self, extracted):
        flags = []

        for doc in extracted:
            target = doc["target_irr"]["value"]
            net = doc["net_irr"]["value"]

            if (
                target is not None and
                net is not None and
                net < target
            ):
                flags.append(
                    Flag(
                        severity="YELLOW",
                        type="UNDER_TARGET_PERFORMANCE",
                        docs=doc["doc_name"],
                        detail="Net IRR below target IRR",
                        evidence=(
                            f'Net IRR={net}% | '
                            f'Target IRR={target}%'
                        ),
                        why_it_matters=(
                            "Fund may be underperforming "
                            "stated underwriting targets."
                        ),
                        question_to_ask=(
                            "What is driving the "
                            "performance shortfall?"
                        )
                    )
                )

        return flags