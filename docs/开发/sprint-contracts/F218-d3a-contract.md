---
status: confirmed
drafted_at: 2026-05-19
confirmed_at: 2026-05-19
sprint: F218-d3a
parent_feature: F218
---

# F218-d3a Sprint Contract — T2 数据层（income-statement client + key_metrics 表 + pool_cache 集成）

> 生成：2026-05-19 | 状态：草案 → 待用户确认
> Feature：[F218](docs/需求/features.json) Cockpit Phase D — Repricing Trigger 完整框架（5 类）
> Sub-sprint：F218-d3a（Phase D 10 sub-sprint 第 5 个；T2 Margin Expansion 数据层 — detector 由 d3b 实装）
> 前置：F218-d1 done（service skeleton + 5 占位 detector）/ F218-d2 done（T1 EARNINGS_ACCEL 实装）/ D097 修正 2026-05-18 confirmed
> 下游：F218-d3b（T2 detector 实装）/ F218-d6a（T5 数据层 — 共享 cash-flow + balance-sheet endpoint，补齐 key_metrics 表的 fcf_margin + roic 列 + 落 fundamentals 表）

> 引用文档：
> - [DATA-MODEL.md](docs/系统设计/DATA-MODEL.md) §StockKeyMetricsQuarterly — 表 schema / service 层计算公式 / null-not-erase upsert / `(ticker, fiscal_quarter)` 业务主键拼接规则
> - [ARCHITECTURE.md](docs/系统设计/ARCHITECTURE.md) §Cockpit Repricing Trigger Service / §FMP 端点表 / `FMP_EP_INCOME_STATEMENT` 常量段
> - [DECISIONS.md](docs/系统设计/DECISIONS.md) §D097（修正 2026-05-18 — 3 endpoint / margin+roic service 层算 / null-not-erase / quota 150/week）
> - [F218-d1-contract.md](docs/开发/sprint-contracts/F218-d1-contract.md) — 上游 framework（model/__init__ 注册模式 / alembic 编号 / repository 风格）
> - [F205-e-contract.md](docs/开发/sprint-contracts/F205-e-contract.md) — pool_cache_service rebuild 集成模式（既有 `_fetch_growth_concurrent` 是本 sprint 新增方法的样板）

---

## 0. 背景与定位

F218-d1 留下的 5 个占位中第 2 个 `_detect_margin_expansion` 需要 `stock_key_metrics_quarterly` 表里有数据才能跑。本 sub-sprint **不实装 detector**（detector 在 d3b），只搭建 T2 的数据层管道：从 FMP `/income-statement` 拉季度数字 → service 层算 gross/op/net margin → upsert 到 `stock_key_metrics_quarterly`，并把这一步挂进既有的 weekly pool rebuild cron（D097：复用周一 06:30 UTC 而非新建独立 daily job）。

**为什么 d3a 仅 income-statement，不含 cash-flow / balance-sheet**：
- D097 §1 把 3 个 endpoint 按 detector 用途切：income-statement 是 **T2 专属**，cash-flow + balance-sheet 是 **T2/T5 共享**
- d3a 聚焦 T2 数据层最小切片；cash-flow + balance-sheet 由 d6a 负责（同时落 fundamentals 表，复用入 key_metrics 表的 fcf_margin + roic 列）
- 落地后 `stock_key_metrics_quarterly` 表 d3a 跑完只填 gross/op/net margin；fcf_margin + roic 列保持 NULL（null-not-erase upsert 保证 d6a 后续补字段时不擦既有 margin 数据）
- 这种切法的合理性：把"FMP 接入 / 表创建 / pool_cache 接线"的 plumbing 与"detector 业务逻辑"完全解耦，d3b 拿到的就是一张已有数据的表，与 T1 detector 写 EarningsEvent 表的访问模式一致

**T2 数据获取定义**（DATA-MODEL §StockKeyMetricsQuarterly + DECISIONS D097 §5）：
- FMP `/stable/income-statement?symbol={ticker}&period=quarter&limit=8` → 每 ticker 最近 8 季 income-statement 记录
- 关键字段：`revenue` / `grossProfit` / `operatingIncome` / `netIncome` / `period` (Q1..Q4) / `fiscalYear` / `date`（FMP `date` = `period_end_date`）
- 业务主键：`fiscal_quarter = f"{period} {fiscalYear}"`（如 `"Q2 2026"`）；UQ `(ticker, fiscal_quarter)`
- 计算公式：`gross_margin = grossProfit / revenue`，`op_margin = operatingIncome / revenue`，`net_margin = netIncome / revenue`
- 空值规则：revenue == 0 或 任一原始字段 null → 对应 margin 字段 null（不抛错，保留行）；FMP 返回 null 字段 upsert 时不擦除既有值（与 F204 `EarningsEvent` upsert 一致）
- pool_cache 集成边界：周一 06:30 UTC `PoolCacheService.rebuild()` 跑完既有 cockpit_pool_cache 后追加一步抓 key_metrics

---

## 1. 实现范围

**包含**：

### 1.1 FMP client — `get_income_statement_quarterly`

**修改** `backend/app/external/fmp_client.py`：

顶部 endpoint 常量段（FMP_EP_FINANCIAL_GROWTH 之后）追加：
```python
FMP_EP_INCOME_STATEMENT = "/income-statement"   # F218 D3 T2 Margin Expansion（D097 修正 2026-05-18）
```

`FmpClient` 类追加一个方法（位置紧跟既有 `get_financial_growth`）：
```python
def get_income_statement_quarterly(
    self, symbol: str, limit: int = 8,
) -> list[dict[str, Any]]:
    """FMP /stable/income-statement?period=quarter (F218 D3 T2 Margin Expansion).

    Returns the most recent `limit` quarterly income-statement records for `symbol`,
    raw FMP JSON list. Field normalization (period_end_date / margin compute) is
    done in the service layer (D097 §5: margins computed service-side, not FMP-native).

    Expected fields per record: symbol, date (period end), period (Q1/Q2/Q3/Q4),
    fiscalYear, revenue, grossProfit, operatingIncome, netIncome.

    Returns [] on empty response / HTTP error / network error so pool rebuild
    callers can fail-open per ticker (consistent with get_financial_growth).
    """
    try:
        body = self._request(
            FMP_EP_INCOME_STATEMENT,
            {"symbol": symbol, "period": "quarter", "limit": limit},
        )
        return list(body or [])
    except (httpx.HTTPStatusError, httpx.RequestError):
        return []
```

### 1.2 ORM model — `StockKeyMetricsQuarterly`

**新建** `backend/app/models/stock_key_metrics_quarterly.py`，按 [DATA-MODEL.md §StockKeyMetricsQuarterly](docs/系统设计/DATA-MODEL.md) 1163–1183 行原文 1:1 实现（不增减字段）。

**修改** `backend/app/models/__init__.py`：
- import 段尾追加：`from app.models.stock_key_metrics_quarterly import StockKeyMetricsQuarterly  # noqa: E402`
- `__all__` 列表追加 `"StockKeyMetricsQuarterly"`

### 1.3 Alembic 023 — 创建表

**新建** `backend/alembic/versions/023_f218_d3a_stock_key_metrics_quarterly.py`：
- `upgrade()`：`op.create_table('stock_key_metrics_quarterly', ...)` 含全 9 列 + UQ `uq_key_metrics_ticker_quarter (ticker, fiscal_quarter)` + ticker 单列 index
- `downgrade()`：`op.drop_table('stock_key_metrics_quarterly')`
- revision id = 'f218_d3a_key_metrics_quarterly'，down_revision = '022_f218_repricing_triggers'
- 不依赖任何 ORM 反射（hand-written 与 d1 alembic 022 同模式）

### 1.4 Repository — `KeyMetricsRepository`

**新建** `backend/app/repositories/key_metrics_repository.py`：

```python
"""F218-d3a: KeyMetricsRepository — null-not-erase upsert + read APIs for T2 margin expansion."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.stock_key_metrics_quarterly import StockKeyMetricsQuarterly

_UQ_COLS = ("ticker", "fiscal_quarter")


class KeyMetricsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Write ──────────────────────────────────────────────────────────────────

    def upsert(self, data: dict) -> StockKeyMetricsQuarterly:
        """INSERT OR UPDATE by (ticker, fiscal_quarter) UQ with null-not-erase semantics.

        On conflict, only non-NULL fields in `data` overwrite existing values
        (D097 §4: avoid wiping cached values when FMP transiently returns null).
        """
        # ... 详见 §3 NP-d3a-3 决策

    def get_recent_for_ticker(
        self, ticker: str, limit: int = 8,
    ) -> list[StockKeyMetricsQuarterly]:
        """Most recent `limit` rows ordered by period_end_date DESC. T2 detector entry."""
        return (
            self.db.query(StockKeyMetricsQuarterly)
            .filter(StockKeyMetricsQuarterly.ticker == ticker)
            .order_by(StockKeyMetricsQuarterly.period_end_date.desc())
            .limit(limit)
            .all()
        )

    def delete_for_tickers_not_in(self, active_tickers: list[str]) -> int:
        """Cleanup rows for tickers no longer in pool (called by monthly universe refresh)."""
        # 实现略，详见 §3 NP-d3a-5
```

API surface 共 3 方法：`upsert(data)` / `get_recent_for_ticker(ticker, limit=8)` / `delete_for_tickers_not_in(active_tickers)`。

### 1.5 PoolCacheService 集成 — 新增 `_rebuild_key_metrics`

**修改** `backend/app/services/cockpit/pool_cache_service.py`：
- 顶部追加 import：`KeyMetricsRepository`、`StockKeyMetricsQuarterly`、`_compute_margins_from_income_statement` helper（位置见 §1.6）
- `__init__` 追加：`self._key_metrics_repo = KeyMetricsRepository(db)`
- `rebuild()` 主流程末尾（既有 commit 之后）追加一行：`km_upserted = self._rebuild_key_metrics(tickers)`
- 新增私有方法 `_rebuild_key_metrics(tickers: list[str]) -> int`：并发抓 income-statement（`ThreadPoolExecutor` 复用 `_FMP_MAX_WORKERS=6`，与 `_fetch_bars_concurrent` 同模式）→ 逐 ticker 逐季度计算 margin → 批量 upsert
- `PoolCacheResult` dataclass 不动（D097 决策：失败 fail-open per ticker，整体 status 仍按 cockpit_pool_cache 判定）
- 仅日志记录 key_metrics 上游数：`log_repo.create("OK", "pool_cache", f"key_metrics upserted={km_upserted} elapsed={...}")`

### 1.6 Margin 计算 helper（service 层纯函数）

**修改** `backend/app/services/cockpit/pool_helpers.py`（既有文件，§F205-e 时新建）：

文件末尾追加一个纯函数：
```python
def compute_key_metrics_row_from_income_statement(
    payload: dict,
) -> dict[str, float | None | str | date] | None:
    """Map one FMP /income-statement?period=quarter record → dict ready for KeyMetricsRepository.upsert.

    Returns None if `payload` lacks required identification fields (symbol/period/fiscalYear/date).
    For numeric inputs missing or revenue ≤ 0, the corresponding margin field is set to None
    (D097 §5 + DATA-MODEL.md null rules).

    Output keys: ticker, fiscal_quarter, period_end_date, gross_margin, op_margin, net_margin,
    fetched_at. Does NOT include fcf_margin / roic (F218-d6a will partial-upsert those).
    """
    # 实现详见 §3 NP-d3a-4
```

### 1.7 Tests

**新建** `backend/tests/test_f218_d3a_key_metrics.py`：

10 个测试，按 4 个 class 分组：
- `TestFmpClientIncomeStatementQuarterly`：FMP client 方法 mock 测试 ×2
- `TestComputeKeyMetricsRow`：margin 纯函数测试 ×3
- `TestKeyMetricsRepository`：repo upsert / null-not-erase / get_recent / delete_for_tickers_not_in ×3
- `TestPoolCacheKeyMetricsIntegration`：pool_cache 集成端到端 ×2

详见 §3。

---

## 2. 预计修改文件

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/external/fmp_client.py` | 修改 | +1 endpoint 常量 + 1 方法 `get_income_statement_quarterly(symbol, limit=8)` |
| 2 | `backend/app/models/stock_key_metrics_quarterly.py` | 新建 | ORM model，按 DATA-MODEL.md 1:1 |
| 3 | `backend/alembic/versions/023_f218_d3a_stock_key_metrics_quarterly.py` | 新建 | `op.create_table` + UQ + index |
| 4 | `backend/app/repositories/key_metrics_repository.py` | 新建 | 3 方法：upsert / get_recent_for_ticker / delete_for_tickers_not_in |
| 5 | `backend/app/services/cockpit/pool_cache_service.py` | 修改 | 注入 KeyMetricsRepository / `_rebuild_key_metrics` 私有方法 / `rebuild()` 末尾追加调用 |
| 6 | `backend/app/services/cockpit/pool_helpers.py` | 修改 | +1 纯函数 `compute_key_metrics_row_from_income_statement` |
| 7 | `backend/tests/test_f218_d3a_key_metrics.py` | 新建 | 10 测试 / 4 class |

**实际 7 文件**。⚠️ 超出 6 文件上限 1 个 — 详见 §5 NP-d3a-1（用户决策：申请超额授权 vs 拆分 vs 跳过 __init__.py 注册）。

> ⚠️ 注意：`backend/app/models/__init__.py` 注册条目在 §1.2 描述但未计入预计文件清单，因为 NP-d3a-1 默认推荐 Path A（合并为同一 logical change with model file，count=1），用户若选 Path B 则该文件单算（count=8，需双倍超额授权）。

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `FmpClient.get_income_statement_quarterly(symbol, limit=N)` 调用 `/stable/income-statement` 时 params 含 `period=quarter` & `limit=N` & `symbol=AAPL`；成功响应返 list；空响应 / 4xx / 5xx / 网络错误均 fail-open 返 `[]` | 单元（mock httpx） | pytest + respx 或 monkeypatch self._http.get |
| 2 | `get_income_statement_quarterly` 限频共享既有 `_FmpRateLimiter`（参数注入路径正确，复用 D044 token bucket）；不引入独立 limiter | 单元 | pytest（断言 `self._acquire` 被调用，与 `get_earnings_calendar` 同 fixture）|
| 3 | `compute_key_metrics_row_from_income_statement(payload)` happy path：`{symbol: "NVDA", period: "Q2", fiscalYear: "2026", date: "2026-07-31", revenue: 30000, grossProfit: 22500, operatingIncome: 18000, netIncome: 16000}` → `{ticker: "NVDA", fiscal_quarter: "Q2 2026", period_end_date: date(2026,7,31), gross_margin: 0.75, op_margin: 0.60, net_margin: 0.5333…, fetched_at: <UTC now>}` | 单元 | pytest |
| 4 | `compute_key_metrics_row_from_income_statement` null/零除安全：(a) revenue=0 → 3 个 margin 全 None；(b) grossProfit=None → gross_margin=None 但 op/net margin 正常；(c) revenue=None → 3 个 margin 全 None；(d) symbol/period/fiscalYear/date 任一缺失 → 整个函数返 None | 单元（参数化 4 case） | pytest |
| 5 | `compute_key_metrics_row_from_income_statement` 浮点精度：margin 数值不四舍五入到固定小数（service 层不做 round；DB Float 自然存储）；输出 dict 不含 fcf_margin / roic 键（避免 upsert 误擦） | 单元 | pytest（assert key 集合精确等于预期 7 keys）|
| 6 | `KeyMetricsRepository.upsert(data)` happy path：首次插入新 `(ticker, fiscal_quarter)` 行 → SELECT 后字段齐全；再次相同 `(ticker, fiscal_quarter)` 但 gross_margin 不同 → 覆盖到新值；commit + expire_all 保证读到最新值（与 RepricingTriggerRepository.upsert 同模式）| 单元（sqlite in-memory） | pytest |
| 7 | `KeyMetricsRepository.upsert` null-not-erase 语义（D097 §4）：第一次 upsert 含 `gross_margin=0.75, fcf_margin=None`；第二次 upsert 含 `gross_margin=None, fcf_margin=0.18`（模拟 d6a 后续补字段）→ 最终行：`gross_margin=0.75`（保留）+ `fcf_margin=0.18`（更新）| 单元 | pytest |
| 8 | `KeyMetricsRepository.get_recent_for_ticker("NVDA", limit=4)` 仅返 NVDA 行，按 period_end_date DESC，limit 截断；ticker 无任何行返空 list | 单元 | pytest |
| 9 | `PoolCacheService._rebuild_key_metrics(tickers)` 集成：mock FMP 对 2 ticker × 2 季返合法 payload + 1 ticker 返 [] + 1 ticker 抛 HTTPStatusError → 最终 stock_key_metrics_quarterly 表中：成功 2 ticker × 2 = 4 行，失败 2 ticker 不阻断 rebuild 整体流程；返回 upserted count = 4 | 集成（mock FmpClient） | pytest |
| 10 | `PoolCacheService.rebuild()` 端到端：mock 既有 cockpit_pool_cache 流程（spy_bars / closes_by_ticker / growth）+ 新 key_metrics 流程并存 → 既有 cockpit_pool_cache 行不受影响（rs_percentile / ma50 / last_close 等仍正确写入）+ stock_key_metrics_quarterly 行也成功写入 + system_logs 同时有 "rebuilt N=..." 与 "key_metrics upserted=..." 两条 OK 日志 | 集成 | pytest |

预期测试数：**10 个**（单文件 `test_f218_d3a_key_metrics.py`，按 4 class 分组）。

---

## 4. Evaluator 自检清单

- [ ] 10 个新测试全部通过（`cd backend && uv run pytest tests/test_f218_d3a_key_metrics.py -v`）
- [ ] d1/d2 既有 28 测试仍全绿（`uv run pytest tests/test_repricing_trigger_skeleton.py tests/test_repricing_trigger_earnings_accel.py -v`）— pool_cache 改动不应影响这些
- [ ] F205-e 既有 pool_cache 测试仍全绿（`uv run pytest tests/test_pool_cache_service.py -v` 如存在）— 验证 `rebuild()` 在新增 key_metrics 步骤后既有路径不回归
- [ ] 全量后端回归通过（`uv run pytest`）— 允许预先存在的 9 个 failure（d2 记录在案），不得新增
- [ ] Alembic 023 双向跑通：`uv run alembic upgrade head` 后表存在 + 字段类型正确（gross_margin/op_margin/net_margin = Float nullable，period_end_date = Date NOT NULL）；`uv run alembic downgrade -1` 后表删除；再 `upgrade head` 幂等
- [ ] `StockKeyMetricsQuarterly` model 字段 / 类型 / UQ / index 与 DATA-MODEL.md §StockKeyMetricsQuarterly 1163–1183 行 1:1 一致（不增减字段）
- [ ] `get_income_statement_quarterly` 签名 = `(self, symbol: str, limit: int = 8) -> list[dict[str, Any]]`，与 `get_earnings_calendar` / `get_financial_growth` 风格一致（raw list / fail-open）
- [ ] `compute_key_metrics_row_from_income_statement` 是模块级纯函数（不挂 service class），便于 d6a 复用相同 fiscal_quarter 拼接逻辑
- [ ] FMP endpoint 常量 `FMP_EP_INCOME_STATEMENT` 在 fmp_client.py 顶部声明区（与 `FMP_EP_EARNINGS_CALENDAR` 等齐列），不散落
- [ ] PoolCacheService 改动只"加"不"改"：`rebuild()` 既有 cockpit_pool_cache 写入路径不变（D097 §2 复用 weekly cron 但与既有数据隔离）
- [ ] `_rebuild_key_metrics` 失败 fail-open per ticker：单 ticker FMP 抛错 / 返 [] / partial 数据 都不阻断整个 rebuild；错误写 system_log WARN 但 status 仍 ok
- [ ] FMP rate limiter 复用既有 token bucket（不引入第二个 limiter；并发 worker 数复用 `_FMP_MAX_WORKERS=6`）
- [ ] models/__init__.py 注册条目存在（若选 Path A）或明确注释延后（若选 Path C）

### 代码质量检查
- [ ] `_rebuild_key_metrics` 函数长度 ≤ 50 行（拆分到 `_fetch_income_statement_concurrent` helper 与现有 `_fetch_bars_concurrent` / `_fetch_growth_concurrent` 同模式）
- [ ] 无硬编码魔法值（`limit=8` / `_FMP_MAX_WORKERS` / fiscal_quarter 分隔符 " " 全部作为常量或入参）
- [ ] `compute_key_metrics_row_from_income_statement` 函数内无副作用（无 logger / 无 DB 调用，纯映射）
- [ ] 无注释掉的代码块 / 死 import / 未使用变量

### 回归测试
- [ ] 后端全量 `uv run pytest` 通过（允许 9 pre-existing failures，不得新增）
- [ ] cockpit/setup/regime/pool_cache/repricing_trigger（d1+d2）未受 import / 字段命名 / FMP rate limiter 改动影响

---

## 5. 关键设计决策（执行前确认）

| # | 议题 | 推荐方案 | 备选方案 |
|---|------|---------|---------|
| **NP-d3a-1** | 文件预算 — 实际 7 文件超 6 上限 1 个 | **Path A：申请超额授权 7 文件（推荐，同 F217-c2c 模式）**：将 §1.2 model file 与 §1.2 models/__init__.py 注册合并为同一 logical change 报告（count=7，含 1 个 __init__.py 1-line edit）。Sprint 内部 wip commit 时合并提交（"feat(F218-d3a): key_metrics model + __init__ register"）保留原子性。 | **Path B**：把 §1.5 pool_cache 集成 + §1.6 helper 推迟到 d3b（d3b 同时实装 detector + 数据接线），d3a 只负责 plumbing（fmp_client + model + __init__ + alembic + repo + test = 6 文件），但 d3b 文件数因此增至 ~5 涨幅大。 **Path C**：跳过 models/__init__.py 注册（仅在 KeyMetricsRepository import 触发 model 注册，functional 等价，但违反既有 21 个 model 注册的项目惯例，d3b/d6a 须 wip 时补 1-line 注册作 chore commit。 |
| **NP-d3a-2** | FMP client 错误处理风格 | **fail-open 返 `[]`（推荐）**：与 `get_financial_growth` 一致（D079 决策），让 pool rebuild 单 ticker 失败不阻断整批 ~50 ticker 抓取；错误细节由 caller log。 | (a) 抛 httpx 原始异常让 caller 决定（与 `get_daily_bars` 同，更显式但 caller 要 try/except）/ (b) 返 None 而非 [] 让"无数据"与"FMP 失败"区分（语义清但 caller 要双分支）。 |
| **NP-d3a-3** | KeyMetricsRepository.upsert 实现 — null-not-erase 怎么写 | **方案 1：先 SELECT 既有行 → 合并 non-null 字段 → INSERT OR REPLACE（推荐）**：清晰、易测、显式表达"null 不擦"语义；性能在 ~50 ticker × 8 season = ~400 行/周尺度下无压力。 | (a) 方案 2：写 ON CONFLICT DO UPDATE SET gross_margin = COALESCE(EXCLUDED.gross_margin, stock_key_metrics_quarterly.gross_margin)，纯 SQL 语义但 SQLAlchemy SQLite dialect 表达较繁琐 / (b) 方案 3：service 层在调 upsert 前先读旧行做合并，repo 保持简单 INSERT OR REPLACE（把语义复杂度往 service 推）。 |
| **NP-d3a-4** | margin 计算 helper 放哪 | **`pool_helpers.py` 末尾（推荐）**：既有 `extract_revenue_growth_yoy_pct` 等纯函数同居所，避免新建 helpers 文件挤占文件数；d6a 复用时同一 import 路径。 | (a) 新建 `backend/app/services/cockpit/key_metrics_helpers.py`（语义内聚但 +1 文件超额变成 8 文件 — 否决）/ (b) 挂 PoolCacheService 内 `_compute_margins` 私有方法（不可单测，d6a 不便复用）。 |
| **NP-d3a-5** | `delete_for_tickers_not_in` 调用时机 | **本 sprint 实装方法但不挂调用点（推荐）**：D097 §影响 提到月度清理 ticker 已退出 pool 的行，但具体调度由 future cleanup 任务负责（不在 F218 范围）。本 sprint 提供方法供未来挂载；不挂避免引入额外文件改动。 | (a) 立刻在 PoolCacheService.rebuild() 末尾调用，每次 rebuild 清理 — 但 weekly 频度太高，可能误删边界 ticker / (b) 完全不实现该方法 — 但 d6a 还会面临同问题，统一在 d3a 先建好 method 形态省后续重复设计。 |
| **NP-d3a-6** | fcf_margin / roic 列在 d3a 期间的初值 | **NULL（推荐）**：d3a 不抓 cash-flow / balance-sheet，自然为 NULL；upsert null-not-erase 保证 d6a 后续补字段不擦既有 margin；DATA-MODEL.md 已定义这 2 列 nullable。 | (a) 0.0 占位 — 误导后续 detector 误判扩张 / (b) 在 d3a 抓 cash-flow + balance-sheet 直接补齐（吞 d6a 范围 → 文件数爆炸 + 2 sub-sprint 边界模糊化，否决）。 |
| **NP-d3a-7** | `_rebuild_key_metrics` 并发方式 | **复用既有 `ThreadPoolExecutor(max_workers=_FMP_MAX_WORKERS=6)`（推荐）**：与 `_fetch_bars_concurrent` / `_fetch_growth_concurrent` 同模式，rate limiter 是模块级单例 token bucket，并发不会撞限；50 ticker × ~150ms/call ÷ 6 worker ≈ 1.3s 总耗时 | (a) 串行（简单但 ~7s 慢 5×）/ (b) 提高 worker 到 12（无收益：token bucket 仍是瓶颈）。 |
| **NP-d3a-8** | FMP 调用 limit 参数取值 | **`limit=8`（推荐）**：DATA-MODEL.md §保留策略 写明"limit=8 单 ticker 最多 8 行"；T2 detector 实际只用最近 2 季同比 = 8 季远超 + 留余量给历史回测；FMP Starter quota 充裕 | (a) limit=4（仅够 detector 不够回测）/ (b) limit=20（quota 浪费 + 与 DATA-MODEL.md 不符）。 |

### 推荐理由速览

- **NP-d3a-1 7 文件超额（Path A 推荐）**：F217-c2c 已有先例（9 文件超 6），sub_sprint_notes 自身也注明 d3a "6 文件" 是 sizing 阶段估算未含 __init__.py 与 pool_helpers helper。Path B 把 pool_cache 集成推 d3b 看似减 d3a 文件数但 d3b 会因此涨到 ~5 文件（detector + pool_cache fetch + 2 测试 + helper），且打破"d3a 是数据层 / d3b 是检测层"的清晰切分。Path C 跳过 __init__.py 违反项目惯例（既有 21 个 model 全部注册），需要 d3b/d6a 额外 chore commit 补，得不偿失。
- **NP-d3a-2 fail-open**：与 D079 既有决策一致；D097 §影响 也明确"FMP rate limit 不变 + 既有重试/失败策略复用"。
- **NP-d3a-3 SELECT-then-INSERT-OR-REPLACE**：性能在 ~400 行/周尺度完全无压力（单 ticker 8 行 SELECT + REPLACE 双语句 < 5ms）；可读性远胜 raw SQL ON CONFLICT COALESCE；d6a 需要同语义实现 fundamentals upsert，统一方案省思考成本。
- **NP-d3a-4 pool_helpers.py**：既有 4 个 cockpit pure-function 都住这（compute_return_ratio_250d 等），新增不破坏内聚；最关键是不挤占文件数。
- **NP-d3a-5 实装但不挂**：避免在 d3a 决策超出范围的"什么时候清理"问题；月度 cleanup job 是独立未来 work，先把数据访问层准备好。
- **NP-d3a-6 NULL 列**：唯一一致的处理；占位值任何选法都会污染 d3b detector 逻辑。
- **NP-d3a-7 6 worker**：与既有 pool_cache 并发设计一致，rate limiter 在 client 内部自动节流。
- **NP-d3a-8 limit=8**：DATA-MODEL.md 已硬编码；T2 detector 只需 2 季同比（"最近 2 季毛利率扩张 ≥ 200bp"），但 8 季留余量便于历史回测验证 SRS 案例对齐。

---

## 6. 不在范围（本 sprint 排除）

- ❌ `_detect_margin_expansion` 真实实装（d3b — 读 stock_key_metrics_quarterly 判定 ≥ 200bp 扩张 / ≥ 300bp fcf 扩张）
- ❌ FMP balance-sheet-statement endpoint（d6a，T2 roic + T5 balance inflection 共享）
- ❌ FMP cash-flow-statement endpoint（d6a，T2 fcf_margin + T5 FCF 拐点 共享）
- ❌ `stock_fundamentals_quarterly` 表 + FundamentalsRepository（d6a）
- ❌ 补齐 `stock_key_metrics_quarterly.fcf_margin` 与 `stock_key_metrics_quarterly.roic` 列（d6a 在 cash-flow + balance-sheet 接入后通过 null-not-erase upsert 补字段）
- ❌ 任何前端文件（widget / API client / design-spec / tokens / data-mapping / component-plan）（d7b）
- ❌ refresh_job.py cron 注册（d7a — 22:40 UTC RepricingTriggerService 调度；本 sprint 复用已存在的 06:30 UTC pool_cache cron）
- ❌ router + 2 endpoint（d7a）
- ❌ DECISIONS.md 追加（NP-d3a-1~8 是实施级决策由本 contract 承载；D097 已含本 sprint 所需全部决策，本 sprint 不产生新 DXXX）
- ❌ ARCHITECTURE.md / DATA-MODEL.md / API-CONTRACT.md 任何修改（4 文档 status 在 2026-05-18 D097 修正同步 confirmed，本 sprint 严格落地无新增 drift）
- ❌ 历史数据回填脚本（首次 deploy 后第一次周一 06:30 UTC cron 跑完即填充；不需要单独脚本）
- ❌ T2 detector 历史回测验证 SRS 案例（acceptance / d7b 收官时统一做）

---

## 7. 用户待确认

1. **NP-d3a-1 ~ NP-d3a-8** 八项决策：全部按推荐？还是有需要调整的？特别注意 **NP-d3a-1 文件预算**（推荐 Path A：申请超额授权 7 文件，与 F217-c2c 同模式）。
2. **Contract 整体是否同意进入 Generator 模式开发**？

确认后我会：
1. 更新 features.json：`F218-d3a` phase `design_needed` → `contract_agreed`；`_pipeline_status.active_sprint` 切到 `F218-d3a`
2. 追加 F218 iteration_history 一条 `contract_agreed` 记录（subtask=F218-d3a，date=2026-05-19）
3. 更新 claude-progress.txt
4. 生成 SESSION-HANDOFF.md（含 d3a 7 步开发顺序：fmp_client 方法 → model + __init__ 注册 → alembic 023 → repository → margin helper → pool_cache 集成 → 测试，及恢复指令）
5. **强制停止本 session**（feature-dev skill 铁律），输出新 session 恢复指令
