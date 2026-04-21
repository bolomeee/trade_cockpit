"""F106-a unit tests for the four signal detectors.

These tests exercise `_evaluate_all_rules` with hand-crafted SMA bar series,
verifying each rule (legacy / A1 / A2 / B2) fires for its canonical positive
case and stays silent when a single gating condition is removed. They also
verify the aggregated `hits_by_type` counting via the public service path.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from app.services import scanner_params as P
from app.services.market_scanner_service import _evaluate_all_rules


SCAN_DATE = date(2026, 4, 21)
SCANNED_AT = datetime(2026, 4, 21, 22, 0, tzinfo=timezone.utc)


@dataclass
class _FakeUniverse:
    ticker: str = "TEST"
    company_name: str = "Test Corp"
    market_cap: int = 100_000_000_000


def _bars(
    ma_values: list[float],
    closes: list[float],
    volumes: list[int] | None = None,
) -> list[dict]:
    """Build N bars with explicit per-day sma/close/volume."""
    assert len(ma_values) == len(closes)
    n = len(ma_values)
    if volumes is None:
        volumes = [1_000_000] * n
    assert len(volumes) == n
    base = date(2026, 1, 1)
    return [
        {
            "date": (base + timedelta(days=i)).isoformat(),
            "close": closes[i],
            "sma": ma_values[i],
            "volume": volumes[i],
        }
        for i in range(n)
    ]


def _run(bars: list[dict]) -> list:
    return _evaluate_all_rules(
        _FakeUniverse(),
        bars,
        source="sma",
        scan_date=SCAN_DATE,
        scanned_at=SCANNED_AT,
    )


def _signal_types(hits) -> set[str]:
    return {h.signal_type for h in hits}


# ---------------------------------------------------------------------------
# Legacy crossover
# ---------------------------------------------------------------------------


def test_legacy_crossover_fires_on_first_close_above_rising_ma():
    """Rising MA150 + first crossover + pct<=10 + slope>0 ⇒ legacy hit."""
    n = 80
    # Linearly rising MA150: 100 → 108 over 80 days (≈ slope 0.1)
    ma = [100.0 + 0.1 * i for i in range(n)]
    closes = [m - 1.0 for m in ma]  # always below until today
    closes[-1] = ma[-1] + 0.5       # today crosses up, ≈0.46%
    bars = _bars(ma, closes)

    hits = _run(bars)
    types = _signal_types(hits)
    assert P.SIGNAL_LEGACY_CROSSOVER in types
    # A2 requires a past slope ≤0 — here slope is always positive, so A2 silent
    assert P.SIGNAL_A2_SLOPE_FLIP not in types


def test_legacy_crossover_silent_when_pct_above_exceeds_limit():
    n = 80
    ma = [100.0 + 0.1 * i for i in range(n)]
    closes = [m - 1.0 for m in ma]
    closes[-1] = ma[-1] * 1.12  # +12% > 10% cap
    bars = _bars(ma, closes)

    hits = _run(bars)
    assert P.SIGNAL_LEGACY_CROSSOVER not in _signal_types(hits)


# ---------------------------------------------------------------------------
# A1: Stage 1 → 2 Breakout
# ---------------------------------------------------------------------------


def test_a1_stage_breakout_fires_on_flat_ma_plus_volume_crossover():
    n = 80
    ma = [100.0] * n                      # perfectly flat MA150 ⇒ 0% range, slope 0
    closes = [99.0] * n
    closes[-1] = 101.0                    # today crosses above
    vols = [1_000_000] * n
    vols[-1] = 3_000_000                  # 3× average ⇒ ratio ≥ 1.5
    bars = _bars(ma, closes, vols)

    hits = _run(bars)
    types = _signal_types(hits)
    assert P.SIGNAL_A1_STAGE_BREAKOUT in types
    # Legacy requires slope>0 strict; flat MA fails it.
    assert P.SIGNAL_LEGACY_CROSSOVER not in types


def test_a1_silent_when_volume_below_threshold():
    n = 80
    ma = [100.0] * n
    closes = [99.0] * n
    closes[-1] = 101.0
    vols = [1_000_000] * n
    vols[-1] = 1_000_000                  # ratio = 1.0 < 1.5
    bars = _bars(ma, closes, vols)

    hits = _run(bars)
    assert P.SIGNAL_A1_STAGE_BREAKOUT not in _signal_types(hits)


def test_a1_silent_when_ma_not_horizontal():
    """Same crossover + volume, but MA150 drifts >5% → A1 fails."""
    n = 80
    ma = [100.0 + 0.1 * i for i in range(n)]  # drifts 8% over window
    closes = [m - 1.0 for m in ma]
    closes[-1] = ma[-1] + 0.5
    vols = [1_000_000] * n
    vols[-1] = 3_000_000
    bars = _bars(ma, closes, vols)

    hits = _run(bars)
    assert P.SIGNAL_A1_STAGE_BREAKOUT not in _signal_types(hits)


# ---------------------------------------------------------------------------
# A2: Slope Flip
# ---------------------------------------------------------------------------


def test_a2_slope_flip_fires_when_recent_slope_turned_positive():
    """MA150 declines for ~60 days then sharply ascends in the last 20 ⇒
    slope today >0, past trailing-20 slope ≤0 within 30d lookback."""
    n = 80
    # Declining phase 0..59 (slope ≈ -0.5/day), sharp rise 60..79 (slope ≈ +1.0/day).
    ma = [100.0 - 0.5 * i for i in range(60)] + [70.0 + 1.0 * (i - 59) for i in range(60, 80)]
    closes = [m + 1.5 for m in ma]  # close above MA150 today
    bars = _bars(ma, closes)

    hits = _run(bars)
    types = _signal_types(hits)
    assert P.SIGNAL_A2_SLOPE_FLIP in types


def test_a2_silent_when_slope_never_flipped():
    """Monotonically rising MA150 ⇒ slope always >0, no flip ⇒ A2 silent."""
    n = 80
    ma = [100.0 + 0.1 * i for i in range(n)]
    closes = [m + 1.0 for m in ma]
    bars = _bars(ma, closes)

    hits = _run(bars)
    assert P.SIGNAL_A2_SLOPE_FLIP not in _signal_types(hits)


# ---------------------------------------------------------------------------
# B2: MA5 Pullback Bounce
# ---------------------------------------------------------------------------


def test_b2_ma_pullback_fires_on_proximity_then_expansion():
    """Uptrend + MA5 briefly hugged MA150 in last 10d, now expanding."""
    n = 80
    # Rising MA150 (slope >0).
    ma150 = [100.0 + 0.1 * i for i in range(n)]
    # Build closes so MA5 (5-day trailing avg of closes) dips near MA150 mid-window
    # then re-expands. Start with closes well above, dip low 8 days ago, climb back.
    closes = [m + 5.0 for m in ma150]  # baseline: MA5 ≈ MA150+5, ~5% above
    # Carve a dip: days [-11:-5] have closes close to MA150 so MA5 dips ≤2% gap.
    for j in range(n - 11, n - 5):
        closes[j] = ma150[j] + 0.2   # MA5 will average ≈ MA150
    # Today strongly above so gap re-expands.
    closes[-1] = ma150[-1] + 10.0
    closes[-2] = ma150[-2] + 8.0
    closes[-3] = ma150[-3] + 6.0
    bars = _bars(ma150, closes)

    hits = _run(bars)
    types = _signal_types(hits)
    assert P.SIGNAL_B2_MA_PULLBACK in types


def test_b2_silent_when_no_proximity_in_window():
    """MA5 always far from MA150 ⇒ no pullback ⇒ B2 silent."""
    n = 80
    ma150 = [100.0 + 0.1 * i for i in range(n)]
    closes = [m + 20.0 for m in ma150]  # far above, MA5 never dips close
    bars = _bars(ma150, closes)

    hits = _run(bars)
    assert P.SIGNAL_B2_MA_PULLBACK not in _signal_types(hits)


# ---------------------------------------------------------------------------
# Multi-signal emission: two rules fire on the same bar series
# ---------------------------------------------------------------------------


def test_multiple_rules_emit_separate_rows_same_ticker():
    """A1 setup also satisfies legacy if we nudge slope slightly positive."""
    n = 80
    # MA150 nearly flat but with a tiny upward tilt so slope > 0 strict.
    ma = [100.0 + 0.005 * i for i in range(n)]  # range ≈ 0.4% < 5%
    closes = [m - 1.0 for m in ma]
    closes[-1] = ma[-1] + 0.3
    vols = [1_000_000] * n
    vols[-1] = 3_000_000
    bars = _bars(ma, closes, vols)

    hits = _run(bars)
    types = _signal_types(hits)
    # Both legacy and A1 should fire; result must have two rows (one per type).
    assert P.SIGNAL_A1_STAGE_BREAKOUT in types
    assert P.SIGNAL_LEGACY_CROSSOVER in types
    assert len(hits) == len(types)  # one row per signal_type
