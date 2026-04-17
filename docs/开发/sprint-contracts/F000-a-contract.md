# Sprint Contract：F000-a 后端脚手架 + 数据库基座

> 日期：2026-04-17 | 状态：草案
> 引用文档：DATA-MODEL.md#orm-schema | ARCHITECTURE.md#目录结构约定 · #依赖层级规则

---

## ⚠️ 脚手架例外声明

本 Sprint 预计修改 13 个文件，**超出常规 6 文件上限**。经用户批准适用"脚手架例外"，理由：

1. 脚手架文件性质单一：7 个 ORM models 为 DATA-MODEL.md 的机械翻译；4 个 Alembic 文件由 `alembic init` 自动生成；真正需要设计决策的仅 2–3 处。
2. 拆分会导致中间态提交（部分 model 已定义），污染 alembic autogenerate。
3. 全部为"新增"文件，零"修改"，回归风险为零。
4. 可测行为仅 3 条（见下方完成标准），Evaluator 验证成本极低。

例外范围：仅适用 F000-a / F000-b / F000-c 三个脚手架 Sprint。此后回到 6 文件硬规则。
用户批准日期：2026-04-17

---

## 本次实现范围

**包含**：
- `backend/` 目录结构完整搭建（按 ARCHITECTURE.md 约定）
- Python 依赖定义（uv + pyproject.toml）：FastAPI 0.115+、SQLAlchemy 2.0+、Alembic 1.x、Pydantic v2、pytest、httpx
- FastAPI 应用入口 `app/main.py` + `GET /health` 返回 `{"status": "ok"}`
- 配置加载 `app/config.py`（从 `.env` 读取 `DATABASE_URL`、`POLYGON_API_KEY`）
- SQLAlchemy 2.0 同步 engine + session 工厂 `app/database.py`
- 7 个 ORM Model 文件，每文件对应 DATA-MODEL.md 中一个实体，字段完全对齐
- Alembic 初始化 + 自动生成初始 migration，`alembic upgrade head` 创建全部 7 张表
- pytest 集成测试：启动 TestClient 调用 `/health`

**明确排除（本次不做）**：
- 任何业务 API（watchlist、signals、data 等）
- Polygon.io 客户端（留给 F000-c）
- APScheduler 调度器（留给 F003）
- Docker / Dockerfile / docker-compose（留给 F000-c）
- 前端（留给 F000-b）
- 异步 SQLAlchemy（MVP 单用户场景，同步即可；如未来需要再决策）

---

## 预计修改文件（13 个，脚手架例外）

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/pyproject.toml` | 新增 | uv 项目声明 + 依赖列表 |
| 2 | `backend/.env.example` | 新增 | 环境变量样例（DATABASE_URL、POLYGON_API_KEY） |
| 3 | `backend/.gitignore` | 新增 | 忽略 .venv / *.db / .env |
| 4 | `backend/app/__init__.py` | 新增 | 包标识（空） |
| 5 | `backend/app/config.py` | 新增 | Pydantic Settings 加载 .env |
| 6 | `backend/app/database.py` | 新增 | SQLAlchemy engine + SessionLocal + get_db 依赖 |
| 7 | `backend/app/main.py` | 新增 | FastAPI 应用 + `/health` 路由 |
| 8 | `backend/app/models/__init__.py` | 新增 | 汇总导出 Base 和 7 个 model |
| 9 | `backend/app/models/stock.py` | 新增 | Stock ORM（对照 DATA-MODEL.md#stock） |
| 10 | `backend/app/models/daily_bar.py` | 新增 | DailyBar ORM |
| 11 | `backend/app/models/signal.py` | 新增 | Signal ORM |
| 12 | `backend/app/models/pullback.py` | 新增 | Pullback ORM |
| 13 | `backend/app/models/market_index.py` | 新增 | MarketIndex ORM |
| 14 | `backend/app/models/system_log.py` | 新增 | SystemLog ORM |
| 15 | `backend/app/models/journal_entry.py` | 新增 | JournalEntry ORM |
| 16 | `backend/alembic.ini` | 新增 | Alembic 配置（sqlalchemy.url 从 env 读） |
| 17 | `backend/alembic/env.py` | 新增 | Alembic 环境，target_metadata 指向 models.Base.metadata |
| 18 | `backend/alembic/script.py.mako` | 新增 | Alembic 模板（`alembic init` 生成，不改动） |
| 19 | `backend/alembic/versions/001_initial.py` | 新增 | autogenerate 初始迁移 |
| 20 | `backend/tests/__init__.py` | 新增 | 空 |
| 21 | `backend/tests/conftest.py` | 新增 | pytest fixtures（TestClient + 测试 DB） |
| 22 | `backend/tests/test_health.py` | 新增 | `/health` 集成测试 |

> 修订：实际列出 22 个文件（含 ORM 拆分后每文件 + 测试支撑文件）。数量略超最初估计的 13，但仍在脚手架例外适用范围。请确认。

---

## 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `uv sync` 成功安装全部依赖，无版本冲突 | 手工 | uv |
| 2 | `uv run uvicorn app.main:app --reload` 可正常启动，控制台无 error | 手工 | uvicorn |
| 3 | `GET /health` 返回 200，响应体 `{"status": "ok"}` | 集成 | pytest + httpx TestClient |
| 4 | `alembic upgrade head` 在空库执行后，SQLite 中存在全部 7 张表（stocks / daily_bars / signals / pullbacks / market_indices / system_logs / journal_entries） | 集成 | pytest（sqlite inspector） |
| 5 | 7 张表字段名、类型、nullable、索引、唯一约束与 DATA-MODEL.md#ORM Schema 完全一致 | 集成 | pytest 逐表断言 schema |
| 6 | `alembic downgrade base` 可干净回滚所有表 | 集成 | pytest |
| 7 | ORM 字段命名为 snake_case（符合 DATA-MODEL.md#命名规范） | 代码审查 | Evaluator 逐文件检查 |
| 8 | `app/database.py` 导出 `get_db` 依赖，session 使用 `yield + close` 模式 | 代码审查 | Evaluator |

---

## 开发顺序（Generator 模式）

1. **查 Context7 文档**（强制）：FastAPI 0.115 最新 app 启动模板、SQLAlchemy 2.0 同步 engine + DeclarativeBase、Alembic autogenerate 最佳实践
2. 创建目录结构 + `.gitignore` + `.env.example`
3. 写 `pyproject.toml`，`uv sync` 验证依赖可装
4. 写 7 个 ORM models（严格对照 DATA-MODEL.md 逐字段）+ `models/__init__.py`
5. 写 `database.py` + `config.py` + `main.py`（含 `/health`）
6. 手工启动 uvicorn 验证服务可跑
7. `alembic init alembic` → 改 `env.py` 指向 `Base.metadata` → `alembic revision --autogenerate -m "initial"` → 验证迁移脚本覆盖全部 7 表
8. `alembic upgrade head` → sqlite inspector 验证
9. 写 `conftest.py` + `test_health.py` + schema 验证测试
10. `pytest` 全通过

---

## Evaluator 自检清单

- [ ] `uv sync` 成功，依赖无冲突
- [ ] `uvicorn app.main:app` 启动无 error
- [ ] pytest 全部通过（≥ 集成测试 2 条 + schema 断言 7 条）
- [ ] `alembic upgrade head` + `downgrade base` 均成功
- [ ] 7 个 model 文件字段与 DATA-MODEL.md#ORM Schema 逐字段对比一致
- [ ] 目录结构与 ARCHITECTURE.md#目录结构约定 一致
- [ ] 依赖层级规则遵守（main → no models business logic；database 不引 routers 等）
- [ ] `.env` 未被提交（`.gitignore` 生效）
- [ ] 无 `console.error`/Python warning 遗留
- [ ] 技术决策（同步 vs 异步 SQLAlchemy 的选择）已追加到 DECISIONS.md
- [ ] Context7 查询记录在 DECISIONS.md 注明

---

## 需要追加到 DECISIONS.md 的决策

- **D00X**：SQLAlchemy 采用同步模式（非 async）。理由：单用户局域网场景，并发极低；同步 API 更简单，测试易写；如未来需要再切换。
- **D00Y**：ORM models 按实体分文件（`app/models/stock.py` 等），遵循 ARCHITECTURE.md 约定。
- **D00Z**：脚手架例外（6 文件规则豁免），适用范围 F000-a/b/c。

---

👤 用户确认本 Contract 后，开发开始。
