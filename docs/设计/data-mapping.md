---
status: draft
last_modified_by: design-bridge
last_modified_at: 2026-04-17
---

# data-mapping.md

> 最后更新：2026-04-17 | 维护者：design-bridge skill
> Figma 图层 → API 字段路径的权威映射。开发时务必以此文档为准，不得"看图起名"。
> ⚠️ 所有 API 字段名为 camelCase（后端 Pydantic alias_generator 统一转换）；DB 列名为 snake_case，此处不暴露。

---

## 字段命名约定

- **API 响应**：camelCase（如 `closePrice`、`ma150Value`、`distancePct`）
- **数据库列**：snake_case（如 `close_price`、`ma150_value`、`distance_pct`），**前端不直接接触**
- **Figma 图层名**：带 `dynamic_` 前缀的即动态字段，需绑定到 API；其余为静态文案/装饰层

---

## 页面 1：Dashboard（`/`）

### 1.1 TopNav（全局）

| Figma 图层 | API 字段路径 | 数据类型 | 说明 |
|-----------|------------|--------|------|
| `dynamic_last_refresh` | `GET /api/data/status` → `data.lastRefreshedAt` | ISO 8601 | 格式化为 `"Last refresh: MM/DD HH:mm"`；`idle` 也取此字段 |
| `dynamic_refresh_status` | `GET /api/data/status` → `data.status` | enum | `idle` / `in_progress` / `completed` / `failed`；控制 RefreshButton 的 loading 状态 |
| `dynamic_refresh_progress` | `GET /api/data/status` → `data.progress.{completed,total}` | number | 刷新进行中时显示 `"8/15"` |

### 1.2 MarketOverviewBar（全局，紧贴 TopNav 下方）

数据源：`GET /api/market/overview` → `data[]`（3 条固定：SPX / NDX / TNX）

| Figma 图层 | API 字段路径 | 数据类型 | 显示规则 |
|-----------|------------|--------|---------|
| `dynamic_index_symbol` | `data[].symbol` | string | `SPX` / `NDX` / `TNX` |
| `dynamic_index_name` | `data[].name` | string | `"S&P 500"` / `"NASDAQ 100"` / `"10-Year Treasury Yield"` |
| `dynamic_index_close` | `data[].close` | number | 保留 2 位小数 |
| `dynamic_index_change_pct` | `data[].changePct` | number | 带 `+/-` 前缀；≥ 0 用 `--color-change-positive`，< 0 用 `--color-change-negative` |
| `dynamic_index_date` | `data[].date` | YYYY-MM-DD | 可选 tooltip 显示 |

### 1.3 SignalBoard（F004，首页主区）

数据源：`GET /api/signals` → `data[]`（已按 BREAKOUT→BUY_ZONE→NEUTRAL→INSUFFICIENT 排序）

| Figma 图层 | API 字段路径 | 数据类型 | 显示规则 |
|-----------|------------|--------|---------|
| `dynamic_signal_card[]` | `data[]` | array | 卡片列表容器 |
| `dynamic_ticker` | `data[].ticker` | string | Ticker，font-family-numeric |
| `dynamic_stock_name` | `data[].name` | string | 公司名，可省略号截断 |
| `dynamic_signal_badge` | `data[].signalType` | enum | `BREAKOUT` / `BUY_ZONE` / `NEUTRAL` / `INSUFFICIENT`，颜色对应 `--color-signal-*` |
| `dynamic_close_price` | `data[].closePrice` | number | 2 位小数 |
| `dynamic_ma150_value` | `data[].ma150Value` | number | 2 位小数，label `"MA150"` |
| `dynamic_distance_pct` | `data[].distancePct` | number | 带 `+/-`，2 位小数，附 `%` |
| `dynamic_slope_indicator` | `data[].slopePositive` | boolean | `true` → ↗ 向上箭头；`false` → ↘ 向下箭头 |
| `dynamic_slope_value` | `data[].slopeValue` | number | 斜率数值（tooltip 或次要文本） |
| `dynamic_signal_date` | `data[].date` | YYYY-MM-DD | 信号日期 |

**交互**：点击 SignalCard → 打开 `StockDetailModal`（基于 `ticker` 路由数据）。

### 1.4 StockDetailModal（F005，Dashboard 弹窗）

由 4 个并发请求驱动。`ticker` 来自被点击的 SignalCard。

#### 1.4.1 信号区（调用 `GET /api/signals/:ticker?days=30`）

| Figma 图层 | API 字段路径 | 说明 |
|-----------|------------|------|
| `dynamic_modal_ticker` | `data.ticker` | 标题 |
| `dynamic_modal_stock_name` | `data.name` | 副标题 |
| `dynamic_modal_signal_badge` | `data.latest.signalType` | 当前信号 |
| `dynamic_modal_close_price` | `data.latest.closePrice` | |
| `dynamic_modal_ma150_value` | `data.latest.ma150Value` | |
| `dynamic_modal_distance_pct` | `data.latest.distancePct` | |
| `dynamic_modal_slope_positive` | `data.latest.slopePositive` | |
| `dynamic_modal_signal_date` | `data.latest.date` | |
| `dynamic_signal_history[]` | `data.history[]` | 信号历史小表（可选区域） |

#### 1.4.2 PriceChart（调用 `GET /api/stocks/:ticker/chart`）

| Figma 图层 | API 字段路径 | 说明 |
|-----------|------------|------|
| `dynamic_chart_bars[]` | `data.bars[]` | OHLCV 序列，渲染 K 线（lightweight-charts） |
| `dynamic_chart_ma150[]` | `data.ma150[]` | MA150 折线（与 bars 日期对齐，早期不足期不绘制） |
| `dynamic_chart_pullback_markers[]` | `data.pullbackMarkers[]` | 回踩事件打点（date + distancePct tooltip） |

#### 1.4.3 PullbackHistoryCard（调用 `GET /api/stocks/:ticker/pullbacks`）

| Figma 图层 | API 字段路径 | 说明 |
|-----------|------------|------|
| `dynamic_pullback_row[]` | `data[]` | 按日期倒序 |
| `dynamic_pullback_date` | `data[].date` | |
| `dynamic_pullback_close_price` | `data[].closePrice` | |
| `dynamic_pullback_ma150` | `data[].ma150Value` | |
| `dynamic_pullback_distance_pct` | `data[].distancePct` | |
| `dynamic_return_10d` | `data[].return10d` | `null` 显示 `"—"` |
| `dynamic_return_20d` | `data[].return20d` | `null` 显示 `"—"` |
| `dynamic_return_30d` | `data[].return30d` | `null` 显示 `"—"`；≥0 绿色，<0 红色 |

#### 1.4.4 FundamentalsCard（调用 `GET /api/stocks/:ticker/fundamentals`）

| Figma 图层 | API 字段路径 | 说明 |
|-----------|------------|------|
| `dynamic_pe` | `data.priceToEarnings` | P/E |
| `dynamic_ps` | `data.priceToSales` | P/S |
| `dynamic_peg` | `data.peg` | PEG |
| `dynamic_fcf` | `data.freeCashFlow` | 自由现金流，千分位格式 |
| `dynamic_market_cap` | `data.marketCap` | 市值 |
| `dynamic_source_badge` | `data.source` | `"mock"` → 显示 `"Mock Data"` 徽章；`"massive"` → 显示 `"Massive"` |
| `dynamic_fundamentals_updated_at` | `data.updatedAt` | |

### 1.5 AddStockCard（F001，首页快捷区）

- 搜索输入：`GET /api/stocks/search?q={keyword}&limit=10` → `data[].{ticker,name,exchange,type}` 作为 Combobox 选项
- 添加按钮：`POST /api/watchlist` body `{ ticker }` → 成功后刷新 SignalBoard 和 watchlist 列表

| Figma 图层 | API 字段路径 | 说明 |
|-----------|------------|------|
| `dynamic_search_options[]` | `GET /api/stocks/search` → `data[]` | Combobox 下拉 |
| `dynamic_search_ticker` | `data[].ticker` | |
| `dynamic_search_name` | `data[].name` | |
| `dynamic_search_exchange` | `data[].exchange` | |
| `dynamic_add_result_status` | `POST /api/watchlist` → `data.dataStatus` | `loading`/`ready`/`insufficient`，成功提示附带 |

### 1.6 JournalQuickAddCard（首页入口卡片）

主要为静态 CTA，点击跳转 `/journal`。无动态数据字段。

---

## 页面 2：Trade Journal（`/journal`）

### 2.1 JournalFilterCard（顶部筛选）

| Figma 图层 | 对应查询参数 | 说明 |
|-----------|------------|------|
| `dynamic_filter_ticker` | `GET /api/journal?ticker=...` | 可选；下拉由 watchlist 生成 |
| `dynamic_filter_action` | `GET /api/journal?action=...` | enum：`BUY`/`SELL`/`ADD`/`REDUCE`/`WATCH` |

### 2.2 JournalTable（列表主区）

数据源：`GET /api/journal` → `data.items[]`

| Figma 图层 | API 字段路径 | 显示规则 |
|-----------|------------|---------|
| `dynamic_journal_row[]` | `data.items[]` | 每行一条记录 |
| `dynamic_journal_date` | `data.items[].date` | YYYY-MM-DD |
| `dynamic_journal_ticker` | `data.items[].ticker` | Ticker |
| `dynamic_journal_stock_name` | `data.items[].stockName` | 公司名，次要文字 |
| `dynamic_journal_action_badge` | `data.items[].action` | 颜色对应 `--color-action-*`（BUY/SELL/ADD/REDUCE/WATCH） |
| `dynamic_journal_price` | `data.items[].price` | 2 位小数 |
| `dynamic_journal_position_size` | `data.items[].positionSize` | 可为空显示 `"—"` |
| `dynamic_journal_stop_loss` | `data.items[].stopLoss` | 可为空 |
| `dynamic_journal_target_price` | `data.items[].targetPrice` | 可为空 |
| `dynamic_journal_reason` | `data.items[].reason` | 单行省略号 |
| `dynamic_journal_reference` | `data.items[].reference` | 展开详情显示 |
| `dynamic_journal_created_at` | `data.items[].createdAt` | 详情内显示 |

分页：`data.total` / `data.limit` / `data.offset` → 分页器控制。

### 2.3 JournalEntryDialog / JournalEntryForm（新建/编辑）

提交：`POST /api/journal`（新建）或 `PUT /api/journal/:id`（编辑）。

| Figma 图层 | 请求体字段 | 必填 |
|-----------|----------|------|
| `dynamic_input_ticker` | `ticker` | ✅（必须在 watchlist 中） |
| `dynamic_input_action` | `action` | ✅ |
| `dynamic_input_price` | `price` | ✅ |
| `dynamic_input_date` | `date` | ✅ |
| `dynamic_input_position_size` | `positionSize` | ❌ |
| `dynamic_input_stop_loss` | `stopLoss` | ❌ |
| `dynamic_input_target_price` | `targetPrice` | ❌ |
| `dynamic_input_reason` | `reason` | ❌ |
| `dynamic_input_reference` | `reference` | ❌（大文本） |

删除：`DELETE /api/journal/:id`。

---

## 页面 3：System Logs（`/logs`）

### 3.1 LogLevelFilter（级别过滤）

| Figma 图层 | 对应查询参数 | 说明 |
|-----------|------------|------|
| `dynamic_level_tabs` | `GET /api/logs?level=...` | 四个 Tab：`OK` / `INFO` / `WARN` / `ERROR`，外加 `"全部"`（不传 level） |

### 3.2 LogsTable

数据源：`GET /api/logs?level={level}&limit=50` → `data[]`

| Figma 图层 | API 字段路径 | 显示规则 |
|-----------|------------|---------|
| `dynamic_log_row[]` | `data[]` | 每行一条日志，按 createdAt 倒序 |
| `dynamic_log_level_badge` | `data[].level` | `OK`/`INFO`/`WARN`/`ERROR`，颜色对应 `--color-log-*` |
| `dynamic_log_source` | `data[].source` | 来源模块名，font-family-mono 样式 |
| `dynamic_log_message` | `data[].message` | 单行省略号 |
| `dynamic_log_detail` | `data[].detail` | 展开查看，等宽字体 |
| `dynamic_log_created_at` | `data[].createdAt` | ISO 8601 → 格式化为 `MM/DD HH:mm:ss` |

---

## Step 7a：data-mapping ↔ DATA-MODEL 一致性验证

字段名在 API 层统一为 camelCase（Pydantic alias 转换），与 DATA-MODEL 中列的 snake_case 形成一对一映射。以下核对 data-mapping 使用的字段是否能在 DATA-MODEL 对应实体中找到来源。

### Stock / DailyBar / Signal / Pullback

| data-mapping 字段 | DATA-MODEL 来源 | 一致性 |
|------------------|---------------|-------|
| `ticker` | `Stock.ticker` | ✅ |
| `name` | `Stock.name` | ✅ |
| `exchange` | `Stock.exchange` | ✅ |
| `addedAt` | `Stock.added_at` | ✅（alias） |
| `signalType` | `Signal.signal_type` | ✅（alias） |
| `date` | `Signal.date` / `DailyBar.date` / `Pullback.date` / `JournalEntry.date` | ✅ |
| `closePrice` | `DailyBar.close` 或 `Signal.close_price`（依接口） | ✅ |
| `ma150Value` | `Signal.ma150_value` / `Pullback.ma150_value` | ✅（alias） |
| `distancePct` | `Signal.distance_pct` / `Pullback.distance_pct` | ✅（alias） |
| `slopePositive` | `Signal.slope_positive` | ✅（alias） |
| `slopeValue` | `Signal.slope_value` | ✅（alias） |
| `return10d` / `return20d` / `return30d` | `Pullback.return_10d / return_20d / return_30d` | ✅（alias） |
| `pullbackMarkers[].date` / `distancePct` | `Pullback.date` / `Pullback.distance_pct` | ✅ |

### MarketIndex

| data-mapping 字段 | DATA-MODEL 来源 | 一致性 |
|------------------|---------------|-------|
| `symbol` | `MarketIndex.symbol` | ✅ |
| `name` | `MarketIndex.name` | ✅ |
| `close` | `MarketIndex.close` | ✅ |
| `prevClose` | `MarketIndex.prev_close` | ✅（alias） |
| `changePct` | `MarketIndex.change_pct` | ✅（alias） |

### JournalEntry

| data-mapping 字段 | DATA-MODEL 来源 | 一致性 |
|------------------|---------------|-------|
| `ticker` | `JournalEntry.ticker` | ✅ |
| `stockName` | 关联 `Stock.name`（接口聚合字段） | ✅ |
| `action` | `JournalEntry.action` | ✅ |
| `price` | `JournalEntry.price` | ✅ |
| `date` | `JournalEntry.date` | ✅ |
| `positionSize` | `JournalEntry.position_size` | ✅（alias） |
| `stopLoss` | `JournalEntry.stop_loss` | ✅（alias） |
| `targetPrice` | `JournalEntry.target_price` | ✅（alias） |
| `reason` | `JournalEntry.reason` | ✅ |
| `reference` | `JournalEntry.reference` | ✅ |
| `createdAt` | `JournalEntry.created_at` | ✅（alias） |
| `updatedAt` | `JournalEntry.updated_at` | ✅（alias） |

### SystemLog

| data-mapping 字段 | DATA-MODEL 来源 | 一致性 |
|------------------|---------------|-------|
| `id` | `SystemLog.id` | ✅ |
| `level` | `SystemLog.level` | ✅ |
| `source` | `SystemLog.source` | ✅ |
| `message` | `SystemLog.message` | ✅ |
| `detail` | `SystemLog.detail` | ✅ |
| `createdAt` | `SystemLog.created_at` | ✅（alias） |

### 枚举值一致性

| 字段 | data-mapping 取值 | DATA-MODEL 定义 | 一致性 |
|------|-----------------|---------------|-------|
| `signalType` | BREAKOUT / BUY_ZONE / NEUTRAL / INSUFFICIENT | `Signal.signal_type` 枚举 | ✅ |
| `action` | BUY / SELL / ADD / REDUCE / WATCH | `JournalEntry.action` 枚举 | ✅ |
| `level` | OK / INFO / WARN / ERROR | `SystemLog.level` 枚举 | ✅ |
| `source` (fundamentals) | mock / massive | DATA-MODEL 未建表（运行时字段），由 API-CONTRACT 明确 | ✅ |

### Fundamentals 特殊说明

`/stocks/:ticker/fundamentals` 的字段（`priceToEarnings`、`priceToSales`、`peg`、`freeCashFlow`、`marketCap`）**不落库**，MVP 阶段从代码内 mock 返回。DATA-MODEL 未定义 Fundamentals 实体，**属于预期内缺失**——不阻塞验证。

**Step 7a 结论**：✅ 全部通过，无命名/枚举差异。

---

## Step 7b：data-mapping ↔ API-CONTRACT 一致性验证

逐字段核对是否有对应接口已定义。

| 页面 / 区块 | 依赖接口 | API-CONTRACT 状态 |
|------------|---------|-----------------|
| Dashboard TopNav 刷新状态 | `GET /api/data/status` | ✅ 已定义 |
| Dashboard RefreshButton | `POST /api/data/refresh` | ✅ 已定义 |
| Dashboard MarketOverviewBar | `GET /api/market/overview` | ✅ 已定义 |
| Dashboard SignalBoard | `GET /api/signals` | ✅ 已定义 |
| Modal 信号区 | `GET /api/signals/:ticker` | ✅ 已定义 |
| Modal PriceChart | `GET /api/stocks/:ticker/chart` | ✅ 已定义 |
| Modal PullbackHistoryCard | `GET /api/stocks/:ticker/pullbacks` | ✅ 已定义 |
| Modal FundamentalsCard | `GET /api/stocks/:ticker/fundamentals` | ✅ 已定义 |
| AddStockCard 搜索 | `GET /api/stocks/search` | ✅ 已定义 |
| AddStockCard 添加 | `POST /api/watchlist` | ✅ 已定义 |
| Journal 列表 | `GET /api/journal` | ✅ 已定义 |
| Journal 新建 | `POST /api/journal` | ✅ 已定义 |
| Journal 编辑 | `PUT /api/journal/:id` | ✅ 已定义 |
| Journal 删除 | `DELETE /api/journal/:id` | ✅ 已定义 |
| System Logs 列表 | `GET /api/logs` | ✅ 已定义 |

**Step 7b 结论**：✅ 全部通过，无缺失接口。

---

## Step 7c：tokens.json ↔ DATA-MODEL 枚举对齐核对

| DATA-MODEL 枚举 | 期望 token | tokens.json 实际 | 一致性 |
|----------------|----------|----------------|-------|
| Signal.signal_type = BREAKOUT | `signal-breakout` | `signal-breakout: #2962ff` | ✅ |
| Signal.signal_type = BUY_ZONE | `signal-buyzone` | `signal-buyzone: #10b981` | ✅ |
| Signal.signal_type = NEUTRAL | `signal-neutral` | `signal-neutral: #9ca3af` | ✅ |
| Signal.signal_type = INSUFFICIENT | `signal-insufficient` | `signal-insufficient: #d1d5db` | ✅ |
| JournalEntry.action = BUY | `action-buy` | `action-buy: #10b981` | ✅ |
| JournalEntry.action = SELL | `action-sell` | `action-sell: #ef4444` | ✅ |
| JournalEntry.action = ADD | `action-add` | `action-add: #2962ff` | ✅ |
| JournalEntry.action = REDUCE | `action-reduce` | `action-reduce: #f97316` | ✅ |
| JournalEntry.action = WATCH | `action-watch` | `action-watch: #9ca3af` | ✅ |
| SystemLog.level = OK | `log-ok` | `log-ok: #10b981` | ✅ |
| SystemLog.level = INFO | `log-info` | `log-info: #9ca3af` | ✅ |
| SystemLog.level = WARN | `log-warn` | `log-warn: #f59e0b` | ✅ |
| SystemLog.level = ERROR | `log-error` | `log-error: #ef4444` | ✅ |
| MarketIndex.change_pct ≥ 0 | `change-positive` | `change-positive: #10b981` | ✅ |
| MarketIndex.change_pct < 0 | `change-negative` | `change-negative: #ef4444` | ✅ |

**Step 7c 结论**：✅ tokens.json 枚举色彩 100% 覆盖 DATA-MODEL 对应字段取值，无缺失、无命名歧义，tokens.json 可作为权威直接用于前端实现。

---

## 总验证结果

| 检查项 | 结果 |
|-------|------|
| 7a — data-mapping ↔ DATA-MODEL 字段对齐 | ✅ PASS |
| 7a — 枚举取值对齐 | ✅ PASS |
| 7b — data-mapping ↔ API-CONTRACT 接口覆盖 | ✅ PASS |
| 7c — tokens.json ↔ DATA-MODEL 枚举色彩对齐 | ✅ PASS |

所有 8 个 P0 feature（F001–F008）的数据绑定基础已验证完整，可将 phase 推进至 `ready_to_dev`。
