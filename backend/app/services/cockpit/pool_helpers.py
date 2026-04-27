"""F205-b: pool funnel 计算 helpers，纯函数，由 F205-c 编排。

这些函数是 population-agnostic 的：调用方负责提供正确的 population（trend 子集），
本模块只做计算，不做 IO、不查数据库、不打日志。
"""
from __future__ import annotations


def compute_return_ratio_250d(
    closes: list[float],
    spy_closes: list[float],
) -> float | None:
    """Return stock_return / spy_return over the provided 250-session sequences.

    Both sequences must contain ≥250 data points (oldest→newest). spy_return≈0
    would produce division instability, so we return None rather than an
    infinite or meaningless ratio that would corrupt the RS percentile map.
    """
    if len(closes) < 250 or len(spy_closes) < 250:
        return None
    first_s, last_s = closes[0], closes[-1]
    first_spy, last_spy = spy_closes[0], spy_closes[-1]
    if first_s == 0 or first_spy == 0:
        return None
    stock_return = (last_s - first_s) / first_s
    spy_return = (last_spy - first_spy) / first_spy
    if abs(spy_return) < 0.001:
        return None
    return stock_return / spy_return


def compute_rs_percentile_map(
    ratio_by_ticker: dict[str, float | None],
) -> dict[str, float]:
    """Mid-rank percentile (0–100) of each RS ratio within the supplied population.

    None values are treated as the absolute bottom so a missing ratio does not
    silently inflate a ticker's rank. Mid-rank formula: (below + 0.5·ties) / n
    ensures ties get the average of the ranks they would occupy, avoiding the
    systematic underestimation of a strictly-below approach.
    """
    if not ratio_by_ticker:
        return {}
    _BOTTOM = float("-inf")
    tickers = list(ratio_by_ticker.keys())
    vals = [v if v is not None else _BOTTOM for v in ratio_by_ticker.values()]
    n = len(vals)
    result: dict[str, float] = {}
    for ticker, v in zip(tickers, vals):
        below = sum(1 for x in vals if x < v)
        at = sum(1 for x in vals if x == v)
        result[ticker] = round((below + 0.5 * at) / n * 100, 2)
    return result


def compute_distance_to_50ma_pct(
    close: float,
    ma50: float | None,
) -> float | None:
    """Distance of close above/below the 50-day MA, expressed as a percentage.

    ma50=None or 0 would produce division by zero; return None rather than
    raise so pool funnel callers can treat the value as 'data unavailable'.
    """
    if ma50 is None or ma50 == 0:
        return None
    return round((close - ma50) / ma50 * 100, 4)


def extract_revenue_growth_yoy_pct(
    financial_growth_payload: dict | None,
) -> float | None:
    """Read revenueGrowth from a get_financial_growth() dict and convert to percent.

    FMP may omit the field, return 'N/A' strings, or carry None; all of these
    map to None here so callers can apply fail-open logic (D079).
    """
    if not financial_growth_payload:
        return None
    try:
        return float(financial_growth_payload["revenueGrowth"]) * 100
    except (KeyError, TypeError, ValueError):
        return None


def passes_fundamental_sanity(
    growth_yoy_pct: float | None,
    threshold_pct: float,
) -> bool:
    """True when the ticker meets the revenue growth threshold.

    None growth means FMP data is unavailable — fail-open (return True) so
    we do not penalise a ticker purely because of missing vendor data (D079).
    """
    if growth_yoy_pct is None:
        return True
    return growth_yoy_pct >= threshold_pct
