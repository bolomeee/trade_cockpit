---
status: confirmed
confirmed_at: 2026-04-16
last_modified_by: system-design
---

# DECISIONS.md — 技术决策记录

> 每次做了非显而易见的技术决策，Claude Code 必须在此追加记录。
> 格式统一，不得省略"放弃了什么"。
> 目的：让任何时候回来的 Claude Code 都能理解"为什么是现在这样"。

---

## D001：图表库选择 lightweight-charts

**日期**：2026-04-16
**决策**：使用 TradingView lightweight-charts 4.x
**原因**：专为金融 K 线图设计，~40KB 轻量，原生支持 OHLC 蜡烛图 + 均线叠加 + 标记点，免费开源。参考 demo：https://tradingview.github.io/lightweight-charts/tutorials/demos/moving-average
**放弃了什么**：
- ECharts（200KB+，过重，金融图表非其强项）
- Recharts（不支持 OHLC 蜡烛图）
- D3（开发量大，需从底层构建）
**影响**：前端 StockChart widget 的实现方案

---

## D002：基本面数据 MVP 阶段使用 mock

**日期**：2026-04-16
**决策**：MVP 阶段基本面数据（PE/PS/PEG/FCF）使用 mock 占位数据，API 响应中 `source: "mock"` 标识
**原因**：Polygon.io Stocks Basic tier 不含估值数据。用户计划后续升级至包含 `/stocks/financials/v1/ratios` 的 Massive 订阅
**放弃了什么**：
- Financial Modeling Prep 免费 API（250次/天限制，引入额外依赖）
- 直接省略基本面模块（用户明确需要占位，方便后续接入）
**影响**：
- GET /api/stocks/:ticker/fundamentals 返回 mock 数据
- 后续接入 Massive API 时仅需修改 external/massive_client.py + 对应 service，API 合约不变
- 字段命名已对齐 Massive API：priceToEarnings, priceToSales, freeCashFlow

---

## D003：前后端分离双容器部署

**日期**：2026-04-16
**决策**：前端 Nginx 容器 + 后端 FastAPI 容器，Docker Compose 编排
**原因**：用户要求解耦，开发调整灵活。Nginx 负责静态文件 + /api/* 反向代理
**放弃了什么**：
- 单容器（FastAPI serve 静态文件）：简单但灵活性低，前后端耦合
**影响**：需要 nginx.conf 配置反向代理、docker-compose.yml 定义两个 service

---

## D004：ORM 选择 SQLAlchemy 2.0 + Alembic

**日期**：2026-04-16
**决策**：使用 SQLAlchemy 2.0（async 模式）+ aiosqlite + Alembic 迁移
**原因**：Python 生态标准 ORM，2.0 版本原生 async 支持，与 FastAPI 配合好。Alembic 是 SQLAlchemy 标配迁移工具
**放弃了什么**：
- Tortoise ORM（社区较小，文档不完善）
- Peewee（不支持 async）
- 手动 SQL（无迁移管理，不安全）
**影响**：DATA-MODEL.md 中 ORM Schema 使用 SQLAlchemy 语法

---

## D005：调度器选择 APScheduler

**日期**：2026-04-16
**决策**：使用 APScheduler 3.x，集成在 FastAPI 进程内
**原因**：轻量级 Python 定时任务库，无需额外进程/服务。CronTrigger 支持 cron 表达式
**放弃了什么**：
- Celery + Redis（太重，单用户场景不需要分布式任务队列）
- 系统 cron（容器外部，难以管理）
**影响**：backend/app/main.py 中初始化 scheduler，美股收盘后（可配置时间）自动执行数据刷新

---

## D006：信号模型简化为 3+1 种

**日期**：2026-04-16
**决策**：信号类型定为 BREAKOUT / BUY_ZONE / NEUTRAL + INSUFFICIENT（数据不足），原先 5 种信号（TOUCH/CROSS_UP/CROSS_DOWN/EXTENDED/NEUTRAL）简化
**原因**：用户确认——核心需求是"均线斜率向上时的买入机会"，斜率为负的所有情况统一归入 NEUTRAL，降低复杂度
**放弃了什么**：
- TOUCH/CROSS_DOWN/EXTENDED 等细分信号（均线斜率为负时不产生买入信号，无需细分）
**影响**：Signal 表 signal_type 枚举值、SignalBoard 颜色系统、信号引擎判定逻辑

---

## D007：大盘数据来源

**日期**：2026-04-16
**决策**：SPX/NDX 通过 Polygon.io Indices API 获取，TNX 通过 Polygon.io Economy API（Treasury Yields）获取
**原因**：统一使用 Polygon.io 作为数据源，避免引入额外依赖。Stocks Basic 订阅已覆盖
**放弃了什么**：
- 其他数据源（Yahoo Finance、Alpha Vantage）
**影响**：external/polygon_client.py 需要支持 Indices 和 Economy 两类 API 调用

---

<!-- 后续决策追加在此，格式同上，编号递增 -->

## D008：SQLAlchemy 采用同步模式（非 async）

**日期**：2026-04-17（F000-a）
**决策**：后端 SQLAlchemy 使用同步 Engine + Session，不使用 `AsyncSession`
**原因**：MVP 为单用户局域网场景，并发量极低；同步 API 更简单、测试更易写；FastAPI 同步依赖也能并行执行（threadpool）；未来若有性能瓶颈再切换
**放弃了什么**：
- 异步 ORM 的理论吞吐优势
**影响**：所有 repositories / services 使用同步 session；`get_db()` 依赖为同步 generator
**API 参考来源**：Context7（/websites/sqlalchemy_en_20，2026-04-17 查询）

## D009：ORM models 按实体拆分独立文件

**日期**：2026-04-17（F000-a）
**决策**：`backend/app/models/` 下每实体一个文件（`stock.py`, `daily_bar.py`, ...共 7 个），由 `models/__init__.py` 定义 `Base` 并再导出
**原因**：遵循 ARCHITECTURE.md 约定；便于未来在各模型文件内添加 hybrid property / event listener 而不让单文件膨胀
**放弃了什么**：
- 单文件 `models.py` 的简洁性
**影响**：每个 model 文件通过 `from app.models import Base` 引用基类（依赖包部分初始化顺序）

## D010：脚手架例外（6 文件规则豁免）

**日期**：2026-04-17
**决策**：F000-a / F000-b / F000-c 三个脚手架 Sprint 豁免 feature-dev skill 的"单 Sprint ≤6 文件"硬规则
**原因**：脚手架文件性质单一（机械翻译 + auto-generated），拆分会污染中间态（部分 model / 半成 alembic migration），评审成本反而更高；正常 feature Sprint 不受影响
**放弃了什么**：
- 严格统一的 Sprint 粒度
**影响**：仅 F000-a/b/c 三个 Sprint；F001 起回到 6 文件硬规则
**用户批准**：2026-04-17 会话中显式确认
