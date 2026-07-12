from ddgpt.risk.engine import RiskEngine


def test_score_is_zero_with_no_flags():
    assert RiskEngine.score_from_severities([]) == 0.0


def test_more_red_flags_score_higher_than_one():
    one_red = RiskEngine.score_from_severities(["RED"])
    ten_red = RiskEngine.score_from_severities(["RED"] * 10)

    # A flat average could not distinguish these -- both would average to
    # the same per-flag weight. The score must be monotonically increasing
    # in flag count, not just severity mix.
    assert ten_red > one_red


def test_score_is_bounded_below_one():
    many_red = RiskEngine.score_from_severities(["RED"] * 50)
    assert many_red < 1.0


def test_red_scores_higher_than_yellow_for_same_count():
    red_score = RiskEngine.score_from_severities(["RED"])
    yellow_score = RiskEngine.score_from_severities(["YELLOW"])
    assert red_score > yellow_score
