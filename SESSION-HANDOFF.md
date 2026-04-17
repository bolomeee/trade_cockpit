# SESSION-HANDOFF.md

> 生成时间：2026-04-17（覆盖上一版 F001-a Generator 前 handoff）
> 当前 Skill：无活跃 Skill（F001-a 全流程完成）
> 下一 Feature：**F001-b Frontend Watchlist 读取展示**（ready_to_dev，等待 Sprint Contract 协商）

---

## 本 Session 完成的内容

### F001-a Backend Watchlist + Stock Search API（✅ done，commit `87c1483` + `befccd0`）

**Generator**：从 Step 4 开始顺序实现 Repository → Service → Router → conftest → tests

新建（10 文件）：
- `backend/app/repositories/stock_repository.py` — `StockRepository`（get_by_ticker / list_active / create / reactivate / soft_delete / count_bars）
- `backend/app/schemas/watchlist.py` — `CamelModel` / `ResponseEnvelope[T]` / `WatchlistItem` / `WatchlistCreatedItem` / `AddStockRequest` / `DeleteStockResponse` / `StockSearchItem`
- `backend/app/services/watchlist_service.py` — `APIError` + `WatchlistService`（常量 `READY_BAR_THRESHOLD=150` / `SEARCH_LIMIT_MAX=20` / `POLYGON_MATCH_LIMIT=5`）
- `backend/app/dependencies.py` — `get_polygon_client` / `get_watchlist_service`
- `backend/app/routers/watchlist.py` + `backend/app/routers/stocks.py`
- `backend/tests/test_watchlist_api.py` — T1–T17（T10 parametrize → 19 items）
- 3 个 `__init__.py`

修改：
- `backend/app/main.py` — mount 2 routers + `APIError` 和 `RequestValidationError` 统一异常 handler
- `backend/tests/conftest.py` — `session_engine` + `db_session` + `mock_polygon` (FakePolygon) + `client` fixture 注入 dependency_overrides

**Evaluator**：`pytest` 38 passed（health 1 + polygon 8 + schema 10 + watchlist 19）

**验收**：用户实货手验通过
- `GET /api/watchlist` → `{"data":[],"message":"success"}`
- `POST /api/watchlist {ticker:AAPL}` → 201 + Apple Inc./XNAS + `dataStatus: "loading"`
- `GET /api/stocks/search?q=AA` → 10 条美股结果（Alcoa + ETF）
- `GET /api/stocks/search` 缺 q → 统一错误 `VALIDATION_ERROR`

验收记录：`docs/验收/v1.0-acceptance.md` 追加 F001-a 段

### 手验暴露的 2 个基础设施 bug（已修复并落 DECISIONS）

**D015 nginx `proxy_pass` 不带末尾斜杠**
- 现象：所有 `/api/*` 返回 `{"detail":"Not Found"}`
- 根因：`proxy_pass http://backend:8000/;` 带斜杠会剥掉 `/api/` 前缀，`/api/watchlist` → `/watchlist` 发给后端
- 修复：`frontend/nginx.conf:9` 去掉末尾斜杠 → 保留完整 URI
- F000-c 未暴露是因为当时后端只有 `/health`

**D016 Polygon `list_tickers` 用 `itertools.islice` 截取首页**
- 现象：`GET /api/stocks/search?q=AA` 返回 502 EXTERNAL_API_ERROR（Polygon 429）
- 根因：`massive` SDK 的 `limit=N` 是每页大小，iterator 自动翻页，`list(...)` 会吃光所有匹配结果，每翻页一次 HTTP 绕过 token bucket
- 修复：`backend/app/external/polygon_client.py:search_tickers` 用 `itertools.islice(iterator, limit)` 截取首页
- **根因教训**：封装外部 client 时，"每页 limit" 与 "总数 limit" 不能混用；仅 token bucket 不足以约束 SDK 级翻页

### 运维教训（非代码）

- backend Dockerfile 是 `COPY` 代码进镜像（非 volume mount），代码改动必须 `docker compose up -d --build backend` 重建；仅 `restart` 无效
- frontend 同理；改 `nginx.conf` 后需要 `--build frontend`

---

## 中断位置

无中断。F001-a 全流程完整收尾（Contract → Generator → Evaluator → 验收 → commit）。

---

## Sprint Contract 执行状态

| Sprint | Phase | 备注 |
|--------|-------|------|
| F001-a Backend | ✅ done | 两 commit 落盘：feat `87c1483` + chore `befccd0` |
| F001-b Frontend 读取展示 | ⬜ ready_to_dev | **下一 Sprint**，未起草 Contract |
| F001-c Frontend 交互 | ⬜ ready_to_dev | 依赖 F001-b 基础 |

F001（父级）：`in_progress`（等 b/c 完成再整体归档）

---

## F001-b 进场前已知条件

### 范围（从 F001-a Contract 拆分段落继承）

- 页面：Dashboard `/` 的 Watchlist 展示区
- 数据源：`GET /api/watchlist`（F001-a 已提供，返回 `WatchlistItem[]`）
- 字段消费：`ticker` / `name` / `exchange` / `addedAt` / `dataStatus` / `latestSignal`（F001-a 始终 null）
- 态：empty / loading / error / ready
- **明确不包含**：搜索框、AddStock 表单、删除交互（F001-c）；信号颜色（F004）；K 线（F005）

### 预计文件（F001-a Contract 协商时用户批准 10 核心例外）

候选（待协商时确认）：
- `frontend/src/api/client.ts` — axios/fetch 封装 + error normalization
- `frontend/src/api/watchlist.ts` — `getWatchlist()` 类型安全包装
- `frontend/src/types/watchlist.ts` — 共享 TS 类型（和 API-CONTRACT 对齐的驼峰）
- `frontend/src/hooks/useWatchlist.ts` — React Query hook（或自研 hook）
- `frontend/src/components/watchlist/WatchlistBoard.tsx` — 列表容器
- `frontend/src/components/watchlist/WatchlistItem.tsx` — 单行
- `frontend/src/components/watchlist/EmptyState.tsx` — "添加你的第一只股票"
- `frontend/src/components/watchlist/ErrorState.tsx`
- `frontend/src/components/watchlist/LoadingState.tsx`
- `frontend/src/pages/Dashboard.tsx` — 接入 WatchlistBoard

### 协商时要确认的关键决策

1. **数据获取方案**：React Query（TanStack Query）还是原生 fetch + useEffect？
2. **dataStatus 可视化**：loading/insufficient/ready 分别如何展示（占位符/徽章/灰态？）
3. **latestSignal = null 的处理**：统一显示"数据收集中"还是按 dataStatus 分支
4. **design-spec.md 是否已覆盖 Watchlist 空态/错误态/骨架屏**（需重读）
5. **是否引入新依赖**（React Query 算新依赖，需用户明确批准）
6. **测试策略**：F001-b 是纯前端展示，是否写 Vitest + React Testing Library？还是手验 Playwright？

---

## 必读文档清单（下一 Session）

| 顺序 | 文档 | 重点 |
|------|------|------|
| 1 | SESSION-HANDOFF.md | 本文件 |
| 2 | CLAUDE.md | 全局约束 |
| 3 | docs/设计/design-spec.md | Watchlist / Dashboard 视觉规格（读全文） |
| 4 | docs/系统设计/API-CONTRACT.md#watchlist §48-82 | 响应字段权威 |
| 5 | frontend/src/pages/Dashboard.tsx | F000-b 空壳现状 |
| 6 | frontend/package.json | 现有依赖（React 19 / Vite 8 / TS 6 / Tailwind v4 / shadcn） |
| 7 | docs/系统设计/DECISIONS.md#D011-D016 | 前端技术决策上下文 |
| 8 | docs/开发/sprint-contracts/F001-a-contract.md | 字段命名规范参照 |
| 9 | claude-progress.txt 最后 60 行 | 本 Session 全流程 |

---

## 环境快照

- git branch：`main` · 最新 commit：`befccd0`（F001-a 验收归档）
- 工作树：clean
- 后端可运行：`cd backend && uv run uvicorn app.main:app --reload`
- 前端可运行：`cd frontend && pnpm dev`（localhost:5173）
- docker 全栈：`docker compose up -d`（localhost:8080；改代码必须 `--build`）
- Polygon API key：项目根 `.env`（gitignored）
- pytest 基线：38 通过

---

## 下一个 Session 继续指令

```
我回来了，请按顺序读取：
1. SESSION-HANDOFF.md（本文件）
2. CLAUDE.md
3. docs/设计/design-spec.md（全文 — 重点 Watchlist 区域）
4. docs/系统设计/API-CONTRACT.md §Watchlist（第 48-82 行）
5. frontend/src/pages/Dashboard.tsx（F000-b 空壳）
6. frontend/package.json（现有依赖清单）
7. claude-progress.txt 最后 60 行

然后触发 feature-dev skill，起草 F001-b Sprint Contract：
  - 明确范围/排除/预计文件
  - 协商数据获取方案（React Query vs 原生）
  - 协商 dataStatus 可视化规则
  - 确认是否引入新依赖
  - 10 核心文件例外已批准（F001-a Contract 协商时确认）
Contract 用户确认后进 Generator。
```
