---
status: confirmed
drafted_at: 2026-05-20
confirmed_at: 2026-05-20
sprint: F218-d5
parent_feature: F218
---

# F218-d5 Sprint Contract — T4 SECTOR_CYCLE detector 实装

> 生成：2026-05-20 | 状态：✅ 已确认（用户 NP-d5-1~10 全部按推荐 @ 2026-05-20）
> Feature：[F218](docs/需求/features.json) Cockpit Phase D — Repricing Trigger 完整框架（5 类）
> Sub-sprint：F218-d5（Phase D 10 sub-sprint 第 8 个；T4 SECTOR_CYCLE **detector 实装**，纯计算 / 无新 FMP endpoint / 无新表）
> 前置：F218-d1 done（service skeleton + 5 占位）/ F218-d2 done（T1 实装样板）/ F218-d3a/d3b done / F218-d4 done（T3 实装）
> 下游：F218-d6a（T5 数据层 — balance-sheet + cash-flow + fundamentals 表）

> 引用文档：
> - [DATA-MODEL.md](docs/系统设计/DATA-MODEL.md) §RepricingTrigger 1080–1129（evidence_json schema §1100 SECTOR_CYCLE 例 + confidence §1107 — T4 默认 0.5）
> - [ARCHITECTURE.md](docs/系统设计/ARCHITECTURE.md) §Cockpit Repricing Trigger Service（T4 复用 SECTOR_ETFS + RS percentile 算法）
> - [DECISIONS.md](docs/系统设计/DECISIONS.md) D096（5 类 detector 串行调度策略 / confidence 默认 0.5 / 不并发）
> - [F218-d4-contract.md](docs/开发/sprint-contracts/F218-d4-contract.md) — detector-only sprint 实装样板（常量段 / DetectorResult / 测试 3 class 分组）
> - [backend/app/services/cockpit/cockpit_params.py](backend/app/services/cockpit/cockpit_params.py) — SHARED.SECTOR_ETFS（11 ETF）/ MA_LONG=200
> - [backend/app/services/cockpit/pool_helpers.py](backend/app/services/cockpit/pool_helpers.py) — `compute_rs_percentile_map(ratio_by_ticker)` 模块函数（D081 算法，T4 直接复用）
> - [backend/app/models/market_index.py](backend/app/models/market_index.py) — `MarketIndex(symbol, date, close)`，UQ symbol+date；SPY + 11 sector ETF 均在 REGIME_ETF_SYMBOLS（universe_refresh_service 每日抓取，MARKET_INDEX_WINDOW=260 行）
> - [backend/app/models/market_scan_universe.py](backend/app/models/market_scan_universe.py) — `sector` String(64) 字段（FMP 原文 11 类）

---

## 0. 背景与定位

F218-d1 留下的 5 个占位中第 4 个 `_detect_sector_cycle` 现在实装。与 T1/T2/T3 不同，T4 完全是**纯计算**：
- 不读财务表（不接 FMP）
- 不读 news_cache
- 仅依赖既有 `market_index`（SPY + 11 sector ETF 每日收盘）+ `market_scan_universe`（ticker → sector 字符串）

**核心语义（DATA-MODEL §1100 + AC #5）**：

```
1. ticker → market_scan_universe.sector（FMP 原文，如 "Technology"）→ 11 sector ETF 之一（如 XLK）
2. 在两个采样日 (scan_date - 60 cal_days) 与 scan_date 上，分别计算 11 sector ETF 的 RS ratio vs SPY
3. 用 pool_helpers.compute_rs_percentile_map 跨 11 ETF 计算目标 ETF 的 percentile
4. 触发条件：start_pct < 40 AND end_pct > 60（跨升）AND etf_close > 200日 SMA
5. evidence: {"sector": "XLK", "rs_history": [{"date":..., "percentile":...} × 2], "price_vs_200d": float}
6. confidence 恒 0.5（DATA-MODEL §1107，T4 无高置信路径）
```

**架构文档对齐说明（NP-d5-3，重要）**：
ARCHITECTURE.md §564 提到 "复用 `market_regime_service._compute_rs_percentile`"。**该方法实际不存在**于 `market_regime_service.py`。等价算法位于 [`pool_helpers.compute_rs_percentile_map`](backend/app/services/cockpit/pool_helpers.py)（D081 mid-rank percentile 已在 F205 验证）。本 sprint 选择直接复用 `pool_helpers` 模块函数，**不**在 `market_regime_service` 新增重复实现 — 这是对架构文档的实施级澄清，由本 Contract 承载，不升 DXXX（与 d4 NP-d4 系列相同处理）。

**关键设计承诺**：
- ❌ 不新增 FMP endpoint / 不新建数据库表 / 不动 cron / 不动 API / 不动前端
- ❌ 不改 `market_regime_service.py` / `pool_helpers.py`（仅 import 调用）
- ❌ 不引入 sector → ETF 反向查找（detector 单向 ticker → ETF）
- ❌ 不写 service body 进入 SystemLog（DEBUG 级日志可有，不写表）

---

## 1. 实现范围

### 1.1 `cockpit_params.py` 新增 `SECTOR_TO_ETF` 映射（11 项）

**修改** `backend/app/services/cockpit/cockpit_params.py`，在 `CockpitSharedParams` 内 `SECTOR_ETFS` 字段之后追加：

```python
SECTOR_TO_ETF: dict[str, str] = Field(
    default={
        # FMP /profile.sector 原文（11 类，2026-05-20 dev DB 实测） → 11 GICS sector ETF
        "Technology": "XLK",
        "Consumer Cyclical": "XLY",
        "Financial Services": "XLF",
        "Industrials": "XLI",
        "Energy": "XLE",
        "Healthcare": "XLV",
        "Communication Services": "XLC",
        "Consumer Defensive": "XLP",
        "Utilities": "XLU",
        "Basic Materials": "XLB",
        "Real Estate": "XLRE",
    },
    description="FMP /profile.sector 字符串 → cockpit 11 GICS sector ETF symbol（T4 SECTOR_CYCLE detector 用，与 SECTOR_ETFS 一一对应）",
)
```

⚠️ 11 个 value 与 `SECTOR_ETFS` 一一对应，无遗漏无重复。

### 1.2 `repricing_trigger_service.py` 实装 `_detect_sector_cycle`

**修改** `backend/app/services/cockpit/repricing_trigger_service.py`：

**(a)** 顶部 import 段追加：
```python
from datetime import timedelta  # 既有 date/datetime/timezone，合并 import 行
from sqlalchemy import select

from app.models.market_index import MarketIndex
from app.models.market_scan_universe import MarketScanUniverse
from app.services.cockpit.cockpit_params import SHARED
from app.services.cockpit.pool_helpers import compute_rs_percentile_map
```

**(b)** 新增 T4 常量段（位置：T3 常量段之后空一行）：
```python
# T4 SECTOR_CYCLE detector 参数 — AC #5 / DATA-MODEL §1100
T4_SAMPLE_WINDOW_DAYS = 60      # start_sample = scan_date - 60 calendar days
T4_RS_LOOKBACK_DAYS = 60        # RS ratio = ETF/SPY 60 calendar-day return
T4_SMA_PERIOD = 200             # close > 200日 SMA 价格门
T4_PCT_LOW = 40.0               # start 端 percentile 上限（严格 < 40）
T4_PCT_HIGH = 60.0              # end 端 percentile 下限（严格 > 60）
T4_DEFAULT_CONFIDENCE = 0.5     # DATA-MODEL §1107: T4 无高置信路径
```

**(c)** 替换占位 `_detect_sector_cycle`（删除 `return None`），按以下伪码实装：

```python
def _detect_sector_cycle(
    self, ticker: str, scan_date: date,
) -> DetectorResult | None:
    """T4 SECTOR_CYCLE: 标的所属 sector ETF 的 RS percentile 跨升 < 40 → > 60 (60d) AND 价 > SMA200 → 触发.

    步骤：
      1. ticker → market_scan_universe.sector → SHARED.SECTOR_TO_ETF → ETF symbol
      2. 拉 SPY + 11 sector ETF 自 [scan_date - 120, scan_date] 的 market_index closes
      3. 在 start_date = scan_date - 60 / end_date = scan_date 上，
         按 60-day calendar return 算 ratio = (close_d / close_{d-60}) / (spy_close_d / spy_close_{d-60})
      4. pool_helpers.compute_rs_percentile_map 跨 11 ETF → 目标 ETF percentile
      5. 触发判定：start_pct < 40 AND end_pct > 60 AND latest_close > SMA200 (200 行简单平均)
    任何中间步骤缺数据（sector 映射 / closes 不足 / spy 缺）→ return None.
    """
    # Step 1: ticker → ETF
    sector = self._lookup_ticker_sector(ticker)
    if sector is None:
        return None
    etf = SHARED.SECTOR_TO_ETF.get(sector)
    if etf is None:
        return None

    # Step 2: fetch closes
    end_date = scan_date
    start_date = scan_date - timedelta(days=T4_SAMPLE_WINDOW_DAYS)
    earliest = start_date - timedelta(days=T4_RS_LOOKBACK_DAYS)
    symbols = ("SPY", *SHARED.SECTOR_ETFS)
    closes_by_symbol = self._fetch_market_index_closes(symbols, earliest, end_date)

    # Step 3: RS ratio per ETF at start / end
    end_ratios = self._rs_ratio_population(closes_by_symbol, end_date)
    start_ratios = self._rs_ratio_population(closes_by_symbol, start_date)
    if end_ratios is None or start_ratios is None:
        return None

    # Step 4: percentile via pool_helpers
    end_pcts = compute_rs_percentile_map(end_ratios)
    start_pcts = compute_rs_percentile_map(start_ratios)
    end_pct = end_pcts.get(etf)
    start_pct = start_pcts.get(etf)
    if end_pct is None or start_pct is None:
        return None

    # Step 5: trigger gates
    if not (start_pct < T4_PCT_LOW and end_pct > T4_PCT_HIGH):
        return None

    sma200, latest_close = self._sma_and_latest(closes_by_symbol.get(etf, []), T4_SMA_PERIOD, end_date)
    if sma200 is None or latest_close is None or latest_close <= sma200:
        return None

    return DetectorResult(
        confidence=T4_DEFAULT_CONFIDENCE,
        evidence={
            "sector": etf,
            "rs_history": [
                {"date": start_date.isoformat(), "percentile": round(start_pct, 2)},
                {"date": end_date.isoformat(),   "percentile": round(end_pct, 2)},
            ],
            "price_vs_200d": round(latest_close / sma200, 4),
        },
    )
```

**(d)** 新增 3 个私有 helper（service 内，位于 `_detector_map` 之前）：

```python
def _lookup_ticker_sector(self, ticker: str) -> str | None:
    """读 market_scan_universe.sector（FMP 原文）；未在 universe / sector NULL → None."""
    row = self.db.execute(
        select(MarketScanUniverse.sector)
        .where(MarketScanUniverse.ticker == ticker)
    ).first()
    if row is None:
        return None
    return row[0]  # 可能为 None

def _fetch_market_index_closes(
    self, symbols: tuple[str, ...], start: date, end: date,
) -> dict[str, list[tuple[date, float]]]:
    """按 symbol 聚合 market_index 行，过滤 [start, end]，按 date ASC."""
    out: dict[str, list[tuple[date, float]]] = {s: [] for s in symbols}
    rows = self.db.execute(
        select(MarketIndex.symbol, MarketIndex.date, MarketIndex.close)
        .where(MarketIndex.symbol.in_(symbols))
        .where(MarketIndex.date >= start)
        .where(MarketIndex.date <= end)
        .order_by(MarketIndex.symbol, MarketIndex.date.asc())
    ).all()
    for sym, d, c in rows:
        out[sym].append((d, c))
    return out

def _rs_ratio_population(
    self, closes_by_symbol: dict[str, list[tuple[date, float]]], at: date,
) -> dict[str, float] | None:
    """11 sector ETF 在 `at` 日的 RS ratio = ETF_return_60d / SPY_return_60d.

    任一 ETF 或 SPY 在 `at` 或 `at - lookback` 无数据 → 整体返 None
    （population 不完整时跳过 detect，避免局部缺失污染 percentile rank）.
    使用比率而非差值，与 pool_helpers.compute_return_ratio_250d 同源（D081）.
    spy_return ≈ 0 → 整体返 None（防除 0 不稳）.
    """
    lookback_at = at - timedelta(days=T4_RS_LOOKBACK_DAYS)
    spy_now = _close_on_or_before(closes_by_symbol.get("SPY", []), at)
    spy_then = _close_on_or_before(closes_by_symbol.get("SPY", []), lookback_at)
    if spy_now is None or spy_then is None or spy_then <= 0:
        return None
    spy_return = spy_now / spy_then - 1.0
    if abs(spy_return) < 0.001:
        return None  # 比例不稳

    ratios: dict[str, float] = {}
    for etf in SHARED.SECTOR_ETFS:
        c_now = _close_on_or_before(closes_by_symbol.get(etf, []), at)
        c_then = _close_on_or_before(closes_by_symbol.get(etf, []), lookback_at)
        if c_now is None or c_then is None or c_then <= 0:
            return None
        etf_return = c_now / c_then - 1.0
        ratios[etf] = etf_return / spy_return
    return ratios

def _sma_and_latest(
    self, closes_asc: list[tuple[date, float]], period: int, at: date,
) -> tuple[float | None, float | None]:
    """ETF 在 `at` 或之前的 SMA(period) 与 latest close；< period 行返 (None, None)."""
    truncated = [c for (d, c) in closes_asc if d <= at]
    if len(truncated) < period:
        return None, None
    sma = sum(truncated[-period:]) / period
    return sma, truncated[-1]
```

**(e)** 模块底部新增**模块级**辅助（与既有 `_quarter_label` / `_eval_margin_arm` 同区）：

```python
def _close_on_or_before(
    closes_asc: list[tuple[date, float]], target: date,
) -> float | None:
    """Return close on or strictly before `target` (closes_asc sorted ASC by date)."""
    candidate = None
    for d, c in closes_asc:
        if d <= target:
            candidate = c
        else:
            break
    return candidate
```

### 1.3 evidence_json schema（最终落地版）

```json
{
  "sector": "XLK",
  "rs_history": [
    {"date": "2026-03-21", "percentile": 35.5},
    {"date": "2026-05-20", "percentile": 65.2}
  ],
  "price_vs_200d": 1.08
}
```

- `sector`：ETF symbol（非 GICS 字符串），DATA-MODEL §1100 example 用 "XLK"
- `rs_history`：长度恒 2，按 date ASC（oldest first），与 DATA-MODEL §1100 example 字面对齐
- `percentile`：float，2 位小数（pool_helpers 已 round(2)）
- `price_vs_200d`：float，4 位小数（latest_close / SMA200）

### 1.4 Tests

**新建** `backend/tests/test_repricing_trigger_sector_cycle.py`，按 3 个 class 分组 10 个测试：

| Class | # | 测试简述 |
|-------|---|---------|
| `TestSectorMapping`（ticker→ETF ×2） | S1 | universe 含 ticker 且 sector="Technology" → 映射 XLK；happy 路径返触发 result |
| | S2 | ticker 不在 universe → return None；ticker 在 universe 但 sector=NULL → return None；sector="Unknown Sector" 不在 SECTOR_TO_ETF → return None |
| `TestSectorCycleDetector`（核心 ×7） | S3 | happy：seed SPY + XLK 等 11 ETF 共 ~125 日 closes，构造 XLK end_pct > 60、start_pct < 40、close > SMA200 → 触发；evidence sector="XLK"、rs_history 长 2 ASC、price_vs_200d ≈ 1.08；confidence=0.5 |
| | S4 | 跨升失败 — start_pct=42 / end_pct=70 → return None（start 未严格 < 40） |
| | S5 | 跨升失败 — start_pct=30 / end_pct=58 → return None（end 未严格 > 60） |
| | S6 | 跨升成功但价格门失败 — close ≤ SMA200 → return None |
| | S7 | 数据不足 — SPY 仅 50 行（< T4_SMA_PERIOD）→ population ratio None → return None；不抛错 |
| | S8 | ETF 缺数据 — XLE 在 start_date 或 lookback_start 无 close → `_rs_ratio_population` 返 None → return None |
| | S9 | SPY return ≈ 0（abs < 0.001）→ ratio 不稳 → return None |
| `TestSectorCycleEndToEnd`（service ×1） | S10 | `compute_and_store_all_triggers` 端到端：seed 1 active Stock + universe row + 完整 ETF closes → repricing_triggers 写 1 行 trigger_type=SECTOR_CYCLE + active=True + evidence_json 三键齐全；再调用 ETF closes 不变（仍触发）→ upsert 同行 active=True（幂等）；最后破坏 closes（删 SMA200 行）→ soft expire active=False |

**Helper（test 文件局部）**：
- `_seed_market_index(db, symbol, dates_closes)` — 批量 INSERT MarketIndex 行
- `_seed_universe(db, ticker, sector)` — INSERT 1 行 MarketScanUniverse（last_seen_at=now）
- `_build_etf_series(target_etf, start_pct, end_pct, ...)` — 构造命中 / 不命中 close 序列的工厂
- 复用 d1/d2/d4 既有 `_stock` helper

**conftest fixture**：复用既有 `db_session`（sqlite in-memory）。

---

## 2. 预计修改文件

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/services/cockpit/cockpit_params.py` | 修改 | `CockpitSharedParams` 新增 `SECTOR_TO_ETF: dict[str, str]` 字段（11 项），其余字段不动 |
| 2 | `backend/app/services/cockpit/repricing_trigger_service.py` | 修改 | +imports (timedelta / select / MarketIndex / MarketScanUniverse / SHARED / compute_rs_percentile_map) / +T4 常量段 6 行 / 替换 `_detect_sector_cycle` 实装（~50 行）/ +3 service 内 helper / +1 模块级 helper `_close_on_or_before` |
| 3 | `backend/tests/test_repricing_trigger_sector_cycle.py` | 新建 | 10 测试 / 3 class（≈ 350 行含 helper） |

**实际 3 文件**，远低于 6 文件上限（与 d4 一致）。

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | ticker→ETF happy：universe.sector="Technology" → SECTOR_TO_ETF["Technology"]="XLK"；detector 后续步骤继续 | 单元 | pytest |
| 2 | ticker→ETF fail-path：ticker 不在 universe / sector=NULL / sector="X-未知" → return None；无异常 | 单元 | pytest |
| 3 | RS ratio population 计算：SPY + 11 ETF 在 `at` 与 `at - 60` 有齐 close → 返长度 11 的 dict；任一缺 → return None | 单元（嵌 S3+S8） | pytest |
| 4 | SPY return ≈ 0：spy_now / spy_then - 1 绝对值 < 0.001 → `_rs_ratio_population` return None | 单元 | pytest |
| 5 | percentile 跨升 happy：start_pct < 40 AND end_pct > 60 AND close > SMA200 → 触发；rs_history 长 2 ASC | 单元 | pytest |
| 6 | percentile 跨升失败（start 端）：start_pct ≥ 40 → return None | 单元 | pytest |
| 7 | percentile 跨升失败（end 端）：end_pct ≤ 60 → return None | 单元 | pytest |
| 8 | 价格门失败：latest_close ≤ SMA200 → return None | 单元 | pytest |
| 9 | 数据不足：ETF closes 不足 SMA200 周期 → return None；不抛 ZeroDivisionError / IndexError | 单元 | pytest |
| 10 | evidence_json 三键完备 + 类型：sector(str) / rs_history(list[dict] len=2) / price_vs_200d(float)；与 DATA-MODEL.md §1100 example schema 1:1 对齐 | 单元（嵌 S3 断言） | pytest |
| 11 | confidence = 0.5 恒值（与 DATA-MODEL §1107 对齐） | 单元（嵌 S3 断言） | pytest |
| 12 | `compute_and_store_all_triggers` 端到端：写 1 行 SECTOR_CYCLE + active=True；幂等 upsert；soft expire 翻 false | 集成 | pytest |

预期测试数：**10 个**（S3/S10 内含 #3/#10/#11 子断言）。单文件 `test_repricing_trigger_sector_cycle.py`。

---

## 4. Evaluator 自检清单

### 功能 + schema
- [ ] 10 个新测试全部通过（`cd backend && uv run pytest tests/test_repricing_trigger_sector_cycle.py -v`）
- [ ] `_detect_sector_cycle` 签名不变：`(self, ticker: str, scan_date: date) -> DetectorResult | None`
- [ ] evidence_json 三键齐全（sector / rs_history / price_vs_200d）；rs_history 长 2、ASC、键 `date`+`percentile` 对齐 DATA-MODEL §1100
- [ ] confidence 恒 0.5；不引入未文档化的高置信路径
- [ ] T4 detector fail-out（return None）而非 raise；任一中间 None 不导致 KeyError / AttributeError / ZeroDivisionError

### 数据访问 + 边界
- [ ] `_fetch_market_index_closes` 仅查 MarketIndex；不写表；不调 SystemLog；不 commit
- [ ] `_lookup_ticker_sector` 仅查 MarketScanUniverse；不引入 last_seen_at 过滤（universe 行是否"过期"由 universe_refresh_service 管理）
- [ ] `_close_on_or_before` 在 `closes_asc` ASC 排序假设下正确；空列表 → None
- [ ] SHARED.SECTOR_TO_ETF 11 项 value 全部出现在 SHARED.SECTOR_ETFS 中（双向对齐）

### 回归
- [ ] d1/d2/d3a/d3b/d4 既有测试全绿（`uv run pytest tests/test_repricing_trigger_skeleton.py tests/test_repricing_trigger_earnings_accel.py tests/test_f218_d3a_key_metrics.py tests/test_repricing_trigger_margin_expansion.py tests/test_repricing_trigger_new_product.py -v`）
- [ ] 全量后端 `uv run pytest`：允许 d4 baseline 9 个 pre-existing failures，**不得**新增
- [ ] cockpit/setup/regime/pool_cache/repricing_trigger 既有 import 无破坏（新增 `from app.services.cockpit.pool_helpers import compute_rs_percentile_map` 不影响既有用户）
- [ ] `compute_and_store_all_triggers` 内 T4 串行位置（第 4 个）与 d1 skeleton 一致；T5 仍占位返 None

### 代码质量
- [ ] `_detect_sector_cycle` 函数长度 ≤ 60 行（含 docstring；3 step 调度）
- [ ] 3 个 service helper 各自 ≤ 30 行
- [ ] 无硬编码魔法值（40/60/200/0.5/60-day 全部抽 T4_* 常量）
- [ ] 无注释掉的代码 / 死 import / 未使用变量
- [ ] cockpit_params.py 既有 11 个 CockpitXxxParams 类全部不动，仅在 CockpitSharedParams 内追加 1 字段

---

## 5. 关键设计决策（执行前确认）

| # | 议题 | 推荐方案 | 备选方案 |
|---|------|---------|---------|
| **NP-d5-1** | RS ratio 公式 | **A：60-day calendar 收益比，ratio = etf_return / spy_return（推荐）**。与 `pool_helpers.compute_return_ratio_250d` 同思路（return / return），保留 D081 算法形态；60 日时间尺度与 "past 60 days" 采样窗自然对齐；spy_return≈0 → return None 防除零。 | (a) **B：return 差值 etf_return - spy_return** — 简单但失去比例信息，与既有 pool RS 算法不同源 / (b) **C：250-day return ratio（pool_helpers.compute_return_ratio_250d 直接复用）** — 时间尺度过长（4 倍于采样窗），慢反应不适配 "60 日反转" 信号 / (c) **D：close/MA50（market_regime_service 风格）** — 瞬时值无 RS 动量，与 SRS § 十一 "RS 从低位升至高位" 含义不符 |
| **NP-d5-2** | 采样点数 | **A：2 点（start = scan_date - 60d, end = scan_date）（推荐）**。与 DATA-MODEL.md §1100 example "rs_history" 字面 2 项一致；判定门 `start<40 AND end>60` 严格语义清晰；evidence JSON 体积可控。 | (a) **B：N=5 点均匀采样** — evidence 体积膨胀且 DATA-MODEL example 仅 2 项，破坏 1:1 schema / (b) **C：滚动检测最大跨升** — 算法复杂度上升，假阳率反而升（任意 60 日窗都可能命中） |
| **NP-d5-3** | RS percentile 算法来源 | **A：`pool_helpers.compute_rs_percentile_map`（推荐）**。该函数为模块级纯函数（D081 mid-rank percentile），已在 F205 pool funnel 验证；ARCHITECTURE.md 提及 `market_regime_service._compute_rs_percentile` 实际不存在 — 由本 Contract 澄清。 | (a) **B：在 `market_regime_service` 新加 `_compute_rs_percentile`** — 重复实现 D081 算法、违反 DRY、扩大 sprint 范围 / (b) **C：内联在 service** — 与 pool_helpers 同算法的 4 行抄写，徒增维护负担 |
| **NP-d5-4** | ticker → sector 数据源 | **A：`market_scan_universe.sector`（FMP /profile 原文）（推荐）**。表存在、字段已有、universe_refresh_service 已在维护；2026-05-20 dev DB 实测 11 个唯一值与 SHARED.SECTOR_ETFS 11 个 ETF 完全对齐。 | (a) **B：在 `stocks` 表加 sector 列** — 引 alembic 023 + 回填，违反 6 文件上限 / (b) **C：硬编码 ticker → sector map** — 维护成本高，新 ticker 漏映射 / (d) **D：FMP 实时 `/profile` 调用** — 引入 detect 期 FMP 调用，违反 D096 "T4 不接 FMP" |
| **NP-d5-5** | SECTOR_TO_ETF 映射位置 | **A：`CockpitSharedParams.SECTOR_TO_ETF`（推荐）**。与既有 `SECTOR_ETFS` 字段同居所，Pydantic v2 frozen model 保证不可变；其他 service（未来）也可复用此映射。 | (a) **B：repricing_trigger_service.py 模块级 dict** — 复用受限 / (b) **C：单独文件 `sector_mapping.py`** — 单 dict 拆文件过度工程 |
| **NP-d5-6** | sector 字符串大小写 | **A：严格大小写（推荐）**。FMP `/profile.sector` 输出固定 Title Case（"Technology" 非 "TECHNOLOGY"），实测 11 项无大小写变体；保持严格匹配避免引入大小写归一化逻辑。 | (a) **B：lower 归一化** — 引入 SECTOR_TO_ETF_NORMALIZED 派生 dict，徒增逻辑 / (b) **C：模糊匹配（startswith 等）** — 假阳风险（"Consumer" 同时匹配 Cyclical/Defensive） |
| **NP-d5-7** | universe 行"过期"处理 | **A：直接查任何 MarketScanUniverse 行（推荐）**。不加 last_seen_at 过滤；universe 行掉出 universe 后 sector 字符串不变（仍可信）；detector 是写场景的下游，universe 维护由 universe_refresh_service 管理。 | (a) **B：last_seen_at >= scan_date - N** — universe rebuild 失效时整批 ticker 失映射，引入级联故障 |
| **NP-d5-8** | population 缺失时的策略 | **A：任一 ETF 或 SPY 在采样日缺数据 → 整体 return None（推荐）**。percentile rank 依赖完整 11 ETF population；局部缺失会让 mid-rank 系统性失真（D081 算法假设）；fail-fast 避免污染 evidence。 | (a) **B：缺失 ETF 跳过，对剩余 N 个 rank** — 改变 percentile 语义（10/N 不同于 11/N），引入 P40/P60 阈值漂移 / (b) **C：缺失 ETF 用 -inf 填充（pool_helpers 内置）** — 在 SECTOR_CYCLE 语义下会让缺数据 ETF 压到 P0，扭曲目标 ETF rank |
| **NP-d5-9** | SMA200 起点 | **A：以 `end_date = scan_date` 为终点取最后 200 行（推荐）**。与既有 `market_regime_service._ma(closes, period)` 同语义（rolling SMA）；不要求 200 个独立 calendar 日，而是 200 个有效 close 行（≈ 280 calendar days，MARKET_INDEX_WINDOW=260 略紧但 universe_refresh_service 持续刷新 → 260 行通常已 ≥ 200）。 | (a) **B：SMA200 by exact 200 calendar days back** — sqlite 行级断点引入复杂度 / (b) **C：EMA200** — 与 DATA-MODEL "200 日 SMA" 字面不符 |
| **NP-d5-10** | rs_history `date` 格式 | **A：ISO 字符串 "YYYY-MM-DD"（推荐）**。与 DATA-MODEL §1100 example "2026-03-01" 字面一致；JSON 友好；前端无需 reparse；evidence_json 保持 stringly-typed。 | (a) **B：Python date 对象 + json default=str** — 看似同效但 default=str 在 service 层 `json.dumps` 链路上脆弱 |

### 推荐理由速览

- **NP-d5-1 60d return ratio**：与 60d 采样窗时间尺度对齐；保留比例信息（不是差值），与 pool_helpers 同源算法形态。spy_return≈0 fail-safe 避免除零不稳。
- **NP-d5-3 pool_helpers 直接复用**：ARCHITECTURE.md `market_regime_service._compute_rs_percentile` 不存在；pool_helpers.compute_rs_percentile_map 已在 D081 验证；本 sprint 不重复造轮子。
- **NP-d5-4 market_scan_universe**：2026-05-20 dev DB 实测 sector 字段已含 11 项完整 GICS，universe_refresh_service 每日抓取；ticker 命中率 = pool overlap，足够。
- **NP-d5-8 fail-fast on partial population**：percentile mid-rank 算法假设完整 N；局部缺失会让 P40/P60 阈值跨升判定漂移，假阳/假阴概率上升；fail-safe 优于 silent bias。

---

## 6. 不在范围（本 sprint 排除）

- ❌ T5 BALANCE_INFLECTION detector 实装（F218-d6b）
- ❌ T5 数据层：balance-sheet + cash-flow + stock_fundamentals_quarterly 表 + FMP 接入（F218-d6a）
- ❌ refresh_job.py cron 注册（F218-d7a — 22:40 UTC RepricingTriggerService 调度）
- ❌ router + 2 endpoint `/api/cockpit/repricing-triggers*`（F218-d7a）
- ❌ 前端 widget + DecisionPanel chip 区 + design-spec 4 文档（F218-d7b）
- ❌ 在 `market_regime_service.py` 新增 `_compute_rs_percentile`（NP-d5-3 已澄清 — 复用 pool_helpers）
- ❌ ticker → sector 缓存（每次 detect 直查 universe；ticker 量 < 100、单 detect << 1ms，无性能压力）
- ❌ ARCHITECTURE.md / DATA-MODEL.md / API-CONTRACT.md / DECISIONS.md 修改（本 sprint 严格无新 drift；ARCHITECTURE 内 `_compute_rs_percentile` 提法属预想性偏差，由 Contract 承载澄清，不升 DXXX）
- ❌ SECTOR_TO_ETF 反向查找 / 多 ETF per sector（每 GICS 1:1 mapping，未来 niche ETF 如 SOXX/SMH 不在本 sprint）
- ❌ T4 触发后对 setup / decision / position 等下游消费（d7a/d7b 阶段处理）
- ❌ 历史回测（NVDA / TSLA / META sector rotation 案例验证 — acceptance / d7b 收官统一做）
- ❌ DECISIONS.md 追加（D096 已覆盖 5 类 detector 框架；NP-d5-1~10 是实施级决策，由本 Contract 承载，不升 DXXX）

---

## 7. 用户待确认

1. **NP-d5-1 ~ NP-d5-10** 十项决策：全部按推荐？还是有需要调整的？重点关注：
   - **NP-d5-1**（RS 公式 = 60d return ratio）— 决定触发频率与对 sector 旋转的敏感度
   - **NP-d5-3**（直接复用 `pool_helpers.compute_rs_percentile_map`，澄清 ARCHITECTURE 提法）— 决定是否需要在 `market_regime_service` 加重复实现
   - **NP-d5-4**（ticker→sector 走 `market_scan_universe`）— 决定本 sprint 是否触发新表/新列改动
   - **NP-d5-8**（population 缺失 → 整体 None）— 决定 false negative 在数据稀疏期的处理方式
2. **evidence_json schema**（§1.3 最终落地版）是否同意？尤其 `rs_history` 长 2、ASC、`date` 为 ISO 字符串。
3. **Contract 整体是否同意进入 Generator 模式开发？**

确认后我会：
1. 更新 features.json：`F218-d5` sub_sprints state `design_needed` → `contract_agreed`；`_pipeline_status.active_sprint_phase` → `contract_agreed`
2. 追加 F218 iteration_history 一条 `contract_agreed` 记录（subtask=F218-d5，date=2026-05-20）
3. 更新 claude-progress.txt
4. 更新本 Contract frontmatter `status: drafted → confirmed`，新增 `confirmed_at`
5. 生成 SESSION-HANDOFF.md（含 d5 3 步开发顺序：cockpit_params.SECTOR_TO_ETF → service T4 实装 + helpers → 10 测试）
6. **强制停止本 session**（feature-dev skill 铁律），输出新 session 恢复指令
