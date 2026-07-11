# component-plan.md

> 最后更新：2026-07-11 | 维护者：design-bridge skill
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
| TopNav | 所有页面 | MA150 Tracker 品牌 + 路由链接 + Last refresh + 主题切换 + 同组操作按钮 |
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
- 职责：品牌 + 路由链接（高亮当前）+ Last refresh + 主题切换 + 路由相关操作。
  - 右侧操作统一由一个 `ButtonGroup` 承载；主题切换为首项，紧接 Last refresh，后接当前路由可用的 AI 摘要、刷新、布局、设置与同步操作。
  - 主题状态来自 `useThemeStore`，切换按钮在所有路由可见；深色显示 `Sun` / “切换到浅色模式”，浅色显示 `Moon` / “切换到深色模式”。
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

---

# v1.8 / v1.9 / v2.0 · Cockpit 章节（2026-04-24 design-bridge 扩展）

> 关联 Feature：F200–F211
> 关联 design-spec：`design-spec.md` v1.8/v1.9/v2.0 Cockpit 章节
> 关联架构：D060（Cockpit 独立第三页 ⟂ Workbench）+ D060-a（沿用 RGL 引擎，独立 Registry/Store/localStorage）

---

## §Cockpit-1：页面与区块拆解

| 页面 | 路由 | 区块 |
|---|---|---|
| Cockpit | `/cockpit` | TopNav（共享 ButtonGroup：主题 + 刷新 + ResetLayout + Settings + 布局同步）、MarketOverviewBar（共享）、CockpitGrid（react-grid-layout）、9 个 widget、UserSettingsDialog |

CockpitGrid 默认布局见 `design-spec.md` 表格（左 4 cols / 中 5 cols / 右 3 cols；rowHeight 40 / margin 12 / padding 16，与 Workbench 一致）。

---

## §Cockpit-2：组件清单

### 基础组件 `src/components/ui/`（既有，无新增）

shadcn/ui 全局复用；Cockpit 不引入新基础组件。

### Cockpit 共享子组件 `src/cockpit/components/`

> 多个 Cockpit widget 内复用，不在 Workbench 里出现。位于 cockpit/ 子目录，不放 features/ 全局区。

| 组件 | 复用于 widget | 说明 |
|---|---|---|
| `RegimePill` | MarketRegime | 5 枚举 → token `--color-regime-*`，badge 风格 |
| `SetupTypeBadge` | SetupMonitor / DecisionPanel / PoolBuilder / Position / PendingOrder / Chart 标题 | 7 枚举 → token `--color-setup-*`；NONE 渲染 "—" |
| `SetupQualityBadge` | SetupMonitor / DecisionPanel / Chart 标题 | A/B/C/null → `--color-setup-quality-*` |
| `EarningsRiskDot` | SetupMonitor / DecisionPanel / Position / Earnings | SAFE/CAUTION/DANGER → token；DANGER 附 "D-{n}" |
| `ChartHorizontalLine` | CockpitChart | 封装 lightweight-charts `createPriceLine`，props `{ price, color, lineStyle, title }` |
| `WidgetShell`（共享自 Workbench） | 全部 cockpit widget | 复用既有，不重新实现；通过 props/className 适配 |

> WidgetShell 在 `src/components/widgets/WidgetShell.tsx`（shared 跨页）；cockpit 仅 import 不修改。

### Cockpit Widget 组件 `src/cockpit/widgets/`

| 组件 | 关联 Feature | 主接口 |
|---|---|---|
| `MarketRegimeWidget` | F201 | `GET /api/cockpit/regime` + `POST /api/ai/market_narrator`（v2.0） |
| `EarningsWidget` | F204 | `GET /api/cockpit/earnings?ticker=` |
| `PoolBuilderWidget` | F205（v1.9） | `GET /api/cockpit/pool` + `POST /api/watchlist` |
| `CockpitChartWidget` | F203 | `GET /api/cockpit/chart/{ticker}` + `GET /api/cockpit/decision/{ticker}` |
| `SetupMonitorWidget` | F202 | `GET /api/cockpit/setup-monitor?filter=` + `POST /api/ai/setup_explainer`（v2.0 hover） |
| `DecisionPanelWidget` | F203 + F210/F211 | `GET /api/cockpit/decision/{ticker}` + `POST /api/ai/trade_plan` + `POST /api/ai/contradiction_detector` + `POST /api/cockpit/pending-orders` |
| `PositionListWidget` | F206（v1.9） | `GET / POST / PATCH / DELETE /api/cockpit/positions` |
| `PendingOrdersWidget` | F206（v1.9） | `GET / POST / PATCH / DELETE /api/cockpit/pending-orders` |
| `ActionListWidget` | F207（v1.9） | `GET /api/cockpit/actions/today` + `POST /api/ai/contradiction_detector`（v2.0 brief） |
| `RepricingTriggerWidget` | F218 | `GET /api/cockpit/repricing-triggers` + `GET /api/cockpit/repricing-triggers/{ticker}`（chip 区共用） |

### Cockpit Dialog 组件

| 组件 | 关联 Feature | 主接口 |
|---|---|---|
| `UserSettingsDialog` | F203 | `GET / PUT /api/cockpit/user-settings` |
| `PositionFormDialog` | F206（v1.9） | `POST / PATCH /api/cockpit/positions` |
| `PendingOrderFormDialog` | F206（v1.9） | `POST / PATCH /api/cockpit/pending-orders` |
| `SaveAsPendingOrderConfirm` | F203 | `POST /api/cockpit/pending-orders`（DecisionPanel 触发） |

### Cockpit 框架组件

| 组件 | 关联 Feature | 说明 |
|---|---|---|
| `CockpitPage` | F200 | 顶层路由组件，初始化 `useCockpitLayoutStore` + 渲染 RGL Grid |
| `CockpitRegistry`（`src/cockpit/CockpitRegistry.ts`） | F200 | 9 个 widget 的 manifest（id / component / defaultLayout / minW/H）；与 `WidgetRegistry.ts` 完全独立 |
| `useCockpitLayoutStore`（`src/cockpit/store/useCockpitLayoutStore.ts`） | F200 | zustand + persist；localStorage key `ma150.cockpit.layouts.v1`；与 `useAppStore` 零交叉 |
| `useCockpitStore`（`src/cockpit/store/useCockpitStore.ts`） | F200 | 共享 cockpit 范围内状态：`selectedTicker`、`setSelectedTicker(t)`、`mas` 选择、`timeframe`；不持久化（运行时） |

### Cockpit 路由 / 页面

| 页面组件 | 路由 | 关键接口 |
|---|---|---|
| CockpitPage | `/cockpit` | 初始化 layout store；TopNav 高亮；齿轮按钮挂载 UserSettingsDialog |

### TopNav / MarketOverviewBar 沿用

不为 Cockpit 单独实现 nav 组件；TopNav 内部按 `useLocation` 增加 `/cockpit` 高亮分支，并在同一个右侧 `ButtonGroup` 内依次组合主题切换、刷新、`[Reset Layout]`、`[⚙ Settings]` 和布局同步按钮。MarketOverviewBar 共享。

---

## §Cockpit-3：组件边界定义

> 仅列出 Cockpit 业务组件 props 契约。基础组件 / shadcn 用法见官方文档。

### CockpitPage
- Props：无（react-router 路由组件）
- 职责：初始化 `useCockpitLayoutStore` + 渲染 RGL Grid + 遍历 `CockpitRegistry` 渲染 widgets
- 不包含：数据获取（每个 widget 自取）

### CockpitRegistry（不是 React 组件，是 manifest 数组）
- 形态：`{ id, component, title, defaultLayout: { x, y, w, h, minW, minH }, version }[]`
- 用途：CockpitPage 遍历渲染；ResetLayout 按钮恢复 defaultLayout

### useCockpitLayoutStore
- State：`layouts: Layouts`（react-grid-layout 标准结构，按断点 `{ lg, md, sm }`）
- Actions：`setLayouts(next)`、`reset()`
- 持久化：localStorage key `ma150.cockpit.layouts.v1`，version 字段嵌入 layouts 末位（schema 升级时 reset）

### useCockpitStore
- State：`selectedTicker: string | null`、`mas: number[]`（默认 `[10,21,50,150,200]`）、`timeframe: 'D' | 'W'`（默认 'D'）
- Actions：`setSelectedTicker(t)`、`setMas(m)`、`setTimeframe(tf)`
- 持久化：无（运行时）

### MarketRegimeWidget
- Props：无
- 内部：自取 `GET /api/cockpit/regime`；点击 indices 行 → `useCockpitStore.setSelectedTicker(symbol)`
- AI 子区：v2.0 起渲染 AI Notes 区域，按钮触发 `POST /api/ai/market_narrator`，cache TTL 由 backend 控制（meta.cacheHit）
- 不包含：sector 点击的 SetupMonitor 过滤逻辑（直接派发到 SetupMonitor 自己的 query 状态，需要在 useCockpitStore 加 `sectorFilter` 字段或局部 state — v1.8 决策见 design-spec "待 feature-dev 阶段细化的项"）

### EarningsWidget
- Props：无
- 内部：subscribe `useCockpitStore.selectedTicker`，selectedTicker 改变时调 `GET /api/cockpit/earnings?ticker=`；watchlist 多 ticker 时循环调用（v1.8 简化）

### PoolBuilderWidget（v1.9）
- Props：无
- 内部：filter 状态 = local React state（不入 store；切页签即丢）；调 `GET /api/cockpit/pool`，debounce 300ms
- `[+ Add]` 按钮：调 `POST /api/watchlist` + react-query invalidate `['cockpit-pool']` + `['watchlist']`

### CockpitChartWidget
- Props：无
- 内部：subscribe `useCockpitStore.{selectedTicker, mas, timeframe}`；selectedTicker 改变时联合 fetch `GET /api/cockpit/chart/{ticker}` + `GET /api/cockpit/decision/{ticker}`；通过 `ChartHorizontalLine` 子组件叠加 entry/stop/target 横线
- ⚠️ 必须：useEffect cleanup 销毁 lightweight-charts 实例
- 技术约束（D063）：独立组件，不复用 Workbench `ChartWidget`，不 import workbench 任何文件

### SetupMonitorWidget
- Props：无
- 内部：filter 状态 = local React state（[Ready/Near/...] tab）；调 `GET /api/cockpit/setup-monitor?filter=`
- 行点击 → `useCockpitStore.setSelectedTicker(ticker)` 联动 Chart/Decision/Earnings
- v2.0 hover [?] → 调 `POST /api/ai/setup_explainer`，缓存 24h（meta.cacheHit）

### DecisionPanelWidget
- Props：无
- 内部：subscribe `useCockpitStore.selectedTicker`；override 输入 = local React state（debounce 500ms 触发 query 重发）；调 `GET /api/cockpit/decision/{ticker}?entryOverride=&stopOverride=&riskPctOverride=`；user-settings 通过独立 query `['cockpit-user-settings']` 获取
- AI 子区：v2.0 [Generate AI Plan] 按钮 → `POST /api/ai/trade_plan`，guardrail 失败 (HTTP 409) 显示红 banner
- [Save as PendingOrder] → 弹 `SaveAsPendingOrderConfirm`，确认后 `POST /api/cockpit/pending-orders` + invalidate `['cockpit-pending-orders']`

### PositionListWidget（v1.9）
- Props：无
- 内部：subscribe `status` 切换 (open/closed/all) = local state；调 `GET /api/cockpit/positions?status=`
- [+ New Position] → 弹 `PositionFormDialog`
- 行内联编辑（stop / status / closedAt / closePrice / notes）→ `PATCH /api/cockpit/positions/{id}`
- 删除 → `DELETE /api/cockpit/positions/{id}`，AlertDialog 二次确认

### PendingOrdersWidget（v1.9）
- Props：无
- 内部：subscribe `status` 切换 = local state；调 `GET /api/cockpit/pending-orders?status=`
- [+ New Order] → 弹 `PendingOrderFormDialog`
- [Triggered] → confirm "已在券商手动下单？" → `PATCH` body `{ status: "TRIGGERED" }` + invalidate `['cockpit-pending-orders']` + `['cockpit-positions']`（若 v1.9 决定自动创建 position）
- [Cancel] → `PATCH` body `{ status: "CANCELLED" }`，无二次确认

### ActionListWidget（v1.9）
- Props：无
- 内部：调 `GET /api/cockpit/actions/today`；行点击 ticker → `setSelectedTicker(t)`
- v2.0 AI Daily Brief 折叠区：默认收起；展开时调 `POST /api/ai/contradiction_detector`

### UserSettingsDialog
- Props：`open: boolean`、`onClose: () => void`
- 内部：mount 时 `GET /api/cockpit/user-settings`；`react-hook-form` + `zod` 校验；提交 `PUT /api/cockpit/user-settings` + invalidate `['cockpit-user-settings']` + `['cockpit-decision', selectedTicker]`（user_setting_cap 影响 effective risk）
- 触发：CockpitPage 在 TopNav 渲染齿轮按钮 → `setOpen(true)`

### PositionFormDialog
- Props：`open: boolean`、`mode: 'new' | 'edit'`、`initialPosition?: Position`、`onClose: () => void`、`onSaved: () => void`
- 内部：`react-hook-form` + `zod`（entry > 0；stop > 0；entry > stop；shares > 0）；POST/PATCH 后 onSaved → invalidate `['cockpit-positions']`
- 提示行（仅 New 模式）：从 `useCockpitStore.selectedTicker` 联合 `['cockpit-decision', t]` 取 `suggestedShares`，下方灰字 "Cockpit 推荐 {n} shares"

### PendingOrderFormDialog
- Props：`open`、`mode`、`initialOrder?`、`onClose`、`onSaved`
- 校验：entry > stop；shares > 0；expirationDate ≥ today（可选字段，不强制）

### SaveAsPendingOrderConfirm
- Props：`open`、`payload: PendingOrderInput`、`onConfirm() => Promise<void>`、`onClose() => void`
- 简单 AlertDialog 形态，文案见 design-spec

### RegimePill / SetupTypeBadge / SetupQualityBadge / EarningsRiskDot / ChartHorizontalLine
（共享子组件）
- Props 见 design-spec "共享子组件"小节定义；纯展示，不发请求
- 必须使用 token，不允许内联 hex

---

## §Cockpit-4：数据获取职责划分（react-query 缓存策略）

| query key | 数据接口 | staleTime | 失效触发 |
|---|---|---|---|
| `['cockpit-regime']` | GET /api/cockpit/regime | 5min | 手动刷新；regime cron 跑完（v1.8 暂无 push 通道，靠 staleTime） |
| `['cockpit-setup-monitor', filter]` | GET /api/cockpit/setup-monitor | 5min | 同上 |
| `['cockpit-chart', ticker, mas, timeframe]` | GET /api/cockpit/chart/{ticker} | 5min | 切换 ticker 自动 refetch |
| `['cockpit-decision', ticker, overrides]` | GET /api/cockpit/decision/{ticker} | 30s | overrides 改变（debounce 500ms 触发 invalidate） |
| `['cockpit-earnings', ticker]` | GET /api/cockpit/earnings?ticker= | 1h | 手动刷新 |
| `['cockpit-pool', filters]` | GET /api/cockpit/pool | 1min | filters 改变（debounce 300ms） |
| `['cockpit-positions', status]` | GET /api/cockpit/positions?status= | 30s | POST/PATCH/DELETE 后 invalidate |
| `['cockpit-pending-orders', status]` | GET /api/cockpit/pending-orders?status= | 30s | POST/PATCH/DELETE 后 invalidate |
| `['cockpit-actions-today']` | GET /api/cockpit/actions/today | 5min | 手动刷新 |
| `['cockpit-user-settings']` | GET /api/cockpit/user-settings | Infinity | PUT 后 invalidate（同时 invalidate decision） |
| `['ai-memo', taskType, inputHash]` | POST /api/ai/{task_type} | Infinity | 由 backend memo 表去重；前端不 invalidate（schema 升级时 backend 自动失效） |

---

## §Cockpit-5：目录结构（cockpit 子树）

```
src/
├── cockpit/                       # ⟂ workbench/，零交叉 import（ESLint enforce）
│   ├── CockpitPage.tsx
│   ├── CockpitRegistry.ts
│   ├── store/
│   │   ├── useCockpitLayoutStore.ts    # zustand + persist (key: ma150.cockpit.layouts.v1)
│   │   └── useCockpitStore.ts          # zustand 运行时（selectedTicker / mas / timeframe）
│   ├── components/
│   │   ├── RegimePill.tsx
│   │   ├── SetupTypeBadge.tsx
│   │   ├── SetupQualityBadge.tsx
│   │   ├── EarningsRiskDot.tsx
│   │   └── ChartHorizontalLine.tsx
│   ├── widgets/
│   │   ├── MarketRegimeWidget.tsx
│   │   ├── EarningsWidget.tsx
│   │   ├── PoolBuilderWidget.tsx
│   │   ├── CockpitChartWidget.tsx
│   │   ├── SetupMonitorWidget.tsx
│   │   ├── DecisionPanelWidget.tsx
│   │   ├── PositionListWidget.tsx
│   │   ├── PendingOrdersWidget.tsx
│   │   └── ActionListWidget.tsx
│   ├── dialogs/
│   │   ├── UserSettingsDialog.tsx
│   │   ├── PositionFormDialog.tsx
│   │   ├── PendingOrderFormDialog.tsx
│   │   └── SaveAsPendingOrderConfirm.tsx
│   └── lib/
│       └── api/                   # cockpit 专属 API 客户端 + 类型定义
│           ├── regime.ts
│           ├── setup-monitor.ts
│           ├── chart.ts
│           ├── decision.ts
│           ├── earnings.ts
│           ├── pool.ts
│           ├── positions.ts
│           ├── pending-orders.ts
│           ├── actions.ts
│           ├── user-settings.ts
│           └── ai.ts              # POST /api/ai/{task_type} 通用 client
```

---

## §Cockpit-6：边界红线（追加）

开发 Cockpit 时发现以下需求，**先回到 design-bridge** 更新文档：

1. `src/cockpit/*` import `src/workbench/*`（ESLint `no-restricted-imports` 强制）
2. CockpitChartWidget 复用 Workbench `ChartWidget`（D063 禁止）
3. cockpit widget 直接调 LiteLLM 而不走 `POST /api/ai/{task_type}`（D064 / D068 / D069 禁止）
4. 在 CockpitRegistry 之外手写 widget 实例（必须经 manifest 才能纳入 RGL）
5. 修改 `localStorage` key `ma150.cockpit.layouts.v1`（破坏既有用户布局；如必须升级 schema，按 layouts 末位 version 字段递增并提供 reset）
6. 在 cockpit widget 内引用 `useAppStore`（Workbench store）— 全部 cockpit 状态走 `useCockpitStore` / `useCockpitLayoutStore`
7. 在 cockpit widget 内硬编码 hex 颜色（必须用 `--color-regime-* / --color-setup-* / --color-earnings-* / --color-action-*-bg / --color-chart-*` 等 token）

---

## §Cockpit-7：v1.8 / v1.9 / v2.0 渐进式实施清单

| 阶段 | 必须落地 | 暂不实现 |
|---|---|---|
| v1.8 P0（F200/F201/F202/F203/F204） | CockpitPage / CockpitRegistry / 两个 store / RegimePill / SetupTypeBadge / SetupQualityBadge / EarningsRiskDot / ChartHorizontalLine / MarketRegimeWidget / EarningsWidget / CockpitChartWidget / SetupMonitorWidget / DecisionPanelWidget / UserSettingsDialog | PoolBuilder / Position / PendingOrders / ActionList / 全部 AI 子区 |
| v1.9 P1（F205/F206/F207） | PoolBuilderWidget / PositionListWidget / PendingOrdersWidget / ActionListWidget / PositionFormDialog / PendingOrderFormDialog / SaveAsPendingOrderConfirm | AI 子区仍延后 |
| v2.0 AI（F208/F209/F210/F211） | `lib/api/ai.ts` 客户端封装 / 各 widget 内的 AI 子区域（不新增 widget） | — |

---

## F222 · Watchlist 颜色标记（2026-07-02 system-design 追加，跳过 design-bridge）

> 范围仅本 feature 新增的两个小组件，挂载于既有 `WatchlistWidget`（`src/workbench/widgets/`）表格行内；`WatchlistWidget` 自身完整组件边界不在本次范围内。

### ColorTagButton
- Props：`ticker: string`、`color: 'red' | 'yellow' | 'blue' | null`、`onChange: (color: 'red' | 'yellow' | 'blue' | null) => void`
- 职责：渲染圆形色块按钮（`red`/`yellow`/`blue` 实心圆，`null` 为空心圆环）；点击打开 `ColorTagPopover`
- 位置：`WatchlistWidget` 表格每行，ticker 文字左侧
- 不包含：持久化请求本身（由父组件 mutation 调用 `PUT /api/watchlist/{ticker}/color`，成功后更新本地/react-query 缓存）

### ColorTagPopover
- 基于 shadcn `Popover`，内容为 4 个色块（红/黄/蓝/无色）横排，单选态
- Props：`value: 'red' | 'yellow' | 'blue' | null`、`onSelect: (color: 'red' | 'yellow' | 'blue' | null) => void`
- 职责：展示 4 个可点击色块，当前值描边高亮；点击任一色块后立即调用 `onSelect` 并关闭 Popover（open state 由 shadcn `Popover` 自身管理，不额外加 state）
- 必须：使用 `--color-label-*` token（见 design-spec.md），不直接写 hex；`null` 态用 border-only 渲染，不填充
