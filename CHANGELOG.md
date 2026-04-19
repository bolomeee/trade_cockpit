# Changelog

所有版本变更记录在此文件。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

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
