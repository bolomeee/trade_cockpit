# Stock Portal

> 个人投资工作台 — 单页面承载多个可拖拽 widget（持仓 / 走势 / 基本面 / 新闻 / 扫描 / AI 观点 …）。
> 当前版本：**v1.2.0** · 最后更新：2026-04-21

## 主要功能

- **Workbench**：基于 `react-grid-layout` 的多 widget 单页工作台，布局持久化到 localStorage
- **SMA150 套件**：Chart / Fundamentals / PullbackHistory / Watchlist / QuickAdd
- **Market Breakout Scanner (v1.2.0)**：每日盘后扫描全美大市值股票池的 MA150 穿越候选，行点击联动 ChartWidget
- **数据源**：FMP (Financial Modeling Prep) 为主，Polygon 作为回滚锚点

更多版本变更见 [CHANGELOG.md](CHANGELOG.md)。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS v4 + shadcn/ui |
| 后端 | FastAPI + Python 3.12 + SQLAlchemy 2.0 + APScheduler |
| 数据 | SQLite (prod.db via Docker volume) |
| 部署 | Docker Compose |

## 本地 Docker 部署

### 1. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入真实的 `FMP_API_KEY`（必填）和 `POLYGON_API_KEY`（可选，rollback 用）。

### 2. 构建 & 启动

```bash
docker compose build
docker compose up -d
```

### 3. 访问

| 服务 | 地址 |
|---|---|
| 前端 Workbench | http://localhost:8080 |
| 后端 API | http://localhost:8001 |
| OpenAPI Docs | http://localhost:8001/docs |

> 后端对外暴露 `:8001`（宿主），容器内仍是 `:8000`，避免与其他服务端口冲突。

### 4. 常用命令

```bash
docker compose logs -f backend      # 查看后端日志（含 cron 执行轨迹）
docker compose logs -f frontend
docker compose restart backend      # 重启后端
docker compose down                 # 停止并移除容器（数据卷保留）
docker compose up -d --build        # 代码变更后重新构建
```

### 5. 数据持久化

- 后端 SQLite 挂载在 `./backend/data:/app/data`，容器销毁不丢数据
- 数据库迁移：镜像启动时 alembic 自动 upgrade 到最新 revision

### 6. Cron 定时任务

容器内置以下调度任务（时区：服务器本地）：

| 任务 | 默认时间 | 说明 |
|---|---|---|
| Watchlist refresh | 每日 06:00 | 拉取 watchlist 股票 SMA/EOD |
| Market Breakout Scanner | 工作日 06:15 | F105 每日市场扫描（D042） |
| Universe refresh | 每月 1 号 05:00 | F105 候选池月级刷新（D038） |

可在 `.env` 中通过 `SCANNER_CRON_*` / `UNIVERSE_CRON_*` 变量覆盖。

## 开发模式（非 Docker）

```bash
# 后端
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
pnpm install
pnpm dev
```

Vite dev server 默认代理 `/api` → `http://localhost:8000`。

## 项目文档

| 文档 | 路径 |
|---|---|
| 项目总纲 | [CLAUDE.md](CLAUDE.md) |
| 产品需求 | [docs/需求/PRD.md](docs/需求/PRD.md) |
| 架构 | [docs/系统设计/ARCHITECTURE.md](docs/系统设计/ARCHITECTURE.md) |
| 数据模型 | [docs/系统设计/DATA-MODEL.md](docs/系统设计/DATA-MODEL.md) |
| API 合约 | [docs/系统设计/API-CONTRACT.md](docs/系统设计/API-CONTRACT.md) |
| 技术决策 | [docs/系统设计/DECISIONS.md](docs/系统设计/DECISIONS.md) |
| 视觉规格 | [docs/设计/design-spec.md](docs/设计/design-spec.md) |

## License

Private / Personal Use.
