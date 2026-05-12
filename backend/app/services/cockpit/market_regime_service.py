from __future__ import annotations

import json
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market_index import MarketIndex
from app.models.market_regime_snapshot import MarketRegimeSnapshot
from app.models.system_log import SystemLog
from app.repositories.market_regime_repository import MarketRegimeRepository
from app.services.cockpit.cockpit_params import REGIME, SHARED


class MarketRegimeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._repo = MarketRegimeRepository(db)

    # ── Public API ────────────────────────────────────────────────────────────

    def compute_and_store(self, today: date | None = None) -> MarketRegimeSnapshot:
        """Compute market regime score from market_indices and upsert a snapshot.

        When a symbol has insufficient history the corresponding sub-score is 0.
        Writes a SystemLog WARN for each such symbol.
        """
        today = today or date.today()
        all_data = self._fetch_all_symbol_data()

        spy = all_data.get("SPY", {})
        qqq = all_data.get("QQQ", {})
        iwm = all_data.get("IWM", {})
        sector_data = {s: all_data.get(s, {}) for s in SHARED.SECTOR_ETFS}

        count_above = self._count_sectors_above_ma_short(sector_data)
        spy_score = self._spy_trend_score(spy)
        qqq_score = self._qqq_trend_score(qqq)
        iwm_score = self._iwm_breadth_score(iwm, spy)
        sector_score = self._sector_participation_score(count_above)
        risk_score = self._risk_appetite_score(sector_data)
        vol_score = self._volatility_stress_score(spy, count_above)

        market_score = spy_score + qqq_score + iwm_score + sector_score + risk_score + vol_score
        regime = self._classify_regime(market_score)

        return self._repo.upsert({
            "date": today,
            "regime": regime,
            "market_score": market_score,
            "spy_trend_score": spy_score,
            "qqq_trend_score": qqq_score,
            "iwm_breadth_score": iwm_score,
            "sector_participation_score": sector_score,
            "risk_appetite_score": risk_score,
            "volatility_stress_score": vol_score,
            "allowed_exposure_pct": REGIME.ALLOWED_EXPOSURE_PCT[regime],
            "single_trade_risk_pct": REGIME.SINGLE_TRADE_RISK_PCT[regime],
            "preferred_setups": json.dumps(REGIME.PREFERRED_SETUPS[regime]),
            "avoid_setups": json.dumps(REGIME.AVOID_SETUPS[regime]),
            "computed_at": datetime.now(timezone.utc),
        })

    def get_indices_and_sectors_state(self) -> tuple[list[dict], list[dict]]:
        """Return (indices, sectors) state dicts for the cockpit GET endpoint.

        indices keys: symbol, close, changePct, aboveMa50, aboveMa200, rsTrend, state
        sectors keys: symbol, close, changePct, state
        """
        all_data = self._fetch_all_symbol_data()
        spy = all_data.get("SPY", {})
        spy_ma_short = self._ma(spy.get("closes", []), SHARED.MA_SHORT)
        spy_ratio = (spy["close"] / spy_ma_short) if spy.get("close") and spy_ma_short else None

        indices = []
        for sym in SHARED.INDEX_ETFS:
            d = all_data.get(sym, {})
            close = d.get("close")
            ma_short = self._ma(d.get("closes", []), SHARED.MA_SHORT)
            ma_long = self._ma(d.get("closes", []), SHARED.MA_LONG)
            above_ma50 = bool(close and ma_short and close > ma_short)
            above_ma200 = bool(close and ma_long and close > ma_long)
            golden_cross = bool(ma_short and ma_long and ma_short > ma_long)
            if sym == "SPY":
                rs_trend = "up"
            else:
                ratio = (close / ma_short) if close and ma_short else None
                rs_trend = "up" if (ratio and spy_ratio and ratio > spy_ratio) else "down"
            indices.append({
                "symbol": sym,
                "close": close,
                "changePct": d.get("change_pct"),
                "aboveMa50": above_ma50,
                "aboveMa200": above_ma200,
                "rsTrend": rs_trend,
                "state": self._index_state(above_ma50, above_ma200, golden_cross, rs_trend, sym),
            })

        sectors = []
        for sym in SHARED.SECTOR_ETFS:
            d = all_data.get(sym, {})
            close = d.get("close")
            ma_short = self._ma(d.get("closes", []), SHARED.MA_SHORT)
            ratio = (close / ma_short) if close and ma_short else None
            sectors.append({
                "symbol": sym,
                "close": close,
                "changePct": d.get("change_pct"),
                "state": self._sector_state(ratio),
            })

        return indices, sectors

    # ── Private helpers ───────────────────────────────────────────────────────

    def _fetch_all_symbol_data(self) -> dict[str, dict]:
        all_symbols = [*SHARED.INDEX_ETFS, *SHARED.SECTOR_ETFS]
        return {sym: self._fetch_symbol_data(sym) for sym in all_symbols}

    def _fetch_symbol_data(self, symbol: str) -> dict:
        rows = (
            self.db.execute(
                select(MarketIndex)
                .where(MarketIndex.symbol == symbol)
                .order_by(MarketIndex.date.desc())
                .limit(SHARED.REGIME_LOOKBACK_DAYS)
            )
            .scalars()
            .all()
        )
        if not rows:
            return {"closes": [], "close": None, "prev_close": None, "change_pct": None}
        latest = rows[0]
        closes = [r.close for r in reversed(rows)]
        return {
            "closes": closes,
            "close": latest.close,
            "prev_close": latest.prev_close,
            "change_pct": latest.change_pct,
        }

    @staticmethod
    def _ma(closes: list[float], period: int) -> float | None:
        if len(closes) < period:
            return None
        window = closes[-period:]
        return sum(window) / len(window)

    def _spy_trend_score(self, spy: dict) -> int:
        closes = spy.get("closes", [])
        close = spy.get("close")
        if close is None or len(closes) < SHARED.MA_SHORT:
            self._log_warn("SPY", "spy_trend_score", len(closes))
            return 0
        ma_short = self._ma(closes, SHARED.MA_SHORT)
        ma_long = self._ma(closes, SHARED.MA_LONG)
        score = 0
        if ma_short and close > ma_short:
            score += REGIME.SPY_ABOVE_MA_SHORT_PTS
        if ma_long and close > ma_long:
            score += REGIME.SPY_ABOVE_MA_LONG_PTS
        if ma_short and ma_long and ma_short > ma_long:
            score += REGIME.SPY_GOLDEN_CROSS_PTS
        return score

    def _qqq_trend_score(self, qqq: dict) -> int:
        closes = qqq.get("closes", [])
        close = qqq.get("close")
        if close is None or len(closes) < SHARED.MA_SHORT:
            self._log_warn("QQQ", "qqq_trend_score", len(closes))
            return 0
        ma_short = self._ma(closes, SHARED.MA_SHORT)
        ma_long = self._ma(closes, SHARED.MA_LONG)
        score = 0
        if ma_short and close > ma_short:
            score += REGIME.QQQ_ABOVE_MA_SHORT_PTS
        if ma_long and close > ma_long:
            score += REGIME.QQQ_ABOVE_MA_LONG_PTS
        if ma_short and ma_long and ma_short > ma_long:
            score += REGIME.QQQ_GOLDEN_CROSS_PTS
        return score

    def _iwm_breadth_score(self, iwm: dict, spy: dict) -> int:
        closes = iwm.get("closes", [])
        close = iwm.get("close")
        if close is None or len(closes) < SHARED.MA_SHORT:
            self._log_warn("IWM", "iwm_breadth_score", len(closes))
            return 0
        ma_short = self._ma(closes, SHARED.MA_SHORT)
        ma_long = self._ma(closes, SHARED.MA_LONG)
        spy_ma_short = self._ma(spy.get("closes", []), SHARED.MA_SHORT)
        spy_close = spy.get("close")
        score = 0
        if ma_short and close > ma_short:
            score += REGIME.IWM_ABOVE_MA_SHORT_PTS
        if ma_long and close > ma_long:
            score += REGIME.IWM_ABOVE_MA_LONG_PTS
        if ma_short and spy_ma_short and spy_close:
            if (close / ma_short) > (spy_close / spy_ma_short):
                score += REGIME.IWM_RS_POSITIVE_PTS
        return score

    def _count_sectors_above_ma_short(self, sector_data: dict) -> int:
        count = 0
        for sym in SHARED.SECTOR_ETFS:
            d = sector_data.get(sym, {})
            close = d.get("close")
            ma_short = self._ma(d.get("closes", []), SHARED.MA_SHORT)
            if close and ma_short and close > ma_short:
                count += 1
        return count

    def _sector_participation_score(self, count_above: int) -> int:
        return int(round(count_above / len(SHARED.SECTOR_ETFS) * 20))

    def _risk_appetite_score(self, sector_data: dict) -> int:
        score = 0
        xly = sector_data.get("XLY", {})
        xlk = sector_data.get("XLK", {})
        xly_close = xly.get("close")
        xly_ma_short = self._ma(xly.get("closes", []), SHARED.MA_SHORT)
        xlk_close = xlk.get("close")
        xlk_ma_short = self._ma(xlk.get("closes", []), SHARED.MA_SHORT)
        if xly_close and xly_ma_short and xly_close > xly_ma_short:
            score += REGIME.XLY_ABOVE_MA_SHORT_PTS
        if xlk_close and xlk_ma_short and xlk_close > xlk_ma_short:
            score += REGIME.XLK_ABOVE_MA_SHORT_PTS
        return score

    def _volatility_stress_score(self, spy: dict, count_above: int) -> int:
        score = 0
        closes = spy.get("closes", [])
        close = spy.get("close")
        if close and len(closes) > SHARED.RS_LOOKBACK_DAYS:
            base = closes[-SHARED.RS_LOOKBACK_DAYS - 1]
            spy_return_pct = (close - base) / base * 100 if base else 0.0
            if spy_return_pct > REGIME.SPY_RETURN_MIN_PCT:
                score += REGIME.SPY_RETURN_PTS
        if count_above >= REGIME.SECTOR_BREADTH_MIN:
            score += REGIME.BREADTH_STRESS_PTS
        return score

    @staticmethod
    def _classify_regime(score: int) -> str:
        if score >= REGIME.RISK_ON_MIN:
            return "RISK_ON"
        if score >= REGIME.CONSTRUCTIVE_MIN:
            return "CONSTRUCTIVE"
        if score >= REGIME.NEUTRAL_MIN:
            return "NEUTRAL"
        if score >= REGIME.DEFENSIVE_MIN:
            return "DEFENSIVE"
        return "RISK_OFF"

    @staticmethod
    def _index_state(above_ma50: bool, above_ma200: bool, golden_cross: bool, rs_trend: str, symbol: str) -> str:
        if above_ma200 and above_ma50 and golden_cross and rs_trend == "up" and symbol != "SPY":
            return "Leading"
        if above_ma200 and above_ma50 and golden_cross:
            return "Bullish"
        if above_ma200 and above_ma50:
            return "Constructive"
        if above_ma200 and not above_ma50:
            return "Neutral"
        if not above_ma200 and above_ma50:
            return "Weak"
        return "Defensive"

    @staticmethod
    def _sector_state(ratio: float | None) -> str:
        if ratio is None:
            return "Neutral"
        if ratio >= REGIME.SECTOR_STRONG_RATIO:
            return "Strong"
        if ratio >= REGIME.SECTOR_NEUTRAL_RATIO:
            return "Constructive"
        if ratio >= REGIME.SECTOR_WEAK_RATIO:
            return "Weak"
        return "Defensive"

    def _log_warn(self, symbol: str, subscore: str, bars: int) -> None:
        msg = f"{symbol} insufficient data for {subscore}: {bars} bars < {SHARED.MA_SHORT} required"
        self.db.add(SystemLog(level="WARN", source="MarketRegimeService", message=msg))
        self.db.commit()
