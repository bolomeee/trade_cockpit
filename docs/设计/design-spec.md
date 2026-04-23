# design-spec.md

> 最后更新：2026-04-18（v1.1.0 Workbench 重构 Phase 0）
> ⚠️ 本文档是开发时视觉 & 交互规格的权威来源。Token 用法见 `tokens.json` / `src/styles/tokens.css`。字段名见 `data-mapping.md`（API-CONTRACT.md 为权威）。
> Figma 文件清单见 `figma-links.md`。

---

## v1.1 · Workbench（当前主视觉）

v1.0.0 的 Dashboard / Journal / Logs 三页合并为单页 Workbench，widget 化渲染。下方"页面 1/2/3"章节仍为各 widget 内部的视觉契约（**作为 widget 内部规格继续生效**），但页面级别的"路由切换 / TopNav 高亮"不再适用。

### 全局结构

```
┌─ TopNav（64px，保留）──────────────────────────┐
│  MA150 Tracker · Last refresh · Refresh Data  │
├─ MarketOverview 条（41px，可选 widget 化）─────┤
├─ Workbench 网格（剩余高度） ───────────────────┤
│                                                │
│   [widget A] [widget B] [widget C]             │
│   [widget D]            [widget E]             │
│                                                │
│  右下：重置布局按钮                             │
└────────────────────────────────────────────────┘
```

### Workbench 网格规格

- **引擎**：react-grid-layout
- **列数**：12（桌面），手机断点降为 4 列（见"响应式"）
- **行高（rowHeight）**：40 px
- **容器 padding**：`[16, 16]`；widget 间 margin：`[12, 12]`
- **背景**：`--color-background`（白）
- **拖拽 handle**：widget 的 WidgetShell 标题栏（整栏可拖），光标 `grab` → `grabbing`
- **resize handle**：widget 右下角（react-grid-layout 默认），12×12px，`--color-border` 淡色三角

### WidgetShell 标准外壳

所有 widget 必须通过 WidgetShell 包装：

```
┌─ Shell（--radius-card 圆角 + --shadow-card）──┐
│ ┌─ 标题栏（36px，拖拽 handle）─────────────┐ │
│ │ Widget 标题（14px semibold）             │ │
│ │                          [⋯ 可选菜单]    │ │
│ └──────────────────────────────────────────┘ │
│ ┌─ 内容区（overflow-auto）─────────────────┐ │
│ │ 具体 widget 内容（即 v1.0.0 的业务组件） │ │
│ └──────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

- 标题栏背景 `#ebf2fa`（v1.1.0 起强制；覆盖早期 `--color-surface-muted` 规格），下分隔线 `--color-border`
- 内容区 padding `16 px`；溢出 overflow-auto（widget 被缩窄时出滚动条，不溢出 Shell）
- Shell 背景 `--color-surface`（白或浅灰），hover 时 `--shadow-card-hover`

#### Widget 内部垂直间距规范（v1.1.0 起强制）

所有 widget 的内容根元素必须遵守：

- **顶部贴边偏移**：根元素 `marginTop: -5px; marginLeft: -5px`（让最上面的组件更靠近 Shell 内容区的上左边缘）
- **组件之间的垂直 gap**：`gap-1`（4px，Tailwind）或 `var(--spacing-1)`（4px）
- 适用于所有含多个堆叠子组件的 widget（tabs + 表格、搜索框 + 表格、表单多字段等）
- 单一内容 widget（如 ChartWidget 的唯一 canvas）可豁免，但若内部有绝对定位叠层 label，label 的 top/left 不再比照此规范
- 新增 widget 时必须照此配置；任何偏离需在 DECISIONS.md 留记录

### 默认布局（首次访问）

| Widget | x | y | w | h |
|--------|---|---|---|---|
| WatchlistWidget | 0 | 0 | 4 | 8 |
| ChartWidget | 4 | 0 | 5 | 6 |
| FundamentalsWidget | 9 | 0 | 3 | 4 |
| PullbackWidget | 9 | 4 | 3 | 4 |
| JournalWidget | 4 | 6 | 5 | 4 |
| LogsWidget | 0 | 8 | 4 | 3 |
| QuickAddWidget | 9 | 8 | 3 | 3 |

> 具体默认布局在 Phase 1/2 实现时可微调；最终以 `WidgetRegistry.ts.defaultLayout` 为准。

### 响应式

- **≥ 1024 px**：12 列完整布局
- **< 1024 px**：react-grid-layout 响应式降为 4 列单列堆叠，widget 按 y 顺序纵向排列
- **widget 内部**：继承 v1.0.0 响应式规则（见下方各 widget 章节）

### AddStockCard 搜索框样式（v1.3 起）

WatchlistWidget 顶部的 ticker 搜索框（`AddStockCard`）从 v1.3 起采用 pill 样式：

- 外形：`rounded-full`（全圆角胶囊形）
- 字号：`10px`（`text-[10px]`）；字重：bold；placeholder 同等字重
- 其余行为（Popover 展开 / 添加逻辑）不变

### Widget 紧凑表通用规格（v1.1，适用 WatchlistWidget / MarketBreakoutWidget 等表格型 widget）

所有"列表型" widget 的表格遵守同一套紧凑表规格，以最大化密度、保持跨 widget 一致性：

- **字号**：`11px`（表头与单元格统一，`text-[11px]` 覆盖 shadcn Table 默认的 `text-sm`）
- **行高**：
  - 表头：`h-5 py-1 px-2`（高度 20px，左右内边距 8px）
  - 单元格：`py-[3px] px-2`（垂直内边距 3px）
- **对齐**：表头与单元格**全部左对齐**（去除 `text-right`，数字列也左对齐以统一视觉节奏）
- **列宽**：
  - Ticker 列固定 `w-14`（56px，容纳 4 字符 bold 代码），确保 Ticker↔Company 列起点在同 widget 多次渲染、跨不同 widget 间保持一致
  - 删除/操作列固定 `w-6`（24px）
  - 其余列自适应
- **字段命名**：列头文案以业务术语为准（公司 → `Company`，而非数据字段名 `name`）。跨 widget 同语义的列（公司名、收盘价、距 MA150 百分比）**必须使用同一列头文案**。
- **数值格式**：货币 `$X.XX`、百分比 `+X.X%`、Vol 比 `X.XX×`，字体使用 `var(--font-family-numeric)` (Helvetica/Arial)，颜色按正负取 `--color-change-positive` / `--color-change-negative`
- **表头吸顶（sticky header，v1.1.1+）**：所有列表型 widget 的表头在内容超出可视区时必须保持吸顶可见。
  - 实现：`<Table>` 外层包 `<div className="flex-1 overflow-y-auto">`（或等价的 h-full overflow-y-auto），`<TableHeader>` 加 `sticky top-0 z-10 bg-card`
  - ⚠️ 陷阱：shadcn `Table` 内部 wrapper 的 `overflow-x-auto` 会被 CSS 规范强制把 `overflow-y` 也计算为 `auto`，从而成为 sticky 的滚动容器并使吸顶失效。已在 `components/ui/table.tsx` 去掉该 class；新增表格型 widget 时如需横向滚动，在外层自行包 `overflow-x-auto`，**不要**改回 Table 内部

> 设计基准：2026-04-22 F-UI 紧凑化 Sprint 确定。早期设计稿中的 Table 默认规格（`text-sm` / `h-10` / 部分列右对齐）在 widget 场景下密度过低，不再适用。sticky 表头于 2026-04-23 补入。

### Widget 内部视觉规格

下方"页面 1 / 1a / 2 / 2a / 3"章节描述各 widget **内容区**的视觉与交互规格（不含顶栏 / MarketOverview）。Dashboard 页面级的布局编排不再适用，改为 Workbench 网格统一管理。

---

## 页面清单（v1.0 · 作为 widget 内部规格参考）

| # | 页面 | 路由 | Figma 链接 | 关联 Feature |
|---|------|------|-----------|-------------|
| 1 | Dashboard | `/` | [stock_portal#0-1](https://www.figma.com/design/Wk5znwTAjGZXPeDDKLtVSb/stock_portal?node-id=0-1) | F001, F002, F003, F004, F006 |
| 1a | StockDetailModal（Dashboard 弹窗） | `/`（Modal，无独立路由） | [stock_portal#7-472](https://www.figma.com/design/Wk5znwTAjGZXPeDDKLtVSb/stock_portal?node-id=7-472) | F005 |
| 2 | Trade Journal | `/journal` | [trade_journal#0-1](https://www.figma.com/design/uoZCLcuEglJh87mfP15C9o/trade_journal?node-id=0-1) | F007 |
| 2a | New Trade Entry Dialog | `/journal`（Modal） | [trade_journal#1-382](https://www.figma.com/design/uoZCLcuEglJh87mfP15C9o/trade_journal?node-id=1-382) | F007 |
| 3 | System Logs | `/logs` | [system_logs#0-1](https://www.figma.com/design/ReibtcedQZ2Zynr5goIUGG/system_logs?node-id=0-1) | F008 |

---

## 全局布局

**画布宽度（设计稿）**：1101 px（移动端断点见"响应式"章节）。
**页面高度结构**：顶栏 64 px → MarketOverview 41 px → 页面主体。
**全局背景**：`--color-background`（白）。
**卡片阴影**：`--shadow-card`。

### 顶栏 TopNav（所有页面共享）
- 高度：64 px。背景：白 + 下分隔线 `--color-border`。
- 左：
  - "MA150 Tracker"（`--font-size-title` bold；**v1.3 起为 NavLink**，点击回 `/`，无下划线，颜色不变，指针变 pointer）
  - 导航链接：Dashboard / Journal / Logs
    - 当前路由激活：文字 `--color-nav-active`（黑）
    - 非激活：`--color-nav-inactive`（灰），hover → `--color-nav-hover`
- 右（v1.3 起）：
  - `dynamic_last_refreshed:` "Last refresh: HH:MM:SS AM"（`--color-text-secondary`，12px/16px）
  - Refresh Data 按钮（F003 触发 `POST /api/data/refresh`）
    - 默认：白底 + 边框 + 刷新图标 + 文字
    - 圆角 `--radius-button`（full pill），高度 32 px
    - 加载中：图标旋转 + 文字保持 "Refresh Data"（禁用交互）
  - ResetLayoutButton（**v1.3 起从 MarketOverviewBar 移到此处**，紧邻 RefreshButton 右侧，**仅在首页 `/` 可见**；其他路由隐藏）

### MarketOverview 条（所有页面共享）
- 高度：41.78 px，居中显示三个指标。
- 三组容器：S&P 500 / NASDAQ 100 / 10Y Treasury
  - `dynamic:` 指标名（常量文案）+ `dynamic_close:` 数值 + `dynamic_change_pct:` 涨跌幅
  - 涨跌幅颜色：正用 `--color-change-positive`，负用 `--color-change-negative`
  - 字号：`--font-size-market-bar`（14.4px）
- 背景：白，下分隔线 `--color-border`。

---

## 页面 1：Dashboard（`/`）

Figma：[stock_portal → frame "Dashboard" (5:4)](https://www.figma.com/design/Wk5znwTAjGZXPeDDKLtVSb/stock_portal?node-id=5-4)
关联 Feature：F001 / F002 / F003 / F004 / F006

### 组件层级

```
Dashboard (/)
├── TopNav（共享）
├── MarketOverviewBar（共享，dynamic_spx / dynamic_ndx / dynamic_tnx）
└── Main (padding 32 × 24, max-width 1053px, marginInline auto, alignItems flex-start)
    │  说明：两列整体水平居中；Sidebar 顶部放置一个与 Left 列 Heading2 等高的不可见占位元素，
    │  使 AddStock 卡片顶边与首行 SignalCard 顶边对齐（而非与 "SignalBoard" 标题文字对齐）。
    ├── Left (flex-1, max-width 871px)
    │   ├── Heading2 "SignalBoard"（静态）
    │   └── SignalBoard (grid, 3–4 cols × N rows, gap 16)
    │       └── SignalCard × N  [dynamic_stocks[]]
    │           ├── Ticker (bold, font-size-subtitle)     [dynamic_stock.ticker]
    │           ├── Company name (font-size-body, text-secondary)  [dynamic_stock.name]
    │           ├── Price (font-size-hero, numeric font)  [dynamic_stock.latestSignal.closePrice]
    │           ├── Distance badge "+X.X%MA150"           [dynamic_stock.latestSignal.distancePct]
    │           └── Signal Badge ("BUY ZONE" / "BREAKOUT" / "NEUTRAL" / "INSUFFICIENT")
    │                                                      [dynamic_stock.latestSignal.signalType]
    └── Sidebar (width 158px, fixed右)
        ├── Card "Add Stock"（F001）
        │   ├── Input (placeholder "e.g. AAPL")           [dynamic_ticker_input]
        │   └── Button "Add to Watchlist"（调用 POST /api/watchlist）
        └── Card "Trade Journal" Widget（F007 的快捷入口）
            ├── Input "Ticker (e.g. AAPL)"                [journal_draft.ticker]
            ├── Dropdown (Action, 值 BUY/SELL/ADD/REDUCE/WATCH)  [journal_draft.action]
            ├── Input "Price"                             [journal_draft.price]
            └── Button "+ Add Entry"（调用 POST /api/journal）
```

### SignalCard 样式细节

- 尺寸：~280 × 122 px（桌面），内边距 `--spacing-card-padding-sm` (16px)
- 圆角：`--radius-card` (10px)，阴影 `--shadow-card`，hover → `--shadow-hover-card`
- 背景：`--color-card`
- Signal Badge：
  - 圆角 full，右上对齐
  - 颜色映射：
    - `BREAKOUT` → 背景 `--color-signal-breakout`，文字白
    - `BUY_ZONE` → 背景 `--color-signal-buyzone`，文字白
    - `NEUTRAL` → 背景 `--color-signal-neutral`，文字白
    - `INSUFFICIENT` → 背景 `--color-signal-insufficient`，文字 `--color-text-primary`（灰底需深色文字保证对比度）
    - Badge 文字：`BUY_ZONE` 显示为 "BUY ZONE"；其他 TitleCase 或按 Figma 原样
- Distance 文字：若价距 ≥ 0 用 `--color-change-positive`，< 0 用 `--color-change-negative`（目前 Figma 仅画了 BUY_ZONE 情况）

### 交互

- **点击 SignalCard** → 打开 StockDetailModal（页面 1a），传入 `ticker`。不改变 URL（可用 URL query `?symbol=TICKER` 作为可选深链，取决于实现侧决定）
- **点击 "Refresh Data"** → 触发 `POST /api/data/refresh`；期间按钮进入 loading 态，完成后更新 `dynamic_last_refreshed`
- **点击 Add Stock "Add to Watchlist"**：
  - 如果输入为空：按钮禁用
  - 调用 `GET /api/stocks/search?q=TICKER` → 结果唯一则直接 `POST /api/watchlist`；否则展示搜索结果下拉（`GET /api/stocks/search` 返回数组，UI 沿用同一 Card 扩展）
  - 搜索无匹配：Alert 提示 "未找到匹配的股票"

> ⚠️ 实现偏离（2026-04-17，F001-c 开发期间）
> 原始设计：输入框后有 "Add to Watchlist" 按钮；结果唯一直接 POST，多个则下拉选择。
> 实际实现：
>   - 取消独立按钮，改为 Input + Enter 键触发搜索。
>   - 全部走 Popover 下拉选择（包括唯一结果），不做"唯一结果自动 POST"分支。
>   - 搜索无结果时在 Popover 内显示文案，不再弹出独立 Alert。
>   - SignalCard 增加 hover 显示的 Trash2 删除按钮 + AlertDialog 二次确认（design-spec 未画，MVP 补全）。
> 原因：
>   1. Enter 触发减少 Polygon API 调用次数（付费 rate-limited）。
>   2. 交互一致性优先，避免"同一 ticker 两次查询得到不同行为"。
>   3. 二次确认防误删，Sidebar 窄，没空间展示独立"确认删除"UI。
> 决策：D019 / D020（DECISIONS.md）
- **点击 Trade Journal "+ Add Entry"**：
  - 必填校验 Ticker + Action + Price；成功调用 `POST /api/journal`；成功后清空表单，不弹 toast（MVP 简化）
  - ⚠️ Dashboard Widget 是"快捷表单"，仅含 ticker/action/price。完整字段（止损/目标/原因/参考）需要跳去 `/journal` 的 New Entry Dialog 录入

### 四种状态

| 状态 | 设计稿 | 说明 |
|------|-------|------|
| 正常 | ✅ [stock_portal#5-4](https://www.figma.com/design/Wk5znwTAjGZXPeDDKLtVSb/stock_portal?node-id=5-4) | Figma 展示 MSFT 4 个示例 Card |
| 空 | ❌ 尚无设计稿 | watchlist 为空时：SignalBoard 区域显示 EmptyState："还没有自选股，从右侧 Add Stock 开始吧"，文字 `--color-text-secondary`，高度占 SignalCard grid 的一行 |
| 加载 | ❌ 尚无设计稿 | 首屏 `GET /api/watchlist` 加载中：SignalCard 位置显示 4 个 Skeleton（宽高同卡片，浅灰 `--color-muted` 背景 + 浅脉冲动画） |
| 错误 | ❌ 尚无设计稿 | `GET /api/watchlist` 失败：区域显示 "数据加载失败，[重试]"，文字 `--color-error`，Inline 按钮重新调用接口 |

> ⚠️ 实现偏离（2026-04-22，F-UI 紧凑化 Sprint）
> 原始设计：SignalBoard = SignalCard 卡片网格（~280×122px，3–4 列 × N 行）。
> 实际实现（WatchlistWidget）：
>   - 改为紧凑 Table 列表，列序为 `Ticker / Company / Signal / Close / % MA150 / [删除]`
>   - 列头 `Company`（非 `Name`），遵循 v1.1 紧凑表通用规格（见前文）
>   - `Signal` 列仍保留 SignalBadge 胶囊呈现（BREAKOUT / BUY_ZONE / NEUTRAL / INSUFFICIENT）
>   - `% MA150` 等同原 `Distance`，正负取 `--color-change-positive` / `--color-change-negative`
>   - 顶部保留搜索栏（AddStockCard 的 Popover 搜索加入），取代 Sidebar 的 "Add Stock" 卡片
> 原因：Workbench 网格下，卡片布局密度过低、一个 widget 塞不下多只股票；列表形式更适配"可拖拽 widget + 多 widget 共存"的 v1.1 工作台范式。
> 默认 `h` 从 8 调大至 14（WidgetRegistry.ts），以减少滚动条出现概率。

---

## 页面 1a：StockDetailModal（Dashboard 弹窗，F005）

Figma：[stock_portal → frame "StockDetailModal" (7:472)](https://www.figma.com/design/Wk5znwTAjGZXPeDDKLtVSb/stock_portal?node-id=7-472)

### 组件层级

```
StockDetailModal (1024 × 804 px，居中)
├── Backdrop（full-screen，背景 --color-overlay-backdrop）
├── Dialog（圆角 --radius-modal，阴影 --shadow-modal，背景 --color-card）
│   ├── HeaderSection (高 100 px)
│   │   ├── Left（Ticker + Signal Badge + 公司名）
│   │   │   ├── Heading1 "META" (font-size-hero + bold)    [dynamic_stock.ticker]
│   │   │   ├── Signal Badge                                [dynamic_stock.latestSignal.signalType]
│   │   │   └── Paragraph "Meta Platforms"                 [dynamic_stock.name]
│   │   └── Right（4 列指标）
│   │       ├── "Close Price" / "$485.58"     [dynamic_latestSignal.closePrice]
│   │       ├── "MA150" / "$400.50"           [dynamic_latestSignal.ma150Value]
│   │       ├── "Distance" / "+21.2%"         [dynamic_latestSignal.distancePct]
│   │       └── "Slope" / [icon↑↓] "UP"/"DOWN" [dynamic_latestSignal.slopePositive]
│   ├── PriceChart Card (976 × 302 px)
│   │   └── 图表：Candlestick + MA150 line (蓝 #2962ff，= --color-signal-breakout)
│   │       ├── 回踩标记（Pullback markers）：在 Pullback.date 位置加 arrowUp 标记（buyzone 色）
│   │       ├── X 轴：最近约 150 日交易日 (YYYY-MM-DD)     [dynamic_chart[].date]
│   │       ├── Y 轴：价格 $              [dynamic_chart[].close]
│   │       └── Hover tooltip：日期 + 收盘价（Figma 已预留 TooltipBoundingBox）
│   │
│   │   > **F107 增强（v1.3 起，同时生效于 Workbench ChartWidget 和 Dashboard 详情弹窗）**：
│   │   > - **短均线叠加**：MA5（`#f59e0b` 橙）/ MA20（`#8b5cf6` 紫），lineWidth 1；前 N-1 天跳过不画点（无左端突刺）
│   │   > - **短均线颜色约定**：`#f59e0b / #8b5cf6` 为硬编码值、不走 token — 遵循 TradingView 社区短期均线配色惯例（MA5 暖色、MA20 冷色、辨识度高），非项目 token 色板覆盖范围；理由记录在此，无需单列 DECISIONS 条目
│   │   > - **成交量 Histogram**：底部独立 priceScale（`priceScaleId: 'volume'`，scaleMargins `top: 0.8 / bottom: 0`）占图表底部 20% 区域
│   │   > - **成交量颜色**：涨日 `upColor + '66'`（~40% 透明的 --color-change-positive），跌日 `downColor + '66'`（~40% 透明的 --color-change-negative）
│   │   > - **主图下移**：Candlestick priceScale `scaleMargins: { top: 0.05, bottom: 0.25 }`，为 volume 区腾出底部 20%
│   │   > - **均线图例**（仅在 Workbench ChartWidget 的左上角 absolute 图例区显示，Dashboard 详情弹窗无）：
│   │   >   - `— MA5` / `— MA20` / `— MA150` 三行，fontSize 11，font-family `--font-family-numeric`
│   │   >   - 颜色与线条一致：MA5 橙、MA20 紫、MA150 `var(--color-signal-breakout, #2962ff)`
│   └── BottomRow (976 × 314 px, split 644 + 312)
│       ├── Card "Pullback History" (644 × 314)
│       │   └── Table: Date / Distance / 10D / 20D / 30D   [dynamic_pullbacks[]]
│       │       - Distance 值：负数用 --color-change-negative
│       │       - 10D/20D/30D：正用 positive 色，负用 negative 色，null 显示 "—"
│       └── Card "Fundamentals" (312 × 314)
│           ├── CardHeader："Fundamentals" + Badge "Mock Data"（当前为占位）
│           └── 2×2 Grid: P/E Ratio / P/S Ratio / PEG Ratio / Free Cash Flow
│                                                           [dynamic_fundamentals.*]
└── CloseButton (X, 右上 16px 偏移，32 × 32)
```

### 交互

- 打开：点击 SignalCard，传入 ticker；拉取并发 4 接口（见 data-mapping.md）
- 关闭：点 Backdrop / X 按钮 / ESC 键
- URL：不改变（MVP 为纯前端弹窗；如未来需要深链，再追加 query param）
- Chart hover：显示 tooltip；Chart 基于 `lightweight-charts` 实现（详见 ARCHITECTURE.md）

### 四种状态

| 状态 | 设计稿 | 说明 |
|------|-------|------|
| 正常 | ✅ [stock_portal#7-472](https://www.figma.com/design/Wk5znwTAjGZXPeDDKLtVSb/stock_portal?node-id=7-472) | META BUY_ZONE 示例，图表有回踩 |
| 空（数据不足） | ❌ 尚无设计稿 | `signalType = INSUFFICIENT`：Badge 显示 "INSUFFICIENT"（灰底深色文字）；Chart 仍展示已有日线；Distance / MA150 / Slope 显示 "—"；Pullback History 显示空表体 "No pullbacks yet" |
| 加载 | ❌ 尚无设计稿 | 4 个接口同时加载：HeaderSection 4 个指标用文本 Skeleton；Chart 区域 Skeleton（高 260）；两个 Card 内容 Skeleton |
| 错误 | ❌ 尚无设计稿 | 任一接口失败：内容区域替换为 "加载 [X] 失败，[重试]"，错误文字 `--color-error`；非致命接口（Fundamentals Mock）失败不阻塞其他部分 |

---

## 页面 2：Trade Journal（`/journal`）

Figma：[trade_journal#0-1](https://www.figma.com/design/uoZCLcuEglJh87mfP15C9o/trade_journal?node-id=0-1)
关联 Feature：F007

### 组件层级

```
/journal
├── TopNav（共享）
├── MarketOverviewBar（共享）
└── Main (padding 32 × 38.5)
    ├── HeaderRow
    │   ├── Heading1 "Trade Journal"（静态）
    │   └── Button "+ New Entry" → 打开 New Trade Entry Dialog（页面 2a）
    ├── FilterCard (padding 17)
    │   ├── Select "Ticker"（下拉 = 去重后的 ticker 列表）   [filter.ticker]
    │   ├── Select "Action"（下拉 = BUY/SELL/ADD/REDUCE/WATCH + "All"） [filter.action]
    │   └── Button "Clear Filters"
    │   > ⚠️ 实现偏离（2026-04-17，F007-b 开发期间）
    │   > 原始设计：两个 Select 使用 shadcn Select 组件
    │   > 实际实现：降级为原生 `<select>`，样式用 tokens 对齐（padding / border-radius / font-size）
    │   > 原因：本 Sprint 6 文件上限，不引入 shadcn select.tsx；F007-c 引入 Dialog 时统一接入 shadcn Select 再替换
    └── TableCard
        └── JournalTable
            ├── Header: Date / Ticker / Action / Price / Position / Actions
            └── TableBody
                └── JournalRow × N  [dynamic_entries[]]
                    ├── ExpandButton (chevron icon, 24×24) — 展开显示 reason & reference
                    ├── Date                          [entry.date]
                    ├── Ticker (bold)                 [entry.stock.ticker]
                    ├── Action Badge                  [entry.action]
                    ├── Price (右对齐)                [entry.price]
                    ├── Position (shares, 右对齐；"—" when null) [entry.positionSize]
                    └── Actions: Edit icon + Delete icon
```

### Action Badge 样式

| action | 显示文案 | 背景颜色 token |
|--------|---------|--------------|
| BUY | BUY | `--color-action-buy` |
| SELL | SELL | `--color-action-sell` |
| ADD | ADD | `--color-action-add` |
| REDUCE | REDUCE | `--color-action-reduce` |
| WATCH | WATCH | `--color-action-watch` |

Badge 圆角 `--radius-badge`（full）；文字白色，`--font-size-caption` (12px)。

### 交互

- **+ New Entry**：打开 New Trade Entry Dialog（页面 2a），成功保存后刷新 `GET /api/journal`
- **Expand chevron**：展开行显示 `reason` / `reference` / `stopLoss` / `targetPrice` 详情
- **Edit icon**：打开 Dialog（同 New Entry Dialog，标题 "Edit Trade Entry"），预填当前行内容，提交调用 `PUT /api/journal/:id`
- **Delete icon**：二次确认（用系统原生 `confirm` 或 shadcn AlertDialog），调用 `DELETE /api/journal/:id`
- **Filter 变更**：前端过滤（数据已全部拉取）；Clear Filters 重置两个 Select
- **默认排序**：`date` 倒序（最近的在上）

### 四种状态

| 状态 | 设计稿 | 说明 |
|------|-------|------|
| 正常 | ✅ [trade_journal#1-2](https://www.figma.com/design/uoZCLcuEglJh87mfP15C9o/trade_journal?node-id=1-2) | 3 行 NVDA / META / TSLA 示例 |
| 空 | ❌ 尚无设计稿 | `entries` 为空：Table 区域显示 EmptyState："还没有交易记录，点右上角 + New Entry 开始记录"，左右居中 |
| 加载 | ❌ 尚无设计稿 | Table Card 内显示 5 行 Skeleton（高度同数据行 64 px） |
| 错误 | ❌ 尚无设计稿 | `GET /api/journal` 失败：替换 Table 区为 "加载失败，[重试]"（`--color-error`） |

---

## 页面 2a：New Trade Entry Dialog（`/journal` 弹窗）

Figma：[trade_journal#1-382](https://www.figma.com/design/uoZCLcuEglJh87mfP15C9o/trade_journal?node-id=1-382)

### 组件层级

```
Dialog (446 × 643 px，居中，背景 --color-card, 圆角 --radius-modal)
├── DialogHeader (padding 24)
│   ├── Title "New Trade Entry" (font-size-subtitle, bold)
│   ├── Description "Record your trading decisions and notes."
│   └── CloseButton (X, 右上)
├── FormBody (padding 24, 字段行距 20)
│   ├── Row1: Ticker * (187px) | Date * (187px)
│   ├── Row2: Action * (Select) | Price ($) *
│   ├── Row3: Position (Shares) | Stop Loss | Target (3 等宽 119px)
│   ├── Row4: Short Reason (full width input, placeholder "e.g. Bounce off 150MA")
│   └── Row5: Reference / Notes (Textarea, 390 × 98, placeholder "Detailed thesis, earnings dates, or market context...")
└── Footer (padding 17，右对齐)
    ├── Button "Cancel"（ghost/outline）
    └── Button "Save Entry"（primary，黑底白字）
```

### 字段规则

| 字段 | 必填 | 类型 | 映射 |
|------|------|------|------|
| Ticker | ✅ | 输入框，提交时校验是否在 watchlist 中，不在则 Alert | `entry.stock.ticker` |
| Date | ✅ | 日期选择器（shadcn DatePicker） | `entry.date` |
| Action | ✅ | Select，5 枚举 | `entry.action` |
| Price | ✅ | 数字输入，> 0 | `entry.price` |
| Position (Shares) | ❌ | 数字输入，≥ 0；Action=WATCH 时禁用/忽略 | `entry.positionSize` |
| Stop Loss | ❌ | 数字输入 | `entry.stopLoss` |
| Target | ❌ | 数字输入 | `entry.targetPrice` |
| Short Reason | ❌ | 单行文本 | `entry.reason` |
| Reference / Notes | ❌ | 多行文本（Textarea） | `entry.reference` |

### 交互

- 打开：点击 "+ New Entry" 或行 Edit
- 提交：`POST /api/journal`（新增）/ `PUT /api/journal/:id`（编辑）
- 必填校验：`VALIDATION_ERROR` 在对应字段下方显示红字（`--color-error`）
- 成功：关闭 Dialog + 刷新 Table
- 失败：Dialog 底部显示统一错误提示（`--color-error`）

### 四种状态

| 状态 | 设计稿 | 说明 |
|------|-------|------|
| 正常（New） | ✅ [trade_journal#1-382](https://www.figma.com/design/uoZCLcuEglJh87mfP15C9o/trade_journal?node-id=1-382) | — |
| 正常（Edit） | ❌ 尚无设计稿 | 复用 New 布局，Title 改为 "Edit Trade Entry"；字段预填 |
| 提交中 | ❌ 尚无设计稿 | "Save Entry" 按钮显示 spinner + 禁用；其他字段禁用 |
| 错误 | ❌ 尚无设计稿 | 字段级错误：输入框红边 + 下方红字。表单级错误：Footer 上方红字提示 |

---

## 页面 3：System Logs（`/logs`）

Figma：[system_logs#1-2](https://www.figma.com/design/ReibtcedQZ2Zynr5goIUGG/system_logs?node-id=1-2)
关联 Feature：F008

### 组件层级

```
/logs
├── TopNav（共享）
├── MarketOverviewBar（共享）
└── Main (padding 32 × 24)
    ├── HeaderRow
    │   ├── Heading2 "System Logs"
    │   └── LogLevelFilter (5 chip toggle group)
    │       ├── "ALL"（默认选中，黑底白字）
    │       ├── "OK"
    │       ├── "INFO"
    │       ├── "WARN"
    │       └── "ERROR"
    └── TableCard
        └── LogsTable
            ├── Header: Timestamp / Level / Source / Message
            └── TableBody
                └── LogRow × N  [dynamic_logs[]]
                    ├── Timestamp (mono font, --font-family-mono)  [log.createdAt]
                    ├── Level Badge                                 [log.level]
                    ├── Source                                      [log.source]
                    └── Message (单行省略，长文本 tooltip)          [log.message]
```

### Level Badge 样式

| level | 显示文案 | 背景颜色 token |
|-------|---------|--------------|
| OK | OK | `--color-log-ok` |
| INFO | INFO | `--color-log-info` |
| WARN | WARN | `--color-log-warn` + 白底 + 边框（Figma 为 outline 样式）|
| ERROR | ERROR | `--color-log-error` |

Badge 圆角 full；OK/INFO/ERROR 为 solid 彩底白字，WARN 为 outline 风格（白底 + amber 边框与文字）。

### 交互

- **LogLevelFilter**：点击切换当前过滤；"ALL" 显示全部，其他只显示对应级别
- **默认排序**：`createdAt` 倒序
- **Message 截断**：单行 `text-overflow: ellipsis`，hover 显示完整内容（tooltip）
- **点击 Log 行**：目前无二级查看（`detail` 字段在 DATA-MODEL 中预留，MVP 前端不展示，如开发时用户要求可改成 expand row 显示 `detail`）

### 四种状态

| 状态 | 设计稿 | 说明 |
|------|-------|------|
| 正常 | ✅ [system_logs#1-2](https://www.figma.com/design/ReibtcedQZ2Zynr5goIUGG/system_logs?node-id=1-2) | 多条 OK/INFO/WARN/ERROR 混合 |
| 空 | ❌ 尚无设计稿 | 当前 filter 无匹配：Table 下显示 "No logs match this filter"，文字 `--color-text-secondary` |
| 加载 | ❌ 尚无设计稿 | 5 行 Skeleton |
| 错误 | ❌ 尚无设计稿 | `GET /api/logs` 失败：替换 Table 为 "加载失败，[重试]"（`--color-error`）|

---

## 响应式断点

> ⚠️ Figma 只提供了桌面 1101 px 稿。移动端规则由 PRD 验收标准要求（F004/F005：移动端响应式）。

| 断点 | 宽度 | 规则 |
|------|------|------|
| Desktop | ≥ 1024 px | 同设计稿 |
| Tablet | 768–1023 px | SignalBoard 改为 2 列；/journal Table 保留所有列；/logs 保留所有列；StockDetailModal 宽度改 95vw，Chart 高度保持 |
| Mobile | < 768 px | SignalBoard 改为 1 列；Sidebar 折叠到 Dashboard 底部；StockDetailModal 改 full-screen sheet；/journal Table 水平滚动（或折叠为 Card 列表）；/logs Table 水平滚动；TopNav 导航变为 Drawer + 汉堡菜单；MarketOverview 水平滚动 |

Tailwind 默认断点采用 `md: 768px`, `lg: 1024px`（与 Tailwind 默认一致）。

---

## 动效 / 过渡

- 按钮 hover：`transition: background-color 150ms ease`
- Card hover：`transition: box-shadow 150ms ease`（从 `--shadow-card` → `--shadow-hover-card`）
- Modal 打开/关闭：背景 backdrop fade 200ms，Dialog scale 95% → 100% + fade 200ms（shadcn Dialog 默认）
- Refresh 按钮加载中：图标 `animation: spin 1s linear infinite`
- Skeleton 加载：pulse 动画 1.5s ease-in-out infinite（Tailwind `animate-pulse`）
- Signal Badge 状态变化（数据刷新后 signalType 改变）：不做过渡动画（避免视觉闪动误导交易判断）

---

## 图标

Figma 中使用的图标均为单色，推荐用 `lucide-react`：

| 使用位置 | lucide 图标名 |
|---------|-------------|
| Refresh Data | `RefreshCw` |
| Add to Watchlist (+) | `Plus` |
| WatchlistWidget CSV 导入 | `Upload` |
| WatchlistWidget CSV 导出 | `Download` |
| Trade Journal + Add Entry | `Plus` |
| Slope UP / DOWN | `TrendingUp` / `TrendingDown` |
| JournalTable Expand | `ChevronRight` |
| JournalTable Edit | `Pencil` |
| JournalTable Delete | `Trash2` |
| Dialog Close (X) | `X` |
| FilterCard Clear | `FilterX` |

---

## 字体规则总结

| 用途 | token |
|------|-------|
| 页面 H1（"Trade Journal" 32px / Ticker 36px） | `--font-size-hero` |
| 页面 H2（"SignalBoard" / "System Logs" 20px + bold） | `--font-size-title` |
| 卡片 Header / 指标数值（20–24px） | `--font-size-subtitle` / `--font-size-title` |
| 正文 / Table cell | `--font-size-body` (14px) |
| 辅助 / 元信息（Last refresh / Placeholder） | `--font-size-caption` (12px) |
| Badge | `--font-size-badge` (10px) |
| 价格 / 金额（等宽风格） | `--font-family-numeric` + `--font-size-subtitle` 以上 |
| 日志时间戳 | `--font-family-mono` |

---

## F110-b：WatchlistWidget CSV 导入/导出（2026-04-22）

### 触发入口

WatchlistWidget 顶部搜索栏行右侧两个 ghost icon 按钮（size="icon-sm"，14px 图标）：

```
[ Search ticker or name... ] [Upload↑] [Download↓]
```

- `Upload`（导入）：点击弹出 `CsvImportDialog`
- `Download`（导出）：直接触发浏览器下载；watchlist 为空时 disabled

### CsvImportDialog 规格

**组件**：`src/components/features/dashboard/CsvImportDialog.tsx`

**阶段状态机**：`input` → `importing` → `done` / `error`

**输入阶段**：
- Tabs 切换：「文件上传」/ 「文本粘贴」
- 文件上传：点击区域弹出文件选择框（`accept=".csv,.txt"`），选中后自动解析
- 文本粘贴：Textarea，实时解析（换行 / 逗号 / Tab 分隔，自动去重去首行标题）
- 解析预览：最多展示 8 个 ticker，超出显示"还有 N 个"；上限 200 个自动截断
- 「导入 (N)」按钮：解析 0 个时 disabled

**结果阶段**：
- ✅ 已添加：N 个（列出 ticker，最多 5 个）
- ⏭ 跳过（重复）：M 个
- ❌ 未找到：P 个
- 「完成」按钮关闭 Dialog

**错误阶段（502 EXTERNAL_API_ERROR）**：
- "导入失败（FMP 服务异常），请重试"
- 「返回」/ 「重试」按钮

### 导出格式

```csv
ticker,name
AAPL,"Apple Inc."
MSFT,"Microsoft Corporation"
```

文件名：`watchlist-YYYY-MM-DD.csv`

---

## 待确认项（开发侧可判断）

1. **Watchlist 搜索结果呈现**：Figma 的 Add Stock Card 仅显示 Input + Button，没画"搜索出多个候选"的 UI。MVP 建议用 `GET /api/stocks/search?q=` 即时结果显示在 Input 下方的浮层（shadcn Combobox）。
2. **SignalCard 上的 Distance 色彩**：Figma 示例只展示 BUY_ZONE 的正向，绝对值显示"+10.6MA150"格式。开发时按 distancePct 正负取色；INSUFFICIENT 情况下隐藏 Distance 文字。
3. **Pullback 标记在 K 线上**：Figma 图表未显式画出 Pullback 标记。开发时用 `lightweight-charts` 的 `createSeriesMarkers` 在 pullback.date 处加向下小三角（颜色 `--color-signal-buyzone`）。
