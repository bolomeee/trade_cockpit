from typing import Literal


def compute_next_action(
    *,
    last_close: float | None,
    entry_price: float,
    stop_price: float,
    days_until_earnings: int | None,
) -> Literal["hold", "raise_stop", "reduce", "exit"]:
    """Deterministic next-action rule engine (F206-a, reused by F207).

    Priority (first match wins):
    1. last_close <= stop_price → exit
    2. days_until_earnings <= 2 → reduce
    3. r_multiple >= 2.0 AND stop still below entry → raise_stop
    4. otherwise → hold
    """
    if last_close is None:
        return "hold"
    if last_close <= stop_price:
        return "exit"
    if days_until_earnings is not None and days_until_earnings <= 2:
        return "reduce"
    risk = entry_price - stop_price
    if risk > 0:
        r = (last_close - entry_price) / risk
        if r >= 2.0 and stop_price < entry_price:
            return "raise_stop"
    return "hold"
