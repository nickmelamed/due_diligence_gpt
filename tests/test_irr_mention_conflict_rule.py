from ddgpt.rules.irr_mention_conflict import IRRMentionConflictRule


def _doc(target_irr=18.0, net_irr=16.8, mentions=None):
    return {
        "doc_name": "test_packet.pdf",
        "target_irr": {"value": target_irr},
        "net_irr": {"value": net_irr},
        "irr_mentions": mentions or [],
    }


def test_no_flag_when_mention_restates_extracted_target_irr():
    doc = _doc(mentions=[{"value": 18.0, "basis": None, "page": 2, "snippet": "Target IRR: 18%"}])
    flags = IRRMentionConflictRule(tolerance_pct_points=1.0).apply([doc])
    assert flags == []


def test_no_flag_when_mention_restates_extracted_net_irr():
    doc = _doc(mentions=[{"value": 16.8, "basis": "net", "page": 2, "snippet": "Net IRR: 16.8%"}])
    flags = IRRMentionConflictRule(tolerance_pct_points=1.0).apply([doc])
    assert flags == []


def test_flag_when_secondary_mention_conflicts():
    doc = _doc(mentions=[
        {"value": 18.0, "basis": None, "page": 2, "snippet": "Target IRR: 18%"},
        {"value": 20.0, "basis": "gross", "page": 2, "snippet": "targeting a 20% gross IRR"},
    ])
    flags = IRRMentionConflictRule(tolerance_pct_points=1.0).apply([doc])

    assert len(flags) == 1
    assert flags[0].type == "IRR_MENTION_CONFLICT"
    assert "20.0%" in flags[0].detail
    assert flags[0].docs == "test_packet.pdf"


def test_duplicate_conflicting_mentions_deduped_to_one_flag():
    doc = _doc(mentions=[
        {"value": 20.0, "basis": "gross", "page": 2, "snippet": "20% gross IRR (first mention)"},
        {"value": 20.0, "basis": "gross", "page": 5, "snippet": "20% gross IRR (repeated)"},
    ])
    flags = IRRMentionConflictRule(tolerance_pct_points=1.0).apply([doc])
    assert len(flags) == 1


def test_no_flag_when_no_mentions_present():
    doc = _doc(mentions=[])
    flags = IRRMentionConflictRule(tolerance_pct_points=1.0).apply([doc])
    assert flags == []


def test_within_tolerance_not_flagged():
    # 18.5 is within the 1.0-pt tolerance of the extracted 18.0 target_irr
    doc = _doc(mentions=[{"value": 18.5, "basis": "gross", "page": 2, "snippet": "18.5% gross IRR"}])
    flags = IRRMentionConflictRule(tolerance_pct_points=1.0).apply([doc])
    assert flags == []
