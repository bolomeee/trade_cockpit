# Changelog

所有版本变更记录在此文件。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

---

## [v2.4.0] - 2026-05-20

### ✨ 新增
- **Repricing Trigger 完整框架（5 类）**：新增 cockpit Phase D，独立识别让市场重新定价的基本面/产业/资产负债端事件，与 Phase C Capitulation 信号解耦
  - T1 Earnings Acceleration：复用 EarningsEventRepository，连续 3 季 EPS YoY 严格单调递增触发，confidence 按末季 yoy ≥ 30% 分 0.8/0.5
  - T2 Margin Expansion：FMP `/income-statement` 接入，新建 `stock_key_metrics_quarterly` 表（alembic 023），gross/FCF margin 连续扩张 ≥ 200/300bp 触发
  - T3 New Product（关键词扫描）：扫描 `news_cache` 过去 30 日 headlines，命中 7 关键词集合 ≥ 2 次触发，evidence 含 keyword_hits/news_links
  - T4 Sector Cycle Reversal：复用 `SECTOR_ETFS` 与 `compute_rs_percentile_map`，sector ETF RS percentile 60 日内从 <40 升至 >60 且 close > SMA200 触发
  - T5 Balance Sheet Inflection：FMP `balance-sheet + cash-flow` 接入（T2/T5 共享），新建 `stock_fundamentals_quarterly` 表（alembic 024），净负债连续环比 ↓5% 或 FCF 负转正 2 季触发
- **定时刷新 cron**：`refresh_job.py` 新增 `REPRICING_TRIGGER_JOB_ID`，每周一至五 22:40 UTC 调度 `RepricingTriggerService.compute_and_store_all_triggers`
- **2 个新 REST 端点**：
  - `GET /api/cockpit/repricing-triggers/{ticker}` — 单标的 active triggers，按 detected_date 倒序
  - `GET /api/cockpit/repricing-triggers/{ticker}` — 全市场 active triggers，支持 `triggerType` 过滤 + `limit` 上限
- **RepricingTriggerWidget**：Cockpit 新 widget（x:6 y:43），表格列出全市场 active triggers，支持 5 类 filter + 行点击联动 chart widget
- **DecisionPanel chip 区**：持仓 ticker 有 active trigger 时，header 下方显示 5 类彩色 chip（hover 展示 evidence 单行概要）；无 trigger 时不占空间
- **5 类 trigger 色板**：`tokens.css` 新增 `--color-trigger-{earnings-accel/margin-expansion/new-product/sector-cycle/balance-inflection}`

### 📐 技术
- `repricing_triggers` 表（alembic 022）：UQ(ticker, trigger_type, detected_date)，soft expire 机制
- `stock_key_metrics_quarterly` 表（alembic 023）：gross/op/net/FCF margin + roic（近似公式）
- `stock_fundamentals_quarterly` 表（alembic 024）：net_debt / FCF 等资产负债指标，与 key_metrics 共享 null-not-erase upsert 模式
- FMP quota 优化：T2/T5 共享 cash-flow 接入，由 4 endpoint 收敛至 3（D097 修正）
- pool_cache rebuild 末尾追加 `_rebuild_key_metrics` + `_rebuild_fundamentals` 步骤

---

## [v2.3.0] - 2026-05-18

### ✨ 新增
- **F217 Capitulation Reversal（投降式抛售反转）— Cockpit Phase C 严格重写**
  - **判定引擎**：`_is_capitulation_reversal` 实现 7 条 AND 门严格判定（5-10日累计跌幅≥10% / Vol z-score≥2.5 / true_range≥2×ATR14 / 收盘位于当日上1/3 / 次日不创新低 / swing low 确认 / RS line 过去5日未新低）；触发频率极稀疏（每月数只），符合 SRS § 五 Setup 4 语义
  - **前端 badge**：SetupMonitorWidget 紫色 `CAP_REV` badge（`--color-setup-capitulation: #8b5cf6`）
  - **决策证据**：DecisionPanelWidget 在 CAPITULATION 标的展示 3 个关键 chip（Vol z-score / Drop 5d / Reversal day）
  - **Pending Order**：表单 setup_type 下拉新增 `CAP_REV` 选项

### 🔨 重构 / 清理
- 移除 PULLBACK setup type：backend Pydantic schemas Literal 收紧、frontend `SetupType` union 删除、`tokens.css` 旧色标退场（`--color-setup-pullback` 删除）
- `setup_snapshots` 表新增 `legacy` 列，存量 PULLBACK 行软删除保留审计记录（alembic 021）
- setup_type 分类优先级更新：CAPITULATION 高于 BREAKOUT/RECLAIM（语义互斥）
- `design-spec.md` 同步最终态（setup color 表 / ASCII mockup / popover 偏离说明 / v2.2.0 偏离记录）

---

## [v2.2.0] - 2026-05-15

### ✨ 新增
- **F216 Weekly Stage Layer（Stan Weinstein Stage 1-4 周线分层，8 个子 sprint 全部交付）**
  - **数据层**：WeeklyChartService 从本地 daily_bars 聚合 ISO 周线（OHLCV + Weekly MA 10/30/40），零 FMP 调用；weekly_stage_snapshots 表存储每日快照
  - **分类引擎**：WeeklyStageService 按 SRS 规则分类 Stage 1–4（Stage 2 = close > 30wMA AND slope_30w > 0 AND ma10w > 30wMA），使用 numpy OLS 斜率计算
  - **前端 Widget**：WeeklyStageChartWidget 渲染周线 K 线 + 三条 MA + 颜色编码 Stage 标签（绿=Stage 2 / 黄=Stage 1/3 / 红=Stage 4），复用 lightweight-charts
  - **Setup 门禁**：setup_snapshots 新增 weekly_stage 列；`_evaluate_ready_signal` 强制 Stage 2 作为第 8 条 AND 门（ready_signal=True 标的预计减少 30–50%，为设计意图）
  - **SetupMonitorWidget WS 列**：setup 列表新增 WS 列展示 Stage 数值，令 ready=False 的原因对用户可见
  - **Scheduler Cron**：refresh_job 新增 22:20 UTC mon–fri job（`cockpit_weekly_stage_refresh`），保持 regime→weekly_stage→setup 的时间顺序

---

## [v2.1.0] - 2026-05-07

> ⚠️ consistency-check 违例覆盖：C5 违例 45 项均为 F001～F113 时代历史遗留合约文件，features.json 尚无对应 sub_sprints entry，功能本身均已完成，与本次发版无关。

### ✨ 新增
- **F213 新闻文章自动翻译（DeepSeek）**：打开 ArticleModal 时自动调用 `/api/ai/translate_article`，标题与正文替换为中文译文；loading 状态显示原文 + 进度指示；重复打开同一篇文章命中 ai_memos 缓存；翻译失败时回退显示原文 + toast 错误提示
- **F212 布局云存储**：TopNav 新增保存/恢复布局按钮，布局持久化至后端 `layouts` 表；支持跨 session 恢复 Workbench widget 位置与大小
- Regime Widget：新增 VXX 指数 ETF；点击指数行 / 行业 Cell → Cockpit Chart 联动展示对应标的
- Admin：新增 `POST /api/admin/refresh-universe` 手动触发端点
- 新闻摘要 Bar 新增 Refresh 按钮（bypass no-cache）

### 🐛 修复
- 修复 AI Gateway 未将 system_prompt 传入 LLM 的严重 bug（所有 AI 功能均受益）
- 修复 DeepSeek Flash 不支持 `json_schema` response_format，改用 `json_mode + 二次 Pydantic 验证`
- Pool：`revenue_growth_yoy` 为 null 时由 fail-closed 改回 fail-open（ETF 通过率修复）
- Pool：市值门槛从 50B → 10B（分两步调整）

### 💄 样式
- Workbench：MA 图例内联行、字号微调、ticker/公司名基线对齐、价格图默认 6 个月视图
- AI 全部任务的 SYSTEM_PROMPT 强制要求中文输出
- 行业热力图显示中文行业标签

---

## [v2.0.0] - 2026-04-29

> ⚠️ consistency-check 违例覆盖：部分早期 feature 修正未纳入 feature-dev 流程，C2/C5 违例均为历史遗留 artifact（旧 status 值 "completed"、已重组的 feature ID），不影响当前功能完整性。

### ✨ 新增
- **F211 AI Layer（6 个子 sprint 全部交付）**
  - AI Contradiction Detector：Decision Panel 新增矛盾检测区，单击生成 severity badge + recommendation
  - AI News Summarizer：News 页新增 AI 摘要 Bar，单击触发对当日新闻的 AI 汇总
  - AI Journal Assistant：平仓后自动触发后台 journal review（BackgroundTask 写入 ai_review 字段）
  - 月度复盘 cron：APScheduler 月度 job，自动聚合上月交易发起 AI 复盘；0 笔交易月份跳过

### 🏗️ 基础设施
- AI task type schema（contradiction_detector / news_summarizer / journal_assistant）+ tier 路由（contradiction_detector → default，journal_assistant → complex）
- Playwright E2E 冒烟探针框架（8 探针，Vite 模块注入 + Zustand setState）

---

## [v1.10.0] - 2026-04-28

### ✨ 新增
- **F205 Pool Builder Widget**：5 个子 sprint 全部交付（universe 字段扩展 / FMP financial-growth / pool service + API / 前端 widget / 周级 cache）
- F205-e Pool Cache：RS percentile 与 fundamental revenue growth 改为周级预算（每周一 06:30 UTC cron），写入 `cockpit_pool_cache`，filter 重请求 < 500ms 不再打 FMP
- F204-b / F202-c：Admin 手动触发端点 `POST /api/admin/refresh-earnings` 与 `POST /api/admin/refresh-setup`
- AiCandidateRanker 区域增加 setup scan 刷新按钮
- PoolFilterBar：MktCap/ADV 输入改为 B/M 单位显示，Sector 改为下拉选择

### 🐛 修复
- F204-a：earnings batch 按 (ticker, earnings_date) 去重
- F105：FMP screener 分页直至最后一页
- F205-e：`_load_trend_tickers` 去重
- 多个 Cockpit widget 移除冗余 header 标题，统一视觉

---

## [v1.9.0] - 2026-04-27

### ✨ 新增
- **Positions Widget**：持仓管理全栈（Position CRUD / Risk Summary / PositionListWidget + PositionFormDialog）（F206-a / F206-c1）
- **Pending Orders Widget**：挂单管理全栈（PendingOrder CRUD / 到期自动清理 / PendingOrdersWidget + PendingOrderFormDialog）（F206-b1 / F206-b2 / F206-c2）
- **Today's Actions Widget**：动作清单 widget，deterministic rule engine，按 Must Act / Monitor / No Action 三栏分类，含 6 种 actionType 规则（F207）
- 后端：Migration 013–014，新增 `positions` / `pending_orders` 表；APScheduler nightly job（挂单到期清理 + regime 快照）
- 后端：`GET /api/cockpit/actions/today` endpoint，返回 `mustAct / monitor / noAction` 三数组，每条含 ticker / actionType / rationale / refs

---

## [v1.8.0] - 2026-04-26

### ✨ 新增
- AI 基础设施：ai_memos 数据表 + LiteLLM 路由层 + AI Gateway 统一接入（/api/ai/{task_type}）(F208)
- MarketRegimeWidget：Score Hero / Subscores / Indices / SectorHeatmap 四区块（F201-c）
- AI Market Notes：MarketRegimeWidget 新增 AI 市场叙述区块，支持刷新与缓存（F209-b）
- AI Setup Explainer：SetupMonitor 每行新增 `?` 弹出 AI 解读 Popover（F209-c）
- DecisionPanel AI Trade Plan + Guardrail Banner：AI 生成交易计划 + 护栏校验（F210-c）

### 🎨 优化
- Cockpit TopNav action buttons 统一为 shadcn Button 组件
- SetupMonitor tabs 紧凑化、标题行合并、字体统一
- CockpitChart 轴标签样式精简

### 🐛 修复
- SetupMonitor sticky header 背景透明度异常
- DecisionPanel trade_plan 接受 earningsRisk=null
- News 缓存永远过期 bug

---

## [v1.7.0] - 2026-04-23

### ✨ 新增
- News 后端缓存：新增 `news_articles_cache` 表，按自然日存储文章，支持增量翻页（FMP 上限5页）（F113-a）
- News 前端持久化：文章存 localStorage（5日滚动窗口），跨刷新免重拉，旧条目自动修剪（F113-b）
- News 增量刷新：Refresh 按钮调 `?since=<最新 publishedAt>`，仅拉新文章并合并到列表顶部（F113-b）
- News 已读状态：点开文章后列表行视觉变淡（opacity-50），跨刷新永久保留（F113-c）
- News 表格行距和字号对齐 Watchlist（11px / py-[3px]）

### 🛠 改进
- `GET /api/news/articles` 支持 `since`、`window`、`limit` 参数；响应新增 `meta`（cache_hit / fmp_calls / truncated / fmp_error）
- FMP 失败但缓存有数据时降级返回缓存 + `meta.fmp_error=true`，不中断用户浏览

---

## [v1.6.0] - 2026-04-23

### ✨ 新增
- News 页：TopNav 增 News 入口，独立 `/news` 路由，react-grid-layout 容器，布局持久化独立于 Workbench（F112-b1）
- NewsTable widget：Date / Title / Tickers 列，点行开 ArticleModal，点 ticker badge 直接切 Price Chart
- ArticleModal：50% 透明遮罩 + 圆形关闭按钮 + DOMPurify sanitize 防 XSS + Escape 关闭（F112-b2）
- News 页复用 ChartWidget、FundamentalsWidget —— ticker 点击通过 `useAppStore.selectedSymbol` 全局联动
- WidgetRegistry 支持按 category 分派，`getWorkbenchDefaultLayout` / `getNewsDefaultLayout` 独立管理不同页布局

### 🔧 变更
- Workbench 首页移除 NewsWidget（迁至 /news 页）
- NewsWidget 由卡片列表重写为 table-fixed 布局

### 📦 依赖
- 新增 `dompurify@3.4.1`（types 自带）

---

## [v1.5.1] - 2026-04-22

### 🐛 修复
- 强化 FMP 429 限流重试策略：指数退避（1s/2s/4s，上限 8s）+ 最多 3 次重试，支持 Retry-After 响应头，解决 scanner 偶发 ticker 扫描失败

---

## [v1.5.0] - 2026-04-22

### ✨ 新增
- 同日 ticker 数据缓存（F111-a）：watchlist 和 breakout list 点击过的 ticker，当日内 chart 和 fundamentals 不再重复请求 FMP，第二次响应速度由 ~500ms 降至 ~5ms

### 🐛 修复
- 修复点击 ETF ticker（如 IVW）时 Fundamentals 面板因 FCF 为 null 导致页面崩溃的问题
- 修复 ETF chart 数据中重复日期导致 lightweight-charts 抛错的问题；新增 Error Boundary 防止图表异常白屏

---

## [v1.4.0] - 2026-04-22

### ✨ 新增
- Watchlist 支持 CSV 批量导入（文件上传 / 文本粘贴，自动去重分桶展示结果）
- Watchlist 支持 CSV 导出（一键下载当日 watchlist）
- `/fundamentals` 与 `/pullbacks` 放开到任意 ticker，Scanner 中点击非自选股不再报 404

### 🎨 优化
- 所有 widget title bar 底色统一（`#ebf2fa`），内容区边距收紧
- TopNav 品牌字「MA150 Tracker」支持点击回首页
- ResetLayoutButton 移至 TopNav 右侧，路由条件渲染（仅首页可见）
- 搜索框（AddStockCard）改为 pill 形、10px 粗体样式

---

## [v1.3.0] - 2026-04-22

ChartWidget 叠加层（volume / MA5 / MA20 / Vol/Float 气泡）+ Fundamentals Float 绝对值 + 多信号扫描器分类 Tabs。

### ✨ 新增
- **多信号扫描器 (F106-a/b/c)**：扫描器扩展为多类信号探测器，schema 增 `signal_type`；`/api/market/breakouts` 支持 `?type=` 过滤；MarketBreakoutWidget 改 shadcn Tabs 分栏 stage / pullback；FMP screener 增 `is_fund` 过滤剔除基金
- **图表叠加层 (F107)**：ChartWidget 增 volume 柱状图 + MA5 / MA20 双均线叠加（与既有 MA150 共存）
- **shares_float 后端数据链路 (F107-b1)**：stocks 表新增 `shares_float` / `shares_float_refreshed_at`（24h TTL DB 缓存，D050）；FMP `/stable/shares-float` 双字段兼容（D051）；`/chart` 响应顶层带 `sharesFloat`
- **Vol/Float 比率气泡 (F107-b2)**：ChartWidget volume 柱上方浮动气泡显示当日 Vol/Float 比率，hover 图例联动；历史 bar 统一用当前快照 float（D052，标注"近似"）
- **Fundamentals Float 行 (F107-b3)**：FundamentalsCard 右列末位新增 Float 绝对值（单位 15.23B / 987.65M）；`/fundamentals` 响应增 `sharesFloat`，复用 F107-b1 缓存路径（D054）

---

## [v1.2.0] - 2026-04-21

Market Breakout Scanner — Workbench 新增 scanner 类别，每日盘后扫描全美大市值股票池的 MA150 穿越候选；配套 FMP 并发调度重构。

### ✨ 新增
- **突破扫描数据层 (F105-a1/a2/a3)**：新表 `market_scan_universe` / `market_breakout_scans` + FMP `/company-screener` 三交易所合并去重 + SMA/EOD 双路径拉取 + 每月 1 号 05:00 universe 刷新 cron + 工作日 06:15 独立 scanner cron（D038/D039/D040/D042）
- **GET /api/market/breakouts (F105-a4)**：返回当日最新 scan 快照，按 `pct_above_ma150` 升序，空态返回 `scanDate=null`
- **Chart on-demand fallback (F105-b)**：`/api/stocks/:ticker/chart` 对非 watchlist 或 inactive ticker 临时拉 FMP 400 天 EOD 并本地算 MA150，不入库（D041）
- **MarketBreakoutWidget (F105-c)**：Workbench 新增 `scanner` 类别 widget，展示 Ticker / Company / Close / % Above MA150 + 一键加 watchlist 按钮；行点击联动 ChartWidget
- **FMP 共享限流器 + Scanner 并发 (F105-a5)**：`_FmpRateLimiter` 提升为进程级单例（token bucket + `Semaphore(6)`），所有 `FmpClient` 实例共享；Scanner 改 `ThreadPoolExecutor(6)` 并发扫描；OK 日志追加 `duration_s` / `workers`（D044）

### 🐛 修复
- **dev proxy 端口冲突**：stock_portal-backend 容器改为发布到宿主 `:8001`，避免与本机其他 `:8000` 服务冲突；Vite proxy 同步

### 📖 决策
- **D038** universe 每月刷新独立 cron；**D039** SMA → EOD 透明 fallback；**D040** 全部失败时保留旧 snapshot；**D041** chart on-demand fallback 不入库；**D042** scanner 独立 cron（watchlist refresh 后 15 分钟）；**D043** widget-only feature 跳过 design-bridge；**D044** FMP 限流器进程级共享 + 6 并发

---

## [v1.1.1] - 2026-04-19

FMP 接入 — 从 Polygon 切换到 Financial Modeling Prep 作为主数据源；fundamentals 首次对接真实财务数据。

### ✨ 新增
- **FMP 客户端 (F104-S1)**：`/stable/` 全量端点封装 + token bucket (300 req/min, burst 50) + 429 一次重试 + 显式 httpx transport 注入便于测试
- **FMP 真值冒烟测试 (F104-S2c)**：`tests/test_fmp_live_smoke.py` + pytest `live` marker，覆盖真实 FMP 返回结构的形状断言
- **Fundamentals 真实接入 (F104-S3)**：P/E · P/S · PEG · ROCE · FCF Yield · marketCap 接入 FMP `ratios-ttm` + `key-metrics-ttm`，取代 F101 mock

### ♻️ 重构
- **数据源整体迁移 (F104-S2)**：所有 services / routers / tests 从 Polygon 切换到 FmpClient；polygon_client 保留作为 rollback anchor（标注 DEPRECATED）

### 📖 决策
- **D034** 主数据源 Polygon → FMP（功能覆盖更广 + 单一 API 配额更清晰）
- **D035** FMP 为主、Polygon 作为紧急回滚；**D036** fundamentals 字段映射（ROCE 从 `returnOnCapitalEmployedTTM` 取）

---

## [v1.1.0] - 2026-04-19

Workbench 重构 — 从单页 Dashboard 演进为可拖拽 widget 工作台。

### ✨ 新增
- **Workbench 框架 (F100)**：`react-grid-layout` 单页多 widget + `WidgetShell` 统一外壳 + `WidgetRegistry` manifest 注册 + `useLayoutStore` 持久化布局（localStorage key `ma150.workbench.layouts.v5`）+ Reset Layout
- **SMA150 widget 迁移 (F101)**：Chart / Fundamentals / PullbackHistory / Watchlist / QuickAdd 五个 widget 默认加载；Watchlist 点击联动 Chart / Fundamentals / Pullback
- **Fundamentals 2 列布局**：shadcn `Table` 双列（P/E · P/S · PEG / ROCE · FCF）+ ROCE mock 占位（真实算法延至 F103）
- **ChartWidget 标题 overlay**：图表左上角 overlay ticker + 公司名（`pointer-events: none`，零额外 API）
- **AddStock 实时搜索**：200ms debounce + Polygon ticker 前缀匹配 + 公司名 fallback

### ♻️ 重构
- **路由切换 (F102)**：`/` 由 Dashboard 改为 Workbench；删除 `pages/Dashboard.tsx` / `StockDetailModal` / `StockDetailHeader` / `SignalBoard` / `SignalCard`
- **widget 去重复包装**：各 widget 去掉内部 card 外壳和重复标题，统一由 `WidgetShell` 承担
- **Watchlist**：卡片网格 → shadcn `Table`（Ticker · Name · Signal · Close · % MA150 · 删除）
- **code-split**：`Workbench` / `Journal` / `Logs` 改 `React.lazy`，initial bundle 降至 234KB（gzip 75KB）

### 🐛 修复
- **Polygon 搜索**：`search=O` 返回 A 开头 ETF 的排序问题，改 `ticker_gte/ticker_lt` 前缀匹配 + `search=` fallback

### 📖 决策
- **D032** Fundamentals 维持 mock；ROCE 延至 F103 真实财报接入
- **D033** 非 watchlist ticker 的 chart preview 延至首个"含外部 ticker 的 widget"立项时设计

---

## [v1.0.0] - 2026-04-18

MA150 Tracker MVP 首次发版 — 围绕 150 日均线的个人美股交易辅助工具。

### ✨ 新增
- **自选股管理 (F001)**：watchlist 增删查 + Polygon 股票搜索 + 软删除恢复
- **150 日均线信号引擎 (F002)**：BREAKOUT / BUY_ZONE / NEUTRAL / INSUFFICIENT 四态识别 + 20 日线性回归斜率 + 回踩检测与后续 10/20/30 日涨幅
- **数据刷新与调度 (F003)**：手动 refresh + APScheduler 工作日 21:30 UTC 自动刷新 + 新股自动 backfill 250 天 + 大盘指数同步刷新
- **Dashboard SignalBoard (F004)**：按信号优先级排序展示 watchlist，点击打开个股详情
- **个股详情 Modal (F005)**：StockDetailHeader + PullbackHistoryCard + FundamentalsCard + lightweight-charts 价格图 (Candle + MA150 + Pullback marker)
- **大盘概览 Bar (F006)**：S&P 500 / NASDAQ 100 / 10Y Treasury 全局共享
- **交易日志 (F007)**：`/journal` CRUD 页面 + RHF + zod 表单 Dialog + Dashboard 快速添加卡片（3 字段）
- **系统日志 (F008)**：`/logs` 页面，5 级别 toggle 过滤（ALL/OK/INFO/WARN/ERROR），4 色 Badge
- **基础设施 (F000)**：FastAPI + SQLAlchemy 2.0 + Alembic 后端 / React 19 + Vite 8 + Tailwind v4 + shadcn/ui 前端 / Docker Compose 本地部署 / Polygon (Massive) Python client 封装

### 🧪 质量
- 后端 pytest 162/162 全绿
- 前端 pnpm build 零 TS 错误

---
