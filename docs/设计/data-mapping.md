---
status: draft
last_modified_by: design-bridge
last_modified_at: 2026-04-24
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

---

# 页面 4：Cockpit（`/cockpit`）— v1.8 / v1.9 / v2.0

> 最后扩展：2026-04-24（design-bridge）
> 关联 Feature：F200–F211
> design-spec 章节：`design-spec.md` v1.8/v1.9/v2.0 章节
> Cockpit 命名空间字段全部经 Pydantic alias_generator 转 camelCase；DB 列保持 snake_case，前端不接触

---

## §Cockpit-1：MarketRegimeWidget（F201）

数据源：`GET /api/cockpit/regime`

### 1.a Score Hero

| design-spec 元素 | API 字段路径 | 数据类型 | 显示规则 |
|---|---|---|---|
| `dynamic_regime_pill` | `data.regime` | enum 5 值 | RegimePill 子组件，按 token `--color-regime-*` 着色 |
| `dynamic_market_score` | `data.marketScore` | integer 0-100 | `"Score 68 / 100"` |
| `dynamic_allowed_exposure_pct` | `data.allowedExposurePct` | number | `"Allowed Exposure: 70%"`，1 位小数 |
| `dynamic_single_trade_risk_pct` | `data.singleTradeRiskPct` | number | `"Single Trade Risk: 1.0%"`，1 位小数 |
| `dynamic_score_date` | `data.date` | YYYY-MM-DD | tooltip 显示"As of {date}" |
| `dynamic_computed_at` | `data.computedAt` | ISO 8601 | tooltip 显示更新时间 |

### 1.b 6-dim Subscores（2×3 网格）

| design-spec 元素 | API 字段路径 | 显示规则 |
|---|---|---|
| `dynamic_subscore_spy_trend` | `data.subscores.spyTrend` | "Trend(SPY) 18 / 25"，进度条满分 25 |
| `dynamic_subscore_qqq_trend` | `data.subscores.qqqTrend` | "Trend(QQQ) 14 / 20"，满分 20 |
| `dynamic_subscore_iwm_breadth` | `data.subscores.iwmBreadth` | "Breadth(IWM) 9 / 15"，满分 15 |
| `dynamic_subscore_sector_participation` | `data.subscores.sectorParticipation` | "Sector Part. 14 / 20"，满分 20 |
| `dynamic_subscore_risk_appetite` | `data.subscores.riskAppetite` | "Risk Appetite 7 / 10"，满分 10 |
| `dynamic_subscore_volatility_stress` | `data.subscores.volatilityStress` | "Volatility 6 / 10"，满分 10 |

> 满分参考 D061；进度条颜色按 ≥80% 绿、≥60% 浅绿、≥40% 黄、≥20% 橙、<20% 红（对齐 regime 色阶）

### 1.c Indices 卡片（3 行：SPY/QQQ/IWM）

| design-spec 元素 | API 字段路径 | 显示规则 |
|---|---|---|
| `dynamic_index_row[]` | `data.indices[]` | 长度固定 3 |
| `dynamic_index_symbol` | `data.indices[].symbol` | "SPY" / "QQQ" / "IWM" |
| `dynamic_index_close` | `data.indices[].close` | 2 位小数，附 `$` |
| `dynamic_index_change_pct` | `data.indices[].changePct` | `+/-` 前缀 + `--color-change-positive/negative` |
| `dynamic_index_above_ma50` | `data.indices[].aboveMa50` | true → "50MA✓" 绿，false → "50MA✗" 灰 |
| `dynamic_index_above_ma200` | `data.indices[].aboveMa200` | 同上 |
| `dynamic_index_state` | `data.indices[].state` | enum 6 值文本 |
| `dynamic_index_rs_trend` | `data.indices[].rsTrend` | enum `up/down/flat` → ↗ / ↘ / → 箭头 |

### 1.d Sector Heatmap（11 sector ETF）

| design-spec 元素 | API 字段路径 | 显示规则 |
|---|---|---|
| `dynamic_sector_cell[]` | `data.sectors[]` | 长度固定 11 |
| `dynamic_sector_symbol` | `data.sectors[].symbol` | XLK/XLY/XLF/XLI/XLE/XLV/XLC/XLP/XLU/XLB/XLRE 之一 |
| `dynamic_sector_close` | `data.sectors[].close` | tooltip；null 时占位 `—` |
| `dynamic_sector_change_pct` | `data.sectors[].changePct` | tooltip 显示 |
| `dynamic_sector_state` | `data.sectors[].state` | enum 4 值 → 单元格背景色 token |

### 1.e AI Market Notes（v2.0，F209 market_narrator）

数据源：`POST /api/ai/market_narrator` 输出（异步加载，cache 24h）

| design-spec 元素 | 输出字段路径 | 显示规则 |
|---|---|---|
| `dynamic_ai_headline` | `data.output.headline` | 一行 ≤80 字 |
| `dynamic_ai_summary[]` | `data.output.summary` | 段落文本，截至 ≤140×2 行 |
| `dynamic_ai_warnings[]` | `data.output.warnings[]` | ⚠️ + 文本，每条独立 chip |
| `dynamic_ai_cache_meta` | `data.meta.cacheHit` + `data.meta.modelUsed` | cacheHit=true 时显示"Cached · {age}"灰字 |
| `dynamic_ai_refresh_button` | — | 按钮 disabled 直至 cache TTL > 1h |

---

## §Cockpit-2：EarningsWidget（F204）

数据源：`GET /api/cockpit/earnings?ticker={cockpitStore.selectedTicker}`（v1.8 单 ticker；watchlist 列表由前端循环调用）

| design-spec 元素 | API 字段路径 | 显示规则 |
|---|---|---|
| `dynamic_selected_ticker` | （来自 cockpitStore，非 API） | "Selected: NVDA" |
| `dynamic_next_earnings_date` | `data.nextEarningsDate` | YYYY-MM-DD；null → "—" |
| `dynamic_time_of_day` | `data.timeOfDay` | enum `BMO/AMC/null` 显示 "(AMC)" |
| `dynamic_days_until` | `data.daysUntil` | integer；null → "—" |
| `dynamic_earnings_risk_dot` | 由 `daysUntil` 派生 | ≤3 → DANGER 红；4-10 → CAUTION 橙；>10 → SAFE 绿；EarningsRiskDot 子组件 |
| `dynamic_eps_estimate` | `data.epsEstimate` | `$5.20`；null → "—" |
| `dynamic_revenue_estimate` | `data.revenueEstimate` | "$48.0B" 自动单位（M/B/T） |
| `dynamic_no_earnings_note` | `data.note` | 当 `nextEarningsDate=null` 显示 |
| `dynamic_watchlist_row[]` | watchlist 多 ticker 循环结果 | 排序按 daysUntil 升序 |

---

## §Cockpit-3：PoolBuilderWidget（F205，v1.9）

数据源：`GET /api/cockpit/pool?...`

### 3.a Funnel

| design-spec 元素 | API 字段路径 | 显示规则 |
|---|---|---|
| `dynamic_funnel_tradable` | `data.funnel.tradable` | "1,850" 千分位 |
| `dynamic_funnel_trend` | `data.funnel.trend` | 同上 |
| `dynamic_funnel_rs` | `data.funnel.rs` | 同上 |
| `dynamic_funnel_fundamental` | `data.funnel.fundamental` | 同上 |
| `dynamic_funnel_action` | `data.funnel.action` | 同上 |

### 3.b Filter Bar（受控查询参数）

| design-spec 元素 | 查询参数 | 默认 |
|---|---|---|
| `dynamic_filter_market_cap_min` | `marketCapMin` | 50000000000 |
| `dynamic_filter_price_min` | `priceMin` | 10 |
| `dynamic_filter_adv_min` | `advMin` | 20000000 |
| `dynamic_filter_trend_score_min` | `trendScoreMin` | 3 |
| `dynamic_filter_rs_percentile_min` | `rsPercentileMin` | 70 |
| `dynamic_filter_revenue_growth_min` | `revenueGrowthYoyMin` | 10.0 |
| `dynamic_filter_sectors` | `sectors` | 全部 |
| `dynamic_filter_setup_types` | `setupTypes` | 全部 |
| `dynamic_filter_limit` | `limit` | 50 |

### 3.c 候选表 items

| design-spec 元素 | API 字段路径 | 显示规则 |
|---|---|---|
| `dynamic_pool_row[]` | `data.items[]` | |
| `dynamic_pool_ticker` | `data.items[].ticker` | font-numeric |
| `dynamic_pool_name` | `data.items[].name` | 单行省略 |
| `dynamic_pool_sector` | `data.items[].sector` | sector ETF symbol |
| `dynamic_pool_price` | `data.items[].price` | 2 位小数，`$` |
| `dynamic_pool_trend_score` | `data.items[].trendScore` | 0-5 |
| `dynamic_pool_rs_percentile` | `data.items[].rsPercentile` | 0-100 |
| `dynamic_pool_setup_type` | `data.items[].setupType` | SetupTypeBadge 子组件 |
| `dynamic_pool_distance_to_pivot_pct` | `data.items[].distanceToPivotPct` | `+/-`，2 位小数，附 `%` |
| `dynamic_pool_distance_to_50ma_pct` | `data.items[].distanceTo50maPct` | tooltip |
| `dynamic_pool_earnings_date` | `data.items[].earningsDate` | tooltip |
| `dynamic_pool_days_until_earnings` | `data.items[].daysUntilEarnings` | "D-28" |
| `dynamic_pool_revenue_growth_yoy` | `data.items[].revenueGrowthYoy` | `%` 后缀 |
| `dynamic_pool_suggested_action` | `data.items[].suggestedAction` | enum 文本 + 配色 |
| `dynamic_pool_in_watchlist` | `data.items[].inWatchlist` | true → 按钮 `[✓ in watchlist]` 灰；false → `[+ Add]` 蓝 |

`[+ Add]` 提交：`POST /api/watchlist` body `{ ticker }`，成功后 react-query invalidate `['cockpit-pool']` + `['watchlist']`。

---

## §Cockpit-4：CockpitChartWidget（F203）

数据源：`GET /api/cockpit/chart/{ticker}` + `GET /api/cockpit/decision/{ticker}`（联合）

### 4.a Chart 标题区

| design-spec 元素 | 字段来源 | 显示规则 |
|---|---|---|
| `dynamic_chart_ticker` | `cockpitStore.selectedTicker` | font-numeric |
| `dynamic_chart_setup_type` | `decision.setupType` | SetupTypeBadge |
| `dynamic_chart_setup_quality` | `decision.setupQuality` | SetupQualityBadge |
| `dynamic_chart_timeframe_toggle` | 前端状态 `D/W` | v1.8 仅 D |
| `dynamic_chart_ma_toggle` | 前端状态 → `?mas=` 参数 | 默认 10,21,50,150,200 |

### 4.b 主图（lightweight-charts）

| design-spec 元素 | API 字段路径 | 渲染方式 |
|---|---|---|
| `dynamic_chart_bars[]` | `chart.bars[]` | candlestick OHLCV |
| `dynamic_chart_ma_10` | `chart.mas["10"]` | line series |
| `dynamic_chart_ma_21` | `chart.mas["21"]` | line series |
| `dynamic_chart_ma_50` | `chart.mas["50"]` | line series |
| `dynamic_chart_ma_150` | `chart.mas["150"]` | line series |
| `dynamic_chart_ma_200` | `chart.mas["200"]` | line series |
| `dynamic_chart_atr` | `chart.atr[]` | 副指标（v1.9 才用，可选） |
| `dynamic_chart_avwap_anchor` | `chart.avwap.anchor` | line legend tooltip 显示 anchor 日期 |
| `dynamic_chart_avwap_series` | `chart.avwap.series[]` | line series，token `--color-chart-avwap-line` |

### 4.c 横线 / 标记叠加

| design-spec 元素 | 字段来源 | 渲染方式 |
|---|---|---|
| `dynamic_chart_entry_line` | `decision.entryPrice` | createPriceLine 实线 `--color-chart-entry-line` |
| `dynamic_chart_stop_line` | `decision.stopPrice` | createPriceLine 虚线 `--color-chart-stop-line` |
| `dynamic_chart_target_2r_line` | `decision.target2r` | createPriceLine 点线 `--color-chart-target-line` |
| `dynamic_chart_target_3r_line` | `decision.target3r` | createPriceLine 点线（更细）|
| `dynamic_chart_earnings_marker` | `earnings.nextEarningsDate` | createSeriesMarkers ▼ `--color-chart-earnings-marker` |
| `dynamic_chart_setup_annotation` | `decision.setupType` + `entryPrice` | tooltip 文本 `"BREAKOUT pivot @{entry}"` |

### 4.d 成交量副图

| design-spec 元素 | API 字段路径 | 渲染方式 |
|---|---|---|
| `dynamic_chart_volume[]` | `chart.bars[].volume` | histogram，up=半透明绿、down=半透明红（沿用 F107 配色） |

---

## §Cockpit-5：SetupMonitorWidget（F202）

数据源：`GET /api/cockpit/setup-monitor?filter=...`

### 5.a Filter Tabs

| design-spec 元素 | API 字段路径 | 显示规则 |
|---|---|---|
| `dynamic_summary_total` | `data.summary.total` | "All 32" |
| `dynamic_summary_ready` | `data.summary.ready` | "Ready 3" |
| `dynamic_summary_near` | `data.summary.near` | "Near 7" |
| `dynamic_summary_extended` | `data.summary.extended` | "Extended 4" |
| `dynamic_summary_broken` | `data.summary.broken` | "Broken 2" |
| `dynamic_summary_none` | `data.summary.none` | "None 16"（默认隐藏） |

Tab 切换 → 改 `?filter=ready,near,...` 重发请求。

### 5.b 行表

| design-spec 元素 | API 字段路径 | 显示规则 |
|---|---|---|
| `dynamic_setup_row[]` | `data.items[]` | 排序按 `suggestedAction` enter→watch→wait→null→reduce→exit |
| `dynamic_setup_ready_marker` | `data.items[].readySignal` | true → 行左侧 `▍` 蓝色高亮条 |
| `dynamic_setup_ticker` | `data.items[].ticker` | font-numeric |
| `dynamic_setup_stock_name` | `data.items[].stockName` | tooltip |
| `dynamic_setup_type` | `data.items[].setupType` | SetupTypeBadge |
| `dynamic_setup_quality` | `data.items[].setupQuality` | SetupQualityBadge |
| `dynamic_setup_entry_price` | `data.items[].entryPrice` | 2 位小数 |
| `dynamic_setup_stop_price` | `data.items[].stopPrice` | 2 位小数 |
| `dynamic_setup_target_2r` | `data.items[].target2r` | 2 位小数（hover/扩展行） |
| `dynamic_setup_target_3r` | `data.items[].target3r` | 同上 |
| `dynamic_setup_reward_risk` | `data.items[].rewardRisk` | "2.0"，1 位小数 |
| `dynamic_setup_distance_to_entry_pct` | `data.items[].distanceToEntryPct` | `+/-`，2 位小数，`%` |
| `dynamic_setup_rs_percentile` | `data.items[].rsPercentile` | 0-100 |
| `dynamic_setup_volume_status` | `data.items[].volumeStatus` | enum HIGH/NORMAL/LOW/null → 上箭头/—/下箭头/隐藏 |
| `dynamic_setup_trend_score` | `data.items[].trendScore` | 0-5（hover/扩展行） |
| `dynamic_setup_earnings_risk` | `data.items[].earningsRisk` | EarningsRiskDot |
| `dynamic_setup_suggested_action` | `data.items[].suggestedAction` | 行右端按钮文本（点击不触发提交，仅展示） |
| `dynamic_setup_scan_date` | `data.items[].scanDate` | tooltip |

行点击 → `cockpitStore.setSelectedTicker(ticker)`，联动 Chart / Decision / Earnings widget。

### 5.c AI Candidate Ranker（F210-b）

数据源：`GET /api/cockpit/regime`（regime + marketScore）+ `POST /api/ai/candidate_ranker`

**输入构造（SetupItem → CandidateInput）**：

| 前端字段 | API/store 来源 | 传入 schema 字段 | 备注 |
|---|---|---|---|
| `regime` | `regimeData.regime` | `CandidateRankerInput.regime` | 5 值 RegimeLabel |
| `regimeScore` | `regimeData.marketScore` | `CandidateRankerInput.regimeScore` | 字段名在前端适配 |
| `candidates[].ticker` | `item.ticker` | 直传 | — |
| `candidates[].setupType` | `item.setupType` | 直传 | 7 值 SetupType |
| `candidates[].setupQuality` | `item.setupQuality` | 直传 | A/B/C/null |
| `candidates[].trendScore` | `item.trendScore` | 直传 | 0-5 |
| `candidates[].rsPercentile` | `item.rsPercentile` | 直传 | 0-100 |
| `candidates[].distanceToEntryPct` | `item.distanceToEntryPct ?? 0` | null → 0 容错 | — |
| `candidates[].rewardRisk` | `Math.max(item.rewardRisk ?? 0, 0)` | null/负 → 0 | schema ge=0 |
| `candidates[].earningsRisk` | `item.earningsRisk` | 直传 | SAFE/CAUTION/DANGER |
| `candidates[].readySignal` | `item.readySignal` | 直传 | boolean |

截断：前端 `items.slice(0, 20)`，超 20 时 result header 显示 "Top 20 / N"。

**输出渲染（CandidateRankerOutput → AiCandidateRankerSection）**：

| UI 元素 | schema 字段路径 | 渲染规则 |
|---|---|---|
| rank 数字 | `output.topCandidates[].rank` | `#1` / `#2` / `#3` |
| ticker 文本 | `output.topCandidates[].ticker` | 粗体 |
| action badge | `output.topCandidates[].action` | enter → breakout 色 / watch → warn 色 / wait → muted 色（三色枚举）|
| reason 文本 | `output.topCandidates[].reason` | 单行 ellipsis |
| cache 徽章 | `meta.cacheHit` | true → "Cached"；false → "Generated · {modelUsed}" |

---

## §Cockpit-6：DecisionPanelWidget（F203 + F210/F211）

数据源：`GET /api/cockpit/decision/{cockpitStore.selectedTicker}` + `GET /api/cockpit/user-settings`

### 6.a Decision Card（左半，全部由 `decision` 接口提供）

| design-spec 元素 | API 字段路径 | 显示规则 |
|---|---|---|
| `dynamic_decision_setup_type` | `decision.setupType` | SetupTypeBadge |
| `dynamic_decision_setup_quality` | `decision.setupQuality` | SetupQualityBadge |
| `dynamic_decision_entry_price` | `decision.entryPrice` | 2 位小数 |
| `dynamic_decision_stop_price` | `decision.stopPrice` | 2 位小数 |
| `dynamic_decision_target_2r` | `decision.target2r` | 2 位小数 |
| `dynamic_decision_target_3r` | `decision.target3r` | 2 位小数 |
| `dynamic_decision_reward_risk` | `decision.rewardRisk` | "2.0" |
| `dynamic_decision_risk_per_share` | `decision.riskPerShare` | `$30.00` |
| `dynamic_decision_suggested_shares` | `decision.suggestedShares` | "33 shares" |
| `dynamic_decision_position_value` | `decision.positionValue` | `$28,050` 千分位 |
| `dynamic_decision_account_risk_pct` | `decision.accountRiskPct` | "0.99%"，2 位小数 |
| `dynamic_decision_earnings_risk` | `decision.earningsRisk` | EarningsRiskDot |
| `dynamic_decision_earnings_date` | `decision.earningsDate` | "(D-28)" 派生 daysUntil |
| `dynamic_decision_deterministic_hash` | `decision.deterministicHash` | 截断 `7f2a9b...` 8 字符 + 完整 tooltip |

### 6.b Override Form（右半，受控输入 → query 参数）

| design-spec 元素 | 查询参数 | 显示规则 |
|---|---|---|
| `dynamic_override_entry` | `entryOverride` | 数字 input；空则不传 |
| `dynamic_override_stop` | `stopOverride` | 数字 input |
| `dynamic_override_risk_pct` | `riskPctOverride` | 数字 input，0-5 |
| `dynamic_effective_risk_pct` | `decision.effectiveRiskPct` | 显示在右半下方 |
| `dynamic_regime_cap` | `decision.regimeCap` | 派生展示 "(regime {n}.{n})" |
| `dynamic_user_setting_cap` | `decision.userSettingCap` | 派生展示 "(user {n}.{n})" |

### 6.c AI Trade Plan（v2.0，F210）

数据源：`POST /api/ai/trade_plan` body `{ input: {...decision quote...} }`

| design-spec 元素 | 输出字段路径 | 显示规则 |
|---|---|---|
| `dynamic_ai_plan_memo` | `data.output.memo` | 多行段落 |
| `dynamic_ai_plan_management[]` | `data.output.management[]` | 编号列表 |
| `dynamic_ai_plan_entry` | `data.output.entry` | 与 decision.entryPrice 严格相等（guardrail） |
| `dynamic_ai_plan_stop` | `data.output.stop` | 与 decision.stopPrice 严格相等 |
| `dynamic_ai_plan_size` | `data.output.size` | 与 decision.suggestedShares 严格相等 |
| `dynamic_ai_plan_guardrail_status` | 派生 | 通过 → "✓ Guardrail passed"；失败 → 红 banner "Guardrail violation - AI output rejected"（HTTP 409 AI_GUARDRAIL_VIOLATION） |
| `dynamic_ai_plan_cache_meta` | `data.meta.cacheHit/modelUsed/costUsd` | "Cached · {age}" 或 "Generated · {model}" |

### 6.d AI Contradictions（v2.0，F211）

数据源：`POST /api/ai/contradiction_detector`

| design-spec 元素 | 输出字段路径 | 显示规则 |
|---|---|---|
| `dynamic_contradiction_item[]` | `data.output.contradictions[]` | ⚠ + 文本 + 严重度（LOW/MEDIUM/HIGH 颜色 chip） |
| `dynamic_contradiction_recommendation` | `data.output.recommendation` | 一行总结文本 |

### 6.e Save as PendingOrder（按钮 → POST）

`[Save as PendingOrder]` 调 `POST /api/cockpit/pending-orders` body：
```
{ ticker, setupType, entryPrice, stopPrice, shares, target2r, target3r, expirationDate, notes }
```
（字段全部取自 decision 当前值；shares = `decision.suggestedShares`）

---

## §Cockpit-7：PositionListWidget（F206，v1.9）

数据源：`GET /api/cockpit/positions?status=open`

### 7.a Summary 顶条

| design-spec 元素 | API 字段路径 | 显示规则 |
|---|---|---|
| `dynamic_summary_open_risk_pct` | `data.summary.openRiskPct` | "Open Risk: 2.5%" |
| `dynamic_summary_total_exposure_pct` | `data.summary.totalExposurePct` | "Exposure: 45%" |
| `dynamic_summary_pending_risk_pct` | `data.summary.pendingRiskPct` | "Pending: 1.0%" |
| `dynamic_summary_positions_count` | `data.summary.positionsCount` | "5 pos" |
| `dynamic_summary_pending_count` | `data.summary.pendingCount` | "2 ord" |

### 7.b 持仓行

| design-spec 元素 | API 字段路径 | 显示规则 |
|---|---|---|
| `dynamic_position_row[]` | `data.items[]` | |
| `dynamic_position_id` | `data.items[].id` | 内部 key |
| `dynamic_position_ticker` | `data.items[].ticker` | font-numeric |
| `dynamic_position_entry_price` | `data.items[].entryPrice` | 2 位小数 |
| `dynamic_position_entry_date` | `data.items[].entryDate` | tooltip |
| `dynamic_position_shares` | `data.items[].shares` | "(33 sh)" 副字 |
| `dynamic_position_last_close` | `data.items[].lastClose` | 2 位小数 |
| `dynamic_position_stop_price` | `data.items[].stopPrice` | 2 位小数 |
| `dynamic_position_target_2r` | `data.items[].target2r` | tooltip |
| `dynamic_position_target_3r` | `data.items[].target3r` | tooltip |
| `dynamic_position_setup_type` | `data.items[].setupType` | SetupTypeBadge |
| `dynamic_position_status` | `data.items[].status` | enum OPEN/CLOSED |
| `dynamic_position_r_multiple` | `data.items[].rMultiple` | "0.83" / "-0.50"，2 位小数，正绿/负红 |
| `dynamic_position_unrealized_pl` | `data.items[].unrealizedPl` | `+$825` / `-$140`，正绿/负红 |
| `dynamic_position_value` | `data.items[].positionValue` | tooltip |
| `dynamic_position_earnings_risk` | 由 `daysUntilEarnings` 派生 | EarningsRiskDot |
| `dynamic_position_days_until_earnings` | `data.items[].daysUntilEarnings` | "D-28" |
| `dynamic_position_next_action` | `data.items[].nextAction` | enum hold(灰)/raise_stop(蓝)/reduce(橙)/exit(红) |
| `dynamic_position_closed_at` | `data.items[].closedAt` | 仅 status=CLOSED 显示 |
| `dynamic_position_close_price` | `data.items[].closePrice` | 同上 |
| `dynamic_position_created_at` | `data.items[].createdAt` | tooltip |
| `dynamic_position_updated_at` | `data.items[].updatedAt` | tooltip |

### 7.c PositionFormDialog（POST / PATCH 请求体）

| design-spec 元素 | 请求体字段 | 必填 |
|---|---|---|
| `dynamic_input_ticker` | `ticker` | ✅ |
| `dynamic_input_entry_price` | `entryPrice` | ✅ |
| `dynamic_input_entry_date` | `entryDate` | ✅ |
| `dynamic_input_shares` | `shares` | ✅ |
| `dynamic_input_stop_price` | `stopPrice` | ✅ |
| `dynamic_input_target_2r` | `target2r` | ❌ |
| `dynamic_input_target_3r` | `target3r` | ❌ |
| `dynamic_input_setup_type` | `setupType` | ❌ |
| `dynamic_input_notes` | `notes` | ❌ |
| `dynamic_suggested_shares_hint` | `decision.suggestedShares` | 灰字提示"Cockpit 推荐 N shares"（仅 New 模式）|

PATCH 额外可选：`status`、`closedAt`、`closePrice`。

---

## §Cockpit-8：PendingOrdersWidget（F206，v1.9）

数据源：`GET /api/cockpit/pending-orders?status=active`

| design-spec 元素 | API 字段路径 | 显示规则 |
|---|---|---|
| `dynamic_order_row[]` | `data[]` | 数组直接 |
| `dynamic_order_id` | `data[].id` | 内部 key |
| `dynamic_order_ticker` | `data[].ticker` | font-numeric |
| `dynamic_order_setup_type` | `data[].setupType` | SetupTypeBadge |
| `dynamic_order_entry_price` | `data[].entryPrice` | 2 位小数 |
| `dynamic_order_stop_price` | `data[].stopPrice` | 2 位小数 |
| `dynamic_order_shares` | `data[].shares` | tooltip |
| `dynamic_order_target_2r` | `data[].target2r` | tooltip |
| `dynamic_order_target_3r` | `data[].target3r` | tooltip |
| `dynamic_order_last_close` | `data[].lastClose` | 2 位小数 |
| `dynamic_order_distance_to_trigger_pct` | `data[].distanceToTriggerPct` | `+/-`，2 位小数，`%`；>5% 灰、1-5% 默认、<1% 加粗 |
| `dynamic_order_risk_pct` | `data[].riskPct` | "0.70%"，2 位小数 |
| `dynamic_order_expiration_date` | `data[].expirationDate` | YYYY-MM-DD；null → "—" |
| `dynamic_order_status` | `data[].status` | enum ACTIVE/TRIGGERED/CANCELLED/EXPIRED |
| `dynamic_order_notes` | `data[].notes` | tooltip |
| `dynamic_order_created_at` | `data[].createdAt` | tooltip |
| `dynamic_order_updated_at` | `data[].updatedAt` | tooltip |

按钮：
- `[Triggered]` → `PATCH /api/cockpit/pending-orders/{id}` body `{ status: "TRIGGERED" }`
- `[Cancel]` → `PATCH` body `{ status: "CANCELLED" }`，无二次确认

---

## §Cockpit-9：ActionListWidget（F207，v1.9）

数据源：`GET /api/cockpit/actions/today`

| design-spec 元素 | API 字段路径 | 显示规则 |
|---|---|---|
| `dynamic_actions_as_of_date` | `data.asOfDate` | 顶部右侧 "2026-04-24" |
| `dynamic_must_act_row[]` | `data.mustAct[]` | 红底淡（`--color-action-must-bg`） |
| `dynamic_monitor_row[]` | `data.monitor[]` | 橙底淡（`--color-action-monitor-bg`） |
| `dynamic_no_action_row[]` | `data.noAction[]` | 绿底淡（`--color-action-noaction-bg`） |
| `dynamic_action_ticker` | `data.{must,...}[].ticker` | font-numeric |
| `dynamic_action_type` | `data.{must,...}[].actionType` | 枚举文本（详见 actionType 表） |
| `dynamic_action_rationale` | `data.{must,...}[].rationale` | 单行截断 + hover tooltip 全文 |
| `dynamic_action_refs` | `data.{must,...}[].refs` | object，按 actionType 解读：positionId / orderId / earningsDate / newStop |

行点击 ticker → `cockpitStore.setSelectedTicker(ticker)` 联动其他 widget。

AI Daily Brief（v2.0，可折叠）：
- 触发 `POST /api/ai/contradiction_detector` + 内部聚合（具体 schema 见 backend/app/ai/schemas，design-spec 不约束）

---

## §Cockpit-Settings：UserSettingsDialog（F203 配置弹窗）

数据源：`GET /api/cockpit/user-settings` + `PUT /api/cockpit/user-settings`

| design-spec 元素 | API 字段路径 | 校验 |
|---|---|---|
| `dynamic_settings_account_size` | `data.accountSize` ↔ PUT body `accountSize` | > 0 |
| `dynamic_settings_max_exposure_pct` | `data.maxExposurePct` ↔ `maxExposurePct` | [0, 100] |
| `dynamic_settings_single_trade_risk_pct` | `data.singleTradeRiskPct` ↔ `singleTradeRiskPct` | [0, 5] |
| `dynamic_settings_default_risk_per_trade_pct` | `data.defaultRiskPerTradePct` ↔ `defaultRiskPerTradePct` | [0, 5] |
| `dynamic_settings_base_currency` | `data.baseCurrency` ↔ `baseCurrency` | enum；MVP 仅 "USD" |
| `dynamic_settings_updated_at` | `data.updatedAt` | "Last saved {ago}" 灰字 |

---

## §Cockpit-AI-Wrapper：所有 `POST /api/ai/{task_type}` 通用响应

适用于 §Cockpit-1.e（market_narrator）、§Cockpit-5（setup_explainer hover）、§Cockpit-6.c/d（trade_plan / contradiction_detector）、§Cockpit-9（contradiction_detector / journal_assistant）

| 字段路径 | 用途 |
|---|---|
| `data.memoId` | 写入 ai_memos 后的主键，前端不展示 |
| `data.taskType` | 回显 |
| `data.schemaVersion` | 用于"AI 输出可能已过期"提示（schemaVersion ≠ 客户端期望版本时弹更新提示） |
| `data.output` | task-specific schema，按各 widget 章节解读 |
| `data.meta.modelUsed` | "gpt-5.4-mini"；"cache" 表示命中缓存 |
| `data.meta.tier` | default/critical/complex（开发调试用，UI 可隐藏） |
| `data.meta.tokensIn` / `tokensOut` | tooltip 显示 |
| `data.meta.costUsd` | tooltip 显示 |
| `data.meta.latencyMs` | tooltip 显示 |
| `data.meta.cacheHit` | 派生 "Cached · {age}" UI |

错误响应统一映射：
- 502 `AI_PROVIDER_ERROR` → 红 banner "AI 服务暂时不可用"
- 502 `AI_SCHEMA_ERROR` → 红 banner "AI 输出格式异常"
- 429 `AI_BUDGET_EXCEEDED` → 橙 banner "本月 AI 预算已用完，下月可用"
- 409 `AI_GUARDRAIL_VIOLATION` → 红 banner "AI 输出被拦截 - 数字不匹配"（仅 trade_plan）

---

# Step 7d：data-mapping ↔ DATA-MODEL 一致性验证（Cockpit）

字段名 API 层 camelCase ↔ DATA-MODEL snake_case 一对一映射（Pydantic alias）。

### MarketRegimeSnapshot

| data-mapping 字段 | DATA-MODEL 来源 | 一致性 |
|---|---|---|
| `regime` | `MarketRegimeSnapshot.regime` | ✅ |
| `marketScore` | `MarketRegimeSnapshot.market_score` | ✅（alias） |
| `subscores.spyTrend` | `MarketRegimeSnapshot.spy_trend_score` | ✅ |
| `subscores.qqqTrend` | `MarketRegimeSnapshot.qqq_trend_score` | ✅ |
| `subscores.iwmBreadth` | `MarketRegimeSnapshot.iwm_breadth_score` | ✅ |
| `subscores.sectorParticipation` | `MarketRegimeSnapshot.sector_participation_score` | ✅ |
| `subscores.riskAppetite` | `MarketRegimeSnapshot.risk_appetite_score` | ✅ |
| `subscores.volatilityStress` | `MarketRegimeSnapshot.volatility_stress_score` | ✅ |
| `allowedExposurePct` | `MarketRegimeSnapshot.allowed_exposure_pct` | ✅ |
| `singleTradeRiskPct` | `MarketRegimeSnapshot.single_trade_risk_pct` | ✅ |
| `preferredSetups` | `MarketRegimeSnapshot.preferred_setups` (JSON) | ✅ |
| `avoidSetups` | `MarketRegimeSnapshot.avoid_setups` (JSON) | ✅ |
| `date` | `MarketRegimeSnapshot.date` | ✅ |
| `computedAt` | `MarketRegimeSnapshot.computed_at` | ✅ |

### MarketIndex（17 symbol 扩展）

| data-mapping 字段 | DATA-MODEL 来源 | 一致性 |
|---|---|---|
| `indices[].symbol` / `sectors[].symbol` | `MarketIndex.symbol` | ✅ |
| `indices[].close` / `sectors[].close` | `MarketIndex.close` | ✅ |
| `indices[].changePct` / `sectors[].changePct` | `MarketIndex.change_pct` | ✅ |
| `indices[].aboveMa50` | `MarketIndex.above_ma50` | ✅ |
| `indices[].aboveMa200` | `MarketIndex.above_ma200` | ✅ |
| `indices[].rsTrend` | `MarketIndex.rs_trend` | ✅ |
| `indices[].state` | API 派生（regime service 中聚合，非列） | ✅（运行时字段，DATA-MODEL 标注 derived） |
| `sectors[].state` | 同上 | ✅ |

### SetupSnapshot

| data-mapping 字段 | DATA-MODEL 来源 | 一致性 |
|---|---|---|
| `ticker` | `SetupSnapshot.ticker` | ✅ |
| `stockName` | 关联 `Stock.name`（API 聚合） | ✅ |
| `setupType` | `SetupSnapshot.setup_type` | ✅ |
| `setupQuality` | `SetupSnapshot.setup_quality` | ✅ |
| `entryPrice` | `SetupSnapshot.entry_price` | ✅ |
| `stopPrice` | `SetupSnapshot.stop_price` | ✅ |
| `target2r` | `SetupSnapshot.target_2r` | ✅ |
| `target3r` | `SetupSnapshot.target_3r` | ✅ |
| `distanceToEntryPct` | `SetupSnapshot.distance_to_entry_pct` | ✅ |
| `rewardRisk` | `SetupSnapshot.reward_risk` | ✅ |
| `rsPercentile` | `SetupSnapshot.rs_percentile` | ✅ |
| `volumeStatus` | `SetupSnapshot.volume_status` | ✅ |
| `trendScore` | `SetupSnapshot.trend_score` | ✅ |
| `earningsRisk` | `SetupSnapshot.earnings_risk` | ✅ |
| `readySignal` | `SetupSnapshot.ready_signal` | ✅ |
| `suggestedAction` | `SetupSnapshot.suggested_action` | ✅ |
| `scanDate` | `SetupSnapshot.scan_date` | ✅ |

### EarningsEvent

| data-mapping 字段 | DATA-MODEL 来源 | 一致性 |
|---|---|---|
| `nextEarningsDate` | `EarningsEvent.earnings_date`（最近一行） | ✅ |
| `daysUntil` | API 派生（today - earnings_date） | ✅（derived） |
| `timeOfDay` | `EarningsEvent.time_of_day` | ✅ |
| `epsEstimate` | `EarningsEvent.eps_estimate` | ✅ |
| `revenueEstimate` | `EarningsEvent.revenue_estimate` | ✅ |

### UserSettings

| data-mapping 字段 | DATA-MODEL 来源 | 一致性 |
|---|---|---|
| `accountSize` | `UserSettings.account_size` | ✅ |
| `maxExposurePct` | `UserSettings.max_exposure_pct` | ✅ |
| `singleTradeRiskPct` | `UserSettings.single_trade_risk_pct` | ✅ |
| `defaultRiskPerTradePct` | `UserSettings.default_risk_per_trade_pct` | ✅ |
| `baseCurrency` | `UserSettings.base_currency` | ✅ |
| `updatedAt` | `UserSettings.updated_at` | ✅ |

### Position

| data-mapping 字段 | DATA-MODEL 来源 | 一致性 |
|---|---|---|
| `id` | `Position.id` | ✅ |
| `ticker` | `Position.ticker` | ✅（D067：无 FK） |
| `entryPrice` | `Position.entry_price` | ✅ |
| `entryDate` | `Position.entry_date` | ✅ |
| `shares` | `Position.shares` | ✅ |
| `stopPrice` | `Position.stop_price` | ✅ |
| `target2r` | `Position.target_2r` | ✅ |
| `target3r` | `Position.target_3r` | ✅ |
| `setupType` | `Position.setup_type` | ✅ |
| `status` | `Position.status` | ✅ |
| `closedAt` | `Position.closed_at` | ✅ |
| `closePrice` | `Position.close_price` | ✅ |
| `notes` | `Position.notes` | ✅ |
| `createdAt` | `Position.created_at` | ✅ |
| `updatedAt` | `Position.updated_at` | ✅ |
| `lastClose` | API 派生（daily_bars 最新或 FMP fallback） | ✅（derived） |
| `rMultiple` | API 派生（(lastClose - entry)/(entry - stop)） | ✅（derived） |
| `unrealizedPl` | API 派生（(lastClose - entry) × shares） | ✅（derived） |
| `positionValue` | API 派生（shares × lastClose） | ✅（derived） |
| `earningsDate` / `daysUntilEarnings` | EarningsEvent 关联派生 | ✅（derived） |
| `nextAction` | API 派生（action_service 规则引擎） | ✅（derived） |

### PendingOrder

| data-mapping 字段 | DATA-MODEL 来源 | 一致性 |
|---|---|---|
| `id` | `PendingOrder.id` | ✅ |
| `ticker` | `PendingOrder.ticker` | ✅（D067：无 FK） |
| `setupType` | `PendingOrder.setup_type` | ✅ |
| `entryPrice` | `PendingOrder.entry_price` | ✅ |
| `stopPrice` | `PendingOrder.stop_price` | ✅ |
| `shares` | `PendingOrder.shares` | ✅ |
| `target2r` | `PendingOrder.target_2r` | ✅ |
| `target3r` | `PendingOrder.target_3r` | ✅ |
| `expirationDate` | `PendingOrder.expiration_date` | ✅ |
| `status` | `PendingOrder.status` | ✅ |
| `notes` | `PendingOrder.notes` | ✅ |
| `createdAt` / `updatedAt` | `PendingOrder.created_at/updated_at` | ✅ |
| `lastClose` / `distanceToTriggerPct` / `riskPct` | API 派生 | ✅（derived） |

### AiMemo（运行时通过 /api/ai/{task_type} 暴露）

| data-mapping 字段 | DATA-MODEL 来源 | 一致性 |
|---|---|---|
| `memoId` | `AiMemo.id` | ✅ |
| `taskType` | `AiMemo.task_type` | ✅ |
| `schemaVersion` | `AiMemo.schema_version` | ✅ |
| `output` | `AiMemo.output_json` | ✅（JSON 解构） |
| `meta.modelUsed` | `AiMemo.model_used` | ✅ |
| `meta.tier` | `AiMemo.tier` | ✅ |
| `meta.tokensIn` | `AiMemo.tokens_in` | ✅ |
| `meta.tokensOut` | `AiMemo.tokens_out` | ✅ |
| `meta.costUsd` | `AiMemo.cost_usd` | ✅ |
| `meta.latencyMs` | `AiMemo.latency_ms` | ✅ |
| `meta.cacheHit` | API 派生（命中已存 memo 时 true） | ✅（derived） |

### 枚举值一致性

| 字段 | data-mapping 取值 | DATA-MODEL 定义 | 一致性 |
|---|---|---|---|
| `regime` | RISK_ON / CONSTRUCTIVE / NEUTRAL / DEFENSIVE / RISK_OFF | `MarketRegimeSnapshot.regime` 枚举 | ✅ |
| `setupType` | BREAKOUT / PULLBACK / RECLAIM / EARNINGS_DRIFT / EXTENDED / BROKEN / NONE | `SetupSnapshot.setup_type` 枚举 | ✅ |
| `setupQuality` | A / B / C / null | `SetupSnapshot.setup_quality` 枚举 | ✅ |
| `volumeStatus` | HIGH / NORMAL / LOW / null | `SetupSnapshot.volume_status` 枚举 | ✅ |
| `earningsRisk` | SAFE / CAUTION / DANGER | `SetupSnapshot.earnings_risk` 枚举 | ✅ |
| `suggestedAction` | enter / watch / wait / reduce / exit / null | `SetupSnapshot.suggested_action` 枚举 | ✅ |
| `position.status` | OPEN / CLOSED | `Position.status` 枚举 | ✅ |
| `pendingOrder.status` | ACTIVE / TRIGGERED / CANCELLED / EXPIRED | `PendingOrder.status` 枚举 | ✅ |
| `nextAction` | hold / raise_stop / reduce / exit | API 派生枚举（与 actions/today actionType 同义） | ✅ |
| `actionType (mustAct)` | raise_stop / cancel_order / reduce_before_earnings / tighten_stop | API 派生（action_service） | ✅ |
| `actionType (monitor)` | approaching_trigger / stable_position | 同上 | ✅ |
| `taskType` | market_narrator / setup_explainer / candidate_ranker / trade_plan / contradiction_detector / news_summarizer / journal_assistant | `AiMemo.task_type` 枚举 | ✅ |
| `tier` | default / critical / complex | `AiMemo.tier` 枚举 | ✅ |
| `timeOfDay` | BMO / AMC / null | `EarningsEvent.time_of_day` 枚举 | ✅ |
| `indices[].state` | Bullish / Leading / Constructive / Neutral / Weak / Defensive | API 派生枚举（regime service） | ✅（contract 文档化即可，非列） |
| `sectors[].state` | Strong / Constructive / Weak / Defensive | 同上 | ✅ |
| `rsTrend` | up / down / flat | `MarketIndex.rs_trend` | ✅ |

### Settings.baseCurrency

`UserSettings.base_currency` MVP 仅 `USD`，无多币种校验逻辑（D066）。

**Step 7d 结论**：✅ Cockpit 全部字段对齐 DATA-MODEL，无命名/枚举差异。运行时派生字段（lastClose / rMultiple / unrealizedPl / nextAction / state / cacheHit / daysUntil 等）已在表中标注 `derived`，DATA-MODEL 不持久化此类字段，由 service 层即算即返。

---

# Step 7e：data-mapping ↔ API-CONTRACT 一致性验证（Cockpit）

| 页面 / Widget | 依赖接口 | API-CONTRACT 状态 |
|---|---|---|
| MarketRegimeWidget | `GET /api/cockpit/regime` | ✅ 已定义 |
| MarketRegimeWidget AI Notes | `POST /api/ai/market_narrator` | ✅ 已定义（统一入口） |
| EarningsWidget | `GET /api/cockpit/earnings?ticker=...` | ✅ 已定义 |
| PoolBuilderWidget | `GET /api/cockpit/pool` | ✅ 已定义 |
| PoolBuilderWidget [+ Add] | `POST /api/watchlist`（既有） | ✅ 已定义（v1.0） |
| CockpitChartWidget | `GET /api/cockpit/chart/{ticker}` | ✅ 已定义 |
| SetupMonitorWidget | `GET /api/cockpit/setup-monitor` | ✅ 已定义 |
| SetupMonitorWidget hover [?] | `POST /api/ai/setup_explainer` | ✅ 已定义（统一入口） |
| DecisionPanelWidget Decision Card | `GET /api/cockpit/decision/{ticker}` | ✅ 已定义 |
| DecisionPanelWidget Override 重算 | `GET /api/cockpit/decision/{ticker}?entryOverride=&stopOverride=&riskPctOverride=` | ✅ 已定义（同一接口 query） |
| DecisionPanelWidget AI Plan | `POST /api/ai/trade_plan` | ✅ 已定义（统一入口） |
| DecisionPanelWidget Contradictions | `POST /api/ai/contradiction_detector` | ✅ 已定义（统一入口） |
| DecisionPanelWidget Save Pending Order | `POST /api/cockpit/pending-orders` | ✅ 已定义 |
| PositionListWidget | `GET /api/cockpit/positions?status=` | ✅ 已定义 |
| PositionListWidget New | `POST /api/cockpit/positions` | ✅ 已定义 |
| PositionListWidget 编辑 | `PATCH /api/cockpit/positions/{id}` | ✅ 已定义 |
| PositionListWidget 删除 | `DELETE /api/cockpit/positions/{id}` | ✅ 已定义 |
| PendingOrdersWidget | `GET /api/cockpit/pending-orders?status=` | ✅ 已定义 |
| PendingOrdersWidget Triggered/Cancel | `PATCH /api/cockpit/pending-orders/{id}` | ✅ 已定义 |
| PendingOrdersWidget New / Delete | `POST /api/cockpit/pending-orders`、`DELETE /api/cockpit/pending-orders/{id}` | ✅ 已定义（CRUD 对称） |
| ActionListWidget | `GET /api/cockpit/actions/today` | ✅ 已定义 |
| UserSettingsDialog | `GET / PUT /api/cockpit/user-settings` | ✅ 已定义 |
| Cockpit AI 通用响应 wrapper | `POST /api/ai/{task_type}` 7 task_type | ✅ 已定义 |

**Step 7e 结论**：✅ Cockpit 全部 widget 数据来源都能在 API-CONTRACT 中找到对应 endpoint，无缺失接口。

---

# Step 7f：tokens.json ↔ DATA-MODEL 枚举对齐核对（Cockpit 扩展）

| DATA-MODEL 枚举 | 期望 token | tokens.json 待加 | 备注 |
|---|---|---|---|
| `MarketRegimeSnapshot.regime = RISK_ON` | `regime-risk-on` | 已规划（→ `var(--color-change-positive)` 别名） | design-spec §"专属新增设计 Token" 表 |
| `MarketRegimeSnapshot.regime = CONSTRUCTIVE` | `regime-constructive` | 已规划 #22c55e | |
| `MarketRegimeSnapshot.regime = NEUTRAL` | `regime-neutral` | 已规划（→ `var(--color-signal-neutral)`） | |
| `MarketRegimeSnapshot.regime = DEFENSIVE` | `regime-defensive` | 已规划（→ `var(--color-log-warn)`） | |
| `MarketRegimeSnapshot.regime = RISK_OFF` | `regime-risk-off` | 已规划（→ `var(--color-change-negative)`） | |
| `SetupSnapshot.setup_quality = A/B/C` | `setup-quality-{a,b,c}` | 已规划 | |
| `SetupSnapshot.setup_type` 7 枚举 | `setup-{breakout,pullback,reclaim,earnings,extended,broken}` | 已规划（NONE 不渲染 Badge，无 token） | |
| `SetupSnapshot.earnings_risk = SAFE/CAUTION/DANGER` | `earnings-{safe,caution,danger}` | 已规划 | |
| `Position.status / PendingOrder.status` | 复用既有 `--color-text-*`（无新增颜色）| 不需新 token | OPEN/CLOSED/ACTIVE 等仅展示文本 |
| `actionType` 三栏背景 | `action-{must,monitor,noaction}-bg` | 已规划 | |
| F203 entry/stop/target/avwap/earnings 横线 | `chart-{entry,stop,target,avwap,earnings}-*` | 已规划 | |

**Step 7f 结论**：✅ Cockpit 新增枚举全部有对应 token 规划；将由 design-bridge 在本次同步阶段写入 `tokens.json` + `tokens.css`。

---

# Cockpit 总验证结果

| 检查项 | 结果 |
|---|---|
| 7d — Cockpit data-mapping ↔ DATA-MODEL 字段对齐 | ✅ PASS |
| 7d — 枚举取值对齐 | ✅ PASS |
| 7e — Cockpit data-mapping ↔ API-CONTRACT 接口覆盖 | ✅ PASS（18 cockpit endpoints + 7 ai task_type 全覆盖） |
| 7f — tokens.json ↔ DATA-MODEL 新枚举色彩对齐 | ✅ PASS（待 tokens.json/css 同步落地） |

F200–F211 共 12 个 feature 的数据绑定基础已验证完整。phase 维持 `design_ready`（features.json 用），UI 设计阶段完成（`_pipeline_status.ui_design = done`）。
