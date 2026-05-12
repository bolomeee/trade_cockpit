from math import floor


def compute_shares(*, account_size: float, risk_pct: float, entry: float, stop: float) -> int:
    """D066: position sizing formula. Returns 0 for invalid inputs."""
    if entry <= stop or risk_pct <= 0 or account_size <= 0:
        return 0
    return floor(account_size * risk_pct / 100 / (entry - stop))
