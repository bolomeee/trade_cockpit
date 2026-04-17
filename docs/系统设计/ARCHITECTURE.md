---
status: confirmed
confirmed_at: 2026-04-17
last_modified_by: feature-dev (F000-b · D011+D012)
---

# ARCHITECTURE.md

> 最后更新：2026-04-16 | 状态：已确认
> ⚠️ 技术栈变更必须先更新此文档并征得用户同意，不得擅自更改

---

## 技术栈（已确认）

| 层 | 技术 | 版本 | 选型原因 |
|----|------|------|---------|
| 前端框架 | React + TypeScript | React 19.2, TS 6.x | D012（2026-04-17 升级，原 React 18 / TS 5.x） |
| 构建工具 | Vite | 8.x | D012（2026-04-17 升级，原 Vite 6.x） |
| 样式 | Tailwind CSS | v4 | 用户指定 |
| UI 组件 | shadcn/ui | latest | 用户指定，可定制性好 |
| 图表 | lightweight-charts (TradingView) | 4.x | 专为金融 K 线图设计，~40KB，原生支持 OHLC + MA 叠加 |
| 后端 | FastAPI (Python) | 0.115+ | 用户指定，异步生态好 |
| 运行时 | Python | 3.12+ | 用户指定 |
| 数据库 | SQLite | 3.x | 单用户局域网场景，零运维 |
| ORM | SQLAlchemy | 2.0+ | Python 标准 ORM，async 支持 |
| 数据迁移 | Alembic | 1.x | SQLAlchemy 标配 |
| 调度器 | APScheduler | 3.x | 轻量定时任务，集成在 FastAPI 进程内 |
| 包管理 | pnpm (前端) / uv (Python) | latest | 用户指定 |
| 部署 | Docker Compose | 2.x | 前后端分离容器，一键启动 |
| 认证 | 无 | — | 局域网单用户，不需要 |

---

## 系统边界

```
用户浏览器（PC / 手机）
    ↓ HTTP
┌──────────────────────────────────┐
│  Nginx 容器 (frontend)           │
│  ├── 静态文件 serve (React SPA)  │
│  └── /api/* → 反向代理到 backend │
└──────────────────────────────────┘
    ↓ HTTP (Docker 内部网络)
┌──────────────────────────────────┐
│  FastAPI 容器 (backend)          │
│  ├── REST API (/api/*)           │
│  ├── 信号计算引擎 (Service 层)    │
│  ├── APScheduler (EOD 定时任务)   │
│  └── SQLAlchemy → SQLite         │
└──────────────────────────────────┘
    ↓ HTTPS (外部)
┌──────────────────────────────────┐
│  Polygon.io API                  │
│  └── EOD 日线数据、指数数据       │
└──────────────────────────────────┘
```

---

## 依赖层级规则（不得违反）

### 前端

```
pages/          → 只能调用 widgets/ 和 hooks/
widgets/        → 只能调用 components/ 和 hooks/
components/     → 纯展示组件，不含业务逻辑，不直接调 API
hooks/          → 只能调用 services/
services/       → 只能调用后端 API（fetch/axios）
lib/            → 纯工具函数，无副作用，任何层可用
```

### 后端

```
routers/        → 只能调用 services/
services/       → 只能调用 repositories/ 和 external/
repositories/   → 只能访问数据库（SQLAlchemy models）
external/       → 只能调用外部 API（Polygon.io）
models/         → SQLAlchemy ORM 定义，无业务逻辑
schemas/        → Pydantic 请求/响应模型
```

违反依赖方向的代码必须停止并报告，不得提交。

---

## 目录结构约定

### 前端 (frontend/)

```
frontend/
├── src/
│   ├── pages/              # 页面（仅路由和布局编排）
│   │   ├── Dashboard.tsx   # 首页：大盘概览 + SignalBoard + Add Stock + Journal 快捷
│   │   ├── Journal.tsx     # 交易日志页
│   │   └── Logs.tsx        # 系统日志页
│   ├── widgets/            # Widget 组件（独立业务单元，可组合）
│   │   ├── MarketOverview/ # 大盘概览 Widget
│   │   ├── SignalBoard/    # 信号总览 Widget
│   │   ├── StockDetailModal/ # 个股详情 Modal（纯前端弹窗，不改变 URL）
│   │   ├── QuickAddStock/  # Dashboard 右侧 Add Stock 快捷表单
│   │   ├── QuickJournalEntry/ # Dashboard 右侧 Trade Journal 完整表单
│   │   ├── StockChart/     # K线图 + MA150 Widget
│   │   ├── PullbackTable/  # 回踩历史 Widget
│   │   ├── Fundamentals/   # 基本面数据 Widget
│   │   ├── JournalList/    # Journal 列表 Widget
│   │   ├── JournalForm/    # Journal 表单 Widget
│   │   └── SystemLog/      # 系统日志 Widget
│   ├── components/         # 通用 UI 组件（shadcn/ui 封装 + 项目共用）
│   ├── hooks/              # 自定义 React Hooks
│   ├── services/           # API 调用层（fetch 封装）
│   ├── lib/                # 工具函数（纯函数，无副作用）
│   ├── types/              # TypeScript 类型定义
│   └── styles/
│       └── tokens.css      # Design Tokens（由 design-bridge 生成）
├── index.html
├── vite.config.ts
├── tsconfig.json (+ tsconfig.app.json / tsconfig.node.json)
├── components.json             # shadcn/ui 配置
├── package.json
├── Dockerfile
└── nginx.conf
```

### 后端 (backend/)

```
backend/
├── app/
│   ├── main.py             # FastAPI 入口 + APScheduler 配置
│   ├── config.py           # 环境变量配置
│   ├── database.py         # SQLAlchemy 引擎 + session
│   ├── models/             # SQLAlchemy ORM 模型
│   │   ├── stock.py
│   │   ├── daily_bar.py
│   │   ├── signal.py
│   │   ├── pullback.py
│   │   ├── market_index.py
│   │   ├── system_log.py
│   │   └── journal_entry.py
│   ├── schemas/            # Pydantic 请求/响应模型
│   ├── routers/            # FastAPI 路由（按模块分文件）
│   │   ├── watchlist.py
│   │   ├── signals.py
│   │   ├── data.py
│   │   ├── market.py
│   │   ├── stocks.py
│   │   └── journal.py
│   ├── services/           # 业务逻辑层
│   │   ├── signal_engine.py    # 150MA 信号计算
│   │   ├── data_service.py     # 数据拉取与调度
│   │   ├── pullback_detector.py # 回踩识别
│   │   └── market_service.py   # 大盘数据
│   ├── repositories/       # 数据访问层
│   └── external/           # 外部 API 客户端
│       └── polygon_client.py
├── alembic/                # 数据迁移
├── alembic.ini
├── pyproject.toml
├── Dockerfile
└── .env.example
```

### 项目根目录

```
stock_portal/
├── frontend/
├── backend/
├── docker-compose.yml
├── .env.example
├── CLAUDE.md
├── CHANGELOG.md
├── claude-progress.txt
└── docs/
    ├── 需求/
    ├── 系统设计/
    ├── 设计/
    ├── 验收/
    └── 开发/
```

---

## 环境配置

| 环境 | 用途 | 数据库 | Polygon API |
|------|------|-------|-------------|
| development | 本地开发 | backend/dev.db | 真实 API（.env 配置） |
| production | Docker 容器 | backend/data/prod.db (volume 挂载) | 真实 API（.env 配置） |

**两个环境的数据库必须严格分离，不得共用。**

环境变量（.env）：
```
POLYGON_API_KEY=your_key_here
DATABASE_URL=sqlite+aiosqlite:///./data/prod.db
REFRESH_CRON_HOUR=6    # 北京时间早6点 = 美东下午6点（收盘后）
REFRESH_CRON_MINUTE=0
```

---

## Widget 化架构原则

前端采用 Widget 化设计，每个 Widget 是独立的业务功能单元：

1. **自包含**：每个 Widget 自带数据获取（通过 hooks）、状态管理、UI 渲染
2. **可组合**：Page 层仅负责 Widget 的布局编排，不含业务逻辑
3. **解耦**：Widget 之间不直接通信，通过 URL 参数或共享的 API 数据间接联动
4. **独立开发**：每个 Widget 可以独立开发和测试

---

## 不可更改的约定

- 所有 API 返回格式见 `docs/系统设计/API-CONTRACT.md`
- 所有数据字段命名见 `docs/系统设计/DATA-MODEL.md`
- 所有颜色/间距/字体见 `frontend/src/styles/tokens.css`
- 数据库变更必须通过 Alembic 迁移脚本，不得直接修改表结构
