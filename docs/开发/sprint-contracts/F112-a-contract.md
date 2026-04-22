# Sprint Contract：F112-a — News 后端 API（FMP /stable/fmp-articles 代理）

> 状态：contract_agreed | 起草：2026-04-22 | 确认：2026-04-22
> 父 Feature：F112 News Widget（v1.3 规划新增）
> 拆分兄弟：F112-b（导航+页骨架+NewsWidget）、F112-c（ArticleModal+Ticker 联动）

---

## 1. 实现范围

**包含：**

- FMP 客户端扩展：
  - 新增常量 `FMP_EP_FMP_ARTICLES = "/fmp-articles"`（沿用 `FMP_BASE`）
  - 新增 `FmpClient.get_fmp_articles(page: int = 0, limit: int = 20) -> list[dict[str, Any]]`
  - 走现有 `_request` → 共享 D044 rate limiter + concurrency semaphore
  - 原样透传 FMP JSON list（不做字段改名；改名在 router/schema 层做）
- 新 API endpoint：`GET /api/news/articles?limit=N`
  - 直连 FMP `/stable/fmp-articles`，不引入本地缓存（v1 简化；观察 RPM 压力后再决定是否复用 F111-a `daily_payload_cache`）
  - **"最近一日"语义**：FMP `/stable/fmp-articles` 默认按 `date` 降序返回，取前 N 条即为"最新 N 篇"。本版本 **不按日期硬过滤**，取 `limit` 决定（默认 20，上限 50）
  - 字段规范化（避免前端重复适配）：
    | FMP 原字段 | 对外字段 | 说明 |
    |-----------|---------|------|
    | `title` | `title` | 原样 |
    | `date` | `publishedAt` | `"YYYY-MM-DD HH:MM:SS"` 转 ISO-8601（假定 UTC，FMP 未标时区） |
    | `content` | `contentHtml` | 原样 HTML |
    | `tickers` | `symbols` | `"NASDAQ:CYTK, NYSE:CB"` → `["CYTK", "CB"]`；去前缀、去空格、去空、去重保序 |
    | `image` | `imageUrl` | 原样 |
    | `link` | `url` | 原样 |
    | `author` | `author` | 原样 |
    | `site` | `site` | 原样 |
  - 响应外层遵循既有 `ResponseEnvelope`：`{"data": [NewsArticle, ...]}`
- 错误处理（遵循项目统一错误契约）：
  - FMP httpx 错误（连接 / 5xx / 超时）→ 502 `EXTERNAL_API_ERROR`
  - FMP 429 → 客户端内置 3 次 backoff 后若仍 429 → 抛 HTTPStatusError → router 映射 502
  - 参数校验失败 → 422（FastAPI 默认）
- 测试：
  - 单元：`get_fmp_articles` 调用路径正确 + 参数透传
  - 集成：endpoint 200 happy path（mock FMP）+ 字段规范化正确 + 错误路径 502
  - 回归：`backend/tests/` 全量通过

**排除：**

- 本地缓存（`daily_payload_cache` 不接入，原因：news 不按 ticker 索引，现有表结构不适配；且 v1 RPM 风险低）
- 前端 React Query / UI（F112-b、F112-c）
- `GET /api/news/articles/{id}` 详情端点（FMP 列表已含全文 `content`，无需二次拉取）
- FMP `page` 分页（仅暴露 `limit`；后续有需要再加 `page` 参数）
- 按 ticker 过滤新闻（未来 F112+1 功能）
- `/stable/news/stock?symbol=X` 个股新闻代理（F112 范围内不做；预留 endpoint 命名空间 `/api/news/stock`）

---

## 2. 预计修改文件（共 7 个，超上限 1 个，参照 F111-a 先例）

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `backend/app/external/fmp_client.py` | 修改 | 新增 `FMP_EP_FMP_ARTICLES` 常量 + `get_fmp_articles()` 方法（~15 行） |
| 2 | `backend/app/schemas/news.py` | 新建 | 纯 Pydantic `NewsArticle` 定义（无业务逻辑） |
| 3 | `backend/app/services/news_service.py` | 新建 | `NewsService`：封装 FMP 调用 + 字段规范化（`normalize_symbols` / `to_iso_datetime` / raw → `NewsArticle`） |
| 4 | `backend/app/routers/news.py` | 新建 | `GET /api/news/articles`，内含 `get_news_service` DI factory（沿用项目 stocks.py 就近定义模式） |
| 5 | `backend/app/main.py` | 修改 | 追加 `app.include_router(news.router)` 一行 |
| 6 | `backend/tests/test_news_api.py` | 新建 | 单元（service）+ 集成（endpoint）+ FMP 错误路径 |
| 7 | `docs/系统设计/API-CONTRACT.md` | 修改 | 新增 `## News（/api/news）` 章节 |

**解耦设计**：
- schemas 只声明数据形状（外部契约）
- service 承载"调 FMP + 规范化映射"的所有逻辑（未来加缓存 / 多源聚合 / 打分在此扩展）
- router 只负责 HTTP 关注点（参数校验、错误映射、响应包装）
- 不改 `dependencies.py`（DI factory 就近定义在 `routers/news.py`，与 `routers/stocks.py::get_stock_detail_service` 一致）
- `features.json` F112/F112-a 条目在 Generator Step 0 追加（不计入 7 文件）

---

## 3. 完成标准

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| 1 | `FmpClient.get_fmp_articles(limit=5)` 透传 `limit=5` 到 `/stable/fmp-articles` | 单元 | pytest + mock `_request` |
| 2 | `get_fmp_articles` 返回 FMP 原始 list（不改字段） | 单元 | pytest |
| 3 | `GET /api/news/articles` 返回 `ResponseEnvelope`，`data` 为数组 | 集成 | pytest + FakeFMP |
| 4 | `date` → `publishedAt` 字符串转 ISO-8601（`2026-04-21 21:11:13` → `2026-04-21T21:11:13Z`） | 单元 | pytest |
| 5 | `tickers: "NASDAQ:CYTK, NYSE:CB"` → `symbols: ["CYTK", "CB"]`（去前缀、去重保序） | 单元 | pytest |
| 6 | `tickers` 为空串 / 缺失 → `symbols: []` | 单元 | pytest |
| 7 | `limit` 默认 20；`limit=0` 或 `limit>50` 返回 422 | 集成 | pytest |
| 8 | FMP 网络失败（httpx.RequestError）→ 502 `EXTERNAL_API_ERROR` | 集成 | pytest + FakeFMP raises |
| 9 | FMP 返回空 list → 200 `{"data": []}`（不报错） | 集成 | pytest |
| 10 | 全量后端回归：`pytest backend/tests` 100% 通过 | 回归 | pytest |
| 11 | API-CONTRACT.md 增补章节与实际响应一致（字段、类型、错误码） | 手动 | diff |

---

## 4. Evaluator 自检清单

- [ ] 单元测试全部通过（`pytest backend/tests/test_news_api.py -v`）
- [ ] 集成测试全部通过（FakeFMP 调用次数验证）
- [ ] 全量回归通过（既有 F105-F111 测试无退化）
- [ ] `get_fmp_articles` 经过 D044 rate limiter（调用走 `_request`，可通过检查是否持有 limiter 锁的 mock 验证，或直接 grep `_request` 调用证明）
- [ ] 响应 JSON 字段命名符合上表规范（camelCase，与项目既有接口一致）
- [ ] 错误响应格式符合 API-CONTRACT.md 统一错误契约（`{error_code, message}`）
- [ ] 无硬编码魔法值（`DEFAULT_LIMIT = 20`、`MAX_LIMIT = 50`、`FMP_EP_FMP_ARTICLES` 皆为常量）
- [ ] API-CONTRACT.md 已增补 `## News（/api/news）` 章节
- [ ] `features.json` 已追加 F112 + F112-a 条目，F112-a phase 流转正常
- [ ] 无 `news_service.py` 被建出来（确认不越界）
- [ ] Lint / type check（项目若配置）通过

### 代码质量检查

- [ ] 无死代码（未使用 import）
- [ ] `normalize_tickers()` 为独立函数，单测覆盖 4 种输入（空 / 单 / 多 / 带空格）
- [ ] ISO 日期转换为独立函数，容错 FMP 返回异常格式（失败 → 保留原字符串而非抛异常，避免一篇坏数据 kill 整列表）
- [ ] 单函数 ≤ 50 行
- [ ] `try/except` 不吞错（映射到 HTTPException 或原样抛）

### 回归测试

| 测试范围 | 通过 | 失败 | 跳过 |
|---------|------|------|------|
| 当前 feature (F112-a) | N/N | 0 | 0 |
| 全量回归 `pytest backend/tests` | ?/? | ? | ? |

---

## 5. 非目标 / 延后决策

- **缓存策略**：如果 News widget 上线后 `/api/news/articles` 调用量使 FMP RPM 超过单分钟 5% 预算，引入 60s in-memory TTL cache（不走 DB）。届时追加 DECISIONS.md。
- **个股新闻** (`/stable/news/stock?symbol=`)：预留 `/api/news/stock?ticker=X` 命名空间，本 Sprint 不实现。
- **多语言 / 内容清洗**：FMP HTML 原样透传；前端 F112-c 渲染时决定 sanitize 策略。

---

## 6. 接口规格预定义（供 Generator 和 F112-b/c 参考）

```http
GET /api/news/articles?limit=20
```

**响应（200）：**
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
  ]
}
```

**错误（502）：**
```json
{
  "error_code": "EXTERNAL_API_ERROR",
  "message": "FMP articles upstream failed"
}
```
