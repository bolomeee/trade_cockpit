---
status: confirmed
confirmed_at: 2026-04-16
last_modified_by: system-design
---

# DATA-MODEL.md

> 最后更新：2026-04-16 | 状态：已确认
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

**业务规则**：
- ticker 全大写存储
- 删除股票时设 is_active = false（软删除），保留历史数据
- 重新添加同一 ticker 时恢复 is_active = true

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
```
