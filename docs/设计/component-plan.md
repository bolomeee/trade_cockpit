# component-plan.md

> 最后更新：2026-04-17 | 维护者：design-bridge skill
> ⚠️ feature-dev 阶段开发组件前必须查阅本文件确认边界。不要引入未规划的组件。
> 技术栈：React 18 + TypeScript + Vite (SPA) + Tailwind CSS v4 + shadcn/ui。
> 项目不是 Next.js，**不使用 Server Components / 'use client'**；所有组件都是 React 函数组件。

---

## 第一节：页面与区块拆解

| 页面 | 路由 | 区块 |
|------|------|------|
| Dashboard | `/` | TopNav、MarketOverviewBar、SignalBoard、AddStockCard、JournalQuickAddCard |
| StockDetailModal | `/`（Modal） | HeaderSection（Ticker + 4 指标）、PriceChartCard、PullbackHistoryCard、FundamentalsCard |
| Trade Journal | `/journal` | TopNav、MarketOverviewBar、页头（Heading + "+ New Entry" 按钮）、FilterCard、JournalTable |
| New Trade Entry Dialog | `/journal`（Dialog） | DialogHeader、JournalEntryForm、DialogFooter |
| System Logs | `/logs` | TopNav、MarketOverviewBar、页头（Heading + LogLevelFilter）、LogsTable |

---

## 第二节：组件清单

### 基础组件 `src/components/ui/`

由 shadcn/ui 提供或基于其定制。全局复用，无业务逻辑，只接收 props 展示。

| 组件 | 来源 | 说明 |
|------|------|------|
| Button | shadcn/ui | 变体：default (primary 黑底)、outline (白底边框)、ghost、destructive |
| Input | shadcn/ui | 文本输入，含错误状态（红边 + 下方错误文字） |
| Card / CardHeader / CardContent / CardTitle | shadcn/ui | 内容卡片容器 |
| Badge | shadcn/ui | 基础徽章；Signal / Action / Level 业务 Badge 基于它扩展 |
| Select / SelectTrigger / SelectContent / SelectItem | shadcn/ui | 下拉选择 |
| Dialog / DialogHeader / DialogFooter / DialogTitle / DialogDescription / DialogClose | shadcn/ui | 弹窗（Backdrop + Dialog） |
| AlertDialog | shadcn/ui | 删除前二次确认 |
| Table / TableHeader / TableBody / TableRow / TableCell | shadcn/ui | 数据表格 |
| Textarea | shadcn/ui | 多行文本输入 |
| Skeleton | shadcn/ui | 加载占位 |
| Toggle / ToggleGroup | shadcn/ui | LogLevelFilter 的 chip toggle |
| Combobox（或 Command） | shadcn/ui | Add Stock 搜索下拉 |
| Popover | shadcn/ui | DatePicker 等浮层的容器 |
| DatePicker | shadcn/ui（基于 react-day-picker） | 日志表单的 Date 字段 |

### 业务组件 `src/components/features/`

含业务逻辑 / 跨页面复用。

| 组件 | 复用于 | 说明 |
|------|--------|------|
| TopNav | 所有页面 | MA150 Tracker 品牌 + 路由链接 + Last refresh + Refresh 按钮 |
| MarketOverviewBar | 所有页面 | 展示 S&P500 / NASDAQ100 / 10Y Treasury 三个指标 |
| RefreshButton | TopNav（内部） | 封装 `POST /api/data/refresh` 调用 + loading 态 |
| SignalBoard | Dashboard | 接收 stocks[]，渲染 SignalCard grid，按信号优先级排序 |
| SignalCard | SignalBoard | 单只股票卡片，点击触发 onOpenDetail(ticker) |
| SignalBadge | SignalCard / StockDetailModal Header | 5 枚举值 → token 颜色映射，根据 signalType 显示样式 |
| StockDetailModal | Dashboard | 容器，接收 ticker，内部并发拉取 4 接口，组合 Header + Chart + Tables |
| StockDetailHeader | StockDetailModal | 只读展示 Ticker + Badge + 公司名 + 4 指标行 |
| PriceChart | StockDetailModal | 基于 lightweight-charts：价格线 + MA150 线 + Pullback markers |
| PullbackHistoryCard | StockDetailModal | Table 展示 pullbacks[]，负值红、正值绿 |
| FundamentalsCard | StockDetailModal | 4 指标网格展示 + "Mock Data" Badge |
| AddStockCard | Dashboard sidebar | Input + Combobox 搜索 + 调用 watchlist POST |
| JournalQuickAddCard | Dashboard sidebar | 精简版 Journal 表单（ticker / action / price）|
| JournalTable | /journal | 接收 entries[]，含 Expand / Edit / Delete 行内交互 |
| JournalRow | JournalTable | 单行；展开区显示 reason / reference / stopLoss / targetPrice |
| ActionBadge | JournalTable / JournalQuickAdd | 5 枚举值 → token 颜色映射 |
| JournalFilterCard | /journal | 两个 Select + Clear Filters 按钮；受控组件 |
| JournalEntryDialog | /journal | 新建和编辑共用；接收 mode: 'new' \| 'edit' 和可选 initialEntry |
| JournalEntryForm | JournalEntryDialog | 纯表单，不关心打开/关闭；接收 onSubmit / onCancel |
| LogsTable | /logs | 接收 logs[]，单级表 |
| LogLevelFilter | /logs | 5 chip ToggleGroup（ALL / OK / INFO / WARN / ERROR）|
| LogLevelBadge | LogsTable | level 枚举 → token 颜色映射；WARN 为 outline 风格 |
| EmptyState | 全局 | 空状态容器，接收 icon / title / description / action |
| ErrorState | 全局 | 错误状态容器，接收 title + retry 回调 |

### 页面组件 `src/pages/`

Vite SPA 每个路由对应一个页面组件，负责：数据获取（通过 react-query）+ 区块组合 + 状态切换（loading / empty / error / success）。

| 页面组件 | 路由 | 关键接口 |
|----------|------|---------|
| DashboardPage | `/` | GET /api/watchlist, GET /api/market/overview |
| JournalPage | `/journal` | GET /api/journal |
| LogsPage | `/logs` | GET /api/logs |

StockDetailModal 虽为弹窗但逻辑复杂，作为"业务组件"放在 `features/` 下，由 DashboardPage 通过 `selectedTicker` 状态控制显隐。

### 路由容器 `src/App.tsx`

- `react-router-dom v6+`：BrowserRouter + Routes
- 顶层布局：TopNav + MarketOverviewBar 固定在所有路由外（共享）
- Outlet 渲染具体 PageComponent

---

## 第三节：组件边界定义

只列出业务组件的 props 契约。基础组件用法见 shadcn/ui 官方文档（必要时通过 context7 查询 `/shadcn-ui/ui`）。

### TopNav
- Props：无（内部自己读 `react-router` 的 location 和 react-query 的 refresh mutation 状态）
- 职责：品牌 + 路由链接（高亮当前）+ RefreshButton
- 不包含：MarketOverviewBar（独立组件）

### MarketOverviewBar
- Props：无（内部通过 react-query 订阅 `GET /api/market/overview`，5 分钟刷新一次）
- 职责：展示 3 指标 + 涨跌配色
- 不包含：手动刷新（用 TopNav 的按钮）

### RefreshButton
- Props：无（内部 mutation `POST /api/data/refresh`，成功后 invalidate 相关 query）
- 职责：按钮 UI + loading 态管理
- 不包含：Last refresh 时间展示（由 TopNav 读取 `GET /api/data/status` 渲染）

### SignalBoard
- Props：`stocks: WatchlistItem[]`（已按 signal 优先级排序）、`onSelectStock: (ticker: string) => void`
- 职责：grid 布局 + 渲染 SignalCard × N
- 不包含：数据获取（由 DashboardPage 拉取）、空/加载/错误态（由 DashboardPage 切换）

### SignalCard
- Props：`stock: WatchlistItem`（含 latestSignal）、`onClick: () => void`
- 职责：单卡片展示 + 点击回调
- 不包含：路由/Modal 打开逻辑（DashboardPage 管理 selectedTicker）

### SignalBadge
- Props：`signalType: 'BREAKOUT' | 'BUY_ZONE' | 'NEUTRAL' | 'INSUFFICIENT'`、`size?: 'sm' | 'md'`
- 职责：根据 signalType 返回对应颜色 token + 显示文本（"BUY ZONE" 用空格分隔，其他大写）
- 必须：使用 `--color-signal-*` token，不直接写 hex

### StockDetailModal
- Props：`ticker: string | null`（null 时隐藏）、`onClose: () => void`
- 职责：Dialog 容器 + 并发拉取 4 接口 + 组合 4 子区块 + 4 种状态切换
- 内部 state：无业务 state，全部通过 react-query

### PriceChart
- Props：`bars: DailyBar[]`（按日期升序）、`ma150Values: { date: string; value: number | null }[]`、`pullbacks: Pullback[]`、`height?: number`
- 职责：初始化 lightweight-charts + 2 条 line series + pullback markers
- ⚠️ 必须：通过 useEffect cleanup 销毁 chart 实例，避免内存泄漏

### PullbackHistoryCard
- Props：`pullbacks: Pullback[]`
- 职责：Card + Table 渲染；空数组展示"No pullbacks yet"
- 配色：Distance 负值用 `--color-change-negative`；10D/20D/30D 按正负；null 显示 "—"

### FundamentalsCard
- Props：`fundamentals: Fundamentals | null`（null 时不渲染本 Card 或显示空态）
- 职责：CardHeader 含 "Mock Data" Badge + 4 指标 Grid
- ⚠️ 当前 API 返回的是 mock 数据，Badge 不能移除直到接入真实数据源

### AddStockCard
- Props：无
- 职责：受控 Input + Combobox 下拉（debounce 300ms 调 `GET /api/stocks/search`）+ 提交 `POST /api/watchlist`
- 成功后 invalidate watchlist query

### JournalQuickAddCard
- Props：无
- 职责：3 字段（ticker / action / price）+ "+ Add Entry" 按钮
- 提交成功后 invalidate journal query；失败显示内联错误
- 不包含：position / stopLoss / target / reason / reference（这些只在完整 Dialog 填写）

### JournalTable
- Props：`entries: JournalEntry[]`、`onEdit: (entry) => void`、`onDelete: (id: number) => void`
- 职责：渲染 + 展开行显示详情
- 不包含：数据获取、Dialog 管理（由 JournalPage 负责）

### ActionBadge
- Props：`action: 'BUY' | 'SELL' | 'ADD' | 'REDUCE' | 'WATCH'`
- 职责：枚举 → token 颜色映射 + 显示
- 必须：使用 `--color-action-*` token

### JournalFilterCard
- Props：`filter: { ticker?: string; action?: Action }`、`onChange: (next) => void`、`tickerOptions: string[]`（去重后的 watchlist ticker）
- 职责：受控组件，3 个 UI 元素（2 Select + 1 Clear Filters 按钮）

### JournalEntryDialog
- Props：`open: boolean`、`mode: 'new' | 'edit'`、`initialEntry?: JournalEntry`、`onClose: () => void`、`onSaved: () => void`
- 职责：Dialog 容器 + JournalEntryForm + 提交逻辑（POST / PUT）

### JournalEntryForm
- Props：`initialValues?: JournalEntryInput`、`onSubmit: (values) => Promise<void>`、`onCancel: () => void`
- 职责：纯表单 + 校验（ticker/date/action/price 必填）
- 使用 `react-hook-form` + `zod` 校验（符合项目技术栈偏好，若 ARCHITECTURE 未定可由 feature-dev Sprint Contract 确认）

### LogsTable
- Props：`logs: SystemLog[]`
- 职责：Table 渲染；Timestamp mono 字体；Message 截断 + hover tooltip

### LogLevelFilter
- Props：`value: 'ALL' | 'OK' | 'INFO' | 'WARN' | 'ERROR'`、`onChange: (next) => void`
- 职责：5 chip ToggleGroup；单选

### LogLevelBadge
- Props：`level: 'OK' | 'INFO' | 'WARN' | 'ERROR'`
- 职责：枚举 → token 颜色映射；WARN 用 outline 风格

### EmptyState
- Props：`title: string`、`description?: string`、`action?: { label: string; onClick: () => void }`
- 职责：统一空状态展示

### ErrorState
- Props：`title?: string`（默认"加载失败"）、`onRetry: () => void`
- 职责：统一错误状态展示 + 重试按钮

---

## 第四节：数据获取职责划分

> Vite SPA 无 Server Components；本节替代 skill 模板中的 "Server/Client 划分"，说明哪层负责拉数据。

**原则**：
- 页面组件（`src/pages/*.tsx`）拉取该页所需的主数据
- 全局共享数据（MarketOverview、Last refresh）由 TopNav / MarketOverviewBar 自己订阅
- StockDetailModal 虽然是业务组件，但因 4 接口仅在打开时才需拉取，由组件自身用 react-query 管理，避免 Dashboard 提前加载
- 其他业务组件接收 props，不自己拉数据

**react-query 缓存策略**（建议，feature-dev 阶段可微调）：

| query key | 关键字段 | staleTime | 失效触发 |
|-----------|---------|----------|---------|
| `['watchlist']` | — | 30s | 添加/删除股票、手动刷新 |
| `['market-overview']` | — | 5min | 手动刷新 |
| `['signals', ticker]` | ticker | 30s | 手动刷新 |
| `['pullbacks', ticker]` | ticker | 5min | 手动刷新 |
| `['chart', ticker]` | ticker | 5min | 手动刷新 |
| `['fundamentals', ticker]` | ticker | 1h（Mock，变化少） | — |
| `['journal', filter]` | ticker/action | 0（每次 mount 刷新） | 新增/编辑/删除 |
| `['logs', level]` | level | 30s | 手动刷新按钮（可选） |
| `['data-status']` | — | 10s | refresh mutation 成功后 |

---

## 目录结构（建议）

```
src/
├── components/
│   ├── ui/                  # shadcn 生成或封装的基础组件
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   └── …（按需）
│   └── features/
│       ├── nav/
│       │   ├── TopNav.tsx
│       │   ├── MarketOverviewBar.tsx
│       │   └── RefreshButton.tsx
│       ├── dashboard/
│       │   ├── SignalBoard.tsx
│       │   ├── SignalCard.tsx
│       │   ├── SignalBadge.tsx
│       │   ├── AddStockCard.tsx
│       │   └── JournalQuickAddCard.tsx
│       ├── stock-detail/
│       │   ├── StockDetailModal.tsx
│       │   ├── StockDetailHeader.tsx
│       │   ├── PriceChart.tsx
│       │   ├── PullbackHistoryCard.tsx
│       │   └── FundamentalsCard.tsx
│       ├── journal/
│       │   ├── JournalTable.tsx
│       │   ├── JournalRow.tsx
│       │   ├── ActionBadge.tsx
│       │   ├── JournalFilterCard.tsx
│       │   ├── JournalEntryDialog.tsx
│       │   └── JournalEntryForm.tsx
│       ├── logs/
│       │   ├── LogsTable.tsx
│       │   ├── LogLevelFilter.tsx
│       │   └── LogLevelBadge.tsx
│       └── common/
│           ├── EmptyState.tsx
│           └── ErrorState.tsx
├── pages/
│   ├── DashboardPage.tsx
│   ├── JournalPage.tsx
│   └── LogsPage.tsx
├── lib/
│   ├── api/                 # fetch 封装 + 类型定义（对应 API-CONTRACT.md）
│   └── utils.ts             # cn / format 工具
├── styles/
│   ├── tokens.css           # 已生成
│   └── globals.css          # tailwind base + tokens 接入
├── App.tsx
└── main.tsx
```

---

## 边界红线

开发时发现以下需求，请**先回到 design-bridge** 更新本文件，不要擅自扩展：

1. 新增不在清单里的业务组件
2. 让 SignalCard / JournalRow 等"只展示"组件自己发起 API 调用
3. 往 ui/ 目录放业务组件（ui/ 只放 shadcn 基础）
4. 直接在组件中写 hex 颜色值（必须用 `--color-*` token）
5. 把 Journal 完整表单拆到 Dashboard Widget（Dashboard 只保留 quick add 3 字段，完整字段在 Dialog 录）
