# Changelog

所有版本变更记录在此文件。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

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
