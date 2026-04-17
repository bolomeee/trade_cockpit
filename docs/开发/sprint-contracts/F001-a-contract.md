---
feature_id: F001-a
parent_feature: F001
name: Backend Watchlist + Stock Search API
status: contract_agreed
drafted_at: 2026-04-17
confirmed_at: 2026-04-17
scope_note: F001 拆分为 a/b/c 三段；本段仅覆盖后端；F001-b/c 为前端
files_over_6_exemption: granted  # 用户 2026-04-17 批准（业务闭环验收诉求）
---

# F001-a Sprint Contract — Backend Watchlist + Stock Search API

## 1. 实现范围

### 包含（4 个 REST 端点完整闭环）

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/watchlist` | 列出所有活跃 Stock，含 `latestSignal` 聚合字段 |
| POST | `/api/watchlist` | 通过 Polygon 校验 ticker → 创建/恢复 Stock；返回 `dataStatus` |
| DELETE | `/api/watchlist/{ticker}` | 软删除：set `is_active=false` |
| GET | `/api/stocks/search?q=&limit=` | 代理 `PolygonClient.search_tickers` |

### 明确排除（给后续 sprint）
- ❌ 添加 Stock 后的 **历史数据自动拉取**（250 天 EOD） → **F003 负责**
- ❌ 150MA 信号计算、`Signal` 表写入 → **F002 负责**
- ❌ 任何前端组件 → **F001-b/c**
- ❌ APScheduler 每日调度 → F003
- ❌ `/api/journal`、`/api/signals` 等其他 feature 接口

### dataStatus 字段（F001-a 定义）
API-CONTRACT 定义 `dataStatus ∈ {"loading", "ready", "insufficient"}`。F001-a 无数据拉取逻辑，但需返回合理值以支持 UI。**运行时从 `daily_bars` 计数派生**：

| bar_count | dataStatus |
|-----------|------------|
| 0 | `"loading"` |
| 1–149 | `"insufficient"` |
| ≥150 | `"ready"` |

F003 接入后该字段自动转 `ready`，无需 schema 变更。

### latestSignal 字段
F001-a 无 Signal 写入路径，`GET /api/watchlist` 中 `latestSignal` 始终为 `null`。F002 接入后自动填充。前端（F001-b）必须正确处理 null。

## 2. 预计修改文件（7 核心 + 3 bookkeeping；用户已批准例外）

### 新建
- `backend/app/schemas/__init__.py`（空）
- `backend/app/schemas/watchlist.py` — Pydantic request/response models
- `backend/app/repositories/__init__.py`（空）
- `backend/app/repositories/stock_repository.py` — `StockRepository` 类
- `backend/app/services/__init__.py`（空）
- `backend/app/services/watchlist_service.py` — 业务逻辑（含 Polygon 调用）
- `backend/app/routers/__init__.py`（空）
- `backend/app/routers/watchlist.py` — `GET/POST/DELETE /api/watchlist`
- `backend/app/routers/stocks.py` — `GET /api/stocks/search`
- `backend/tests/test_watchlist_api.py` — 全端点集成测试

### 修改
- `backend/app/main.py` — 挂载 2 个 router，保留 `/health`
- `backend/tests/conftest.py` — 追加 in-memory SQLite + `get_db` 依赖覆盖 + PolygonClient mock fixture

## 3. 关键技术约定

### 3.1 字段命名（DATA-MODEL 权威 → API 驼峰）
| DB 字段 | API JSON 字段 |
|---------|--------------|
| `ticker` | `ticker` |
| `name` | `name` |
| `exchange` | `exchange` |
| `added_at` | `addedAt` (ISO8601) |
| `last_refreshed_at` | `lastRefreshedAt` (ISO8601) |
| 派生 | `dataStatus`（POST 响应）|
| 聚合 | `latestSignal`（GET list，F001-a 为 null）|

Pydantic `model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)` 统一处理。

### 3.2 Ticker 规范化
- 入参大小写不敏感，存储/返回统一大写
- POST `{"ticker": "aapl"}` → DB 存 `AAPL` → 返回 `AAPL`
- DELETE `/api/watchlist/aapl` 等价于 `/api/watchlist/AAPL`

### 3.3 软删除与恢复
- DELETE：若 `stocks.ticker` 存在且 `is_active=true` → 设 `is_active=false`，200；若已 `is_active=false` 或不存在 → 404 NOT_FOUND
- POST：
  - ticker 在库且 `is_active=true` → 409 DUPLICATE
  - ticker 在库且 `is_active=false` → 恢复 `is_active=true`，更新 `added_at=now()`，201
  - ticker 不在库 → 经 Polygon 校验后新建，201
  - Polygon 查不到 → 404 NOT_FOUND

### 3.4 Polygon 校验策略（POST）
- 调用 `PolygonClient().search_tickers(query=ticker_upper, limit=5)`
- 从结果中找 `ticker == ticker_upper` 的精确匹配
- 精确命中 → 取 `name` / `exchange`（primary_exchange 字段）写入
- 未命中 → 返回 404
- Polygon 抛 `Exception` → 502 `EXTERNAL_API_ERROR`

### 3.5 Stock Search 端点
- 直接转发到 `PolygonClient().search_tickers(query=q, limit=min(limit, 20))`
- `limit` 默认 10，上限 20；超上限强制裁剪（非 422，宽松处理）
- 响应格式固定 `[{ticker, name, exchange, type}]`；`type` 从 Polygon 返回的 `type` 字段透传（如 `CS` / `ETF`）

### 3.6 统一响应格式（API-CONTRACT §General）
所有成功响应：`{"data": ..., "message": "success"}`
所有错误响应：`{"error": {"code": "...", "message": "..."}}`（HTTP 4xx/5xx）

实现方式：自定义 `APIError` 异常 + FastAPI exception_handler 统一转换；成功路径用 `ResponseModel[T]` 泛型包装。

### 3.7 依赖注入
- DB：`Depends(get_db)` → `Session`
- PolygonClient：通过 `Depends` 工厂返回实例；测试用 `app.dependency_overrides` 替换为 mock

### 3.8 测试隔离
`conftest.py` 追加：
- `session_engine` fixture：内存 SQLite + `Base.metadata.create_all()`
- 每个测试覆盖 `get_db` 返回该 session
- `mock_polygon` fixture：提供可编程的 fake PolygonClient，通过 `app.dependency_overrides` 注入

## 4. 完成标准（Evaluator 测试用例）

| # | 场景 | 期望 | 层级 |
|---|------|------|------|
| T1 | `GET /api/watchlist` 空库 | 200 `{"data":[], ...}` | 集成 |
| T2 | `POST /api/watchlist` 新 ticker（Polygon mock 命中） | 201，Stock 入库 `is_active=true`，返回 `dataStatus=loading` | 集成 |
| T3 | `POST /api/watchlist` 小写 ticker | 入库为大写 | 集成 |
| T4 | `POST /api/watchlist` 已有活跃 ticker | 409 DUPLICATE | 集成 |
| T5 | `POST /api/watchlist` 恢复软删除的 ticker | 201，`is_active` 翻回 true | 集成 |
| T6 | `POST /api/watchlist` Polygon mock 未命中 | 404 NOT_FOUND | 集成 |
| T7 | `POST /api/watchlist` Polygon mock 抛异常 | 502 EXTERNAL_API_ERROR | 集成 |
| T8 | `POST /api/watchlist` 缺 ticker 字段 | 422 VALIDATION_ERROR | 集成 |
| T9 | `GET /api/watchlist` 有 1 活跃 + 1 软删除 | 只返回活跃那条，`latestSignal=null` | 集成 |
| T10 | `GET /api/watchlist` dataStatus 派生：0/100/200 bars 三场景 | 对应 loading / insufficient / ready | 集成 |
| T11 | `DELETE /api/watchlist/AAPL` 活跃 ticker | 200，DB `is_active=false` | 集成 |
| T12 | `DELETE /api/watchlist/aapl` 大小写无关 | 200 | 集成 |
| T13 | `DELETE /api/watchlist/XXX` 不存在 | 404 | 集成 |
| T14 | `GET /api/stocks/search?q=AA` | 200，转发 mock 返回 | 集成 |
| T15 | `GET /api/stocks/search` 缺 q | 422 | 集成 |
| T16 | `GET /api/stocks/search?q=AA&limit=50` | 自动裁剪到 20，不 422 | 集成 |
| T17 | `GET /api/stocks/search` Polygon 抛异常 | 502 | 集成 |
| T18 | 回归：F000-a 原 11 + F000-c 8 polygon unit 全部通过 | 通过 | 全量 |

## 5. Evaluator 自检清单

- [ ] 上述 T1–T18 全部 ✅
- [ ] API 响应字段命名与 API-CONTRACT 一致（驼峰）
- [ ] DB 字段命名与 DATA-MODEL 一致（蛇形）
- [ ] 所有错误响应有明确 `error.code` 和 HTTP code
- [ ] 无硬编码 magic value（Polygon limit 上限、dataStatus 阈值 150 抽为常量）
- [ ] 函数 ≤ 50 行；无死代码
- [ ] `uv run pytest` 全量通过（新增 ≥ 17 集成 + 原 19 回归 = ≥ 36）
- [ ] 无 DECISIONS 级技术决策遗漏（如有会议级决策追加 DXXX）

## 6. 风险

- R1：`get_previous_close` 和 `list_aggs` 返回 iterator，mock 要匹配；search_tickers 已是 `list(...)`，好 mock → 可接受
- R2：Polygon 校验消耗 1 次/add 的 rate-limit token。单用户场景下 5/min 够用 → 可接受
- R3：`latestSignal=null` 前端（F001-b）必须正确处理（UI 显示 INSUFFICIENT 或占位）→ F001-b 的 Contract 会显式约束
- R4：ticker `primary_exchange` 字段在 Polygon 响应中可能缺失 → 回落 `""` 或 None，exchange 字段 nullable 兼容
