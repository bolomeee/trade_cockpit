# Cockpit vs《慢交易系统框架》(SRS) 对比报告

## 0. 元信息

| 项 | 值 |
|---|---|
| Spec 路径 | `~/Downloads/慢交易系统框架.md`（879 行，12 节） |
| 实现范围 | `backend/app/services/cockpit/`, `backend/app/routers/cockpit/`, `frontend/src/cockpit/`, `backend/layouts/cockpit.json` |
| 扫描时间 | 2026-05-12 |
| Git HEAD | `49cfd8b` feat(news-summary): 切换 DeepSeek + 详细摘要 + 1天窗口 |
| 分类标准 | ✅ 已实现 / 🟡 部分实现 / ❌ 缺失 / ⚠️ 偏离 / ➖ N/A |

**一句话结论**：cockpit 把 SRS 的"市场环境 → 股票池 → 日线触发 → ATR 风控"主线落地度很高（约 65–70%），但**周线层（Stage Chart / Weekly MA）、EMA 系列、Volume z-score、Fundamental Inflection 图表、Repricing trigger 显式标注**这五块缺口最大，正好是 SRS 与"普通技术指标系统"拉开差距的部分。

---

## 1. SRS 框架要点摘要

SRS = **Slow Repricing System**，5 层模型：

```
市场环境 → 股票池 → 周线结构 → 日线触发 → 风控与执行
```

核心理念：不做日内、不追盘中分时，每天盘后批处理一次，靠**条件单 + ATR 风控**执行。
判定顺序：**基本面/事件 re-rating → 周线机构吸筹 → 日线低风险 entry → 条件单 → ATR**。

四个核心 setup：Volatility Contraction Breakout / Post-Earnings Drift Pullback / 50MA Reclaim / Capitulation Reversal。三层股票池：Core Universe / Quality Growth / Technical Leadership。五大信号：Trend Score / RS / Volume Accumulation / ATR Risk / Earnings Risk Flag。

---

## 2. 五档分类对比总表

| § | SRS 要素 | 状态 | 证据 | 备注 |
|---|---------|:---:|------|------|
| 三.1 | Daily OHLCV | ✅ | [chart_service.py:178-211](backend/app/services/cockpit/chart_service.py:178) | DB + FMP fallback |
| 三.1 | Adjusted close | 🟡 | — | 用 close，未明确区分 adjusted |
| 三.1 | EMA 10/21 | ❌ | 未找到 | 仅实现 SMA |
| 三.1 | SMA 50/150/200 | ✅ | [chart_service.py:25-40](backend/app/services/cockpit/chart_service.py:25), [setup_service.py:54-63](backend/app/services/cockpit/setup_service.py:54) | MA_PERIODS=[10,21,50,150,200] |
| 三.1 | Weekly 10/30/40 MA | ❌ | 未找到 | 仅 daily bars |
| 三.1 | ATR 14 / ATR 20 | 🟡 | [chart_service.py:43-73](backend/app/services/cockpit/chart_service.py:43) | Wilder ATR 已实现，但仅 ATR_PERIOD=14；ATR 20 未提供 |
| 三.1 | 52-week high | ❌ | 未找到 | 无显式计算（pivot 用 20 日高代替） |
| 三.1 | Volume z-score | ❌ | 未找到 | 仅 HIGH/NORMAL/LOW 三档 ratio |
| 三.1 | RS vs SPY / QQQ | 🟡 | [setup_service.py:286-329](backend/app/services/cockpit/setup_service.py:286), [pool_cache_service.py](backend/app/services/cockpit/pool_cache_service.py) | RS 仅 vs SPY，未对 QQQ；用 percentile rank (20 日 RS_LOOKBACK_DAYS) |
| 三.1 | AVWAP | ✅ | [chart_service.py:76-101](backend/app/services/cockpit/chart_service.py:76) | 锚 earnings date，cumulative VWAP |
| 三.1 | AVWAP from major low | ❌ | 未找到 | 仅支持 earnings anchor |
| 三.2 | 基本面 (Revenue growth / Margin / FCF / ROIC) | 🟡 | [pool_service.py:171-193](backend/app/services/cockpit/pool_service.py:171) | 只用 revenue_growth_yoy；毛利率/FCF/ROIC 未取 |
| 三.3 | Earnings date | ✅ | [earnings_service.py](backend/app/services/cockpit/earnings_service.py) | FMP earnings calendar，缓存下次日期 |
| 三.3 | EPS estimate vs actual | 🟡 | [earnings.py](backend/app/routers/cockpit/earnings.py) | API 返回 EPS estimate；surprise 未计算 |
| 三.3 | News headlines | ➖ | — | 项目有 news widget，但未关联 cockpit 决策 |
| 三.4 | SPY / QQQ / IWM | ✅ | [cockpit_params.py:21-24](backend/app/services/cockpit/cockpit_params.py:21) | INDEX_ETFS=[SPY,QQQ,IWM,VXX] |
| 三.4 | 11 Sector ETFs | ✅ | [cockpit_params.py:17-20](backend/app/services/cockpit/cockpit_params.py:17) | XLK/XLY/XLF/XLI/XLE/XLV/XLC/XLP/XLU/XLB/XLRE |
| 三.4 | VIX | 🟡 | [cockpit_params.py:23](backend/app/services/cockpit/cockpit_params.py:23) | 用 VXX 代理（注释说明） |
| 三.4 | 10Y Treasury / USD index | ❌ | 未找到 | |
| 四.1 | Market Regime Dashboard | ✅ | [market_regime_service.py](backend/app/services/cockpit/market_regime_service.py), [MarketRegimeWidget.tsx](frontend/src/cockpit/widgets/MarketRegimeWidget.tsx) | 6 子分数 + 5 阶 regime + 允许敞口 + 单笔风险 |
| 四.2 | Weekly Stage Chart | ❌ | 未找到 | **重大缺口** — 仅 daily chart |
| 四.3 | Daily Setup Chart | ✅ | [chart_service.py](backend/app/services/cockpit/chart_service.py), [CockpitChartWidget.tsx](frontend/src/cockpit/widgets/CockpitChartWidget.tsx) | K 线 + 多 MA + ATR + AVWAP |
| 五.1 | Volatility Contraction Breakout | 🟡 | [setup_service.py:141-149](backend/app/services/cockpit/setup_service.py:141) | 代码名 `SETUP_BREAKOUT`；用"20 日 pivot high ± 5%" 近似，**未实现波动率收缩 (NR7/range contraction)**、未要求 RS 横住 |
| 五.2 | Post-Earnings Drift Pullback | 🟡 | [setup_service.py:134-139](backend/app/services/cockpit/setup_service.py:134) | 代码名 `SETUP_EARNINGS_DRIFT`；条件仅"earnings 7 日内 & close>MA21"，**未识别 gap up %、未识别 pullback to AVWAP**、未识别 reversal day |
| 五.3 | 50MA Reclaim / Shakeout Reversal | ✅ | [setup_service.py:162-169](backend/app/services/cockpit/setup_service.py:162) | 10 bar lookback 找 close<MA50，今日 close>MA50 → RECLAIM |
| 五.4 | Capitulation Reversal | ❌ | 未找到 | 当前用 `SETUP_PULLBACK` 近似（MA150~MA50 之间回撤），**没有放量 + 反转日 + higher low 的判定** |
| 六.1 | Core Universe (Tradable) | ✅ | [pool_service.py:99-111](backend/app/services/cockpit/pool_service.py:99) | market_cap≥$5B/$10B, price≥$10, ADV≥$20M |
| 六.2 | Quality / Growth Filter | 🟡 | [pool_service.py:171-193](backend/app/services/cockpit/pool_service.py:171) | 仅 revenue_growth_yoy≥10%；**毛利率、FCF margin、稀释、净负债等未取** |
| 六.3 | Technical Leadership Filter | ✅ | [pool_service.py:113-169](backend/app/services/cockpit/pool_service.py:113) | trend (breakout proxy) + rs_percentile≥70 |
| 六.3 | 距 52-week high < 15-20% | ❌ | 未找到 | |
| 六.3 | RS 3M/6M percentile | 🟡 | [setup_service.py:286-329](backend/app/services/cockpit/setup_service.py:286) | 仅 20 日 RS percentile（RS_LOOKBACK_DAYS=20）；3M/6M 未分别计算 |
| 六.3 | 行业 ETF 强于 SPY 过滤 | ❌ | 未找到 | sectors 仅作为可选 filter 参数，未做 sector RS 判定 |
| 七.1 | Trend Score (0-6) | ⚠️ | [setup_service.py:66-79](backend/app/services/cockpit/setup_service.py:66) | **5 阶梯版**（close>MA10>MA21>MA50>MA150>MA200），**少了 50MA slope>0 这一项**；SRS 用 50/150/200 三 MA 给 5 分，再加 50MA slope |
| 七.2 | RS Score (3M/6M/RS line new high) | 🟡 | [pool_cache_service.py](backend/app/services/cockpit/pool_cache_service.py) | 仅一个 rs_percentile；3M/6M 分项与 RS line new high 未实现 |
| 七.3 | Volume Accumulation Signal | ❌ | 未找到 | 无 OBV、无累计、无 up vs down volume |
| 七.4 | ATR Risk / Position Sizing | ✅ | [position_sizer.py:4-8](backend/app/services/cockpit/position_sizer.py:4) | `shares = floor(account × risk% / (entry-stop))` |
| 七.5 | Earnings Risk Flag (T-10/T-3/T+1/T+15) | 🟡 | [setup_service.py:174-183](backend/app/services/cockpit/setup_service.py:174) | 仅 DANGER/CAUTION/SAFE 三档（T-3/T-10）；T+1~T+15 drift 窗口在 setup 分类里识别，未作为独立 flag |
| 八.A | Weekly Leadership Chart 模板 | ❌ | 未找到 | |
| 八.B | Daily Execution Chart 模板 | ✅ | [CockpitChartWidget.tsx](frontend/src/cockpit/widgets/CockpitChartWidget.tsx) | 含 K 线 / MA / ATR / Volume / AVWAP |
| 八.B | Entry / Stop / 2R / 3R target line | ✅ | [setup_service.py:115-119](backend/app/services/cockpit/setup_service.py:115) | targets 已计算并返回，DecisionPanel 显示 |
| 八.C | Fundamental Inflection Chart | ❌ | 未找到 | 5 年 Revenue/Margin/FCF/ROIC 历史图缺失 |
| 九 | 每周末工作流 | 🟡 | [pool_cache_service.py](backend/app/services/cockpit/pool_cache_service.py) | 有 weekly pool cache rebuild (Mon 06:30 UTC)；watchlist 标注 setup 类型已自动；2R/3R 预设有 |
| 九 | 每天盘后 30 分钟工作流 | ✅ | scheduler + cockpit dashboard | regime / setup-monitor / pool 都是 daily 批处理 |
| 十 | 买入前必须满足 10 条 | 🟡 | [setup_service.py:203-224](backend/app/services/cockpit/setup_service.py:203) | Ready signal 是 7 条 AND 门（regime/trend/rs/quality/distance/RR/earnings）；SRS 还要"周线不是下降趋势、2R 前无明显阻力、单笔风险 ≤ 1%" |
| 十 | Buy stop 触发方式 | 🟡 | [setup_service.py:136,147,166](backend/app/services/cockpit/setup_service.py:136) | entry 价位已算 (pivot/MA50/MA21+tick)，但 cockpit 不下单，需用户手动挂；pending_orders 是手动录入 |
| 十 | 加仓规则（盈利时 0.25-0.5R） | ❌ | 未找到 | 无加仓 / pyramid 逻辑 |
| 十 | 减仓三段式 (2R/3R/trailing) | 🟡 | [setup_service.py:115-119](backend/app/services/cockpit/setup_service.py:115) | target_2r/3r 已算并展示；trailing (21EMA/50MA/10wMA) 未实现 |
| 十一 | Repricing 核心思想 | ⚠️ | — | 系统设计上偏"技术指标系统"，未显式标注 5 类 repricing trigger (earnings acceleration / margin expansion / new product / sector cycle / balance sheet inflection) |

---

## 3. 分主题逐项扫描

### 3.A 数据源 (SRS § 三)

| 数据 | 状态 | 说明 |
|------|:---:|------|
| Daily OHLCV / volume / market cap / sector | ✅ | FMP + DB |
| Beta / shares outstanding | ➖ | 未用 |
| 基本面：revenue growth | ✅ | revenue_growth_yoy 周缓存 |
| 基本面：gross margin / op margin / FCF / ROIC / EPS growth / net debt / 估值 (P/E, EV/EBITDA, P/FCF) | ❌ | 全部未取 |
| Earnings date / EPS estimate | ✅ | FMP earnings calendar |
| Earnings surprise (actual vs estimate) | ❌ | 未计算 |
| Market & sector ETFs | ✅ | 4 个 index + 11 个 sector |
| VIX / 10Y / USD index | 🟡 / ❌ / ❌ | 仅 VXX 代理 |

### 3.B 三大核心图表 (SRS § 四)

| 图表 | 状态 | 说明 |
|------|:---:|------|
| Market Regime Dashboard | ✅ | [MarketRegimeWidget.tsx](frontend/src/cockpit/widgets/MarketRegimeWidget.tsx) — 5 阶 regime + 6 子分数 + 允许敞口 + 单笔风险 + 推荐/避开 setup |
| Weekly Stage Chart | ❌ | **完全缺失**。SRS 把它定位为"牛散主图"，是判定 Stage 2 / Post-Earnings Gap Base / Deep Correction Reclaim 的唯一图。当前只有 daily chart |
| Daily Setup Chart | ✅ | [CockpitChartWidget.tsx](frontend/src/cockpit/widgets/CockpitChartWidget.tsx) — 完整覆盖 K 线 / 多 MA / ATR / Volume / AVWAP / earnings marker |

### 3.C 四种核心 Setup (SRS § 五)

| Setup | 代码命名 | 状态 | 阈值对比 |
|------|---------|:---:|---------|
| **Volatility Contraction Breakout** | `SETUP_BREAKOUT` | 🟡 | SRS 要求：10-30 日横盘 + 日内 range 收缩 + 成交量低于 50D 均 + 21EMA/50MA 上方 + RS 横住 + 明确 pivot。<br>**代码**：仅判定"20 日 pivot high - 5% 内 + trend_score≥3"。<br>**缺**：range contraction (NR7/Volatility Contraction Pattern)、成交量低水平、RS 横住判定 |
| **Post-Earnings Drift Pullback** | `SETUP_EARNINGS_DRIFT` | 🟡 | SRS 要求：Gap up >5% + 当日收盘上半区 + 成交量 >2×50D + 之后 3-15 日无快速回补 + RS 新高。两种买法：earnings gap high break / pullback to AVWAP reversal。<br>**代码**：仅"earnings 7 日内 & close>MA21"。<br>**缺**：gap 大小判定、gap day high/low 记录、AVWAP pullback 触发逻辑 |
| **50MA Reclaim / Shakeout Reversal** | `SETUP_RECLAIM` | ✅ | SRS 要求：长期上升 + 跌破 50MA 后 1-10 日收复 + 收复日放量 + 收盘上半区 + RS 未坏 + 大盘不坏。<br>**代码**：trend_score≥2 + 过去 10 日有 close<MA50 + 今日 close>MA50。**已覆盖核心**；放量与上半区判定缺失但是 nice-to-have |
| **Capitulation Reversal** | — | ❌ | SRS 要求：连续下跌 + 极端放量 + 大 range + 收盘脱离最低 + 次日不创新低 + higher low + RS 止跌。<br>**代码**：当前 `SETUP_PULLBACK` 是回踩 MA21 而非投降式抛售，**完全是另一种语义** |

### 3.D 三层股票池 (SRS § 六)

cockpit 实现的是 **5 层 funnel**（tradable → trend → rs → fundamental → action），比 SRS 的 3 层更细，映射关系：

| SRS 层 | cockpit 层 | 状态 |
|--------|-----------|:---:|
| Core Universe | tradable | ✅ |
| Quality / Growth Filter | fundamental | 🟡 仅 revenue growth |
| Technical Leadership Filter | trend + rs | 🟡 缺"距 52w high" 和"sector ETF 强于 SPY" |
| — | action（基于 setup type + distance + R/R） | ✅ cockpit 独有，在 SRS 中相当于"watchlist 标注 setup 类型" |

### 3.E 五大核心信号 (SRS § 七)

| 信号 | 状态 | 备注 |
|------|:---:|------|
| Trend Score | ⚠️ | 5 阶梯 vs SRS 0-6 分；少 50MA slope>0 |
| RS Score | 🟡 | 单一 percentile vs SRS 3M/6M 分项 + new high 检测 |
| Volume Accumulation | ❌ | **完全缺失** — SRS 强调机构吸筹判定，volume z-score / up vs down volume / breakout volume z-score 都未实现 |
| ATR Risk | ✅ | [position_sizer.py](backend/app/services/cockpit/position_sizer.py) |
| Earnings Risk Flag | 🟡 | 三档 (DANGER/CAUTION/SAFE) vs SRS 四档 (T-10/T-3/T+1~T+15/已盈利可跨) |

### 3.F 图表模板 (SRS § 八)

| 模板 | 状态 |
|------|:---:|
| A. Weekly Leadership Chart | ❌ |
| B. Daily Execution Chart | ✅ |
| C. Fundamental Inflection Chart | ❌ |

### 3.G 工作流 + 规则样板 (SRS § 九~十)

| 规则 | 状态 | 备注 |
|------|:---:|------|
| 每周末筛 20-50 只 watchlist | 🟡 | 有 weekly pool cache，但 watchlist 是用户手动维护 |
| 每日盘后 30 分钟批处理 | ✅ | regime + setup-monitor + pool 都是 daily |
| 不看盘中分时图 | ✅ | cockpit 没有 intraday widget |
| 买入前 10 条必须满足 | 🟡 | Ready signal 是 7 条；缺周线趋势、2R 前阻力、单笔风险 ≤1% 显式校验（单笔风险由 regime 决定，最高 1.5%，**已偏离 SRS 上限 1.25%**） |
| Buy stop 自动下单 | ❌ | 系统不接券商；用户手动用 pending_orders 录入 |
| 加仓规则 | ❌ | |
| 减仓三段式 (2R/3R/trailing) | 🟡 | 2R/3R 已算并显示；trailing 未实现 |

### 3.H Repricing 核心思想 (SRS § 十一)

SRS 第十一节是整套系统的"灵魂"——强调慢交易不是技术指标系统，而是**重新定价系统**，应识别 5 类 repricing trigger：

| Trigger 类型 | 在 cockpit 中是否显式标注 |
|-------------|:---:|
| Earnings acceleration | 🟡 — earnings 已识别，但没标注"加速"维度 |
| Margin expansion | ❌ |
| New product / AI / platform shift | ❌ |
| Sector cycle reversal | ❌ |
| Balance sheet / cash flow inflection | ❌ |

**结论**：cockpit 目前是一个"技术指标 + 风控"系统，**尚未上升到"重定价"层级**。这是 SRS 与 cockpit 在哲学上的最大差距。

---

## 4. 关键 Gap Top 8（按建议优先级）

| # | Gap | 重要性 | 工作量估计 |
|---|-----|--------|-----------|
| 1 | **Weekly Stage Chart 缺失** — SRS 把周线作为"牛散主图"，决定 Stage 2 / Post-Earnings Gap Base / Deep Correction Reclaim 的判定 | ★★★★★ | 中（聚合 daily bars 成 weekly + 新 chart endpoint + 新 widget） |
| 2 | **Volume Accumulation / z-score 缺失** — SRS 第七节核心信号之一，影响 BREAKOUT 触发的成交量确认门槛 | ★★★★ | 小（在 setup_service 新增列） |
| 3 | **EMA 系列缺失** (10/21 EMA) — SRS 退出规则依赖 21 EMA / 10 EMA trailing | ★★★★ | 小（chart_service 新增 EMA series） |
| 4 | **Capitulation Reversal 严格定义缺失** — 当前 `SETUP_PULLBACK` 与 SRS 第五节 Setup 4 完全是两种语义 | ★★★ | 中（新增 setup type + 放量 + higher low + RS 止跌判定） |
| 5 | **Fundamental Inflection Chart + 多维基本面缺失** — gross margin / FCF / ROIC / 稀释 / 净负债 都未取，无法做 SRS 第十一节的"重定价"判定 | ★★★ | 大（FMP key-metrics + fundamentals API 整合 + 新 widget） |
| 6 | **52-week high 显式计算缺失** — SRS 三层池"距 52w high < 15-20%"过滤维度 | ★★ | 极小（在 pool_cache 加一列） |
| 7 | **Repricing trigger 显式标注缺失** — SRS § 十一 的 5 类 trigger 当前完全不被识别 | ★★ | 大（需新 service 跨数据源做 trigger detection） |
| 8 | **Trailing stop 规则缺失** (21 EMA / 50 MA / 10 wMA 三段式) — SRS § 十的减仓三段式只实现了 2R/3R 部分 | ★★ | 小（DecisionPanel 加 trailing 计算） |

---

## 5. 偏离点（实现了但与 SRS 思路不同）

| 项 | SRS | cockpit 实现 | 差异 |
|----|-----|-------------|------|
| Trend Score | 0-6 分（含 50MA slope>0） | 5 阶梯（含 MA10、MA21 连续高于） | cockpit 增加了 MA10/MA21 阶梯，少了 50MA slope |
| 单笔风险上限 | RISK_ON 0.75%-1.25% | RISK_ON 1.5% / CONSTRUCTIVE 1.0% / NEUTRAL 0.75% | cockpit RISK_ON 上限高于 SRS 推荐 |
| RS 计算窗口 | 3M / 6M 分别比较，看 RS line 新高 | 20 日 percentile rank vs SPY return | cockpit 单一窗口，未做 3M/6M 分项与 RS line 新高 |
| BREAKOUT 判定 | Volatility Contraction（横盘 + 缩 range + 缩量） | 20 日 pivot high 内 5% + trend_score≥3 | cockpit 用价格位置近似，未做波动率收缩 |
| Earnings Risk 档位 | T-10 / T-3 / T+1 / T+15 四阶段策略 | DANGER (≤3d) / CAUTION (≤10d) / SAFE 三档 | cockpit 三档；T+1~T+15 drift 窗口在 setup 分类层而非 flag 层 |
| Pool 中 fundamental 维度 | Revenue / 毛利率 / Op margin / FCF / ROIC / 估值 多维 | 仅 revenue_growth_yoy 单维 | cockpit 大幅简化 |

---

## 6. 结论

**覆盖率**（按 ≈50 个要素粗算）：
- ✅ 已实现：约 18 项（36%）
- 🟡 部分实现：约 16 项（32%）
- ⚠️ 偏离：约 3 项（6%）
- ❌ 缺失：约 13 项（26%）

**整体评价**：
1. cockpit 已经把 SRS 主线"市场环境 → 股票池 → 日线触发 → ATR 风控"落地为可工作系统，盘后批处理 + 条件单 + ATR 风控的工作方式完全对齐 SRS 慢交易理念。
2. 但 SRS 中区别于"普通技术指标系统"的两大特色——**周线 Stage 判定**和**Repricing trigger 识别**——cockpit 都还没建立。当前 cockpit 更像"日线技术指标 + ATR 风控"系统，距离 SRS 的"慢重定价系统"还有半步。
3. 最值得优先补的：**周线层**（Stage 2/Post-Earnings Gap Base/Deep Correction Reclaim 都需要它）+ **Volume Accumulation**（机构吸筹判定）+ **EMA**（trailing stop 与 SRS 退出规则的基础）。

**一句话**：cockpit 已经是一个"能用的慢交易系统"，但还不是"完整的 SRS"——补齐周线 + Volume Accumulation + 多维基本面后，才接近 SRS 第十一节的"重定价系统"愿景。
