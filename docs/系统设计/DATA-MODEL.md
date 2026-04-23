---
status: confirmed
confirmed_at: 2026-04-20
last_modified_by: system-design (F106 v1.3 迭代 — MarketBreakoutScan 扩展 signal_type / volume / volume_ratio_20，唯一键改为 scan_date+ticker+signal_type)
---

# DATA-MODEL.md

> 最后更新：2026-04-20 | 状态：已确认
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
- symbol 枚举：SPX（标普500）、NDX（纳斯达克）、TNX（10年期美债利率）
- 随 EOD 刷新自动更新
- 仅保留最近 5 个交易日数据（大盘只看当前，不做历史分析）
- 数据来源：SPX / NDX 通过 Polygon.io Indices API 获取，TNX 通过 Polygon.io Economy API（Treasury Yields）获取

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
| last_seen_at | DateTime | ✅ | 最近一次在 refresh 结果中出现的 UTC 时间 |
| added_at | DateTime | ✅ | 首次进入 universe 的 UTC 时间 |

**业务规则**：
- 每月 1 号自动刷新（`UNIVERSE_CRON_*` 配置）；3 次 screener 调用：分别按 `exchange=NYSE / NASDAQ / AMEX`，`marketCapMoreThan=50000000000`，合并去重
- Upsert 策略：已存在 → 更新 `company_name / exchange / market_cap / last_seen_at`；不存在 → 插入
- **不删除**"掉出 universe"的记录，保留审计痕迹。每日扫描通过 `last_seen_at >= 最近一次 refresh 时间` 筛选有效行
- 冷启动：服务启动时若表为空，自动触发一次 universe refresh 作为初始化
- 不做 FK 到 `stocks` 表，两张表职责独立

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

## ORM Schema（SQLAlchemy 2.0）

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
```
