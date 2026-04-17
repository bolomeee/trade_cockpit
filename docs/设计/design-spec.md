# design-spec.md

> 最后更新：2026-04-17 | 维护者：design-bridge skill
> ⚠️ 本文档是开发时视觉 & 交互规格的权威来源。Token 用法见 `tokens.json` / `src/styles/tokens.css`。字段名见 `data-mapping.md`（API-CONTRACT.md 为权威）。
> Figma 文件清单见 `figma-links.md`。

---

## 页面清单

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
  - `dynamic:` "MA150 Tracker"（产品名，静态，`--font-size-title` bold）
  - 导航链接：Dashboard / Journal / Logs
    - 当前路由激活：文字 `--color-nav-active`（黑）
    - 非激活：`--color-nav-inactive`（灰），hover → `--color-nav-hover`
- 右：
  - `dynamic_last_refreshed:` "Last refresh: HH:MM:SS AM"（`--color-text-secondary`，12px/16px）
  - Refresh Data 按钮（F003 触发 `POST /api/data/refresh`）
    - 默认：白底 + 边框 + 刷新图标 + 文字
    - 圆角 `--radius-button`（full pill），高度 32 px
    - 加载中：图标旋转 + 文字保持 "Refresh Data"（禁用交互）

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
└── Main (padding 32 × 24)
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
│   │   └── 图表：Price line (黑) + MA150 line (蓝 #2962ff，= --color-signal-breakout)
│   │       ├── 回踩标记（Pullback markers）：在 Pullback.date 位置加小圆点
│   │       ├── X 轴：最近约 150 日交易日 (YYYY-MM-DD)     [dynamic_chart[].date]
│   │       ├── Y 轴：价格 $              [dynamic_chart[].close]
│   │       └── Hover tooltip：日期 + 收盘价（Figma 已预留 TooltipBoundingBox）
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

## 待确认项（开发侧可判断）

1. **Watchlist 搜索结果呈现**：Figma 的 Add Stock Card 仅显示 Input + Button，没画"搜索出多个候选"的 UI。MVP 建议用 `GET /api/stocks/search?q=` 即时结果显示在 Input 下方的浮层（shadcn Combobox）。
2. **SignalCard 上的 Distance 色彩**：Figma 示例只展示 BUY_ZONE 的正向，绝对值显示"+10.6MA150"格式。开发时按 distancePct 正负取色；INSUFFICIENT 情况下隐藏 Distance 文字。
3. **Pullback 标记在 K 线上**：Figma 图表未显式画出 Pullback 标记。开发时用 `lightweight-charts` 的 `createSeriesMarkers` 在 pullback.date 处加向下小三角（颜色 `--color-signal-buyzone`）。
