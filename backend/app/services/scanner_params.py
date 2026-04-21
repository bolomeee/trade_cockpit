"""F106 Multi-Signal Scanner parameters.

All thresholds and windows for the A1 / A2 / B2 rules live here so users
can tune behavior without touching scanner logic. Legacy F105 crossover
parameters are kept here too for symmetry.

Any change here takes effect on the next scan (no migration needed).
"""
from __future__ import annotations

# -- Signal type constants ---------------------------------------------------
# These string values are the on-disk enum and the API-contract enum.

SIGNAL_LEGACY_CROSSOVER = "legacy_crossover"
SIGNAL_A1_STAGE_BREAKOUT = "a1_stage_breakout"
SIGNAL_A2_SLOPE_FLIP = "a2_slope_flip"
SIGNAL_B2_MA_PULLBACK = "b2_ma_pullback"

ALL_SIGNAL_TYPES: tuple[str, ...] = (
    SIGNAL_LEGACY_CROSSOVER,
    SIGNAL_A1_STAGE_BREAKOUT,
    SIGNAL_A2_SLOPE_FLIP,
    SIGNAL_B2_MA_PULLBACK,
)

# API default: what the widget shows. Legacy is excluded by default
# (kept in DB as a baseline but hidden from UI; request explicitly to see).
DEFAULT_API_SIGNAL_TYPES: tuple[str, ...] = (
    SIGNAL_A1_STAGE_BREAKOUT,
    SIGNAL_A2_SLOPE_FLIP,
    SIGNAL_B2_MA_PULLBACK,
)

# -- Shared fetch / engine ---------------------------------------------------

# Calendar days requested from FMP per ticker. A1 needs 60 *trading* days
# of MA150 history; 90 calendar days ≈ 62 trading days with room to spare.
FETCH_WINDOW_CALENDAR_DAYS = 90

# -- Legacy F105 crossover ---------------------------------------------------

LEGACY_PCT_ABOVE_MA_LIMIT = 10.0  # %

# -- A1: Stage 1 → 2 Breakout ------------------------------------------------
# Long sideways base followed by first crossover above MA150 with volume.

A1_HORIZONTAL_WINDOW_DAYS = 60       # trading days of MA150 to check for "flat"
A1_HORIZONTAL_RANGE_PCT = 5.0        # (max - min) / min of MA150 over window ≤ this %
A1_VOLUME_RATIO_MIN = 1.5            # today volume ≥ 1.5 × 20-day avg
A1_VOLUME_AVG_WINDOW = 20            # days for the average
A1_REQUIRE_SLOPE_NONNEGATIVE = True  # slope ≥ 0 (just turned flat counts)

# -- A2: Slope Flip ----------------------------------------------------------
# MA150 slope itself recently turned positive (structural trend start).

A2_FLIP_LOOKBACK_DAYS = 30   # how many past days to look for a non-positive slope
# A2 reuses compute_slope (SLOPE_WINDOW=20) from signal_engine.

# -- B2: MA5 Pullback Bounce -------------------------------------------------
# Price already in uptrend; MA5 dipped close to MA150 then re-expanded.

B2_MA_SHORT_WINDOW = 5                 # MA5
B2_PROXIMITY_PCT = 2.0                 # recent min((MA5-MA150)/MA150) ≤ this % (absolute value)
B2_EXPANSION_DELTA_PCT = 0.5           # today's gap must be ≥ recent_min + this %
B2_LOOKBACK_DAYS = 10                  # window to scan for proximity & min

# -- Scanner execution -------------------------------------------------------

SCAN_WORKER_COUNT = 6   # threads; must not exceed FmpClient's semaphore limit
