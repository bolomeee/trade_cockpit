---
status: confirmed
confirmed_at: 2026-06-10
last_modified_by: system-design (F220 正常化 P/E 体系 v2.6 — 新增 §Normalized Valuation 模块（workbench 纯函数，禁 import cockpit）+ FMP analyst-estimates 端点/常量 + weekly 周一 07:00 UTC cron；上一版 F218 Phase D 修正见 git history)
---

# ARCHITECTURE.md

> 最后更新：2026-04-24 | 状态：已确认
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
| LLM 抽象层（后端） | litellm | >=1.83,<2.0 | v2.0 引入，provider-agnostic 路由、Pydantic response_format、cost tracking、fallbacks 全覆盖（D064 / D069） |
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
│  Financial Modeling Prep (FMP)   │
│  /stable/ REST 端点              │
│  ├── EOD 日线 (historical-price-eod/full) │
│  ├── 指数 / 大盘 (quote, EOD) ^GSPC ^NDX  │
│  ├── 10Y 国债 (treasury-rates)   │
│  ├── 搜索 (search-symbol / search-name)    │
│  └── 基本面 TTM (ratios-ttm)     │
└──────────────────────────────────┘

> 数据源自 D034（2026-04-19）起从 Polygon (massive) Stocks Starter 迁移至 FMP Starter /stable/ 端点。
> `polygon_client.py` 保留作为 deprecated 回滚参考，不再被导入。
```

---

## 运行端口（权威表）

> 任何文档、脚本、CORS、跨项目集成均以此表为准。变更必须同步 `docker-compose.yml` 与 `frontend/vite.config.ts`。

| 服务 | 模式 | 容器内端口 | 宿主端口 | URL |
|------|------|-----------|----------|-----|
| 后端 FastAPI | 开发 (uvicorn --reload) | — | **8001** | http://localhost:8001 |
| 后端 FastAPI | Docker (发版) | 8000 | **8001** | http://localhost:8001 |
| 前端 Vite dev server | 开发 (pnpm dev) | — | **5173** | http://localhost:5173 |
| 前端 Nginx | Docker (发版) | 80 | **8080** | http://localhost:8080 |

**绝对约定：**
- **后端端口永远是 8001**（宿主侧），无论 dev 还是 Docker。容器内 8000 仅是 Docker 内部细节。
- 开发期访问入口：**http://localhost:5173**（Vite dev 代理 `/api` → `127.0.0.1:8001`）
- 发版后访问入口：**http://localhost:8080**（Nginx serve SPA + 反代 `/api` → backend:8000）
- 跨项目调用 stock_portal 后端 → 一律用 `http://localhost:8001/api/*`

---

## 依赖层级规则（不得违反）

### 前端

```
pages/Workbench.tsx     → 只能引用 workbench/
pages/Cockpit.tsx       → 只能引用 cockpit/（v1.8 新增，D060）

workbench/Workbench.tsx → 只能引用 workbench/WidgetRegistry
workbench/widgets/      → 只能调用 components/features/* 和 hooks/ 和 store/useAppStore

cockpit/CockpitShell.tsx → 只能引用 cockpit/CockpitRegistry
cockpit/widgets/        → 只能调用 cockpit/components/*、cockpit/hooks/*、store/cockpitStore
cockpit/components/     → cockpit 专属组件（CockpitChartWidget 等）
cockpit/hooks/          → cockpit 专属 React Query hooks（调用 lib/api/cockpit/*）
store/cockpitStore.ts   → cockpit 专属 client state（selectedTicker 等），**不 import useAppStore**

components/features/    → 业务组件（v1.0.0 既有），可被 workbench widget 包装复用；**cockpit 不使用**
components/ui/          → shadcn/ui 封装 + 通用纯展示组件（cockpit 和 workbench 共享 OK）
hooks/                  → workbench 专属；cockpit 用 cockpit/hooks/
lib/api/                → 调用后端 API；子目录 lib/api/cockpit/ 专属 cockpit
store/useAppStore       → workbench 专属 zustand store；cockpit 不 import
lib/                    → 纯工具函数，无副作用，任何层可用
```

**硬约束（v1.8 新增，D060）**：
- `cockpit/` ⇄ `workbench/` 零交叉 import（ESLint `no-restricted-imports` 规则 enforce）
- `store/cockpitStore.ts` ⇄ `store/useAppStore.ts` 零交叉 import
- 共享仅限于 `components/ui/`（shadcn 原生组件）和 `lib/`（纯函数 util）

> v1.1.0 起，`pages/` 目录收敛到 `Workbench.tsx`；v1.8 起重新扩展为 `Workbench.tsx` / `Cockpit.tsx` / `News.tsx` 三页并列，路由由 `App.tsx` 编排。v1.0.0 的 `Dashboard.tsx` / `Journal.tsx` / `Logs.tsx` 已在 Phase 4 清理，其内容迁移为 widget。

### 后端

```
routers/            → 只能调用 services/
routers/cockpit/    → 只能调用 services/cockpit/ 和 ai/（v1.8 新增）
services/           → 只能调用 repositories/ 和 external/
services/cockpit/   → 只能调用 repositories/cockpit/ 和 external/ 和 ai/；可 import signal_engine 的纯函数 util（MA/ATR 等）
repositories/       → 只能访问数据库（SQLAlchemy models）
repositories/cockpit/ → 只能访问 cockpit models（market_regime_snapshots / setup_snapshots / earnings_events / user_settings / positions / pending_orders / ai_memos）
external/           → 只能调用外部 API（FMP /stable/；polygon_client.py 为 deprecated 回滚参考，不再被导入）
models/             → SQLAlchemy ORM 定义，无业务逻辑
models/cockpit/     → cockpit 专属 ORM 定义（v1.8 新增，D060）
schemas/            → Pydantic 请求/响应模型
schemas/cockpit/    → cockpit 专属 Pydantic schema
ai/                 → LLM Gateway 抽象层（v2.0 新增，D064）
  ai/gateway.py     → AiGateway.run(task_type, input) 统一入口
  ai/routing.py     → task_type → tier → model_id 映射（env 驱动）
  ai/schemas/       → 每 task_type 的 Pydantic input/output schema
  ai/budget.py      → 月预算熔断
  ai/memo_repo.py   → ai_memos 表持久化 + 去重缓存查询
  ai/errors.py      → AiSchemaError / AiBudgetExceeded / AiGuardrailViolation / AiProviderError
```

**硬约束（v1.8 新增，D060）**：
- `routers/cockpit/` ⇄ `routers/{watchlist,signals,stocks,news,market,journal,logs,data,scanner}/` 零交叉 import
- `services/cockpit/` 可 import `services/signal_engine.py` 的**纯函数**（MA/ATR/linear regression 等，无状态、无 DB session），但**禁止 import**有状态服务（`journal_service`、`watchlist_service` 等）
- `ai/` 模块只被 `routers/cockpit/ai_router.py`（/api/ai/{task_type}）和 `services/cockpit/*` 调用；非 cockpit 路径禁止调用 AI

违反依赖方向的代码必须停止并报告，不得提交。

---

## 目录结构约定

### 前端 (frontend/)

```
frontend/
├── src/
│   ├── pages/              # v1.8 扩展为三页：Workbench / Cockpit / News
│   │   ├── Workbench.tsx
│   │   ├── Cockpit.tsx     # v1.8 新增（D060）
│   │   └── News.tsx
│   ├── workbench/          # v1.1.0 引入：Widget 框架
│   │   ├── WidgetRegistry.ts
│   │   ├── WidgetShell.tsx
│   │   ├── Workbench.tsx
│   │   ├── useLayoutStore.ts   # zustand + persist (localStorage: ma150.workbench.layouts.v5)
│   │   └── widgets/            # 薄包装，复用 components/features/*
│   ├── cockpit/            # v1.8 新增，与 workbench/ 零交叉引用
│   │   ├── CockpitRegistry.ts
│   │   ├── CockpitShell.tsx
│   │   ├── useCockpitLayoutStore.ts  # zustand + persist (localStorage: ma150.cockpit.layouts.v1)
│   │   ├── components/      # CockpitChartWidget（独立，不共享 ChartWidget） 等
│   │   ├── hooks/           # cockpit 专属 React Query hooks
│   │   └── widgets/         # MarketRegime / SetupMonitor / Decision / Earnings / Pool / Position / Action
│   ├── components/
│   │   ├── features/       # v1.0.0 业务组件（被 workbench widget 复用；cockpit 不使用）
│   │   └── ui/             # shadcn/ui 封装（共享）
│   ├── store/              # zustand 全局 state
│   │   ├── useAppStore.ts   # workbench 专属（selectedSymbol 等）
│   │   └── cockpitStore.ts  # v1.8 新增：cockpit 专属（selectedTicker / selectedSetup 等）
│   ├── hooks/              # 自定义 React Hooks（workbench 专用；cockpit 用 cockpit/hooks/）
│   ├── lib/
│   │   └── api/            # API 调用层（apiFetch 封装）
│   │       └── cockpit/    # v1.8 新增：cockpit API client
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
│   │   ├── journal_entry.py
│   │   └── cockpit/        # v1.8 新增（D060）
│   │       ├── market_regime_snapshot.py
│   │       ├── setup_snapshot.py
│   │       ├── earnings_event.py
│   │       ├── user_settings.py
│   │       ├── position.py
│   │       ├── pending_order.py
│   │       └── ai_memo.py
│   ├── schemas/            # Pydantic 请求/响应模型
│   │   └── cockpit/        # v1.8 新增：cockpit 专属 Pydantic schema
│   ├── routers/            # FastAPI 路由（按模块分文件）
│   │   ├── watchlist.py
│   │   ├── signals.py
│   │   ├── data.py
│   │   ├── market.py
│   │   ├── stocks.py
│   │   ├── journal.py
│   │   └── cockpit/        # v1.8 新增（D060）
│   │       ├── regime.py
│   │       ├── setup_monitor.py
│   │       ├── decision.py
│   │       ├── chart.py
│   │       ├── user_settings.py
│   │       ├── earnings.py
│   │       ├── pool.py
│   │       ├── positions.py
│   │       ├── pending_orders.py
│   │       ├── actions.py
│   │       └── ai_router.py    # POST /api/ai/{task_type}
│   ├── services/           # 业务逻辑层
│   │   ├── signal_engine.py    # 150MA 信号计算（MA/ATR 纯函数被 cockpit 复用）
│   │   ├── data_service.py     # 数据拉取与调度
│   │   ├── pullback_detector.py # 回踩识别
│   │   ├── market_service.py   # 大盘数据
│   │   └── cockpit/            # v1.8 新增（D060）
│   │       ├── market_regime_service.py
│   │       ├── setup_service.py
│   │       ├── decision_service.py         # entry/stop/size + deterministicHash
│   │       ├── cockpit_chart_service.py
│   │       ├── user_settings_service.py
│   │       ├── earnings_service.py
│   │       ├── pool_service.py
│   │       ├── position_service.py
│   │       ├── pending_order_service.py
│   │       └── action_service.py           # F207 deterministic 规则引擎
│   ├── repositories/       # 数据访问层
│   │   └── cockpit/        # v1.8 新增：7 张 cockpit 表的 repository
│   ├── ai/                 # v2.0 新增（D064 LiteLLM 抽象层）
│   │   ├── gateway.py      # AiGateway.run(task_type, input) 统一入口
│   │   ├── routing.py      # task_type → tier → model_id 映射（env 驱动）
│   │   ├── schemas/        # 每 task_type 的 Pydantic input/output schema
│   │   │   ├── market_narrator.py
│   │   │   ├── setup_explainer.py
│   │   │   ├── candidate_ranker.py
│   │   │   ├── trade_plan.py
│   │   │   ├── contradiction_detector.py
│   │   │   ├── news_summarizer.py
│   │   │   └── journal_assistant.py
│   │   ├── budget.py       # 月预算熔断查询
│   │   ├── memo_repo.py    # ai_memos 去重缓存 + 审计
│   │   ├── guardrail.py    # F210 trade_plan post-validate（D068）
│   │   └── errors.py       # AiSchemaError / AiBudgetExceeded / AiGuardrailViolation / AiProviderError
│   └── external/           # 外部 API 客户端
│       ├── fmp_client.py         # FMP /stable/ REST 客户端（D034 后的主数据源）
│       └── polygon_client.py     # DEPRECATED（D034），保留作为回滚参考，不被导入
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

| 环境 | 用途 | 数据库 | FMP API |
|------|------|-------|---------|
| development | 本地开发 | backend/dev.db | 真实 API（.env 配置 `FMP_API_KEY`） |
| production | Docker 容器 | backend/data/prod.db (volume 挂载) | 真实 API（.env 配置 `FMP_API_KEY`） |

**两个环境的数据库必须严格分离，不得共用。**

环境变量（.env）：
```
FMP_API_KEY=your_fmp_key_here           # D034 起主数据源
POLYGON_API_KEY=                         # LEGACY（D034 后不再使用，保留仅供回滚；默认留空不阻塞启动）
DATABASE_URL=sqlite+aiosqlite:///./data/prod.db
REFRESH_CRON_HOUR=6                      # watchlist EOD 刷新（北京 06:00 = 美东 18:00 收盘后）
REFRESH_CRON_MINUTE=0
SCANNER_CRON_HOUR=6                      # F105 每日市场扫描（错开 watchlist，避免 token bucket 竞争；D042）
SCANNER_CRON_MINUTE=15                   # 默认 06:15（watchlist refresh 耗时 <10s，留 15min 缓冲）
UNIVERSE_CRON_DAY=1                      # F105 候选池月级刷新：每月 1 号（D038）
UNIVERSE_CRON_HOUR=5                     # 05:00 早于 REFRESH/SCANNER，避免相互阻塞
UNIVERSE_CRON_MINUTE=0

# ── Cockpit Epic（v1.8 / v1.9 / v2.0 新增） ──

# F201 Market Regime 每日计算（依赖 market_indices 17 个 symbol 的 EOD 数据就绪）
REGIME_CRON_HOUR=6                       # 默认 06:30，在 REFRESH（06:00）之后
REGIME_CRON_MINUTE=30

# F202 Setup Monitor 每日计算（依赖 signals 表就绪）
SETUP_CRON_HOUR=6                        # 默认 06:45
SETUP_CRON_MINUTE=45

# F216 Weekly Stage refresh（工作日 22:20 UTC，在 regime 22:15 之后、setup 22:30 之前）
WEEKLY_STAGE_CRON_HOUR=22
WEEKLY_STAGE_CRON_MINUTE=20

# F204 Earnings Calendar 每日拉取（FMP /stable/earnings-calendar）
EARNINGS_CRON_HOUR=5                     # 05:30，早于 REFRESH，作为独立轻量调用
EARNINGS_CRON_MINUTE=30

# F206 Pending Order 到期扫描（置 EXPIRED）
PENDING_ORDER_EXPIRE_CRON_HOUR=7
PENDING_ORDER_EXPIRE_CRON_MINUTE=0

# F208 AI Gateway（LiteLLM）
OPENAI_API_KEY=sk-...                    # LiteLLM 默认 provider
# ANTHROPIC_API_KEY=...                  # 可选，LiteLLM 通过 model 字符串自动路由
AI_MODEL_DEFAULT=gpt-5.4-nano            # tier=default（F209 / contradiction / news_summarizer）
AI_MODEL_CRITICAL=gpt-5.4-mini           # tier=critical（F210 candidate_ranker / trade_plan）
AI_MODEL_COMPLEX=gpt-5.4                 # tier=complex（F211 journal_assistant / 月度审计）
AI_MONTHLY_BUDGET_USD=30                 # 月预算熔断阈值（超限抛 AI_BUDGET_EXCEEDED，不降级）
AI_MEMO_CACHE_TTL_HOURS=24               # ai_memos 去重缓存有效期
AI_SCHEMA_VERSION=v1                     # 对应 backend/app/ai/schemas/ 版本号，bump 后旧 memo 天然失效
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

---

## 外部数据源：FMP /stable/ 端点映射（D034）

| 后端职责 | FMP 端点 | 参数 | 替代的 Polygon 调用 |
|---------|---------|------|--------------------|
| 股票搜索（ticker 前缀优先） | `/stable/search-symbol` | `query`, `apikey` | `list_tickers(ticker_gte, ticker_lt)` |
| 股票搜索（公司名 fallback） | `/stable/search-name` | `query`, `apikey` | `list_tickers(search=...)` |
| 股票 EOD 日线 | `/stable/historical-price-eod/full` | `symbol=AAPL`, `apikey` | `list_aggs(ticker, "day", from, to)` |
| 大盘指数 SPX | `/stable/historical-price-eod/full` 或 `/stable/quote` | `symbol=^GSPC` | `list_aggs("I:SPX", ...)` |
| 大盘指数 NDX | 同上 | `symbol=^NDX` | `list_aggs("I:NDX", ...)` |
| 10Y 国债 TNX | `/stable/treasury-rates` | 无（取最新一条），读 `year10` 字段 | 直连 `/fed/v1/treasury-yields` |
| 基本面 TTM（F104） | `/stable/ratios-ttm` | `symbol=AAPL`, `apikey` | 无（Polygon Starter 不覆盖 CapEx，D002/D032 走 mock） |
| 全市场筛选（F105 universe 月级刷新） | `/stable/company-screener` | `marketCapMoreThan=50000000000`, `exchange=NYSE\|NASDAQ\|AMEX`（按交易所各调用一次，合并去重，不带 `country` 以覆盖 ADR）, `isEtf=false`, `isActivelyTrading=true`, `limit=500`, `apikey` | 无（Polygon Starter 无同类端点） |
| MA150 时间序列（F105 每日扫描主路径） | `/stable/technical-indicators/sma` | `symbol=AAPL`, `periodLength=150`, `timeframe=1day`, `from`/`to` 取最近 25 交易日窗口, `apikey` | 无；D039 fallback 方案 Y 改走 `/stable/historical-price-eod/full` 本地算 MA150 |
| ETF 日线（F201 SPY/QQQ/IWM + 11 sector ETF） | `/stable/historical-price-eod/full` | `symbol={SPY\|QQQ\|IWM\|XLK\|...}`, `apikey` | 无（v1.8 新增） |
| 财报日历（F204 earnings_events） | `/stable/earnings-calendar` | `from=today-7`, `to=today+30`, `apikey` | 无（v1.8 新增，D065） |
| 季度利润表（F218 T2 Margin Expansion） | `/stable/income-statement` | `symbol=AAPL`, `period=quarter`, `limit=8`, `apikey` | 无（v2.4 新增，D097 修正 2026-05-18：原计划 key-metrics+ratios quarterly Starter 不支持） |
| 季度资产负债表（F218 T5 Balance Sheet Inflection + T2 roic 近似公式） | `/stable/balance-sheet-statement` | `symbol=AAPL`, `period=quarter`, `limit=8`, `apikey` | 无（v2.4 新增，D097） |
| 季度现金流（F218 T2 fcf_margin + T5 balance sheet inflection，T2/T5 共享） | `/stable/cash-flow-statement` | `symbol=AAPL`, `period=quarter`, `limit=8`, `apikey` | 无（v2.4 新增，D097 修正：T2/T5 共享同一 endpoint，pool rebuild 单次抓取） |
| 分析师 EPS 预期（F220-e 预期修正方向） | `/stable/analyst-estimates` | `symbol=AAPL`, `period=annual`, `limit=...`, `apikey` | 无（v2.6 新增，weekly 周一 07:00 UTC 抓 watchlist+pool 快照，D106） |

> DB 层 `market_indices.symbol` 保留 `SPX/NDX/TNX` 三个原 symbol + v1.8 新增 14 个 ETF symbol（SPY/QQQ/IWM + 11 sector ETF），FMP 的 `^GSPC / ^NDX` 在 service/repo 边界做映射，ETF symbol 直接等于 FMP symbol；数据库字段命名不变。

### Rate Limit 策略

| 数据源 | 文档限速 | 本项目策略 |
|--------|---------|-----------|
| Polygon Stocks Starter（历史） | 5 req/min | Token bucket 5/min, burst 5，阻塞等待（D014） |
| **FMP Starter（D034 起）** | 300 req/min | Token bucket 300/min, burst 50，阻塞等待；超限退避 1s 后重试一次 |

理由：300/min 在单用户 + 30 只 watchlist 的场景下极难触达（满 refresh 约 30 次调用，耗时 <10s），token bucket 作为防御层防止 bug 导致误刷；burst 50 允许单次 refresh 一口气打完 30 只股票无人工节流。

### 实时性边界（FMP 能力限制）

- **本项目只使用 EOD 数据 + 盘后自动刷新**，不需要 intraday / WebSocket / 分钟级 aggs
- 如果未来引入需要实时报价或 Level-2 的 widget（期权、盘中扫描等），需要重新评估 FMP Starter 能力，或在该 feature 内单独引入额外订阅（D034 风险 6）

### Endpoint 常量集中管理

所有 `/stable/` 路径常量集中在 `backend/app/external/fmp_client.py` 顶部声明，例如：
```python
FMP_BASE = "https://financialmodelingprep.com/stable"
FMP_EP_RATIOS_TTM = "/ratios-ttm"
FMP_EP_HIST_EOD = "/historical-price-eod/full"
FMP_EP_TREASURY = "/treasury-rates"
FMP_EP_SEARCH_SYMBOL = "/search-symbol"
FMP_EP_SEARCH_NAME = "/search-name"
FMP_EP_QUOTE = "/quote"
FMP_EP_SCREENER = "/company-screener"          # F105 universe
FMP_EP_SMA = "/technical-indicators/sma"       # F105 每日扫描
FMP_EP_EARNINGS_CAL = "/earnings-calendar"     # F204 earnings_events（v1.8 新增）
FMP_EP_KEY_METRICS_TTM = "/key-metrics-ttm"    # F104 / D035 估值 TTM（marketCap/ROCE/FCF yield），与 F218 无关
FMP_EP_INCOME_STATEMENT = "/income-statement"  # F218 T2 Margin Expansion，period=quarter（v2.4 新增，D097 修正 2026-05-18 取代原 key-metrics+ratios quarterly）
FMP_EP_BALANCE_SHEET = "/balance-sheet-statement"  # F218 T5 Balance Sheet Inflection + T2 roic 近似公式分母（v2.4 新增，D097）
FMP_EP_CASH_FLOW = "/cash-flow-statement"      # F218 T2 fcf_margin + T5 balance sheet inflection（T2/T5 共享，v2.4 新增，D097）
FMP_EP_ANALYST_ESTIMATES = "/analyst-estimates"  # F220-e 预期修正方向（v2.6 新增，D106）
```
> F220 正常化 P/E 当前价（pool-非watchlist）复用 `LastCloseLoader._fmp_latest_close`（FMP EOD 末根），**不**新增 quote 方法（`FMP_EP_QUOTE` 仅声明未用，维持现状）；季度利润表 / 现金流复用 F218 既有 `get_income_statement_quarterly` / `get_cash_flow_quarterly`，仅在解析层新增字段（incomeTaxExpense / incomeBeforeTax / weightedAverageShsOutDil / stockBasedCompensation / OCF / capex）。
未来 FMP 若改路径，只改一处。

---

## AI Gateway（v2.0 新增，D064）

Cockpit P2 的 LLM 抽象层，**provider-agnostic**：业务代码只写 `AiGateway.run(task_type, input_dict)`，不关心用哪个 model。通过 `.env` 在 default / critical / complex 三档之间切换。

### 调用链

```
routers/cockpit/ai_router.py     # POST /api/ai/{task_type}
    ↓
services/cockpit/*               # 业务侧按需调用（F209 Market Regime Widget 顶部 AI Notes 等）
    ↓
ai/gateway.py  →  ai/routing.py  →  LiteLLM Router  →  OpenAI / Anthropic / ...
    ↓                    ↓
    └── ai/budget.py → 查 ai_memos.SUM(cost_usd) 判断是否超月预算
    ↓
    └── ai/memo_repo.py → 查 (task_type, input_hash, schema_version) 去重缓存
    ↓
    └── ai/guardrail.py → F210 trade_plan post-validate（entry/stop/size 必须等于 deterministicHash 对应值）
    ↓
    └── ai/schemas/{task_type}.py → Pydantic input/output 校验
```

### Tier → model 映射

| Tier | env 变量 | 默认值 | 覆盖的 task_type |
|------|---------|-------|----------------|
| default | `AI_MODEL_DEFAULT` | `gpt-5.4-nano` | market_narrator / setup_explainer / contradiction_detector / news_summarizer |
| critical | `AI_MODEL_CRITICAL` | `gpt-5.4-mini` | candidate_ranker / trade_plan |
| complex | `AI_MODEL_COMPLEX` | `gpt-5.4` | journal_assistant |

> 模型名以用户提供的 `gpt-5.4-*` 为准，未来可在 `.env` 自由改成 Anthropic、本地 Llama 等 LiteLLM 支持的 model 字符串，无需改业务代码。

### 强制约束

- **Pydantic schema 校验**：每次 LLM 调用必须走 `response_format=<PydanticModel>`；失败抛 `AiSchemaError` 并在 ai_memos **不入库**
- **月预算熔断**：`ai_memos.SUM(cost_usd) ≥ AI_MONTHLY_BUDGET_USD` → 抛 `AiBudgetExceeded`，不降级不 fallback（预期用户手动提高预算或等下月）
- **Guardrail（F210 trade_plan）**：post-validate 输出的 entry / stop / size 必须等于 `/api/cockpit/decision/{ticker}` deterministic 计算（2 位小数对齐）；不等 → 抛 `AiGuardrailViolation`，响应 409
- **禁止 non-cockpit 调用**：`ai/` 模块只允许被 `routers/cockpit/*` 和 `services/cockpit/*` import；`routers/news/*` 等禁止调用（即使 F211 news_summarizer 在概念上服务 News 页，入口仍走 cockpit ai_router）

### 去重缓存

- 每次调用前查 `(task_type, input_hash, schema_version)` 最近 `AI_MEMO_CACHE_TTL_HOURS` 内（默认 24h）的 memo
- 命中 → 返回 `output_json`，`meta.cacheHit=true`，不打 LLM
- schema_version bump（例如 `v1` → `v2`）→ 所有旧 memo 天然失效

### 数据流

请求 `/api/ai/trade_plan` 走 critical tier：
```
POST /api/ai/trade_plan
  body: { input: {ticker: "NVDA", ...}, noCache: false }
    ↓
ai_router 校验 task_type ∈ Literal[...]
    ↓
AiGateway.run("trade_plan", input):
  1. budget.check() → 若超限抛 AiBudgetExceeded
  2. memo_repo.get_cached(task_type, input_hash, schema_version) → 命中即返
  3. routing.resolve("trade_plan") → tier=critical → model=AI_MODEL_CRITICAL
  4. schemas.trade_plan.validate(input)
  5. litellm.completion(model=..., response_format=TradePlanOutput, messages=[...])
  6. schemas.trade_plan.parse(raw_output) → schema-validated
  7. guardrail.check_trade_plan(output, decision_service_result) → 违规抛
  8. memo_repo.write(task_type, input_hash, output, cost, tokens, ...)
  9. 返回 { output, meta }
```

---

## Cockpit Repricing Trigger Service（v2.4 新增，D096/D097/D098）

cockpit 慢交易框架第 4 支柱（与 Phase A Volume z-score / Phase B Weekly Stage / Phase C Capitulation Reversal 协同），识别"让市场重新定价此公司"的基本面 / 产业 / 资产负债事件。与价格 setup 完全解耦但在 DecisionPanel 同屏展示。

### 模块位置

```
backend/app/services/cockpit/repricing_trigger_service.py   # 主入口 + 5 detector
backend/app/repositories/repricing_trigger_repository.py    # repricing_triggers 表 CRUD
backend/app/repositories/key_metrics_repository.py          # stock_key_metrics_quarterly 表 CRUD（F218 D3 新增）
backend/app/repositories/fundamentals_repository.py         # stock_fundamentals_quarterly 表 CRUD（F218 D6 新增）
backend/app/routers/cockpit/repricing_triggers_router.py    # 2 endpoint
```

### 5 类 detector 串行调度

```
RepricingTriggerService.compute_and_store_all_triggers(date):
  1. _detect_earnings_acceleration(ticker)   # T1，复用 EarningsEventRepository
  2. _detect_margin_expansion(ticker)        # T2，读 stock_key_metrics_quarterly
  3. _detect_new_product(ticker)             # T3 D4a，扫描 news_cache headlines + 关键词集合
  4. _detect_sector_cycle(ticker)            # T4，复用 SECTOR_ETFS + market_regime_service._compute_rs_percentile
  5. _detect_balance_inflection(ticker)      # T5，读 stock_fundamentals_quarterly
  每个 detector 命中 → upsert repricing_triggers (UQ: ticker+trigger_type+detected_date)
  未命中 + 存在 active 既有行 → soft expire (active=true → false)
```

**串行非并发**：5 detector 总耗时预估 < 10s（pure DB 查询为主），串行便于错误隔离与日志归因（D096）。

### 调度时段

```
APScheduler cron 周一-周五 22:40 UTC（refresh_job.py）：
  → RepricingTriggerService.compute_and_store_all_triggers(today)

完整 cockpit 每日调度链（UTC）：
  05:30 earnings-calendar 增量（F204）
  06:30 weekly pool rebuild（仅周一，含 F218 D3/D6 FMP 3 endpoint 抓取 — income-statement / balance-sheet / cash-flow，cash-flow 由 T2/T5 共享 — 后 upsert 2 缓存表）
  22:05 market regime（F201）
  22:10 setup snapshots（F202/F203/F217）
  22:20 weekly stage（F216-e，仅周五）
  22:40 repricing triggers（F218，本次新增）
```

### FMP 数据获取（D097 决策）

- T2/T5 季度数据由 **weekly pool rebuild cron（周一 06:30 UTC）** 同步抓取，cockpit pool 内 ~50 ticker × 3 endpoint × 周 1 次 ≈ 150 calls/week（D097 修正 2026-05-18：原计划 4 endpoint 含 key-metrics-ttm + ratios quarterly Starter 不支持改 income-statement；T2/T5 共享 cash-flow，自然收敛到 3 endpoint）
- T2 margin / fcf_margin / roic 字段在 service 层从原始财务数字计算（详见 DATA-MODEL §StockKeyMetricsQuarterly 公式段）
- FMP Starter 限频 300 req/min 充裕（详见上文 Rate Limit 策略）
- T1（earnings）/T3（news）/T4（sector）detector 不需要新 FMP 调用（复用既有数据源）

### 模块边界

- `services/cockpit/repricing_trigger_service.py` 可 import：
  - `repositories/earnings_event_repository.py`（T1 复用）
  - `repositories/news_cache_repository.py`（T3 复用）
  - `repositories/key_metrics_repository.py` / `fundamentals_repository.py`（T2/T5 新建）
  - `services/cockpit/market_regime_service._compute_rs_percentile`（T4 函数级复用）
  - `services/cockpit/cockpit_params.SECTOR_ETFS`（T4 配置复用）
- **禁止 import**：`journal_service` / `watchlist_service` / `signal_engine`（除既有纯函数 utility 外）
- 前端 `frontend/src/cockpit/lib/api/cockpitRepricingApi.ts` 消费 2 endpoint；`RepricingTriggerWidget.tsx` 注册到 Cockpit Registry；`DecisionPanelWidget` 顶部 trigger badge 区按 `/repricing-triggers/{ticker}` 渲染（5 类颜色 chip 区分）

---

## Normalized Valuation（F220 正常化 P/E 体系，v2.6，D104–D107）

把 Fundamentals widget 的 P/E 从 FMP `/ratios-ttm` 透传的原始 GAAP P/E 升级为去噪 + 稳定的正常化估值体系。主锚 = 正常化 P/E（异常季用税后营业利润 NOPAT 替代 GAAP 净利润）；交叉验证 = P/(FCF−SBC)。**workbench 命名空间，非 cockpit。**

### 模块位置

```
backend/app/services/normalized_valuation.py                     # 纯函数模块（无 IO / 无 DB / 无日志）
backend/app/services/stock_detail_service.py                     # get_fundamentals 门控编排 + _resolve_current_price（既有，扩展）
backend/app/repositories/normalized_pe_history_repository.py     # normalized_pe_history 表 CRUD（F220-c 新增）
backend/app/repositories/analyst_estimate_snapshot_repository.py # analyst_estimate_snapshots 表 CRUD（F220-e 新增）
```

### 架构守约（硬约束，最易违反）

- `normalized_valuation.py` **照 `services/cockpit/pool_helpers.py` 的 `compute_*_from_*` 纯函数模式重写**（`_to_float` 容错 + None 传播），但**禁止 import `cockpit/pool_helpers`**（依赖层级规则：workbench 侧不得 import cockpit）。纯函数无 IO / 无 DB / 无日志，便于单测（含税率防循环回归测试）。
- 计算编排在 `stock_detail_service.get_fundamentals()`（service 层），FMP IO 在 `fmp_client`，落库在 repository — 遵 routers→services→repositories→models 单向依赖。
- trend pool 成员判断通过**只读访问 pool_cache 表（repository 层数据访问）**，**不** import cockpit service 逻辑；具体 repository 入口 F220-a 实现时确认（待查-1）。

### 编排链（get_fundamentals on-demand）

```
get_fundamentals(ticker):
  1. same-day daily_payload_cache 命中（含正常化字段）→ 直接返回
  2. 成员门控：stock = stocks.get_by_ticker(ticker)（watchlist active）OR trend pool 成员
     非成员 → 正常化字段 None + degradeReason="out_of_scope"，原始 TTM 照常返回（短路）
  3. 成员且 miss → fmp.get_income_statement_quarterly(ticker, limit=8)
                 + fmp.get_cash_flow_quarterly(ticker, limit=8)（复用 F218 方法，解析新增字段）
  4. _resolve_current_price(ticker, stock)：watchlist→daily_bars latest close；
     pool-非watchlist→LastCloseLoader._fmp_latest_close 模式（FMP EOD 末根）；fail-open None
  5. normalized_valuation 纯函数编排（税率破环 → 异常季 NOPAT → TTM 正常化 EPS → 正常化 P/E
     → P/(FCF−SBC) 双版本 + 红旗 → EPS 加速度 → 组装 traceability）
  6. 机会性 normalized_pe_history.upsert_today（成功才写，F220-c）
  7. estimateRevision：读 analyst_estimate_snapshot_repository.get_two_latest diff（F220-e）
  8. upsert_today_payload 落 daily cache
  fail-open：季报失败/不足 → 正常化字段 None + degradeReason，endpoint 仍 200
```

### 调度时段（F220-e 唯一新增 cron）

```
APScheduler cron 周一 07:00 UTC（refresh_job.py，紧接 06:30 pool rebuild、避开既有窗口）：
  → 对 watchlist(active) + trend pool 批量 fmp.get_analyst_estimates → analyst_estimate_snapshots upsert

注：正常化 P/E 计算本身**无 cron**（on-demand，成员门控 + 同日缓存）；
    normalized_pe_history 为 get_fundamentals 成功后**机会性写库**（非 cron）。
```

### 模块边界

- `services/normalized_valuation.py`（纯函数）：不 import 任何 service / repository / cockpit；只接收 dict/list 入参、返回 dict
- `services/stock_detail_service.py` 可 import：`external/fmp_client`、`repositories/normalized_pe_history_repository`、`repositories/analyst_estimate_snapshot_repository`、`services/normalized_valuation`（纯函数）、当前价 loader
- **禁止 import**：`services/cockpit/*`（含 `pool_helpers`）；pool 成员查询走只读 repository 入口（不引 cockpit service 逻辑）
- 阈值硬编码常量（带注释来源，R2）：异常季偏离 20% / 税率边界 0–50% / 红旗 40% / 滑动窗口 4 季 / 季报 limit=8
