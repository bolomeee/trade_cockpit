# Sprint Contract：F003-b 刷新 API + 调度器 + add_stock 钩子

> 日期：2026-04-17 | 状态：草案
> 引用文档：
>   API-CONTRACT.md#data-refresh
>   DATA-MODEL.md#daily-bar / #system-log
>   features.json#F003
>   ARCHITECTURE.md

> F003 拆分：
> - F003-a ✅ done（DataRefreshService 核心）
> - **F003-b（本 Contract）**：刷新 API + APScheduler + add_stock 触发 backfill
> - F003-c：前端 TopNav Refresh Data 按钮 + 轮询

---

## 本次实现范围

**包含**：

- **新依赖**：`APScheduler>=4.0`（task scheduling，MemoryDataStore，进程内单实例）
  - 用途：每日 21:30 UTC（美股盘后，约 ET 17:30）触发数据刷新
  - 参考 Context7 `/agronholm/apscheduler` 文档，使用 `Scheduler()` + `CronTrigger.from_crontab("30 21 * * 1-5")` + `start_in_background()`

- **`services/refresh_job.py`**（新建）
  - `RefreshJobState`（dataclass）：`job_id`、`status` ∈ {`idle`, `in_progress`, `completed`, `failed`}、`total`、`completed`、`failed`、`started_at`、`last_refreshed_at`
  - `RefreshJobManager`（单例模块级实例）：
    - 内存状态（threading.Lock 守护）
    - `start_refresh(session_factory) -> RefreshJobState`：已运行中直接返回当前状态（不重复启动）；否则生成 `job_id = f"refresh-{UTC YYYYMMDD-HHMMSS}"`，在后台线程执行 `DataRefreshService.refresh_all(all_active_stock_ids)`，完成时更新 `last_refreshed_at`
    - `get_status() -> RefreshJobState`
    - `_run(job_id, session_factory)`：线程入口，自建 Session（SQLAlchemy Session 不跨线程），完成后调用 `DataRefreshService.purge_old_logs()`
  - Scheduler 管理（同文件内，集中背景任务管理）：
    - `start_scheduler(session_factory)`：创建 `Scheduler()`，注册 cron 任务，`start_in_background()`
    - `shutdown_scheduler()`：关闭 Scheduler
    - `_daily_refresh_task(session_factory)`：Scheduler 调用入口，内部调用 `manager.start_refresh(session_factory)`

- **`schemas/data.py`**（新建）
  - `RefreshStartedPayload`：`jobId`、`status`、`totalStocks`
  - `RefreshStatusPayload`：`jobId` | None、`status`、`progress {total, completed, failed}`、`startedAt` | None、`lastRefreshedAt` | None
  - 使用 Pydantic `alias_generator = to_camel` + `populate_by_name`

- **`routers/data.py`**（新建）
  - `POST /api/data/refresh` → 202 Accepted：调用 `manager.start_refresh(session_factory)`；返回 `{data: RefreshStartedPayload, message: "success"}`
  - `GET /api/data/status` → 200：调用 `manager.get_status()`；按 API-CONTRACT 格式返回
  - 两端点均通过 DI 获取 Session；后台线程不用请求 Session，用注入的 session_factory

- **`main.py`**（修改）
  - 加入 `asynccontextmanager lifespan`：启动时 `start_scheduler(SessionLocal)`；关闭时 `shutdown_scheduler()`
  - `app = FastAPI(lifespan=lifespan)`
  - `app.include_router(data.router)`

- **`services/watchlist_service.py`**（修改）
  - `add_stock` 成功 `create`/`reactivate` 后：
    - 构造 `DataRefreshService(self.db, self.polygon)` 并调用 `backfill_stock(stock.id)`
    - 失败不阻止 POST 返回（写 SystemLog(WARN) 继续）——股票已创建，后续可手动刷新
  - `WatchlistService.__init__` 增加可选 `session` 参数（用于构造 DataRefreshService）；保持向后兼容默认行为

- **`pyproject.toml`**（修改）
  - 添加 `apscheduler>=4.0` 到依赖

**明确排除**：

- 前端 UI（Refresh Data 按钮 + 轮询）→ F003-c
- MarketIndex 刷新 → F006
- 持久化 Job 状态（MVP 进程重启丢 job 状态；对单用户可接受）
- 多实例部署下的调度去重（MVP 单实例）

---

## 预计修改文件（6 个）

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/services/refresh_job.py` | 新增 | 内存 Job 状态 + 后台线程 + APScheduler 启停 |
| 2 | `backend/app/schemas/data.py` | 新增 | Pydantic 响应 schema（camelCase alias） |
| 3 | `backend/app/routers/data.py` | 新增 | POST /api/data/refresh · GET /api/data/status |
| 4 | `backend/app/main.py` | 修改 | lifespan 启停 scheduler · include data router |
| 5 | `backend/app/services/watchlist_service.py` | 修改 | add_stock 后触发 backfill_stock（失败写 WARN） |
| 6 | `backend/tests/test_data_api.py` | 新增 | /refresh 202 · /status 路径 · 已运行中不重复启动 · add_stock 触发 backfill 集成测试 |

（附带：`pyproject.toml` 添加 `apscheduler>=4.0` 依赖，属于配置变更，不计入 6 文件清单；追加 DECISIONS D024 记录 APScheduler 选型 + inline backfill 决策。）

---

## 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `POST /api/data/refresh`（首次）返回 202，响应含 `jobId`、`status: "started"`、`totalStocks = 活跃股数` | 集成 | pytest + TestClient |
| 2 | `POST /api/data/refresh`（已在运行）返回当前任务状态，不启动第二个任务 | 集成 | pytest + mock |
| 3 | `GET /api/data/status` 无任务时返回 `{status:"idle", jobId:null, progress:{total:0, completed:0, failed:0}}` | 集成 | pytest + TestClient |
| 4 | `GET /api/data/status` 运行中返回 `{status:"in_progress", progress:{total, completed, failed}}` | 集成 | pytest + mock（控制线程执行顺序） |
| 5 | 刷新完成后，`GET /api/data/status` 返回 `status:"completed"` 且 `lastRefreshedAt` 更新 | 集成 | pytest + mock |
| 6 | 响应字段全部 camelCase，符合 API-CONTRACT.md（`jobId` / `lastRefreshedAt` / `totalStocks`） | 集成 | pytest（JSON schema 断言） |
| 7 | `POST /api/watchlist`（新增股票）成功后，DailyBar 表含该股票 ≥1 行 bar（mock PolygonClient 返回若干 agg） | 集成 | pytest + mock |
| 8 | `POST /api/watchlist` 若 backfill 抛错：股票仍成功创建返回 201，SystemLog 多出 1 条 WARN | 集成 | pytest + mock |
| 9 | APScheduler 启动时注册 daily cron schedule（验证 `scheduler.get_schedules()` 非空） | 单元 | pytest（直接调 start_scheduler 不启动线程，或用 mock） |
| 10 | `RefreshJobManager` 线程安全：并发 10 次 `start_refresh` 仅产生 1 个 job | 单元 | pytest + threading |

E2E 留给 F003-c（前端 + 后端联调）。

---

## Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] `uv run pytest backend/tests/test_data_api.py` 全绿
- [ ] `uv run pytest backend/tests`（全量回归）全绿，F001/F002/F003-a 测试未被破坏
- [ ] `uv run uvicorn app.main:app` 启动无报错（lifespan 正常运行）
- [ ] API 响应字段 100% camelCase（jobId / totalStocks / progress / startedAt / lastRefreshedAt）
- [ ] 未对 Alembic migration 做破坏性修改
- [ ] `POST /api/data/refresh` 返回 202（不是 200）
- [ ] `status` 枚举 ∈ {idle, in_progress, completed, failed}，`POST` 响应 `status` = `started`（API-CONTRACT 使用 "started"）
- [ ] 已运行中的二次 POST 不重复启动（等同幂等）
- [ ] SQLAlchemy Session 不跨线程（后台线程自建 Session）
- [ ] APScheduler 使用 MemoryDataStore（无 DB 持久化需求）
- [ ] `add_stock` backfill 失败写 SystemLog(WARN) 且不阻塞 POST 返回
- [ ] 新增依赖 `apscheduler>=4.0` 在 pyproject.toml
- [ ] 无 `print(...)` / 无 `TODO` / 无 `console.error`
- [ ] 函数单体 ≤ 50 行
- [ ] 魔法数提取：cron 表达式 `"30 21 * * 1-5"` 作为命名常量 `DAILY_REFRESH_CRON`
- [ ] DECISIONS.md 追加 D024（APScheduler 4.x 选型 + inline add_stock backfill + 线程模型）

---

👤 用户确认本 Contract 后，开发开始。
