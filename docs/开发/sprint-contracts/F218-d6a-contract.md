---
status: confirmed
drafted_at: 2026-05-20
confirmed_at: 2026-05-20
sprint: F218-d6a
parent_feature: F218
---

# F218-d6a Sprint Contract — T5 数据层（balance-sheet + cash-flow + fundamentals 表 + key_metrics partial-upsert + pool_cache 集成）

> 生成：2026-05-20 | 状态：草案 → 待用户确认
> Feature：[F218](docs/需求/features.json) Cockpit Phase D — Repricing Trigger 完整框架（5 类）
> Sub-sprint：F218-d6a（Phase D 10 sub-sprint 第 7 个；T5 Balance Inflection 数据层 — detector 由 d6b 实装；同时补齐 T2 fcf_margin + roic 列）
> 前置：F218-d1 done（service skeleton + 5 占位）/ F218-d3a done（T2 数据层 + key_metrics 表 + income-statement）/ F218-d3b done（T2 detector）/ F218-d4 done（T3）/ F218-d5 done（T4）
> 下游：F218-d6b（T5 detector 实装 — 净负债下降 ≥5% × 2 季 OR FCF 负→连续 2 正）/ F218-d7a（调度）/ F218-d7b（前端）

> 引用文档：
> - [DATA-MODEL.md](docs/系统设计/DATA-MODEL.md) §StockFundamentalsQuarterly（1186–1235）— 表 schema / net_debt service 层计算 / null-not-erase upsert / `(ticker, fiscal_quarter)` 业务主键拼接规则；§StockKeyMetricsQuarterly（1163–1183）— fcf_margin + roic 列在本 sprint 补齐
> - [DECISIONS.md](docs/系统设计/DECISIONS.md) §D097（FMP 3 endpoint 接入 — income-statement / balance-sheet / cash-flow，后 2 共享；修正 2026-05-18）；§D097 §5（fcf + roic 计算公式与 service 层语义）
> - [ARCHITECTURE.md](docs/系统设计/ARCHITECTURE.md) §Cockpit Repricing Trigger Service / §FMP 端点表 / `FMP_EP_BALANCE_SHEET` + `FMP_EP_CASH_FLOW` 常量段
> - [F218-d3a-contract.md](docs/开发/sprint-contracts/F218-d3a-contract.md) — 同质模板（数据层 plumbing — FMP client + model + alembic + repo + helper + pool_cache 集成 + tests）
> - [F218-d1-contract.md](docs/开发/sprint-contracts/F218-d1-contract.md) — 上游 framework（model/__init__ 注册模式 / alembic 编号 / repository 风格）

---

## 0. 背景与定位

F218-d1 留下的 5 个占位中第 5 个 `_detect_balance_inflection` 需要 `stock_fundamentals_quarterly` 表里有数据才能跑。本 sub-sprint **不实装 detector**（detector 在 d6b），只搭建 T5 的数据层管道：
1. 从 FMP `/stable/balance-sheet-statement?period=quarter` 拉季度资产负债（`total_debt` / `cash`）
2. 从 FMP `/stable/cash-flow-statement?period=quarter` 拉季度现金流（`freeCashFlow` 或 OCF+CapEx 计算，详 NP-d6a-2）
3. service 层算 `net_debt = total_debt - cash`，upsert 到 `stock_fundamentals_quarterly`
4. **同时**用 income-statement（d3a 已抓）+ balance-sheet + cash-flow 计算 `fcf_margin` 与 `roic`，partial-upsert 到 `stock_key_metrics_quarterly`（null-not-erase 保留 d3a 写入的 gross/op/net margin）
5. 挂进既有 weekly pool rebuild cron（周一 06:30 UTC），与 d3a `_rebuild_key_metrics` 同一 pool rebuild 复用 income-statement 数据

**为什么 d6a 同时补 key_metrics 的 fcf_margin + roic**：
- D097 §5 明确：`fcf_margin = freeCashFlow / revenue`，`roic ≈ netIncome / (totalStockholdersEquity + totalDebt - cashAndShortTermInvestments)`
- 这两个字段的计算输入跨 IS（revenue / netIncome）+ BS（equity / debt / cash）+ CF（freeCashFlow），单 endpoint 无法独立产出
- d3a contract 已明确"d6a 在 cash-flow + balance-sheet 接入后通过 null-not-erase upsert 补字段"
- DATA-MODEL.md §StockKeyMetricsQuarterly 把 fcf_margin + roic 与 gross/op/net margin 同表（统一 T2 detector 的入口），d3a 留空字段等 d6a 填

**为什么共享 cash-flow 不是单独抓 T2 / T5 各一次**：
- D097 §影响 明确"T2/T5 共享 cash-flow，pool rebuild 单次抓取分别 upsert 进 2 张缓存表"
- 减半的 quota 估算（~50 ticker × 3 endpoint × 周 1 次 ≈ 150 calls/week vs 假设 4 endpoint 200）
- 避免时间窗口不一致风险（同次 pool rebuild 内同一 ticker 的 IS/BS/CF 三个 endpoint 在分钟级时间窗内成功 / 失败一致）

**T5 数据获取定义**（DATA-MODEL §StockFundamentalsQuarterly + DECISIONS D097 §5）：
- FMP `/stable/balance-sheet-statement?symbol={ticker}&period=quarter&limit=8` → 最近 8 季 BS 记录
- FMP `/stable/cash-flow-statement?symbol={ticker}&period=quarter&limit=8` → 最近 8 季 CF 记录
- BS 关键字段：`totalDebt` / `cashAndShortTermInvestments`（或 `cashAndCashEquivalents` — 详 NP-d6a-6） / `totalStockholdersEquity` / `period` / `fiscalYear` / `date`
- CF 关键字段：`freeCashFlow`（或 `netCashProvidedByOperatingActivities` + `investmentsInPropertyPlantAndEquipment` — 详 NP-d6a-2） / `period` / `fiscalYear` / `date`
- 业务主键：`fiscal_quarter = f"{period} {fiscalYear}"`（与 d3a 同模式）；UQ `(ticker, fiscal_quarter)` — 但与 key_metrics 表是独立表
- 空值规则：FMP null 任一字段 → 对应派生字段 null（不抛错，保留行）；FMP 返回 null 字段 upsert 时不擦既有值（D097 §4）

---

## 1. 实现范围

**包含**：

### 1.1 FMP client — `get_balance_sheet_quarterly` + `get_cash_flow_quarterly`

**修改** `backend/app/external/fmp_client.py`：

顶部 endpoint 常量段（紧跟 `FMP_EP_INCOME_STATEMENT` 之后）追加 2 行：
```python
FMP_EP_BALANCE_SHEET = "/balance-sheet-statement"  # F218 D6 T5 Balance Inflection + T2 roic 分母 (D097)
FMP_EP_CASH_FLOW = "/cash-flow-statement"          # F218 D6 T5 + T2 fcf_margin (T2/T5 共享，D097)
```

`FmpClient` 类追加 2 方法（紧跟既有 `get_income_statement_quarterly`），与之 1:1 同风格（fail-open 返 `[]`）：
```python
def get_balance_sheet_quarterly(
    self, symbol: str, limit: int = 8,
) -> list[dict[str, Any]]:
    """FMP /stable/balance-sheet-statement?period=quarter (F218 D6 T5)."""
    try:
        body = self._request(
            FMP_EP_BALANCE_SHEET,
            {"symbol": symbol, "period": "quarter", "limit": limit},
        )
        return list(body or [])
    except (httpx.HTTPStatusError, httpx.RequestError):
        return []

def get_cash_flow_quarterly(
    self, symbol: str, limit: int = 8,
) -> list[dict[str, Any]]:
    """FMP /stable/cash-flow-statement?period=quarter (F218 D6 T2/T5 共享)."""
    try:
        body = self._request(
            FMP_EP_CASH_FLOW,
            {"symbol": symbol, "period": "quarter", "limit": limit},
        )
        return list(body or [])
    except (httpx.HTTPStatusError, httpx.RequestError):
        return []
```

### 1.2 ORM model — `StockFundamentalsQuarterly`

**新建** `backend/app/models/stock_fundamentals_quarterly.py`，按 [DATA-MODEL.md §StockFundamentalsQuarterly](docs/系统设计/DATA-MODEL.md) 1217–1235 行原文 1:1（9 字段：id / ticker / fiscal_quarter / period_end_date / total_debt / cash / net_debt / fcf / fetched_at；UQ `uq_fundamentals_ticker_quarter`；ticker 单列 index）。

**修改** `backend/app/models/__init__.py`：
- import 段尾追加：`from app.models.stock_fundamentals_quarterly import StockFundamentalsQuarterly  # noqa: E402`
- `__all__` 列表追加 `"StockFundamentalsQuarterly"`

### 1.3 Alembic 024 — 创建 `stock_fundamentals_quarterly` 表

**新建** `backend/alembic/versions/024_f218_d6a_stock_fundamentals_quarterly.py`：
- `upgrade()`：`op.create_table('stock_fundamentals_quarterly', ...)` 含全 9 列 + UQ `uq_fundamentals_ticker_quarter (ticker, fiscal_quarter)` + ticker 单列 index
- `downgrade()`：`op.drop_table('stock_fundamentals_quarterly')`
- revision id = `f218_d6a_fundamentals_quarterly`，down_revision = `f218_d3a_key_metrics_quarterly`
- hand-written 与 alembic 022/023 同模式（不依赖 ORM 反射）

### 1.4 Repository — `FundamentalsRepository`

**新建** `backend/app/repositories/fundamentals_repository.py`：

API 与 `KeyMetricsRepository` 同 surface（共 3 方法）：
- `upsert(data: dict) -> StockFundamentalsQuarterly`：SELECT-then-merge non-null-fields-then-INSERT-OR-REPLACE，null-not-erase 语义（D097 §4，与 d3a §1.4 同实现模板）
- `get_recent_for_ticker(ticker: str, limit: int = 8) -> list[StockFundamentalsQuarterly]`：按 period_end_date DESC 截断；d6b detector 入口
- `delete_for_tickers_not_in(active_tickers: list[str]) -> int`：实装但不挂调用点（同 d3a NP-d3a-5）

### 1.5 helpers — `pool_helpers.py` 末尾追加 2 纯函数

**修改** `backend/app/services/cockpit/pool_helpers.py`：

```python
def compute_fundamentals_row_from_balance_cash(
    balance_payload: dict,
    cash_payload: dict,
) -> dict | None:
    """Map one (BS, CF) pair (same ticker/fiscal_quarter) → dict for FundamentalsRepository.upsert.

    Identification fields (symbol/period/fiscalYear/date) MUST agree between BS and CF;
    otherwise returns None. Pairing is the caller's responsibility (pool_cache_service intersects
    by fiscal_quarter before passing).

    net_debt = total_debt - cash, null if either input null.
    fcf source: NP-d6a-2 (default = FMP freeCashFlow field directly).
    Returns 8 keys: ticker, fiscal_quarter, period_end_date, total_debt, cash, net_debt, fcf, fetched_at.
    """
    # 实现详见 §3 NP-d6a-2/6

def compute_supplemental_key_metrics_from_is_bs_cf(
    income_payload: dict,
    balance_payload: dict,
    cash_payload: dict,
) -> dict | None:
    """Build a partial-upsert dict for stock_key_metrics_quarterly (fcf_margin + roic only).

    Used together with KeyMetricsRepository.upsert (null-not-erase) so that
    gross_margin/op_margin/net_margin written by d3a are preserved.

    fcf_margin = freeCashFlow / revenue; null if either missing or revenue ≤ 0.
    roic       ≈ netIncome / (totalStockholdersEquity + totalDebt - cash);
                 null if any input null or denominator ≤ 0 (D097 §5).
    Output keys (exactly 5): ticker, fiscal_quarter, fcf_margin, roic, fetched_at.
    Does NOT include period_end_date or margin keys — upsert null-not-erase keeps existing values.
    """
    # 实现详见 §3 NP-d6a-5/7
```

### 1.6 PoolCacheService 集成 — 新增 `_rebuild_fundamentals` + 重构 `_rebuild_key_metrics` 返回 IS 字典

**修改** `backend/app/services/cockpit/pool_cache_service.py`：

- 顶部追加 imports：`FundamentalsRepository`、`StockFundamentalsQuarterly`、`compute_fundamentals_row_from_balance_cash`、`compute_supplemental_key_metrics_from_is_bs_cf`
- `__init__` 追加：`self._fundamentals_repo = FundamentalsRepository(db)`
- 新增 2 个并发抓取 helper（参照 `_fetch_income_statement_concurrent` 模板）：
  - `_fetch_balance_sheet_concurrent(tickers) -> dict[str, list[dict]]`
  - `_fetch_cash_flow_concurrent(tickers) -> dict[str, list[dict]]`
- **重构** `_rebuild_key_metrics` 签名从 `(tickers) -> int` 改为 `(tickers) -> tuple[int, dict[str, list[dict]]]`，返回 (upserted_count, income_statements_by_ticker)，便于 `_rebuild_fundamentals` 复用同次 IS 抓取结果（NP-d6a-4 决策）
- 新增 `_rebuild_fundamentals(tickers, income_statements_by_ticker) -> tuple[int, int]`：并发抓 BS + CF → 按 (ticker, fiscal_quarter) 配对 IS/BS/CF → 调 2 helper → 2 表 upsert → 返回 (fundamentals_upserted, supplemental_key_metrics_upserted)
- `rebuild()` 主流程改造：
  ```python
  km_upserted, is_by_ticker = self._rebuild_key_metrics(tickers)
  ...log key_metrics OK...
  fund_upserted, supp_km_upserted = self._rebuild_fundamentals(tickers, is_by_ticker)
  ...log fundamentals OK: "fundamentals upserted=N supplemental_key_metrics upserted=M elapsed=..."
  ```
- `PoolCacheResult` dataclass 不动；失败 fail-open per ticker（D097 §影响 一致）

### 1.7 Tests

**新建** `backend/tests/test_f218_d6a_fundamentals.py`：

11 个测试，按 5 个 class 分组：
- `TestFmpClientBalanceSheetQuarterly`：FMP BS client mock 测试 ×2（happy + fail-open）
- `TestFmpClientCashFlowQuarterly`：FMP CF client mock 测试 ×1（happy；fail-open 复用 BS 测试断言路径无需重复）
- `TestComputeFundamentalsRow`：纯函数测试 ×3（happy / null 字段 / 缺 id 字段返 None）
- `TestComputeSupplementalKeyMetrics`：纯函数测试 ×3（happy / roic 分母 ≤ 0 → null / fcf_margin revenue=0 → null）
- `TestFundamentalsRepository`：repo upsert + null-not-erase + get_recent ×1（合并为 1 综合测试，d3a 已验同模板）
- `TestPoolCacheFundamentalsIntegration`：pool_cache 端到端 ×1（mock IS/BS/CF 三 endpoint，验 2 表写入正确 + 既有 cockpit_pool_cache + key_metrics 路径无回归）

详见 §3。

---

## 2. 预计修改文件

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/external/fmp_client.py` | 修改 | +2 endpoint 常量 + 2 方法 `get_balance_sheet_quarterly` / `get_cash_flow_quarterly` |
| 2 | `backend/app/models/stock_fundamentals_quarterly.py` | 新建 | ORM model，按 DATA-MODEL.md 1217-1235 1:1 |
| 3 | `backend/alembic/versions/024_f218_d6a_stock_fundamentals_quarterly.py` | 新建 | `op.create_table` + UQ + index |
| 4 | `backend/app/repositories/fundamentals_repository.py` | 新建 | 3 方法：upsert / get_recent_for_ticker / delete_for_tickers_not_in |
| 5 | `backend/app/services/cockpit/pool_cache_service.py` | 修改 | +2 并发 helper + 重构 `_rebuild_key_metrics` 返回 IS 字典 + `_rebuild_fundamentals` 新方法 + `rebuild()` 流程改造 |
| 6 | `backend/app/services/cockpit/pool_helpers.py` | 修改 | +2 纯函数 `compute_fundamentals_row_from_balance_cash` / `compute_supplemental_key_metrics_from_is_bs_cf` |
| 7 | `backend/tests/test_f218_d6a_fundamentals.py` | 新建 | 11 测试 / 5 class |

**实际 7 文件**。⚠️ 超出 6 文件上限 1 个 — 详见 §5 NP-d6a-1（同 F218-d3a Path A 模式）。

> ⚠️ 注意：`backend/app/models/__init__.py` 注册条目在 §1.2 描述但未计入预计文件清单 — Path A 与 model file 合并为同一 logical change（与 d3a NP-d3a-1 同处理）。

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `FmpClient.get_balance_sheet_quarterly(symbol, limit=N)` 调用 `/stable/balance-sheet-statement`，params 含 `period=quarter` & `limit=N` & `symbol=AAPL`；成功返 list；空 / 4xx / 5xx / 网络错均 fail-open 返 `[]` | 单元（mock httpx） | pytest + monkeypatch self._http.get |
| 2 | `FmpClient.get_cash_flow_quarterly` 同 #1 但 endpoint = `/cash-flow-statement`；happy path 返非空 list | 单元 | pytest |
| 3 | 2 新方法限频复用既有 `_FmpRateLimiter`（注入路径正确，不引入独立 limiter；与 `get_income_statement_quarterly` 同 fixture）| 单元 | pytest（断言 `self._acquire` 被调用）|
| 4 | `compute_fundamentals_row_from_balance_cash` happy path：BS `{symbol:"NVDA", period:"Q2", fiscalYear:"2026", date:"2026-07-31", totalDebt:10_000_000_000, cashAndShortTermInvestments:3_000_000_000, totalStockholdersEquity:50_000_000_000}` + CF `{symbol:"NVDA", period:"Q2", fiscalYear:"2026", date:"2026-07-31", freeCashFlow:8_500_000_000}` → `{ticker:"NVDA", fiscal_quarter:"Q2 2026", period_end_date:date(2026,7,31), total_debt:10_000_000_000, cash:3_000_000_000, net_debt:7_000_000_000, fcf:8_500_000_000, fetched_at:<UTC now>}` | 单元 | pytest |
| 5 | `compute_fundamentals_row_from_balance_cash` null/缺字段安全：(a) totalDebt=None → net_debt=None；(b) cash=None → net_debt=None；(c) freeCashFlow=None → fcf=None 但 net_debt 仍可计算；(d) BS 与 CF 的 (symbol/period/fiscalYear/date) 任一不匹配 → 返 None；(e) symbol/period/fiscalYear/date 任一缺失 → 返 None | 单元（参数化） | pytest |
| 6 | `compute_supplemental_key_metrics_from_is_bs_cf` happy path：IS `{symbol:"NVDA", period:"Q2", fiscalYear:"2026", date:"2026-07-31", revenue:30_000_000_000, netIncome:16_000_000_000}` + BS（同 #4） + CF（同 #4） → `{ticker:"NVDA", fiscal_quarter:"Q2 2026", fcf_margin: 8.5/30 ≈ 0.2833…, roic: 16/(50+10-3) = 16/57 ≈ 0.2807…, fetched_at:<UTC now>}`；输出 dict 仅 5 keys（不含 period_end_date / 不含 gross/op/net_margin） | 单元 | pytest |
| 7 | `compute_supplemental_key_metrics_from_is_bs_cf` 空值与零除安全：(a) revenue=0 → fcf_margin=None（但 roic 可能仍可算）；(b) roic 分母 = totalStockholdersEquity + totalDebt - cash ≤ 0 → roic=None；(c) netIncome=None → roic=None；(d) freeCashFlow=None → fcf_margin=None；(e) 3 payload 任一 ticker/quarter 不匹配 → 返 None | 单元（参数化） | pytest |
| 8 | `FundamentalsRepository.upsert(data)` 与 `KeyMetricsRepository.upsert` 同实现模板：null-not-erase（首次 `total_debt=10B, fcf=None` → 第二次 `total_debt=None, fcf=8.5B` → 最终 `total_debt=10B`(保留) + `fcf=8.5B`(更新)）；`get_recent_for_ticker` 按 period_end_date DESC limit 截断 | 单元（sqlite in-memory） | pytest |
| 9 | `PoolCacheService._rebuild_fundamentals(tickers, is_by_ticker)` 集成：mock 2 ticker × 2 季合法 BS + CF + IS 三 endpoint → 最终 stock_fundamentals_quarterly 表 4 行 + stock_key_metrics_quarterly 表 4 行已有 d3a margin + 本次补上 fcf_margin + roic（null-not-erase 既有 margin 字段保留）；返回 `(fundamentals_upserted=4, supplemental_km_upserted=4)`；1 ticker BS 返 [] 不阻断（fundamentals 该 ticker 跳过）；1 ticker CF 返 [] 不阻断 | 集成（mock FmpClient） | pytest |
| 10 | `PoolCacheService.rebuild()` 端到端：mock 既有 cockpit_pool_cache 流程（spy_bars + closes + growth）+ d3a key_metrics 流程 + d6a fundamentals 流程并存 → 三类数据都正确写入 + system_logs 有 3 条 OK 日志（rebuilt N=... / key_metrics upserted=... / fundamentals upserted=N supplemental_key_metrics upserted=M）+ 既有 cockpit_pool_cache 行 rs_percentile/ma50/last_close 未受影响 | 集成 | pytest |
| 11 | Alembic 024 双向跑通：`uv run alembic upgrade head` 后 stock_fundamentals_quarterly 表存在 + 字段类型正确（total_debt/cash/net_debt/fcf = BigInteger nullable，period_end_date = Date NOT NULL，fetched_at = DateTime NOT NULL）；`uv run alembic downgrade -1` 后表删除；再 `upgrade head` 幂等 | 集成 | alembic CLI |

预期测试数：**11 个**（单文件 `test_f218_d6a_fundamentals.py`，按 5 class 分组）。

---

## 4. Evaluator 自检清单

- [ ] 11 个新测试全部通过（`cd backend && uv run pytest tests/test_f218_d6a_fundamentals.py -v`）
- [ ] d1/d2/d3a/d3b/d4/d5 既有 75 测试仍全绿（`uv run pytest tests/test_repricing_trigger_*.py tests/test_f218_d3a_*.py -v`）— pool_cache 改动不应影响这些
- [ ] 全量后端回归通过（`uv run pytest`）— 允许预先存在的 9 个 failure（d5 baseline 一致），不得新增
- [ ] Alembic 024 双向跑通（见 #11）
- [ ] `StockFundamentalsQuarterly` model 字段 / 类型 / UQ / index 与 DATA-MODEL.md §StockFundamentalsQuarterly 1217–1235 行 1:1（不增减字段）
- [ ] `get_balance_sheet_quarterly` / `get_cash_flow_quarterly` 签名 = `(self, symbol: str, limit: int = 8) -> list[dict[str, Any]]`，与 `get_income_statement_quarterly` 风格 1:1
- [ ] FMP endpoint 常量 `FMP_EP_BALANCE_SHEET` / `FMP_EP_CASH_FLOW` 在 fmp_client.py 顶部声明区（与 `FMP_EP_INCOME_STATEMENT` 齐列）
- [ ] 2 helper 是模块级纯函数（不挂 service class）；d6b detector 直接 import 复用
- [ ] PoolCacheService 改动遵循"加"为主 + 1 处必要重构（`_rebuild_key_metrics` 返回值从 int 改 tuple，因 d6a 需要 IS 字典）；既有 cockpit_pool_cache 写入路径不变
- [ ] `_rebuild_fundamentals` 失败 fail-open per ticker：BS / CF / IS 任一返 [] 该 ticker 跳过，整体不阻断
- [ ] FMP rate limiter 复用既有 token bucket（不引入第二/三个 limiter；并发 worker 数复用 `_FMP_MAX_WORKERS=6`）
- [ ] models/__init__.py 注册条目存在（Path A）
- [ ] **null-not-erase 关键验证**：d6a 跑完后，d3a 已写的 gross/op/net_margin 没有任何行被改成 NULL（测试 #9 涵盖；通过 SQL 直接 SELECT 验证）

### 代码质量检查
- [ ] `_rebuild_fundamentals` 函数长度 ≤ 50 行（拆分到 `_fetch_balance_sheet_concurrent` / `_fetch_cash_flow_concurrent` helper + 内联 pairing 逻辑可 ≤ 50 行）
- [ ] 无硬编码魔法值（`limit=8` / `_FMP_MAX_WORKERS` / fiscal_quarter 分隔符 " " 全部作为常量或入参）
- [ ] 2 helper 函数内无副作用（无 logger / 无 DB 调用，纯映射）
- [ ] 无注释掉的代码块 / 死 import / 未使用变量
- [ ] context7 已查询 SQLAlchemy 2.0 `sqlite_insert.on_conflict_do_update` 语法（KeyMetricsRepository 已用同模板，本 sprint 复制时如需调整再查）— **如复制 d3a 实现无改动则跳过查询**

### 回归测试
- [ ] 后端全量 `uv run pytest` 通过（允许 9 pre-existing failures，不得新增）
- [ ] cockpit/setup/regime/pool_cache/repricing_trigger（d1-d5）未受 import / 字段命名 / FMP rate limiter / pool_cache 重构影响

---

## 5. 关键设计决策（执行前确认）

| # | 议题 | 推荐方案 | 备选方案 |
|---|------|---------|---------|
| **NP-d6a-1** | 文件预算 — 实际 7 文件超 6 上限 1 个 | **Path A：申请超额授权 7 文件（推荐，与 F218-d3a / F217-c2c 同模式）**：§1.2 model file 与 §1.2 models/__init__.py 注册合并为同一 logical change（count=7，含 1 个 __init__.py 1-line edit）；wip commit 合并提交保留原子性。 | **Path B**：把 §1.6 pool_cache 集成 + §1.5 helper 推迟到 d6b（d6b 同时实装 detector + 数据接线），d6a 只负责 plumbing（fmp_client + model + __init__ + alembic + repo + test = 6 文件），但 d6b 文件数因此涨至 ~5 涨幅大且打破"d6a 数据层 / d6b 检测层"清晰切分。 **Path C**：跳过 models/__init__.py 注册（违反既有 22 个 model 注册的项目惯例，d6b 须 chore commit 补，得不偿失）。 |
| **NP-d6a-2** | FCF 计算来源 — D097 §5 公式 vs DATA-MODEL.md §1203 `freeCashFlow` 字段 | **推荐：FMP `freeCashFlow` 字段直接取（更稳，DATA-MODEL §1203 原文）**：FMP 自身的 `freeCashFlow` = OCF + capex（capex 是负值，加号）— 与 D097 §5 公式等价；直接取省 1 步 service 层计算 + 避免 OCF / capex 字段命名变动风险；可观测性更好（出错时直接对照 FMP 原始字段）。 | (a) D097 §5 字面：service 层算 `netCashProvidedByOperatingActivities + investmentsInPropertyPlantAndEquipment`，更显式但 +2 字段命名依赖；若 FMP 改 capex 字段名我们能更早发现（但 freeCashFlow 字段如果消失我们也能更早发现，对称）。 / (b) 双源策略：优先 `freeCashFlow`，缺失时 fallback 到 OCF+capex；额外复杂度无明显收益，否决。 |
| **NP-d6a-3** | FMP client 错误处理风格 | **fail-open 返 `[]`（推荐）**：与 d3a `get_income_statement_quarterly` + D079 `get_financial_growth` 一致；单 ticker 失败不阻断 ~50 ticker 批量。 | 抛 httpx 原始异常（caller 须 try/except 不一致）。 |
| **NP-d6a-4** | `_rebuild_key_metrics` 是否重构返回值（int → tuple[int, dict]） | **是 — 重构返回 IS 字典，传给 `_rebuild_fundamentals` 复用（推荐）**：避免 d6a 重复抓 IS（quota / 时间窗口一致性）；`_rebuild_key_metrics` 与 `_rebuild_fundamentals` 在同次 rebuild 共享 IS 数据；签名变 1 处但调用方只有 rebuild() 内部。 | (a) `_rebuild_fundamentals` 内部独立再抓 IS（quota 浪费 + 时间窗口分裂风险，否决）/ (b) 把 IS 字典挂到 PoolCacheService 实例属性 `self._last_is_by_ticker`（隐式状态污染，单测难，否决）/ (c) `_rebuild_key_metrics` 仍返 int，新增 `_fetch_income_statement_concurrent` 在 rebuild() 顶部调用一次后传给 2 个 rebuild 步骤（更显式分离，但 rebuild() 函数行数增加且双方耦合到外部状态）— 备选，作 Path B。 |
| **NP-d6a-5** | `compute_supplemental_key_metrics_from_is_bs_cf` 输出键集 | **仅 5 keys：ticker / fiscal_quarter / fcf_margin / roic / fetched_at（推荐）**：null-not-erase 语义下，省略 gross/op/net_margin 才能保证不擦 d3a 已写值；period_end_date 在 d3a 行已存在不需再写。 | (a) 输出全 10 keys（含 gross/op/net_margin=None） — 即便依赖 null-not-erase upsert 也擦不掉，但语义混乱且增加测试断言量 / (b) 仅 4 keys（不含 fetched_at）— fetched_at 仍应刷新表示该字段最新计算时间。 |
| **NP-d6a-6** | BS 中 `cash` 字段名 — `cashAndShortTermInvestments` vs `cashAndCashEquivalents` | **`cashAndShortTermInvestments`（推荐，D097 §5 原文）**：包含可快速变现的短期投资，更准确反映 roic 分母中的"非营运资本"扣除；FMP /stable/balance-sheet-statement 返回此字段。 | (a) `cashAndCashEquivalents`：定义更窄，会高估 roic 分母（漏减短期投资部分） / (b) 两者求和：若 FMP 同时返回二者会重复计算（FMP `cashAndShortTermInvestments` 本身已含 `cashAndCashEquivalents`） — 否决。**实施提示**：实际编码时 helper 兜底逻辑：优先用 `cashAndShortTermInvestments`，若 FMP 该字段缺失则 fallback 到 `cashAndCashEquivalents`，全缺再返 null。 |
| **NP-d6a-7** | `roic` 分母 ≤ 0 时的处理 | **返 null（推荐，D097 §5 明示）**：当总资本结构异常（高杠杆 + 低权益 → 分母为负）roic 无业务意义；返 null 让 T2 detector 跳过该季度判定（不影响其他正常季度）。 | (a) 0.0 — 误导信号 / (b) abs(分母) — 数学上无依据 / (c) 抛错 — 违反 fail-open。 |
| **NP-d6a-8** | `_rebuild_fundamentals` 并发方式 | **复用 `ThreadPoolExecutor(max_workers=_FMP_MAX_WORKERS=6)`（推荐）**：与 d3a `_rebuild_key_metrics` + 既有 `_fetch_bars_concurrent` 同模式；BS 和 CF 在同 ticker 内可并行（独立 future）；rate limiter 是模块级单例，并发不撞限。 | (a) 串行（慢 6×，50 ticker × 2 endpoint × ~150ms ≈ 15s） / (b) BS+CF 同 future 内串行（实现简单但损失 worker 时间）— 备选可接受。 |

### 推荐理由速览

- **NP-d6a-1 7 文件超额（Path A 推荐）**：F218-d3a 已先例（7 文件超 6），用户已批准同 Path A；本 sprint 与 d3a 文件分布几乎 1:1 对应（FMP client +endpoints / model + __init__ 注册 / alembic / repo / helper / pool_cache 集成 / test），保持模板一致便于跨 sprint review。Path B 把 pool_cache 集成推 d6b 看似减 d6a 文件数但破坏"数据层 / 检测层"切分，d6b 还要因此处理 detector + 数据接线 2 件事。
- **NP-d6a-2 freeCashFlow 字段直接取**：DATA-MODEL.md §1203 原文锁死，D097 §5 公式与字段值在 FMP 内部本就等价；service 层算的小好处不抵 +1 步出错可能。
- **NP-d6a-3 fail-open**：与 d3a NP-d3a-2 + D079 一致；不该 sprint 翻案。
- **NP-d6a-4 重构返回 IS 字典**：避免重复 quota 调用是首要；rebuild() 内部签名变化影响面零（无外部 caller 改动）；测试 #9 # 10 验证该路径。
- **NP-d6a-5 仅 5 keys**：null-not-erase 语义最关键的不变量 — 输出键集明确等于"本 sprint 新写的字段集"，避免任何意外擦除既有 margin。
- **NP-d6a-6 cashAndShortTermInvestments**：D097 §5 原文一致；fallback `cashAndCashEquivalents` 兜底保证 FMP 字段缺失时仍能算出 roic（非主路径）。
- **NP-d6a-7 分母 ≤ 0 → null**：D097 §5 原文；null 与 fail-open 一致语义。
- **NP-d6a-8 6 worker 并发**：与既有所有 pool_cache 并发模式 1:1；rate limiter 自动节流。

---

## 6. 不在范围（本 sprint 排除）

- ❌ `_detect_balance_inflection` 真实实装（d6b — 读 stock_fundamentals_quarterly 判定 "净负债下降 ≥5% × 2 季 OR FCF 从负值切为连续 2 季正"）
- ❌ T5 detector confidence / evidence_json 设计（d6b）
- ❌ d6b detector 历史回测验证 SRS 案例（acceptance / d7b 收官时统一做）
- ❌ 任何前端文件（widget / API client / design-spec / tokens / data-mapping / component-plan）（d7b）
- ❌ refresh_job.py cron 注册（d7a — 22:40 UTC RepricingTriggerService 调度；本 sprint 复用既有周一 06:30 UTC pool_cache cron）
- ❌ router + 2 endpoint（d7a）
- ❌ DECISIONS.md 追加（NP-d6a-1~8 是实施级决策由本 contract 承载；D097 已含本 sprint 所需全部决策，本 sprint 不产生新 DXXX）
- ❌ ARCHITECTURE.md / DATA-MODEL.md / API-CONTRACT.md 任何修改（4 文档 status 在 2026-05-18 D097 修正同步 confirmed，本 sprint 严格落地无新增 drift）
- ❌ 历史数据回填脚本（首次 deploy 后第一次周一 06:30 UTC cron 跑完即填充；不需要单独脚本）
- ❌ delete_for_tickers_not_in 调用点挂载（实装方法但保留未挂，同 d3a NP-d3a-5）

---

## 7. 用户待确认

1. **NP-d6a-1 ~ NP-d6a-8** 八项决策：全部按推荐？还是有需要调整的？特别注意：
   - **NP-d6a-1 文件预算**（推荐 Path A：申请超额授权 7 文件，与 d3a 同模式）
   - **NP-d6a-2 FCF 来源**（推荐 FMP `freeCashFlow` 字段直接取 vs D097 §5 字面公式 — 二者等价，前者更稳）
   - **NP-d6a-4 重构 `_rebuild_key_metrics` 返回值**（int → tuple — 仅影响 rebuild() 内部，无外部 caller）
2. **Contract 整体是否同意进入 Generator 模式开发**？

确认后我会：
1. 更新 features.json：`F218-d6a` phase `design_needed` → `contract_agreed`；`_pipeline_status.active_sprint_phase` → `contract_agreed`
2. 追加 F218 iteration_history 一条 `contract_agreed` 记录（subtask=F218-d6a，date=2026-05-20）
3. 更新 claude-progress.txt
4. 生成 SESSION-HANDOFF.md（含 d6a 7 步开发顺序：fmp_client +2 方法 → model + __init__ 注册 → alembic 024 → repository → 2 helper → pool_cache 集成（含 `_rebuild_key_metrics` 重构） → 11 测试，及恢复指令）
5. **强制停止本 session**（feature-dev skill 铁律），输出新 session 恢复指令
