# Sprint Contract：F205-c PoolService + GET /api/cockpit/pool（漏斗组装 + endpoint）

> 日期：2026-04-27 | 状态：草案
> 父 Feature：F205 Pool Builder Widget（v1.9 Cockpit P1）
> 前置 Sprint：F205-a ✅ done（universe 扩字段） / F205-b ✅ done（FMP financial-growth + pool_helpers 5 个纯函数）
> 引用文档：
>   - `docs/系统设计/API-CONTRACT.md` §GET /api/cockpit/pool（行 1322–1387）
>   - `docs/系统设计/DATA-MODEL.md` §MarketScanUniverse / §MarketBreakoutScan / §SetupSnapshot / §EarningsEvent / §Stock
>   - `docs/系统设计/DECISIONS.md` D034（FMP 主源）/ D044（FMP 限流）/ D055（DailyPayloadCache 模式）/ D078（universe 字段）/ D079（pool helpers + fail-open）
>   - `backend/app/services/cockpit/pool_helpers.py`（F205-b 交付，本 sprint 消费）
>   - `backend/app/external/fmp_client.py::get_financial_growth` / `::get_daily_bars`

---

## 0. Sprint 定位

F205 拆 4 子 sprint：F205-a ✅ → F205-b ✅ → **F205-c（本 sprint）** → F205-d（前端）。

本 sprint 把 F205-b 的 building blocks 编排成完整漏斗，对外暴露 `GET /api/cockpit/pool` HTTP endpoint。**不**碰前端，**不**改 setup_service.py，**不**新建数据库表/迁移，**不**重构 F106 scanner。

---

## 1. 本次实现范围

### 1.1 新建 PoolService

文件：`backend/app/services/cockpit/pool_service.py`

职责：5 层漏斗编排（tradable → trend → rs → fundamental → action），返回 `{funnel, items}` 结构。

**漏斗各层定义（关键设计决策，需用户确认）**：

| 层 | 数据源 | 过滤条件 |
|---|--------|---------|
| **tradable** | `market_scan_universe` 表 | `market_cap >= marketCapMin` AND `last_price >= priceMin` AND `last_price * last_volume >= advMin`（**单日 dollar volume 代理**，见决策 §2.1）AND `sector ∈ sectors`（若指定） |
| **trend** | `market_breakout_scans` 最新快照 | tradable ∩ 最新 breakout 扫描中**任一 signal_type** 出现的 ticker（**视为已通过 F106 趋势过滤**，见决策 §2.2）。`trendScoreMin` 参数本 sprint **忽略**（见决策 §2.2） |
| **rs** | FMP `get_daily_bars`（**6 并发**，见决策 §2.3）+ `market_indices` SPY closes | 对 trend 子集每个 ticker：拉 250d closes → `compute_return_ratio_250d` → `compute_rs_percentile_map` → 保留 `rs_percentile >= rsPercentileMin` |
| **fundamental** | FMP `get_financial_growth`（**6 并发**） | 对 rs 子集每个 ticker：`extract_revenue_growth_yoy_pct` → `passes_fundamental_sanity(growth, revenueGrowthYoyMin)`（None → fail-open，D079） |
| **action** | fundamental 子集 + setup_snapshots（仅 watchlist） | 取前 `limit` 条；按 RS percentile 降序排序 |

**并发实现**：FMP 调用走 `concurrent.futures.ThreadPoolExecutor(max_workers=6)`，与 `_FmpRateLimiter.CONCURRENCY_LIMIT=6` 对齐。限流由 fmp_client 内置 token bucket + semaphore 兜底，service 层不重复实现限流。

**规模保护**：trend 子集 ticker 数若 > `POOL_TREND_CAP`（默认 200），按 universe.market_cap 降序前 200 截断进入 RS 层（见决策 §2.3）。

**items 字段映射**（对照 API-CONTRACT.md 第 1356–1369 行）：

| 字段 | 来源 |
|------|------|
| `ticker` | universe.ticker |
| `name` | universe.company_name |
| `sector` | universe.sector |
| `price` | universe.last_price |
| `trendScore` | setup_snapshots.trend_score（仅 watchlist；非 watchlist → `null`） |
| `rsPercentile` | 本次计算结果（pool 子集内 rank） |
| `setupType` | setup_snapshots.setup_type（仅 watchlist；非 watchlist → `null`） |
| `distanceToPivotPct` | setup_snapshots.distance_to_entry_pct（仅 watchlist；非 watchlist → `null`） |
| `distanceTo50maPct` | `compute_distance_to_50ma_pct(close, ma50)`（ma50 = 250d 序列后 50 日均值） |
| `earningsDate` | earnings_events.earnings_date（最近未来一次；无 → `null`） |
| `daysUntilEarnings` | `(earningsDate - today).days`（无 → `null`） |
| `revenueGrowthYoy` | F205-b extract_revenue_growth_yoy_pct 结果 |
| `suggestedAction` | setup_snapshots.suggested_action（仅 watchlist；非 watchlist → `"watch"` 默认） |
| `inWatchlist` | `ticker ∈ {s.ticker for s in stocks where is_active=true}` |

### 1.2 新建 router

文件：`backend/app/routers/cockpit/pool.py`

`GET /api/cockpit/pool` — 接受 API-CONTRACT.md 定义的所有 query params（`marketCapMin / priceMin / advMin / trendScoreMin / rsPercentileMin / revenueGrowthYoyMin / sectors / setupTypes / limit`），调用 `PoolService.get_pool(params)`，返回 `PoolResponse`。

参数校验沿用现有 setup router 的 `APIError("VALIDATION_ERROR", …, 422)` 风格（参考 `backend/app/routers/cockpit/setup.py`）。

### 1.3 新建 Pydantic schemas

文件：`backend/app/schemas/cockpit/pool.py`

```python
class PoolFunnel(BaseModel):
    tradable: int
    trend: int
    rs: int
    fundamental: int
    action: int

class PoolItem(BaseModel):
    ticker: str
    name: str
    sector: str | None
    price: float | None
    trendScore: int | None
    rsPercentile: float
    setupType: str | None
    distanceToPivotPct: float | None
    distanceTo50maPct: float | None
    earningsDate: date | None
    daysUntilEarnings: int | None
    revenueGrowthYoy: float | None
    suggestedAction: str | None
    inWatchlist: bool

class PoolData(BaseModel):
    funnel: PoolFunnel
    items: list[PoolItem]

class PoolResponse(BaseModel):
    data: PoolData
    message: str = "success"
```

字段命名严格按 API-CONTRACT.md（camelCase 在 schema/JSON 层）。

### 1.4 注册 router

修改 `backend/app/routers/cockpit/__init__.py` 加一行 `router.include_router(pool_router)`。**不动** `backend/app/main.py`（前缀 `/api/cockpit` 已在 main.py 设置）。

### 1.5 测试覆盖

- 服务单元测试（`backend/tests/test_pool_service.py`）：mock repos + FMP client，覆盖各漏斗层 + 边界条件
- Router 集成测试（`backend/tests/test_cockpit_pool_router.py`）：用 FastAPI TestClient + sqlite session fixture 走完整路径

详见 §3。

### 1.6 决策落档

`docs/系统设计/DECISIONS.md` 追加 **D080**：
- ADV proxy = `last_price * last_volume`（单日，非 20 日均），技术债标注，待 F205-x 重构
- Trend filter = market_breakout_scans 出现 + 忽略 `trendScoreMin` 参数（trend_score 仅 watchlist 可得，pool 范围用"被 F106 扫到"作为二元代理）
- POOL_TREND_CAP = 200（FMP 调用上限保护，避免 trend 层 800+ ticker 触发限流风暴）
- FMP 调用走 `ThreadPoolExecutor(max_workers=6)`（与 `_FmpRateLimiter.CONCURRENCY_LIMIT` 对齐），限流仍由 fmp_client 进程级 singleton（token bucket 300 rpm + semaphore 6 in-flight）兜底，service 层不重复实现；`max_workers=6` 接受"pool 请求期间挤占其他 FMP 消费者"的取舍
- 非 watchlist ticker 的 setupType / trendScore / distanceToPivotPct 返回 null（setup_snapshots 仅覆盖 watchlist；扩展到 pool 全集需要单独 sprint）

---

**明确排除（本次不做）**：

- ❌ 不新建数据库表 / migration（pool 调用都是即时计算，无持久化）
- ❌ 不实现 DailyPayloadCache 类的持久化缓存（请求级 in-memory 字典即可；持久化缓存归 F205-x）
- ❌ 不引入 asyncio（FmpClient 是同步的；并发用 ThreadPoolExecutor，详见 §2.3）
- ❌ 不在 service 层重新实现限流（沿用 fmp_client 内置 token bucket + semaphore）
- ❌ 不为非 watchlist ticker 计算 trend_score / setup_type（需要 setup_service 改造，超范围）
- ❌ 不动前端
- ❌ 不修改 F205-b pool_helpers.py / fmp_client.get_financial_growth（已 done）
- ❌ 不动 setup_service.py / market_scanner_service.py（避免 F202-a / F106 回归）
- ❌ 不实现 ADV 20d 真值（用单日 proxy；列入技术债）

---

## 2. 关键决策（须用户确认）

### 2.1 ADV 实现：单日代理 vs 20d 真值

**选择**：`last_price * last_volume`（单日 dollar volume，从 universe 表读，0 IO 成本）

**理由**：
- 真 20d ADV 需要拉 20 天 bars per universe ticker（≥1500 ticker × 20d = 大量 FMP 调用），冷启动时间不可接受
- `last_volume` 在 F205-a 已经存进 universe，单日量虽然有噪音但作为 tradable 层粗筛**够用**
- 用户期望：默认 `advMin=20M`，单日量本就常超过 20d 均值的 1.5x，单日代理偏严而非偏松，**不会漏掉真正活跃 ticker**

**技术债**：D080 记录"ADV 单日代理"，建议 F205-x 在 universe 表加 `avg_dollar_volume_20d` 字段并由 `universe_refresh_service` 在每日刷新时计算。

### 2.2 Trend filter：忽略 trendScoreMin 参数

**选择**：trend 层 = "tradable ∩ 最新 market_breakout_scans 中出现"，**忽略** `trendScoreMin` query param。

**理由**：
- `trend_score (0-5)` 在 `setup_snapshots` 表里只对 watchlist 计算（F202-a 范围）。pool 范围（数百 ticker）若要现算 trend_score，需要给每个 ticker 拉 200d bars + 计算 5 阶 MA ladder，相当于把 setup_service 改造成 population-agnostic。
- F106 扫描器已经过 ma150 / slope / volume 阈值过滤过 universe，被扫到的 ticker = "趋势良好"。把"在最新 breakout_scans 里出现"作为二元 trend filter，是工程性价比最高的代理。
- API-CONTRACT.md 写的 `trendScoreMin` 参数依然接受 + 校验范围（不报错），但 service 内部 **不使用**。响应 `items[].trendScore` 仅对 watchlist ticker 填实值，其他返回 null。
- 真正的 pool-wide trend_score 改到独立 sprint（F205-x 或 F205-d 之后），届时需要扩 setup_service 或新 service。

**风险**：若 F106 扫描参数收紧（比如某天 breakout_scans 只剩 50 行），pool 漏斗"trend"层会大幅缩水。已知接受。

### 2.3 并发调用 + POOL_TREND_CAP = 200

**选择**：FMP 调用走 `ThreadPoolExecutor(max_workers=6)` 并发；trend 子集若 > 200 ticker，按 universe.market_cap 降序保留前 200 进入 RS 层。

**为什么并发（而非串行）**：
- `FmpClient` 类注释明确"Thread-safe FMP client"；`_FmpRateLimiter` 用 `threading.Lock` 保护 token bucket，`BoundedSemaphore(6)` 限制 in-flight = **基础设施就是为并发设计的**（D044）
- 限流仍由 fmp_client 内置机制兜底（token bucket 稳态 5 calls/s = 300 rpm，burst 50），service 层**不重复**实现限流

**全局共享限流器（关键约束）**：
- `default_rate_limiter()` 是**进程级 singleton**（fmp_client.py:119–130）。整个 backend 进程内 ~15 个 FMP 消费者（market_refresh / data_refresh / news / chart / scanner / setup / pool …）**共用同一个 token bucket + 同一个 semaphore**。
- 含义：PoolService 的 `max_workers=N` 不是"独占 N 个 FMP 槽"，而是"**最多向全局 6 槽 semaphore 申请 N 个**"。其他 service 同时在调 FMP 时，pool 的有效并发会自动降级；反之，pool 请求期间也会自然限制其他 service 的吞吐。
- 这是"安全 by 设计"：pool 不可能因为开太多线程把 FMP 限额打爆 —— limiter 兜住了。但要选 max_workers 时考虑"是否愿意在 pool 请求期间挤占其他 service 的 FMP 配额"。

**max_workers 选择**：`max_workers=6`（与 `CONCURRENCY_LIMIT` 对齐）

| 取值 | 行为 | 评估 |
|---|---|---|
| 6（推荐）| pool 请求期间最多吃满全局 6 槽，**主动**挤占其他后台调用 | pool 是用户主动触发查询，用户在等结果；定时任务（每日 universe_refresh）撞车概率低，撞车时 refresh 慢 30s 可接受 |
| 3–4 | 主动让一半槽给其他 service | pool 耗时近乎翻倍（60–80s），逼近前端 timeout，得不偿失 |
| >6 | 多余线程在 semaphore 上空转 | 无收益，徒增线程开销 |

**结论**：`max_workers=6` 接受"pool 请求高优先级、期间独占大部分 FMP 资源"的取舍；任务调度层面的协调（避免 pool 和定时 refresh 撞车）不在本 sprint 范围。

**为什么需要 POOL_TREND_CAP**：
- 即使 6 并发，稳态吞吐受 token bucket 限速 5 calls/s = 300 rpm
- 单请求 200 ticker × 2 调用 = 400 calls：burst 吃 50 + 350 × 0.2s 稳态 ≈ 30–40s（vs 串行 ~80s，约 2× 提升）
- 不截断的话 800 ticker × 2 = 1600 calls / ~5 min，前端不可能等
- market_cap 降序截断：大盘股优先，符合 P1 用户场景（慢交易找候选）

**实现细节**：
- `POOL_TREND_CAP = 200` 和 `_FMP_MAX_WORKERS = 6` 作为模块级常量放在 `pool_service.py` 顶（**不**进 cockpit_params.py，避免凭空扩 section 触发 6 文件外的扩展）
- 用 `concurrent.futures.ThreadPoolExecutor` 同步上下文管理器（不引入 asyncio，FmpClient 是同步的）
- FMP 单 call 异常（HTTPError / 超时）由 fmp_client 内吞掉返回 None / 空，service 层 `as_completed` 收集结果时按 ticker 跳过（不让一个 ticker 的失败炸掉整个 pool 请求）
- 截断时记录 SystemLog WARN（"pool trend cap hit, dropped N tickers"）

**性能预期**：
| trend 子集大小 | 估算耗时（含 latency 抖动） |
|---|---|
| 50 | ~5–10s |
| 100 | ~15–25s |
| 200（cap）| ~30–40s |

### 2.4 setup-related 字段对非 watchlist ticker 返回 null

**选择**：`setupType / distanceToPivotPct / trendScore / suggestedAction` 仅对 watchlist ticker 从 `setup_snapshots` 读取；非 watchlist 全部返回 `null`（`suggestedAction` 默认 `"watch"`）。

**理由**：与 §2.2 同源 — setup_snapshots 仅覆盖 watchlist，扩到 pool 范围需要独立 sprint。前端 F205-d 在表格层把 null setupType 显示为 "—"。

### 2.5 缓存策略：仅请求级 in-memory，不落 DB

**选择**：本 sprint **不**实现持久化缓存。同一请求内 SPY closes 取一次后复用；FMP 调用按 ticker 串行；下一次请求重新拉。

**理由**：
- 持久化缓存（DailyPayloadCache 类）会引入新表 + TTL 管理 + 失效策略，远超 6 文件
- 用户场景：pool 是手动触发查询（widget 拉一次看结果），非高频；缓存收益不大
- 列入技术债：F205-x 视性能再决策

---

## 3. 预计修改文件

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/services/cockpit/pool_service.py` | 新建 | `PoolService` 类 + `get_pool(params: PoolParams) -> dict`；漏斗 5 层编排 |
| 2 | `backend/app/routers/cockpit/pool.py` | 新建 | `GET /api/cockpit/pool` endpoint + 参数校验 |
| 3 | `backend/app/routers/cockpit/__init__.py` | 修改 | 注册 pool_router 一行 |
| 4 | `backend/app/schemas/cockpit/pool.py` | 新建 | `PoolFunnel / PoolItem / PoolData / PoolResponse` Pydantic models |
| 5 | `backend/tests/test_pool_service.py` | 新建 | 单元测试，mock repos + FMP，覆盖漏斗各层 + 边界 |
| 6 | `backend/tests/test_cockpit_pool_router.py` | 新建 | 集成测试，TestClient 走完整路径 |

**附加文档更新**（不计入 6 文件硬上限）：
- `docs/系统设计/DECISIONS.md` — 追加 D080（4 项决策）
- `docs/系统设计/API-CONTRACT.md` — **不动**（已含 GET /api/cockpit/pool 完整定义；本 sprint 仅按其实现，无新增字段）

文件计数：**6/6**（在硬上限内，不需要拆分）

---

## 4. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | universe 空（冷启动）→ 返回 `funnel={tradable:0, trend:0, rs:0, fundamental:0, action:0}, items=[]`，HTTP 200 | 集成 | TestClient + 空 DB fixture |
| 2 | universe 有 100 个 ticker，无 breakout_scans 行 → tradable>0, trend=0, rs=0, fundamental=0, action=0 | 集成 | TestClient + fixture |
| 3 | universe 100，breakout_scans 50（其中 30 个在 universe 内）→ tradable=N（按市值过滤后），trend=30 | 集成 | TestClient + fixture |
| 4 | `marketCapMin=100B` → 仅市值 ≥1000 亿的 ticker 进 tradable | 集成 | TestClient + fixture |
| 5 | `priceMin=50` → 仅 last_price ≥ 50 的进 tradable | 集成 | TestClient + fixture |
| 6 | `advMin=50M`（默认 20M）→ 仅 last_price × last_volume ≥ 50M 的进 tradable | 集成 | TestClient + fixture |
| 7 | `sectors=XLK,XLY` → 仅 sector ∈ {XLK, XLY} 的 ticker 进 tradable | 集成 | TestClient + fixture |
| 8 | `rsPercentileMin=80` → 只保留 rs_percentile ≥ 80（pool 子集内 rank） | 单元 | mock FMP closes |
| 9 | `revenueGrowthYoyMin=15.0` → 只保留 growth ≥ 15%；FMP 返回 None 的 ticker fail-open（保留） | 单元 | mock FMP financial_growth |
| 10 | trend 子集 = 250 ticker → 截断到 POOL_TREND_CAP=200，按 market_cap 降序，前 200 进入 RS 层 | 单元 | mock breakout_repo |
| 10b | RS 层和 fundamental 层用 `ThreadPoolExecutor(max_workers=6)` 并发调用 FMP；30 个 ticker mock latency 200ms 时，总耗时 < 串行（200×30=6s）的 50% | 单元 | mock FMP + sleep + 计时断言 |
| 10c | 并发调用中某 ticker FMP 返回 None / 抛被 fmp_client 吞掉的异常 → 该 ticker 在 RS 层 ratio=None（视为底部），fundamental 层 fail-open，**不**导致整个 pool 请求失败 | 单元 | mock FMP per-ticker raise |
| 11 | items 排序：按 rsPercentile 降序 | 集成 | TestClient + fixture |
| 12 | `limit=10` → items 长度 ≤ 10；funnel.action 仍是截断**前**的真实 fundamental ∩ items 数 | 集成 | TestClient + fixture |
| 13 | watchlist ticker（stocks.is_active=true）→ items 中 inWatchlist=true，setupType / suggestedAction / trendScore 从 setup_snapshots 读 | 集成 | fixture 含 stocks + setup_snapshots |
| 14 | 非 watchlist ticker → inWatchlist=false，setupType=null, trendScore=null, suggestedAction="watch" | 集成 | fixture |
| 15 | earnings_events 有该 ticker 未来 30 天的事件 → earningsDate / daysUntilEarnings 非空；无 → 均为 null | 集成 | fixture |
| 16 | distanceTo50maPct = `compute_distance_to_50ma_pct(close, ma50)`，ma50 = closes[-50:] 均值 | 单元 | mock FMP bars |
| 17 | FMP `get_daily_bars` 抛异常 → 该 ticker 跳过 RS 层（视为 RS=None → percentile=底部） | 单元 | mock FMP raise |
| 18 | FMP `get_financial_growth` 返回 None → 该 ticker 通过 fundamental 层（fail-open D079） | 单元 | mock FMP None |
| 19 | 参数 `limit=300` → 422 VALIDATION_ERROR（API-CONTRACT.md 上限 200） | 集成 | TestClient |
| 20 | 参数 `rsPercentileMin=120` → 422 VALIDATION_ERROR（合理 0–100） | 集成 | TestClient |
| 21 | 参数 `sectors=XYZ`（无效 sector ETF）→ 仍接受（按字符串过滤，结果空），不报错 | 集成 | TestClient |
| 22 | 全量回归：`pytest backend/` 总数 = 758（F205-b 后基线）+ 新增用例数，无新失败、无原失败 | 回归 | pytest |

---

## 5. Evaluator 自检清单

### 功能正确性
- [ ] `pytest backend/tests/test_pool_service.py` 全部通过
- [ ] `pytest backend/tests/test_cockpit_pool_router.py` 全部通过
- [ ] 全量回归 `pytest backend/` 通过；758 → 758 + N（无新失败）
- [ ] `GET /api/cockpit/pool` 默认参数 + 真实 fixture 数据走通完整漏斗，5 层 funnel count 单调递减
- [ ] FMP 任一调用失败（HTTPError / 超时 / 429 已被 F205-b 装饰器吃掉返回 None）下，pool endpoint 仍返回 200，对应 ticker 在该层降级（不抛异常给 client）

### 设计纯净度
- [ ] `pool_service.py` 只 import：sqlalchemy.orm.Session、F205-b helpers、existing repos、FmpClient、`concurrent.futures`、cockpit_params（如需）、stdlib
- [ ] **不**修改 `pool_helpers.py`（diff 验证）
- [ ] **不**修改 `setup_service.py` / `market_scanner_service.py` / `cockpit_params.py`（diff 验证）
- [ ] **不**修改 `backend/app/main.py`（router 注册走 cockpit/__init__.py）
- [ ] 所有响应字段命名符合 API-CONTRACT.md camelCase（`rsPercentile / inWatchlist / earningsDate / daysUntilEarnings / suggestedAction / distanceToPivotPct / distanceTo50maPct / setupType / revenueGrowthYoy / trendScore`）

### 命名 / 文档规范
- [ ] PoolService 类方法 snake_case，schemas 字段 camelCase（FastAPI alias 或 model_config 控制）
- [ ] PoolService 主方法（如 `get_pool`）有 1-2 行 docstring 说明漏斗顺序 + 截断点
- [ ] router endpoint 函数有 docstring 注明 API-CONTRACT.md 引用

### 决策记录
- [ ] DECISIONS.md 已追加 D080，含 4 项决策（ADV 代理 / 忽略 trendScoreMin / POOL_TREND_CAP / 非 watchlist null 字段）
- [ ] D080 中明确"ADV 单日代理"和"非 watchlist null setup"是已知技术债，dedup 推到 F205-x

### 代码质量
- [ ] Lint 通过（项目已配置的 linter）
- [ ] 无 print / pdb / 调试代码
- [ ] 无未引用 import / 死代码
- [ ] POOL_TREND_CAP / 默认参数等魔法值写为模块级常量（不内联函数体）
- [ ] PoolService 单一方法长度 ≤ 50 行；超过须拆私有方法（漏斗各层用私有方法 `_filter_tradable / _filter_trend / _compute_rs_layer / _filter_fundamental / _build_items` 分隔）

### 回归
- [ ] `test_setup_service.py` / `test_setup_*.py` 通过（确认未误改 setup_service.py）
- [ ] `test_market_scanner_service.py` 通过（确认未改 F106）
- [ ] `test_pool_helpers_f205b.py` 通过（F205-b 交付未受影响）
- [ ] `test_fmp_client.py` 通过

---

## 6. 开发顺序（Generator 模式严格遵循）

```
1. 确认 DATA-MODEL.md / API-CONTRACT.md 无需改动（仅消费现有定义）— 通过即继续
2. 新建 backend/app/schemas/cockpit/pool.py（4 个 Pydantic 模型）
   → wip commit: "wip(F205-c): pool schemas"
3. 新建 backend/app/services/cockpit/pool_service.py（PoolService + 5 个私有过滤方法）
   → wip commit: "wip(F205-c): PoolService"
4. 新建 backend/tests/test_pool_service.py（覆盖标准 #8–#10, #16–#18）
   → 跑通 → wip commit: "wip(F205-c): pool service unit tests"
5. 新建 backend/app/routers/cockpit/pool.py + 修改 __init__.py 注册
   → wip commit: "wip(F205-c): pool router + register"
6. 新建 backend/tests/test_cockpit_pool_router.py（覆盖标准 #1–#7, #11–#15, #19–#21）
   → 跑通 → wip commit: "wip(F205-c): pool router integration tests"
7. 全量回归 `pytest backend/` → 通过
8. 追加 DECISIONS.md D080
9. Evaluator 模式跑自检清单
10. 全部通过 → 最终 commit "feat(F205-c): pool service + GET /api/cockpit/pool"
   → phase: in_progress → testing → needs_review
```

---

## 7. 风险与权衡

| 风险 | 缓解 |
|------|------|
| FMP 200 ticker × 2 调用 在 6 并发下仍可能 30–40s（受 token bucket 5/s 稳态约束），逼近前端默认 timeout | F205-d 前端把 query timeout 设 60s + widget loading state；本 sprint 用 ThreadPoolExecutor 并发 + POOL_TREND_CAP 收敛规模；持久化缓存归 F205-x |
| breakout_scans 当天 0 行（F106 未跑或市场假期）→ trend=0，整个 pool 空 | items=[] 是合法响应；前端展示"今日扫描未运行" empty state（F205-d 处理） |
| ADV 单日代理在低流动性 ticker 上误判（如某天巨量 spike 通过粗筛但 20d 均量低于阈值） | D080 已记录技术债；advMin 默认 20M 已经偏松，误差可接受；F205-x 正本 |
| trend_score 字段对非 watchlist 返回 null，前端表格列对齐受影响 | F205-d 表格在 design-spec 中已规划"—"占位（待与设计核对，design-spec.md §Pool Builder 行有相应说明） |
| 测试中 `MockFmpClient` 与真 `FmpClient` 接口漂移 | 单元测试用 `monkeypatch` 直接打补丁 `FmpClient.get_daily_bars` / `get_financial_growth` 方法，不构造平行 mock 类（与现有 `test_fmp_client.py` 风格一致） |
| pool 请求和每日 universe_refresh / scanner 定时任务撞车，互相饿死 FMP 配额 | 接受。limiter singleton 保证总体不会爆 FMP 限额；pool 请求一次最多 30–40s，refresh 撞上时延迟可接受。任务调度层面的协调（如 pool 高峰避开 refresh 时段）不在本 sprint 范围；F205-x 视监控数据再决策 |

---

## 8. 与下游 sub-sprint 的接口约定（仅备查）

F205-d（前端 PoolBuilderWidget）将这样消费本 sprint 交付物：

```ts
// react-query
const { data } = useQuery(['cockpit-pool', filters], () =>
  fetch(`/api/cockpit/pool?${qs.stringify(filters)}`).then(r => r.json())
)
// data.data.funnel: { tradable, trend, rs, fundamental, action }
// data.data.items: PoolItem[]
```

F205-d 负责：filter UI、funnel 可视化、表格渲染、`+ Add to Watchlist` 按钮（调 F003 watchlist API）。本 sprint 与前端**零交互**。

---

👤 用户确认本 Contract 后，feature-dev skill 将：
1. 更新 `features.json`：F205-c → `contract_agreed`；`active_sub_sprint` → `F205-c`；写入 `estimated_files_changed` 列表
2. 追加 `claude-progress.txt`（Contract 协商完成记录）
3. 生成 `SESSION-HANDOFF.md`（含 Contract 摘要 + 开发顺序 + 下 session 恢复指令）
4. **强制结束 session**，建议 Sonnet 新 session 进入 Generator 模式
