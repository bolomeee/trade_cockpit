---
status: confirmed
confirmed_at: 2026-04-18
last_modified_by: workbench refactor phase 0 (v1.1.0)
---

# ARCHITECTURE.md

> 最后更新：2026-04-18 | 状态：已确认
> ⚠️ 技术栈变更必须先更新此文档并征得用户同意，不得擅自更改

---

## 技术栈（已确认）

| 层 | 技术 | 版本 | 选型原因 |
|----|------|------|---------|
| 前端框架 | React + TypeScript | React 19.2, TS 6.x | D012（2026-04-17 升级，原 React 18 / TS 5.x） |
| 构建工具 | Vite | 8.x | D012（2026-04-17 升级，原 Vite 6.x） |
| 样式 | Tailwind CSS | v4 | 用户指定 |
| UI 组件 | shadcn/ui | latest | 用户指定，可定制性好 |
| 图表 | lightweight-charts (TradingView) | 5.x | 专为金融 K 线图设计，~40KB，原生支持 OHLC + MA 叠加 |
| Widget 布局引擎 | react-grid-layout | 1.x | v1.1.0 引入，支持拖拽 + resize + 响应式断点（D029） |
| Client state（跨 widget） | zustand | 5.x | v1.1.0 引入，替代 React Query 不覆盖的跨 widget 联动状态（D030） |
| Server state | @tanstack/react-query | 5.x | v1.0.0 引入（D017） |
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
workbench/Workbench.tsx → 只能引用 WidgetRegistry
workbench/widgets/      → 只能调用 components/features/* 和 hooks/ 和 store/
components/features/    → 业务组件（v1.0.0 既有），可被 widget 包装复用
components/ui/          → shadcn/ui 封装 + 通用纯展示组件
hooks/                  → 只能调用 lib/api/
lib/api/                → 只能调用后端 API（apiFetch 封装）
store/                  → zustand client state，任何层可用
lib/                    → 纯工具函数，无副作用，任何层可用
```

> v1.1.0 起，`pages/` 目录收敛到仅 `Workbench.tsx`；v1.0.0 的 `Dashboard.tsx` / `Journal.tsx` / `Logs.tsx` 在 Phase 4 清理删除，其内容迁移为 widget。

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
│   ├── pages/              # v1.1.0 收敛到仅 Workbench（v1.0.0 的 Dashboard/Journal/Logs 已删除）
│   ├── workbench/          # v1.1.0 引入：Widget 框架
│   │   ├── WidgetRegistry.ts
│   │   ├── WidgetShell.tsx
│   │   ├── Workbench.tsx
│   │   ├── useLayoutStore.ts   # zustand + persist (localStorage)
│   │   └── widgets/            # 薄包装，复用 components/features/*
│   ├── components/
│   │   ├── features/       # v1.0.0 业务组件（被 widget 复用）
│   │   └── ui/             # shadcn/ui 封装
│   ├── store/              # v1.1.0 引入：跨 widget 全局 state（zustand）
│   ├── hooks/              # 自定义 React Hooks（React Query 包装）
│   ├── lib/
│   │   └── api/            # API 调用层（apiFetch 封装）
│   ├── types/              # TypeScript 类型定义
│   └── styles/
│       └── tokens.css      # Design Tokens
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

## Workbench Widget Framework（v1.1.0）

前端核心是一个 Workbench 单页面承载多个可拖拽 widget。加新功能 = 加一个 widget + 一个后端 endpoint + 注册一行。

### 层级

```
src/workbench/
├── WidgetRegistry.ts       # widget manifest（id → 组件 + 默认布局 + 分类）
├── WidgetShell.tsx         # 标准外壳（标题栏 + 拖拽 handle + 内容区）
├── Workbench.tsx           # react-grid-layout 容器
├── useLayoutStore.ts       # zustand + persist：layouts → localStorage
└── widgets/                # 薄包装，复用 components/features/*
    ├── WatchlistWidget.tsx
    ├── ChartWidget.tsx
    ├── FundamentalsWidget.tsx
    ├── PullbackWidget.tsx
    ├── JournalWidget.tsx
    ├── LogsWidget.tsx
    ├── MarketOverviewWidget.tsx
    └── QuickAddWidget.tsx

src/store/useAppStore.ts    # 跨 widget client state（selectedSymbol 等）
```

### Widget 契约

```typescript
type WidgetManifest = {
  id: string;                          // 唯一 id，如 "sma150.watchlist"
  title: string;
  component: React.ComponentType;      // 从 store 读共享态，自己 fetch 数据
  defaultLayout: { w: number; h: number; minW?: number; minH?: number };
  category?: string;                   // "sma150" | "scanner" | "news" | "ai" …
};
```

### 原则

1. **自包含**：每个 widget 自带数据获取（React Query hooks）、状态管理、UI 渲染
2. **可组合**：Workbench 只负责布局编排，不含业务逻辑
3. **解耦**：Widget 之间不直接通信，通过 zustand 全局 store（D030）间接联动
4. **独立开发**：每个 widget 可以独立开发和测试
5. **布局持久化**：localStorage，key `ma150.workbench.layouts.v1`，不进数据库（D029）
6. **后端零改动**：加 widget 不要求改现有 router；若需新数据，新增 router 遵循既有分层

---

## 不可更改的约定

- 所有 API 返回格式见 `docs/系统设计/API-CONTRACT.md`
- 所有数据字段命名见 `docs/系统设计/DATA-MODEL.md`
- 所有颜色/间距/字体见 `frontend/src/styles/tokens.css`
- 数据库变更必须通过 Alembic 迁移脚本，不得直接修改表结构
