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

## D015：nginx `proxy_pass` 不带末尾斜杠（保留 `/api/` 前缀）

**日期**：2026-04-17（F001-a 手验暴露）
**决策**：`frontend/nginx.conf` 的 `location /api/` 块使用 `proxy_pass http://backend:8000;`（无末尾斜杠），把完整 `/api/xxx` 原样转给 FastAPI
**原因**：
- FastAPI 路由定义即为 `/api/watchlist` / `/api/stocks/search`（与 API-CONTRACT.md 一致），不在后端另设 root 重写
- nginx 语义：`proxy_pass` 带末尾斜杠会用 `location` 匹配部分替换，`/api/watchlist` → `http://backend:8000/watchlist`（前缀被剥掉）；无斜杠则保留完整 URI，`/api/watchlist` → `http://backend:8000/api/watchlist`
- F000-c 阶段后端只有 `/health`，带斜杠的错误配置没暴露；F001-a 新增 `/api/*` 路由后所有请求 404
**放弃了什么**：
- 后端"不关心前缀"的抽象（从运行时看 URL 自带 `/api/`）
**影响**：
- 所有后续 router 继续以 `/api/xxx` 为前缀（router 层自带），不要试图在后端去前缀
- 若将来要把后端直接暴露到没有 nginx 的环境（如开发时 `uvicorn` 直连），URL 语义一致，无需差异化配置

## D016：Polygon `list_tickers` 用 `itertools.islice` 截取首页

**日期**：2026-04-17（F001-a 手验暴露）
**决策**：`PolygonClient.search_tickers` 把 `list_tickers(...)` 返回的 iterator 用 `itertools.islice(iterator, limit)` 截取，避免消费第二页
**原因**：
- `massive` SDK 的 `list_tickers(limit=N)` 参数语义是**每页大小**，iterator 会在首页耗尽后自动用 cursor 翻下一页，每翻一页一次 HTTP 调用
- 原实现 `list(self._client.list_tickers(...))` 会吃光所有匹配结果（模糊搜索 "AA" 能翻出成千上万条），瞬间耗尽 5/min token → 429
- Token bucket 只在调用入口 `_acquire()` 一次，SDK 内部翻页绕过 bucket，bucket 失效
**放弃了什么**：
- "SDK 自动翻页"的便利性（F003 历史数据拉取用 `list_aggs` 也需留意；目前 `get_daily_aggs` 场景固定日期窗口，单次返回可接受，不强制切片）
**影响**：
- 搜索/校验路径稳定，不会因 SDK 翻页绕过 rate limit
- 未来如需跨页查询，需要显式 cursor 控制 + 每页 `_acquire()` 一次
**根因教训**：封装外部 client 时，"每页 limit" 和 "结果总数 limit" 两个语义不能混用；仅 bucket token 不足以约束 SDK 级翻页

## D017：引入 @tanstack/react-query

**日期**：2026-04-17（F001-b Sprint Contract 协商时用户批准）
**决策**：前端数据获取统一使用 `@tanstack/react-query` v5
**版本**：安装时最新版（v5.x）
**API 参考来源**：Context7 文档（/tanstack/query）
**原因**：
- loading/error/success 状态开箱即用，无需在每个组件手写 useState
- F001-c（添加/删除）和 F003（手动刷新）依赖跨组件 cache invalidation，原生 fetch 无此能力
- `invalidateQueries` 一行代码替代多组件协调逻辑
**放弃了什么**：原生 fetch + useEffect（代码量少但扩展性差，后续 sprint 会后悔）
**影响**：所有数据获取通过 QueryClient；main.tsx 需 QueryClientProvider 包裹

## D018：Vite dev server 添加 /api 代理

**日期**：2026-04-17（F001-b Generator 阶段发现）
**决策**：`vite.config.ts` 中 `server.proxy['/api']` → `http://localhost:8000`
**原因**：`pnpm dev` 开发时浏览器在 5173 端口，直接调用 `/api/*` 会 404；需要 Vite 代理转发到后端 8000
**放弃了什么**：无（Docker 全栈模式通过 nginx 代理，两者互不影响）
**影响**：仅 dev 环境生效；prod（Docker）走 nginx 代理，配置不变

## D019：Watchlist 搜索统一走下拉（偏离 design-spec）

**日期**：2026-04-17（F001-c Sprint Contract 协商时用户确认）
**决策**：Add Stock 搜索不做"唯一结果自动 POST"分支，全部走 Popover 下拉选择；搜索由 Enter 键触发，而非 debounce 实时。
**原因**：
- 交互一致性：避免"同一 ticker 两次查询得到不同行为"（一次唯一直接添加、一次多条需点击）
- Enter 触发减少 Polygon API 调用次数（5/min rate limit 下敏感）
**放弃了什么**：design-spec.md L104-L107 描述的"结果唯一直接 POST"分支；debounce 实时搜索 UX
**影响**：design-spec.md 相应段落已追加偏离说明；实际实现 = `AddStockCard.tsx`

## D020：引入 shadcn/ui command + popover + alert-dialog

**日期**：2026-04-17（F001-c Sprint Contract 协商时用户批准）
**决策**：
- `popover` + 自定义结果列表 → 实现 AddStockCard 搜索下拉（未使用 Command 的内部 filter，因为搜索完全由后端完成）
- `alert-dialog` → 实现 SignalCard 删除二次确认
- 配套依赖 `input` / `dialog` / `textarea` / `input-group` / `command` 由 shadcn CLI 连带安装（未全部使用，但不删以保持 shadcn 一致性）
**版本**：shadcn registry radix-nova style
**API 参考来源**：Context7 文档（/shadcn-ui/ui）
**原因**：
- Popover 的 anchor / portal / 键盘焦点管理由 radix 处理，避免手写
- AlertDialog 的焦点陷阱 / ESC 关闭 / 无障碍语义开箱即用
**放弃了什么**：手写下拉 / 手写 Dialog（ROI 低）
**影响**：`frontend/src/components/ui/` 新增 7 个文件（shadcn CLI 副产品，业务核心 6 文件未变）

---

## D021：F002 6 文件上限豁免 + 信号引擎纯函数化

**日期**：2026-04-17（F002 Sprint Contract 协商时用户批准）
**决策**：
- **豁免 6 文件上限**：F002 实际 9 文件（6 业务 + 3 测试）。拒绝拆分为 F002-a/b。
  - 业务文件：signal_engine.py / signal_repository.py / signal_service.py / schemas/signal.py / routers/signals.py / main.py（+1 行 include）
  - 测试文件：test_signal_engine.py / test_signal_service.py / test_signals_api.py
- **信号引擎纯函数化**：`app/services/signal_engine.py` 不依赖 SQLAlchemy，仅操作 `BarPoint` / `SignalPoint` / `PullbackPoint` dataclass，使得单元测试零 DB 开销
- **斜率算法**：对最近 20 个有效 MA150 值做最小二乘线性回归 `y = ax + b`，取斜率 a；有效 MA 不足 20 时 slope_positive = None，signal 自动降级 NEUTRAL
- **upsert 策略**：Signal / Pullback 采用 delete-then-insert（stock_id 维度），放弃 SQLite `ON CONFLICT DO UPDATE`。recompute 天生幂等，Signal.id / Pullback.id 会变但没有下游依赖

**原因**：
- 拆分后 F002-a 既无 UI 也无 HTTP，只能靠 pytest 验收，无可感知交付；API 层仅 ~30 行不值单独一个 sprint
- 引擎纯函数化让 `test_signal_engine.py` 完全不碰数据库，运行时间 < 20ms
- delete-then-insert 比 SQLAlchemy SQLite 方言的 `on_conflict_do_update` 更简单，读者理解成本低；对 stock 级规模（≤ 250 行）写入开销可忽略

**放弃了什么**：
- 6 文件上限的机械执行（保留了"业务文件 ≤ 6"的精神，因为实际业务文件正好 6 个）
- 行级 upsert 的 ID 稳定性（F002 下游未用到 Signal.id / Pullback.id）
- numpy.polyfit（不引入新依赖，手写 20 点线性回归 ~5 行）

**影响**：
- 测试分层清晰：engine 纯单元、service 集成、api 集成
- F003 数据刷新完成后需调用 `SignalService.recompute_for_stock(stock_id)` 触发重算（当前未 hook，留给 F003）

---

## D022：F003-a Polygon agg 字段映射约定

**日期**：2026-04-17
**决策**：DataRefreshService 将 Polygon.io daily aggregate 映射为 DailyBar 时，约定：
- `timestamp`（毫秒，UTC）→ `date`（UTC 日期）
- `open/high/low/close` 直接 1:1 映射为 float
- `volume` 强制 int
- 任一必填字段缺失返回 None（被 DataRefreshService 过滤），不抛异常

**原因**：Polygon SDK（massive-com/client-python）的 Agg 对象字段名与 dict 模式均兼容；通过 `_get(obj, name)` 双分支读取，规避 SDK 版本间对象/字典漂移。
**放弃了什么**：
- 严格对 SDK 类型做 isinstance 检查（脆弱，SDK 升级易破坏）
- 数据库层显式记录时间戳精度（业务语义只需 date，已足够）

**影响**：
- 如果 Polygon 未来字段重命名，修改点集中在 `_agg_to_bar`
- 测试通过 SimpleNamespace + dict 双路径验证，确保兼容两种形态

---

## D023：F003-a SystemLog 7 天保留 + DailyBar 250 天窗口常量化

**日期**：2026-04-17
**决策**：
- `DAILY_BAR_WINDOW = 250`（daily_bar_repository.py）
- `SYSTEM_LOG_RETENTION_DAYS = 7`（system_log_repository.py）
- `BACKFILL_DEFAULT_DAYS = 250`（data_refresh_service.py）
- `BACKFILL_CALENDAR_MULTIPLIER = 2`：日历日 ≈ 2×交易日（~250 交易日覆盖 ~500 日历日足够）

**原因**：DATA-MODEL.md 明确要求这些阈值，提取为命名常量后修改单点、测试可以直接导入。
**放弃了什么**：
- 配置文件化（MVP 规模不需要；修改窗口是产品决策而非运行时参数）

**影响**：
- F003-b 调度器将复用 `purge_old_logs()` 触发 SystemLog 定期清理
- F003-c 前端如需展示 "保留 7 天" 文案，引用同一常量（通过 API 返回，不在前端硬编码）
