# Sprint Contract：F113-a — News 后端缓存与增量拉取

> 状态：contract_agreed | 起草：2026-04-23 | 同意：2026-04-23
> 父 Feature：F113 News 缓存与增量刷新
> 依赖：F112-a（`/api/news/articles` 已就绪）、F111-a/D055（`daily_payload_cache` 模式参考，本 Sprint 新建 `news_articles_cache` 不复用此表）
> 兄弟：F113-b（前端当日持久化 + 增量合并）、F113-c（已读状态）

---

## 0. 背景

当前 `GET /api/news/articles` 每次请求都直接打 FMP，无任何本地缓存。用户反馈：

1. 刷新页面、软跳路由回 /news 都会重拉，浪费 FMP 配额
2. 希望默认看"最近自然日"范围（而非 FMP 默认的"最新 20 条"）
3. 刷新时希望只拉增量（`since = 本地最新 publishedAt`），而不是整列表重拉

本 Sprint 只做**后端**能力。前端持久化/合并逻辑在 F113-b 落地。

---

## 1. 实现范围

### 1.1 新数据表 `news_articles_cache`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK autoincrement | — |
| article_key | String(512) | NOT NULL | 去重主键：优先用 FMP `link`（URL），缺省时 fallback 为 `hash(title + published_at)` |
| published_at | DateTime | NOT NULL, index | UTC |
| as_of_date | Date | NOT NULL, index | 服务端本地日期（写入当日），用于按自然日失效 |
| payload_json | Text | NOT NULL | 序列化完整 NewsArticle JSON（title/content_html/symbols/imageUrl/url/author/site） |
| cached_at | DateTime | NOT NULL | UTC 写入时间 |

**索引**：
- 唯一：`(as_of_date, article_key)` — 防重复写入
- 辅助：`(as_of_date, published_at DESC)` — 读列表按时间倒序

**为何不复用 `daily_payload_cache`**：该表语义是"单 payload / 覆盖式写"（单次响应整体存 payload_json）；news 是**多行增量 upsert**，需要按 `article_key` 去重，复用会把 schema 搅浑。D057 会在 DECISIONS.md 记录此决策。

### 1.2 API 合约变更 — `GET /api/news/articles`

**新查询参数：**

| 参数 | 类型 | 必填 | 默认 | 约束 | 说明 |
|------|------|------|------|------|------|
| limit | integer | ❌ | 20 | 1 ≤ limit ≤ 200 | 上限从 50 提到 200（首屏可能需要覆盖 2 个自然日） |
| since | string (ISO-8601) | ❌ | null | 合法 ISO datetime | 增量模式：只返回 `publishedAt > since` 的文章 |
| window | string | ❌ | `"calendar-1d"` | `"calendar-1d"` \| `"none"` | 缓存窗口策略：`calendar-1d` = 昨日 00:00（server local TZ）至今；`none` = 不加时间下界 |

**行为矩阵：**

| 场景 | 请求 | 后端行为 |
|------|------|---------|
| 首次打开 | `GET /articles?window=calendar-1d` | 读 `news_articles_cache` where `as_of_date IN (today, yesterday)`；若覆盖度不足（见下文），走 FMP 补齐；写缓存；返回 |
| 增量刷新 | `GET /articles?since=<iso>` | 翻 FMP `page=0..N`（上限 5 页）直到 `date <= since`；新文章 upsert 到 cache；仅返回 `publishedAt > since` 的新文章 |
| 明确跳缓存 | `GET /articles?window=none&limit=50` | 直接打 FMP（**保留原 F112-a 行为以兼容回归**） |

**"覆盖度不足" 判定**：缓存结果数 `< limit` 且**最旧一条 `published_at` 比窗口下界新**（意味着缓存没到窗口尾） → 触发 FMP 补齐。

**增量翻页终止条件**（`since` 模式）：
- 任意一条 `date <= since` → 停
- 已翻到 `page=5` → 停（返回已有，记 warn log，前端视作"可能还有更旧增量未捞到"）
- FMP 返回空页 → 停

**新响应字段（可选）**：
```json
{
  "data": [ ... ],
  "meta": { "cache_hit": true, "fmp_calls": 0, "truncated": false },
  "message": "success"
}
```
`truncated=true` 仅在 `since` 模式触顶 5 页时为 true；`meta` 字段不影响现有前端（额外字段容忍）。

**错误响应：**

| 状态码 | code | 触发 |
|-------|------|------|
| 422 | VALIDATION_ERROR | `since` 非合法 ISO / `limit` 越界 / `window` 非枚举 |
| 502 | EXTERNAL_API_ERROR | FMP 网络失败（且缓存也空） |

**缓存错误策略**：FMP 失败但缓存有数据 → 返回缓存数据 + `meta.cache_hit=true, meta.fmp_error=true`（degraded 模式，200），由前端决定是否提示用户。

### 1.3 service 层改造

- `NewsService` 新增 `list_articles(limit, since, window)` 签名扩展（默认参数保持向后兼容 F112-a 老调用点）
- 新模块 `news_cache_repository.py`：
  - `get_cached(as_of_dates: list[date], since: datetime | None, limit: int) -> list[NewsArticle]`
  - `upsert_many(articles: list[NewsArticle]) -> int` — 按 `(as_of_date, article_key)` 去重
  - `compute_article_key(article) -> str` — URL 优先，fallback SHA256(title+publishedAt)

### 1.4 依赖注入

沿用 F112-a 的 `get_news_service` 工厂。新仓储通过 `Depends(get_db)` + 构造器注入 NewsService。

---

## 2. 预计修改文件（共 6 个）

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `backend/app/models.py` | 修改 | 新增 `NewsArticleCache` ORM 类 |
| 2 | `backend/alembic/versions/006_f113a_news_articles_cache.py` | 新建 | 建表 migration + 索引 |
| 3 | `backend/app/repositories/news_cache_repository.py` | 新建 | 读/写/去重 + article_key 计算 |
| 4 | `backend/app/services/news_service.py` | 修改 | 扩展签名；增量翻页；缓存优先 + 降级 |
| 5 | `backend/app/routers/news.py` | 修改 | 新参数解析 + 校验 + 错误映射 |
| 6 | `backend/app/schemas/news.py` | 修改 | 新增 `NewsListResponseMeta`；Response envelope 扩展 |

**额外（不计入 6 文件）：**
- `backend/tests/test_news_api.py`：补充测试（参数校验、增量、缓存命中、降级）
- `docs/系统设计/API-CONTRACT.md`：同步新参数与行为矩阵
- `docs/系统设计/DATA-MODEL.md`：新增 `news_articles_cache` 表
- `docs/系统设计/DECISIONS.md`：D057（为何不复用 daily_payload_cache）
- `docs/需求/features.json`：新增 F113 feature + F113-a subtask

---

## 3. 完成标准

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| 1 | `uv run pytest backend/tests/test_news_api.py` 全部通过 | 单元 | pytest |
| 2 | 新 migration `alembic upgrade head` 成功建表 | 集成 | alembic |
| 3 | `alembic downgrade -1` 可正常回滚 | 集成 | alembic |
| 4 | 首次请求 `?window=calendar-1d` → 缓存空 → 打 FMP → 落库；再次同请求 → `meta.fmp_calls=0` 命中缓存 | 集成 | pytest + mock FmpClient |
| 5 | `?since=<iso>` 模式：mock FMP 返回 3 页（page2 起出现 `date <= since`），backend 翻到 page2 停，只回新文章 | 单元 | pytest |
| 6 | `?since=<iso>` 模式触顶 5 页 → `meta.truncated=true` | 单元 | pytest |
| 7 | `?window=none` 保持 F112-a 原行为（直打 FMP 无缓存） | 回归 | pytest |
| 8 | FMP 失败 + 缓存有数据 → 200 + `meta.cache_hit=true, meta.fmp_error=true` | 单元 | pytest |
| 9 | FMP 失败 + 缓存空 → 502 | 单元 | pytest |
| 10 | `since` 非法 ISO → 422 | 单元 | pytest |
| 11 | API-CONTRACT.md / DATA-MODEL.md / DECISIONS.md(D057) / features.json 已同步更新 | 文档 | diff |

---

## 4. Evaluator 自检清单

- [ ] ORM / migration / 索引定义一致，无 schema 漂移
- [ ] `compute_article_key`：URL 为 null 的文章走 hash fallback，且与 `published_at` 精度一致（去毫秒，避免同文不同 key）
- [ ] 增量翻页最大页数常量集中在 `news_service.py`（`FMP_INCREMENTAL_MAX_PAGES = 5`）
- [ ] 无裸 `print` / 调试语句；新增 log 用结构化（`logger.info` + extras）
- [ ] DI：`NewsCacheRepository(session)` 通过 `Depends(get_db)` 注入
- [ ] `list_articles(limit=20, since=None, window="calendar-1d")` 默认参数保持 F112-a 调用兼容
- [ ] `meta` 字段：F112-a 现有调用可忽略该字段（容忍性测试）
- [ ] SQLite UTC 时间：`cached_at` 用 `datetime.now(timezone.utc)`

---

## 5. 非目标（留给 F113-b / F113-c）

- 前端 React Query persist（F113-b）
- 前端刷新按钮调用 `?since=` 的流程（F113-b）
- 已读状态（F113-c）
- 跨日缓存清理（设计为自然过期 `as_of_date` 过滤，不做 vacuum 任务）
- 文章详情端点（FMP 列表已含 content，不需要）

---

## 6. 开发顺序

1. `models.py` + Alembic migration → `alembic upgrade head` 验证
2. `news_cache_repository.py` + 单测（compute_article_key / upsert_many / get_cached）
3. `news_service.py` 增量翻页逻辑 + 单测（mock FmpClient）
4. `routers/news.py` 参数校验 + 错误映射
5. `schemas/news.py` meta envelope
6. 集成测试：端到端场景（首次 / 增量 / 降级 / 跳缓存）
7. 文档同步：API-CONTRACT / DATA-MODEL / DECISIONS / features.json
8. `pnpm build` 前端兼容性验证（额外 meta 字段不应破坏现有 hook）

---

## 7. 风险与取舍

- **时区**：`as_of_date = datetime.now(local_tz).date()`。服务器若跨 UTC 边界运行，可能与用户的 `local_tz` 相差 1 天。F113 假定单用户本地部署（server TZ == user TZ），暂不引入显式时区参数。
- **FMP article 无稳定 ID**：依赖 URL 作为主键；URL 可能带 query 参数变动。现阶段不做 URL 归一化（`strip_query_params`），先 URL 原样 + hash fallback。若实测出现误判，F113-b 阶段再收紧。
- **`news_articles_cache` 无限增长**：每日条目数小（几十~几百），不做定期清理；若未来数据膨胀再加 vacuum cron。
