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

## D011：Tailwind v4 集成方式（放弃 tailwind.config.ts）

**日期**：2026-04-17（F000-b）
**决策**：前端采用 `@tailwindcss/vite` 插件 + `@import "tailwindcss"`（CSS 入口），不生成 `tailwind.config.ts`；主题 token 来源为 `src/styles/tokens.css` + shadcn 插入的 `@theme inline` 块
**原因**：Tailwind v4 官方推荐的 Vite 集成方式即此方案（已通过 context7 `/websites/tailwindcss` 验证），`tailwind.config.ts` 非必需，配置分散反而增加心智负担
**放弃了什么**：
- ARCHITECTURE.md 目录结构中原计划的 `frontend/tailwind.config.ts`（已偏离）
**影响**：未来若需要 tailwind plugin / preset 再按需新建 config 文件；目前 content 扫描由 Vite 插件自动处理
**API 参考来源**：Context7 文档（已验证）

## D012：前端版本升级到 React 19 / Vite 8 / TypeScript 6

**日期**：2026-04-17（F000-b）
**决策**：放弃 ARCHITECTURE.md 中"React 18 / Vite 6.x / TS 5.x"的原版本规划，采用 `pnpm create vite@latest` 2026-04 的默认值：React 19.2 / Vite 8.0 / TypeScript 6.0
**原因**：
- create-vite 当前默认即为该组合，React 19 已稳定发布，Vite 8 / TS 6 也是 2026 主流
- 新项目从最新版本起步，减少未来抬版本成本
- Tailwind v4 + shadcn/ui 均兼容该组合
**放弃了什么**：
- 与 ARCHITECTURE.md 原版本表的一致性（已同步更新该表）
**影响**：
- TS 6 废弃 `baseUrl`，`paths` 单独存在即可
- React 19 的 StrictMode / Suspense 行为与 18 有差异，开发时需注意（特别是 useEffect 双调用 + Action hooks）
- 后续 feature 开发若遇到库不兼容 React 19，单独评估
**用户批准**：2026-04-17 显式确认（选 A）

## D013：Polygon 客户端采用 `massive` 包（而非 `polygon-api-client`）

**日期**：2026-04-17（F000-c）
**决策**：后端 Polygon.io 客户端采用 PyPI 包 `massive>=2.5.0`（`from massive import RESTClient`），放弃 `polygon-api-client`
**原因**：
- `massive` 2.5.x 是 Polygon.io 官方改名后的包（PyPI summary：“Official Massive (formerly Polygon.io) REST and Websocket client”），版本号已超过 polygon-api-client（2.5.0 vs 1.16.3），新品牌是长期维护方向
- API 表面与 polygon-api-client 完全一致（`list_tickers` / `get_previous_close_agg` / `list_aggs`），迁移无成本
- CLAUDE.md 的 Context7 library ID `/massive-com/client-python` 即指该包
**放弃了什么**：
- `polygon-api-client` 更成熟的历史讨论生态（Stack Overflow / GitHub issues 命中率更高）
**影响**：
- 环境变量仍保留 `POLYGON_API_KEY`（不跟随品牌改名为 `MASSIVE_API_KEY`），`PolygonClient` 手动读取后显式传入 `RESTClient(api_key=...)`，避免跨项目/文档迁移成本
- 若将来 `polygon-api-client` 彻底停止维护或 `massive` API breaking change，单独评估
**API 参考来源**：Context7 `/massive-com/client-python` + PyPI 元数据（已验证）

## D014：Polygon Rate Limit 使用线程安全 Token Bucket（5 / 60s）

**日期**：2026-04-17（F000-c）
**决策**：`PolygonClient._acquire()` 采用 token bucket：容量 5，每 12 秒补 1 个 token，用 `threading.Lock` 保证并发安全，无 token 时 `time.sleep()` 阻塞等待
**原因**：
- Polygon Stocks Basic tier 硬限制 5 次/分钟，超限返回 429
- token bucket 支持突发（瞬时 5 连发）同时长期不超限，比等间隔节流更贴合数据刷新场景（F003 批量拉 watchlist 时）
- 同步阻塞（非 async）是因为 APScheduler EOD 任务跑在同步线程，FastAPI 请求处理是少量（用户手动刷新），简化实现优先
- 时间源和 sleep 函数通过构造函数依赖注入（`_time_source` / `_sleep`），单元测试用假时钟精确断言，无 flaky `time.sleep`
**放弃了什么**：
- async 版本（`asyncio.sleep`）；异步场景到 F003 再评估
- 429 响应自动重试（Polygon SDK 自行抛异常，上层 `SystemLog` 记录即可）
**影响**：
- `services/data_service.py`（F003）批量调用直接 `polygon_client.get_daily_aggs(...)`，rate limit 透明
- 若将来升级到高阶 tier（unlimited），把 `RATE_CAPACITY` 改大或去掉 `_acquire()` 即可
