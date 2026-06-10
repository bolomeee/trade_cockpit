# PRD：MA150 Tracker → Workbench

> 版本：v1.1（2026-04-18，Workbench 重构） / v1.0（2026-04-16，历史）
> 以下 v1.1 内容为当前 vision，替代 v1.0 中"固定三页 app"的设定。v1.0 章节保留作为首批 widget 的功能基线参考。

---

## v1.1 · Workbench 愿景（当前）

### 一句话描述

个人投资 **Workbench**：一个可拖拽 widget 的单页面工作台，首批 widget 提供 SMA150 信号 / 走势 / 基本面 / 交易日志 / 系统日志，未来按相同模式扩展全市场扫描、PDF/OCR、AI 观点等。

### 核心设计原则

1. **单一页面**：所有功能 widget 都渲染在同一个 Workbench 网格里，不再有"切到 /journal 页"的概念
2. **可拖拽 + resize**：用户自主决定每个 widget 在屏幕上的位置和大小，布局存本地（localStorage）
3. **加新功能 = 加一个 widget + 一个后端 endpoint + 注册一行**：不动布局、不影响现有功能
4. **个人单用户**：简单优先，不上多 dashboard 切换、用户系统、云端同步；布局不进数据库

### Widget 类别规划（v1.1 首批 + 未来）

| 类别 | v1.1 首批 widget | 未来扩展 widget |
|------|----------------|----------------|
| sma150 | Watchlist / Chart / Fundamentals / Pullback / QuickAdd | — |
| journal | Journal | — |
| logs | Logs | — |
| market | MarketOverview | — |
| scanner（未来） | — | 全市场 150MA 回踩扫描 |
| news（未来） | — | 个股新闻流 / 行业热度 |
| research（未来） | — | PDF/OCR 研报解析、AI thesis |

### 与 v1.0 的关系

v1.0.0 的全部功能作为"首批 widget"完整保留：
- `Dashboard` → 拆解为 `WatchlistWidget` / `QuickAddWidget` / `JournalQuickAddWidget` + 若干独立 widget
- `StockDetailModal` → 拆解为 `ChartWidget` / `FundamentalsWidget` / `PullbackWidget` 3 个独立 widget（D031）
- `/journal` 页 → `JournalWidget`
- `/logs` 页 → `LogsWidget`

后端零改动：所有现有 API 继续工作，加新 widget 时按既有分层新增 router。

### 新增用户旅程（v1.1）

**旅程 D：自定义工作台**
1. 首次打开 Workbench，看到默认布局（5–7 个 widget 铺满屏幕）
2. 拖动某 widget 到新位置 / 改大小 → 自动保存到 localStorage
3. 刷新浏览器 → 布局保留
4. "重置布局"按钮 → 清 localStorage → 回到默认

**旅程 E：并排对比多只股票（v1.0 做不到）**
1. 在 WatchlistWidget 点 AAPL → ChartWidget + FundamentalsWidget + PullbackWidget 同步拉 AAPL
2. 需要对比 MSFT 时：再加一组 chart/fundamentals/pullback widget（未来 v1.2 考虑；v1.1 先支持单 ticker 联动）

### v1.1 明确不做

- ❌ widget 布局进数据库（localStorage 足够）
- ❌ 多 dashboard 预设切换
- ❌ `/api/widgets` 或 widget marketplace（前端静态 registry）
- ❌ micro-frontend / iframe / Module Federation
- ❌ widget 间复杂消息总线（zustand 全局 store 已覆盖所有联动需求）

---

## v1.0 · MA150 Tracker 原始需求（历史，功能基线）

> 以下内容为 v1.0.0 发布时的完整需求，作为首批 widget 的功能验收基线保留。

### 1. 一句话描述

个人美股投资辅助 web app，围绕 150 日均线自动识别回踩买点和均线突破信号，让交易机会主动来找用户。

---

## 2. 目标用户 + 使用场景 + 核心痛点

**目标用户**：个人美股正股 & ETF 投资者，节奏慢、不做快速交易，每天收盘后看一次信号决定是否行动。

**使用场景**：
- 美股收盘后（北京时间早上），打开浏览器或手机查看信号总览
- 发现某只股票出现 BUY_ZONE 或 BREAKOUT 信号，点进详情查看均线斜率、历史回踩质量、基本面数据
- 查看大盘环境（标普、纳指、美债利率）判断是否适合操作
- 记录交易决策和理由到 Journal

**核心痛点**：
- 手动在 TradingView 逐只检查，没有统一的信号汇总视图
- 容易错过回踩窗口（信号转瞬即逝，第二天才发现已经涨回去了）
- 没有历史回踩质量记录，无法判断"这次回踩和以前比如何"
- 交易决策分散在各处，缺乏结构化的交易日志

---

## 3. MVP 功能范围

### ✅ 包含
- **Watchlist 管理**：增删自选股，搜索添加
- **150MA 信号引擎**：3 种信号（BUY_ZONE / BREAKOUT / NEUTRAL），仅在均线斜率为正时产生买入信号
- **每日 EOD 自动调度 + 手动刷新**：基于 Polygon.io 免费 tier
- **信号总览（SignalBoard）**：一目了然所有自选股的当前信号状态
- **个股 150MA 详情 Modal**：点击 SignalBoard 卡片弹出 Modal，K线图表（显示价格和150MA均线），均线斜率、价距百分比、历史回踩记录、基本面数据（PE/PS/PEG/FCF）
- **大盘概览**：标普500、纳斯达克、美债利率（10Y）
- **交易日志（Journal）**：记录交易决策、理由、结果；Dashboard 右侧提供完整表单快捷入口
- **系统日志页面**：独立页面展示系统运行日志，按级别过滤
- **局域网部署**：Docker Compose 一键启动，电脑 + 手机响应式

### ❌ 不包含（后续迭代）
- 实时行情（MVP 仅支持 EOD 数据）
- 回测 / 模拟交易
- 全市场扫描（扫描所有美股找回踩机会）
- Opportunity Radar 图
- 用户认证/多用户
- 推送通知（邮件/微信等）
- 多 watchlist 分组（MVP 为单一 watchlist，但架构预留扩展空间）

---

## 4. 核心用户旅程

### 旅程 A：每日信号检查（主要旅程）
1. 用户打开 MA150 Tracker 首页
2. 看到 **大盘概览 Widget**（标普/纳指涨跌、美债利率）
3. 看到 **SignalBoard**：所有自选股按信号类型排列，BREAKOUT / BUY_ZONE 等买入信号排在最前
4. 发现某只股票出现 BUY_ZONE 信号，点击卡片弹出个股详情 Modal（纯前端弹窗，不改变 URL）
5. 在 Modal 中查看：K线图表包括当前价格 vs 150MA、价距%、均线斜率（上升/走平/下降）、历史回踩记录（时间、价距、后续涨幅）
6. 查看基本面数据（PE/PS/PEG/FCF）辅助判断
7. 关闭 Modal，在 Dashboard 右侧的 Trade Journal Widget 中填写完整交易记录

### 旅程 B：管理自选股
1. 用户在 Dashboard 右侧的 Add Stock 表单中输入股票代码（首次使用时，watchlist 为空，首页显示引导提示"添加你的第一只股票"）
2. 输入股票代码或名称（与美股同步）搜索；若搜索无结果则弹出 Alert 提示"未找到匹配的股票"
3. 从搜索结果中选择，添加到 watchlist
4. 系统自动拉取该股票过去 250 个交易日的历史日线数据并计算 150MA 信号；若数据不足 150 个交易日（如新上市股票），仍添加到 watchlist，信号显示"数据不足"
5. 该股票出现在 SignalBoard 中

### 旅程 C：数据刷新
1. 用户觉得数据不是最新的，点击"手动刷新"按钮
2. 系统调用 Polygon.io API 拉取最新 EOD 数据
3. 重新计算所有自选股的 150MA 信号
4. SignalBoard 更新为最新状态

---

## 5. 页面清单

| 页面名 | 路由 | 主要功能 | 需要登录 |
|--------|------|---------|---------|
| 首页 / Dashboard | `/` | 大盘概览 + SignalBoard 信号总览 + Add Stock 快捷表单 + Trade Journal 完整表单 | 否 |
| 个股详情 | 无独立路由（Modal） | 150MA 详情、K线图、历史回踩、基本面（点击 SignalBoard 卡片弹出） | 否 |
| 交易日志 | `/journal` | 查看/新增/编辑/过滤交易记录 | 否 |
| 系统日志 | `/logs` | 查看系统日志，按级别过滤（ALL/OK/INFO/WARN/ERROR） | 否 |

---

## 6. 数据实体说明

系统中有以下核心"东西"：

- **股票（Stock）**：代码（ticker）、名称、所属交易所。用户通过 watchlist 管理关注哪些股票。
- **日线数据（DailyBar）**：每只股票过去 250 个交易日的 OHLCV（开高低收量）数据，从 Polygon.io 拉取。首次添加股票时下载 250 天基线数据，之后每日增量更新（添加最新交易日、删除最早交易日，始终保持 250 天窗口）。
- **150MA 信号（Signal）**：基于日线数据计算出的信号，包含信号类型（BUY_ZONE / BREAKOUT / NEUTRAL）、价距百分比、均线斜率、均线值等。每只股票每天一个信号。仅当均线斜率为正时才产生 BUY_ZONE 或 BREAKOUT 信号。
- **回踩记录（Pullback）**：在K线图上标识历史上价格回落触及 150MA 附近的事件，并显示包括触及日期、价距、后续 10/20/30 日涨幅等，用于评估回踩质量。
- **大盘指标（MarketIndex）**：标普500、纳斯达克、10年期美债利率的每日数据。数据来源：SPX/NDX 通过 Polygon.io Indices API，美债利率通过 Polygon.io Economy API（Treasury Yields）。
- **系统日志（SystemLog）**：系统运行日志，记录数据同步、信号计算、调度等操作的结果。级别：OK（成功）/ INFO（信息）/ WARN（警告）/ ERROR（错误）。保留最近 7 天。
- **交易日志（Journal Entry）**：用户的交易决策记录，关联到某只股票，包含操作类型（买/卖/加仓/减仓/观望）、价格、日期、仓位大小（数字输入，加仓/减仓时在当前仓位基础上调整）、止损位、目标价、买入原因、参考内容（大文本）。

**关系**：
- 一只 Stock 有多条 DailyBar（一对多）
- 一只 Stock 每天产生一个 Signal（一对多）
- 一只 Stock 有多条 Pullback 历史（一对多）
- 一条 Journal Entry 关联一只 Stock（多对一）

---

## 7. 非功能要求

- **性能**：首页加载 < 3s（局域网环境）；手动刷新 30 只股票数据 < 60s
- **兼容性**：Chrome/Safari 最新版；移动端 Safari/Chrome 响应式布局
- **数据限制**：Polygon.io “Stocks Basic” API调用5次/分钟，调度和刷新需做好 rate limiting
- **部署**：Docker Compose 一键启动，不依赖外部数据库服务（使用 SQLite）
- **安全**：仅局域网使用，无需用户认证；Polygon.io API Key 通过环境变量配置

---

## 8. 已确认问题

1. **信号定义**（已确认）：系统输出 3 种信号类型，均以收盘价和 150MA 的关系判定：
   - **BUY_ZONE**：均线斜率为正（定义见第 5 条），且收盘价在 150MA 上方 0–5% 以内（含等于 MA）。价距% = (close - MA150) / MA150 × 100%。
   - **BREAKOUT**：均线斜率为正，且收盘价从前一交易日低于 150MA 变为当日高于或等于 150MA（向上穿越）。
   - **NEUTRAL**：不满足以上条件（包括斜率为负、价格远离 MA、价格在 MA 下方等所有情况）。
   - 当同一天同时满足 BUY_ZONE 和 BREAKOUT 条件时，取 BREAKOUT（穿越事件优先）。

2. **回踩后续追踪窗口**（已确认）：10日 / 20日 / 30日 三个窗口。

3. **回踩事件去重**（已确认）：当信号从非 BUY_ZONE 变为 BUY_ZONE 时，记录为一次新的回踩事件；连续 BUY_ZONE 期间不重复记录。

5. **均线斜率定义**（已确认）：对最近 20 个交易日的 MA150 值做线性回归，斜率 > 0 为正、≤ 0 为负。仅斜率为正时才可能产生 BUY_ZONE 或 BREAKOUT 信号。

6. **Journal 字段**（已确认）：股票代码、操作类型（买/卖/加仓/减仓/观望）、价格、日期、仓位大小（数字输入，加仓/减仓时在当前仓位基础上调整）、止损位、目标价、买入原因、参考内容（大文本）。

7. **错误处理**（已确认）：
   - API 调用失败或异常：首页系统日志区域展示错误信息，记录时间和详情
   - 股票搜索无结果：弹出 Alert 组件提示"未找到匹配的股票"
   - 新上市股票数据不足 150 个交易日：仍添加到 watchlist，信号显示"数据不足"

---

## 版本迭代记录

### v1.2 迭代 — 2026-04-20

**变更原因**：v1.0/v1.1 的 SMA150 分析都基于手动输入的 watchlist。需要主动发现 watchlist 之外的新候选 —— 当日刚穿越 150MA 的大市值股票（市值≥500亿，以避免微盘股噪声）。

**新增 feature**：
- **F105：Market Breakout Scanner Widget** — 每日盘后扫描全美股（NYSE/NASDAQ/AMEX，含 ADR）市值≥500亿的股票池，筛出今日 MA150 穿越候选（昨日<MA、今日≥MA、幅度≤10%、MA150 斜率>0），以新 widget（category: `scanner`）形式展示。点击 ticker 联动现有 ChartWidget（服务端加 on-demand fallback，非 watchlist ticker 不入库）；行内 + 按钮一键加入 watchlist。

**修改 feature**：无。

**废弃 feature**：无。

**对下游文档的影响**：
- **DATA-MODEL.md**：新增 `market_breakout_scans` 表
- **API-CONTRACT.md**：新增 `GET /api/market/breakouts`；扩展现有 `GET /api/stocks/:ticker/chart` 加入 non-watchlist on-demand fallback（响应 schema 不变）
- **DECISIONS.md**：待新增决策 —— (a) 扫描只存最新快照、不保留历史；(b) 扩展现有 chart 端点而非新建 on-demand 端点（前端 ChartWidget 零改动）；(c) FMP screener 端点补入 D034 映射表并验证参数；(d) 扫描调度时间与 EOD refresh 的关系
- **design-spec.md**：待补 scanner widget 视觉规格（空态、错误态、+ 按钮 3 种状态）
- **ARCHITECTURE.md**：FMP 端点映射表新增 screener 条目

**下一步**：触发 system-design skill 补系统设计文档。

---

### v1.8 / v1.9 / v2.0 迭代 — 2026-04-24（Cockpit Epic）

**变更原因**：Workbench 主页偏试验（SMA150 信号验证、watchlist 试错、Chart 联动等），随着个人交易风格固化为"慢交易 / repricing / 周-日结合"，需要一个独立工作流页面承载：Market Regime 判断、结构化 Setup Monitor、Entry/Stop/Size 决策、持仓与条件单管理、复盘。参照 `/Users/wonderer/Downloads/slow_trading_system_proposal.md`（参考稿，非定稿）的 SRS（Slow Repricing System）构想落地。

**关键架构约束**（与 Workbench 哲学不同之处）：

1. **独立页 `/cockpit`**（非 Workbench 新 widget），TopNav 与 Workbench / News 平级。理由：完整工作流视图 + 迭代独立性。
2. **代码完全解耦**：`frontend/src/cockpit/` 与 `src/workbench/` 互不引用；`backend/app/routers/cockpit/` 与现有 router 互不引用；cockpit 专属 client state（`cockpitStore`）不复用 `useAppStore.selectedSymbol`。
3. **CockpitChart 与 Workbench ChartWidget 不共享代码**，接受代码重复换解耦。
4. **持仓全手动录入**（嘉信证券无 API），不做 broker 集成。
5. **AI 层 provider-agnostic**：选 LiteLLM 作为抽象层，通过 `.env` 配置 tier（default/critical/complex）对应的 model 字符串，换 provider 不改业务代码。
6. **Earnings 数据仅 cockpit 消费**，不泄露到 Workbench / News widget。

**切分为 3 期**：

| 迭代 | 版本 | 范围 | Features |
|---|---|---|---|
| P0 骨架 + 核心工作流 | v1.8 | 页面框架、Regime、Setup Monitor、Decision Panel、Earnings | F200 / F201 / F202 / F203 / F204 |
| P1 扩展 + 持仓 | v1.9 | Pool Builder、Position Manager、Daily Action List | F205 / F206 / F207 |
| P2 AI 层 | v2.0 | LLM Gateway、Narrator/Explainer、Ranker/Planner、Contradiction/News/Journal | F208 / F209 / F210 / F211 |

**新增 feature**：

- **F200**：Cockpit 页面框架（TopNav 入口 + `/cockpit` 路由 + 独立 react-grid-layout + 独立 layout localStorage key + CockpitRegistry）
- **F201**：Market Regime Widget（SPY/QQQ/IWM + 11 sector ETF + regime score + heatmap）
- **F202**：Setup Monitor Widget（watchlist cockpit 专用扩展视图：R/R / distance to entry / setup quality / earnings risk）
- **F203**：Decision Panel（独立 CockpitChartWidget + AVWAP/ATR/Entry/Stop/Target 叠加 + Position Size 计算 + `user_settings` 表）
- **F204**：Earnings Calendar 接入（FMP `/earnings-calendar` + 新表 `earnings_events`，仅 cockpit 消费）
- **F205**：Pool Builder Widget（多维筛选漏斗，复用 F105/F106 scanner 扩展 RS percentile + ADV filter + fundamental sanity）
- **F206**：Position Manager（手动录入 `positions` + `pending_orders` 两张新表，R multiple 实时计算）
- **F207**：Daily Action List Widget（must act / monitor / no action 三栏聚合，deterministic 规则引擎）
- **F208**：LLM Gateway（LiteLLM Router + tier config via env + budget 熔断 + `ai_memos` 表 + Pydantic schema validation）
- **F209**：Market Narrator + Setup Explainer（default tier）
- **F210**：Candidate Ranker + Trade Plan Generator（critical tier）
- **F211**：Contradiction Detector + News Summarizer + Journal Assistant（混合 tier，复杂任务走 complex）

**修改 feature**：无（cockpit 与现有 widget 完全解耦，不改现有 feature）。

**废弃 feature**：无。

**对下游文档的影响**：

- **DATA-MODEL.md**：新增 `market_regime_snapshots` / `earnings_events` / `user_settings` / `positions` / `pending_orders` / `ai_memos` 共 6 张表；`market_indices` 需扩展 symbol 集合（SPY/QQQ/IWM + 11 sector ETF）或新建 `sector_etfs`（待 system-design 决）。
- **API-CONTRACT.md**：新增 cockpit 命名空间下约 10 个 endpoint（/regime / /pool / /setup-monitor / /user-settings / /decision/{ticker} / /positions / /pending-orders / /actions/today / /earnings）+ AI 统一入口 `POST /api/ai/{task_type}`（6 个 task 共用路径）。
- **ARCHITECTURE.md**：新增 `backend/app/ai/` 模块 + `backend/app/routers/cockpit/` + `backend/app/services/cockpit/`；新前端 `frontend/src/pages/Cockpit.tsx` + `frontend/src/cockpit/` + `frontend/src/store/cockpitStore.ts`；依赖层级规则追加 cockpit/workbench 互不引用；外部依赖加 `litellm`；新 env：`OPENAI_API_KEY` / `AI_MODEL_DEFAULT` / `AI_MODEL_CRITICAL` / `AI_MODEL_COMPLEX` / `AI_MONTHLY_BUDGET_USD`。FMP 端点映射表加 `/stable/earnings-calendar`。
- **DECISIONS.md**：预计追加 5–6 条决策：(a) Cockpit 独立页、(b) 选 LiteLLM 作 AI 抽象（context7 已确认契合）、(c) CockpitChart 不共享 ChartWidget 代码、(d) cockpit 专属 store 不复用 useAppStore、(e) Earnings 仅 cockpit 消费、(f) `market_indices` 表复用 vs 新建 `sector_etfs`（由 system-design 拍板）。
- **design-spec.md**：全 12 个 cockpit widget 的视觉规格待 design-bridge 阶段补齐。

**明确不做**：

- ❌ 券商 API 接入（手动录入持仓）
- ❌ Intraday / Level-2（维持 EOD only）
- ❌ 真实下单（pending_orders 只是计划，不落单）
- ❌ 多用户系统（保持单用户）
- ❌ AI 直接改写 deterministic 数字（strict guardrail）

**下一步**：

1. 用户在新 session 中触发 `system-design` skill，扩展 DATA-MODEL / API-CONTRACT / ARCHITECTURE / DECISIONS 覆盖 F200–F211。
2. system-design 完成后触发 `design-bridge` 设计 Cockpit 页面 Figma。
3. design-bridge 完成后进入 `feature-dev` 循环，从 F200 开始。

---

### v2.3 迭代 — 2026-05-15（Cockpit 改善计划 Phase C：Capitulation Reversal 严格重写）

**变更原因**：对照 `docs/对比/cockpit-vs-srs-framework.md` 扫描报告 §3.C row 4 + §4 Gap #4：当前 setup_service 用 `SETUP_PULLBACK`（仅判定 MA150~MA50 之间回踩 MA21）近似 SRS § 五 Setup 4 "Capitulation Reversal"（投降式抛售反转），**两者语义完全不同**。Phase A (F215) / Phase B (F216) 已落地，本 Phase C 把核心 setup 之一从近似实现升级为 SRS 严格定义。Phase D (F218 Repricing Trigger) 是下游待规划阶段。

**新增 feature**：

- **F217**：Cockpit Phase C — Capitulation Reversal 严格重写。按 SRS § 五 Setup 4 实现 7 条 AND 门：(1) 过去 5-10 日 close 累计跌幅 ≥ 10%；(2) 当日 Vol z-score ≥ 2.5（复用 F215-b `_compute_volume_zscore`）；(3) true_range ≥ 2 × ATR14；(4) close 位于当日 high-low 上 1/3；(5) 当日之后 1-2 日 low > 当日 low（不创新低）；(6) 当前 low > 过去 30 日内倒数第二个 swing low（`_detect_swing_lows` 辅助）；(7) RS line 过去 5 日未创新低。同时移除 `SETUP_PULLBACK` 全部引用、升级 `_classify_setup_type` 优先级为 BROKEN → EXTENDED → EARNINGS_DRIFT → **CAPITULATION** → BREAKOUT → RECLAIM → NONE、DB 迁移 + 历史 PULLBACK 软删、前端 DecisionPanel chips（Vol z / Drop 5d / Reversal day）+ SetupMonitor 紫色 badge。拆 F217-a / F217-b / F217-c 三 sub-sprint。

**修改 feature**：无。

**废弃 feature**：无（PULLBACK 仅是 setup_type 枚举值，不是独立 feature，所以不走 deprecated 流程；通过 setup_snapshots 历史行软删保留审计）。

**对下游文档的影响**：

- **DATA-MODEL.md**：`SetupSnapshot.setup_type` 枚举去 `PULLBACK` 加 `CAPITULATION`；alembic 021 迁移脚本同步描述；可选新增 `legacy` 列保留历史 PULLBACK 行审计（plan §C4 软删方案）。
- **API-CONTRACT.md**：`GET /api/cockpit/setup` 响应 `setupType` 字段枚举更新；`GET /api/cockpit/decision/{ticker}` 响应追加可选 `capitulationEvidence` 对象（`volZscore` / `drop5dPct` / `reversalDay`）。
- **DECISIONS.md**：新增 D095 "Capitulation 替换 PULLBACK"，记录 (a) PULLBACK 与 SRS Setup 4 语义错位的判定证据 (b) 7 条 AND 门取阈值的依据 (c) 历史数据软删而非硬删的理由 (d) `_classify_setup_type` 优先级升级理由（CAPITULATION 与 BREAKOUT/RECLAIM 互斥）。
- **design-spec.md**：Widget 5 (SetupMonitor) 追加 CAPITULATION 紫色 badge 规则（token 例：`#a78bfa`）；新增 DecisionPanel CAPITULATION 状态下 3 chip 规格（Vol z-score / Drop 5d / Reversal day）。
- **data-mapping.md**：`setupType` / `capitulationEvidence` 字段映射追加。
- **ARCHITECTURE.md**：无影响（无新模块、无新依赖）。

**预期影响**：

- CAPITULATION 严格判定（7 条 AND）触发非常稀疏，历史上每月可能只有几只标的命中 — **这是 SRS 设计意图，不是 bug**。
- 现有 `SETUP_PULLBACK` 当前在 setup_monitor 上显示部分标的，切换后这些行会落到 NONE，进一步缩减 `ready_signal=true` 候选（继 F216-d 30-50% reduction 之后）。
- F215（Volume z-score）+ F216（Weekly Stage）无代码改动，仅作为 C2 / ready_signal 协同复用。

**明确不做**：

- ❌ 不动 F216-d 的 ready_signal 8 门 gate 逻辑（CAPITULATION 与 ready_signal 解耦，由 F218 评估是否需要进一步集成）。
- ❌ 不删除 setup_snapshots 历史 PULLBACK 行（软删保留审计，plan §C4 明确）。
- ❌ 不在本 Phase C 处理 SRS § 十一 Repricing Trigger（属 Phase D / F218）。

**下一步**：

1. 触发 `system-design` skill 走变更协议，更新 DATA-MODEL.md SetupSnapshot 枚举 + API-CONTRACT.md setup/decision 端点 + DECISIONS.md D095。
2. system-design 完成后进入 `feature-dev`，从 F217-a 开始协商 Sprint Contract（后端 setup_service 重写 + pure tests）。
3. F217-a Evaluator 通过后顺序进入 F217-b（DB 迁移）→ F217-c（前端 chips + badge）。
4. F217 整体 acceptance 通过后规划 F218 (Phase D: Repricing Trigger 5 类完整框架)。

---

### v2.4 迭代 — 2026-05-18（Cockpit 改善计划 Phase D：Repricing Trigger 完整框架 5 类）

**变更原因**：cockpit-vs-srs-framework 改善计划的 4 阶段收官阶段（Phase D）。Phase A (F215 Volume z-score) / Phase B (F216 Weekly Stage) / Phase C (F217 Capitulation Reversal) 已全部落地，cockpit 已具备 setup-level 信号能力。Phase D 对照 SRS § 十一 Repricing Trigger 完整框架，新增独立信号层 —— 识别『让市场重新定价此公司』的基本面/产业/资产负债端事件，与价格 setup 解耦但在慢交易框架中决定持仓周期与仓位规模。完成后 cockpit 4 个支柱齐全。

**新增 feature**：

- **F218**：Cockpit Phase D — Repricing Trigger 完整框架（5 类）。新建独立 `RepricingTriggerService` 与 `repricing_triggers` 表，串行调度 5 个 detector：
  - **T1 EARNINGS_ACCEL**：复用 `EarningsEventRepository`，连续 2 季 EPS+revenue YoY 加速 AND q0 yoy ≥ 20%
  - **T2 MARGIN_EXPANSION**：新接 FMP `key-metrics-ttm` + `ratios?period=quarter`，新表 `stock_key_metrics_quarterly`，毛利率扩张 ≥ 200bp 或 FCF margin 扩张 ≥ 300bp
  - **T3 NEW_PRODUCT (D4a)**：扫描 `news_cache` 过去 30 日 headlines，关键词集合 {launch, unveil, introduce, release, AI, platform, new product} ≥ 2 次命中（D4b NLP 升级留后续 issue）
  - **T4 SECTOR_CYCLE**：复用 `SECTOR_ETFS` + `_compute_rs_percentile`，sector ETF RS percentile <40 → >60 且 sector ETF > SMA200
  - **T5 BALANCE_INFLECTION**：新接 FMP `balance-sheet-statement` + `cash-flow-statement`，新表 `stock_fundamentals_quarterly`，净负债连降或 FCF 转正
  - `refresh_job.py` 新增 cron 周一—周五 22:40 UTC（setup_tick 之后）调度。前端新增独立 `RepricingTriggerWidget`（全市场 active triggers 表格）+ `DecisionPanelWidget` 顶部 trigger badge 区。Sub-sprint 拆分留给 feature-dev sizing（预期 D1 框架 / D2-D6 五 detector / D7 调度+前端，约 7-9 sub-sprint）。

**修改 feature**：无。

**废弃 feature**：无。

**对下游文档的影响**：

- **DATA-MODEL.md**：新增 3 张表 —
  - `repricing_triggers`（id / ticker / trigger_type / detected_date / confidence / evidence_json / active；trigger_type ∈ {EARNINGS_ACCEL, MARGIN_EXPANSION, NEW_PRODUCT, SECTOR_CYCLE, BALANCE_INFLECTION}）
  - `stock_key_metrics_quarterly`（quarter / gross_margin / op_margin / net_margin / fcf_margin / roic，去重键 ticker+quarter）
  - `stock_fundamentals_quarterly`（quarter / net_debt / fcf / total_debt / cash，去重键 ticker+quarter）
- **API-CONTRACT.md**：新增 2 个 endpoint —
  - `GET /api/cockpit/repricing-triggers/{ticker}`：返回该标的所有 active triggers
  - `GET /api/cockpit/repricing-triggers`：返回全市场 active triggers，按 `detected_date` 倒序，支持可选 `trigger_type` 过滤
  - 响应中 `evidence` 对象按 `trigger_type` 区分形态（5 套 schema）
- **DECISIONS.md**：预期新增至少 3 条 —
  - **D096**：5 类 Repricing Trigger 框架与表设计（evidence_json 用 JSON 列 vs 分表的取舍）
  - **D097**：FMP 新增 4 个 endpoint 接入（`key-metrics-ttm` / `ratios?period=quarter` / `balance-sheet-statement` / `cash-flow-statement`），quota 占用与缓存策略（quarterly 粒度 + weekly pool rebuild 时刷新）
  - **D098**：T3 New Product 采用 D4a 关键词扫描而非 NLP 的取舍（D4b 升级路径与独立 issue 划界）
- **ARCHITECTURE.md**：新增模块 `backend/app/services/cockpit/repricing_trigger_service.py` + 2 个 repository（`KeyMetricsRepository` / `FundamentalsRepository`）+ cron 调度新增 22:40 UTC 时间窗
- **design-spec.md**：新增 `RepricingTriggerWidget` 视觉规格（表格列、5 类 trigger 颜色 token、行内 evidence 简写）+ DecisionPanel 顶部 trigger badge 区规格（持仓 ticker 有 active trigger 时渲染，无则不留空白）
- **component-plan.md**：`RepricingTriggerWidget` 注册到 Cockpit Registry；DecisionPanel 边界更新（新增 trigger badge 区，独立于现有 setup chip 区）
- **data-mapping.md**：新字段映射（5 trigger types / 各 evidence shape / activeTriggers 数组）
- **tokens.css**：新增 5 个 trigger 类型颜色 token

**预期影响**：

- 触发频率预期合理（每日全市场 5 类合计数十至百量级），单 ticker 同时持有 2+ trigger 属高 conviction 信号
- T3 关键词扫描的 precision 偏低（高 recall），用户在 widget 中需配合 evidence 中的 `news_links` 人工判读 — 这是 D4a 的设计取舍，D4b NLP 升级后会改善
- FMP 新增 4 endpoint 接入会增加 API 调用，缓存策略（quarterly 粒度 + weekly 刷新）确保 quota 占用可控
- F215 / F216 / F217 代码零改动，仅 DecisionPanel 集成 trigger badge 区为 additive 改动

**明确不做**：

- ❌ T3 D4b NLP 升级（嵌入相似度 + LLM 标签）— 留作独立 issue
- ❌ Trigger 信号纳入 AI prompt 上下文（F209/F210/F211）— 留待 F218 验收后单独决策
- ❌ Trigger 与 `ready_signal` 8 门 gate 集成 — 保持解耦，trigger 只是参考信号
- ❌ Intraday trigger 检测 — 维持 EOD only（与 cockpit 全局约束一致）

**下一步**：

1. 触发 `system-design` skill 走变更协议，更新 DATA-MODEL.md（3 新表）+ API-CONTRACT.md（2 endpoint）+ DECISIONS.md（D096/D097/D098）+ ARCHITECTURE.md（新模块 + cron）。
2. system-design 完成后进入 `feature-dev` A-1 sizing 协商，按 plan D1 / D2-D6 / D7 自然拆 sub-sprints（预期 7-9 个）。design-spec.md / tokens.css / data-mapping.md / component-plan.md 由前端 sub-sprint 内联模式更新（参考 F216-d3 / F217-c2c 经验，无需独立 design-bridge）。
3. F218 整体 acceptance 通过后，cockpit-vs-srs-framework 改善计划 4 阶段（A/B/C/D）全部收官，可衔接 v3.0 发版规划。

### v2.6 迭代 — 2026-06-10（Fundamentals 估值指标增强：正常化 P/E 体系）

**变更原因**：当前 Fundamentals widget 的 P/E 是 FMP `/ratios-ttm` 透传的原始 GAAP P/E，无任何计算，极易被一次性会计项目失真 —— DUOL FY2025 净利润含一次性递延税资产转回约 $222.7M，原始 P/E ~13×（假象便宜），剔除后正常化 P/E 实际 ~28×。本次把估值指标从『易被会计噪音误导』升级为『去噪 + 稳定』的体系，并补充 swing trading 有指征意义的动量/预期派生信号。主锚 = 正常化 P/E（异常季用税后营业利润 NOPAT 替代 GAAP 净利润）；交叉验证 = P/(FCF−SBC)（现金流视角，SBC 当真实股东成本）；两者自洽性本身是信号。

**新增 feature**：

- **F220**：Fundamentals 估值指标增强 — 正常化 P/E 体系。范围 P0 + P1（⑤历史分位计算后置到未来 F220-f）。5 个 sub-sprint：
  - **F220-a 正常化 P/E 核心（P0）**：新建 `backend/app/services/normalized_valuation.py` 纯函数模块（季报归一化 / 防循环平均有效税率 / 异常季 NOPAT 判定 / TTM 正常化 EPS / 正常化 P/E）+ `get_fundamentals` 成员门控编排 + 当前价路径 + schema/cache 扩展 + 前端主位渲染 + 追溯折叠区
  - **F220-b P/(FCF−SBC) 双版本 + 自洽红旗（P0）**：`p_fcf_raw` / `p_fcf_adj`（市值 = 最新季 Diluted 股本 × 当前价，自算口径自洽）+ `sbcSensitiveFlag`（gap>40% 红旗）
  - **F220-c 正常化 P/E 时序表预埋（P0）**：新表 `normalized_pe_history`（alembic 026）+ repository + 机会性 `upsert_today`（同日幂等）；分位字段本轮恒 None
  - **F220-d EPS 加速度（P1）**：`compute_normalized_eps_series`（最近 8 季滑动 4 季 TTM 正常化 EPS）+ 二阶差分信号；<8 季 → None 不报错
  - **F220-e 预期修正方向（P1）**：fmp `get_analyst_estimates` + 新表 `analyst_estimate_snapshots`（alembic 027）+ weekly cron（建议 Mon 07:00 UTC）抓 watchlist+pool 快照 + 两快照 diff 算方向/幅度/离散度；仅辅助信号不进①主锚

**修改 feature**：无。

**废弃 feature**：无。

**对下游文档的影响**：

- **API-CONTRACT.md**：扩展 `GET /api/stocks/{ticker}/fundamentals` —— `Fundamentals` 模型保留 `priceToEarnings` 作 raw（向后兼容 + 自洽检验），新增 `normalizedPe` / `normalizedEps` / `normalizedTtmEarnings` / `pFcfRaw` / `pFcfAdj` / `sbcSensitiveFlag` / `traceability`（子对象：currentPrice / priceSource / dilutedShares / avgEffectiveTaxRate / taxRateSourceQuarters[] / abnormalQuarters[] / degradeReason）/ `epsAcceleration` / `estimateRevision` / `normalizedPePercentile`（本轮恒 None）。router `stocks.py` 无需改（response_model 自动带新字段）。
- **DATA-MODEL.md**：新增 2 张表 —
  - `normalized_pe_history`（id / ticker / as_of_date / normalized_pe / normalized_eps / current_price / p_fcf_adj / computed_at；UQ ticker+as_of_date 同日幂等）
  - `analyst_estimate_snapshots`（id / ticker / snapshot_date / target_period / estimated_eps_avg/low/high / fetched_at；UQ ticker+snapshot_date+target_period）
  - `daily_payload_cache`（复用：正常化字段塞进同一 payload，无需新 endpoint）
- **DECISIONS.md**：预期新增至少 4 条 — 正常化税率防循环策略（税率自身边界 IBT>0 且 0≤rate≤0.50 筛种子，绝不复用净利润异常判定）/ 市值自算口径（最新季 Diluted × 当前价，不用 key-metrics-ttm 的 marketCap）/ 成员门控（仅 watchlist+pool 计算正常化）+ 同日缓存 / 降级显式不可用绝不回退 raw P/E。
- **ARCHITECTURE.md**：新增模块 `backend/app/services/normalized_valuation.py`（workbench 侧纯函数，照 `cockpit/pool_helpers.py` 模式重写但**禁止 import**，遵依赖方向 routers→services→repositories→models）+ FMP `get_analyst_estimates` 端点 + weekly cron Mon 07:00 UTC（避开既有窗口）。
- **design-spec.md**：新增追溯折叠区（`<details>`）紧凑规范（11px 表 + `--font-family-numeric` + 正负色）；正常化 P/E 主位大字 + raw 小灰字副标 + 红旗角标规范。
- **WidgetRegistry.ts**：`sma150.fundamentals` 默认高度上调（h:7, minH:5），`news.fundamentals` 同步，否则追溯区被截断。

**明确不做**：

- ❌ ⑤历史分位计算（F220-f）—— 本轮只做 F220-c 时序表预埋，待积累历史后单列
- ❌ 覆盖全市场任意 ticker —— 仅 watchlist(active) + trend pool 成员门控（FMP 配额 + 同日缓存）
- ❌ 降级时回退原始 P/E —— 原始 GAAP P/E 正是要规避的失真源，算不出就显式标不可用
- ❌ NTM（forward）P/E —— 规避分析师预期主观性，正常化用 TTM 历史实绩去噪
- ❌ 预期修正引入 NLP —— F220-e 只读 FMP analyst-estimates 数值 diff

**下一步**：

1. 触发 `system-design` skill 走变更协议，更新 API-CONTRACT.md（fundamentals 扩展）+ DATA-MODEL.md（2 新表 + daily_payload_cache 复用口径）+ DECISIONS.md（税率破环/市值自算/成员门控/降级 4 决策）+ ARCHITECTURE.md（normalized_valuation 模块 + 架构守约 + weekly cron）。
2. system-design 完成后进入 `feature-dev` A-1，从 F220-a 起逐 sub-sprint sizing 协商（注意 F220-a ≈7 文件 / F220-e ≈9 文件超 6 文件原则，按 F217-c2c / F218-d3a 模式申请超额授权或二次拆）。design-spec.md 由前端 sub-sprint 内联模式更新（参考 F216-d3 / F217-c2c）。
3. F220 全部 sub-sprint done 后做 DUOL 实测 acceptance（正常化 P/E ∈ [25,30]× / p_fcf_adj ∈ [20,22]× / EPS 加速度给减速 / 追溯区可查），衔接 v2.6 发版。

