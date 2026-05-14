---
status: confirmed
confirmed_at: 2026-04-24
last_modified_by: system-design (v1.8/v1.9/v2.0 Cockpit Epic — 新增 /api/cockpit/* 18 个 endpoint + /api/ai/{task_type} 统一入口)
---

# API-CONTRACT.md

> 最后更新：2026-04-24 | 状态：已确认
> ⚠️ 新增 API 必须先在此文档定义，经用户确认后才能实现。
> ⚠️ 修改已有接口必须同步更新此文档，并评估前端影响。

---

## 全局约定

**Base URL**：`/api`
**认证方式**：无（局域网单用户）
**内容类型**：`Content-Type: application/json`

**统一响应格式**：
```json
// 成功
{ "data": { ... }, "message": "success" }

// 成功（列表）
{ "data": [ ... ], "message": "success" }

// 失败
{ "error": { "code": "ERROR_CODE", "message": "人类可读描述" } }
```

**字段命名**：API 响应一律 camelCase（由 Pydantic alias_generator 转换）

**标准错误码**：

| 错误码 | HTTP 状态 | 含义 |
|--------|---------|------|
| NOT_FOUND | 404 | 资源不存在 |
| VALIDATION_ERROR | 422 | 请求参数错误 |
| DUPLICATE | 409 | 资源已存在 |
| EXTERNAL_API_ERROR | 502 | 外部 API（FMP `/stable/`；D034 前为 Polygon.io）调用失败 |
| RATE_LIMITED | 429 | 请求频率超限 |
| INTERNAL_ERROR | 500 | 服务器内部错误 |

---

## Watchlist（/api/watchlist）

### GET /api/watchlist
> Feature：F001 Watchlist 管理

**用途**：获取当前 watchlist 中所有活跃股票
**认证**：不需要

**请求参数**：无

**成功响应（200）**：
```json
{
  "data": [
    {
      "id": 1,
      "ticker": "AAPL",
      "name": "Apple Inc.",
      "exchange": "NASDAQ",
      "addedAt": "2026-04-16T08:00:00Z",
      "lastRefreshedAt": "2026-04-16T06:00:00Z",
      "dataStatus": "loading",
      "latestSignal": {
        "signalType": "BUY_ZONE",
        "distancePct": 2.3,
        "date": "2026-04-15"
      }
    }
  ],
  "message": "success"
}
```

**说明**：
- `dataStatus`：枚举 `"loading" | "insufficient" | "ready"`。`loading` = 数据拉取中；`insufficient` = 历史 bar 数不足 150 条；`ready` = 信号可用。
- `latestSignal`：聚合字段，取该股票最新一条 Signal 记录；`dataStatus` 为 `loading` 或 `insufficient` 时为 `null`。watchlist 为空时返回空数组。

---

### POST /api/watchlist
> Feature：F001 Watchlist 管理

**用途**：添加股票到 watchlist
**认证**：不需要

**请求体**：
```json
{
  "ticker": "AAPL"
}
```

**成功响应（201）**：
```json
{
  "data": {
    "id": 1,
    "ticker": "AAPL",
    "name": "Apple Inc.",
    "exchange": "NASDAQ",
    "addedAt": "2026-04-16T08:00:00Z",
    "dataStatus": "loading"
  },
  "message": "success"
}
```

**说明**：
- 添加后后台异步拉取 250 天历史数据并计算信号
- `dataStatus`：`"loading"`（数据拉取中）/ `"ready"`（就绪）/ `"insufficient"`（数据不足150天）
- 如果 ticker 之前被软删除过（is_active=false），恢复 is_active=true

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| ticker 已在 watchlist 中 | DUPLICATE | 409 |
| ticker 无效（Polygon 查不到） | NOT_FOUND | 404 |
| 请求体缺少 ticker | VALIDATION_ERROR | 422 |

---

### DELETE /api/watchlist/:ticker
> Feature：F001 Watchlist 管理

**用途**：从 watchlist 中移除股票（软删除）
**认证**：不需要

**路径参数**：`ticker` — 股票代码

**成功响应（200）**：
```json
{
  "data": { "ticker": "AAPL", "removed": true },
  "message": "success"
}
```

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| ticker 不在 watchlist 中 | NOT_FOUND | 404 |

---

### POST /api/watchlist/bulk
> Feature：F110-a Watchlist 批量添加接口

**用途**：批量添加股票到 watchlist，单次请求上限 200 个 ticker
**认证**：不需要

**请求体**：
```json
{
  "tickers": ["AAPL", "MSFT", "GOOGL"]
}
```

**成功响应（200）**：
```json
{
  "data": {
    "added": [
      {
        "id": 1,
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "exchange": "NASDAQ",
        "addedAt": "2026-04-22T08:00:00Z",
        "dataStatus": "loading"
      }
    ],
    "skippedDuplicate": ["MSFT"],
    "notFound": ["FAKE"]
  },
  "message": "success"
}
```

**说明**：
- `tickers`：1–200 个股票代码，大小写不敏感（自动转大写），请求内重复的 ticker 自动去重
- `added`：成功新增的股票列表（同 `POST /api/watchlist` 的单条响应格式）
- `skippedDuplicate`：已在 watchlist 中的 ticker（大写），跳过写入
- `notFound`：FMP 查不到的 ticker（大写），跳过写入
- 不保证原子性：单个 ticker 成功写入后，后续 ticker 的网络失败会中止整个 batch（返回 502）
- 每个新增 ticker 自动触发 250 天历史数据 backfill（同单条接口）

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| `tickers` 为空数组 / 缺失 | VALIDATION_ERROR | 422 |
| `tickers` 超过 200 个 | VALIDATION_ERROR | 422 |
| FMP 网络失败（非 NOT_FOUND） | EXTERNAL_API_ERROR | 502 |

---

## Stock Search（/api/stocks）

### GET /api/stocks/search
> Feature：F001 Watchlist 管理

**用途**：搜索美股代码/名称（D034 起代理 FMP `/stable/search-symbol` 前缀匹配 + `/stable/search-name` fallback；D034 前为 Polygon Tickers API）
**认证**：不需要

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| q | string | ✅ | 搜索关键词（ticker 或公司名） |
| limit | integer | ❌ | 返回条数，默认 10，最大 20 |

**成功响应（200）**：
```json
{
  "data": [
    {
      "ticker": "AAPL",
      "name": "Apple Inc.",
      "exchange": "NASDAQ",
      "type": "CS"
    }
  ],
  "message": "success"
}
```

**说明**：
- `type` 字段值——CS（普通股）、ETF（交易所交易基金）等。搜索结果为空时返回空数组。
- D034 起 `type` 由 FMP `search-symbol` 返回的 `exchangeShortName` + `type` 组合映射（FMP 直接区分 `stock`/`etf`），contract 不变
- 两阶段搜索：`search-symbol`（ticker 严格前缀匹配）→ 空则 fallback `search-name`（公司名子串匹配），排序规则保持"前缀命中优先"（D028）

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| q 参数缺失 | VALIDATION_ERROR | 422 |
| FMP API 调用失败 | EXTERNAL_API_ERROR | 502 |

---

## Signals（/api/signals）

### GET /api/signals
> Feature：F002 信号引擎, F004 SignalBoard

**用途**：获取所有 watchlist 股票的最新信号（SignalBoard 数据源）
**认证**：不需要

**成功响应（200）**：
```json
{
  "data": [
    {
      "ticker": "AAPL",
      "name": "Apple Inc.",
      "signalType": "BUY_ZONE",
      "date": "2026-04-15",
      "closePrice": 185.50,
      "ma150Value": 180.20,
      "distancePct": 2.94,
      "slopePositive": true,
      "slopeValue": 0.15
    }
  ],
  "message": "success"
}
```

**说明**：
- 返回列表已按信号优先级排序：BREAKOUT → BUY_ZONE → NEUTRAL → INSUFFICIENT
- 每只股票只返回最新一天的信号

---

### GET /api/signals/:ticker
> Feature：F002 信号引擎, F005 个股详情

**用途**：获取单只股票的信号历史
**认证**：不需要

**路径参数**：`ticker` — 股票代码

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| days | integer | ❌ | 返回最近 N 天的信号，默认 30，最大 250 |

**成功响应（200）**：
```json
{
  "data": {
    "ticker": "AAPL",
    "name": "Apple Inc.",
    "latest": {
      "signalType": "BUY_ZONE",
      "date": "2026-04-15",
      "closePrice": 185.50,
      "ma150Value": 180.20,
      "distancePct": 2.94,
      "slopePositive": true,
      "slopeValue": 0.15
    },
    "history": [
      {
        "date": "2026-04-15",
        "signalType": "BUY_ZONE",
        "closePrice": 185.50,
        "ma150Value": 180.20,
        "distancePct": 2.94
      }
    ]
  },
  "message": "success"
}
```

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| ticker 不在 watchlist 中 | NOT_FOUND | 404 |

---

## Stock Detail（/api/stocks/:ticker）

### GET /api/stocks/:ticker/chart
> Feature：F005 个股详情；F105 扩展（non-watchlist on-demand fallback，见 D041）

**用途**：获取 K 线图表数据（OHLCV + MA150 值）。数据来源 D034 起为 FMP `/stable/historical-price-eod/full`，后端在 service 层将 FMP 响应（`date / open / high / low / close / volume`）转成本契约；响应 schema 保持不变
**认证**：不需要

**路径参数**：`ticker` — 股票代码

**服务端行为分支（F105 / D041 新增）**：
1. 查 `stocks` 表（不限 `is_active`）：
   - **命中** → 走原逻辑：从本地 `DailyBar` 读取 + service 层 MA150 计算 + 查 `Pullback` 表生成 `pullbackMarkers`
   - **未命中** → fallback on-demand 拉 FMP `/stable/historical-price-eod/full?symbol={ticker}&from=(今日-400天)&to=今日`，服务端计算 MA150 序列（取约 250 个交易日窗口），不写 `DailyBar` 表；`pullbackMarkers` 固定返回空数组（Scanner 场景无历史回踩需求）
2. 两条分支的响应 schema **完全一致**，前端不需分支逻辑
3. FMP 返回 404 / 空数据 → 返回本契约的 `NOT_FOUND` 错误码

**成功响应（200）**：
```json
{
  "data": {
    "ticker": "AAPL",
    "bars": [
      {
        "date": "2026-04-15",
        "open": 184.00,
        "high": 186.50,
        "low": 183.20,
        "close": 185.50,
        "volume": 52000000
      }
    ],
    "ma150": [
      {
        "date": "2026-04-15",
        "value": 180.20
      }
    ],
    "pullbackMarkers": [
      {
        "date": "2026-03-10",
        "distancePct": 1.2
      }
    ],
    "sharesFloat": 15200000000
  },
  "message": "success"
}
```

**说明**：
- `bars`：按日期升序，最多 250 天
- `ma150`：与 bars 对齐，数据不足 150 天的早期日期不包含
- `pullbackMarkers`：回踩事件的日期和价距，用于在 K 线图上标记
- `sharesFloat`（F107-b1 / D049）：流通股数量，int | null。watchlist 路径走 Stock 表 24h TTL 缓存（D050），miss 或过期时回源 FMP `/stable/shares-float`（D051 修订，原计划 `/profile` 不携带该字段）；ETF / FMP 404 / 字段缺失时为 null。前端据此计算 Vol/Float 比率。

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| ticker 不在 watchlist 且 FMP on-demand 拉取失败 / 返回空 | NOT_FOUND | 404 |
| FMP 外部服务异常 | EXTERNAL_API_ERROR | 502 |

---

### GET /api/stocks/:ticker/pullbacks
> Feature：F005 个股详情

**用途**：获取历史回踩记录详情
**认证**：不需要

**路径参数**：`ticker` — 股票代码

**成功响应（200）**：
```json
{
  "data": [
    {
      "date": "2026-03-10",
      "closePrice": 182.50,
      "ma150Value": 180.30,
      "distancePct": 1.22,
      "return10d": 3.5,
      "return20d": 5.8,
      "return30d": null
    }
  ],
  "message": "success"
}
```

**说明**：按日期倒序。`return30d: null` 表示数据不足 30 个交易日，尚无法计算。

**说明（F108 更新）**：
- `ticker` 不在 watchlist 或 is_active=False → 返回 200 + 空列表（`data: []`），不再 404
- pullback 计算依赖 180 天本地滚动窗口，非 watchlist ticker 无历史数据，语义与 chart fallback 的 `pullbackMarkers: []` 一致

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| ~~ticker 不在 watchlist 中~~ ~~NOT_FOUND~~ ~~404~~ | — | — |

> F108（2026-04-22）：非 watchlist / inactive ticker 不再 404，改为 200+空列表。

---

### GET /api/stocks/:ticker/fundamentals
> Feature：F005 个股详情；F104 数据源迁移至 FMP

**用途**：获取基本面 TTM 数据（D034 起代理 FMP `/stable/ratios-ttm`）
**认证**：不需要

**路径参数**：`ticker` — 股票代码

**成功响应（200）**：
```json
{
  "data": {
    "ticker": "AAPL",
    "priceToEarnings": 33.84,
    "priceToSales": 9.12,
    "peg": 5.75,
    "roce": 0.6503,
    "freeCashFlow": 104000000000,
    "marketCap": 3200000000000,
    "sharesFloat": 15200000000,
    "source": "fmp",
    "updatedAt": "2026-04-18"
  },
  "message": "success"
}
```

**字段语义（D034 / D036 / F104-S3 / D054）**：

| 字段 | 类型 | 来源 / 计算 | null 语义 |
|------|------|------------|----------|
| priceToEarnings | number \| null | FMP `ratios-ttm.priceToEarningsRatioTTM` | 亏损股（PE 负）或字段缺失 → null |
| priceToSales | number \| null | FMP `ratios-ttm.priceToSalesRatioTTM` | 缺失 → null |
| peg | number \| null | FMP `ratios-ttm.priceToEarningsGrowthRatioTTM` | 增长率 ≤ 0 或缺失 → null |
| roce | number \| null | FMP `key-metrics-ttm.returnOnCapitalEmployedTTM`，比例（0.65 表示 65%） | 资本分母 ≤ 0 或缺失 → null |
| freeCashFlow | number \| null | FMP `key-metrics-ttm.marketCap × key-metrics-ttm.freeCashFlowYieldTTM` | 任一分量缺失 → null |
| marketCap | number \| null | FMP `key-metrics-ttm.marketCap`（无 TTM 后缀） | 缺失 → null |
| sharesFloat | int \| null | F107-b1 `stocks.shares_float` 24h DB 缓存（D050），miss / 过期 → FMP `/stable/shares-float` 回源；非 watchlist / inactive ticker → null（D054） | FMP 字段缺失 / 非 watchlist / FMP HTTP 失败 → null |
| source | string | 取值 `"fmp"`（D034 前为 `"mock"`） | — |
| updatedAt | string (YYYY-MM-DD) | 后端拉取日期 | — |

**说明**：
- 负数语义由**字段意义决定**：ROCE 可以为负（亏损公司），`priceToEarnings` 当 EPS < 0 时业界惯例返回 null 而非负 PE；前端不做二次过滤
- **D036（2026-04-19）**：fundamentals 由 `ratios-ttm`（估值）+ `key-metrics-ttm`（ROCE / marketCap / FCF 推导）合并组装。D035 的"只走 key-metrics-ttm"因 smoke 观察偏差被作废
- FCF 计算：FMP `/stable/` 系列无直出 absolute FCF 字段，按 `FCF = marketCap × freeCashFlowYieldTTM` 反推（精度对齐到 B 级）
- 前端 `Fundamentals` 类型保持不变（D034 约束：不改前端类型）；`FundamentalsCard` 已对 null 字段容错显示 `—`

**说明（F108 更新）**：
- 任意 ticker 均可调用，无需在 watchlist 中（D047）
- `sharesFloat` 仍仅对 watchlist active ticker 有值，非 watchlist / inactive → null（D054 不变）

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| ticker 为空字符串（trim 后） | NOT_FOUND | 404 |
| FMP 接口失败（ratios-ttm 或 key-metrics-ttm 任一） | EXTERNAL_API_ERROR | 502 |
| ~~ticker 不在 watchlist 中~~ | — | ~~404~~ |

> F108（2026-04-22）：移除 watchlist 限制；任意 ticker 直接打 FMP。

---

## Data Refresh（/api/data）

### POST /api/data/refresh
> Feature：F003 数据获取与调度

**用途**：手动触发数据刷新（拉取所有 watchlist 股票的最新 EOD 数据）
**认证**：不需要

**请求体**：无

**成功响应（202）**：
```json
{
  "data": {
    "jobId": "refresh-20260416-080000",
    "status": "started",
    "totalStocks": 15
  },
  "message": "success"
}
```

**说明**：
- 返回 202 Accepted，数据刷新异步执行
- 前端通过 GET /api/data/status 轮询进度
- 如果已有刷新任务在进行中，返回当前任务状态（不重复启动）

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| FMP API Key 未配置 | VALIDATION_ERROR | 422 |

---

### GET /api/data/status
> Feature：F003 数据获取与调度

**用途**：查询当前数据刷新任务的进度
**认证**：不需要

**成功响应（200）**：
```json
{
  "data": {
    "jobId": "refresh-20260416-080000",
    "status": "in_progress",
    "progress": {
      "total": 15,
      "completed": 8,
      "failed": 0
    },
    "startedAt": "2026-04-16T08:00:00Z",
    "lastRefreshedAt": "2026-04-16T06:00:00Z"
  },
  "message": "success"
}
```

**说明**：
- `status`：`"idle"`（无任务）/ `"in_progress"`（进行中）/ `"completed"`（完成）/ `"failed"`（失败）
- 无正在进行的任务时，`status: "idle"`，`lastRefreshedAt` 显示上次刷新时间

---

## Admin（/api/admin）

手动触发后台定时任务，供开发调试和运维使用。所有 endpoint 均为 POST，无请求体，返回执行摘要。

### POST /api/admin/refresh-universe
> Feature：F105

**用途**：触发 FMP 全量 screener 扫描，更新 pool 股票池。

**成功响应（200）**：
```json
{ "status": "ok", "upserted": 120, "skipped": 30, "error": null }
```

---

### POST /api/admin/refresh-pool-cache
> Feature：F205-e

**用途**：重建 pool_cache 表（缓存池内每只股票的最新 fundamental 指标）。

**成功响应（200）**：
```json
{ "status": "ok", "upserted": 120, "elapsed_seconds": 4.2, "error": null }
```

---

### POST /api/admin/refresh-earnings
> Feature：F204-b

**用途**：刷新 earnings 日历（今日 -7 至今日 +30 天范围）。

**成功响应（200）**：
```json
{ "inserted": 12, "updated": 3, "skipped": 5 }
```

---

### POST /api/admin/refresh-setup
> Feature：F202-b

**用途**：对 watchlist 内所有活跃 ticker 执行 setup snapshot 扫描，等价于 22:30 UTC cron。

**成功响应（200）**：
```json
{ "status": "ok", "elapsed_seconds": 8.1 }
```

---

### POST /api/admin/refresh-regime
> Feature：F201-b

**用途**：刷新 14 个 regime ETF 历史数据（400 天），并重新计算 market regime 评分快照，等价于 22:15 UTC cron。

**注意**：`POST /api/data/refresh`（主刷新按钮）内部已包含此步骤，通常无需单独调用。

**成功响应（200）**：
```json
{
  "status": "ok",
  "etf_completed": 15,
  "etf_failed": 0,
  "regime": "RISK_ON",
  "market_score": 95,
  "date": "2026-05-11",
  "elapsed_seconds": 7.1
}
```

---

### POST /api/admin/refresh-scanner
> Feature：F105

**用途**：对 pool 全量 universe（~500 只）执行 MA150 breakout/pullback 信号扫描，等价于每日 06:15 UTC cron。结果写入 market_breakout_snapshots 表，Market Breakouts widget 自动更新。

**注意**：扫描全量 universe 约需 3–6 分钟（受 FMP 限速影响）。

**成功响应（200）**：
```json
{
  "status": "ok",
  "scanned": 597,
  "hits": 94,
  "failed": 136,
  "hits_by_type": {
    "a1_stage_breakout": 2,
    "a2_slope_flip": 45,
    "b2_ma_pullback": 28,
    "legacy_crossover": 19
  },
  "scan_date": "2026-05-11",
  "elapsed_seconds": 295.0
}
```

---

## Market（/api/market）

### GET /api/market/overview
> Feature：F006 大盘概览

**用途**：获取大盘指标（标普500、纳斯达克、10年美债利率）。数据来源 D034 起：SPX/NDX 走 FMP `/stable/historical-price-eod/full?symbol=^GSPC|^NDX`，TNX 走 FMP `/stable/treasury-rates.year10`。DB 层 `market_indices.symbol` 仍保留 `SPX/NDX/TNX`（DATA-MODEL 未变），响应 schema 保持不变
**认证**：不需要

**成功响应（200）**：
```json
{
  "data": [
    {
      "symbol": "SPX",
      "name": "S&P 500",
      "close": 5200.50,
      "prevClose": 5180.20,
      "changePct": 0.39,
      "date": "2026-04-15"
    },
    {
      "symbol": "NDX",
      "name": "NASDAQ 100",
      "close": 18200.30,
      "prevClose": 18050.10,
      "changePct": 0.83,
      "date": "2026-04-15"
    },
    {
      "symbol": "TNX",
      "name": "10-Year Treasury Yield",
      "close": 4.25,
      "prevClose": 4.22,
      "changePct": 0.71,
      "date": "2026-04-15"
    }
  ],
  "message": "success"
}
```

---

### GET /api/market/breakouts
> Feature：F105 Market Breakout Scanner Widget；F106 扩展为多信号（A1/A2/B2 + legacy）

**用途**：读取最新一次扫描快照。F106 起一次扫描会按多种 signal_type 各自评估并写入多行，本端点可按类型过滤返回。纯读端点，不触发扫描。
**认证**：不需要

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `type` | string (逗号分隔) | `a1_stage_breakout,a2_slope_flip,b2_ma_pullback` | 返回哪些 signal_type；合法值见下方枚举；未指定时**不包含 legacy_crossover**（v1.2 旧规则保留入库但默认隐藏） |

**signal_type 枚举**：
- `legacy_crossover`（F105 原规则；默认不返回，需显式请求）
- `a1_stage_breakout`
- `a2_slope_flip`
- `b2_ma_pullback`

**成功响应（200）**：
```json
{
  "data": {
    "scanDate": "2026-04-21",
    "scannedAt": "2026-04-21T05:05:10Z",
    "items": [
      {
        "ticker": "NVDA",
        "companyName": "NVIDIA Corp",
        "signalType": "a1_stage_breakout",
        "closePrice": 850.50,
        "ma150Value": 812.30,
        "pctAboveMa150": 4.70,
        "slopeValue": 0.85,
        "volume": 31250000,
        "volumeRatio20": 1.78,
        "marketCap": 2100000000000
      }
    ],
    "total": 1
  },
  "message": "success"
}
```

**说明**：
- `scanDate` / `scannedAt`：整个快照共享一套时间戳（同一次扫描产生，所有 signal_type 共享）
- `items`：按 `pctAboveMa150` 升序；同一 ticker 可能出现多次（对应不同 signalType）
- `signalType`：F106 起新增，取值为上述枚举；F105 历史行为 `legacy_crossover`
- `slopeValue`：对应 MA150 最近 20 日线性回归斜率；各 signal_type 下含义一致
- `volume` / `volumeRatio20`：F106 起每次扫描都填充；legacy_crossover 历史行可能为 `null`
- 无命中标的时返回 `{scanDate: "<date>", scannedAt: "<ts>", items: [], total: 0}`
- 尚无任何扫描快照时返回 `{scanDate: null, scannedAt: null, items: [], total: 0}`
- 所有金额 / 价格数值按 2 位小数四舍五入返回；`marketCap` 与 `volume` 以原始整数返回

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| `type` 含非法值 | VALIDATION_ERROR | 400 |
| 数据库异常 | INTERNAL_SERVER_ERROR | 500 |

**不提供**：
- 不提供历史快照查询（表设计为只存最新一次）
- 不提供"触发立即扫描"端点（扫描仅由调度器执行；如需手动触发，后续可在 /api/data/refresh 扩展）

---

## Journal（/api/journal）

### GET /api/journal
> Feature：F007 交易日志

**用途**：获取所有交易日志（按日期倒序）
**认证**：不需要

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| ticker | string | ❌ | 按股票代码过滤 |
| action | string | ❌ | 按操作类型过滤（BUY/SELL/ADD/REDUCE/WATCH） |
| limit | integer | ❌ | 返回条数，默认 50 |
| offset | integer | ❌ | 分页偏移，默认 0 |

**成功响应（200）**：
```json
{
  "data": {
    "items": [
      {
        "id": 1,
        "ticker": "AAPL",
        "stockName": "Apple Inc.",
        "action": "BUY",
        "price": 182.50,
        "date": "2026-04-10",
        "positionSize": 50,
        "stopLoss": 175.00,
        "targetPrice": 200.00,
        "reason": "BUY_ZONE 信号，MA150 斜率向上",
        "reference": "参考了...",
        "createdAt": "2026-04-10T10:30:00Z",
        "updatedAt": "2026-04-10T10:30:00Z"
      }
    ],
    "total": 25,
    "limit": 50,
    "offset": 0
  },
  "message": "success"
}
```

---

### POST /api/journal
> Feature：F007 交易日志

**用途**：新建交易日志
**认证**：不需要

**请求体**：
```json
{
  "ticker": "AAPL",
  "action": "BUY",
  "price": 182.50,
  "date": "2026-04-10",
  "positionSize": 50,
  "stopLoss": 175.00,
  "targetPrice": 200.00,
  "reason": "BUY_ZONE 信号，MA150 斜率向上",
  "reference": "参考了..."
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| ticker | string | ✅ | 股票代码（必须在 watchlist 中） |
| action | string | ✅ | BUY / SELL / ADD / REDUCE / WATCH |
| price | number | ✅ | 操作价格 |
| date | string | ✅ | 操作日期（YYYY-MM-DD） |
| positionSize | number | ❌ | 仓位大小（股数） |
| stopLoss | number | ❌ | 止损位 |
| targetPrice | number | ❌ | 目标价 |
| reason | string | ❌ | 操作原因 |
| reference | string | ❌ | 参考内容（大文本） |

**成功响应（201）**：
```json
{
  "data": {
    "id": 1,
    "ticker": "AAPL",
    "stockName": "Apple Inc.",
    "action": "BUY",
    "price": 182.50,
    "date": "2026-04-10",
    "positionSize": 50,
    "stopLoss": 175.00,
    "targetPrice": 200.00,
    "reason": "BUY_ZONE 信号，MA150 斜率向上",
    "reference": "参考了...",
    "createdAt": "2026-04-10T10:30:00Z",
    "updatedAt": "2026-04-10T10:30:00Z"
  },
  "message": "success"
}
```

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| ticker 不在 watchlist 中 | NOT_FOUND | 404 |
| action 值不合法 | VALIDATION_ERROR | 422 |
| 缺少必填字段 | VALIDATION_ERROR | 422 |

---

### PUT /api/journal/:id
> Feature：F007 交易日志

**用途**：更新交易日志
**认证**：不需要

**路径参数**：`id` — 日志 ID

**请求体**：与 POST 相同（所有字段可选，只传需要修改的字段）

**成功响应（200）**：返回更新后的完整 journal entry（格式同 POST 响应）

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| id 不存在 | NOT_FOUND | 404 |
| 字段验证失败 | VALIDATION_ERROR | 422 |

---

### DELETE /api/journal/:id
> Feature：F007 交易日志

**用途**：删除交易日志
**认证**：不需要

**路径参数**：`id` — 日志 ID

**成功响应（200）**：
```json
{
  "data": { "id": 1, "deleted": true },
  "message": "success"
}
```

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| id 不存在 | NOT_FOUND | 404 |

---

## System Logs（/api/logs）

### GET /api/logs
> Feature：F008 系统日志页面

**用途**：获取系统日志（/logs 页面数据源）
**认证**：不需要

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| level | string | ❌ | 按级别过滤（OK/INFO/WARN/ERROR） |
| limit | integer | ❌ | 返回条数，默认 50 |

**成功响应（200）**：
```json
{
  "data": [
    {
      "id": 1,
      "level": "ERROR",
      "source": "fmp_client",
      "message": "Failed to fetch AAPL daily bars: rate limited",
      "detail": "HTTP 429 from financialmodelingprep.com/stable/historical-price-eod/full...",
      "createdAt": "2026-04-16T06:02:15Z"
    }
  ],
  "message": "success"
}
```

---

## News（/api/news）

### GET /api/news/articles
> Feature：F112-a + F113-a News Widget 后端（FMP 代理 + 后端缓存层）

**用途**：获取全市场新闻。`calendar-1d`（默认）从 `news_articles_cache` 读取当日+昨日文章，缓存不足时补拉 FMP；`since` 模式增量翻页只返回新文章；`window=none` 直打 FMP（F112-a 兼容路径）。

**查询参数**：

| 参数 | 类型 | 必填 | 默认 | 约束 | 说明 |
|------|------|------|------|------|------|
| limit | integer | ❌ | 20 | 1 ≤ limit ≤ 200 | 返回条数（上限从 50 提至 200） |
| since | string (ISO-8601) | ❌ | null | 合法 ISO datetime | 增量模式：只返回 `publishedAt > since` 的文章 |
| window | string | ❌ | `"calendar-1d"` | `"calendar-1d"` \| `"none"` | 缓存策略：`calendar-1d` = 当日+昨日缓存优先；`none` = 直打 FMP |

**行为矩阵**：

| 场景 | 请求 | 后端行为 |
|------|------|---------|
| 首次打开 | `?window=calendar-1d` | 读 `news_articles_cache` where `as_of_date IN (today, yesterday)`；覆盖度不足则 FMP 补齐并写缓存 |
| 增量刷新 | `?since=<iso>` | 翻 FMP page=0..4（上限 5 页）直到 `date <= since`；新文章 upsert 缓存；仅返回 `publishedAt > since` |
| 跳过缓存 | `?window=none` | 直打 FMP（F112-a 原行为） |

**成功响应（200）**：
```json
{
  "data": [
    {
      "title": "Cytokinetics (NASDAQ: CYTK) Executive Sells Shares ...",
      "publishedAt": "2026-04-21T21:11:13Z",
      "contentHtml": "<ul><li>An executive ...</li></ul>",
      "symbols": ["CYTK"],
      "imageUrl": "https://portal.financialmodelingprep.com/positions/....jpeg",
      "url": "https://financialmodelingprep.com/market-news/...",
      "author": "Gordon Thompson",
      "site": "Financial Modeling Prep"
    }
  ],
  "meta": {
    "cacheHit": true,
    "fmpCalls": 0,
    "truncated": false,
    "fmpError": false
  },
  "message": "success"
}
```

**meta 字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `cacheHit` | bool | true = 完全从缓存读，未打 FMP |
| `fmpCalls` | int | 本次请求打了几次 FMP |
| `truncated` | bool | `since` 模式触顶 5 页仍未到 since 边界 |
| `fmpError` | bool | FMP 失败但缓存降级成功（degraded 模式） |

`meta` 为额外字段，F112-a 现有前端调用可安全忽略。

**字段规范化规则**（FMP 原字段 → 对外字段）：

| FMP 原字段 | 对外字段 | 类型 | 处理 |
|-----------|---------|------|------|
| `title` | `title` | string | 原样 |
| `date` | `publishedAt` | string (ISO-8601) | `"YYYY-MM-DD HH:MM:SS"` → `"YYYY-MM-DDTHH:MM:SSZ"`（假定 UTC）；解析失败保留原字符串 |
| `content` | `contentHtml` | string | 原样 HTML，前端负责 sanitize |
| `tickers` | `symbols` | string[] | `"NASDAQ:CYTK, NYSE:CB"` → `["CYTK", "CB"]`；去交易所前缀、去空格、去空、去重保序；缺失/空串 → `[]` |
| `image` | `imageUrl` | string \| null | 原样 |
| `link` | `url` | string \| null | 原样 |
| `author` | `author` | string \| null | 原样 |
| `site` | `site` | string \| null | 原样 |

**错误响应**：

| 状态码 | code | 触发条件 |
|-------|------|---------|
| 422 | VALIDATION_ERROR | `limit` 越界 / `since` 非合法 ISO / `window` 非枚举值 |
| 502 | EXTERNAL_API_ERROR | FMP 失败且缓存为空 |

降级（200）：FMP 失败 + 缓存有数据 → `meta.fmpError=true`，由前端决定是否提示用户。

**非目标**：
- 不做按 ticker 过滤（预留 `/api/news/stock?ticker=X` 命名空间）
- 不做详情端点（FMP 列表已含全文 `content`）
- 不做跨日缓存清理（按 `as_of_date` 自然过期）

---

## ── Cockpit Epic（v1.8 / v1.9 / v2.0 新增命名空间）──

> Cockpit 专属命名空间 `/api/cockpit/*`，与 Workbench / News 命名空间**零交叉依赖**（后端 router 层互不 import）。所有 endpoint 遵循全局约定（`{ data, message }` / `{ error }` 响应格式、camelCase 字段）。

---

## Cockpit Market Regime（/api/cockpit/regime）

### GET /api/cockpit/regime
> Feature：F201 Market Regime Widget

**用途**：获取最新一日 market regime 打分 + SPY/QQQ/IWM/VXX 大盘卡片 + 11 sector ETF heatmap。数据来自 `market_regime_snapshots`（最新一行）+ `market_indices`（相关 18 个 symbol 的最近一行）

**请求参数**：无

**成功响应（200）**：
```json
{
  "data": {
    "date": "2026-04-24",
    "regime": "CONSTRUCTIVE",
    "marketScore": 68,
    "subscores": {
      "spyTrend": 18,
      "qqqTrend": 14,
      "iwmBreadth": 9,
      "sectorParticipation": 14,
      "riskAppetite": 7,
      "volatilityStress": 6
    },
    "allowedExposurePct": 70.0,
    "singleTradeRiskPct": 1.0,
    "preferredSetups": ["BREAKOUT", "PULLBACK"],
    "avoidSetups": ["EXTENDED"],
    "indices": [
      { "symbol": "SPY", "close": 520.50, "changePct": 0.43, "aboveMa50": true, "aboveMa200": true, "rsTrend": "up", "state": "Bullish" },
      { "symbol": "QQQ", "close": 450.20, "changePct": 0.62, "aboveMa50": true, "aboveMa200": true, "rsTrend": "up", "state": "Leading" },
      { "symbol": "IWM", "close": 210.10, "changePct": -0.15, "aboveMa50": false, "aboveMa200": true, "rsTrend": "down", "state": "Weak" },
      { "symbol": "VXX", "close": 23.45, "changePct": 1.20, "aboveMa50": true, "aboveMa200": false, "rsTrend": "up", "state": "Constructive" }
    ],
    "sectors": [
      { "symbol": "XLK", "close": 210.10, "changePct": 0.52, "state": "Strong" },
      { "symbol": "XLV", "close": 145.30, "changePct": -0.20, "state": "Weak" }
    ],
    "computedAt": "2026-04-24T22:05:00Z"
  },
  "message": "success"
}
```

**字段说明**：
- `regime` 枚举：`RISK_ON` / `CONSTRUCTIVE` / `NEUTRAL` / `DEFENSIVE` / `RISK_OFF`
- `indices[].state` 枚举：`Bullish` / `Leading` / `Constructive` / `Neutral` / `Weak` / `Defensive`
- `sectors[].state` 枚举：`Strong` / `Constructive` / `Weak` / `Defensive`
- `sectors` 总是返回 11 条（XLK/XLY/XLF/XLI/XLE/XLV/XLC/XLP/XLU/XLB/XLRE），缺数据时 `close=null / state="Neutral"` 占位不抛错

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| `market_regime_snapshots` 为空（冷启动未跑过调度） | NOT_FOUND | 404 |
| `market_indices` 18 个 symbol 数据不全 | 返回 200 + 部分字段 null，**不报错**，前端占位 | — |

---

## Cockpit Setup Monitor（/api/cockpit/setup-monitor）

### GET /api/cockpit/setup-monitor
> Feature：F202 Setup Monitor Widget

**用途**：获取 cockpit 视角下 watchlist 每只 active 股票的结构化 setup 快照 + 汇总（Ready / Near Setup / Extended / Broken 数量）

**请求参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `filter` | string (逗号分隔) | 全部 | 可选值 `ready,near,extended,broken,none`；未指定返回全部（按 suggested_action 排序）|

**成功响应（200）**：
```json
{
  "data": {
    "summary": {
      "total": 32,
      "ready": 3,
      "near": 7,
      "extended": 4,
      "broken": 2,
      "none": 16
    },
    "items": [
      {
        "ticker": "NVDA",
        "stockName": "NVIDIA Corp",
        "setupType": "BREAKOUT",
        "setupQuality": "A",
        "entryPrice": 850.00,
        "stopPrice": 820.00,
        "target2r": 910.00,
        "target3r": 940.00,
        "distanceToEntryPct": 1.25,
        "rewardRisk": 2.0,
        "rsPercentile": 88,
        "volumeStatus": "HIGH",
        "trendScore": 5,
        "earningsRisk": "SAFE",
        "readySignal": true,
        "suggestedAction": "enter",
        "scanDate": "2026-04-24",
        "volumeZscore": 1.83,
        "obvTrend": "UP",
        "upDownVolumeRatio": 1.45
      }
    ]
  },
  "message": "success"
}
```

**字段说明**：
- `setupType` 枚举：`BREAKOUT` / `PULLBACK` / `RECLAIM` / `EARNINGS_DRIFT` / `EXTENDED` / `BROKEN` / `NONE`
- `setupQuality` 枚举：`A` / `B` / `C` / `null`（NONE 时 null）
- `volumeStatus` 枚举：`HIGH` / `NORMAL` / `LOW` / `null`
- `earningsRisk` 枚举：`SAFE`（>10 天）/ `CAUTION`（4–10 天）/ `DANGER`（≤3 天）
- `readySignal`: 7 条 AND 门（trend≥4 & rs≥70 & quality≥B & dist≤3% & R:R≥2 & earnings≠DANGER & regime≠RISK_OFF），具体定义见 F202 acceptance criteria 和 D062
- `suggestedAction` 枚举：`enter` / `watch` / `wait` / `reduce` / `exit` / `null`
- `volumeZscore`：`number | null`；当日 volume 相对过去 50 日均量的 z-score；bars 不足或 std=0 时为 null（F215-b）
- `obvTrend`：`'UP' | 'DOWN' | 'FLAT' | null`；OBV 20 日趋势分类；历史不足或基值为 0 时为 null（F215-b）
- `upDownVolumeRatio`：`number | null`；近 50 日 O'Neil U/D ratio；无下跌日时为 null（F215-b）
- 返回 watchlist 内 active 股票，按 `suggestedAction` 优先级排序（enter > watch > wait > null > reduce > exit）

**BREAKOUT 吸筹门槛（F215-b / D088）**：
- `setupType=BREAKOUT` 的候选在写入快照前需额外满足 `volumeZscore ≥ 1.5` AND `upDownVolumeRatio ≥ 1.2`。
- 任一不达标（含 `volumeZscore=null` 短历史），`setupType` **直接降级为 `NONE`**，不 fall-through 至 PULLBACK / RECLAIM。
- 此门槛有意使 BREAKOUT 数量下降（预期行为）；前端展示无需感知降级过程，读取快照时 `setupType` 已是最终值。

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| `filter` 含非法值 | VALIDATION_ERROR | 422 |
| setup_snapshots 尚未生成（冷启动） | 200 + `summary.total=0, items=[]` | — |

---

## Cockpit Chart（/api/cockpit/chart/{ticker}）

### GET /api/cockpit/chart/{ticker}
> Feature：F203 Decision Panel（CockpitChartWidget 数据源）
> 决策依据：D063（独立端点，不共享 `/api/stocks/:ticker/chart` schema）

**用途**：为 Cockpit Decision Panel 提供独立的 chart 数据：OHLCV + 多条 MA + ATR + AVWAP 锚点元信息。与 Workbench `/api/stocks/:ticker/chart` 完全独立（前端 CockpitChartWidget 不共享 ChartWidget 代码）

**路径参数**：`ticker` — 股票代码

**查询参数**：

| 参数 | 类型 | 默认 | 约束 | 说明 |
|------|------|------|------|------|
| `mas` | string (逗号分隔) | `10,21,50,150,200` | 每个值 ∈ [5, 250] | 返回哪些 MA 周期序列 |
| `days` | integer | 250 | [100, 400] | bars 返回天数窗口 |
| `anchor` | string (ISO 日期) | null | `YYYY-MM-DD` | AVWAP 起点；为空时后端从 F204 earnings_events 取最近一次 earnings_date |

**服务端行为**：
- `stocks` 表命中 → 走本地 `daily_bars` 取最近 `days` 天
- 未命中 → fallback on-demand 拉 FMP（复用 D041 逻辑），不写 `daily_bars`
- MA 计算在 service 层完成（复用 workbench 信号引擎中的 MA utility，作为纯函数被 cockpit 服务 import —— 函数级复用允许，目录级解耦硬约束）
- ATR（14）固定返回一条序列
- AVWAP 从 `anchor` 日期起累计计算；无 anchor 且 earnings_events 无数据时 `anchor` 字段为 null，`avwap` 序列为空数组
- EMA 序列固定计算 EMA 10 / EMA 21（由 `CHART.DEFAULT_EMAS` 参数控制，**不接受查询参数**）；算法：α=2/(period+1)，seed=SMA(period)；bars 不足 period 时对应序列为空数组

**成功响应（200）**：
```json
{
  "data": {
    "ticker": "NVDA",
    "bars": [
      { "date": "2026-04-24", "open": 845, "high": 852, "low": 840, "close": 850, "volume": 31250000 }
    ],
    "mas": {
      "10": [{ "date": "2026-04-24", "value": 842.1 }],
      "21": [{ "date": "2026-04-24", "value": 835.5 }],
      "50": [{ "date": "2026-04-24", "value": 820.3 }],
      "150": [{ "date": "2026-04-24", "value": 780.0 }],
      "200": [{ "date": "2026-04-24", "value": 760.2 }]
    },
    "atr": [{ "date": "2026-04-24", "value": 15.2 }],
    "avwap": {
      "anchor": "2026-02-15",
      "series": [{ "date": "2026-02-15", "value": 770.0 }]
    },
    "emas": {
      "10": [{ "date": "2026-04-24", "value": 848.3 }],
      "21": [{ "date": "2026-04-24", "value": 837.1 }]
    }
  },
  "message": "success"
}
```

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| FMP 查不到 ticker | NOT_FOUND | 404 |
| `mas` 含非法值 | VALIDATION_ERROR | 422 |
| FMP 外部异常 | EXTERNAL_API_ERROR | 502 |

---

### GET /api/cockpit/chart/{ticker}/weekly
> Feature：F216-c1 Weekly Stage Layer（后端路由）
> 决策依据：NP3（pure compute，不写 DB）/ NP4（顶层 stage payload）/ D091（Stage 分类细则）

**用途**：返回周线 OHLCV + 3 条周均线 + Stan Weinstein Stage 分析结果。Stage 为实时纯计算（router 调 `WeeklyStageService.classify`），不写 `weekly_stage_snapshots`（持久化交由 F216-e cron）。

**路径参数**：`ticker` — 股票代码（大小写不敏感，服务端转大写）

**查询参数**：

| 参数 | 类型 | 默认 | 约束 | 说明 |
|------|------|------|------|------|
| `weeks` | integer | 50 | [10, 50] | 返回最近 N 周的 weekly bars 及均线；越界 → 422 |

**服务端行为**：
- `stocks` 表无此 ticker → 404 NOT_FOUND
- daily_bars < 4 → `weeklyBars=[]`，MAs 全为空，`stage.stage=0`，`stage.scanDate=null`
- 4 ≤ daily_bars 但聚合后 weekly_bars < 30 → `weeklyBars` 非空，`stage.stage=0`，`stage.scanDate` = 最后周 date
- weekly_bars ≥ 30 → 按 D091 Stage 规则分类
- `stage.scanDate` 始终取 `weeklyBars[-1].date`（非空时）；`weeklyBars` 为空时 null
- MA 周期固定：10w / 30w / 40w；序列长度 = max(0, len(weeklyBars) - period + 1)

**成功响应（200）**：
```json
{
  "data": {
    "ticker": "AAPL",
    "weeklyBars": [
      { "date": "2025-05-09", "open": 210.5, "high": 215.0, "low": 208.2, "close": 213.8, "volume": 18750000 }
    ],
    "weeklyMas": {
      "10": [{ "date": "2025-05-09", "value": 205.3 }],
      "30": [{ "date": "2025-05-09", "value": 195.1 }],
      "40": [{ "date": "2025-05-09", "value": 190.8 }]
    },
    "stage": {
      "stage": 2,
      "weeklyClose": 213.8,
      "weeklyMa10": 205.3,
      "weeklyMa30": 195.1,
      "weeklyMa40": 190.8,
      "slope30W": 0.79,
      "scanDate": "2025-05-09"
    }
  },
  "message": "success"
}
```

**stage 字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `stage` | integer | 0=UNKNOWN / 1=Base / 2=Advancing / 3=Distribution / 4=Declining |
| `weeklyClose` | float \| null | 本周收盘价；bars 为空时 null |
| `weeklyMa10` | float \| null | 10 周 SMA；数据不足时 null |
| `weeklyMa30` | float \| null | 30 周 SMA；数据不足时 null |
| `weeklyMa40` | float \| null | 40 周 SMA；数据不足时 null |
| `slope30W` | float \| null | 30wMA 斜率（%/周，OLS 归一化）；数据不足时 null |
| `scanDate` | string (ISO date) \| null | = weeklyBars[-1].date；weeklyBars 为空时 null |

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| ticker 不在 stocks 表 | NOT_FOUND | 404 |
| weeks 不在 [10, 50] | VALIDATION_ERROR | 422 |

---

## Cockpit Decision（/api/cockpit/decision/{ticker}）

### GET /api/cockpit/decision/{ticker}
> Feature：F203 Decision Panel

**用途**：对指定 ticker 计算 deterministic entry / stop / position size（Decision Card 数据源）。受当前 `market_regime_snapshots` 和 `user_settings` 联合影响

**路径参数**：`ticker` — 股票代码

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `entryOverride` | number | ❌ | 用户手动指定 entry（覆盖 setup 默认推荐） |
| `stopOverride` | number | ❌ | 用户手动指定 stop |
| `riskPctOverride` | number | ❌ | 用户覆盖 risk%（否则走 regime × user_settings 合成值） |

**服务端行为**：
- 查 `setup_snapshots` 最新一行取默认 entry/stop/R:R/setup_type
- 应用 override 字段
- risk_pct = min(user_settings.single_trade_risk_pct, regime.single_trade_risk_pct, override)；即"regime 优先于 user"、但 override 可向下
- position size = `floor(account_size × risk_pct / 100 / (entry - stop))`

**成功响应（200）**：
```json
{
  "data": {
    "ticker": "NVDA",
    "setupType": "BREAKOUT",
    "setupQuality": "A",
    "entryPrice": 850.00,
    "stopPrice": 820.00,
    "target2r": 910.00,
    "target3r": 940.00,
    "rewardRisk": 2.0,
    "riskPerShare": 30.00,
    "suggestedShares": 33,
    "positionValue": 28050.00,
    "accountRiskPct": 0.99,
    "effectiveRiskPct": 1.0,
    "regimeCap": 1.0,
    "userSettingCap": 1.0,
    "earningsRisk": "SAFE",
    "earningsDate": "2026-05-22",
    "deterministicHash": "7f2a9b..."
  },
  "message": "success"
}
```

**字段说明**：
- `effectiveRiskPct`：实际应用的 risk%（= min(regimeCap, userSettingCap, override)）
- `deterministicHash`：SHA-256(ticker + entryPrice + stopPrice + riskPct + date)；**F210 AI trade_plan guardrail 的校验锚点**（D068）—— AI 输出的 entry/stop/size 必须复现同一 hash，否则抛 `AiGuardrailViolation`
- `earningsDate`: 从 `earnings_events` 取 ticker 未来最近一次，无 → null

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| ticker 无 setup_snapshots 且未传 override | NOT_FOUND | 404 |
| entry ≤ stop（无论来自 setup 还是 override） | VALIDATION_ERROR | 422 |

---

## Cockpit User Settings（/api/cockpit/user-settings）

### GET /api/cockpit/user-settings
> Feature：F203 Decision Panel

**用途**：获取账户配置（单行单用户）

**成功响应（200）**：
```json
{
  "data": {
    "accountSize": 100000.00,
    "maxExposurePct": 80.0,
    "singleTradeRiskPct": 1.0,
    "defaultRiskPerTradePct": 0.75,
    "baseCurrency": "USD",
    "updatedAt": "2026-04-24T10:00:00Z"
  },
  "message": "success"
}
```

**说明**：行不存在时返回默认值（不写库）；字段默认值见 DATA-MODEL UserSettings

---

### PUT /api/cockpit/user-settings
> Feature：F203 Decision Panel

**用途**：Upsert 账户配置（始终写 id=1）

**请求体**（所有字段可选；仅覆盖传入字段）：
```json
{
  "accountSize": 120000,
  "singleTradeRiskPct": 0.75
}
```

**成功响应（200）**：返回更新后的完整配置（格式同 GET）

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| `accountSize <= 0` | VALIDATION_ERROR | 422 |
| `maxExposurePct ∉ [0, 100]` | VALIDATION_ERROR | 422 |
| `singleTradeRiskPct ∉ [0, 5]` | VALIDATION_ERROR | 422 |

---

## Cockpit Earnings（/api/cockpit/earnings）

### GET /api/cockpit/earnings
> Feature：F204 Earnings Calendar 接入

**用途**：查询单 ticker 下一次 earnings（仅 cockpit 消费；Workbench/News 禁用）

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ticker` | string | ✅ | 股票代码 |

**成功响应（200）**：
```json
{
  "data": {
    "ticker": "NVDA",
    "nextEarningsDate": "2026-05-22",
    "daysUntil": 28,
    "timeOfDay": "AMC",
    "epsEstimate": 5.20,
    "revenueEstimate": 48000000000
  },
  "message": "success"
}
```

**未来 30 天内无 earnings**：
```json
{
  "data": {
    "ticker": "NVDA",
    "nextEarningsDate": null,
    "daysUntil": null,
    "timeOfDay": null,
    "epsEstimate": null,
    "revenueEstimate": null,
    "note": "No upcoming earnings in next 30 days"
  },
  "message": "success"
}
```

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| `ticker` 缺失 | VALIDATION_ERROR | 422 |

---

## Cockpit Pool Builder（/api/cockpit/pool）

### GET /api/cockpit/pool
> Feature：F205 Pool Builder Widget

**用途**：多维筛选漏斗。复用 F105 `market_scan_universe` + F106 `market_breakout_scans` 数据，扩展 RS percentile + ADV filter + fundamental sanity

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `marketCapMin` | integer | 50000000000 | 市值下限（美元） |
| `priceMin` | number | 10 | 股价下限 |
| `advMin` | integer | 20000000 | 20日均 dollar volume 下限（美元） |
| `trendScoreMin` | integer | 3 | 0-5，默认 3 |
| `rsPercentileMin` | integer | 70 | 0-100 |
| `revenueGrowthYoyMin` | number | 10.0 | 营收增速下限（%） |
| `sectors` | string (逗号分隔) | 全部 | sector ETF symbol（XLK 等） |
| `setupTypes` | string (逗号分隔) | 全部 | SetupSnapshot 枚举 |
| `limit` | integer | 50 | 1–200 |

**成功响应（200）**：
```json
{
  "data": {
    "funnel": {
      "tradable": 1850,
      "trend": 820,
      "rs": 210,
      "fundamental": 95,
      "action": 22
    },
    "items": [
      {
        "ticker": "NVDA",
        "name": "NVIDIA Corp",
        "sector": "XLK",
        "price": 850.00,
        "trendScore": 5,
        "rsPercentile": 88,
        "setupType": "BREAKOUT",
        "distanceToPivotPct": 1.25,
        "distanceTo50maPct": 3.60,
        "earningsDate": "2026-05-22",
        "daysUntilEarnings": 28,
        "revenueGrowthYoy": 56.0,
        "suggestedAction": "enter",
        "inWatchlist": false
      }
    ]
  },
  "message": "success"
}
```

**说明**：
- `funnel`: 漏斗各层淘汰后剩余数量（tradable → trend → rs → fundamental → action）
- `items`: 最终层候选数组
- `inWatchlist`：当前是否已在 `stocks.is_active=true` 中，前端据此决定 `+ Add to Watchlist` 按钮状态

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| 参数类型错误 | VALIDATION_ERROR | 422 |
| universe 为空（冷启动未刷新） | 200 + `funnel` 全 0 + `items: []` | — |

---

## Cockpit Positions（/api/cockpit/positions）

### GET /api/cockpit/positions
> Feature：F206 Position Manager

**用途**：获取持仓列表，默认返回 status=OPEN

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `status` | string | `open` | `open` / `closed` / `all` |

**成功响应（200）**：
```json
{
  "data": {
    "summary": {
      "openRiskPct": 2.5,
      "totalExposurePct": 45.0,
      "pendingRiskPct": 1.0,
      "positionsCount": 5,
      "pendingCount": 2
    },
    "items": [
      {
        "id": 1,
        "ticker": "NVDA",
        "entryPrice": 850.00,
        "entryDate": "2026-04-15",
        "shares": 33,
        "stopPrice": 820.00,
        "target2r": 910.00,
        "target3r": 940.00,
        "setupType": "BREAKOUT",
        "status": "OPEN",
        "lastClose": 875.00,
        "rMultiple": 0.83,
        "unrealizedPl": 825.00,
        "positionValue": 28875.00,
        "earningsDate": "2026-05-22",
        "daysUntilEarnings": 28,
        "nextAction": "hold",
        "closedAt": null,
        "closePrice": null,
        "createdAt": "2026-04-15T10:00:00Z",
        "updatedAt": "2026-04-15T10:00:00Z"
      }
    ]
  },
  "message": "success"
}
```

**字段说明**：
- `rMultiple` / `unrealizedPl` / `positionValue` / `nextAction`：**服务端实时计算**（不持久化），基于 `last_close`
- `last_close` 来源：watchlist 内走 `daily_bars` 最新行；非 watchlist 走 on-demand FMP（D041）
- `nextAction` 枚举：`hold` / `raise_stop` / `reduce` / `exit`（规则引擎生成，供 F207 action list 复用）
- `summary` 由 F207 action_service 计算；`positionValue` = shares × last_close，百分比 = `positionValue / account_size × 100`

---

### POST /api/cockpit/positions
> Feature：F206 Position Manager

**用途**：手动录入开仓

**请求体**：
```json
{
  "ticker": "NVDA",
  "entryPrice": 850.00,
  "entryDate": "2026-04-15",
  "shares": 33,
  "stopPrice": 820.00,
  "target2r": 910.00,
  "target3r": 940.00,
  "setupType": "BREAKOUT",
  "notes": "earnings 28 days away"
}
```

**成功响应（201）**：返回完整 position 对象（格式同 GET.items[0]）

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| 缺必填 | VALIDATION_ERROR | 422 |
| `entryPrice <= stopPrice` | VALIDATION_ERROR | 422 |
| `shares <= 0` | VALIDATION_ERROR | 422 |

---

### PATCH /api/cockpit/positions/{id}
> Feature：F206 Position Manager

**用途**：修改持仓（常见场景：移动 stop、转 CLOSED）

**请求体**（字段可选）：
```json
{
  "stopPrice": 840.00,
  "status": "CLOSED",
  "closedAt": "2026-04-30T10:00:00Z",
  "closePrice": 900.00,
  "notes": "hit 2r, moved stop then exit"
}
```

**成功响应（200）**：返回更新后完整 position

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| id 不存在 | NOT_FOUND | 404 |
| status=CLOSED 但 closedAt / closePrice 缺失 | VALIDATION_ERROR | 422 |

**副作用**：
- status 由 OPEN→CLOSED 时，若 v2.0 已上线，异步触发 F211 `journal_assistant`（失败不阻塞）；v1.9 阶段无此副作用

---

### DELETE /api/cockpit/positions/{id}
> Feature：F206 Position Manager

**用途**：硬删除（用于误录入修正；已平仓数据不强制删除）

**成功响应（200）**：
```json
{ "data": { "id": 1, "deleted": true }, "message": "success" }
```

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| id 不存在 | NOT_FOUND | 404 |

---

## Cockpit Pending Orders（/api/cockpit/pending-orders）

### GET /api/cockpit/pending-orders
> Feature：F206 Position Manager

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `status` | string | `active` | `active` / `all` / `ACTIVE` / `TRIGGERED` / `CANCELLED` / `EXPIRED`（大小写不敏感） |

**成功响应（200）**：
```json
{
  "data": [
    {
      "id": 1,
      "ticker": "AMD",
      "setupType": "BREAKOUT",
      "entryPrice": 180.00,
      "stopPrice": 173.00,
      "shares": 40,
      "target2r": 194.00,
      "target3r": 201.00,
      "expirationDate": "2026-05-15",
      "status": "ACTIVE",
      "lastClose": 176.50,
      "distanceToTriggerPct": 1.98,
      "riskPct": 0.70,
      "notes": "",
      "createdAt": "2026-04-20T10:00:00Z",
      "updatedAt": "2026-04-20T10:00:00Z"
    }
  ],
  "message": "success"
}
```

**字段说明**：
- `lastClose` / `distanceToTriggerPct` / `riskPct`：服务端实时计算
- `riskPct` = `(entryPrice - stopPrice) × shares / account_size × 100`

---

### POST / PATCH / DELETE /api/cockpit/pending-orders(/{id})
> Feature：F206 Position Manager

**说明**：CRUD 语义与 positions 对称，请求/响应字段同 GET.items[0] 的可写子集。状态流转：`ACTIVE` → `{TRIGGERED, CANCELLED, EXPIRED}`；`TRIGGERED` 后不允许再改回 ACTIVE（422）。

---

## Cockpit Daily Action List（/api/cockpit/actions/today）

### GET /api/cockpit/actions/today
> Feature：F207 Daily Action List Widget

**用途**：聚合 positions / pending_orders / setup_snapshots，生成今日三栏动作清单。**deterministic 规则引擎**，不调用 AI

**请求参数**：无

**成功响应（200）**：
```json
{
  "data": {
    "asOfDate": "2026-04-24",
    "mustAct": [
      {
        "ticker": "AAPL",
        "actionType": "raise_stop",
        "rationale": "New swing low formed at 195.50; stop can be tightened from 190 to 195",
        "refs": { "positionId": 3, "newStop": 195.00 }
      },
      {
        "ticker": "MSFT",
        "actionType": "reduce_before_earnings",
        "rationale": "Earnings in 2 days (AMC); reduce to 50% per regime CONSTRUCTIVE playbook",
        "refs": { "positionId": 1, "earningsDate": "2026-04-26" }
      }
    ],
    "monitor": [
      {
        "ticker": "NVDA",
        "actionType": "approaching_trigger",
        "rationale": "Pending order trigger at 850; current 843 (-0.83%)",
        "refs": { "orderId": 5 }
      }
    ],
    "noAction": [
      {
        "ticker": "GOOG",
        "actionType": "stable_position",
        "rationale": "Trend intact, no rule change",
        "refs": { "positionId": 2 }
      }
    ]
  },
  "message": "success"
}
```

**actionType 枚举**：

| 栏 | actionType | 触发条件 |
|----|-----------|---------|
| mustAct | `raise_stop` | position 对应 ticker 形成新 swing low 且高于当前 stop |
| mustAct | `cancel_order` | pending_order 对应 setup 已 broken（SetupSnapshot.setup_type=BROKEN） |
| mustAct | `reduce_before_earnings` | position 持有 ticker earnings ≤ 2 天 |
| mustAct | `tighten_stop` | regime 转 DEFENSIVE / RISK_OFF |
| monitor | `approaching_trigger` | pending_order 距触发 ≤ 3% |
| monitor | `stable_position` | position 无规则变化 |
| noAction | `stable_position` | 同上（为清晰起见也放此栏的稳态持仓） |

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| positions + pending_orders 全空 | 200 + 三数组全 `[]` | — |

---

## ── AI 统一入口（v2.0 新增） ──

### POST /api/ai/{task_type}
> Feature：F208 LLM Gateway / F209 / F210 / F211
> 决策依据：D064（单一动态入口）+ D068（guardrail post-validate）+ D069（memo 去重缓存）

**用途**：8 种 AI task 的统一入口。后端按 `task_type` 路由到对应 Pydantic schema 和 tier 配置，LiteLLM 调用，schema 校验后返回。每次调用写入 `ai_memos`

**路径参数**：`task_type` — 必须是以下 8 个枚举之一（Pydantic `Literal`）：
- `market_narrator`（default tier, F209）
- `setup_explainer`（default tier, F209）
- `candidate_ranker`（critical tier, F210）
- `trade_plan`（critical tier, F210）
- `contradiction_detector`（default tier, F211）
- `news_summarizer`（default tier, F211）
- `journal_assistant`（complex tier, F211）
- `translate_article`（default tier, F213; DeepSeek per-task override via `AI_TASK_OVERRIDES_JSON`，D084）

**请求体**：
```json
{
  "input": { ...任意 task-specific schema... },
  "noCache": false
}
```

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `input` | object | ✅ | 对应 task_type 的输入 schema（Pydantic 校验） |
| `noCache` | bool | false | 跳过去重缓存，强制真实调用（调试用） |

**成功响应（200）**：
```json
{
  "data": {
    "memoId": 1234,
    "taskType": "trade_plan",
    "schemaVersion": "v1",
    "output": { ...schema-validated 输出... },
    "meta": {
      "modelUsed": "gpt-5.4-mini",
      "tier": "critical",
      "tokensIn": 820,
      "tokensOut": 540,
      "costUsd": 0.012340,
      "latencyMs": 1850,
      "cacheHit": false
    }
  },
  "message": "success"
}
```

**缓存命中响应**：`meta.cacheHit=true` / `tokensIn=0` / `tokensOut=0` / `costUsd=0.000000` / `latencyMs<50` / `modelUsed="cache"`

**Guardrail（F210 trade_plan 专属）**：
- 响应前后端 post-validate：`trade_plan.output.entry / stop / size` 必须等于 `GET /api/cockpit/decision/{ticker}.deterministicHash` 对应的 entry/stop/size（浮点对齐到 2 位小数）
- 不等 → 抛 `AI_GUARDRAIL_VIOLATION`，不写 ai_memos，前端显示"AI 输出被拦截"

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| `task_type` 非枚举 | VALIDATION_ERROR | 422 |
| `input` schema 校验失败 | VALIDATION_ERROR | 422 |
| LiteLLM 外部失败 | AI_PROVIDER_ERROR | 502 |
| LLM 输出 schema 校验失败 | AI_SCHEMA_ERROR | 502 |
| 月预算超限 | AI_BUDGET_EXCEEDED | 429 |
| Guardrail 违规（F210） | AI_GUARDRAIL_VIOLATION | 409 |

**新增标准错误码（仅 AI 命名空间）**：

| 错误码 | HTTP | 含义 |
|--------|------|------|
| AI_PROVIDER_ERROR | 502 | LiteLLM / 底层 provider 调用失败 |
| AI_SCHEMA_ERROR | 502 | LLM 输出不符合 Pydantic schema（多次重试仍失败） |
| AI_BUDGET_EXCEEDED | 429 | 当月 AI_MONTHLY_BUDGET_USD 已耗尽 |
| AI_GUARDRAIL_VIOLATION | 409 | trade_plan 数字改写，被 deterministic 校验拦截 |

**Task-specific input / output schema**：
- 每个 task_type 的详细 schema 定义在 `backend/app/ai/schemas/*.py`，由 feature-dev 阶段（F209/F210/F211）落地；本合约只保证上述统一外层结构
- 输入 schema 示例（`market_narrator`）：`{ "regime": "CONSTRUCTIVE", "marketScore": 68, "subscores": {...}, "sectors": [...] }`
- 输出 schema 示例（`market_narrator`）：`{ "headline": "...", "summary": "...", "riskPosture": "...", "preferredSetups": [...], "avoid": [...], "warnings": [...] }`

---

## Layouts（/api/layouts）
> Feature：F212 跨设备 Layout 同步

### GET /api/layouts/{page}

**用途**：读取指定页面已保存的 layout（JSON 数组），文件不存在时返回空数组
**路径参数**：`page` — `workbench` | `cockpit` | `news`

**成功响应（200）**：
```json
{ "data": [{ "i": "watchlist", "x": 0, "y": 0, "w": 4, "h": 8 }], "message": "success" }
```
文件不存在时 `data` 为 `[]`。

---

### PUT /api/layouts/{page}

**用途**：持久化当前页面的 layout 到 `backend/layouts/{page}.json`
**路径参数**：`page` — `workbench` | `cockpit` | `news`
**请求 Body**：layout 数组（直接 `[...]`，非 wrapped object）

```json
[{ "i": "watchlist", "x": 0, "y": 0, "w": 4, "h": 8 }]
```

**成功响应（200）**：
```json
{ "data": null, "message": "success" }
```

---

## Cockpit/AI Namespace 汇总

| 命名空间 | Endpoint 总数 | Feature 映射 |
|---------|------|------------|
| `/api/cockpit/*` | 18 | F200（框架，零 endpoint） / F201 / F202 / F203 (×4) / F204 / F205 / F206 (×8) / F207 |
| `/api/ai/{task_type}` | 1 动态（8 task） | F208（基座） / F209 / F210 / F211 / F213 |

**依赖层级约束**（与 ARCHITECTURE.md 同步）：
- `backend/app/routers/cockpit/*` ⇄ `backend/app/routers/{watchlist,signals,stocks,news,...}/*` **零交叉 import**
- `backend/app/services/cockpit/*` 可 import `backend/app/services/signal_engine.py` 中的**纯函数** MA/ATR utility（函数级复用允许），但不得 import `journal_service` / `watchlist_service` 等有状态服务
- `frontend/src/cockpit/*` ⇄ `frontend/src/workbench/*` 零交叉 import（ESLint 规则 enforce）
