---
status: confirmed
confirmed_at: 2026-05-18
last_modified_by: system-design (F218 Phase D T2 数据源修正 2026-05-18 live probe — D097 endpoint key-metrics+ratios quarterly Starter 不支持，改 income-statement；T2/T5 共享 cash-flow，4 endpoint → 3 endpoint；roic 改 service 层近似公式)
---

# DATA-MODEL.md

> 最后更新：2026-04-24 | 状态：已确认
> ⚠️ 此文档是字段命名的唯一权威。前端、后端、数据库命名必须以此为准。
> ⚠️ 修改前必须评估对已有 API 和前端的影响，并告知用户。

---

## 命名规范

| 层 | 规范 | 示例 |
|----|------|------|
| 数据库字段 | snake_case | created_at |
| API 响应字段 | camelCase | createdAt |
| 前端变量 | camelCase | createdAt |
| 转换方式 | Pydantic alias_generator | — |

---

## 实体关系图

```
Stock (1) ──────── (N) DailyBar
  │
  ├──── (1) ────── (N) Signal
  │
  ├──── (1) ────── (N) Pullback
  │
  └──── (1) ────── (N) JournalEntry

MarketIndex（独立实体，无外键关联）
SystemLog（独立实体，无外键关联）
MarketScanUniverse（独立实体，无外键关联；市值≥500亿候选池，月级刷新）
MarketBreakoutScan（独立实体，无外键关联；当日 breakout 快照，覆盖写入）

── Cockpit Epic（v1.8 / v1.9 / v2.0，独立命名空间）──
MarketRegimeSnapshot（独立实体，每日一条，regime 打分）
SetupSnapshot（独立实体，按 ticker 存 cockpit setup 快照）
EarningsEvent（独立实体，(ticker, earnings_date) 唯一）
UserSettings（单行单用户，id=1 常量行）
Position（独立实体；ticker 为字符串，不 FK）
PendingOrder（独立实体；ticker 为字符串，不 FK）
AiMemo（独立实体；task_type + input_hash 双列索引供去重）
```

---

## Stock（股票）

> 对应数据库表：`stocks`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| ticker | String(10) | ✅ | 股票代码，唯一索引，如 "AAPL" |
| name | String(200) | ✅ | 公司名称 |
| exchange | String(20) | ❌ | 交易所，如 "NASDAQ" |
| is_active | Boolean | ✅ | 是否在 watchlist 中，默认 true |
| added_at | DateTime | ✅ | 添加到 watchlist 的时间 |
| last_refreshed_at | DateTime | ❌ | 最后一次数据刷新时间 |
| shares_float | Integer | ❌ | 流通股数量（F107-b1）；FMP `/stable/shares-float` 的 `floatShares`（D051 修订：原计划走 `/profile`，Starter 档位不含该字段）；ETF / 小盘无数据时 null |
| shares_float_refreshed_at | DateTime | ❌ | shares_float 最近一次从 FMP 刷新的 UTC 时间（F107-b1）；24h TTL 缓存戳（D050） |

**业务规则**：
- ticker 全大写存储
- 删除股票时设 is_active = false（软删除），保留历史数据
- 重新添加同一 ticker 时恢复 is_active = true
- shares_float 懒加载：首次 `/chart` 调用后写入；超过 24h 自动过期回源（D050）；FMP miss 仍写 refreshed_at 以避免反复请求

---

## DailyBar（日线数据）

> 对应数据库表：`daily_bars`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| stock_id | Integer (FK → stocks.id) | ✅ | 关联股票 |
| date | Date | ✅ | 交易日期 |
| open | Float | ✅ | 开盘价 |
| high | Float | ✅ | 最高价 |
| low | Float | ✅ | 最低价 |
| close | Float | ✅ | 收盘价 |
| volume | BigInteger | ✅ | 成交量 |

**业务规则**：
- (stock_id, date) 联合唯一索引
- 始终保持最近 250 个交易日的数据窗口
- 每日增量更新：添加最新交易日、删除最早交易日
- 首次添加股票时拉取 250 天基线数据

---

## Signal（150MA 信号）

> 对应数据库表：`signals`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| stock_id | Integer (FK → stocks.id) | ✅ | 关联股票 |
| date | Date | ✅ | 信号日期 |
| signal_type | String(20) | ✅ | 信号类型枚举 |
| ma150_value | Float | ❌ | 150 日均线值（数据不足时为 null） |
| close_price | Float | ✅ | 当日收盘价 |
| distance_pct | Float | ❌ | 价距百分比 = (close - MA150) / MA150 × 100% |
| slope_positive | Boolean | ❌ | 均线斜率是否为正（20日线性回归） |
| slope_value | Float | ❌ | 斜率原始值（用于展示） |

**业务规则**：
- (stock_id, date) 联合唯一索引
- 每次数据刷新后重新计算所有股票的最新信号
- 保留最近 250 天的信号记录，与 DailyBar 对齐，旧数据随 DailyBar 删除同步清理
- 数据不足 150 个交易日时，signal_type = "INSUFFICIENT"

**signal_type 枚举值**：

| 值 | 含义 | 判定条件 | 前端颜色 Token |
|----|------|---------|--------------|
| BREAKOUT | 向上穿越 | 斜率正 + 前日 close < MA150 且当日 close ≥ MA150 | --color-signal-breakout |
| BUY_ZONE | 回踩买入区 | 斜率正 + 收盘价在 MA150 上方 0–5%（含等于） | --color-signal-buyzone |
| NEUTRAL | 无信号 | 不满足以上条件 | --color-signal-neutral |
| INSUFFICIENT | 数据不足 | 交易日数据 < 150 条 | --color-signal-insufficient |

**信号判定优先级**：BREAKOUT > BUY_ZONE > NEUTRAL

---

## Pullback（回踩记录）

> 对应数据库表：`pullbacks`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| stock_id | Integer (FK → stocks.id) | ✅ | 关联股票 |
| date | Date | ✅ | 回踩触发日期（信号首次变为 BUY_ZONE 的日期） |
| close_price | Float | ✅ | 触发日收盘价 |
| ma150_value | Float | ✅ | 触发日 MA150 值 |
| distance_pct | Float | ✅ | 触发日价距百分比 |
| return_10d | Float | ❌ | 后续 10 个交易日涨幅（%），数据不足时 null |
| return_20d | Float | ❌ | 后续 20 个交易日涨幅（%） |
| return_30d | Float | ❌ | 后续 30 个交易日涨幅（%） |

**业务规则**：
- (stock_id, date) 联合唯一索引
- 当信号从非 BUY_ZONE 变为 BUY_ZONE 时，记录一次回踩事件
- 连续 BUY_ZONE 期间不重复记录
- 后续涨幅 = (第 N 日 close - 触发日 close) / 触发日 close × 100%
- 后续涨幅在每次数据刷新时更新（只要有新数据就重新计算）
- 若回踩发生在最近 30 个交易日内，涨幅可能不完整——字段保持 null 表示数据不足

---

## MarketIndex（大盘指标）

> 对应数据库表：`market_indices`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| symbol | String(20) | ✅ | 指标代码：SPX / NDX / TNX |
| name | String(100) | ✅ | 显示名称 |
| date | Date | ✅ | 数据日期 |
| close | Float | ✅ | 收盘值 |
| prev_close | Float | ❌ | 前一交易日收盘值 |
| change_pct | Float | ❌ | 涨跌幅（%） |

**业务规则**：
- (symbol, date) 联合唯一索引
- **symbol 枚举（v1.8 扩展，D060）**：
  - Workbench 原有：`SPX`、`NDX`、`TNX`（Workbench MarketOverviewWidget 消费；TNX 来自 FMP `/stable/treasury-rates.year10`）
  - Cockpit 新增 index ETF：`SPY`、`QQQ`、`IWM`（Market Regime 三大盘趋势）
  - Cockpit 新增 11 个 sector ETF：`XLK`（科技）/ `XLY`（非必需消费）/ `XLF`（金融）/ `XLI`（工业）/ `XLE`（能源）/ `XLV`（医疗）/ `XLC`（通信）/ `XLP`（必需消费）/ `XLU`（公用）/ `XLB`（原材料）/ `XLRE`（地产）
- 随 EOD 刷新自动更新；新增 14 个 symbol 通过 FMP `/stable/historical-price-eod/full?symbol={SPY|QQQ|...}` 拉取；D034 FMP 限流器覆盖，无额外限流配置
- 仅保留最近 **260 个交易日**数据（v1.8 起，Cockpit Regime 需要 200MA / 50MA / RS 计算；原 5 天窗口扩大，不影响既有 workbench 查询，workbench 仍读最新一行）
- 数据来源：SPX / NDX 走 FMP `/stable/historical-price-eod/full?symbol=^GSPC|^NDX`（D034），TNX 走 FMP `/stable/treasury-rates`；ETF 走 `/stable/historical-price-eod/full`
- DB symbol 字段命名权威（SPX/NDX/TNX 不受 FMP ^GSPC/^NDX 原始命名影响，service 层做映射；ETF 直接用 FMP symbol）
- **消费边界**：Workbench MarketOverviewWidget 继续只读 `SPX / NDX / TNX` 三行，**不消费** SPY/QQQ/IWM/sector ETF；Cockpit `GET /api/cockpit/regime` 读全部 17 个 symbol 的最新 260 天窗口

---

## SystemLog（系统日志）

> 对应数据库表：`system_logs`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| level | String(10) | ✅ | 日志级别：OK / INFO / WARN / ERROR |
| source | String(50) | ✅ | 来源模块，如 "polygon_client"、"signal_engine" |
| message | String(500) | ✅ | 错误/异常摘要 |
| detail | Text | ❌ | 详细信息（堆栈、请求参数等） |
| created_at | DateTime | ✅ | 记录时间，自动生成 |

**业务规则**：
- 按 created_at 倒序展示
- 保留最近 7 天的日志，超过 7 天的在每日刷新时自动清理
- 独立页面 `/logs` 展示，支持按级别 toggle 过滤
- level 枚举：OK（操作成功）、INFO（信息记录）、WARN（警告）、ERROR（错误）

---

## JournalEntry（交易日志）

> 对应数据库表：`journal_entries`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| stock_id | Integer (FK → stocks.id) | ✅ | 关联股票 |
| action | String(10) | ✅ | 操作类型枚举 |
| price | Float | ✅ | 操作价格 |
| date | Date | ✅ | 操作日期 |
| position_size | Float | ❌ | 仓位大小（股数），可与价格相乘计算成本/现值 |
| stop_loss | Float | ❌ | 止损位 |
| target_price | Float | ❌ | 目标价 |
| reason | Text | ❌ | 买入/操作原因 |
| reference | Text | ❌ | 参考内容（大文本） |
| created_at | DateTime | ✅ | 记录创建时间，自动生成 |
| updated_at | DateTime | ✅ | 记录更新时间，自动更新 |

**action 枚举值**：

| 值 | 含义 | 前端显示 |
|----|------|---------|
| BUY | 买入 | 买入 |
| SELL | 卖出 | 卖出 |
| ADD | 加仓 | 加仓 |
| REDUCE | 减仓 | 减仓 |
| WATCH | 观望 | 观望 |

**业务规则**：
- 按 date 倒序展示
- 加仓/减仓在概念上是在当前持仓基础上调整，但本表只记录单次操作的股数，不跟踪累计持仓
- position_size 单位为股数，前端可通过 price × position_size 计算成本

---

## MarketScanUniverse（全市场候选池）

> 对应数据库表：`market_scan_universe`
> Feature：F105 Market Breakout Scanner Widget
> 决策依据：D038（universe 与每日扫描解耦）

持久化市值≥500亿美元的全市场候选池，月级刷新一次。每日扫描读取此表，对每个 ticker 调用 SMA 端点判定 breakout。与 `stocks` 表解耦（`stocks` 只存 watchlist）。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| ticker | String(10) | ✅ | 股票代码，全大写，唯一索引 |
| company_name | String(200) | ✅ | 公司名称（来自 FMP screener） |
| exchange | String(20) | ✅ | 交易所：NYSE / NASDAQ / AMEX |
| market_cap | BigInteger | ✅ | 最近一次 universe refresh 时的市值（美元） |
| sector | String(64) | ❌ | 行业大类（来自 FMP screener；ETF 常缺失，存 null） |
| industry | String(128) | ❌ | 细分行业（来自 FMP screener；同上） |
| last_price | Float | ❌ | 最近一次 refresh 当天的快照收盘价；非实时（见 D078） |
| last_volume | BigInteger | ❌ | 最近一次 refresh 当天的快照成交量；非 ADV（见 D078） |
| last_seen_at | DateTime | ✅ | 最近一次在 refresh 结果中出现的 UTC 时间 |
| added_at | DateTime | ✅ | 首次进入 universe 的 UTC 时间 |

**业务规则**：
- 每月 1 号自动刷新（`UNIVERSE_CRON_*` 配置）；3 次 screener 调用：分别按 `exchange=NYSE / NASDAQ / AMEX`，`marketCapMoreThan=50000000000`，合并去重
- Upsert 策略：已存在 → 更新 `company_name / exchange / market_cap / sector / industry / last_price / last_volume / last_seen_at`；不存在 → 插入
- **不删除**"掉出 universe"的记录，保留审计痕迹。每日扫描通过 `last_seen_at >= 最近一次 refresh 时间` 筛选有效行
- 冷启动：服务启动时若表为空，自动触发一次 universe refresh 作为初始化
- 不做 FK 到 `stocks` 表，两张表职责独立
- `sector` / `industry` 字段缺失时存 null（ETF 等无此信息），**不跳过该 ticker**；`universe_refresh_service` 在 SystemLog 中记录各字段缺失行数供监控（F205-a）
- `last_price` / `last_volume` 是月级 refresh 快照，**不**用于实时展示；ADV 计算在 F205-b 走 trend 子集 EOD（见 D078）

---

## MarketBreakoutScan（每日多信号扫描快照）

> 对应数据库表：`market_breakout_scans`
> Feature：F105（初版）+ F106（v1.3 多信号扩展）
> 决策依据：D040（只存最新快照，覆盖写入）+ D045（单表多 signal_type，多行表达同 ticker 同日命中多信号）

存储每日扫描结果。每次扫描开始时单事务 `DELETE FROM market_breakout_scans` + 批量 `INSERT`，表永远只含最新一次扫描的命中记录。不保留历史。自 F106 起，同一 `(scan_date, ticker)` 可存在多条记录（每种命中的 `signal_type` 一行）。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| scan_date | Date | ✅ | 扫描所依据的交易日（美东日历） |
| ticker | String(10) | ✅ | 股票代码，全大写 |
| company_name | String(200) | ✅ | 公司名称（来自 universe 表） |
| signal_type | String(32) | ✅ | 信号类型枚举，见下方 |
| close_price | Float | ✅ | 扫描日收盘价 |
| ma150_value | Float | ✅ | 扫描日的 MA150 值 |
| pct_above_ma150 | Float | ✅ | (close - ma150) / ma150 × 100；保留 2 位小数业务含义 |
| slope_value | Float | ✅ | 最近 20 日 MA150 线性回归斜率 |
| volume | BigInteger | ❌ | 扫描日成交量（legacy 行为空，F106 起填充） |
| volume_ratio_20 | Float | ❌ | 当日成交量 / 过去 20 日均量；null 表示不可计算 |
| market_cap | BigInteger | ✅ | 扫描日该 ticker 的市值（扫描时从 universe 表读取） |
| scanned_at | DateTime | ✅ | 扫描任务的 UTC 执行时间 |

**signal_type 枚举**（F106）：
- `legacy_crossover`（F105 原规则；默认不通过 API 暴露，作对照基线保留）
- `a1_stage_breakout`（Stage 1→2 Breakout：长期横盘后放量上穿 MA150）
- `a2_slope_flip`（MA150 斜率近 30 日内由 ≤0 翻正且当前 close>MA150）
- `b2_ma_pullback`（MA5 贴 MA150 回踩后重新扩大）

**索引**：
- 唯一：`(scan_date, ticker, signal_type)`
- 辅助：`scanned_at DESC` 用于前端快速读最新快照

**业务规则**：
- 各 `signal_type` 具体规则参数集中在 `backend/app/services/scanner_params.py`，非逻辑代码可独立调整
- 一次扫描内，同一 ticker 对 4 条规则独立评估；每条命中都写一行（可同日多行）
- 扫描失败（FMP 异常、数据不足）：该 ticker 跳过，记 SystemLog，不写入本表
- 本表**不持久化未命中的 ticker**，只存命中记录
- 不做 FK 到 `stocks` 或 `market_scan_universe` 表，避免跨实体依赖约束；`ticker` 保持独立 VARCHAR(10)
- `volume` / `volume_ratio_20` 在 legacy_crossover 行可能为 null（F105 历史数据兼容），但 F106 起扫描出的所有行都会填充

---

## DailyPayloadCache（按日 on-demand 响应缓存）

> 对应数据库表：`daily_payload_cache`
> Feature：F111-a（2026-04-22）
> 决策依据：D055

为非 watchlist ticker 的 on-demand 请求（chart fallback、fundamentals）提供当日级别的 DB 缓存，避免同日同 ticker 多次触发 FMP 请求。有效期 = 当日（`as_of_date == date.today()`），下一交易日自动失效。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| ticker | String(10) | ✅ | 股票代码，全大写 |
| endpoint | String(20) | ✅ | 缓存端点枚举：`"chart"` / `"fundamentals"` |
| as_of_date | Date | ✅ | 缓存所属交易日（server local date） |
| payload_json | Text | ✅ | 序列化的 JSON 字符串（响应 data 字段） |
| cached_at | DateTime | ✅ | 写入 UTC 时间戳 |

**业务规则**：
- 联合唯一索引 `(ticker, endpoint, as_of_date)`
- 命中条件：`as_of_date == date.today()`；跨日记录保留但不再被服务层读取（自然过期）
- 只缓存成功响应（FMP 抛 httpx.HTTPError → 不写入；FMP 返回空 → 不写入，走原有 null 路径）
- Watchlist ticker chart 仍走 `daily_bars` 表，不写入此表
- 无需清理旧记录（数据量极小：每天最多几十行）

---

## NewsArticleCache（News 文章缓存）

> 对应数据库表：`news_articles_cache`
> Feature：F113-a（2026-04-23）
> 决策依据：D057

按自然日存储 FMP `/stable/fmp-articles` 文章，用于 `GET /api/news/articles` 缓存优先 + 增量模式。有效窗口 = `as_of_date IN (today, yesterday)`，旧行自然过期（不做 vacuum）。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| article_key | String(512) | ✅ | 去重主键：优先用 FMP `link` URL；缺失时 `SHA-256(title + publishedAt[:19])` |
| published_at | DateTime | ✅ | 文章发布 UTC 时间（naive） |
| as_of_date | Date | ✅ | 服务端本地写入日期（用于窗口过滤） |
| payload_json | Text | ✅ | 完整 `NewsArticle` JSON（title/contentHtml/symbols/imageUrl/url/author/site） |
| cached_at | DateTime | ✅ | 写入 UTC 时间戳（naive） |

**索引**：
- 唯一：`(as_of_date, article_key)` — 防重复写入（`uq_news_articles_cache_date_key`）
- 辅助：`(as_of_date, published_at DESC)` — 读列表按时间倒序
- 单列：`as_of_date`、`published_at`

---

## ── Cockpit Epic 新增实体（v1.8 / v1.9 / v2.0）──

> 以下 7 张表全部在 `backend/app/models/cockpit/` 新目录下定义（或独立文件，保持与 workbench models 零交叉依赖）；Alembic 迁移 `xxxx_cockpit_initial.py`。

---

## MarketRegimeSnapshot（每日 regime 打分快照）

> 对应数据库表：`market_regime_snapshots`
> Feature：F201 Market Regime Widget
> 决策依据：D061

每日 APScheduler 计算一条，按 date 唯一。Market Score = SPY trend 25 + QQQ trend 20 + IWM breadth 15 + Sector participation 20 + Risk appetite 10 + Volatility stress 10 = 100 分。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| date | Date | ✅ | regime 所属交易日（美东日历），唯一索引 |
| regime | String(16) | ✅ | regime 枚举（见下方） |
| market_score | Integer | ✅ | 0-100 总分 |
| spy_trend_score | Integer | ✅ | SPY 子项分（0-25） |
| qqq_trend_score | Integer | ✅ | QQQ 子项分（0-20） |
| iwm_breadth_score | Integer | ✅ | IWM 子项分（0-15） |
| sector_participation_score | Integer | ✅ | 11 sector ETF 聚合分（0-20） |
| risk_appetite_score | Integer | ✅ | Risk-on vs Risk-off 子项分（0-10） |
| volatility_stress_score | Integer | ✅ | Volatility 子项分（0-10） |
| allowed_exposure_pct | Float | ✅ | 推荐允许的总仓位百分比（0-100） |
| single_trade_risk_pct | Float | ✅ | 单笔推荐风险百分比（如 0.5 / 1.0 / 1.5） |
| preferred_setups | Text (JSON) | ✅ | 推荐 setup 类型数组的 JSON 字符串 |
| avoid_setups | Text (JSON) | ✅ | 规避 setup 类型数组的 JSON 字符串 |
| computed_at | DateTime | ✅ | UTC 计算时间戳 |

**regime 枚举**：

| 值 | 含义 | 典型 allowed_exposure_pct | single_trade_risk_pct |
|----|------|-------|-------|
| RISK_ON | 全面风险偏好 | 80–100 | 1.5 |
| CONSTRUCTIVE | 建设性 | 60–80 | 1.0 |
| NEUTRAL | 中性 | 40–60 | 0.75 |
| DEFENSIVE | 防守 | 20–40 | 0.5 |
| RISK_OFF | 避险 | 0–20 | 0 |

（阈值 → regime 的映射算法在 `backend/app/services/cockpit/market_regime_service.py`，默认阈值写入 DECISIONS.md D061；配置可覆盖。）

**业务规则**：
- `date` 唯一索引
- 每日盘后 APScheduler（`REGIME_CRON_*` 新 env，默认与 `REFRESH_CRON_*` 错开 5 分钟）计算并 upsert
- 保留最近 **90 天**快照（便于前端展示 regime 变化史、AI Market Narrator 引用上下文）
- 数据不足（market_indices 17 个 symbol 中任一缺失当日 bar）时，子项分给 null 并跳过整行写入，SystemLog 记 WARN

---

## SetupSnapshot（Cockpit watchlist 每日结构化 setup 快照）

> 对应数据库表：`setup_snapshots`
> Feature：F202 Setup Monitor Widget
> 决策依据：D062

Cockpit 专属，每日计算 watchlist 每只 active 股票的 setup 快照。与 workbench `signals` 表完全独立（不扩 signals），避免污染 SMA150 信号语义。按 `(ticker, scan_date)` 唯一。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| ticker | String(10) | ✅ | 股票代码，全大写（不 FK `stocks.ticker`，与 market_breakout_scans 一致） |
| scan_date | Date | ✅ | 快照所属交易日 |
| setup_type | String(24) | ✅ | setup 类型枚举（见下方） |
| setup_quality | String(1) | ❌ | A/B/C（NONE 时为 null） |
| entry_price | Float | ❌ | 推荐 entry 价（NONE 时 null） |
| stop_price | Float | ❌ | 推荐 stop 价 |
| target_2r | Float | ❌ | 2R 目标 |
| target_3r | Float | ❌ | 3R 目标 |
| distance_to_entry_pct | Float | ❌ | (entry - last_close) / last_close × 100；负值表示已穿越 |
| reward_risk | Float | ❌ | (target_2r - entry) / (entry - stop) |
| rs_percentile | Float | ❌ | 相对 SPY 的 250 日 return ratio 分位（0-100） |
| volume_status | String(8) | ❌ | HIGH / NORMAL / LOW（基于 20 日成交量比） |
| trend_score | Integer | ❌ | 0-5（MA10>MA21>MA50>MA150>MA200 阶梯加分） |
| earnings_risk | String(8) | ✅ | SAFE / CAUTION / DANGER，依赖 `earnings_events` join |
| ready_signal | Boolean | ✅ | 全 8 条 AND 门是否满足（trend≥4 & rs≥70 & quality≥B & dist≤3% & R:R≥2 & earnings≠Danger & regime≠Risk-Off & weekly_stage==2）（F216-d2 / D093） |
| suggested_action | String(16) | ❌ | enter / watch / wait / reduce / exit / null |
| volume_zscore | Float | ❌ | 当日 volume 相对过去 N 日（默认 50）均量的 z-score；`(vol - mean) / std`；`std==0` 或 bars 不足 N+1 时为 null（F215-b / D087） |
| obv_trend | VARCHAR(4) | ❌ | OBV 趋势：`'UP'`（20 日 OBV 变化 > +2%）/ `'DOWN'`（< -2%）/ `'FLAT'`（其余）；历史不足或 OBV 基值为 0 时为 null（F215-b / D087） |
| up_down_volume_ratio | Float | ❌ | O'Neil U/D ratio：近 50 日上涨日成交量总和 ÷ 下跌日成交量总和；无下跌日（分母为 0）时为 null（F215-b / D087） |
| weekly_stage | Integer | ❌ | Stan Weinstein Stage 1-4（0=UNKNOWN；NULL=该日 cron 未跑到 weekly_stage 阶段）。来源：weekly_stage_snapshots.stage 当日同 ticker upsert。ready_signal 强制要求 weekly_stage==2（F216-d2 实施） |
| macd_divergence | String(8) | ❌ | 价 vs MACD 20 日背离分类：`'bearish'`（价新高 MACD 不新高）/ `'bullish'`（价新低 MACD 不新低）/ `NULL`（无背离或 bars<50）。不参与 ready_signal 8-AND gate（F219 / D098） |
| scanned_at | DateTime | ✅ | UTC 写入时间 |

**setup_type 枚举**：

| 值 | 含义 |
|----|------|
| BREAKOUT | 突破 pivot |
| CAPITULATION | 投降式抛售反转（SRS § 五 Setup 4 严格定义：连续下跌≥10% + Vol z-score≥2.5 + true_range≥2×ATR14 + 收盘脱底1/3 + 次日不创新低 + higher low + RS 止跌；F217 / D095 引入） |
| RECLAIM | 重夺关键价 |
| EARNINGS_DRIFT | 财报后延伸 |
| EXTENDED | 过度延伸（不可追） |
| BROKEN | 结构破位 |
| NONE | 无结构化 setup |

> ⚠️ 历史枚举值 `PULLBACK` 已于 F217 (Phase C) 移除（与 SRS Setup 4 语义错位）。历史 `setup_snapshots` 行通过 F217-b alembic 021 软删（plan §C4：保留行加 `legacy=true` 标记或 `purge_legacy_pullback()`）；新代码不得再产生 PULLBACK 行。

**业务规则**：
- `(ticker, scan_date)` 联合唯一索引
- 每日 APScheduler（与 `signals` 同批次触发，复用 EOD 刷新事务；`SETUP_CRON_*` 可选独立 env）计算并 upsert
- 保留最近 **60 天**快照（供 F210 AI ranker 回看最近表现 + F211 contradiction 检测历史）
- `ready_signal` 计算依赖 `market_regime_snapshots.regime` 当日值，数据缺失时视为 NEUTRAL
- 不写命中/未命中过滤：**所有 watchlist active 股票每日必写一行**（setup_type=NONE 也要写，便于前端统一展示）
- **BREAKOUT 吸筹门槛（F215-b / D088）**：候选达到 BREAKOUT 条件后，还必须同时满足 `volume_zscore ≥ 1.5`（`VOL_ACC_BREAKOUT_Z_MIN`）AND `up_down_volume_ratio ≥ 1.2`（`VOL_ACC_BREAKOUT_UD_MIN`）；任一不达标（含 `volume_zscore=None` 短历史）则 `setup_type` **直接降级为 NONE**，不 fall-through 到 CAPITULATION / RECLAIM。历史快照 3 列保持 NULL 直至下次 cron 自然填充（不回填）
- **\_classify\_setup\_type 优先级（F217 / D095）**：`BROKEN → EXTENDED → EARNINGS_DRIFT → CAPITULATION → BREAKOUT → RECLAIM → NONE`。CAPITULATION 排在 BREAKOUT/RECLAIM 之前是因为投降底语义与正向突破/重夺互斥；同一日同标的命中 CAPITULATION 后即停止后续分类
- **Weekly Stage 门禁（F216-d2 / D093）**：`ready_signal` 第 8 条 AND 门要求 `weekly_stage == 2`（Stan Weinstein Advancing）；`NULL/0/1/3/4` 一律视为不满足 → `ready_signal=False`。预期减少 ready=true 标的 30-50%，回避 Stage 3 顶部分布与 Stage 4 下跌中的低胜率 setup。可通过 `SETUP.READY_REQUIRE_STAGE2=False` 关闭门禁（默认开启）。weekly_stage 来自 `weekly_stage_snapshots.stage` 最新一行 join（cron 顺序保证 regime→weekly_stage→setup）

---

## EarningsEvent（财报事件，仅 cockpit 消费）

> 对应数据库表：`earnings_events`
> Feature：F204 Earnings Calendar 接入
> 决策依据：D065

FMP `/stable/earnings-calendar` 每日增量拉取未来 30 天 earnings 事件。按 `(ticker, earnings_date)` 唯一。Workbench / News widget 严禁消费（代码审查规则）。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| ticker | String(10) | ✅ | 股票代码，全大写 |
| earnings_date | Date | ✅ | 财报日期（美东日历） |
| eps_estimate | Float | ❌ | EPS 预期 |
| eps_actual | Float | ❌ | EPS 实际（公布后回填） |
| revenue_estimate | BigInteger | ❌ | 营收预期（美元） |
| revenue_actual | BigInteger | ❌ | 营收实际 |
| time_of_day | String(8) | ❌ | BMO（盘前）/ AMC（盘后）/ DMH（盘中）/ null |
| fetched_at | DateTime | ✅ | 最近一次从 FMP upsert 的 UTC 时间 |

**业务规则**：
- `(ticker, earnings_date)` 联合唯一索引（UPSERT 键）
- 每日 APScheduler（`EARNINGS_CRON_*` 新 env，默认 05:30 在 regime 之前）增量拉取：查询窗口 `from=today, to=today+30`，并补拉 `from=today-7, to=today-1`（已发生未入库的）合并 upsert
- estimate 字段会变，upsert 时**完整覆盖** estimate / time_of_day / fetched_at；eps_actual / revenue_actual 只在非空时覆盖（避免 FMP 尚未回填时擦掉已有数据）
- **消费边界**：仅 `backend/app/services/cockpit/*` 读取；Workbench / News 路由禁止 import earnings_events model
- 距今 > 60 天的历史 earnings 每月 universe refresh 时清理（保留 60 天审计窗口）

---

## UserSettings（账户配置，单行单用户）

> 对应数据库表：`user_settings`
> Feature：F203 Decision Panel
> 决策依据：D066

严格单行设计。`id` 硬编码为 `1`，所有 upsert 走 `id=1`。不做认证、不存多用户。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，常量 1（CHECK 约束 `id=1`） |
| account_size | Float | ✅ | 账户总额（美元），默认 100000 |
| max_exposure_pct | Float | ✅ | 总仓位上限百分比（0-100），默认 80 |
| single_trade_risk_pct | Float | ✅ | 单笔最大风险百分比，默认 1.0 |
| default_risk_per_trade_pct | Float | ✅ | 默认每笔风险百分比（position size 计算用），默认 0.75 |
| base_currency | String(8) | ✅ | 默认 "USD" |
| updated_at | DateTime | ✅ | 最后修改 UTC 时间 |

**业务规则**：
- 首次启动自动插入默认值（Alembic data migration）
- PUT 接口 upsert id=1 一行
- GET 接口若行不存在，返回默认值但不写库（防止读操作写库）
- position size 计算公式：`floor(account_size × risk_pct / (entry - stop))`；其中 `risk_pct` 按 `market_regime_snapshots.single_trade_risk_pct` 动态调整（regime 优先于 user_settings）

---

## Position（持仓，手动录入）

> 对应数据库表：`positions`
> Feature：F206 Position Manager
> 决策依据：D067

嘉信证券无 API，全手动录入。`ticker` 为字符串，不 FK（允许非 watchlist ticker 录入）。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| ticker | String(10) | ✅ | 股票代码，全大写 |
| entry_price | Float | ✅ | 开仓均价 |
| entry_date | Date | ✅ | 开仓日期 |
| shares | Integer | ✅ | 持股数量（正整数） |
| stop_price | Float | ✅ | 当前止损位 |
| target_2r | Float | ❌ | 2R 目标价 |
| target_3r | Float | ❌ | 3R 目标价 |
| setup_type | String(24) | ❌ | 开仓时的 setup 类型（SetupSnapshot 枚举） |
| notes | Text | ❌ | 用户自由备注 |
| status | String(8) | ✅ | OPEN / CLOSED；默认 OPEN |
| closed_at | DateTime | ❌ | 平仓 UTC 时间（CLOSED 时必填） |
| close_price | Float | ❌ | 平仓均价（CLOSED 时必填） |
| created_at | DateTime | ✅ | 记录创建 UTC 时间 |
| updated_at | DateTime | ✅ | 最后修改 UTC 时间 |

**业务规则**：
- R multiple 计算（服务端实时，每次 GET 计算不持久化）：`(last_close - entry_price) / (entry_price - stop_price)`；`last_close` 优先取 `daily_bars` 最新一行（仅 watchlist），否则走 on-demand fallback（D041）拉一次 FMP
- 平仓（status 改为 CLOSED）时自动触发 F211 `journal_assistant`（v2.0 AI feature），将复盘结果写入 `journal_entries.ai_review` 字段（v2.0 新字段，**非本 Epic 加**，留待 F211 feature-dev 阶段 Alembic 迁移）
- 状态变更审计：updated_at 自动更新
- **与 JournalEntry 的关系**：positions 记"当前持仓实时状态"，journal_entries 记"每次交易事件"；两者不 FK、不冗余、通过 ticker + 时间关联
- 软删除不做：用户真要删就硬删（DELETE），持仓数据量小

---

## PendingOrder（条件单计划，手动录入）

> 对应数据库表：`pending_orders`
> Feature：F206 Position Manager
> 决策依据：D067

用户在 app 里维护的"准备好去券商手动下单的计划"。**不真实下单**（no broker integration）。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| ticker | String(10) | ✅ | 股票代码，全大写 |
| setup_type | String(24) | ✅ | setup 类型（SetupSnapshot 枚举） |
| entry_price | Float | ✅ | 计划 entry 价 |
| stop_price | Float | ✅ | 计划 stop 价 |
| shares | Integer | ✅ | 计划股数 |
| target_2r | Float | ❌ | 2R 目标 |
| target_3r | Float | ❌ | 3R 目标 |
| expiration_date | Date | ❌ | 计划有效期（到期自动转 EXPIRED） |
| status | String(16) | ✅ | ACTIVE / TRIGGERED / CANCELLED / EXPIRED；默认 ACTIVE |
| notes | Text | ❌ | 备注 |
| created_at | DateTime | ✅ | 创建 UTC 时间 |
| updated_at | DateTime | ✅ | 最后修改 UTC 时间 |

**业务规则**：
- 无唯一索引（同 ticker 可以有多个不同 setup 的计划）
- 辅助索引：`status`（筛 ACTIVE 常用）、`ticker`
- 状态流转：ACTIVE → {TRIGGERED by 用户 / CANCELLED by 用户 / EXPIRED by 调度器}
- APScheduler 每日（复用 `REFRESH_CRON_*` 的末尾阶段）扫描所有 ACTIVE 行，过期则置 EXPIRED
- 用户实际下单后手动 PATCH status=TRIGGERED（可选联动自动创建 Position，v1.9 feature-dev 阶段决定）

---

## AiMemo（AI 调用审计 + 去重缓存）

> 对应数据库表：`ai_memos`
> Feature：F208 LLM Gateway
> 决策依据：D069

每次 AI 调用完整落库，既是 audit log 也是去重缓存基底（输入哈希命中 + 未过期 → 可复用，无需重新打 LLM）。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| task_type | String(32) | ✅ | 6 种之一（见下方枚举） |
| input_hash | String(64) | ✅ | SHA-256(input_dict 的 canonical JSON) |
| input_json | Text | ✅ | 原始 input（审计用，不写敏感数据） |
| output_json | Text | ✅ | schema-validated output 的 JSON |
| schema_version | String(16) | ✅ | 对应 `backend/app/ai/schemas/` 版本号（e.g. "v1"），供未来 schema 变更 invalidate 旧 memo |
| model_used | String(64) | ✅ | LiteLLM model 字符串（如 "gpt-5.4-nano"） |
| tier | String(16) | ✅ | default / critical / complex |
| tokens_in | Integer | ✅ | prompt tokens |
| tokens_out | Integer | ✅ | completion tokens |
| cost_usd | Numeric(10, 6) | ✅ | 费用美元（LiteLLM cost_tracking） |
| latency_ms | Integer | ✅ | LLM 调用耗时毫秒 |
| created_at | DateTime | ✅ | UTC 创建时间 |

**索引**：
- 辅助：`(task_type, input_hash, created_at DESC)` — 去重缓存查询主入口
- 辅助：`created_at DESC` — 月度 budget 统计扫描

**task_type 枚举**（8 种，Pydantic `Literal` 校验）：

| 值 | Tier | Feature |
|----|------|---------|
| market_narrator | default | F209 |
| setup_explainer | default | F209 |
| candidate_ranker | critical | F210 |
| trade_plan | critical | F210 |
| contradiction_detector | default | F211 |
| news_summarizer | default | F211 |
| journal_assistant | complex | F211 |
| translate_article | default | F213（DeepSeek via per-task override，D084） |

> ⚠️ 以上 8 行对应 8 个 task_type；F211 包含 3 个 task（contradiction/news=default, journal=complex）；F213 默认 default tier 但通过 `AI_TASK_OVERRIDES_JSON` 接入 DeepSeek（D084）。

**业务规则**：
- `input_hash` 计算：对 input_dict 做 `json.dumps(obj, sort_keys=True, separators=(',',':'))` 后 SHA-256；保证相同输入产生相同哈希
- 去重缓存策略：LLM gateway 调用前先查 `(task_type, input_hash, schema_version)` 最近 N 小时内（默认 24h，配置化），命中则直接返回 `output_json`，不打 LLM
- Budget 熔断：月初到当前时刻 `SUM(cost_usd)` ≥ `AI_MONTHLY_BUDGET_USD` → gateway 抛 `AiBudgetExceeded`，**不降级不 fallback**
- schema_version 变更时旧 memo 自动不命中缓存（天然 invalidate）
- 保留策略：保留最近 **180 天**，超期 APScheduler 清理（audit 需求有限）

---



```python
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime, Text,
    BigInteger, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime, timezone


class Base(DeclarativeBase):
    pass


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    exchange = Column(String(20), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    added_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_refreshed_at = Column(DateTime, nullable=True)

    daily_bars = relationship("DailyBar", back_populates="stock")
    signals = relationship("Signal", back_populates="stock")
    pullbacks = relationship("Pullback", back_populates="stock")
    journal_entries = relationship("JournalEntry", back_populates="stock")


class DailyBar(Base):
    __tablename__ = "daily_bars"
    __table_args__ = (
        UniqueConstraint("stock_id", "date", name="uq_daily_bar_stock_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(BigInteger, nullable=False)

    stock = relationship("Stock", back_populates="daily_bars")


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        UniqueConstraint("stock_id", "date", name="uq_signal_stock_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    signal_type = Column(String(20), nullable=False)
    ma150_value = Column(Float, nullable=True)
    close_price = Column(Float, nullable=False)
    distance_pct = Column(Float, nullable=True)
    slope_positive = Column(Boolean, nullable=True)
    slope_value = Column(Float, nullable=True)

    stock = relationship("Stock", back_populates="signals")


class Pullback(Base):
    __tablename__ = "pullbacks"
    __table_args__ = (
        UniqueConstraint("stock_id", "date", name="uq_pullback_stock_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    close_price = Column(Float, nullable=False)
    ma150_value = Column(Float, nullable=False)
    distance_pct = Column(Float, nullable=False)
    return_10d = Column(Float, nullable=True)
    return_20d = Column(Float, nullable=True)
    return_30d = Column(Float, nullable=True)

    stock = relationship("Stock", back_populates="pullbacks")


class MarketIndex(Base):
    __tablename__ = "market_indices"
    __table_args__ = (
        UniqueConstraint("symbol", "date", name="uq_market_index_symbol_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    date = Column(Date, nullable=False, index=True)
    close = Column(Float, nullable=False)
    prev_close = Column(Float, nullable=True)
    change_pct = Column(Float, nullable=True)


class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(String(10), nullable=False)
    source = Column(String(50), nullable=False)
    message = Column(String(500), nullable=False)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    action = Column(String(10), nullable=False)
    price = Column(Float, nullable=False)
    date = Column(Date, nullable=False, index=True)
    position_size = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    reference = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    stock = relationship("Stock", back_populates="journal_entries")


class MarketScanUniverse(Base):
    __tablename__ = "market_scan_universe"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, unique=True, index=True)
    company_name = Column(String(200), nullable=False)
    exchange = Column(String(20), nullable=False)
    market_cap = Column(BigInteger, nullable=False)
    last_seen_at = Column(DateTime, nullable=False)
    added_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class MarketBreakoutScan(Base):
    __tablename__ = "market_breakout_scans"
    __table_args__ = (
        UniqueConstraint(
            "scan_date", "ticker", "signal_type",
            name="uq_breakout_scan_date_ticker_signal",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_date = Column(Date, nullable=False, index=True)
    ticker = Column(String(10), nullable=False)
    company_name = Column(String(200), nullable=False)
    signal_type = Column(String(32), nullable=False, index=True)
    close_price = Column(Float, nullable=False)
    ma150_value = Column(Float, nullable=False)
    pct_above_ma150 = Column(Float, nullable=False)
    slope_value = Column(Float, nullable=False)
    volume = Column(BigInteger, nullable=True)
    volume_ratio_20 = Column(Float, nullable=True)
    market_cap = Column(BigInteger, nullable=False)
    scanned_at = Column(DateTime, nullable=False, index=True)


class DailyPayloadCache(Base):
    __tablename__ = "daily_payload_cache"
    __table_args__ = (
        UniqueConstraint(
            "ticker", "endpoint", "as_of_date",
            name="uq_daily_payload_cache_ticker_endpoint_date",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    endpoint = Column(String(20), nullable=False)
    as_of_date = Column(Date, nullable=False)
    payload_json = Column(Text, nullable=False)
    cached_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


# ── Cockpit Epic 新增 ORM（v1.8 / v1.9 / v2.0） ──
# 以下 7 张表建议放入 backend/app/models/cockpit/*.py（或保持平铺，但命名 cockpit_*.py）
# 与 workbench 既有 models 零交叉引用（依赖层级规则硬约束）

from sqlalchemy import Numeric, CheckConstraint  # 补充导入


class MarketRegimeSnapshot(Base):
    __tablename__ = "market_regime_snapshots"
    __table_args__ = (
        UniqueConstraint("date", name="uq_market_regime_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    regime = Column(String(16), nullable=False)
    market_score = Column(Integer, nullable=False)
    spy_trend_score = Column(Integer, nullable=False)
    qqq_trend_score = Column(Integer, nullable=False)
    iwm_breadth_score = Column(Integer, nullable=False)
    sector_participation_score = Column(Integer, nullable=False)
    risk_appetite_score = Column(Integer, nullable=False)
    volatility_stress_score = Column(Integer, nullable=False)
    allowed_exposure_pct = Column(Float, nullable=False)
    single_trade_risk_pct = Column(Float, nullable=False)
    preferred_setups = Column(Text, nullable=False)   # JSON array
    avoid_setups = Column(Text, nullable=False)       # JSON array
    computed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class SetupSnapshot(Base):
    __tablename__ = "setup_snapshots"
    __table_args__ = (
        UniqueConstraint("ticker", "scan_date", name="uq_setup_snapshot_ticker_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    scan_date = Column(Date, nullable=False, index=True)
    setup_type = Column(String(24), nullable=False)
    setup_quality = Column(String(1), nullable=True)
    entry_price = Column(Float, nullable=True)
    stop_price = Column(Float, nullable=True)
    target_2r = Column(Float, nullable=True)
    target_3r = Column(Float, nullable=True)
    distance_to_entry_pct = Column(Float, nullable=True)
    reward_risk = Column(Float, nullable=True)
    rs_percentile = Column(Float, nullable=True)
    volume_status = Column(String(8), nullable=True)
    trend_score = Column(Integer, nullable=True)
    earnings_risk = Column(String(8), nullable=False)
    ready_signal = Column(Boolean, nullable=False, default=False)
    suggested_action = Column(String(16), nullable=True)
    macd_divergence = Column(String(8), nullable=True)
    scanned_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class EarningsEvent(Base):
    __tablename__ = "earnings_events"
    __table_args__ = (
        UniqueConstraint("ticker", "earnings_date", name="uq_earnings_event_ticker_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    earnings_date = Column(Date, nullable=False, index=True)
    eps_estimate = Column(Float, nullable=True)
    eps_actual = Column(Float, nullable=True)
    revenue_estimate = Column(BigInteger, nullable=True)
    revenue_actual = Column(BigInteger, nullable=True)
    time_of_day = Column(String(8), nullable=True)
    fetched_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class UserSettings(Base):
    __tablename__ = "user_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_user_settings_single_row"),
    )

    id = Column(Integer, primary_key=True)  # 常量 1
    account_size = Column(Float, nullable=False, default=100000.0)
    max_exposure_pct = Column(Float, nullable=False, default=80.0)
    single_trade_risk_pct = Column(Float, nullable=False, default=1.0)
    default_risk_per_trade_pct = Column(Float, nullable=False, default=0.75)
    base_currency = Column(String(8), nullable=False, default="USD")
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    entry_price = Column(Float, nullable=False)
    entry_date = Column(Date, nullable=False)
    shares = Column(Integer, nullable=False)
    stop_price = Column(Float, nullable=False)
    target_2r = Column(Float, nullable=True)
    target_3r = Column(Float, nullable=True)
    setup_type = Column(String(24), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(8), nullable=False, default="OPEN", index=True)
    closed_at = Column(DateTime, nullable=True)
    close_price = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class PendingOrder(Base):
    __tablename__ = "pending_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    setup_type = Column(String(24), nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_price = Column(Float, nullable=False)
    shares = Column(Integer, nullable=False)
    target_2r = Column(Float, nullable=True)
    target_3r = Column(Float, nullable=True)
    expiration_date = Column(Date, nullable=True)
    status = Column(String(16), nullable=False, default="ACTIVE", index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AiMemo(Base):
    __tablename__ = "ai_memos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_type = Column(String(32), nullable=False, index=True)
    input_hash = Column(String(64), nullable=False, index=True)
    input_json = Column(Text, nullable=False)
    output_json = Column(Text, nullable=False)
    schema_version = Column(String(16), nullable=False)
    model_used = Column(String(64), nullable=False)
    tier = Column(String(16), nullable=False)
    tokens_in = Column(Integer, nullable=False)
    tokens_out = Column(Integer, nullable=False)
    cost_usd = Column(Numeric(10, 6), nullable=False)
    latency_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
```


## CockpitPoolCache（F205-e）

```python
class CockpitPoolCache(Base):
    __tablename__ = "cockpit_pool_cache"

    ticker        = Column(Text,     primary_key=True)
    rs_percentile = Column(Float,    nullable=False)
    ma50          = Column(Float,    nullable=True)   # 250d 序列后 50 日均值
    last_close    = Column(Float,    nullable=True)   # 250d 序列最后一日 close
    revenue_growth_yoy = Column(Float, nullable=True) # null = FMP 未返回（fail-open）
    computed_at   = Column(DateTime, nullable=False)

    __table_args__ = (Index("ix_cockpit_pool_cache_computed_at", "computed_at"),)
```

**更新策略**：整表替换（每周一次 `DELETE + INSERT`，在事务内原子执行）。

**范围（Q1=A）**：仅缓存最新 breakout_scans 中的 trend tickers（~50 个）。RS percentile 相对于当次 rebuild 时的 trend 总体计算。

**Cache miss**：表为空时 PoolService 返回空 funnel（rs=0, fundamental=0, action=0）+ WARN 日志，不 fallback 实时 FMP（Q3=A）。


## WeeklyStageSnapshot（F216-b — Stan Weinstein Stage 1-4 周线快照）

> 对应数据库表：`weekly_stage_snapshots`
> Feature：F216-b Weekly Stage Classifier + 持久化
> 决策依据：D091（Stage 量化判定细则）/ D092（引入 numpy 的范围与版本约束）

Cockpit 专属，每周对 active stocks 计算 Stan Weinstein Stage 分类并持久化。以 `(ticker, scan_date)` 唯一（NP3/NP4），每周 upsert 一行。`scan_date` = 本周最后实际交易日（周 bar 的 date）。数据不足时仍写入 `stage=0(UNKNOWN)`，其他字段 null（NP7）。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| ticker | String(10) | ✅ | 股票代码，全大写，有独立 index |
| scan_date | Date | ✅ | 本周最后实际交易日（= weekly_bars[-1].date），有独立 index |
| stage | Integer | ✅ | 0=UNKNOWN / 1=Base / 2=Advancing / 3=Distribution / 4=Declining（NP3） |
| weekly_close | Float | ❌ | 本周收盘价；UNKNOWN 时 null |
| weekly_ma_10 | Float | ❌ | 10 周 SMA；数据不足时 null |
| weekly_ma_30 | Float | ❌ | 30 周 SMA；数据不足时 null |
| weekly_ma_40 | Float | ❌ | 40 周 SMA；数据不足时 null |
| slope_30w | Float | ❌ | 30wMA 斜率，单位 %/周（OLS 归一化：`beta/mean_y*100`）；数据不足时 null（NP2） |
| computed_at | DateTime | ✅ | UTC 计算时间戳 |

**唯一约束**：`uq_weekly_stage_ticker_date (ticker, scan_date)`

**Stage 分类规则**（优先级从高到低，详见 D091）：
1. `weekly_bars < 30 周` → UNKNOWN
2. `slope_30w > 0.5% AND close > 30wMA AND (10wMA IS NULL OR 10wMA > 30wMA)` → Stage 2
3. `slope_30w < -0.5% AND close < 30wMA` → Stage 4
4. `|slope_30w| ≤ 2% AND |close - 30wMA|/30wMA ≤ 3%` → Stage 1
5. `|slope_30w| ≤ 2% AND 过去 10 周穿越次数 ≥ 3` → Stage 3
6. 其余 → UNKNOWN（不强行归类）

**保留策略**：`WEEKLY_STAGE_RETENTION_DAYS = 60`（与 SetupSnapshot 对齐），由 F216-e cron 负责清理旧行。

**下游依赖**：F216-c router（`GET /cockpit/chart/{ticker}/weekly` 附带 stage 字段）；F216-d setup_service ready_signal gate（stage ≠ 2 → ready_signal=false）；F216-e cron（22:20 UTC 触发 `compute_and_store_all`）。

```python
class WeeklyStageSnapshot(Base):
    __tablename__ = "weekly_stage_snapshots"
    __table_args__ = (
        UniqueConstraint("ticker", "scan_date", name="uq_weekly_stage_ticker_date"),
    )

    id          = Column(Integer, primary_key=True, autoincrement=True)
    ticker      = Column(String(10), nullable=False, index=True)
    scan_date   = Column(Date, nullable=False, index=True)   # 本周最后实际交易日（NP4）
    stage       = Column(Integer, nullable=False)             # 0=UNKNOWN, 1-4（NP3）
    weekly_close = Column(Float, nullable=True)
    weekly_ma_10 = Column(Float, nullable=True)
    weekly_ma_30 = Column(Float, nullable=True)
    weekly_ma_40 = Column(Float, nullable=True)
    slope_30w   = Column(Float, nullable=True)               # %/周，OLS 归一化（NP2）
    computed_at = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
```


## RepricingTrigger（F218 Phase D — 重定价触发信号）

> 对应数据库表：`repricing_triggers`
> Feature：F218 Cockpit Phase D — Repricing Trigger 完整框架（5 类）
> 决策依据：D096（5 类框架 + evidence_json 单列设计）

Cockpit 专属。识别"让市场重新定价此公司"的基本面/产业/资产负债事件，与价格 setup 解耦但在慢交易框架（4 支柱第 4 个）中决定持仓周期与仓位规模。串行调度 5 个 detector，每日 22:40 UTC 后写入；`active` 标记长期保留 + soft expire（非物理删）。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| ticker | String(10) | ✅ | 股票代码，全大写，有独立 index |
| trigger_type | String(24) | ✅ | 枚举 5 选 1：`EARNINGS_ACCEL` / `MARGIN_EXPANSION` / `NEW_PRODUCT` / `SECTOR_CYCLE` / `BALANCE_INFLECTION` |
| detected_date | Date | ✅ | trigger 触发日（= compute_and_store_all_triggers 调度日），有独立 index |
| confidence | Float | ✅ | 0.0-1.0 置信度，由各 detector 按命中条件强度打分（详见 detector 规则） |
| evidence_json | Text | ✅ | 证据 JSON 字符串，按 trigger_type 区分 schema（见下）；service 内 dataclass 反序列化 |
| active | Boolean | ✅ | true=当前 active；false=已 expire（detector 在后续日 re-scan 时未再命中即 soft expire） |
| computed_at | DateTime | ✅ | UTC 计算时间戳 |

**唯一约束**：`uq_repricing_trigger_ticker_type_date (ticker, trigger_type, detected_date)` — 同一标的同一 trigger 类型每日至多一条；同类型多次触发用 detected_date 区分。

**evidence_json schema（按 trigger_type 区分）**：

| trigger_type | evidence_json 字段示例 |
|-------------|----------------------|
| `EARNINGS_ACCEL` | `{"eps_yoy_growth": [0.18, 0.24, 0.32], "revenue_yoy_growth": [0.12, 0.15, 0.22], "quarters": ["2025Q3", "2025Q4", "2026Q1"]}` |
| `MARGIN_EXPANSION` | `{"gross_margin_trend": [0.42, 0.44, 0.46], "fcf_margin_trend": [0.18, 0.22, 0.25], "quarters": [...], "trigger_metric": "gross_margin", "expansion_bp": 400}` |
| `NEW_PRODUCT` | `{"keyword_hits": [{"keyword": "AI", "count": 3}, {"keyword": "launch", "count": 2}], "news_links": ["url1", "url2"], "scan_window_days": 30}` |
| `SECTOR_CYCLE` | `{"sector": "XLK", "rs_history": [{"date": "2026-03-01", "percentile": 35}, {"date": "2026-05-01", "percentile": 65}], "price_vs_200d": 1.08}` |
| `BALANCE_INFLECTION` | `{"net_debt_trend": [120000000, 105000000, 95000000], "fcf_trend": [-15000000, 8000000, 22000000], "quarters": [...], "trigger_metric": "net_debt"}` |

**业务规则**：
- 每日 22:40 UTC（refresh_job cron，setup_tick 之后）调用 `RepricingTriggerService.compute_and_store_all_triggers(date)`，串行调用 5 个 `_detect_*` 函数
- 同一 (ticker, trigger_type) 已存在 active 行 + 当日 re-detect 仍命中 → 不写新行，更新 evidence/confidence/computed_at（detector 内部判断幂等）
- soft expire：detector re-scan 未命中（如 EARNINGS_ACCEL 在下次财报后判定条件失效）→ 将既有 active=true 行改 active=false（保留审计）
- `confidence` 默认值 0.5；EARNINGS_ACCEL 若 yoy ≥ 30% confidence=0.8；MARGIN_EXPANSION 若 expansion ≥ 400bp confidence=0.8；其余维持 0.5（D096 简化策略，可在 D4b NLP 升级时细化）
- **消费边界**：仅 `backend/app/services/cockpit/*` 与 `backend/app/routers/cockpit/*` 读写；前端通过 `/api/cockpit/repricing-triggers*` 消费
- **保留策略**：`REPRICING_TRIGGER_RETENTION_DAYS = 365`（与年度复盘窗口对齐），由 F218 cron 在 active=false 行上做硬删；active=true 行不删

```python
class RepricingTrigger(Base):
    __tablename__ = "repricing_triggers"
    __table_args__ = (
        UniqueConstraint("ticker", "trigger_type", "detected_date", name="uq_repricing_trigger_ticker_type_date"),
    )

    id            = Column(Integer, primary_key=True, autoincrement=True)
    ticker        = Column(String(10), nullable=False, index=True)
    trigger_type  = Column(String(24), nullable=False)      # 5 类枚举
    detected_date = Column(Date, nullable=False, index=True)
    confidence    = Column(Float, nullable=False, default=0.5)
    evidence_json = Column(Text, nullable=False)             # JSON 字符串，service 内反序列化
    active        = Column(Boolean, nullable=False, default=True, index=True)
    computed_at   = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
```


## StockKeyMetricsQuarterly（F218 Phase D — T2 Margin Expansion 缓存）

> 对应数据库表：`stock_key_metrics_quarterly`
> Feature：F218 D3 T2 Margin Expansion
> 决策依据：D097（FMP 3 endpoint 接入 — income-statement / balance-sheet / cash-flow，后 2 个 T2/T5 共享 + weekly cron 复用；修正 2026-05-18）

T2 Margin Expansion detector 的季度财务比率缓存表。数据源 FMP `/stable/income-statement?period=quarter` + `/stable/cash-flow-statement?period=quarter`（与 T5 共享）+ `/stable/balance-sheet-statement?period=quarter`（与 T5 共享，roic 近似公式用）。所有 margin 字段在 service 层从原始财务数字计算（D097 修正 2026-05-18：live probe 发现 FMP Starter 不支持 `/key-metrics?period=quarter` 与 `/ratios?period=quarter`，均返 402 Premium）。按 `(ticker, fiscal_quarter)` 唯一（fiscal_quarter 拼接为 FMP `period` + " " + `fiscalYear`，如 "Q2 2026"），weekly pool rebuild（周一 06:30 UTC）同步刷新 cockpit pool 内 ~50 ticker 的最近 8 季数据。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| ticker | String(10) | ✅ | 股票代码，全大写，有独立 index |
| fiscal_quarter | String(12) | ✅ | FMP `period` + " " + `fiscalYear` 拼接（如 "Q2 2026"），业务主键 |
| period_end_date | Date | ✅ | 财季结束日（FMP `date` 字段），用于排序 |
| gross_margin | Float | ❌ | 毛利率 = grossProfit / revenue（income-statement），0-1 区间；revenue=0 或任一 null → null |
| op_margin | Float | ❌ | 营业利润率 = operatingIncome / revenue（income-statement），0-1 区间 |
| net_margin | Float | ❌ | 净利率 = netIncome / revenue（income-statement），0-1 区间 |
| fcf_margin | Float | ❌ | FCF / revenue 比率，0-1 区间；FCF = netCashProvidedByOperatingActivities + investmentsInPropertyPlantAndEquipment（cash-flow，capex 已为负值故加号） |
| roic | Float | ❌ | ROIC **近似公式**（D097 修正 2026-05-18）：`netIncome / (totalStockholdersEquity + totalDebt - cashAndShortTermInvestments)`；非标准 ROIC（不扣 NOPAT 税务调整、不剔除现金等价物）但有方向性信号；任一输入 null 或分母 ≤ 0 → null |
| fetched_at | DateTime | ✅ | 最近一次从 FMP upsert 的 UTC 时间 |

**唯一约束**：`uq_key_metrics_ticker_quarter (ticker, fiscal_quarter)`（NP-sd-2 决策）

**业务规则**：
- weekly pool rebuild 触发：对 cockpit pool 中每个 ticker，调用 FMP `/income-statement?symbol={ticker}&period=quarter&limit=8` 一次（T2 专属）+ `/cash-flow-statement?...` 一次（T2/T5 共享）+ `/balance-sheet-statement?...` 一次（T5 主用，T2 roic 近似公式复用）。共 3 endpoint 串行；T2 + T5 合计 quota 估算：~50 ticker × 3 endpoint × 周 1 次 ≈ 150 calls/week（D097 修正 2026-05-18：原 4 endpoint 含 key-metrics-ttm + ratios 不可用，且 cash-flow 由 T2/T5 共享，收敛到 3 endpoint）
- upsert 策略：按 `(ticker, fiscal_quarter)` 覆盖；FMP 返回 null 字段不擦除既有值（避免 FMP 暂时缺数据时数据丢失）
- service 层职责：从 income-statement 的 revenue/grossProfit/operatingIncome/netIncome 计算 gross/op/net margin；从 cash-flow 的 OCF + capex 计算 fcf 与 fcf_margin；从 balance-sheet 的 totalStockholdersEquity/totalDebt/cashAndShortTermInvestments + netIncome 计算 roic 近似值；任一原始字段 null 或分母 ≤ 0 → 对应 margin/roic 字段 null（不抛错，保留行）
- T2 detector 读取：取最近 2 季同比 → 毛利率扩张 ≥ 200bp 或 FCF margin 扩张 ≥ 300bp 触发
- **消费边界**：仅 `backend/app/services/cockpit/repricing_trigger_service.py` 与对应 repository 读写
- **保留策略**：保留全量历史季度（FMP 已限 limit=8，单 ticker 最多 8 行），月度 universe refresh 时清理 ticker 已退出 pool 的行

```python
class StockKeyMetricsQuarterly(Base):
    __tablename__ = "stock_key_metrics_quarterly"
    __table_args__ = (
        UniqueConstraint("ticker", "fiscal_quarter", name="uq_key_metrics_ticker_quarter"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(10), nullable=False, index=True)
    fiscal_quarter  = Column(String(12), nullable=False)      # 如 "Q1 2026"
    period_end_date = Column(Date, nullable=False)
    gross_margin    = Column(Float, nullable=True)
    op_margin       = Column(Float, nullable=True)
    net_margin      = Column(Float, nullable=True)
    fcf_margin      = Column(Float, nullable=True)
    roic            = Column(Float, nullable=True)
    fetched_at      = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
```


## StockFundamentalsQuarterly（F218 Phase D — T5 Balance Sheet Inflection 缓存）

> 对应数据库表：`stock_fundamentals_quarterly`
> Feature：F218 D6 T5 Balance Sheet Inflection
> 决策依据：D097（FMP 3 endpoint 接入 — income-statement / balance-sheet / cash-flow，后 2 个 T2/T5 共享 + weekly cron 复用；修正 2026-05-18）

T5 Balance Sheet Inflection detector 的季度资产负债 + 现金流缓存表。数据源 FMP `/stable/balance-sheet-statement?period=quarter` + `/stable/cash-flow-statement?period=quarter`（**与 T2 共享，d3a 已抓取 cash-flow 与 balance-sheet 时 d6a 在同次 pool rebuild 内复用而非重复 fetch**，D097 修正 2026-05-18）。按 `(ticker, fiscal_quarter)` 唯一（fiscal_quarter 拼接为 FMP `period` + " " + `fiscalYear`，如 "Q2 2026"），weekly pool rebuild 同步刷新。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | ✅ | 主键，自增 |
| ticker | String(10) | ✅ | 股票代码，全大写，有独立 index |
| fiscal_quarter | String(12) | ✅ | FMP `period` + " " + `fiscalYear` 拼接（如 "Q2 2026"），业务主键 |
| period_end_date | Date | ✅ | 财季结束日（FMP `date` 字段），用于排序 |
| total_debt | BigInteger | ❌ | 总债务（美元）；FMP 缺值时 null |
| cash | BigInteger | ❌ | 现金及等价物（美元） |
| net_debt | BigInteger | ❌ | 净债务 = total_debt - cash；service 层计算后持久化（FMP 不直接返回） |
| fcf | BigInteger | ❌ | 自由现金流（美元），FMP `freeCashFlow` 字段 |
| fetched_at | DateTime | ✅ | 最近一次从 FMP upsert 的 UTC 时间 |

**唯一约束**：`uq_fundamentals_ticker_quarter (ticker, fiscal_quarter)`（NP-sd-2 决策）

**业务规则**：
- weekly pool rebuild 触发：对 cockpit pool 中每个 ticker，FMP `/balance-sheet-statement?period=quarter&limit=8` + `/cash-flow-statement?period=quarter&limit=8` 各一次 — **与 T2 共享**，d3a 抓取一次后 d6a 在同次 pool rebuild 内复用结果，不重复 fetch（D097 quota 估算 2026-05-18 修正：T2 income-statement + T2/T5 共享 cash-flow + balance-sheet，合计 ~50 ticker × 3 endpoint × 周 1 次 ≈ 150 calls/week，FMP Starter 300 req/min 充裕）
- `net_debt` 在 service 层计算（`total_debt - cash`），FMP 任一字段 null → net_debt = null
- upsert 策略：按 `(ticker, fiscal_quarter)` 覆盖；FMP null 字段不擦除既有值
- T5 detector 读取：净负债连续 2 季环比下降 ≥ 5% OR FCF 从负值切为连续 2 季正 → 触发
- **消费边界**：同 StockKeyMetricsQuarterly
- **保留策略**：同 StockKeyMetricsQuarterly（limit=8，月度清理已退出 pool 的 ticker）

```python
class StockFundamentalsQuarterly(Base):
    __tablename__ = "stock_fundamentals_quarterly"
    __table_args__ = (
        UniqueConstraint("ticker", "fiscal_quarter", name="uq_fundamentals_ticker_quarter"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(10), nullable=False, index=True)
    fiscal_quarter  = Column(String(12), nullable=False)
    period_end_date = Column(Date, nullable=False)
    total_debt      = Column(BigInteger, nullable=True)
    cash            = Column(BigInteger, nullable=True)
    net_debt        = Column(BigInteger, nullable=True)        # service 层算 (total_debt - cash)
    fcf             = Column(BigInteger, nullable=True)
    fetched_at      = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
```
