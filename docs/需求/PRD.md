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
