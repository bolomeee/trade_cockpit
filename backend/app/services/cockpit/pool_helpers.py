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

    None growth (e.g. ETFs, missing FMP data) → fail-open: pass through
    so tickers aren't penalised purely for missing vendor data (D079).
    """
    if growth_yoy_pct is None:
        return True
    return growth_yoy_pct >= threshold_pct


def compute_fundamentals_row_from_balance_cash(
    balance_payload: dict,
    cash_payload: dict,
) -> dict | None:
    """Map one (BS, CF) pair (same ticker/fiscal_quarter) → dict for FundamentalsRepository.upsert.

    Both payloads must share identical symbol/period/fiscalYear/date; returns None on mismatch
    or missing identification fields. Pairing is the caller's responsibility.

    net_debt = total_debt - cash; null if either input null.
    cash source: cashAndShortTermInvestments, fallback cashAndCashEquivalents (NP-d6a-6).
    fcf source: FMP freeCashFlow field (NP-d6a-2, equivalent to D097 §5 OCF+capex formula).
    Returns 8 keys: ticker, fiscal_quarter, period_end_date, total_debt, cash, net_debt, fcf, fetched_at.
    """
    from datetime import date, datetime, timezone

    def _id_fields(p: dict) -> tuple | None:
        symbol = p.get("symbol")
        period = p.get("period")
        fiscal_year = p.get("fiscalYear")
        raw_date = p.get("date")
        if not all([symbol, period, fiscal_year, raw_date]):
            return None
        return (str(symbol), str(period), str(fiscal_year), str(raw_date))

    bs_id = _id_fields(balance_payload)
    cf_id = _id_fields(cash_payload)
    if bs_id is None or cf_id is None or bs_id != cf_id:
        return None

    symbol, period, fiscal_year, raw_date = bs_id
    try:
        period_end_date = date.fromisoformat(raw_date)
    except (ValueError, TypeError):
        return None

    fiscal_quarter = f"{period} {fiscal_year}"

    total_debt_raw = balance_payload.get("totalDebt")
    cash_raw = (
        balance_payload.get("cashAndShortTermInvestments")
        or balance_payload.get("cashAndCashEquivalents")
    )
    fcf_raw = cash_payload.get("freeCashFlow")

    def _to_int(v) -> int | None:
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    total_debt = _to_int(total_debt_raw)
    cash = _to_int(cash_raw)
    fcf = _to_int(fcf_raw)
    net_debt = (total_debt - cash) if (total_debt is not None and cash is not None) else None

    return {
        "ticker": symbol,
        "fiscal_quarter": fiscal_quarter,
        "period_end_date": period_end_date,
        "total_debt": total_debt,
        "cash": cash,
        "net_debt": net_debt,
        "fcf": fcf,
        "fetched_at": datetime.now(timezone.utc),
    }


def compute_supplemental_key_metrics_from_is_bs_cf(
    income_payload: dict,
    balance_payload: dict,
    cash_payload: dict,
) -> dict | None:
    """Build a partial-upsert dict for stock_key_metrics_quarterly (fcf_margin + roic only).

    All 3 payloads must share identical symbol/period/fiscalYear/date; returns None on mismatch
    or missing identification fields.

    fcf_margin = freeCashFlow / revenue; null if either missing or revenue ≤ 0.
    roic       ≈ netIncome / (totalStockholdersEquity + totalDebt - cash);
                 null if any input null or denominator ≤ 0 (D097 §5, NP-d6a-7).
    cash source: cashAndShortTermInvestments fallback cashAndCashEquivalents (NP-d6a-6).
    Output keys (exactly 5): ticker, fiscal_quarter, fcf_margin, roic, fetched_at.
    """
    from datetime import datetime, timezone

    def _id_key(p: dict) -> tuple | None:
        symbol = p.get("symbol")
        period = p.get("period")
        fiscal_year = p.get("fiscalYear")
        raw_date = p.get("date")
        if not all([symbol, period, fiscal_year, raw_date]):
            return None
        return (str(symbol), str(period), str(fiscal_year), str(raw_date))

    is_id = _id_key(income_payload)
    bs_id = _id_key(balance_payload)
    cf_id = _id_key(cash_payload)
    if None in (is_id, bs_id, cf_id) or not (is_id == bs_id == cf_id):
        return None

    symbol, period, fiscal_year, _ = is_id
    fiscal_quarter = f"{period} {fiscal_year}"
    ticker = str(symbol)

    def _to_float(v) -> float | None:
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    revenue = _to_float(income_payload.get("revenue"))
    net_income = _to_float(income_payload.get("netIncome"))
    fcf = _to_float(cash_payload.get("freeCashFlow"))
    equity = _to_float(balance_payload.get("totalStockholdersEquity"))
    total_debt = _to_float(balance_payload.get("totalDebt"))
    cash_raw = (
        balance_payload.get("cashAndShortTermInvestments")
        or balance_payload.get("cashAndCashEquivalents")
    )
    cash = _to_float(cash_raw)

    fcf_margin: float | None = None
    if fcf is not None and revenue is not None and revenue > 0:
        fcf_margin = fcf / revenue

    roic: float | None = None
    if all(v is not None for v in (net_income, equity, total_debt, cash)):
        denom = equity + total_debt - cash  # type: ignore[operator]
        if denom > 0:
            roic = net_income / denom  # type: ignore[operator]

    return {
        "ticker": ticker,
        "fiscal_quarter": fiscal_quarter,
        "fcf_margin": fcf_margin,
        "roic": roic,
        "fetched_at": datetime.now(timezone.utc),
    }


def compute_key_metrics_row_from_income_statement(
    payload: dict,
) -> dict | None:
    """Map one FMP /income-statement?period=quarter record → dict for KeyMetricsRepository.upsert.

    Returns None if `payload` lacks required identification fields (symbol/period/fiscalYear/date).
    For numeric inputs where revenue is missing/zero, the corresponding margin field is set to None
    (D097 §5 + DATA-MODEL.md null rules). No rounding — DB Float stores natural precision.

    Output keys (exactly 7): ticker, fiscal_quarter, period_end_date,
    gross_margin, op_margin, net_margin, fetched_at.
    Does NOT include fcf_margin / roic (F218-d6a will partial-upsert those via null-not-erase).
    """
    from datetime import date, datetime, timezone

    symbol = payload.get("symbol")
    period = payload.get("period")
    fiscal_year = payload.get("fiscalYear")
    raw_date = payload.get("date")

    if not all([symbol, period, fiscal_year, raw_date]):
        return None

    try:
        period_end_date = date.fromisoformat(str(raw_date))
    except (ValueError, TypeError):
        return None

    fiscal_quarter = f"{period} {fiscal_year}"

    revenue = payload.get("revenue")
    gross_profit = payload.get("grossProfit")
    operating_income = payload.get("operatingIncome")
    net_income = payload.get("netIncome")

    def _margin(numerator, denom) -> float | None:
        if denom is None or denom == 0 or numerator is None:
            return None
        try:
            return float(numerator) / float(denom)
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    return {
        "ticker": str(symbol),
        "fiscal_quarter": fiscal_quarter,
        "period_end_date": period_end_date,
        "gross_margin": _margin(gross_profit, revenue),
        "op_margin": _margin(operating_income, revenue),
        "net_margin": _margin(net_income, revenue),
        "fetched_at": datetime.now(timezone.utc),
    }
