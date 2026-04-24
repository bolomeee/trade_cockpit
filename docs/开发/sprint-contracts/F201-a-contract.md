# Sprint Contract：F201-a — Market Regime 数据层

> 状态：草案 | 起草：2026-04-24
> 父 Feature：F201 Market Regime Widget
> 兄弟：F201-b（market_indices ETF 扩展 + APScheduler + Schema + Router，独立 Sprint）
> 引用文档：
>   - DATA-MODEL.md §Entity: MarketRegimeSnapshot（字段权威）
>   - API-CONTRACT.md §GET /api/cockpit/regime（接口权威，F201-b 实现）
>   - DECISIONS.md D061（market_indices 扩展 17 symbol + regime 阈值，F201-a 修订版）
>   - DECISIONS.md D070（cockpit_params.py 约定；**本 Sprint 首次创建 §0+§1**）

---

## 0. 背景与定位

F201 Market Regime Widget 总文件数约 13，拆分为：

- **F201-a（本 Sprint，6 生产文件）**：数据层 — Alembic 建表 + SQLAlchemy Model + Repository + `cockpit_params.py` §0+§1 + `MarketRegimeService` 计分引擎
- **F201-b（后续 Sprint，6 生产文件）**：接入层 — market_indices 扩展 14 ETF symbol（+`market_index_repository.py` + `market_refresh_service.py`）+ APScheduler cron + Pydantic Schema + FastAPI Router + `routers/cockpit/__init__.py` 注册

F201-a 完成后，计分引擎可以独立跑单元/集成测试，但需要手动插入 `market_indices` 测试数据（14 个 ETF symbol 的拉取逻辑在 F201-b 落地）。

---

## 1. 实现范围

### 1.1 Alembic 迁移

新文件 `backend/alembic/versions/009_f201a_market_regime_snapshots.py`：

```sql
CREATE TABLE market_regime_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    regime VARCHAR(16) NOT NULL,
    market_score INTEGER NOT NULL,
    spy_trend_score INTEGER NOT NULL,
    qqq_trend_score INTEGER NOT NULL,
    iwm_breadth_score INTEGER NOT NULL,
    sector_participation_score INTEGER NOT NULL,
    risk_appetite_score INTEGER NOT NULL,
    volatility_stress_score INTEGER NOT NULL,
    allowed_exposure_pct FLOAT NOT NULL,
    single_trade_risk_pct FLOAT NOT NULL,
    preferred_setups TEXT NOT NULL,      -- JSON array string
    avoid_setups TEXT NOT NULL,          -- JSON array string
    computed_at DATETIME NOT NULL,
    UNIQUE (date)                        -- uq_market_regime_date
);
CREATE INDEX ix_market_regime_snapshots_date ON market_regime_snapshots(date);
```

upgrade / downgrade 均实现。

### 1.2 SQLAlchemy Model

新文件 `backend/app/models/market_regime_snapshot.py`：

- 严格照搬 DATA-MODEL.md 中 `class MarketRegimeSnapshot(Base)` 定义
- `UniqueConstraint("date", name="uq_market_regime_date")`
- `computed_at` 默认 `lambda: datetime.now(timezone.utc)`
- `preferred_setups` / `avoid_setups` 为 `Text`（JSON 字符串，service 层负责序列化/反序列化）

修改 `backend/app/models/__init__.py`：

- 新增 `from app.models.market_regime_snapshot import MarketRegimeSnapshot  # noqa: E402`
- `__all__` 追加 `"MarketRegimeSnapshot"`

### 1.3 MarketRegimeRepository

新文件 `backend/app/repositories/market_regime_repository.py`：

```python
class MarketRegimeRepository:
    def __init__(self, db: Session): ...

    def upsert(self, data: dict) -> MarketRegimeSnapshot:
        """
        INSERT OR UPDATE by date (uq_market_regime_date)。
        data keys 与 model 字段名一一对应（snake_case）。
        preferred_setups / avoid_setups 传入 JSON 字符串。
        返回 upsert 后的 ORM 对象。
        """

    def get_latest(self) -> MarketRegimeSnapshot | None:
        """
        返回 date 最大的一行，表为空返回 None。
        """

    def delete_old(self, cutoff: date) -> int:
        """
        删除 date < cutoff 的行（90 天 retention 窗口）。
        返回删除行数。
        """
```

### 1.4 cockpit_params.py（§0 SHARED + §1 REGIME）

新文件 `backend/app/services/cockpit/cockpit_params.py`，遵循 D070 约定：
- Pydantic v2 `BaseModel` + `model_config = ConfigDict(frozen=True)`
- 每字段必带 `Field(description=..., ge=..., le=...)` 或 `Field(description=...)`
- 模块级实例 `SHARED = CockpitSharedParams()` 和 `REGIME = CockpitRegimeParams()`

**§0 CockpitSharedParams**：

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `MA_SHORT` | `50` | 短期 MA 周期（用于 regime + setup scoring） |
| `MA_LONG` | `200` | 长期 MA 周期 |
| `REGIME_LOOKBACK_DAYS` | `200` | 计分所需最少历史交易日数 |
| `RS_LOOKBACK_DAYS` | `20` | RS trend 对比窗口（N 交易日回报率） |
| `SECTOR_ETFS` | `["XLK","XLY","XLF","XLI","XLE","XLV","XLC","XLP","XLU","XLB","XLRE"]` | 11 sector ETF |
| `INDEX_ETFS` | `["SPY","QQQ","IWM"]` | 3 大盘 ETF |

**§1 CockpitRegimeParams**：

*Sub-score 点数*（总计 100）：

| 字段 | 默认值 | 条件 |
|------|--------|------|
| `SPY_ABOVE_MA_SHORT_PTS` | `8` | `spy.close > spy.ma50` |
| `SPY_ABOVE_MA_LONG_PTS` | `8` | `spy.close > spy.ma200` |
| `SPY_GOLDEN_CROSS_PTS` | `9` | `spy.ma50 > spy.ma200` |
| `QQQ_ABOVE_MA_SHORT_PTS` | `7` | `qqq.close > qqq.ma50` |
| `QQQ_ABOVE_MA_LONG_PTS` | `6` | `qqq.close > qqq.ma200` |
| `QQQ_GOLDEN_CROSS_PTS` | `7` | `qqq.ma50 > qqq.ma200` |
| `IWM_ABOVE_MA_SHORT_PTS` | `5` | `iwm.close > iwm.ma50` |
| `IWM_ABOVE_MA_LONG_PTS` | `5` | `iwm.close > iwm.ma200` |
| `IWM_RS_POSITIVE_PTS` | `5` | `iwm.close/iwm.ma50 > spy.close/spy.ma50` |
| `XLY_ABOVE_MA_SHORT_PTS` | `5` | `xly.close > xly.ma50`（risk appetite） |
| `XLK_ABOVE_MA_SHORT_PTS` | `5` | `xlk.close > xlk.ma50`（risk appetite） |
| `SPY_RETURN_PTS` | `5` | SPY N 日涨幅 > threshold（volatility stress） |
| `BREADTH_STRESS_PTS` | `5` | sector 宽度 >= min（volatility stress） |
| `SPY_RETURN_MIN_PCT` | `-5.0` | SPY N 日涨幅阈值（%），小于此视为 stress |
| `SECTOR_BREADTH_MIN` | `5` | 至少 N/11 sector ETF 在 MA50 上方视为非 stress |

> 点数校验：SPY(8+8+9=25) + QQQ(7+6+7=20) + IWM(5+5+5=15) + Sector 最高 20（动态公式）+ Risk(5+5=10) + Vol(5+5=10) = 100

*Regime 分类阈值*：

| 字段 | 默认值 |
|------|--------|
| `RISK_ON_MIN` | `80` |
| `CONSTRUCTIVE_MIN` | `60` |
| `NEUTRAL_MIN` | `40` |
| `DEFENSIVE_MIN` | `20` |
| （< 20 → `RISK_OFF`） | — |

*Sector 状态阈值*（close / ma50 ratio）：

| 字段 | 默认值 | 状态 |
|------|--------|------|
| `SECTOR_STRONG_RATIO` | `1.02` | ratio ≥ 1.02 → "Strong" |
| —（1.00–1.02）— | — | → "Constructive" |
| `SECTOR_WEAK_RATIO` | `0.97` | ratio ≥ 0.97 → "Weak"，< 0.97 → "Defensive" |

*风险敞口 / setup 推荐*（`dict[str, ...]` 字段）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `ALLOWED_EXPOSURE_PCT` | `dict[str, float]` | 各 regime 对应的推荐总敞口 % |
| `SINGLE_TRADE_RISK_PCT` | `dict[str, float]` | 各 regime 单笔风险 % |
| `PREFERRED_SETUPS` | `dict[str, list[str]]` | 各 regime 偏好的 setup 类型 |
| `AVOID_SETUPS` | `dict[str, list[str]]` | 各 regime 规避的 setup 类型 |

默认值：

```python
ALLOWED_EXPOSURE_PCT = {
    "RISK_ON": 90.0, "CONSTRUCTIVE": 70.0, "NEUTRAL": 50.0,
    "DEFENSIVE": 30.0, "RISK_OFF": 10.0
}
SINGLE_TRADE_RISK_PCT = {
    "RISK_ON": 1.5, "CONSTRUCTIVE": 1.0, "NEUTRAL": 0.75,
    "DEFENSIVE": 0.5, "RISK_OFF": 0.0
}
PREFERRED_SETUPS = {
    "RISK_ON":        ["BREAKOUT", "PULLBACK", "RECLAIM"],
    "CONSTRUCTIVE":   ["BREAKOUT", "PULLBACK"],
    "NEUTRAL":        ["PULLBACK", "RECLAIM"],
    "DEFENSIVE":      ["RECLAIM"],
    "RISK_OFF":       [],
}
AVOID_SETUPS = {
    "RISK_ON":        [],
    "CONSTRUCTIVE":   ["EXTENDED"],
    "NEUTRAL":        ["BREAKOUT", "EXTENDED"],
    "DEFENSIVE":      ["BREAKOUT", "PULLBACK", "EXTENDED"],
    "RISK_OFF":       ["BREAKOUT", "PULLBACK", "RECLAIM", "EARNINGS_DRIFT", "EXTENDED"],
}
```

### 1.5 MarketRegimeService（计分引擎）

新文件 `backend/app/services/cockpit/market_regime_service.py`：

```python
class MarketRegimeService:
    def __init__(self, db: Session): ...

    def compute_and_store(self, today: date | None = None) -> MarketRegimeSnapshot:
        """
        从 market_indices 读取历史数据，计算 regime 打分，upsert 到
        market_regime_snapshots。today 默认 date.today()。
        数据不足（任一 symbol 的历史 bar < SHARED.REGIME_LOOKBACK_DAYS）
        时，对应子项得 0 分，不抛异常，但写入 SystemLog WARN。
        返回 upsert 后的 snapshot ORM 对象。
        """

    def get_indices_and_sectors_state(self) -> tuple[list[dict], list[dict]]:
        """
        从 market_indices 读取最近数据，派生 indices（SPY/QQQ/IWM）和
        sectors（11 ETF）的状态字典，供 F201-b GET endpoint 使用。
        返回 (indices_list, sectors_list)，字段名与 API-CONTRACT camelCase 对齐。
        indices item keys: symbol, close, changePct, aboveMa50, aboveMa200, rsTrend, state
        sectors item keys: symbol, close, changePct, state
        """
```

**计分算法细节**（所有阈值从 `cockpit_params.REGIME` 读取，无魔法值）：

```
MA 计算：
  取 market_indices 中 symbol=X 的最近 REGIME_LOOKBACK_DAYS 条记录，
  按 date ASC 排序，取 close 序列。
  MA_SHORT = mean(closes[-MA_SHORT:])
  MA_LONG  = mean(closes[-MA_LONG:])
  数据不足时对应子项得 0 分。

SPY Trend Score（max 25）：
  +SPY_ABOVE_MA_SHORT_PTS  if spy.close > spy.ma_short
  +SPY_ABOVE_MA_LONG_PTS   if spy.close > spy.ma_long
  +SPY_GOLDEN_CROSS_PTS    if spy.ma_short > spy.ma_long

QQQ Trend Score（max 20）：
  +QQQ_ABOVE_MA_SHORT_PTS  if qqq.close > qqq.ma_short
  +QQQ_ABOVE_MA_LONG_PTS   if qqq.close > qqq.ma_long
  +QQQ_GOLDEN_CROSS_PTS    if qqq.ma_short > qqq.ma_long

IWM Breadth Score（max 15）：
  +IWM_ABOVE_MA_SHORT_PTS  if iwm.close > iwm.ma_short
  +IWM_ABOVE_MA_LONG_PTS   if iwm.close > iwm.ma_long
  +IWM_RS_POSITIVE_PTS     if iwm.close/iwm.ma_short > spy.close/spy.ma_short

Sector Participation Score（max 20）：
  count = len([s for s in SECTOR_ETFS if sector[s].close > sector[s].ma_short])
  score = round(count / 11 * 20)

Risk Appetite Score（max 10）：
  +XLY_ABOVE_MA_SHORT_PTS  if xly.close > xly.ma_short
  +XLK_ABOVE_MA_SHORT_PTS  if xlk.close > xlk.ma_short

Volatility Stress Score（max 10）：
  spy_20d_return = (spy.close - spy_closes[-RS_LOOKBACK_DAYS]) / spy_closes[-RS_LOOKBACK_DAYS] * 100
  +SPY_RETURN_PTS       if spy_20d_return > SPY_RETURN_MIN_PCT
  +BREADTH_STRESS_PTS   if count_above_ma_short >= SECTOR_BREADTH_MIN

market_score = sum of 6 sub-scores

Regime 分类：
  RISK_ON      if market_score >= RISK_ON_MIN
  CONSTRUCTIVE if market_score >= CONSTRUCTIVE_MIN
  NEUTRAL      if market_score >= NEUTRAL_MIN
  DEFENSIVE    if market_score >= DEFENSIVE_MIN
  RISK_OFF     otherwise
```

**`get_indices_and_sectors_state` 算法**：

```
Index state（SPY/QQQ/IWM）：
  aboveMa50  = close > ma_short
  aboveMa200 = close > ma_long
  golden_cross = ma_short > ma_long
  rsTrend = "up" if (close / ma_short) > (spy.close / spy.ma_short) else "down"
           （SPY 自身 rsTrend 固定 "up"）

  state:
    aboveMa200 AND aboveMa50 AND golden_cross AND rsTrend=="up" AND symbol != "SPY"
        → "Leading"
    aboveMa200 AND aboveMa50 AND golden_cross
        → "Bullish"
    aboveMa200 AND aboveMa50
        → "Constructive"
    aboveMa200 AND NOT aboveMa50
        → "Neutral"
    NOT aboveMa200 AND aboveMa50
        → "Weak"
    NOT aboveMa200 AND NOT aboveMa50
        → "Defensive"

Sector state（11 ETF）：
  ratio = close / ma_short（数据不足时 close=None, state="Neutral"）
  ratio >= SECTOR_STRONG_RATIO     → "Strong"
  ratio >= 1.00                    → "Constructive"
  ratio >= SECTOR_WEAK_RATIO       → "Weak"
  ratio < SECTOR_WEAK_RATIO        → "Defensive"
```

---

## 2. 预计修改文件（共 7 个）

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `backend/alembic/versions/009_f201a_market_regime_snapshots.py` | 新建 | Alembic 建表迁移 |
| 2 | `backend/app/models/market_regime_snapshot.py` | 新建 | SQLAlchemy ORM model |
| 3 | `backend/app/models/__init__.py` | 修改 | +1 import MarketRegimeSnapshot |
| 4 | `backend/app/repositories/market_regime_repository.py` | 新建 | upsert + get_latest + delete_old |
| 5 | `backend/app/services/cockpit/cockpit_params.py` | 新建 | §0 SHARED + §1 REGIME（D070 首次落地） |
| 6 | `backend/app/services/cockpit/market_regime_service.py` | 新建 | 计分引擎 + indices/sectors state |
| 7 | `backend/tests/test_regime_f201a.py` | 新建 | S1–S15 测试用例 |

**额外 test infra 改动**（不计入 6 文件）：
- `backend/tests/test_schema.py`：`EXPECTED_TABLES` 追加 `"market_regime_snapshots"`

---

## 3. 完成标准（可测试）

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| S1 | `alembic upgrade head` 成功，`market_regime_snapshots` 表存在，唯一索引 `uq_market_regime_date` 存在 | 集成 | alembic CLI |
| S2 | `alembic downgrade -1` 成功，`market_regime_snapshots` 表删除 | 集成 | alembic CLI |
| S3 | 全牛市数据（SPY/QQQ/IWM 均 close > MA50 > MA200 + 11 sector 全在 MA50 上方 + XLY/XLK 在 MA50 上方 + SPY 20d return > -5%）→ `market_score = 100`，`regime = "RISK_ON"` | 单元 | pytest + in-memory SQLite |
| S4 | 全熊市数据（所有 symbol close < MA50 < MA200，SPY 20d return < -5%，sector 全低）→ `market_score = 0`，`regime = "RISK_OFF"` | 单元 | pytest |
| S5 | SPY sub-score：close > MA50（+8）+ close > MA200（+8）+ MA50 > MA200（+9）= 25；QQQ、IWM、sector、risk、vol 均给 0 → total = 25 | 单元 | pytest |
| S6 | Sector participation：6/11 sector 在 MA50 上方 → `sector_participation_score = round(6/11*20) = 11` | 单元 | pytest |
| S7 | IWM RS positive：`iwm.close/iwm.ma50 > spy.close/spy.ma50` → IWM_RS_POSITIVE_PTS 计入 | 单元 | pytest |
| S8 | Regime 阈值边界：score=80 → RISK_ON；score=79 → CONSTRUCTIVE；score=60 → CONSTRUCTIVE；score=59 → NEUTRAL；score=20 → DEFENSIVE；score=19 → RISK_OFF | 单元 | pytest（参数化） |
| S9 | UPSERT：同一 date 计算两次（第二次用不同分数）→ `market_regime_snapshots` 只有 1 行，值为第二次 | 单元 | pytest |
| S10 | `repo.get_latest()` 表空时返回 `None` | 单元 | pytest |
| S11 | `repo.delete_old(cutoff)` 删除 `date < cutoff` 行，保留 `date >= cutoff` 行 | 单元 | pytest |
| S12 | 数据不足（SPY 历史 bars < 50 条）→ `spy_trend_score = 0`，无异常，其他子项正常计算 | 单元 | pytest |
| S13 | `get_indices_and_sectors_state()` 返回 tuple：indices 含 SPY/QQQ/IWM 各 1 条（含 symbol/close/changePct/aboveMa50/aboveMa200/rsTrend/state 字段），sectors 含 11 ETF 各 1 条（含 symbol/close/changePct/state 字段） | 单元 | pytest |
| S14 | `cockpit_params.py` 启动时 Pydantic 校验通过（import 无异常）；所有 ge/le 约束在边界值之内 | 单元 | pytest import check |
| S15 | `pytest backend/tests/` 全量回归通过（含新增测试），无新增 failure（pre-existing `test_news_api` failure 不阻塞） | 回归 | pytest |

---

## 4. Evaluator 自检清单

### 文件存在性
- [ ] 7 个文件全部存在，路径与表 2 一致
- [ ] `alembic/versions/009_f201a_market_regime_snapshots.py` 含 `upgrade` 和 `downgrade`

### 数据模型合规性
- [ ] `MarketRegimeSnapshot.__tablename__` = `"market_regime_snapshots"`
- [ ] `UniqueConstraint("date", name="uq_market_regime_date")` 存在
- [ ] `models/__init__.py` 的 `__all__` 包含 `"MarketRegimeSnapshot"`
- [ ] `preferred_setups` / `avoid_setups` 字段类型为 `Text`（非 JSON column type）

### D070 合规性
- [ ] `market_regime_service.py` 内无任何魔法数字 / 字符串阈值（grep 确认）
- [ ] 所有阈值通过 `from app.services.cockpit.cockpit_params import REGIME, SHARED` 引入
- [ ] `cockpit_params.py` 中每个字段均有 `Field(description=...)`
- [ ] `REGIME = CockpitRegimeParams()` 和 `SHARED = CockpitSharedParams()` 模块级实例存在
- [ ] 进程 import cockpit_params 无异常（pytest import check 通过）

### 算法正确性
- [ ] sub-score 点数之和等于 `market_score`（测试用例 S3 验证）
- [ ] sector participation 公式为 `round(count / 11 * 20)`（grep 确认）
- [ ] Regime 分类按 RISK_ON_MIN / CONSTRUCTIVE_MIN / NEUTRAL_MIN / DEFENSIVE_MIN 顺序判断（> 而非 >=，边界值 S8 验证）

### API 字段合规性
- [ ] `get_indices_and_sectors_state` 返回字段名为 camelCase（`aboveMa50` 而非 `above_ma50`）
- [ ] `preferred_setups` / `avoid_setups` 在存储前用 `json.dumps` 序列化，读取时 `json.loads`

### 测试
- [ ] S1–S15 全部通过
- [ ] S15 全量回归通过（`test_news_api` pre-existing failure 标注为非本 feature 引入）

### 代码质量
- [ ] 单个函数不超过 50 行
- [ ] 无 `print` 遗留（数据不足时用 `SystemLog WARN`）
- [ ] `_compute_regime_data` 为私有方法（前缀 `_`）
- [ ] `MarketIndexRepository.get_closes_by_symbol` 或等效查询方法用于批量读取历史 close

---

## 5. 非目标（明确不做，留给 F201-b）

- `market_index_repository.py` 扩展（`MARKET_INDEX_WINDOW=260`，添加 14 ETF symbol）
- `market_refresh_service.py` 扩展（拉取 14 ETF 日线数据）
- APScheduler cron 任务（`REGIME_CRON_*`）
- `config.py` cron 参数
- Pydantic response schema（`RegimeData` / `RegimeResponse`）
- FastAPI Router `GET /api/cockpit/regime`
- `routers/cockpit/__init__.py` 注册
- 前端 MarketRegimeWidget UI（F201 前端由 design-bridge 定义，属 v1.8 后期 sprint）

---

## 6. 开发顺序

1. Alembic 迁移 `009_f201a_market_regime_snapshots.py`，运行 `alembic upgrade head` 验证
2. `models/market_regime_snapshot.py` + `models/__init__.py`
3. `repositories/market_regime_repository.py`（upsert + get_latest + delete_old）
4. `services/cockpit/cockpit_params.py`（§0 SHARED + §1 REGIME，Pydantic 校验通过）
5. `services/cockpit/market_regime_service.py`（compute_and_store + get_indices_and_sectors_state）
6. 单元/集成测试 `tests/test_regime_f201a.py`（S1–S15）
7. `tests/test_schema.py` 追加 `"market_regime_snapshots"`
8. 全量 `pytest backend/tests/` 回归（S15）
9. Evaluator 自检清单逐条打勾
10. `features.json` 更新 + `claude-progress.txt` 追加
11. `git commit -m "feat(F201-a): Market Regime 数据层（model + repo + cockpit_params + scoring service）"`

---

## 7. 风险与取舍

- **market_indices 14 ETF 数据缺失**：F201-a 测试全部通过手动插入测试数据；实际 ETF 数据由 F201-b `market_refresh_service.py` 扩展后才有。冷启动第一次 `compute_and_store` 在 F201-b 之前运行会因数据不足给出低分，符合"数据不足 → sub-score = 0"的容错设计。
- **SQLite `round()` 精度**：Python 内置 `round(x, 0)` 使用银行家舍入；sector participation 得分用 `int(round(...))` 确保类型一致性。
- **`preferred_setups` / `avoid_setups` 存为 JSON Text**：service 层统一 `json.dumps` / `json.loads`，repository 层不做解析（透传 str）。

---

👤 请确认：

1. **F201-a / F201-b 拆分方案**（F201-a=数据层，F201-b=ETF 数据拉取+cron+router）→ OK？
2. **计分算法**（6 维，权重 SPY25/QQQ20/IWM15/Sector20/Risk10/Vol10）→ OK？
3. **cockpit_params.py 默认阈值**（RISK_ON≥80 / CONSTRUCTIVE≥60 / NEUTRAL≥40 / DEFENSIVE≥20 / <20=RISK_OFF）→ OK？
4. **Sector state 比例阈值**（close/MA50：≥1.02=Strong / ≥1.00=Constructive / ≥0.97=Weak / <0.97=Defensive）→ OK？
5. **Index state 规则**（上方两 MA + golden cross → Bullish；QQQ/IWM 超跑 SPY → Leading）→ OK？

全部 OK 后进入 Generator 模式写代码。
