---
status: confirmed
confirmed_at: 2026-04-16
last_modified_by: system-design
---

# API-CONTRACT.md

> 最后更新：2026-04-16 | 状态：已确认
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
| EXTERNAL_API_ERROR | 502 | 外部 API（Polygon.io）调用失败 |
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

## Stock Search（/api/stocks）

### GET /api/stocks/search
> Feature：F001 Watchlist 管理

**用途**：搜索美股代码/名称（代理 Polygon.io Tickers API）
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

**说明**：`type` 字段值——CS（普通股）、ETF（交易所交易基金）等。搜索结果为空时返回空数组。

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| q 参数缺失 | VALIDATION_ERROR | 422 |
| Polygon API 调用失败 | EXTERNAL_API_ERROR | 502 |

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
> Feature：F005 个股详情

**用途**：获取 K 线图表数据（OHLCV + MA150 值）
**认证**：不需要

**路径参数**：`ticker` — 股票代码

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
    ]
  },
  "message": "success"
}
```

**说明**：
- `bars`：按日期升序，最多 250 天
- `ma150`：与 bars 对齐，数据不足 150 天的早期日期不包含
- `pullbackMarkers`：回踩事件的日期和价距，用于在 K 线图上标记

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| ticker 不在 watchlist 中 | NOT_FOUND | 404 |

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

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| ticker 不在 watchlist 中 | NOT_FOUND | 404 |

---

### GET /api/stocks/:ticker/fundamentals
> Feature：F005 个股详情

**用途**：获取基本面数据（MVP 阶段返回 mock 数据）
**认证**：不需要

**路径参数**：`ticker` — 股票代码

**成功响应（200）**：
```json
{
  "data": {
    "ticker": "AAPL",
    "priceToEarnings": 28.5,
    "priceToSales": 7.2,
    "peg": 1.8,
    "freeCashFlow": 95000000000,
    "marketCap": 2800000000000,
    "source": "mock",
    "updatedAt": "2026-04-15"
  },
  "message": "success"
}
```

**说明**：
- MVP 阶段 `source: "mock"`，字段值为占位数据
- 后续接入 Massive API `/stocks/financials/v1/ratios` 后，`source` 改为 `"massive"`
- 字段命名与 Massive API 对齐：`priceToEarnings`、`priceToSales`、`freeCashFlow`

**错误响应**：

| 场景 | 错误码 | HTTP |
|------|--------|------|
| ticker 不在 watchlist 中 | NOT_FOUND | 404 |

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
| Polygon API Key 未配置 | VALIDATION_ERROR | 422 |

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

## Market（/api/market）

### GET /api/market/overview
> Feature：F006 大盘概览

**用途**：获取大盘指标（标普500、纳斯达克、10年美债利率）
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
      "source": "polygon_client",
      "message": "Failed to fetch AAPL daily bars: rate limited",
      "detail": "HTTP 429 from api.polygon.io/v2/aggs/...",
      "createdAt": "2026-04-16T06:02:15Z"
    }
  ],
  "message": "success"
}
```
