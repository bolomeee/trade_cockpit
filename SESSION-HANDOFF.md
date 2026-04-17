# SESSION-HANDOFF.md

> 生成时间：2026-04-17
> 当前 Skill：feature-dev（F001-a Contract 已确认，尚未进入 Generator）
> 当前 Feature：**F001-a Backend Watchlist + Stock Search API**（contract_agreed）

---

## 本 Session 完成的内容

### F000-c Docker Compose + Polygon Client（✅ done，commit `0764e10` + `93cba6f`）

- Sprint Contract 协商并确认
- Context7 `/massive-com/client-python` 查询 → PyPI 验证 `massive` 2.5.0 是 Polygon.io 官方改名后包（见 D013）
- 实施：
  - `backend/app/external/polygon_client.py`：封装 `massive.RESTClient` + 线程安全 token bucket（5/60s，12s/token）
  - 三方法：`search_tickers` / `get_previous_close` / `get_daily_aggs`
  - `backend/tests/test_polygon_client.py`：8 用例（missing key×2 + 方法转发×3 + rate limit×3）
  - `backend/Dockerfile`：python:3.12-slim + uv 0.5.11，启动时 `alembic upgrade head`
  - `frontend/Dockerfile`：node:20-alpine 多阶段 → nginx:alpine
  - `frontend/nginx.conf`：`/api/*` 反代 `backend:8000`，SPA fallback
  - `docker-compose.yml`：frontend `8080:80`（本机 80 占用），backend 内部 expose
  - 根 `.env.example` + `.env`（gitignored）
- Evaluator 全绿：build + up 成功 · nginx 反代生效 · volume 持久化验证 · pytest 19/19 · `.env` 未泄露
- 用户亲自验收通过，验收记录追加至 `docs/验收/v1.0-acceptance.md`
- DECISIONS.md 追加 D013（massive 包选型）、D014（token bucket rate limit）

### F001 Sprint Contract 协商（本 Session 收尾）

- 读 DATA-MODEL / API-CONTRACT / design-spec / component-plan 的 F001 相关段
- 扫描代码库：F001 整体 ~22 核心文件 → 严重超 6 文件
- 用户批准拆分 a/b/c，授权例外：
  - **F001-a Backend**（7 核心，申请例外 +1）
  - **F001-b Frontend 读取**（10 核心，申请例外 +4）
  - **F001-c Frontend 交互**（5-6 文件）
- F001-a Sprint Contract 起草并用户确认
- Contract 落盘：`docs/开发/sprint-contracts/F001-a-contract.md`
- features.json：F001 phase → `contract_agreed`，新增 `subtasks` 字段登记 a/b/c

---

## 中断位置

**F001-a Generator 尚未开始**。Contract 已确认，代码未动。

---

## Sprint Contract 执行状态（F001-a）

| # | 开发步骤 | 状态 |
|---|---------|------|
| 1 | DATA-MODEL 检查 | ✅ 无需变更（Stock 已在 F000-a 建表） |
| 2 | API-CONTRACT 检查 | ✅ 4 端点均已定义 |
| 3 | 数据库迁移 | ⏭️ 跳过（无 schema 变更） |
| 4 | Repository 层 | 🔄 **中断点 / 立即执行** |
| 5 | Service 层 | ⬜ 未开始 |
| 6 | Router 层 | ⬜ 未开始 |
| 7 | 测试 | ⬜ 未开始 |

---

## F001-a 关键技术约定（从 Contract 摘要，新 Session 立即可用）

### 范围
- 仅后端，4 端点：`GET/POST/DELETE /api/watchlist` + `GET /api/stocks/search`

### 排除
- ❌ 历史数据拉取（F003）
- ❌ 信号计算（F002）
- ❌ 所有前端代码（F001-b/c）

### dataStatus 派生规则（POST 响应 + GET 列表）
| bar_count | dataStatus |
|-----------|------------|
| 0 | `"loading"` |
| 1–149 | `"insufficient"` |
| ≥150 | `"ready"` |

### latestSignal（GET list）
F001-a 始终返回 `null`（F002 后填充）。

### Ticker 规范化
入参大小写不敏感，DB 存大写，API 返回大写。

### 软删除恢复语义
- POST 命中 `is_active=true` ticker → 409 DUPLICATE
- POST 命中 `is_active=false` ticker → 翻回 true + 更新 `added_at` → 201
- POST 新 ticker → Polygon 精确匹配校验 → 201 或 404/502
- DELETE → set `is_active=false`，不存在返回 404

### Polygon 校验（POST）
调用 `PolygonClient().search_tickers(ticker_upper, limit=5)`，找 `ticker == ticker_upper` 精确匹配；未命中 404；抛异常 502。

### 统一响应格式
- 成功：`{"data": ..., "message": "success"}`
- 失败：`{"error": {"code": "...", "message": "..."}}`
- 错误码：`VALIDATION_ERROR` 422 / `DUPLICATE` 409 / `NOT_FOUND` 404 / `EXTERNAL_API_ERROR` 502

### 字段命名
- DB 蛇形（DATA-MODEL 权威）
- API JSON 驼峰：`addedAt` / `lastRefreshedAt` / `dataStatus` / `latestSignal`
- Pydantic `alias_generator=to_camel, populate_by_name=True`

### 测试隔离（conftest.py 追加）
- `session_engine` fixture：in-memory SQLite + `Base.metadata.create_all()`
- `app.dependency_overrides[get_db]` → 该 session
- `mock_polygon` fixture：可编程的 fake PolygonClient，通过 `app.dependency_overrides` 注入

---

## 预计修改文件（F001-a，7 核心 + 3 bookkeeping）

### 新建
- `backend/app/schemas/__init__.py`（空）
- `backend/app/schemas/watchlist.py` — Pydantic models
- `backend/app/repositories/__init__.py`（空）
- `backend/app/repositories/stock_repository.py`
- `backend/app/services/__init__.py`（空）
- `backend/app/services/watchlist_service.py`
- `backend/app/routers/__init__.py`（空）
- `backend/app/routers/watchlist.py`
- `backend/app/routers/stocks.py`
- `backend/tests/test_watchlist_api.py`

### 修改
- `backend/app/main.py` — mount 2 routers
- `backend/tests/conftest.py` — in-memory DB + dependency overrides + mock Polygon

---

## 测试目标（F001-a 完成标准）

18 用例：17 集成 + 1 全量回归（pytest ≥ 36/36，含 F000-a 的 11 + F000-c 的 8 + F001-a 的 17）

T1–T17 涵盖：空库 / 新增 / 大小写 / 冲突 / 软删除恢复 / Polygon 未命中 / Polygon 异常 / 字段缺失 / 聚合字段 / dataStatus 三档 / 删除 / 大小写删除 / 不存在删除 / 搜索 / 搜索缺 q / 搜索 limit 裁剪 / 搜索异常

---

## 遗留决策

无。F001-a Contract 中所有决策已与用户确认：
- ✅ dataStatus 派生规则（0/1-149/150+）
- ✅ latestSignal=null（UI 兜底）
- ✅ 文件例外（7 核心 +1）

---

## 下一个 Session 继续指令

```
我回来了，请按顺序读取：
1. SESSION-HANDOFF.md（本文件）
2. CLAUDE.md
3. docs/开发/sprint-contracts/F001-a-contract.md（F001-a 完整合同）
4. docs/需求/features.json（F001 subtasks 状态）
5. docs/系统设计/DATA-MODEL.md#stock
6. docs/系统设计/API-CONTRACT.md#watchlist + #stock-search（48-190 行）
7. claude-progress.txt 最后 30 行

然后直接进入 feature-dev Generator（类型 E2 开发恢复）：
从 Step 4 Repository 层开始，顺序实现 Repository → Service → Router → main.py mount → conftest 增强 → test_watchlist_api.py 18 用例 → Evaluator → commit。
```

---

## 环境快照

- git branch：`main` · 最新 commit：`93cba6f`（F000-c 验收归档）
- 工作树状态：
  - `docs/需求/features.json` 已 modify（F001 subtasks）
  - `docs/开发/sprint-contracts/F001-a-contract.md` 新文件
  - `claude-progress.txt` 已 modify
  - 本 handoff 文件
  - **以上都将在本 Session 暂停前一并 commit**
- backend 可运行：`cd backend && uv run uvicorn app.main:app`
- frontend 可运行：`cd frontend && pnpm dev`（localhost:5173）
- docker 全栈可运行：`docker compose up -d`（localhost:8080）
- Polygon API key 已配置于项目根 `.env`（gitignored）
