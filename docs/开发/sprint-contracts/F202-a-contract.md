# Sprint Contract：F202-a — Setup Monitor 数据层

> 状态：草案 | 起草：2026-04-25
> 父 Feature：F202 Setup Monitor Widget
> 兄弟：F202-b（cron + schema + router，独立 Sprint）；F202-c（前端 Widget，独立 Sprint）
> 引用文档：
>   - DATA-MODEL.md §Entity: SetupSnapshot（字段权威）
>   - API-CONTRACT.md §GET /api/cockpit/setup-monitor（接口权威，F202-b 实现）
>   - DECISIONS.md D062（setup_snapshots 独立表）
>   - DECISIONS.md D070（cockpit_params.py 约定；**本 Sprint 追加 §2 CockpitSetupParams**）

---

## 0. 背景与定位

F202 Setup Monitor Widget 总文件约 20 个，拆分为：

- **F202-a（本 Sprint，7 生产文件）**：数据层 — Alembic 建表 + ORM Model + Repository + `cockpit_params.py §2` + `SetupService` 核心计算
- **F202-b（后续 Sprint，6 文件）**：接入层 — `config.py` cron 参数 + `refresh_job.py` cron tick + Pydantic Schema + FastAPI Router + `routers/cockpit/__init__.py` 注册
- **F202-c（后续 Sprint，6 文件）**：前端 Widget — 3 共享子组件（SetupTypeBadge / SetupQualityBadge / EarningsRiskDot）+ SetupMonitorWidget + API client + CockpitRegistry 注册

F202-a 完成后，`SetupService.compute_and_store_all()` 可通过手动调用（测试）计算全 watchlist 快照；F202-b 之前不挂 cron、不暴露 HTTP endpoint。

---

## 1. 实现范围

### 1.1 Alembic 迁移

新文件 `backend/alembic/versions/010_f202a_setup_snapshots.py`：

```sql
CREATE TABLE setup_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      VARCHAR(10) NOT NULL,
    scan_date   DATE NOT NULL,
    setup_type  VARCHAR(24) NOT NULL,
    setup_quality VARCHAR(1),
    entry_price FLOAT,
    stop_price  FLOAT,
    target_2r   FLOAT,
    target_3r   FLOAT,
    distance_to_entry_pct FLOAT,
    reward_risk FLOAT,
    rs_percentile FLOAT,
    volume_status VARCHAR(8),
    trend_score INTEGER,
    earnings_risk VARCHAR(8) NOT NULL,
    ready_signal  BOOLEAN NOT NULL,
    suggested_action VARCHAR(16),
    scanned_at  DATETIME NOT NULL,
    UNIQUE (ticker, scan_date)            -- uq_setup_snapshot_ticker_date
);
CREATE INDEX ix_setup_snapshots_scan_date ON setup_snapshots(scan_date);
CREATE INDEX ix_setup_snapshots_ticker    ON setup_snapshots(ticker);
```

upgrade / downgrade 均实现。

### 1.2 SQLAlchemy ORM

新文件 `backend/app/models/setup_snapshot.py`：

- 严格照搬 DATA-MODEL.md §SetupSnapshot 字段
- `UniqueConstraint("ticker", "scan_date", name="uq_setup_snapshot_ticker_date")`
- `scanned_at` 默认 `lambda: datetime.now(timezone.utc)`
- 不设外键（与 `market_breakout_scans` 一致，D062 约定）

修改 `backend/app/models/__init__.py`：

- 新增 `from app.models.setup_snapshot import SetupSnapshot`
- `__all__` 追加 `"SetupSnapshot"`

### 1.3 SetupSnapshotRepository

新文件 `backend/app/repositories/setup_snapshot_repository.py`：

```python
class SetupSnapshotRepository:
    def __init__(self, db: Session): ...

    def upsert_batch(self, rows: list[dict]) -> int:
        """
        批量 INSERT OR REPLACE (ticker, scan_date) 唯一约束。
        rows 每项 key 与 ORM 字段名一一对应（snake_case）。
        返回 upserted 行数。
        """

    def get_latest_for_tickers(self, tickers: list[str]) -> list[SetupSnapshot]:
        """
        对 tickers 列表中每个 ticker，返回 scan_date 最大的一行。
        ticker 无快照时跳过（不报错）。
        结果按 suggested_action 优先级排序
        （enter > watch > wait > null > reduce > exit > None）。
        """

    def get_latest_all_active(self, active_tickers: list[str]) -> list[SetupSnapshot]:
        """
        等价于 get_latest_for_tickers(active_tickers)，
        供 get_setup_monitor_data 直接调用。
        """

    def delete_before(self, cutoff: date) -> int:
        """
        删除 scan_date < cutoff 的行（60 天 retention 窗口）。
        返回删除行数。
        """
```

### 1.4 cockpit_params.py — 追加 §2 CockpitSetupParams

修改 `backend/app/services/cockpit/cockpit_params.py`，追加：

```python
class CockpitSetupParams(BaseModel):
    """§2 SETUP — setup type classification, quality thresholds, Ready signal gates."""

    model_config = ConfigDict(frozen=True)

    # ── MA 周期（trend_score 5 阶梯）────────────────────────────────────────
    MA_PERIODS: list[int] = Field(
        default=[10, 21, 50, 150, 200],
        description="5 MA periods for trend_score ladder: close>MA10>MA21>MA50>MA150>MA200",
    )

    # ── 成交量状态阈值（vs 20 日均量）──────────────────────────────────────
    VOLUME_MA_PERIOD: int = Field(default=20, description="Rolling period for volume average", ge=5, le=50)
    VOLUME_HIGH_RATIO: float = Field(default=1.2, description="last_volume/avg > this → HIGH", ge=1.0, le=3.0)
    VOLUME_LOW_RATIO: float = Field(default=0.8, description="last_volume/avg < this → LOW", ge=0.1, le=1.0)

    # ── Setup 分类阈值 ────────────────────────────────────────────────────
    EXTENDED_MA50_PCT: float = Field(
        default=15.0,
        description="close > MA50*(1 + this/100) → EXTENDED",
        ge=5.0, le=50.0,
    )
    BREAKOUT_ZONE_PCT: float = Field(
        default=5.0,
        description="close within this% below 20d-high → BREAKOUT zone",
        ge=0.5, le=10.0,
    )
    PULLBACK_ZONE_ABOVE_MA50_PCT: float = Field(
        default=3.0,
        description="close <= MA50*(1+this/100) → still in pullback zone (not extended)",
        ge=0.5, le=10.0,
    )
    RECLAIM_LOOKBACK_BARS: int = Field(
        default=10,
        description="Look back N bars to find a close < MA50; if found and current close > MA50 → RECLAIM",
        ge=2, le=30,
    )
    EARNINGS_DRIFT_MAX_DAYS: int = Field(
        default=7,
        description="Earnings in past N days + price above MA21 → EARNINGS_DRIFT",
        ge=1, le=21,
    )

    # ── Setup quality 阈值 ────────────────────────────────────────────────
    QUALITY_A_TREND_MIN: int = Field(default=4, description="Min trend_score for quality A", ge=1, le=5)
    QUALITY_A_RS_MIN: float = Field(default=75.0, description="Min rs_percentile for quality A", ge=1.0, le=100.0)
    QUALITY_B_TREND_MIN: int = Field(default=3, description="Min trend_score for quality B", ge=1, le=5)
    QUALITY_B_RS_MIN: float = Field(default=60.0, description="Min rs_percentile for quality B", ge=1.0, le=100.0)
    QUALITY_C_TREND_MIN: int = Field(default=2, description="Min trend_score for quality C", ge=1, le=5)
    QUALITY_C_RS_MIN: float = Field(default=45.0, description="Min rs_percentile for quality C", ge=1.0, le=100.0)

    # ── RS percentile 计算 ────────────────────────────────────────────────
    RS_LOOKBACK_DAYS: int = Field(
        default=252,
        description="Days of history used for RS return calculation (stock and SPY)",
        ge=20, le=500,
    )
    RS_SPY_FALLBACK_PCT: float = Field(
        default=50.0,
        description="rs_percentile fallback when SPY data unavailable or single-stock watchlist",
        ge=0.0, le=100.0,
    )

    # ── Ready signal 7 条 AND 门 ──────────────────────────────────────────
    READY_TREND_MIN: int = Field(default=4, description="Min trend_score for readySignal", ge=1, le=5)
    READY_RS_MIN: float = Field(default=70.0, description="Min rs_percentile for readySignal", ge=1.0, le=100.0)
    READY_QUALITY_MIN: str = Field(
        default="B",
        description="Min quality for readySignal ('B' means A or B; 'A' means A only; 'C' means any)",
    )
    READY_DIST_MAX_PCT: float = Field(default=3.0, description="Max distanceToEntryPct for readySignal (%)", ge=0.1, le=10.0)
    READY_REWARD_RISK_MIN: float = Field(default=2.0, description="Min rewardRisk for readySignal", ge=1.0, le=10.0)

    # ── Earnings risk 阈值 ────────────────────────────────────────────────
    EARNINGS_DANGER_DAYS: int = Field(default=3, description="Days to next earnings ≤ this → DANGER", ge=1, le=14)
    EARNINGS_CAUTION_DAYS: int = Field(default=10, description="Days to next earnings ≤ this (> DANGER_DAYS) → CAUTION", ge=2, le=30)

    # ── 数据保留 ──────────────────────────────────────────────────────────
    SETUP_RETENTION_DAYS: int = Field(default=60, description="Days to retain setup snapshots (D062)", ge=7, le=365)


SETUP = CockpitSetupParams()
```

### 1.5 SetupService（计算引擎）

新文件 `backend/app/services/cockpit/setup_service.py`：

```python
class SetupService:
    def __init__(self, db: Session): ...

    def compute_and_store_all(self, today: date | None = None) -> int:
        """
        为所有 is_active=True 的 watchlist 股票计算 setup 快照并 upsert。
        today 默认 date.today()。
        1. 从 StockRepository 获取全部 active tickers
        2. 从 MarketRegimeRepository.get_latest() 获取当日 regime（无数据时视为 NEUTRAL）
        3. 批量从 daily_bars 拉取每只股票的 bars（最多 260 日）
        4. 查询 MarketIndex SPY 历史 close（最多 RS_LOOKBACK_DAYS 条）用于 rs_percentile 排名
        5. 对每只股票调用 _compute_snapshot(ticker, bars, spy_closes, earnings_event, regime)
        6. 计算全 watchlist 的 rs_percentile 排名（百分位）
        7. upsert_batch + delete_before(today - SETUP_RETENTION_DAYS)
        返回 upserted 行数。
        """

    def get_setup_monitor_data(
        self,
        filter_str: str | None = None,
        today: date | None = None,
    ) -> dict:
        """
        读取最新 setup 快照，按 filter 过滤，组装 API-CONTRACT §summary + items。
        filter_str 逗号分隔（如 "ready,near"），None 表示全部。
        今天无快照时返回 summary.total=0, items=[]（不报 APIError）。
        """
```

**纯函数（模块级，供测试直接调用）**：

```python
def _compute_mas(closes: list[float]) -> dict[int, float | None]:
    """计算 MA_PERIODS 各周期的 SMA，数据不足时对应值为 None。"""

def _compute_trend_score(last_close: float, mas: dict[int, float | None]) -> int:
    """
    5 条件阶梯加分：
      close > ma10 (+1), ma10 > ma21 (+1), ma21 > ma50 (+1),
      ma50 > ma150 (+1), ma150 > ma200 (+1)
    任一 MA 为 None 时该条件不计分（视为 False）。
    """

def _compute_volume_status(volumes: list[int]) -> str | None:
    """
    取最后一个 volume vs 前 VOLUME_MA_PERIOD 日均量。
    bars < VOLUME_MA_PERIOD+1 时返回 None。
    """

def _classify_setup_type(
    last_close: float,
    mas: dict[int, float | None],
    highs: list[float],
    trend_score: int,
    had_recent_earnings: bool,
    prev_closes: list[float],
) -> tuple[str, float | None, float | None, float | None, float | None]:
    """
    返回 (setup_type, entry_price, stop_price, target_2r, target_3r)。

    分类优先级（首匹配退出）：
    1. BROKEN:   ma150 is not None AND last_close < ma150
                 entry/stop/targets = None
    2. EXTENDED: ma50 is not None AND (last_close - ma50)/ma50*100 > EXTENDED_MA50_PCT
                 entry/stop/targets = None
    3. EARNINGS_DRIFT: had_recent_earnings AND ma21 is not None AND last_close > ma21
                 entry = last_close*1.001, stop = ma21*(1-0.02)
    4. BREAKOUT: len(highs) >= 20 AND trend_score >= 3
                 pivot20 = max(highs[-20:])
                 last_close >= pivot20*(1-BREAKOUT_ZONE_PCT/100)
                 entry = pivot20, stop = ma50*(1-0.02) if ma50 else last_close*0.95
    5. PULLBACK: ma21 is not None AND ma50 is not None AND trend_score >= 3
                 AND last_close > (ma150 if ma150 else ma50*0.90)
                 AND ma21*0.97 <= last_close <= ma50*(1+PULLBACK_ZONE_ABOVE_MA50_PCT/100)
                 entry = ma21, stop = ma21*(1-0.03)
    6. RECLAIM:  ma50 is not None AND trend_score >= 2 AND last_close > ma50
                 AND any(c < ma50 for c in prev_closes[-RECLAIM_LOOKBACK_BARS:])
                 entry = ma50*1.001, stop = ma50*(1-0.02)
    7. NONE:     else; entry/stop/targets = None
    """

def _compute_earnings_risk(
    earnings_event: Any | None,
    today: date,
) -> str:
    """
    earnings_event: EarningsEvent ORM 对象或 None。
    today 之后最近一次财报：
      days = (earnings_date - today).days
      days <= EARNINGS_DANGER_DAYS  → "DANGER"
      days <= EARNINGS_CAUTION_DAYS → "CAUTION"
      else                           → "SAFE"
    earnings_event 为 None 时 → "SAFE"
    """

def _compute_ready_signal(
    trend_score: int,
    rs_percentile: float,
    setup_quality: str | None,
    distance_to_entry_pct: float | None,
    reward_risk: float | None,
    earnings_risk: str,
    regime: str,
) -> bool:
    """
    全 7 条件 AND：
    1. trend_score >= READY_TREND_MIN
    2. rs_percentile >= READY_RS_MIN
    3. setup_quality in quality_set(READY_QUALITY_MIN)  # "B"→{"A","B"}，"A"→{"A"}，"C"→{"A","B","C"}
    4. distance_to_entry_pct is not None AND 0 <= distance_to_entry_pct <= READY_DIST_MAX_PCT
    5. reward_risk is not None AND reward_risk >= READY_REWARD_RISK_MIN
    6. earnings_risk != "DANGER"
    7. regime != "RISK_OFF"
    """

def _compute_suggested_action(
    setup_type: str,
    ready_signal: bool,
    distance_to_entry_pct: float | None,
    regime: str,
) -> str | None:
    """
    enter:  ready_signal = True
    watch:  setup_type in [BREAKOUT, PULLBACK, RECLAIM, EARNINGS_DRIFT]
            AND NOT ready_signal
            AND distance_to_entry_pct is not None
            AND 0 <= distance_to_entry_pct <= READY_DIST_MAX_PCT * 2
    wait:   setup_type in above AND NOT ready_signal AND dist > READY_DIST_MAX_PCT * 2
    reduce: setup_type = EXTENDED
    exit:   setup_type = BROKEN
    null:   setup_type = NONE
    """

def _percentile_rank(values: list[float], value: float) -> int:
    """百分位排名：返回 0-100 的整数，value 在 values 中从小到大的排名百分比。"""
```

**`rs_percentile` 批量计算策略**（在 `compute_and_store_all` 中）：

```
1. spy_closes = 从 market_indices 取最近 RS_LOOKBACK_DAYS 条 SPY close，ASC 排序
2. spy_return = (spy_closes[-1] - spy_closes[0]) / spy_closes[0]   若 SPY 数据不足 / spy_return ≈ 0 → 全部股票 rs_percentile = RS_SPY_FALLBACK_PCT
3. 对每只股票：stock_return = (closes[-1] - closes[-RS_LOOKBACK_DAYS]) / closes[-RS_LOOKBACK_DAYS]
   rs_ratio = stock_return / spy_return（如 spy_return > 0.001 else stock_return）
4. 收集所有 ratios → 对每只股票 rs_percentile = _percentile_rank(all_ratios, ratio)
   单只股票 watchlist → rs_percentile = RS_SPY_FALLBACK_PCT
```

---

## 2. 预计修改文件（共 7 个）

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `backend/alembic/versions/010_f202a_setup_snapshots.py` | 新建 | Alembic 建表迁移 |
| 2 | `backend/app/models/setup_snapshot.py` | 新建 | SQLAlchemy ORM model |
| 3 | `backend/app/models/__init__.py` | 修改 | +1 import SetupSnapshot |
| 4 | `backend/app/repositories/setup_snapshot_repository.py` | 新建 | upsert_batch + get_latest + delete_before |
| 5 | `backend/app/services/cockpit/cockpit_params.py` | 修改 | 追加 §2 CockpitSetupParams + `SETUP` 实例 |
| 6 | `backend/app/services/cockpit/setup_service.py` | 新建 | SetupService + 纯函数计算引擎 |
| 7 | `backend/tests/test_setup_f202a.py` | 新建 | S1–S16 测试用例 |

**额外 test infra 改动**（不计入 7 文件）：
- `backend/tests/test_schema.py`：`EXPECTED_TABLES` 追加 `"setup_snapshots"`

---

## 3. 完成标准（可测试）

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| S1 | `alembic upgrade head` 成功，`setup_snapshots` 表存在，唯一索引 `uq_setup_snapshot_ticker_date` 存在 | 集成 | alembic CLI |
| S2 | `alembic downgrade -1` 成功，`setup_snapshots` 表删除 | 集成 | alembic CLI |
| S3 | `upsert_batch` 插入新行，返回正确行数 | 单元 | pytest + in-memory SQLite |
| S4 | `upsert_batch` 在同一 (ticker, scan_date) 重复调用时覆盖旧值（UPSERT 语义）| 单元 | pytest |
| S5 | `delete_before(cutoff)` 删除 scan_date < cutoff 行，保留 >= cutoff 行 | 单元 | pytest |
| S6 | `get_latest_all_active` 每只 ticker 只返回最新一行，无快照 ticker 不报错 | 单元 | pytest |
| S7 | `_compute_trend_score`：MA 全梯度 close>ma10>ma21>ma50>ma150>ma200 → 5 | 单元 | pytest |
| S8 | `_compute_trend_score`：ma200=None（不足 200 bars）→ 最后一个梯度不加分，其余正常 | 单元 | pytest |
| S9 | `_compute_earnings_risk`：days=3 → DANGER；days=4 → CAUTION；days=10 → CAUTION；days=11 → SAFE；earnings_event=None → SAFE | 单元 | pytest（参数化 5 个用例） |
| S10 | `_compute_ready_signal`：全 7 条件满足 → True | 单元 | pytest |
| S11 | `_compute_ready_signal`：任一条件不满足（参数化 7 个 case）→ False | 单元 | pytest |
| S12 | `_classify_setup_type`：close < ma150 → BROKEN，entry/stop/targets=None | 单元 | pytest |
| S13 | `_classify_setup_type`：close = ma50 * 1.20（超出 15% 阈值）→ EXTENDED，entry/stop=None | 单元 | pytest |
| S14 | `_classify_setup_type`：BREAKOUT 条件满足 → entry=pivot20，stop=ma50*(1-0.02)，target_2r=entry+2*(entry-stop) | 单元 | pytest |
| S15 | `_classify_setup_type`：PULLBACK 条件满足 → entry=ma21，stop=ma21*(1-0.03) | 单元 | pytest |
| S16 | `compute_and_store_all`（集成）：注入 2 只 active stock + SPY market_index bars → setup_snapshots 写入 2 行，每行字段完整，无异常 | 集成 | pytest + in-memory SQLite |
| S17 | `pytest backend/tests/` 全量回归通过，无新增 failure（pre-existing `test_news_api` failure 标注为非本 feature 引入）| 回归 | pytest |

---

## 4. Evaluator 自检清单

### 文件存在性
- [ ] 7 个文件全部存在，路径与表 2 一致
- [ ] `alembic/versions/010_f202a_setup_snapshots.py` 含 `upgrade` 和 `downgrade`

### 数据模型合规性
- [ ] `SetupSnapshot.__tablename__` = `"setup_snapshots"`
- [ ] `UniqueConstraint("ticker", "scan_date", name="uq_setup_snapshot_ticker_date")` 存在
- [ ] `models/__init__.py` 的 `__all__` 包含 `"SetupSnapshot"`
- [ ] `earnings_risk` 字段 `nullable=False`；`setup_type` 字段 `nullable=False`
- [ ] 字段名与 DATA-MODEL.md 一字不差（snake_case）

### D070 合规性
- [ ] `setup_service.py` 内无任何魔法数字 / 字符串阈值（grep 确认）
- [ ] 所有阈值通过 `from app.services.cockpit.cockpit_params import SETUP, SHARED` 引入
- [ ] `cockpit_params.py` 新增字段均有 `Field(description=...)`
- [ ] `SETUP = CockpitSetupParams()` 模块级实例存在
- [ ] import cockpit_params 无异常（pytest import check 通过）

### 算法正确性
- [ ] `_compute_trend_score` 使用 5 条件（close>ma10、ma10>ma21、ma21>ma50、ma50>ma150、ma150>ma200）
- [ ] `_classify_setup_type` 优先级顺序：BROKEN > EXTENDED > EARNINGS_DRIFT > BREAKOUT > PULLBACK > RECLAIM > NONE
- [ ] `_compute_ready_signal` 严格 7 条 AND，无 OR 短路
- [ ] `rs_percentile` 在 `compute_and_store_all` 批量计算后才填入，单只 watchlist 使用 fallback
- [ ] `distance_to_entry_pct` = (entry - last_close) / last_close * 100（负值表示已穿越）
- [ ] `reward_risk` = (target_2r - entry) / (entry - stop)，stop < entry 才有意义

### 测试
- [ ] S1–S17 全部通过
- [ ] S11 参数化覆盖全 7 个 ready_signal 条件
- [ ] S17 全量回归通过（`test_news_api` pre-existing failure 标注为非本 feature）

### 代码质量
- [ ] 单个函数不超过 50 行
- [ ] 纯函数（`_compute_*` / `_classify_*`）无 `self`，可独立测试
- [ ] 无 `print` 遗留
- [ ] 无未使用的 import

---

## 5. 非目标（明确不做，留给 F202-b/c）

- `config.py` cron 参数（F202-b）
- `refresh_job.py` cron tick（F202-b）
- Pydantic response schema `SetupMonitorResponse`（F202-b）
- FastAPI Router `GET /api/cockpit/setup-monitor`（F202-b）
- `routers/cockpit/__init__.py` 注册（F202-b）
- 前端 SetupMonitorWidget 及 3 个共享子组件（F202-c）
- `CockpitRegistry.ts` 注册（F202-c）

---

## 6. 开发顺序

1. Alembic 迁移 `010_f202a_setup_snapshots.py`，运行 `alembic upgrade head` 验证
2. `models/setup_snapshot.py` + `models/__init__.py`
3. `repositories/setup_snapshot_repository.py`（upsert_batch + get_latest_all_active + delete_before）
4. `services/cockpit/cockpit_params.py` 追加 §2（Pydantic 校验通过，import 无异常）
5. `services/cockpit/setup_service.py` 纯函数层（_compute_mas / _compute_trend_score / _compute_volume_status / _classify_setup_type / _compute_earnings_risk / _compute_ready_signal / _compute_suggested_action / _percentile_rank）
6. `SetupService` 类（compute_and_store_all + get_setup_monitor_data）
7. 单元/集成测试 `tests/test_setup_f202a.py`（S1–S17）
8. `tests/test_schema.py` 追加 `"setup_snapshots"`
9. 全量 `pytest backend/tests/` 回归（S17）
10. Evaluator 自检清单逐条打勾
11. `features.json` 更新 + `claude-progress.txt` 追加
12. `git commit -m "feat(F202-a): Setup Monitor 数据层（model + repo + cockpit_params §2 + setup_service）"`

---

## 7. 风险与取舍

- **SPY 数据缺失**：`compute_and_store_all` 在 F201-b ETF 数据写入前 SPY bars 可能不足。降级处理：rs_percentile 使用 `RS_SPY_FALLBACK_PCT=50.0`，不抛异常。
- **Setup type 算法简化**：v1.0 优先确定性、可测试；算法基于 MA 相对位置和 20 日高点，未引入 pivot 识别算法（未来可升级）。所有参数走 `SETUP.*`，算法升级只需修改 `cockpit_params.py`。
- **daily_bars 不足**（< 10 bars）：`_classify_setup_type` 返回 `"NONE"`，所有 MA 为 None，trend_score=0；不阻塞整体批量计算。
- **SQLite `ON CONFLICT` 语法**：使用 `sqlite_insert().on_conflict_do_update()` 而非 `REPLACE INTO`，保留 id 主键连续性。

---

👤 请确认：

1. **F202 三段拆分**（F202-a 数据层 / F202-b 接入层 / F202-c 前端）→ OK？
2. **Setup type 分类算法优先级**（BROKEN > EXTENDED > EARNINGS_DRIFT > BREAKOUT > PULLBACK > RECLAIM > NONE）→ OK？
3. **CockpitSetupParams §2 默认阈值**（EXTENDED=15% / BREAKOUT_ZONE=5% / QUALITY_A: trend≥4 + rs≥75 / READY: trend≥4 + rs≥70 + dist≤3% + RR≥2）→ OK？
4. **rs_percentile 批量排名策略**（全 watchlist 相对 SPY 的 return ratio 百分位，SPY 不足时 fallback=50）→ OK？
5. **entry/stop 定义**（BREAKOUT: entry=pivot20, stop=ma50*0.98；PULLBACK: entry=ma21, stop=ma21*0.97；RECLAIM: entry=ma50*1.001, stop=ma50*0.98）→ OK？

全部 OK 后进入 Generator 模式写代码。
