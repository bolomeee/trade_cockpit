"""Unit tests for pool_helpers (F205-b).

Covers all 5 pure functions + boundary conditions defined in
docs/开发/sprint-contracts/F205-b-contract.md §3.

Note on RS percentile formula:
  pool_helpers uses mid-rank: (below + 0.5·ties) / n * 100.
  setup_service._percentile_rank uses strictly-below: below / n * 100.
  These are intentionally different; the discrepancy is documented in D079.
  Tests here validate pool_helpers directly against expected mid-rank values.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from app.services.cockpit.pool_helpers import (
    compute_distance_to_50ma_pct,
    compute_return_ratio_250d,
    compute_rs_percentile_map,
    extract_revenue_growth_yoy_pct,
    passes_fundamental_sanity,
)

# ── compute_return_ratio_250d ─────────────────────────────────────────────────


def test_return_ratio_spy_return_zero_returns_none():
    """Test #5: flat SPY (return=0) → spy_return≈0 → None."""
    closes = [100.0] * 250
    spy = [100.0] * 250
    assert compute_return_ratio_250d(closes, spy) is None


def test_return_ratio_stock_up20_spy_up10():
    """Test #6: stock +20%, SPY +10% → ratio ≈ 2.0."""
    closes = [100.0] + [100.0] * 248 + [120.0]
    spy = [100.0] + [100.0] * 248 + [110.0]
    result = compute_return_ratio_250d(closes, spy)
    assert result is not None
    assert abs(result - 2.0) < 1e-9


def test_return_ratio_short_stock_sequence_returns_none():
    """Test #7: stock sequence < 250 → None."""
    assert compute_return_ratio_250d([100.0] * 249, [100.0] * 250) is None


def test_return_ratio_short_spy_sequence_returns_none():
    """Test #7: SPY sequence < 250 → None."""
    assert compute_return_ratio_250d([100.0] * 250, [100.0] * 249) is None


def test_return_ratio_both_short_returns_none():
    assert compute_return_ratio_250d([100.0] * 10, [100.0] * 10) is None


def test_return_ratio_zero_first_close_returns_none():
    closes = [0.0] + [100.0] * 249
    spy = [100.0] * 250
    assert compute_return_ratio_250d(closes, spy) is None


def test_return_ratio_zero_first_spy_close_returns_none():
    closes = [100.0] * 250
    spy = [0.0] + [100.0] * 249
    assert compute_return_ratio_250d(closes, spy) is None


# ── compute_rs_percentile_map ─────────────────────────────────────────────────


def test_rs_percentile_no_ties_three_items():
    """Test #8: mid-rank percentile with no ties."""
    result = compute_rs_percentile_map({"A": 1.0, "B": 2.0, "C": 3.0})
    assert abs(result["A"] - 16.67) < 0.01
    assert abs(result["B"] - 50.0) < 0.01
    assert abs(result["C"] - 83.33) < 0.01


def test_rs_percentile_ties_mid_rank():
    """Test #9: two tied values get mid-rank; top value gets 83.33."""
    result = compute_rs_percentile_map({"A": 1.0, "B": 1.0, "C": 2.0})
    assert abs(result["A"] - 33.33) < 0.01
    assert abs(result["B"] - 33.33) < 0.01
    assert abs(result["C"] - 83.33) < 0.01


def test_rs_percentile_empty_dict():
    """Test #10: empty input → empty output."""
    assert compute_rs_percentile_map({}) == {}


def test_rs_percentile_none_value_treated_as_bottom():
    """Test #11: None ratio → assigned bottom rank; result stays in [0, 100]."""
    result = compute_rs_percentile_map({"A": None, "B": 1.0})
    assert 0 <= result["A"] <= 100
    assert 0 <= result["B"] <= 100
    assert result["A"] < result["B"]  # None < 1.0


def test_rs_percentile_all_none():
    result = compute_rs_percentile_map({"A": None, "B": None})
    # both map to -inf, so they tie at mid-rank 50
    assert abs(result["A"] - 50.0) < 0.01
    assert abs(result["B"] - 50.0) < 0.01


def test_rs_percentile_single_ticker():
    result = compute_rs_percentile_map({"A": 1.5})
    # only element: below=0, at=1, pct = 0.5/1*100 = 50.0
    assert abs(result["A"] - 50.0) < 0.01


def test_rs_percentile_values_in_range():
    ratios = {"T1": 0.5, "T2": 1.2, "T3": None, "T4": 2.5, "T5": 0.9}
    result = compute_rs_percentile_map(ratios)
    for pct in result.values():
        assert 0.0 <= pct <= 100.0


# ── compute_distance_to_50ma_pct ─────────────────────────────────────────────


def test_distance_above_50ma():
    """Test #12: close above MA."""
    assert abs(compute_distance_to_50ma_pct(110.0, 100.0) - 10.0) < 1e-9


def test_distance_below_50ma():
    """Test #12: close below MA."""
    assert abs(compute_distance_to_50ma_pct(95.0, 100.0) - (-5.0)) < 1e-9


def test_distance_ma50_none_returns_none():
    """Test #13: ma50=None → None."""
    assert compute_distance_to_50ma_pct(100.0, None) is None


def test_distance_ma50_zero_returns_none():
    """Test #13: ma50=0 → None (avoids ZeroDivisionError)."""
    assert compute_distance_to_50ma_pct(100.0, 0) is None


def test_distance_returns_four_decimal_places():
    result = compute_distance_to_50ma_pct(100.1234, 100.0)
    assert result is not None
    # result = (100.1234 - 100) / 100 * 100 = 0.1234
    assert abs(result - 0.1234) < 1e-4


# ── extract_revenue_growth_yoy_pct ────────────────────────────────────────────


def test_extract_revenue_growth_standard():
    """Test #14: standard FMP payload with 0.0202 → 2.02."""
    result = extract_revenue_growth_yoy_pct({"revenueGrowth": 0.0202})
    assert result is not None
    assert abs(result - 2.02) < 1e-9


def test_extract_revenue_growth_na_string():
    """Test #15: 'N/A' string → None (fail-open)."""
    assert extract_revenue_growth_yoy_pct({"revenueGrowth": "N/A"}) is None


def test_extract_revenue_growth_none_value():
    """Test #15: None field value → None."""
    assert extract_revenue_growth_yoy_pct({"revenueGrowth": None}) is None


def test_extract_revenue_growth_missing_field():
    """Test #15: field absent → None."""
    assert extract_revenue_growth_yoy_pct({}) is None


def test_extract_revenue_growth_none_payload():
    """Test #15: None payload → None."""
    assert extract_revenue_growth_yoy_pct(None) is None


def test_extract_revenue_growth_negative():
    result = extract_revenue_growth_yoy_pct({"revenueGrowth": -0.05})
    assert result is not None
    assert abs(result - (-5.0)) < 1e-9


# ── passes_fundamental_sanity ─────────────────────────────────────────────────


def test_passes_above_threshold():
    """Test #16: 15% growth, 10% threshold → True."""
    assert passes_fundamental_sanity(15.0, 10.0) is True


def test_fails_below_threshold():
    """Test #16: 8% growth, 10% threshold → False."""
    assert passes_fundamental_sanity(8.0, 10.0) is False


def test_passes_exactly_at_threshold():
    assert passes_fundamental_sanity(10.0, 10.0) is True


def test_passes_none_growth_fail_open():
    """Test #16: None → True (fail-open; D079)."""
    assert passes_fundamental_sanity(None, 10.0) is True


# ── pure module validation (Test #17) ────────────────────────────────────────


def test_pool_helpers_has_no_app_imports():
    """Test #17: pool_helpers.py must not import any app.* modules."""
    src = pathlib.Path(__file__).parent.parent / "app" / "services" / "cockpit" / "pool_helpers.py"
    tree = ast.parse(src.read_text())
    app_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app."):
                    app_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("app."):
                app_imports.append(module)
    assert app_imports == [], f"Unexpected app.* imports: {app_imports}"


def test_pool_helpers_has_no_io_imports():
    """Test #17: pool_helpers.py must not import logging / SQLAlchemy / httpx."""
    src = pathlib.Path(__file__).parent.parent / "app" / "services" / "cockpit" / "pool_helpers.py"
    tree = ast.parse(src.read_text())
    banned = {"logging", "sqlalchemy", "httpx", "requests"}
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(alias.name.startswith(b) for b in banned):
                    found.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if any(module.startswith(b) for b in banned):
                found.append(module)
    assert found == [], f"Banned imports found: {found}"
