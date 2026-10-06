def final_confidence(extraction_conf, authority, agreement, recency):
    return (
        0.35 * extraction_conf +
        0.25 * authority +
        0.20 * agreement +
        0.20 * recency
    )

def compute_agreement(values, tolerance=0.05):
    """Cross-extractor agreement for a single field, in [0, 1].

    1.0 when only zero/one extractor produced a value (nothing to disagree
    with), or when the extractors' values are within `tolerance` of each
    other. Degrades linearly as the relative spread between the min and max
    reported value grows beyond that tolerance.
    """
    present = [v for v in values if v is not None]
    if len(present) < 2:
        return 1.0

    hi, lo = max(present), min(present)
    denom = (abs(hi) + abs(lo)) / 2.0
    if denom == 0:
        return 1.0

    relative_spread = abs(hi - lo) / denom
    if relative_spread <= tolerance:
        return 1.0

    return max(0.0, 1.0 - relative_spread)