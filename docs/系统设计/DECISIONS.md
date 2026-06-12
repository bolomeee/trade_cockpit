---
status: confirmed
confirmed_at: 2026-06-10
last_modified_by: feature-dev (F220-b doc-first 2026-06-12 — D105 推翻自算市值+砍 sbcSensitiveFlag / D106 pFcf 成员门控落地+坐实待查-1；v2.6 原 D104-D107 见 git history)
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

---

## D024：F003-b APScheduler 3.x + 线程模型 + add_stock 内联 backfill

**日期**：2026-04-17
**决策**：
- **调度器**：选用 APScheduler **3.11**（`apscheduler>=3.10,<4`），而非 4.x。
  - 4.x（4.0.0a6）仍是 alpha，API 未稳定；3.x 生态成熟、BackgroundScheduler 同步线程模型简单。
- **Job Store**：默认 MemoryJobStore。进程重启后重新 add_job，cron 配置来自代码常量无需持久化。
- **刷新任务线程模型**：
  - `RefreshJobManager` 为模块级单例，`threading.Lock` 保护状态；`start_refresh` 在 in_progress 时幂等返回。
  - worker 跑在 daemon `Thread`，通过 `session_factory`（`Callable[[], Session]`）打开自己的 Session —— SQLAlchemy Session 非线程安全，绝不跨线程复用请求 Session。
- **add_stock backfill**：**内联同步**调用（阻塞 POST /api/watchlist ~1–3s）。
  - MVP 阶段不引入额外异步队列；失败用 WARN 记 SystemLog，不把主流程带挂。
- **测试隔离**：通过 `MA150_DISABLE_SCHEDULER=1` env 在 conftest 中关闭调度器启动；新增 `get_session_factory` 依赖以便 TestClient 将 worker session 指向内存 SQLite。
- **Cron 表达式**：`30 21 * * 1-5`（UTC，周一至周五 21:30）—— 美股收盘后 30–90 分钟窗口。

**放弃了什么**：
- APScheduler 4.x 的 async API（等稳定再评估）
- Celery/RQ 之类的队列后端（MVP 单实例、单用户，不值得）
- add_stock 异步 backfill（会引入"股票已添加但还没数据"的 UI 临时态，复杂度不划算）

**影响**：
- F003-c 前端刷新按钮只需 poll `GET /api/data/status`；不用也不该自己维护进度。
- 生产部署必须由 uvicorn 启动 FastAPI（lifespan 触发 `start_scheduler`），而不是 gunicorn 多 worker（会启动多个 scheduler 重复触发）；多 worker 场景需改用 `MA150_DISABLE_SCHEDULER=1` + 独立调度进程。

---

## D025：引入 lightweight-charts v5 + PriceChart 实现细节
**时间**：2026-04-17（F005-c Sprint 期间）
**背景**：F005 Modal 需要显示 K 线 + MA150 + Pullback 标记；design-spec、component-plan 已指定 TradingView lightweight-charts。

**决策**：
- **版本**：`lightweight-charts@5.1.0`（当前稳定版）。
- **API 选择**（v5 新 API，已通过 context7 `/tradingview/lightweight-charts` 验证）：
  - 主图：`chart.addSeries(CandlestickSeries, …)`（v5 废弃 `addCandlestickSeries`）。
  - 均线：`chart.addSeries(LineSeries, …)`，`priceLineVisible=false`、`lastValueVisible=false` 避免污染 Y 轴右缘。
  - 标记：v5 独立 primitive `createSeriesMarkers(series, markers[])`，而非 v4 的 `series.setMarkers()`。Pullback 在 K 线下方显示 `arrowUp` 指示回踩入场，颜色 `--color-signal-buyzone`。
- **时间格式**：后端返回 `YYYY-MM-DD` 字符串；前端转成 `UTCTimestamp`（`Date.parse(date + 'T00:00:00Z')/1000`）以避免 lightweight-charts 的 BusinessDay 对象校验歧义。
- **主题注入**：运行时 `getComputedStyle(document.documentElement).getPropertyValue('--color-xxx')` 读取 tokens.css 变量传给 chart options，避免在组件内硬编码 hex。
- **React 生命周期**：`useEffect` 依赖 `[data, height]`；cleanup 调用 `chart.remove()` 并移除 window resize 监听器，防止 Modal 切换股票时泄漏。
- **响应式**：监听 window resize 调 `chart.applyOptions({ width: container.clientWidth })`，不引入 `ResizeObserver`（lightweight-charts `autoSize` 选项实际依赖 ResizeObserver，在 Dialog 初次挂载时宽度读取不稳定，显式 width + resize listener 更可控）。

**放弃了什么**：
- v4 API（`addCandlestickSeries` / `series.setMarkers`）—— 新项目直接用 v5，不背兼容包袱。
- Chart 主题切换、多时段切换（1M/3M/6M/1Y）—— 留给后续 feature。
- Marker hover 展开 Pullback 详情 —— P2，本次只画三角形。

**影响**：
- Dashboard Modal 打开时并发拉 4 个接口（已有 3 个 + chart）；chart 数据 5 分钟 staleTime 与 pullbacks 对齐。
- 前端 bundle 增加 ~50KB gzip（lightweight-charts 核心），在 MVP 可接受。

**API 参考来源**：context7 `/tradingview/lightweight-charts`（2026-04-17 查询），非训练数据。


---

## D026：TNX 数据源走 httpx 直连 Polygon Treasury Yields 端点
**时间**：2026-04-17（F006-a Sprint 期间）
**背景**：MarketIndex.TNX（10 年期美债）数据源。最初 D007 标注"Polygon Economy API (Treasury Yields)"，但 F006-a 开发时发现当前使用的 `massive` Python 客户端（polygon-api-client 的兼容 fork）**未封装** `/fed/v1/treasury-yields` 端点。

**决策**：
- 在 `PolygonClient` 内增加 `get_treasury_10y_latest()`：用 `httpx.Client` 直接 GET `https://api.polygon.io/fed/v1/treasury-yields?limit=2&sort=date.desc&apiKey=...`，取 `results[0]` 为最新、`results[1]` 为前一日。
- 响应字段名权威：`date`（YYYY-MM-DD）、`yield_10_year`（number），来源：https://massive.com/docs/rest/economy/treasury-yields。
- 鉴权走 `apiKey` query param（Polygon 标准），与 SDK 共用 `settings.polygon_api_key`。
- httpx.Client 作为 `PolygonClient.__init__` 的可选注入参数，测试用 `httpx.MockTransport` 直接 stub，无需第三方 mock 库。
- 共享同一个令牌桶 `_acquire()`：httpx 调用也计入 5 次/分钟限额，防止混合调用突破 Polygon rate limit。

**放弃了什么**：
- **FRED API（DGS10）**：免费稳定但需引入第二个外部源 + 新环境变量 + 更新 DATA-MODEL 数据来源脚注。本次选择保持"所有数据走 Polygon 一家"的架构简洁性。
- **mock TNX**：与 SPX/NDX 真实数据不一致，且 MVP 设计稿就要求显示真实涨跌。
- 等 massive SDK 官方封装：不可控时间线。

**影响**：
- `backend/pyproject.toml` httpx>=0.27（已有，F005 引入时已加）。
- `PolygonClient` 多一个内部 httpx.Client 实例；生命周期与客户端一致。
- 若 Polygon 订阅不含 Economy API，此端点会 403；已在 `MarketRefreshService._refresh_one` 的 per-symbol try/except 内隔离，SystemLog ERROR 记录但不影响 SPX/NDX。

**API 参考来源**：https://massive.com/docs/rest/economy/treasury-yields（WebFetch 于 2026-04-17 验证），非训练数据。

---

## D027：指数 symbol 用 `I:` 前缀经 aggregates 端点获取
**时间**：2026-04-17（F006-a Sprint 期间）
**背景**：SPX / NDX 指数数据。Polygon 的 indices 与 stock aggregates 共用同一端点，通过 symbol 前缀区分：`I:SPX` / `I:NDX` / `I:DJI`。massive SDK 没有专用 `get_index_*` 方法。

**决策**：
- `PolygonClient.get_index_recent_aggs(symbol, days=10)`：对外暴露裸 symbol（"SPX"），内部拼接 `I:` 前缀传给 `list_aggs`。不选用 `get_previous_close_agg`，因为它只返回 T-1 一天，算不出 change_pct。
- `days=10` 日历日约覆盖 7 交易日（含 2 周末 + 可能的节假日），确保至少能取到 T-1 和 T-2；取 list 排序后最后两根为 latest/prev。
- 返回 list 原样，`symbol` 前缀逻辑不泄漏到 service 层。

**放弃了什么**：
- `get_previous_close_agg`：返回单日，change_pct 需另取一日，多一个 rate-limit token，不如一次 list_aggs 划算。
- 硬编码两次调用拼接 latest + prev：当 T-1 是节假日时会失败。

**影响**：
- SPX / NDX 每次刷新消耗 1 个 rate token（共用 5/分钟桶），加上 TNX httpx 1 个 + 每只股票 1 个，整体 refresh 在 10 只 watchlist + 3 市场指标约消耗 13 token，>12s 窗口需要分批，现有 token bucket 已处理。

**API 参考来源**：context7 `/massive-com/client-python` + https://massive.com/docs（2026-04-17），非训练数据。


---

## D028：F007-c 引入 react-hook-form + zod + shadcn Select/Label
**时间**：2026-04-17（F007-c Sprint 期间）
**背景**：Journal 新建/编辑 Dialog 表单 9 字段，含数字/日期/枚举/文本；需可测试的字段级校验 + 编辑模式预填。

**决策**：
- 引入 `react-hook-form@^7`、`zod@^3`、`@hookform/resolvers@^5` 三个依赖（pnpm -F frontend add）
- 用 `zodResolver(schema)` 统一类型推导与运行时校验
- 引入 shadcn `select` 与 `label` 基础组件（通过 shadcn CLI），用 `Controller` 包 Select 接入 RHF
- 校验策略：ticker/action/price/date 必填；price/position/stopLoss/targetPrice 数字 > 0；reason/reference 可选文本

**放弃了什么**：
- 手写 useState + validator：字段多且需 edit 模式 reset + 字段级错误展示，手写成本高且易错
- yup / joi：Zod 更强的 TS 推导一次到位

**影响**：
- `frontend/package.json` 新增三个运行时依赖
- FilterCard（F007-b）暂保留原生 select（见 design-spec 偏离块），本 Sprint **不回退**替换，避免 F007-c 超文件数；留给后续样式统一阶段
- `+New Entry` / `Edit` 按钮从 F007-b 的 disabled 状态解锁

**API 参考来源**：
- context7 `/react-hook-form/resolvers`（2026-04-17，zodResolver 用法与 TS 推导）
- context7 `/shadcn-ui/ui`（2026-04-17，Select+Controller 用法与 Label 规范）
- 非训练数据。

---

## D029：Workbench widget 框架技术选型
**时间**：2026-04-18（v1.1.0 Workbench 重构 Phase 0）
**背景**：v1.0.0 的 Dashboard/Journal/Logs 三个固定页面要演化为 Grafana 风格的单页面 widget 工作台。选型需要支持拖拽重排、自由缩放、布局持久化。

**决策**：
- **布局引擎**：`react-grid-layout@1.x` —— 成熟度高、支持拖拽 + resize + 响应式断点、API 稳定
- **跨 widget 状态**：`zustand` + `persist` 中间件，替代 React Query 解决不了的"选中 ticker 跨 widget 联动"等 client state
- **布局持久化**：浏览器 `localStorage`，key `ma150.workbench.layouts.v1`（带版本号方便未来 schema 迁移），**不进数据库**

**放弃了什么**：
- **DB 持久化 widget 布局**（新增 Widget / WidgetInstance 表）：个人单用户场景无跨设备同步需求，localStorage 足够；架构简洁性优先
- **micro-frontend / iframe / Module Federation**：同 React app 内的组件复用即可，隔离成本远大于收益
- **`@dnd-kit` 自实现 grid**：react-grid-layout 开箱即用，风险更低（若与 React 19 有兼容问题，Phase 1 demo 阶段暴露时再评估切换）

**影响**：
- 新增前端依赖 `react-grid-layout`、`zustand`
- 后端零改动（ARCHITECTURE 已声明"每个前端 widget 自包含、独立取数"）
- 未来若要多 dashboard 预设切换、跨设备同步，再迁移到 DB

---

## D030：Widget 间通信 = zustand 全局 store
**时间**：2026-04-18（v1.1.0 Workbench 重构 Phase 0）
**背景**：WatchlistWidget 点击股票需要让 ChartWidget / FundamentalsWidget / PullbackWidget 同步刷新。v1.0.0 通过 `Dashboard.tsx` 的 `useState` + props drilling 实现。widget 化后没有共同父组件。

**决策**：
- 新建 `src/store/useAppStore.ts`（zustand），暴露 `selectedSymbol` / `setSelectedSymbol` 等跨 widget client state
- Widget 通过 hook 独立读写 store，彼此无直接依赖
- Server state 仍由 React Query 管理，zustand 只管跨 widget 的 client state

**放弃了什么**：
- **props drilling**：widget 无共同父组件，不可行
- **URL state（search params）**：`selectedSymbol` 改变不应 push history，也不应在刷新后保留（布局保留足够）
- **Context**：rerender 范围不可控，多 widget 监听会性能退化
- **复杂消息总线（RxJS 等）**：现有联动需求只是"一个选中态"，zustand 足够

**影响**：
- StockDetailModal 将删除，替代为 3 个独立 widget 共同订阅 `selectedSymbol`
- 未来跨 widget 联动新增字段（如 `watchlistFilter`、`dateRange`）继续扩展 AppStore

---

## D031：StockDetailModal 拆解为 3 个独立 widget
**时间**：2026-04-18（v1.1.0 Workbench 重构 Phase 0）
**背景**：v1.0.0 的 `StockDetailModal` 是 Dialog，点击 SignalCard 弹出 K线 + 基本面 + 回踩历史。widget 化后 Dialog 模式与拖拽网格冲突。

**决策**：
- 删除 `StockDetailModal.tsx`
- 拆成 3 个独立 widget：`ChartWidget` / `FundamentalsWidget` / `PullbackWidget`，全部从 `useAppStore.selectedSymbol` 读 ticker
- 点 WatchlistWidget 中的股票 → `setSelectedSymbol("AAPL")` → 3 个 widget 同步 rerender 拉新数据
- `PriceChart` 需要改造：去掉硬编码 `height: 302px`，用 ResizeObserver 让图表填满 widget 容器

**放弃了什么**：
- **保留 Modal 同时也有 widget**：两套入口同一份数据容易行为漂移，维护成本高
- **内嵌 Modal 到 widget 内部**：widget 本应"永久可见"、"可 resize"，Modal 语义冲突

**影响**：
- 用户可在 Workbench 同时并排看多个股票（切换 selectedSymbol），或只开 Chart 不开 Fundamentals，灵活度大幅提升
- 失去 "Modal 弹出感" UX —— 可接受，因为 widget 本身就是"聚焦显示"
- `PriceChart` 响应式改造需同步解决 lightweight-charts 在窄宽度下的标签遮挡问题

---

## D032：Fundamentals 维持 mock，ROCE 以 mock 占位，真实财报接入延至独立 feature
**时间**：2026-04-19（v1.1.0 Workbench 重构期间）
**背景**：`FundamentalsWidget` UI 改为双列 shadcn Table 后需要展示 ROCE = EBIT / (Total Assets − Total Current Liabilities)。但 `/api/stocks/:ticker/fundamentals` 目前整体是 mock（`_mock_fundamentals` 基于 sha1 造假数据，source 字段标记为 `"mock"`），PE / PS / PEG / FCF / MarketCap 全部是假。接入 ROCE 真值需要拉 Polygon `vX/reference/financials`（EBIT / TotalAssets / CurrentLiabilities），并改 repo + service + caching，影响 ≥ 4 文件，超出"架构变更影响 2 文件"红线。

**决策**：
- 现阶段在 `_mock_fundamentals` 里追加 mock `roce`（sha1 衍生，0.05–0.40 范围），保持与其他字段一致的 mock 风格
- 前端 `Fundamentals` 类型新增 `roce?: number | null`，widget 用 "—" 兜底缺值
- 真实财报接入延至新 feature（**F103 — Fundamentals 真实财报接入**），需单独 sprint contract：
  - Polygon `vX/reference/financials` endpoint 封装 + rate-limit 预算
  - 新 repository / service / schema（`StockFundamentals` ORM 或 JSON 列）
  - 季度级缓存策略
  - 同时将 PE / PS / PEG / FCF 从 mock 替换为 trailing price / market cap + 财报字段计算
  - `source` 字段从 `"mock"` 改为 `"polygon"`

**放弃了什么**：
- **这次就接真财报**：scope 过大，破坏重构节奏，与 Workbench 主线不正交
- **只接 ROCE 不碰其他四个**：会出现 "4 假 + 1 真" 的不一致状态，用户难分辨可信度

**影响**：
- v1.1.0 发版时 FundamentalsWidget 的 5 个指标全部 mock，保留 `source: "mock"` 语义
- `features.json` 追加 F103 占位（phase: `design_needed`），v1.1.0 发版后评估优先级
- 前端 `roce?: number | null` 可选字段，将来真实接入保持兼容

---

## D033：非 watchlist ticker 的 chart preview 延到首个"含外部 ticker 的 widget"立项时再设计
**时间**：2026-04-19（v1.1.0 Workbench 重构期间）
**背景**：Workbench 的跨 widget 联动走 `useAppStore.selectedSymbol`（D030），理论上任何 widget 调 `setSelectedSymbol(ticker)` 就能驱动 ChartWidget / FundamentalsWidget / PullbackWidget 切换。疑问：如果将来某个 widget（News / Scan / AI 观点）里的 ticker 不在 watchlist，点击后 chart 该怎么办？要不要做本地缓存？

**现状盘点**：
- **watchlist 内 ticker**：chart/pullbacks/fundamentals 读本地 `DailyBar`，零外部 API；F003 daily scheduler + 手动 Refresh 增量维护 250 天滚动窗口；前端 React Query 额外 5min staleTime 内存缓存。不重复拉
- **非 watchlist ticker**：`StockDetailService._resolve_active_stock` 硬卡 404，当前根本点不了

**决策**：
- **不在 v1.1.0 动这块**。当前所有 widget 的 ticker 来源都在 watchlist 内，point 2（preview 缓存）是未触发的问题
- 等第一个"含外部 ticker 的 widget"立项（News / Scan / AI 观点等）时，把 preview 流程作为那个 feature 的一部分一起设计，候选方案：
  - **方案 A（preview-without-add）**：解除 `_resolve_active_stock` 硬拦 + Polygon `get_daily_aggs` 按需拉 250 天 + TTL 缓存（建议 24h，不用一个月）
  - **方案 B（强制加 watchlist）**：点击外部 ticker 时不直接 preview，弹"加入 watchlist"按钮，走 F001 已有流程
- 选哪个由那个 feature 的 UX 决定，现在不预判

**放弃了什么**：
- **现在就做 preview 缓存**：没有调用方，YAGNI；且 TTL 策略（时长、失效触发、与 EOD refresh 关系）需要结合具体 UX 决，现在决定大概率要推翻
- **一个月缓存**：太长，财报更新、分红、拆股会让缓存和真值漂移；24h 对 preview 够用

**影响**：
- `StockDetailService._resolve_active_stock` 的 404 行为保留，不动
- 新 widget 开发者要记住：如果 widget 会显示外部 ticker 且计划联动 chart，需要先立 feature 决 preview 策略，不要直接硬接
- Polygon rate limit（5/min）在 preview 方案 A 下可能触发，缓存命中率是那个 feature 的验收指标之一

---

## D034：数据源从 Polygon Stocks Starter 迁移至 FMP Starter（/stable/ 端点）
**时间**：2026-04-19（v1.1.0 发版后）

**背景**：
- v1.0.0/v1.1.0 以 Polygon.io (massive) Stocks Starter 订阅为唯一外部数据源。信号引擎、刷新调度、图表、搜索、大盘指数、10Y 国债全部走 Polygon。
- F103（Fundamentals 真实财报接入）在排期时发现：Polygon Stocks Starter **不含 cash flow 细项**，`vX/reference/financials` 返回的 cash-flow-statement 不包含 CapEx 字段。没有 CapEx 就无法按 `OCF − CapEx` 算真实 FCF，PE/PS/PEG 还可以从 price + income/balance 组装，但 FCF 缺口是硬伤。
- 用户对比后发现 Financial Modeling Prep (FMP) Starter 订阅同价位：
  - `/stable/ratios-ttm` 一把拉到 PE / PS / PEG / ROCE（`returnOnCapitalEmployedTTM`）/ `freeCashFlowPerShareTTM` + `marketCapTTM`，**5/5 指标全覆盖且 TTM 直出**，不需要自己组合三表
  - `/stable/historical-price-eod/full` 覆盖日线 + adjClose，replace `get_daily_aggs`
  - `/stable/search-symbol` + `/stable/search-name` 取代 Polygon `list_tickers` 前缀/名称两套
  - `/stable/treasury-rates` 直出 10Y，不需要 fallback 到 `/fed/v1/treasury-yields` 直连
  - 指数 `^GSPC` / `^NDX` 在 `/stable/quote` 和 EOD 端点都可查，不再需要 `I:SPX` 前缀那套 hack
- 实测 AAPL：P/E 33.84 / P/S 9.12 / PEG 5.75 / ROCE 65.03% / FCF $104B；20 并发 profile 调用 20/20 成功 avg 1.2s
- 价格相同、覆盖更广、一个 REST 客户端替代"SDK + 直连 HTTP 两套"，决定整体替换。

**决策**：
1. **整体替换**：所有 Polygon 调用迁移到 FMP REST（httpx 直连 `/stable/` 端点），不保留双数据源并行
2. **保留 `polygon_client.py` 作为 deprecated 参考**：不删除文件，只在模块头 docstring 标注 `DEPRECATED as of 2026-04-19 — see fmp_client.py; kept for rollback reference`。任何代码路径不再导入
3. **env 变量**：新增 `FMP_API_KEY`；`POLYGON_API_KEY` 保留读取但 `config.py` 注释为 legacy，默认为空不阻塞启动
4. **Rate limit**：FMP Starter 300 req/min，不再需要 5/min token bucket。保留一个 **宽松 token bucket（300/min，burst 50）作为防御层**，避免误用爆 quota；不做 1/s 的苛刻节流
5. **Frontend 零改动**：后端 `/api/stocks/:ticker/fundamentals` 和 `/chart` 的响应 schema 保持不变，FMP 响应在 service 层适配成既有 `Fundamentals` / `ChartPoint` 契约
6. **指数端点**：SPX → `^GSPC`、NDX → `^NDX`、TNX → `/stable/treasury-rates` 的 `year10` 字段
7. **数据契约变化**：`fundamentals.source` 取值从 `"mock"` 改为 `"fmp"`；前端 "Mock Data" 提示条在此次迁移后删除

**备选方案对比**：

| 方案 | 范围 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| **A. 整体替换（本决策）** | Polygon → FMP 全量 | 单数据源，少一层抽象；ratios-ttm 直出 5 指标省去组合计算；rate limit 宽松；订阅同价 | 一次性改动面广（~6 文件核心 + 测试回归）；SDK 换 REST 略增手写负担；短期 dual-read 成本高故不做 | **采用** |
| B. 保留 Polygon 日线/指数，仅为 Fundamentals 新增 FMP | 日线/搜索继续 Polygon，fundamentals 走 FMP | 改动面小，F103 能按期交付 | 双数据源长期维护，两套 rate limit / 错误处理；Polygon 5/min 的束缚仍然压着刷新任务；搜索/指数仍是两套 hack | 放弃：避免长期债务 |
| C. 维持 Polygon 升级更高档位 | 升级到 Polygon Stocks Advanced 才含 CapEx | 不改代码 | 月费上浮约 2–3 倍；ROCE 仍需自组合；单用户项目不值 | 放弃：性价比差 |
| D. 换 Financial Datasets / 其他 | 第三方 | 覆盖类似 | 无实测数据，切换风险高 | 放弃：没有实测背书 |

**风险**：
1. **实时性差异**：Polygon 支持 `get_previous_close` 和分钟级 aggs；FMP Starter 的 intraday 精度与 WebSocket 支持需在实装前二次确认。**本项目只用 EOD + 盘后刷新，无 intraday 需求**，风险可控，但写入 ARCHITECTURE 作为边界条件
2. **搜索语义差异**：Polygon `list_tickers` 支持 `ticker_gte/lt` 的严格前缀范围；FMP `search-symbol` 按子串匹配。需要在 service 层重做"前缀优先"排序逻辑（D028 两阶段搜索策略要重现）
3. **指数前缀变更**：所有已存 `market_indices` 记录以 `SPX/NDX/TNX` 为 symbol 存储（DATA-MODEL 未变），FMP `^GSPC` 在 repo 层映射为 `SPX` 保存，不破坏库
4. **/stable/ 端点稳定性**：Legacy `/api/v3/` 对此 key 已关闭，只能用 `/stable/`。如果 FMP 将来 `/stable/` 端点重命名，需有 version pin 机制——约定在 `fmp_client.py` 集中所有 endpoint path 常量
5. **Starter 条款中的限速实测**：文档 300/min 未在本地确认；若打高并发触发 429，需退回 token bucket
6. **不覆盖的 FMP 能力**：期权链、level-2 quote、historic split-adjusted factor 具体化程度弱于 Polygon——**本项目不依赖这些**，但未来做期权 widget 前必须重新评估

**回滚路径**：
- `polygon_client.py` 保留完整，dependencies.py / main.py / services 里只是"不再注入"；回滚 = revert 一个 commit 即可
- DB schema 无变化（`market_indices.symbol` / `stocks.ticker` 字段不变），无数据迁移问题
- env 变量 `POLYGON_API_KEY` 仍支持读取，回滚后不需要改 .env

**迁移影响清单（按优先级）**：

| 优先级 | 文件/模块 | 改动 | 说明 |
|--------|----------|------|------|
| P0 | `backend/app/external/fmp_client.py` | **新建** | httpx 直连 `/stable/`；封装 `search_tickers` / `get_daily_bars` / `get_index_recent_bars` / `get_treasury_10y_latest` / `get_ratios_ttm`；内置 token bucket（300/min, burst 50） |
| P0 | `backend/app/external/polygon_client.py` | 顶部 docstring 加 `DEPRECATED` 标记，不删 | 保底回滚 |
| P0 | `backend/app/external/__init__.py` | 改导出 `FMPClient` | `PolygonClient` 保留导出，标 deprecated |
| P0 | `backend/app/config.py` | 新增 `fmp_api_key`，`polygon_api_key` 注释 legacy | |
| P0 | `backend/app/dependencies.py` | `get_polygon_client` → `get_fmp_client` | WatchlistService / DataRefreshService / MarketRefreshService / RefreshJob 全部改注入 |
| P0 | `backend/app/services/watchlist_service.py` | `polygon.search_tickers` → `fmp.search_tickers`；重现两阶段搜索（symbol 前缀 → name fallback）| 见风险 2 |
| P0 | `backend/app/services/data_refresh_service.py` | `polygon.get_daily_aggs` → `fmp.get_daily_bars`；bar 映射器从 `Agg.timestamp(ms UTC)` 改成 FMP `date(YYYY-MM-DD)` + OHLCV + volume | |
| P0 | `backend/app/services/market_refresh_service.py` | 指数拉 `^GSPC`/`^NDX` EOD；10Y 走 `/stable/treasury-rates`；`SPX/NDX/TNX` 仍作为 DB symbol 保留 | |
| P0 | `backend/app/services/stock_detail_service.py` | `_fundamentals_payload` 从 `_mock_fundamentals` 改为调用 `fmp.get_ratios_ttm`；字段映射：priceEarningsRatioTTM→priceToEarnings, priceToSalesRatioTTM→priceToSales, priceEarningsToGrowthRatioTTM→peg, freeCashFlowPerShareTTM × sharesOutstanding(来自 quote 或 profile)→freeCashFlow, returnOnCapitalEmployedTTM→roce, marketCapTTM→marketCap；负值/null 直接返回 null | 替代 F103 |
| P0 | `backend/app/services/refresh_job.py` | `PolygonFactory` 改名 `FMPFactory`，类型别名更新 | |
| P0 | `backend/app/main.py` | `_polygon_factory` 重命名；scheduler 入参同步 | |
| P0 | `backend/app/routers/data.py` | 入参类型 `PolygonClient` → `FMPClient` | |
| P0 | `.env` / `.env.example` | 新增 `FMP_API_KEY`；`POLYGON_API_KEY` 保留但注释 legacy | |
| P0 | `backend/tests/conftest.py` | fake polygon fixture 改 fake_fmp（相同接口签名） | |
| P0 | `backend/tests/test_polygon_client.py` | **重命名** `test_fmp_client.py`，新 case 覆盖 FMP 端点/rate limit/错误处理 | |
| P0 | 既有 pytest 162 个 | 使用 fake_fmp fixture 替代 fake_polygon；contract 层回归而非真打 API；增 3–5 个 live smoke test 打真实 FMP（标 `@pytest.mark.live`，CI 跳过） | 回归策略 |
| P1 | `backend/app/services/stock_detail_service.py` Fundamentals 季度缓存 | FMP Starter rate limit 宽松，短期可直查；后续仍建议 24h in-process cache | 非阻塞 |
| P1 | `frontend/src/workbench/widgets/FundamentalsWidget.tsx` | 删除 "Mock Data" 提示条；`source === 'fmp'` 无 banner | UI 清理 |
| P1 | `docs/系统设计/ARCHITECTURE.md` | 外部依赖章节、rate limit 策略、指数端点 | 本次一并 |
| P1 | `docs/系统设计/API-CONTRACT.md` | fundamentals source 语义 + 字段定义 | 本次一并 |
| P1 | `docs/需求/features.json` | F103 标 `deprecated` + `superseded_by: F104`；新增 F104 | 本次一并 |

**放弃了什么**：
- **双数据源并行过渡期**：一次性切换比长期维护"某些字段 Polygon、某些 FMP"简单，回滚成本也可控
- **删除 polygon_client.py**：保留一个废弃模块成本低（不被导入即 0 运行时开销），回滚复杂度低很多
- **强制每季度刷新 fundamentals**：FMP rate limit 宽松下短期不必要，按需拉即可；后续 F105（性能优化）统一做缓存

**影响**：
- **冻结 F103**：F103 的目标（真实财报、ROCE 真值、source != "mock"）被 F104 整体吸收；F103 phase 改为 `deprecated`，`superseded_by: F104`
- **新增 F104**："数据源迁移到 FMP"，工程 feature（非产品 feature），优先级 P0，估 2–3 个 session
- **DATA-MODEL.md 无变化**：字段命名、表结构、枚举值全部保留
- **前端类型定义无变化**：`Fundamentals` / `ChartPoint` / `MarketIndex` 类型不动
- **MarketOverviewBar 行为无变化**：SPX/NDX/TNX 仍按既有逻辑渲染

---

## D035：fundamentals 估值指标改走 `/stable/key-metrics-ttm`（D034 补充）
**时间**：2026-04-19（F104-S2c 联网 smoke 发现）

**背景**：
- D034 在 2026-04-19 早些时候确认后，F104-S1 封装 `FmpClient.get_ratios_ttm` 对接 `/stable/ratios-ttm`，期望一把拉到 PE/PS/PEG/ROCE/FCF（D034 决策第 580 行）。
- F104-S2c 跑真实联网 smoke（AAPL）发现 `/stable/ratios-ttm` **实际响应只含 margin/turnover 系列**（`grossProfitMarginTTM / netProfitMarginTTM / receivablesTurnoverTTM …`），**不包含 P/E / P/S / PEG / ROCE / FCF**。
- FMP 在 D034 调研与 S2c 执行之间似乎调整了 `/stable/` 端点职责划分：估值类 TTM 指标迁到 `/stable/key-metrics-ttm`，`/stable/ratios-ttm` 专注盈利能力/运营效率比率。

**决策**：
1. **S3 fundamentals 真实接入改走 `/stable/key-metrics-ttm`** 作为估值指标主源，`/stable/ratios-ttm` 作为盈利能力指标补充源
2. **FmpClient 扩展**：S3 新增 `get_key_metrics_ttm(symbol)`，与 `get_ratios_ttm` 并列；顶部新增 `FMP_EP_KEY_METRICS_TTM = "/key-metrics-ttm"` 常量
3. **现有 `get_ratios_ttm` 保留**：不回滚 S1 产出，S3 将其定位为盈利能力数据源而非估值数据源；API-CONTRACT.md 的 `fundamentals` 响应在 service 层合并两个端点的字段
4. **ARCHITECTURE.md 端点映射表更新**：在 D034 映射表新增一行 `估值 TTM → /stable/key-metrics-ttm`
5. **不影响 F104-S1/S2/S2c**：这三个 sprint 的范围里没有消费 ratios-ttm 的业务代码，只有契约封装 + smoke test

**放弃的方案**：
- **手工从 income/balance 三表组装 P/E**：FMP Starter 有直出端点就走直出，不重造组合逻辑
- **推迟到 S3 再发现**：S2c smoke test 就是这类契约漂移的早期预警机制，在封装层抓住比在 feature 开发中后期抓住廉价得多

**影响**：
- **F104-S3 范围扩大**：原计划单纯 wire `get_ratios_ttm` → fundamentals router，现需要先在 FmpClient 扩展 `get_key_metrics_ttm` 并在 service 层合并两端点响应
- **API-CONTRACT.md 的 `fundamentals` 字段映射**：S3 启动时需要具体写明哪些字段来自 ratios-ttm、哪些来自 key-metrics-ttm
- **Rate 预算**：每支股票的 fundamentals 刷新由 1 次 FMP 调用变为 2 次；300/min 下仍宽裕，暂不引入缓存


---

## D036：fundamentals 字段真实映射（修订 D035）
**时间**：2026-04-19（F104-S3 执行期间 live smoke 发现）

**背景**：
- D035 基于 S2c smoke 的一条断言（`grossProfitMarginTTM` 存在）推断"`/stable/ratios-ttm` 只含 margin/turnover"，进而决定估值 TTM 迁到 `/stable/key-metrics-ttm`。这是**假阴性误判**。
- S3 执行时 live smoke `test_live_key_metrics_ttm_aapl` 失败（`peRatioTTM` 不在 key-metrics-ttm 响应里），遂用真实 API key 对四个候选端点 (`ratios-ttm / key-metrics-ttm / quote / profile`) 做字段 dump，得到权威答案。

**观察到的真实字段分布（AAPL，2026-04-19）**：
- `/stable/ratios-ttm`：**含** `priceToEarningsRatioTTM` / `priceToSalesRatioTTM` / `priceToEarningsGrowthRatioTTM` / `freeCashFlowPerShareTTM`；**不含** ROCE / marketCap
- `/stable/key-metrics-ttm`：**含** `marketCap`（无 TTM 后缀）/ `returnOnCapitalEmployedTTM` / `freeCashFlowYieldTTM`；**不含** PE/PS/PEG
- `/stable/quote`：含 `marketCap` / `price`，无 PE 比率
- `/stable/profile`：含 `marketCap` / `price` / `beta`，无 PE 比率

**决策**：
1. fundamentals service 层**合并调用** `ratios-ttm` + `key-metrics-ttm`（每次 2 次 FMP 调用，与 D035 "Rate 预算" 段落一致）
2. **最终字段映射**：
   | API | FMP 字段 |
   |---|---|
   | priceToEarnings | `ratios-ttm.priceToEarningsRatioTTM` |
   | priceToSales | `ratios-ttm.priceToSalesRatioTTM` |
   | peg | `ratios-ttm.priceToEarningsGrowthRatioTTM` |
   | roce | `key-metrics-ttm.returnOnCapitalEmployedTTM` |
   | freeCashFlow | `key-metrics-ttm.marketCap × key-metrics-ttm.freeCashFlowYieldTTM` |
   | marketCap | `key-metrics-ttm.marketCap` |
3. **FCF 推导路径**：FMP `/stable/` 系无直接 "absolute FCF" 字段；`freeCashFlowYieldTTM = FCF / marketCap`，逆推即可，精度够前端展示（与 AAPL TTM 公开口径对齐到 B 级）
4. **保留 `get_key_metrics_ttm` 和 `get_ratios_ttm` 两个客户端方法**：S1/S3 的产物不回滚
5. **Smoke test 加强**：`test_live_ratios_ttm_aapl` 改断言 `priceToEarningsRatioTTM` 存在（比 margin 字段更切题 S3 真实消费路径）；`test_live_key_metrics_ttm_aapl` 改断言 `marketCap` 与 `freeCashFlowYieldTTM` 存在（而非 `peRatioTTM`）

**放弃的方案**：
- **引入第 3 端点 quote/profile 取 sharesOutstanding**：`freeCashFlowYieldTTM` 已在 key-metrics-ttm 直出，不需要三端点组合
- **接受 FCF 为 null**：损失产品信息价值；AAPL/MSFT 这类主仓位股 FCF 是核心基本面指标，不能放掉
- **保留 D035 的"只走 key-metrics-ttm"**：live smoke 已证伪，留着是错的契约

**影响**：
- **API-CONTRACT.md**：S3 第一次修订（只改 endpoint 名）作废，按 D036 再次修订字段映射表
- **Service 实现**：`StockDetailService.get_fundamentals` 从"调 1 个端点 + 6 字段映射"改为"并发/串行调 2 个端点 + FCF 推导"
- **Rate 预算**：与 D035 一致，2 次/symbol，无新影响
- **S2c 经验教训**：smoke test 只断言"存在"不够，关键字段需要**正向命名断言**（`priceToEarningsRatioTTM in response`），否则契约漂移可能被漏网

---

## D037：NDX 数据源用 QQQM ETF 价格替代 `^NDX` 指数
**时间**：2026-04-20（v1.0.0 Docker 部署后冒烟发现）

**背景**：
- `docker compose up` 首次运行后，`/api/market/overview` 缺 NDX 行。后端日志：`^NDX` 调 `/stable/historical-price-eod/full` 返回 `402 Payment Required`
- 验证：FMP Starter 套餐不包含 `^NDX`（Nasdaq 授权指数通常在 Premium 及以上档位，或需独立 index 附加包）。FMP 文档列出的通用 index 集 (`^GSPC / ^DJI / ^IXIC / ^RUT / ^FTSE / ^N225 / ^HSI / ^STOXX50E / ^VIX`) 也没有 `^NDX`
- 用户明确排除 `^IXIC`（NASDAQ Composite）方案："纳指看宽泛了没用"

**决策**：
1. **数据源切到 QQQM**（Invesco NASDAQ 100 ETF，费率 0.15% 版本的 QQQ），走既有 `get_daily_bars` 股票历史端点，Starter 覆盖
2. **DB symbol 保持 `NDX`**：DATA-MODEL 不变，前端 `MarketOverviewBar` 显示名仍为 "NASDAQ 100"（QQQM 跟踪 NDX，日内方向 >99% 同步，用户层语义等价）
3. **代码改动**：只改 `market_refresh_service._DB_TO_FMP_INDEX["NDX"]` 从 `"^NDX"` 改为 `"QQQM"`；tests 同步把 `fake_fmp.index_bars_results["^NDX"]` 改为 `"QQQM"`
4. **部署配置**：`docker-compose.yml` backend service 补透传 `FMP_API_KEY`（发版前漏了）

**放弃的方案**：
- **升级到 Premium**：为一个指标升套餐不值得；且 Nasdaq 授权变动不透明，续费后仍可能被降级
- **`^IXIC` 替代**：用户明确否决
- **QQQ 代替 QQQM**：两者同样 track NDX，价格/方向一致；选 QQQM 纯粹因为费率稍低，差异可忽略

**影响**：
- NDX 行展示的是 ETF 价格（~$267）而非指数点数（~18000）。change_pct 仍然表达当日 NDX 方向，信息价值等同
- 后端测试 `test_market_refresh.py` 3 处 `^NDX` → `QQQM`（其中 `called_symbols` 断言保留，证实映射正确）
- DATA-MODEL.md / API-CONTRACT.md **不变**
- 未来若 FMP 对 `^NDX` 放开 Starter 访问，单行配置即可回切

---

## D038：F105 universe 与每日扫描解耦，候选池独立月级刷新

**日期**：2026-04-20
**feature**：F105 Market Breakout Scanner

**决策**：新增 `market_scan_universe` 表作为"市值≥500亿美股"候选池的持久化事实，与每日 breakout 扫描解耦。universe 由独立 cron 月级刷新（`UNIVERSE_CRON_DAY=1, UNIVERSE_CRON_HOUR=5`），每日扫描仅读取此表后调用 SMA 端点。

**原因**：
- 市值≥500亿的股票变化缓慢，周/月级刷新足够（用户敲定月级）
- 解耦后每日扫描只需 ~N 次 SMA 调用（N ≈ universe 规模 280），省去每日重复 3 次 screener 调用
- universe 表可持久化 `company_name / exchange / market_cap`，扫描任务读取直接生成 breakout 快照，无需等 screener 响应回填
- 故障隔离：universe 刷新失败不影响当日扫描（若冷启动则自动先补一次 refresh）

**放弃的备选**：
- **方案 N1：每日扫描时实时调 screener** — 放弃：每日 3 次 screener 调用为重复劳动；若 screener 端点波动则当天所有扫描报废
- **方案 N2：screener 调用结果放 in-memory / Redis 缓存** — 放弃：本项目无缓存层（D017 仅前端有 react-query），为此单端点引入缓存过度
- **方案 N3：一张表合并 universe 与 scan 结果** — 放弃：违背单一职责（universe 是全市场事实，scan 是 breakout 选择），字段集与刷新频率不同

**影响**：
- DATA-MODEL.md 新增 `MarketScanUniverse` 实体
- 后端新增 `UniverseRefreshService` + 独立 cron 任务（`refresh_job.py` 或新文件）
- 冷启动：扫描任务启动时若 `market_scan_universe` 表为空，自动先触发一次 universe refresh 作为初始化
- Upsert 语义：`last_seen_at` 记录最近一次 refresh 中出现的时间；掉出 universe 的记录不删除，每日扫描通过 `last_seen_at >= 最近 refresh 时间` 筛选有效行
- 环境变量 `UNIVERSE_CRON_DAY / UNIVERSE_CRON_HOUR / UNIVERSE_CRON_MINUTE` 已加入 `.env.example`

---

## D039：F105 扫描数据源选 SMA 端点，EOD fallback 透明兜底

**日期**：2026-04-20
**feature**：F105 Market Breakout Scanner

**决策**：每日扫描主路径使用 FMP `/stable/technical-indicators/sma?periodLength=150&timeframe=1day`，每次请求返回时间序列（每点含 `date/open/high/low/close/volume/sma`）。本地只需计算 20 日 MA150 线性回归斜率 + 应用 breakout 判定。端点不可用（402/403/非 200）时在 `fmp_client` 层透明切换到 `/stable/historical-price-eod/full`，本地复用 F002 `signal_engine.py` 的 MA150 + 斜率算法。

**原因**：
- SMA 端点单次调用即包含 breakout 判定所需的全部数据（昨日/今日的 close+sma、最近 20 日 sma 序列）
- 单次 payload ≈ 25 行 JSON（取最近 25 交易日窗口），比方案 Y（170 行 EOD）小 ~7 倍
- MA150 由 FMP 计算，本地只算 20 日线性回归，逻辑简化
- API 调用预算：1 股/次 × ~280 股 = ~280 次；300/min + burst 50 token bucket 下约 56s 可完成，符合 <90s 目标

**放弃的备选**：
- **方案 Y：全量批量拉 171 天 EOD 本地算 MA150** — 降级为 fallback；主路径不选的原因是每次响应 7× 大、本地算 MA150 的代码路径更长
- **方案 Z：组合并行** — 放弃：并发让 token bucket 策略复杂化，收益不明显

**影响**：
- `backend/app/external/fmp_client.py` 新增 `get_sma_series()` 方法 + fallback 逻辑 `get_ma150_series_or_eod()`
- Starter tier 是否覆盖 SMA 端点 FMP docs 页未能确认；S1 Sprint Contract 第一步必须做 live smoke test，失败自动走 fallback
- Fallback 触发时记 SystemLog WARN `"SMA endpoint unavailable, falling back to EOD"`
- `signal_engine.py` 的纯函数接口（D021）可直接被 scanner service 复用

---

## D040：F105 `market_breakout_scans` 只存最新快照，覆盖写入

**日期**：2026-04-20
**feature**：F105 Market Breakout Scanner

**决策**：`market_breakout_scans` 表只保留最新一次扫描的结果，不保留历史。扫描开始时在单事务内 `DELETE FROM market_breakout_scans; INSERT ALL rows;`。

**原因**：
- 用户明确"只展示今日扫描结果，不需要历史"（v1.2 project-init 对话）
- 避免累积表带来的索引维护、vacuum 成本
- 后续如需历史回溯，可追加 `market_breakout_scan_history` 表不破坏当前读路径

**放弃的备选**：
- **保留 7 / 30 天快照** — 放弃：需求未明，先按 YAGNI 做最小，历史需求出现时再引入历史表
- **版本化行（同表保留多 scan_date）** — 放弃：读取快照时需额外按 `scanned_at DESC LIMIT` 筛选，逻辑复杂度换不到用户价值

**影响**：
- `MarketBreakoutRepository.replace_scan()` 必须单事务 `DELETE` + `INSERT`，事务中断不得留空表（通过 SAVEPOINT 或回滚）
- 若扫描过程中发生异常，保留上次快照（不做清空）— 即事务只在成功获取所有扫描结果后才执行

---

## D041：F105 扩展 `/api/stocks/:ticker/chart` 行为，非 watchlist ticker 走 on-demand fallback（落实 D033）

**日期**：2026-04-20
**feature**：F105 Market Breakout Scanner
**上位决策**：D033（曾推迟该设计至"首个含外部 ticker 的 widget"立项，F105 即该立项）

**决策**：在服务端扩展现有 `GET /api/stocks/:ticker/chart` 行为：ticker 不在 `stocks` 表时，fallback 拉 FMP `/stable/historical-price-eod/full?from=今日-400&to=今日` on-demand 获取数据，服务端算 MA150 序列返回；**不写 `DailyBar` 表**。响应 schema 对前端完全不变（ChartWidget 零改动）。`pullbackMarkers` 在 fallback 路径下固定返回空数组。

**原因**：
- 方案 A（扩展现有端点 + 服务端分支）对前端零侵入，最符合 CLAUDE.md "加新功能 = 加 widget + 加 endpoint + 注册一行" 原则
- 复用 service 层的 MA150 计算逻辑，新增代码只在数据获取层增加 branch
- 不入库避免 Scanner 池污染 watchlist 的 DailyBar 数据窗口（250 天），保持 F003 的"watchlist 增量维护"语义纯净

**放弃的备选**：
- **B：新建独立 on-demand 端点** — 放弃：前端 ChartWidget 需判断 ticker 属于 watchlist 还是非 watchlist 走不同端点，逻辑复杂
- **C：Scanner widget 自带迷你 Chart** — 放弃：两份 chart 实现会漂移，维护成本双倍

**影响**：
- `stock_detail_service.get_chart()` 增加 ticker 查库分支；fmp_client 新增 `get_historical_eod_range()`（复用现有 EOD 调用）
- 复用既有错误码 `EXTERNAL_API_ERROR` (502) 用于 FMP 外部故障（F105-b 实现时确认：现网代码 + test_stock_detail 已固化此命名，API-CONTRACT.md 已统一）
- Pullback markers 固定空数组是契约级约定（F105 场景无回踩历史需求）；若后续需要，再扩展
- 不引入缓存层（一次用户点击对应一次 FMP 调用；性能瓶颈出现时再加）

---

## D042：F105 扫描调度独立 cron，错开现有 watchlist refresh

**日期**：2026-04-20
**feature**：F105 Market Breakout Scanner

**决策**：Scanner 扫描不复用 `REFRESH_CRON_*`（watchlist EOD 刷新），而是独立一个 `SCANNER_CRON_*`，默认 `HOUR=6, MINUTE=15`（北京时间），在 watchlist refresh 之后 15 分钟启动。

**原因**：
- watchlist refresh ~30 次调用 <10s，scanner ~280 次调用 <60s，两者若同时跑会竞争 FMP 300/min token bucket
- 独立 cron 任务解耦失败影响：scanner 失败不影响 watchlist；watchlist 失败不阻塞 scanner
- 观测性分离：SystemLog source 区分 `data_refresh` vs `market_scanner`，排查快
- 15 min 缓冲给 watchlist refresh 充足完成窗口（<10s 实际 + 含异常重试余量）

**放弃的备选**：
- **A：串行共用 cron** — 放弃：scanner 失败会让"watchlist 已刷新"的观测模糊
- **C：并发同时跑** — 放弃：token bucket 竞争导致整体耗时增加，无并发收益

**影响**：
- 新增环境变量 `SCANNER_CRON_HOUR / SCANNER_CRON_MINUTE`
- `refresh_job.py`（或新 `scanner_job.py`）注册独立 APScheduler 任务
- `SystemLog` 新增 source 值 `market_scanner` / `universe_refresher`

---

## D043：widget 类 feature 跳过 design-bridge
**日期**：2026-04-20
**决策**：纯 widget 形态的 feature（新增一个挂在 Workbench 上的 widget，不引入新页面、不改框架）不走 design-bridge skill，不产出独立 design-spec 章节；视觉规格沿用 Workbench 既有约定：tokens.css 变量 + shadcn/ui 组件 + 参考既有 widget（WatchlistWidget / ChartWidget / FundamentalsWidget）。feature 的 `notes` 字段追加"视觉沿用清单"即可替代 design-spec。

**原因**：Workbench 架构（react-grid-layout + WidgetRegistry）本身的设计意图就是"加一个 widget 等于注册一行 + 复用既有视觉"，F100-F104 均未单独出 design-spec。再为 F105 走一遍 design-bridge 属于流程冗余，且会产出与既有 widget 重复的视觉规格。

**放弃了什么**：独立的 F105 design-spec 章节、单独的 component-plan 条目、design-bridge 的 data-mapping 校验（F105 字段命名由 DATA-MODEL.md + API-CONTRACT.md 直接约束，无需额外映射层）。

**影响**：
- F105 phase 从 `design_needed` 直接前进到 `ready_to_dev`，不经 design-bridge
- 未来新增 widget-only feature 可援引 D043 同样跳过 design-bridge
- 若 feature 引入新页面、新布局模式或框架级视觉变更，仍必须走 design-bridge
- feature-dev skill 的前置条件检查中，widget-only feature 允许 design-spec.md 不含该 feature 章节，以 `notes` 中"视觉沿用清单"为准

---

## D044：FMP 共享限流器 + Scanner 6 并发
**日期**：2026-04-21
**决策**：
- 将 `FmpClient` 的 token-bucket 从 per-instance 提升为**进程级共享限流器** `_FmpRateLimiter`，通过模块级单例 `default_rate_limiter()` 注入所有生产 `FmpClient` 实例；DI 工厂 (`dependencies.py`、`main.py::_fmp_factory`) 均走该单例。
- 在限流器中增加 `threading.BoundedSemaphore(6)` 并发上限；`FmpClient._request` 先获取 semaphore、再获取 token、finally 释放 semaphore。
- `MarketScannerService.run_scan` 改为 `ThreadPoolExecutor(max_workers=6)` 并发执行 per-ticker FMP 调用；主线程聚合 hits/计数器 并串行写入 `SystemLog`（SQLite single-writer 约束）。
- OK 日志追加 `duration_s=X.XX workers=6` 字段便于观测。

**原因**：
- **共享限流**：scanner 每日扫 ~250 ticker；watchlist refresh ~30 次；用户手动触发 chart/fundamentals 数十次。三路并行时若各自独立 bucket（50 tokens、5 rps）会叠加冲破 FMP 300 rpm 上限，存在被限流/封禁风险。
- **并发上限 6（Semaphore）**：token bucket 只控"长期速率"，burst 50 在 200ms 内可瞬时发出 50 个 in-flight 请求，对单端点（如 SMA）不友好；Semaphore(6) 匹配用户实测的安全并发边界（~5 rps × 1.2s 平均延迟）。
- **ThreadPoolExecutor（非 asyncio）**：`FmpClient` 基于 sync `httpx.Client`；改 async 会传染到所有 11 个 caller。线程池方案把并发改动局部化在 scanner。
- **主线程写日志**：per-ticker 失败/fallback 日志在 worker 中仅收集到 `pending_logs` 列表，主线程在 ThreadPoolExecutor 结束后串行写入 SystemLogRepository，避开 SQLite `check_same_thread=True`。

**放弃了什么**：
- **进程外限流器（Redis / 中间件）**：单进程 SQLite 部署下属于过度设计，引入额外运维面。
- **asyncio 全线改造**：ROI 低；当前同步链路清晰，引入 async 会同时改动 DI、scheduler、所有 service，超出 F105-a5 范围。
- **per-worker session**：ThreadPoolExecutor worker 不直接访问 DB，避免 SQLite 多线程约束，也简化实现。

**影响**：
- 新增模块级单例 `default_rate_limiter()` + `reset_default_rate_limiter()`（test-only）。
- `FmpClient.__init__` 新增 `rate_limiter` 参数（可选注入，默认每实例一个私有 limiter 以保持测试隔离）。
- 测试侧：`test_fmp_client.py` 现有 40 条保持不变（per-instance 路径）；新增 4 条覆盖共享 limiter、Semaphore(6) 上限、异常释放、单例语义。
- Scanner 测试侧：新增 3 条覆盖并发加速（ThreadPool 实际并行）、OK 日志含 duration_s/workers、D040 语义在并发下保留。
- 可观察性：scan OK 日志含 `duration_s` 字段，便于对比并发前后耗时差异。

**2026-04-22 补丁：429 重试策略强化**
- 背景：生产日志观察到 scanner 运行中偶发 `TGT scan failed: Client error '429'`。旧策略（sleep 1s 重试 1 次后直接抛错）在 FMP 端瞬时突发 429 时兜底不足，将 ticker 直接计入 failed。
- 调整：`FmpClient._request` 保留限流主策略（共享 bucket + Semaphore(6)）不变；仅扩展重试：
  - 最多 `MAX_RETRIES_429 = 3` 次重试（总尝试 ≤ 4）
  - 指数退避：1s / 2s / 4s，上限 `RETRY_BACKOFF_MAX_S = 8s`
  - 若响应含 `Retry-After`（秒数或 HTTP-date），优先采用其值，上限 `RETRY_AFTER_CAP_S = 30s`
- 其他状态码（5xx、4xx）行为不变：立即抛错、不重试。
- 测试新增：`test_429_exhausts_max_retries_then_raises`、`test_429_exponential_backoff_waits`、`test_429_honors_retry_after_seconds`、`test_429_retry_after_capped`。

## D045：F106 Multi-Signal Scanner 的单表多 signal_type 数据模型

**日期**：2026-04-21
**状态**：accepted
**Feature**：F106

**决定**：
- 在 `market_breakout_scans` 表追加 `signal_type String(32)`、`volume BigInteger NULL`、`volume_ratio_20 Float NULL` 三列。
- 唯一键由 `(scan_date, ticker)` 改为 `(scan_date, ticker, signal_type)`，允许同 ticker 同日对多条规则同时命中各写一行。
- 所有信号规则参数集中在 `backend/app/services/scanner_params.py`，与业务逻辑分离，便于用户调参而不改代码。
- `GET /api/market/breakouts` 默认 type 列表为 `a1_stage_breakout,a2_slope_flip,b2_ma_pullback`；F105 legacy crossover 保留入库但不在默认响应中暴露，需显式 `?type=legacy_crossover` 请求。
- scanner FMP 抓取窗口从 35 天扩至 90 天（A1 需要 60 日 MA150 近似水平的历史序列）；单次调用仍只消耗 1 次 FMP 额度。

**原因**：
- **单表 vs 新表**：新表会带来两套覆盖写语义 + 两个读端点 + 两个 widget 的维护成本；F106 的业务语义（扫描出的信号集合）与 F105 同质，只是规则更多，数据上属于同一实体的扩展而非新实体。
- **多行 vs 合并行**：多行是干净的关系模型；合并行（一个 ticker 一行，信号类型数组）会让 API 排序、前端分组、按信号统计等全部复杂化，且不符合 SQLite 的表达习惯。
- **默认排除 legacy**：现有 F105 规则与 A1 语义部分重叠（都是"今日穿越"），混展会让用户迷惑；保留入库作对照基线，不强迫用户在 UI 中看到两遍。
- **参数独立文件**：用户明确提出"参数要能方便改"；放 Pydantic Settings / env 过度工程，直接一个 `scanner_params.py` 模块常量即可。
- **抓取窗口 90 天**：A1 要求 MA150 过去 60 个交易日近似水平，加上斜率窗口缓冲，90 个自然日约 62-65 个交易日，足够覆盖。

**放弃了什么**：
- **signal_type 作为 Enum 类型**：SQLite 不原生支持 Enum；String + 上层校验足够。
- **每种 signal_type 独立表**：DDL 爆炸、跨类排序需要 UNION，运维成本远大于收益。
- **扫描时写"未命中"行**：会让表从 ~10 行膨胀到 ~2000 行 × 4 type，且读端点要过滤，没有价值。
- **把 volume 拆到独立表**：EOD/SMA 返回已经携带 volume，冗余到本表一列无额外 IO。

**影响**：
- 新增 Alembic migration `003_f106_signal_type_and_volume.py`：SQLite 通过 batch_alter_table 完成（加列 + 重建唯一键）。
- `BreakoutScanRow` dataclass 扩字段；`MarketBreakoutRepository.replace_scan` 接受混合 signal_type 的行集合。
- `MarketScannerService.run_scan` 对每个 ticker 的 bars 序列**并行**跑 4 条规则（legacy + a1 + a2 + b2），无额外 FMP 调用。
- `_evaluate_breakout` 保留并重命名为 `_detect_legacy_crossover`；新增 `_detect_a1_stage_breakout` / `_detect_a2_slope_flip` / `_detect_b2_ma_pullback`，各自纯函数，参数从 `scanner_params` 常量读。
- API schema 的 `BreakoutItemOut` 新增 `signal_type / slope_value / volume / volume_ratio_20`，前端类型同步。
- 前端 widget 改为 shadcn Tabs：Tab "Stage Breakout"（合并展示 A1、A2，每行加 signalType badge）和 Tab "Pullback"（B2）；legacy 不暴露。

---

## D046：Widget 外壳层 UI 规范允许硬编码值（title 底色 / 内部间距）

**日期**：2026-04-21
**状态**：accepted
**Feature**：F109

**决定**：
- widget title bar 底色统一硬编码 `#ebf2fa`（覆盖早期 `--color-surface-muted` token 规格）。
- widget 内容根元素顶部偏移统一 `marginTop: -5px; marginLeft: -5px`；多子组件 widget 内部间距用 `gap-1`（4px）。
- 以上三个值**允许硬编码**，不再走 tokens.css。仅适用于 widget **外壳层**（WidgetShell + widget 顶级容器），不得扩散到业务组件内部。
- design-spec.md §Workbench-Widget-Shell 已备案；任何偏离须在 DECISIONS.md 再开一条。

**原因**：
- **跨 widget 视觉一致性压倒 token 抽象**：`#ebf2fa` 是经过多轮视觉打磨选出的精确值，试图用 token 名称表达反而语义含糊（`muted` / `surface-alt` / `shell-head-bg` 都不贴切），最终会变成一个只有一处用途的 token，增加抽象成本无收益。
- **`-5px` 偏移是对 Shell 内容区 padding 的纠正**：既有 Shell 内部 padding 16px 对多数 widget 偏大，-5px 紧贴是目视优化结果，未来若修改 Shell padding 本偏移会被同步调整；用 token 反而让调整路径割裂。
- **`gap-1` 用 Tailwind 原子类即可**：这是布局原子值，无需进一步抽象。

**放弃了什么**：
- **用新 token `--color-widget-shell-head-bg`**：会让 tokens.css 有多个只在一处使用的 token，维护反而重。
- **用 `bg-muted` 继续配合全局 muted token**：muted 本身 token 值已被其它组件复用，若为 widget 单独改动会污染其它使用者。
- **用 CSS variable in-file 定义**：仍是 token 形式，收益等同于方案 B。

**影响**：
- `WidgetShell.tsx` 的 handle bar 从 `bg-muted` 换为 `style={{ backgroundColor: '#ebf2fa' }}`。
- 4 个 widget（Watchlist / Pullback / Fundamentals / QuickAdd）根节点加 inline style `marginTop/marginLeft: -5px` + Tailwind `gap-1`。
- 新 widget 加入 Workbench 时必须照同规范（已写入 design-spec.md）。
- `scan build` / linter 不会对 inline style 报错，但需在 code review 注意不要把规范扩散到业务组件内部。

---

## D047：F108 `/fundamentals` `/pullbacks` 沿用 D041 on-demand 语义（不再走 system-design）

**日期**：2026-04-21
**状态**：accepted
**Feature**：F108

**决定**：
- `GET /api/stocks/:ticker/fundamentals` 对非 watchlist / inactive ticker 不再 404，直接打 FMP `get_ratios_ttm` + `get_key_metrics_ttm`，错误路径保留（空 ticker → 404；FMP httpx error → 502 `EXTERNAL_API_ERROR`）。
- `GET /api/stocks/:ticker/pullbacks` 对非 watchlist / inactive ticker 返回 `200 + items=[]`，不再 404；也不 on-demand 计算（pullback 依赖本地 180 天 daily bars 滚动窗口，on-demand 成本高、语义弱，保持空 list）。
- **不重新走 system-design**：本变更是 D041（chart on-demand fallback）的同族语义推广，不涉及新的数据源、限流或存储模型变化，只是把 scanner 场景下的 UX 体验延伸到两个邻近端点。

**原因**：
- **用户侧痛点明确**：scanner 让用户点任意 ticker 看图成为常态（F105），但 Fundamentals / Pullbacks Tab 仍返回 404，造成"图能看基本面看不到"的体验撕裂。
- **D041 已定义原则**：`/chart` 的 fallback 已确认"Scanner 场景里 ticker 一旦被点，都应能看图"，推广到 fundamentals 是同一原则自然延伸。
- **pullbacks 不 on-demand**：历史回踩需要本地 180 天 daily bars + signal 引擎的状态计算，on-demand 一次要拉 260 天 bars 并跑完整引擎，成本不成比例；且该数据对非 watchlist ticker 没有强产品价值（"看看基本面"是主诉求，"看历史回踩"属于自选股深度研究场景）。

**放弃了什么**：
- **pullbacks on-demand 计算**：成本收益不成比例（见上）。
- **所有非 watchlist 请求都走 FMP**：对 pullbacks 明确划边界，避免把 /pullbacks 变成一个对每个未知 ticker 都要跑 180 天 bars + signal 引擎的重接口。
- **开新端点 `/fundamentals/on-demand`**：既有 `/fundamentals` 路径对前端语义已自洽，前端 FundamentalsWidget 不需感知 ticker 来源，复用即可。

**影响**：
- `StockDetailService.get_fundamentals` 移除 `_resolve_active_stock` 前置校验，直接大写 ticker 打 FMP。
- `StockDetailService.get_pullbacks` 对 `stock is None or not is_active` 返回空 list 而非抛 404。
- `API-CONTRACT.md` 这两接口的 404 语义收窄：fundamentals 仅对空 ticker 返 404；pullbacks 不再 404。
- `test_stock_detail.py` 的 `test_detail_endpoints_404_when_ticker_inactive` 需要再次调整（F105-b 已动过 chart 分支），继续收窄到空 ticker 的 404 场景。
- 前端 FundamentalsWidget / PullbackWidget 代码无需改（既有 loading / empty / error 三态已覆盖新 200-empty 语义）。
- FMP 共享 bucket（D044）覆盖新调用路径；scanner 场景下用户点击触发的 fundamentals 请求与已有 chart fallback 共享限流，无额外风险。

---

## D048：前端单测基建延迟到 v1.4

**日期**：2026-04-22
**触发**：F106-c Evaluator 阶段发现 Contract 列了 6 条 RTL 单元测试，但项目无 vitest / @testing-library/react / jsdom 基建
**决策者**：用户（F106-c Evaluator 选项 B）

**选项对比**：
- A：本 sprint 引入 vitest + @testing-library/react + jsdom（3 新 dev deps），补 6 条单测后 commit
- B：降级 F106-c Contract 的测试门禁为"typecheck + build + docker 手工 E2E"，单测基建留到 v1.4 统一规划
- C：写 `.test.tsx` 但不配框架 → 零价值

**选择**：B

**理由**：
1. F107/F108/F109 都是反向补契约，都面临同样问题；单独给 F106-c 引 vitest 意义有限
2. v1.4 规划一个"前端测试基建"sprint 统一做，效率更高：届时 F106-c/F107/F108/F109 的单测一并补
3. 后端已有 vitest 级别的 pytest 全量覆盖（252/254 绿），前端门禁由 `tsc -b` + `vite build` + docker E2E 三者兜底，v1.3 阶段可接受

**影响**：
- F106-c Contract 的可测试标准 #3–#8 改为"代码审查/手工回归"，#9–#11 保留为硬门禁
- v1.4 必须开一个"前端测试基建"feature：装 vitest + @testing-library/react + jsdom，补本迭代漏掉的所有单测
- F107/F108/F109 的 Contract 按同样路径降级（引用 D048）


---

## D049：/chart 响应携带 sharesFloat（F107-b1）

**日期**：2026-04-22
**触发**：F107-b 需要在 ChartWidget 计算并展示"当日成交量 ÷ 流通股"的百分比；前端必须拿到 shares_float 才能算
**决策者**：用户（plan 协商阶段，AskUserQuestion A1 vs A2）

**选项对比**：
- A1：`/chart` 响应顶层加 `sharesFloat: int | null`，一次请求搞定
- A2：新开 `/api/stocks/{ticker}/float` 端点，前端并行 useQuery 拉
- A3：塞进 `/fundamentals`（但 shares_float 不在估值维度，语义错位）

**选择**：A1

**理由**：shares_float 是图表计算上下文（每根 bar 的 volume 都要用），与 /chart 的语义同源；前端不必维护第二个 useQuery + 状态协调；/fundamentals 维持 PE/PS/PEG/FCF 聚焦。

**影响**：
- `backend/app/schemas/stock_detail.py` 的 `ChartData` 加 `shares_float: int | None = None`（camelCase 别名 `sharesFloat`）
- `backend/app/services/stock_detail_service.py` `_assemble_chart_payload` 签名加 `shares_float`
- `API-CONTRACT.md` /chart 响应补字段说明
- 旧前端兼容：字段可缺省，v1.2.x 前端读不到也不炸

---

## D050：shares_float 落 Stock 表 + 24h TTL DB 缓存（F107-b1）

**日期**：2026-04-22
**触发**：每次 /chart 都打 FMP /profile 既浪费 300rpm bucket，也慢；必须缓存
**决策者**：用户（plan 协商，B2 内存 vs B3 DB）

**选项对比**：
- B1：无缓存，每次 /chart 都打 FMP
- B2：进程内存字典 + TTL
- B3：Stock 表加两列 `shares_float` + `shares_float_refreshed_at`，24h TTL

**选择**：B3

**理由**：
1. 跨实例一致（docker 多进程 / 未来 worker / 开发重启都不丢缓存）
2. shares_float 日级变化，24h TTL 够用
3. 与 Stock 表既有 last_refreshed_at 一致风格
4. 代价仅两列 nullable，在线 add column 安全

**实现**：
- Alembic 004 加两列，均 nullable 默认 null
- 常量 `_SHARES_FLOAT_TTL = timedelta(hours=24)`
- 判定：`refreshed_at is None or (now - refreshed_at) > _SHARES_FLOAT_TTL` → miss，打 FMP
- 即使 FMP 返回 null，也写回 `refreshed_at = now` 以避免 24h 内反复请求空数据

**未决 / 候选**：
- 日后遇到 split / IPO 导致 float 跳变的 bug，再加主动失效（reactivate 或事件触发）

**影响**：
- Stock 模型 + DATA-MODEL.md + 003→004 migration chain
- 仅 watchlist 路径（`_chart_from_watchlist`）用缓存；fallback 路径（非 watchlist）直接打 FMP，不写 DB（无 Stock 行）

---

## D051：FMP /shares-float（D051 修订，原计划 /profile）+ floatShares 字段（F107-b1）

**日期**：2026-04-22
**触发**：Context7 官方文档 `/stable/shares-float-all` 用字段名 `floatShares`；社区与旧版 `/profile` 历史上返 `sharesFloat`；需要稳定兜底
**决策者**：Claude（Generator 阶段 Context7 查询结果 → Evaluator 阶段 docker E2E 回写）

**数据源选择（最终）**：
- 端点：`GET /stable/shares-float?symbol={ticker}&apikey=...`
- 响应：list，首记录含 `{symbol, date, freeFloat, floatShares, outstandingShares, source}`
- 字段提取：`record.get("floatShares") or record.get("sharesFloat")`（后者仅做前向兜底）
- 共享 rate limiter（D044，300rpm bucket + concurrency 6）

**理由（修订）**：原选 `/profile` 预期顺带拿到 sharesFloat；Generator E2E 阶段实测 FMP Starter 档 `/stable/profile` 响应不含 `floatShares` / `sharesFloat` 任一字段（无论拼写），AAPL 返回 `price / marketCap / sector / ...` 但两个 float 字段为 None。改走专用 `/stable/shares-float` 端点，字段 `floatShares` 以整数返回，语义干净。

**影响**：
- `fmp_client.py`：`FMP_EP_SHARES_FLOAT = "/shares-float"` + `get_shares_float(symbol)` 方法（替换原 `FMP_EP_PROFILE` / `get_company_profile`）
- 走 `_request` 共享限流
- 单元测试 fixture 改为真实 shares-float payload 形态；`sharesFloat` 别名分支保留作兜底
- 契约合规性：合约原写 `/stable/profile`，Evaluator 阶段按 feature-dev Rule 8 回写文档（本条 + API-CONTRACT.md + DATA-MODEL.md）

---

## D052：历史 bar 的 Vol/Float 比率统一用当前快照 float（F107-b1 + b2）

**日期**：2026-04-22
**触发**：stocks 表只存当前 shares_float，不存每日历史 float；若要精准则需新表 + 每日抓取
**决策者**：用户（plan 协商）

**选择**：所有历史 bar 的分母统一用当前 shares_float；UI 标注"近似"

**理由**：
1. FMP 不提供按日 shares_float 历史 API
2. 自建历史表：空间 × 刷新成本 × 用户心智收益比过低
3. shares_float 年级变化，"近似"误差对投资判断几乎无影响（split 会跳变，已记入未决候选）

**影响**：
- design-spec.md ChartWidget 小节标注"Vol/Float 近似值，未追踪历史 float"（F107-b2 阶段写入）
- 避免了 Stock × date 的新维度表

## D054：/fundamentals 响应携带 sharesFloat，复用 F107-b1 缓存路径（F107-b3）

**日期**：2026-04-22
**触发**：F107-b3 要在 FundamentalsCard 显示 Float 绝对值；后端需暴露字段
**决策者**：用户（b3 contract 协商）

**选择**：
1. 在 `get_fundamentals` 内调用 `_resolve_shares_float_for_watchlist`（F107-b1 已有 24h TTL DB 缓存 + FMP `/stable/shares-float` 回源），不新增 service / 缓存层
2. 非 watchlist / inactive ticker → `sharesFloat: null`，不做 on-demand 回源（与 b3 边界一致；F108 再放开）
3. 前端单位格式：`15.23B / 987.65M`（无 `$` 前缀，与 marketCap/FCF 区分）

**理由**：
1. F107-b1 已建好缓存路径，再走一遍是零成本复用；不复用就会重复抓 FMP
2. /chart 与 /fundamentals 共享同一 Stock.shares_float 缓存项 → 同一 ticker 两个 widget 命中同一份数据，TTL 协同
3. 不带 `$` 前缀避免误读为美元金额（Float 是股数）

**影响**：
- API-CONTRACT.md /fundamentals 字段表 + 响应示例已追加
- 前端 `Fundamentals` 类型 + FundamentalsCard 增 'Float' 行（右列末位）
- F108 放开 watchlist 限制后，可在 b3 基础上加 `_resolve_shares_float_for_fallback`，不影响本次决策


## D-F110a-1：bulk 添加采用"快速失败"策略（F110-a）

**日期**：2026-04-22
**触发**：`POST /api/watchlist/bulk` 遇到 FMP 网络异常时的处理策略
**决策者**：Sprint Contract（用户确认）

**选择**：单个 ticker FMP 网络失败（`code != NOT_FOUND` 的 `EXTERNAL_API_ERROR`）→ 中止整个 batch，返回 502；不容错继续。

**理由**：
1. 避免半成功状态（已成功写入 N 个，第 N+1 个网络失败，后续 M 个又成功）导致前端无法准确反馈用户
2. 网络失败通常是暂时性的，整体重试比部分重试逻辑更简单，用户体验一致
3. DUPLICATE / NOT_FOUND 属于业务层分类，继续处理是正确的；网络失败属于基础设施层，中止是正确的

**影响**：
- `bulk_add_stocks` 仅捕获 `DUPLICATE` 和 `NOT_FOUND`，其他 `APIError` 冒泡至 router → 502
- 前端（F110-b）应在收到 502 时提示"导入失败，请重试"，而非展示部分成功列表


## D047：F108 `/fundamentals` / `/pullbacks` 沿用 D041 on-demand 语义

**日期**：2026-04-22
**触发**：Scanner 场景用户点击任意 ticker → 切 Fundamentals / Pullbacks 标签 → 原逻辑走 `_resolve_active_stock` → 404，体验割裂

**决策**：
1. `/fundamentals`：直接调 FMP `ratios-ttm` + `key-metrics-ttm`，不再要求 ticker 在 watchlist。只对空 ticker（trim 后空串）返回 404；FMP 网络失败返回 502。
2. `/pullbacks`：非 watchlist / inactive ticker → 返回 200 + 空列表（不走 FMP on-demand）。pullback 计算依赖本地 180 天 daily bars 滚动窗口，非 watchlist ticker 无历史，on-demand 成本高且语义不强；返回空列表与 `/chart` fallback 的 `pullbackMarkers: []` 语义一致（D041 族决策）。
3. `_resolve_active_stock` 仍由 `/chart` 使用（chart 需要 DB bars → inactive / 不在 DB 的 ticker 走 on-demand FMP fallback），不删除。

**为何不重新走 system-design**：与 D041 同族决策（on-demand fallback 语义推广），D041 已通过系统设计确认。API-CONTRACT.md 的 404 语义范围收窄，不涉及新 endpoint 或 schema 变更。

**影响**：
- API-CONTRACT.md：`/fundamentals` 404 仅限空 ticker；`/pullbacks` 非 watchlist → 200+[]
- `test_detail_endpoints_404_when_ticker_missing` / `_inactive`：pullbacks + fundamentals 分支从 404 改为 200


## D055：F111-a on-demand ticker 数据当日缓存策略

**日期**：2026-04-22
**触发**：用户在 watchlist / breakout scanner 中点击 ticker 时，chart fallback 和 fundamentals 每次都打 FMP，同日切换同一 ticker 重复请求慢且浪费 API quota。

**决策**：引入 `daily_payload_cache` 表（`ticker, endpoint, as_of_date, payload_json`），以 `(ticker, endpoint, as_of_date)` 为唯一键存储每日响应 JSON。

缓存规则：
- 命中条件：`as_of_date == date.today()`（server local date）
- 覆盖对象：`/chart` fallback（非 watchlist ticker）+ `/fundamentals`（所有 ticker）
- 不覆盖：watchlist ticker chart（已从 daily_bars 读，无 FMP 调用）；pullbacks（返回空 list 无 FMP 调用）
- 错误不缓存：FMP httpx.HTTPError → 不写表，下次仍尝试 FMP
- 空结果不缓存：FMP 返回 None/空 dict → 不写表，保持原 null 路径

**为何不用 Redis / 内存缓存**：单用户局域网场景，SQLite 足够（D004 原则）；重启后缓存仍有效（session 级内存缓存重启即失）；无运维依赖。

**为何不清理旧记录**：每日最多几十行，全量数据极小（每行 ~5–10 KB JSON）；下次访问自然跳过旧行（`as_of_date != today()`）；无清理任务 = 无背景作业竞争风险。

**影响**：
- 新表 `daily_payload_cache`（Alembic migration 005）
- `stock_detail_service._chart_from_fmp_fallback`：先查缓存
- `stock_detail_service.get_fundamentals`：先查缓存
- 用户体验：同日第二次点击同一 ticker 响应速度由 ~500ms（FMP RTT）降至 ~5ms（SQLite read）


## D056：F112-b2 引入 DOMPurify 做新闻正文 HTML sanitize

**日期**：2026-04-23
**触发**：F112-b2 的 ArticleModal 需要渲染 FMP `/stable/fmp-articles` 返回的 `content` 字段（任意 HTML），直接用 `dangerouslySetInnerHTML` 存在 XSS 风险（`<script>`、`onerror` inline、`<iframe>` 等）。

**决策**：引入 `dompurify@3.4.x`（TypeScript 类型自带，无需 `@types/dompurify`），在 ArticleModal 渲染前对 `article.contentHtml` 调用 `DOMPurify.sanitize`，配置 `FORBID_TAGS: ['style','script','iframe','object','embed']` + `FORBID_ATTR: ['onerror','onload','onclick']`。

**为何不自己写白名单**：安全关键路径，DOMPurify 是 cure53 维护的主流方案，已处理各种 HTML 解析边缘 case（mXSS、SVG/MathML 注入、属性混淆等）；自写黑白名单几乎必然漏 payload。

**为何 Forbid 而非 Allow**：FMP 新闻正文格式多样（p/a/img/ul/li/h1-6/blockquote/table 等），写死 `ALLOWED_TAGS` 会丢排版；黑名单 + DOMPurify 默认 profile 足以覆盖 XSS 向量。

**为何不用 isomorphic-dompurify**：前端 SPA，无 SSR 需求；原生 dompurify 足够。

**影响**：
- 新依赖：`frontend/package.json` + `dompurify@3.4.1`
- `frontend/src/components/common/ArticleModal.tsx`：调用 `DOMPurify.sanitize`
- 包体积 +~50KB gzipped（可接受）



## D057：F113-a 新建 `news_articles_cache` 而不复用 `daily_payload_cache`

**日期**：2026-04-23
**触发**：F113-a 需要缓存 FMP 新闻文章，`daily_payload_cache` 已存在。

**决策**：新建独立表 `news_articles_cache`，不复用 `daily_payload_cache`。

**为何不复用**：`daily_payload_cache` 语义是"单 payload / 覆盖式写"，每行代表 `(ticker, endpoint, as_of_date)` 的一次整体响应 JSON。News 需要**多行增量 upsert**（每篇文章一行，按 `article_key` 去重），且去重逻辑（URL 或 SHA-256 hash）和索引模式（按 `published_at` 排序读取）与现有表完全不同。复用会混淆表语义并破坏现有 F111-a 路径。

**影响**：
- 新表 `news_articles_cache`（Alembic migration 006）
- 新文件 `backend/app/repositories/news_cache_repository.py`
- `backend/app/models/news_article_cache.py`


## D058：F113-b 不引入 @tanstack/react-query-persist-client

**日期**：2026-04-23
**触发**：F113-b 需要持久化 News 文章到 localStorage；features.json 原计划使用 `@tanstack/react-query-persist-client` + `@tanstack/query-sync-storage-persister`。

**决策**：改用手动 localStorage，不引入该库。

**为何不用 PersistQueryClientProvider**：该方案持久化整个 QueryClient 缓存（watchlist、chart、signals 等），不只是 news articles。对其他 query 的持久化既多余又有潜在风险（过期数据被恢复为 initial state）。针对单一 query 做定向持久化用手动 localStorage 更简洁、可控。

**实现**：`src/lib/news-persist.ts` — key `ma150.news.v1.<YYYY-MM-DD>`，`useQuery.initialData` + `staleTime: Infinity`（有今日缓存时），`useMutation` 做增量 refresh。

**影响**：
- 无新依赖
- 4 文件（原计划 5 文件 + 1 依赖）
- 仅 `['news', 'articles']` query 被持久化，其余 query 行为不变


## D059：Universe refresh 硬过滤 5-letter-X 共同基金代码

**日期**：2026-04-23
**触发**：`MarketBreakoutWidget` 再次出现 OAKIX / VPMAX / ABALX / CAIBX 等共同基金代码（上次 153dcda 已加 `isFund=false` 并验收通过）。

**根因**：FMP `company-screener` 的 `isFund=false` 过滤不稳定——部分开放式共同基金（5 字母、以 X 结尾）仍会随 `exchange=NASDAQ` 的响应返回。依赖 FMP 的单一过滤位不够。

**决策**：在 `universe_refresh_service._parse_screener_row` 增加一层 ticker 形态过滤：`^[A-Z]{4}X$`（即 5 字母以 X 结尾）一律 skip。SEC/FINRA 约定开放式共同基金代码都符合该形态；普通股 / ETF 基本不命中（ETF 为 2–4 字母，单 X 结尾如 XOM 仅 3 字母）。FMP 端 `isFund=false` 保留，作为首道过滤；本规则为 defense-in-depth。

**影响**：
- `backend/app/services/universe_refresh_service.py`：新增正则 + 过滤分支
- `backend/tests/test_universe_refresh_service.py`：新增 `test_refresh_skips_mutual_fund_tickers`
- 既有污染的 `market_scan_universe` 行：下一次月度 refresh 不再续期 `last_seen_at`，`MarketScannerService.list_active(since=latest)` 自动将其排除；breakout 表每次扫描 `replace_scan` 覆盖写，下次扫描即清空。


## D060：Cockpit 作为独立第三页（不并入 Workbench）

**日期**：2026-04-24
**触发**：v1.8 Cockpit Epic 启动，需决定 Cockpit 与现有 Workbench 的关系。

**决策**：新建独立页 `/cockpit`，TopNav 三页并列（`/workbench` / `/news` / `/cockpit`）。`frontend/src/cockpit/` 与 `src/workbench/` 零交叉引用，cockpit 拥有独立 `cockpitStore`（不复用 `useAppStore.selectedSymbol`），`CockpitChartWidget` 独立实现、不共享 `ChartWidget` 代码。

**放弃**：
- 方案 B：Cockpit 作为 Workbench 新 widget。放弃原因：Cockpit 是**决策工作流**（regime → setup → decision → order），Workbench 是**自由观察工作台**，语义冲突；将 7 个 cockpit widget 塞进 Workbench 会污染 Workbench 的 SMA150 验证场景，也会让 cockpitStore / useAppStore 的所有权混乱。
- 方案 C：共享 ChartWidget 代码。放弃原因：Cockpit 需要在图表上叠加 entry/stop/target 三条 horizontal line 及 setup annotation，Workbench 不需要；强行抽象会引入条件分支污染两端。接受代码重复换取模块解耦。

**布局引擎说明（2026-04-24 design-bridge 阶段补充）**：Cockpit **沿用 react-grid-layout**（而非"固定 3 栏不可拖"），与 Workbench 共用 RGL 引擎但拥有独立的 `CockpitRegistry` / `useCockpitLayoutStore` / localStorage key（`ma150.cockpit.layouts.v1`）。默认布局按 3 列信息分组（左：regime/earnings/pool；中：chart/setup/decision；右：position/order/action），但用户可拖拽/缩放/重置。理由：(1) 易于后续迭代（增减 widget 不需改框架）；(2) 与 Workbench 视觉一致性高（WidgetShell / 紧凑表规格全站统一）；(3) Cockpit 与 Workbench 的解耦由"工作流语义 + 目录隔离 + cockpitStore 独立 + ChartWidget 不共享"四条硬约束保证，与 RGL 复用无关。

**影响**：
- 新目录 `frontend/src/cockpit/`（pages / widgets / hooks / store / api / types）
- 新目录 `backend/app/routers/cockpit/` / `services/cockpit/`
- ARCHITECTURE.md 依赖规则：`cockpit/` 不得 import `workbench/`，反之亦然（由 ESLint `no-restricted-imports` 硬约束）
- CSS Token 可共享（design-spec.md 的 palette / spacing / typography 保持全站唯一）

---

## D061：market_indices 扩展至 17 symbol（不新建 sector_etfs）

**日期**：2026-04-24
**触发**：F201 Market Regime 需要市场宽度（SPY/QQQ/IWM）与 sector rotation（11 sector ETF）信号源。

**决策**：在既有 `market_indices` 表增加 14 行 symbol：SPY / QQQ / IWM + XLK / XLY / XLF / XLI / XLE / XLV / XLC / XLP / XLU / XLB / XLRE，总计 17 行（原有 SPX / NDX / TNX 保留）。不新建 `sector_etfs` 表。

**放弃**：
- 方案 B：新建 `sector_etfs` 表。放弃原因：schema 几乎与 `market_indices` 完全一致（都是日度 OHLC + 可选辅助指标），拆两张表引入 JOIN 无净收益；ETF 与 index 都是"市场级时间序列"，语义并无本质区别。

**Regime 评分默认阈值**（存入 `cockpit_params.py §1`，D070 修订，不进 .env）：
- `RISK_ON` ≥ 80
- `CONSTRUCTIVE` 60–80
- `NEUTRAL` 40–60
- `DEFENSIVE` 20–40
- `RISK_OFF` < 20

**Subscore 权重**（总分 0–100；权威来源 DATA-MODEL.md + API-CONTRACT.md；2026-04-24 F201 Sprint Contract 协商时修订）：
SPY trend(25) + QQQ trend(20) + IWM breadth(15) + Sector participation(20) + Risk appetite(10) + Volatility stress(10) = 100

> ⚠️ D061 原草案（system-design 阶段）写了不同的 6 维名称（breadth/trend/volatility/credit/rates/sentiment），与 DATA-MODEL.md 及 API-CONTRACT.md 字段冲突，已在 F201 Sprint Contract 协商阶段按 DATA-MODEL 优先级修订为上述版本。

**影响**：
- `market_indices` retention 由 5 个交易日扩展至 260 个交易日（覆盖 52-week 需求）
- 新调度 `fetch_sector_etfs_daily`（复用既有 indices 日度 fetch 框架）
- Regime 阈值与子项权重均写入 `cockpit_params.py §1`（D070 约定）；不新增 .env 变量

---

## D062：Setup 存储使用独立表 setup_snapshots（不扩 signals 表）

**日期**：2026-04-24
**触发**：F202 Setup Monitor 需要每日快照 setup 质量、distance_to_entry、reward_risk 等 cockpit 特有字段。

**决策**：新建 `setup_snapshots` 表，60 天 retention。不扩 `signals` 表字段。

**放弃**：
- 方案 B：扩展 `signals` 表，增加 `setup_type` / `quality` / `distance_to_entry` / `reward_risk` 等列。放弃原因：`signals` 是 Workbench watchlist 的 EOD 信号缓存，语义是"单资产多指标快照"；Cockpit 的 setup 是"**候选交易机会**"，二者生命周期不同（signals 每日覆写、setup 有状态流转 new → triggered → invalidated），混表会让 `signals` 膨胀并破坏现有 F104 watchlist 的数据契约。

**影响**：
- 新表 `setup_snapshots`（Alembic migration）
- 新 service `cockpit/setup_service.py`（复用 workbench 的 TA 计算但独立落表）
- 60 天 retention 由 APScheduler 日度任务清理

---

## D063：CockpitChartWidget 独立实现 + 独立 `/api/cockpit/chart/{ticker}` endpoint

**日期**：2026-04-24
**触发**：Cockpit Decision Panel 需要在图表上叠加 entry / stop / target 横线 + setup annotation；Workbench `ChartWidget` 不具备这些需求。

**决策**：新建 `CockpitChartWidget`（基于 lightweight-charts 重新实现，不 import Workbench 的 `ChartWidget`）+ 新 endpoint `GET /api/cockpit/chart/{ticker}?range=...`（复用后端 OHLC repository 但走独立 service 层）。

**放弃**：方案 B：ChartWidget 抽象出可配置 overlay prop。放弃原因：见 D060。

**影响**：
- `frontend/src/cockpit/widgets/CockpitChartWidget.tsx`
- `backend/app/routers/cockpit/chart.py` + `services/cockpit/chart_service.py`

---

## D064：选 LiteLLM 作为 AI 抽象层 + 单一动态 endpoint `/api/ai/{task_type}`

**日期**：2026-04-24
**触发**：v2.0 AI 层需要跨 provider（OpenAI / Anthropic / local）、结构化输出、fallback、成本追踪。

**决策**：
1. 选 LiteLLM `>=1.83,<2.0`（pin 到 pyproject.toml），已通过 context7 文档验证四项核心能力：Router / `response_format=Pydantic` / fallbacks / budget。
2. AI endpoint 采用**单一动态入口** `POST /api/ai/{task_type}`，`task_type` 为 path param（narrate_regime / explain_setup / rank_pool / contradict_plan / summarize_news / journal_reflect 等），后端 dispatch 到对应 handler。
3. **三 tier 模型配置**（.env 驱动，provider 可自由替换）：
   - `AI_MODEL_DEFAULT` — 低成本 nano（narrate / summarize / journal_reflect）
   - `AI_MODEL_CRITICAL` — 中等 mini（contradict_plan / decision-critical 路径）
   - `AI_MODEL_COMPLEX` — 完整 full（rank_pool 等推理密集任务）

**放弃**：
- 直接调用 OpenAI SDK：放弃原因：provider lock-in、无法 fallback。
- 方案 B：每 task 独立 endpoint（如 `POST /api/ai/narrate/regime`）。放弃原因：endpoint 蔓延；task_type 本质是 string dispatch，单入口 + `AiTaskType` enum 更易扩展。

**AI Gateway 架构**（`backend/app/ai/`）：
- `gateway.py` — 入口：校验 task_type → 查 memo 去重 → budget check → routing → guardrail → 落 ai_memos
- `routing.py` — task_type → tier → LiteLLM Router config
- `schemas/` — 每个 task_type 的 Pydantic 响应 schema（response_format 锁定）
- `budget.py` — 月度预算 cap（`AI_MONTHLY_BUDGET_USD`）
- `memo_repo.py` — 读写 `ai_memos`
- `guardrail.py` — 每个 task_type 的 post-validate hook
- `errors.py` — `AiProviderError` / `AiSchemaError` / `AiBudgetExceeded` / `AiGuardrailViolation`

**影响**：
- pyproject.toml 增 `litellm>=1.83,<2.0`
- .env 增 `OPENAI_API_KEY` / `AI_MODEL_DEFAULT` / `AI_MODEL_CRITICAL` / `AI_MODEL_COMPLEX` / `AI_MONTHLY_BUDGET_USD` / `AI_MEMO_CACHE_TTL_HOURS` / `AI_SCHEMA_VERSION`
- 新表 `ai_memos`（audit + dedup cache 双用途）
- API-CONTRACT.md 新增 AI 错误码：`AI_PROVIDER_ERROR` / `AI_SCHEMA_ERROR` / `AI_BUDGET_EXCEEDED` / `AI_GUARDRAIL_VIOLATION`

---

## D065：Earnings 数据仅 Cockpit 消费 + 每日增量 upsert

**日期**：2026-04-24
**触发**：F204 Earnings Panel 需要财报日历；Workbench / News widget 是否也应消费？

**决策**：
1. Earnings 数据只给 Cockpit 使用（Workbench / News 不读取 `earnings_events`），避免 widget 边界污染。
2. 使用 FMP `/stable/earnings-calendar`，每日一次增量 upsert（FMP 对未来 estimate 会更新，必须 upsert 而非 append）。
3. 拉取范围：`today - 7d ~ today + 14d`，老数据按 90 天 retention 清理。

**放弃**：方案 B：每周一次拉取。放弃原因：estimate 更新频率高于每周，会遗漏分析师调整。

**影响**：
- 新表 `earnings_events`
- 新调度 `EARNINGS_CRON`（default `0 18 * * *` 美东时间）
- `backend/app/routers/cockpit/earnings.py`
- FMP endpoint 映射新增 `/stable/earnings-calendar`

---

## D066：user_settings 单行单用户（CHECK id=1）+ 仓位公式

**日期**：2026-04-24
**触发**：F207 Position Manager 需要持久化 account size / risk per trade / exposure caps / regime override。

**决策**：
1. 新表 `user_settings`，`CHECK(id=1)` 约束强制单行（当前为个人单用户；未来多用户场景再改 schema）。
2. 不走 localStorage（localStorage 不同步后端，无法支撑服务端 regime 计算时的风险上限）。
3. **仓位公式**（F207 硬约束）：
   ```
   shares = floor(account_size × min(user_risk_pct, regime_risk_pct, override_pct) / 100
                  / (entry_price - stop_price))
   ```
   三个 risk pct 取**最小值**（安全优先），其中 `regime_risk_pct` 来自 regime 分层默认值，`override_pct` 允许用户在 user_settings 中手动下调。

**放弃**：方案 B：risk 参数每次交易手输。放弃原因：易错、不符合"慢交易系统"的纪律化目标。

**影响**：
- 新表 `user_settings`
- `cockpit/position_sizer.py`（纯函数，不走 LLM）
- F206 Position Manager 新建/编辑 position 时调用 position_sizer 自动计算 shares

---

## D067：positions / pending_orders 的 ticker 字段不设 FK

**日期**：2026-04-24
**触发**：Position / Pending Order 表需要引用 ticker，是否 FK 到 `market_scan_universe.ticker`？

**决策**：`positions.ticker` 和 `pending_orders.ticker` 不设 FK，仅建 index。原因：
1. `market_scan_universe` 的 `active` 状态会变化（月度 refresh 后部分 ticker 退出），但 positions / pending_orders 是**历史不可变**记录，不应随 universe 变动而受限。
2. 用户可能持有不在 scan universe 中的 ticker（OTC / 新上市），FK 会阻止录入。

**放弃**：方案 B：FK 到 `market_scan_universe`。放弃原因：如上。

**影响**：
- `positions` / `pending_orders` 表仅对 `ticker` 建 index（用于按 ticker 查询）
- 前端 ticker 输入时做**软校验**（查不到 scan universe 给 warning 但不阻止提交）

---

## D068：F210 trade_plan 确定性护栏（entry / stop / size post-validate）

**日期**：2026-04-24
**触发**：F210 Ranker/Planner 由 LLM 生成 trade_plan；LLM 可能幻觉出不符合风险约束的 entry / stop / size。

**决策**：
1. LLM 生成 `(entry, stop, target)` 后，后端 `guardrail.py` **必须重算** shares（使用 D066 的公式）并**覆写** LLM 返回的 shares 字段。
2. `/api/cockpit/decision/{ticker}` 响应中增加 `deterministicHash` 字段：`SHA256(ticker + entry + stop + risk_pct + date)`，作为幂等锚点；前端在创建 pending_order 时必须回传该 hash，后端校验一致才入表。
3. 任何 guardrail 失败（entry ≤ stop、reward_risk < 1、stop 超过 ATR×3 等）抛 `AiGuardrailViolation`，不落表不返回计划。

**放弃**：完全信任 LLM。放弃原因：违反"慢交易系统"的安全原则。

**影响**：
- `backend/app/ai/guardrail.py` 为每个 task_type 实现 post-validate hook
- API-CONTRACT.md `POST /api/ai/rank_pool` 和 `/api/cockpit/decision/{ticker}` 响应 schema 增 `deterministicHash`

---

## D069：ai_memos 双用途（audit + dedup cache）+ schema_version 失效

**日期**：2026-04-24
**触发**：AI 调用需要审计（成本 / 错误追踪）+ 去重（同一 ticker + task_type + setup_hash 在短窗口内重复调用会烧钱）。

**决策**：
1. `ai_memos` 表同时承担审计和缓存双角色，不拆两表。
2. 缓存 key：`(task_type, input_hash, schema_version)`，其中 `input_hash = SHA256(normalized_input_json)`。
3. 命中缓存条件：同 key + `created_at > now() - AI_MEMO_CACHE_TTL_HOURS`（默认 24h）+ `schema_version` 相同。
4. `AI_SCHEMA_VERSION` 升级（例如 Pydantic schema 字段变更）时，旧缓存自动失效。
5. 月度预算 `AI_MONTHLY_BUDGET_USD` 由 `budget.py` 累加 `ai_memos.cost_usd`；超额抛 `AiBudgetExceeded`。

**放弃**：拆 `ai_audit` + `ai_cache` 两表。放弃原因：字段 95% 重叠，拆表只是概念洁癖，无实际收益。

**影响**：
- 新表 `ai_memos`（字段：task_type / input_hash / schema_version / response_json / model / tier / cost_usd / latency_ms / error_code / created_at）
- 唯一索引 `(task_type, input_hash, schema_version)` 支持快速去重查询
- `budget.py` 每次调用前 SUM 当月 cost_usd

---

## D070：Cockpit 参数管理用 Pydantic BaseModel 单文件集中

**日期**：2026-04-24（F200-a Sprint Contract 起草同步确定）
**触发**：F201–F204 涉及大量算法阈值 / 权重 / 规则参数（regime 6 子项权重 / 5 档阈值 / ready 7 门 / setup quality A/B/C / earnings risk 天数 / entry/stop 规则 / 2R/3R 倍数 / MA 周期 / RS 窗口 / retention 天数 等），需要在"散落魔法值"与"过度工程化（YAML / DB / UI）"之间取平衡。

**决策**：
1. Cockpit 所有算法参数统一落到 `backend/app/services/cockpit/cockpit_params.py`，用 Pydantic v2 `BaseModel` 组织
2. 每个字段必须带 `Field(description=..., ge=..., le=...)`（description 为业务含义说明，ge/le 为合理范围校验）
3. 文件内按 feature 分 section，命名前缀 `SHARED_* / REGIME_* / SETUP_* / DECISION_* / EARNINGS_*`
4. 参数仍是"Python 常量"性质，改参数 = 改代码重启，**不做**运行时热更新 / .env 覆盖 / DB 读取 / YAML 加载 / admin UI
5. Pydantic 启动时自动校验所有阈值范围，阈值配置错误则进程启动失败（fail fast）

**不进 cockpit_params.py 的参数**：
- cron 时间（`REGIME_CRON_*` / `SETUP_CRON_*` / `EARNINGS_CRON_*`）→ `.env`（部署差异）
- `user_settings` 4 字段（account_size / max_exposure_pct / single_trade_risk_pct / default_risk_per_trade_pct）→ DB 表（用户运行时调）
- AI 模型名 / 预算 / memo TTL / schema_version → `.env`（ARCHITECTURE.md 已定，属部署选项）
- FMP rate limit / API key → `.env` + `fmp_client.py`（跨模块设施）
- 前端默认布局 / debounce 时长 / react-query staleTime → 前端代码

**放弃**：
- 拆文件（`regime_params.py` / `setup_params.py` / `decision_params.py`）— 共享参数（MA_PERIODS / RS_LOOKBACK_DAYS / SECTOR_ETFS）需被多 feature 引用，拆文件多一层 import 无收益
- 运行时可调（DB / UI 可视化）— 单用户项目 YAGNI；Pydantic 结构化已为未来可视化铺路，真有需求时加 1 步"持久化 overrides"即可

**理由**：
- 集中常量 → 调参 / 审计 / 测试断言只改一处，grep 不漏
- Pydantic 结构化 → 启动时自动校验，且字段 description 在用户设计阈值时顺手写最省脑（事后补痛苦）
- 单文件 → 跨 feature 共享常量零冗余
- 先例：`backend/app/services/scanner_params.py`（D045）是同款模式（纯 Python 常量版），D070 是其 Pydantic 升级

**Evaluator 强制检查**（写入每个 F201–F211 Sprint Contract 自检清单）：
- [ ] cockpit service 代码内无魔法数字 / 字符串字面量阈值（grep 确认）
- [ ] 所有阈值通过 `from app.services.cockpit.cockpit_params import X` 引入
- [ ] 新增字段必带 `Field(description=..., ge=..., le=...)`
- [ ] 进程启动时 Pydantic 校验通过（启动 smoke test）

**首次落地**：F201-a Sprint（同时新建 §0 SHARED 部分 + §1 F201 REGIME 部分）。F200-a 纯前端无后端参数，不新建此文件，只立此规矩。

**§4 DECISION 参数（F203-b2 落地，2026-04-25）**：
- `HASH_DIGEST_LENGTH: int = 16` — deterministicHash 取 SHA-256 前 16 位 hex
- `HASH_PRICE_DECIMALS: int = 2` — hash preimage 中 entry/stop 小数位数
- `HASH_RISK_DECIMALS: int = 4` — hash preimage 中 effective_risk_pct 小数位数
- `PRICE_DECIMAL_PLACES: int = 2` — 价格 / 金额输出字段的小数位
- `ACCOUNT_RISK_DECIMAL_PLACES: int = 2` — accountRiskPct 输出小数位
- `OVERRIDE_RECOMPUTE_RR: bool = False` — override 改 entry/stop 后是否重算 rewardRisk；当前 False（保留 setup_snapshots 原值，防副作用扩散）；留作 F210 扩展位
- `REGIME_FALLBACK: str = "NEUTRAL"` — market_regime_snapshots 表空时 fallback regime 标签
- `DEFAULT_ACCOUNT_SIZE: float = 100000.0` — user_settings 行不存在时的默认账户规模（镜像 user_settings_repository._DEFAULTS）
- `DEFAULT_SINGLE_TRADE_RISK_PCT: float = 1.0` — user_settings 行不存在时的默认单笔风险 %（镜像 user_settings_repository._DEFAULTS）

**OVERRIDE_RECOMPUTE_RR 决策理由**：entry/stop override 时保留 setup_snapshots.reward_risk 原值（不重算），避免 override 副作用扩散至下游指标。若业务需要重算（如 F210 AI 校验场景），将此字段改为 True 并在 decision_service 中读取即可，不改接口契约。

**影响**：
- 新文件 `backend/app/services/cockpit/cockpit_params.py`（F201-a 起）
- F201–F211 Sprint Contract 模板追加 D070 合规自检项

---

## D071：AiGateway.run 50 行约束豁免

**日期**：2026-04-25（F208-c Evaluator 阶段，用户明确批准）
**触发**：Contract §5.2 要求单函数 ≤ 50 行，`AiGateway.run` 实际 103 行（含空行和步骤注释），Evaluator 阶段提出。

**决策**：保留 103 行，不拆 `_check_cache` / `_call_and_validate` 私有方法。

**理由**：
1. `run()` 是严格线性的 11 步编排流程（Contract §1.1.1 明确列出）；每步用注释标注，注释即文档
2. 拆成私有方法只是机械地把线性序列折叠为"调用序列 + 两段 body"，增加间接层，可读性下降
3. 实际可执行代码约 45–50 行，103 行里约 50% 是结构化空行和步骤注释
4. 所有功能测试通过，无代码质量缺陷

**约束**：此豁免仅限 `AiGateway.run`（编排层的线性流程）；其他新增函数仍执行 50 行约束。

---

## D072：litellm.completion_cost 必须显式传 model 参数

**日期**：2026-04-25（F208-c Evaluator live smoke 发现）
**触发**：live smoke 测试 `cost_usd > Decimal("0")` 断言失败，`cost_usd` 实际为 0。

**根因**：
- 我们发送 `model='gpt-5.4-nano'`
- OpenAI API 返回的 `response.model = 'gpt-5.4-nano-2026-03-17'`（带日期版本号）
- `litellm.completion_cost(response)` 用 `response.model` 查定价库
- `gpt-5.4-nano-2026-03-17` 不在 LiteLLM 定价库 → 抛异常 → gateway except 兜底 → `Decimal("0")`

**修复**：在 `_call_litellm` 中改为 `litellm.completion_cost(response, model=model)`，用我们发送的短名（`gpt-5.4-nano`）查价，不依赖 OpenAI 返回的版本化名称。

**影响**：`backend/app/ai/gateway.py` L76，1 行改动，mock 测试 + live smoke 全通过。

**教训**：凡调用 `litellm.completion_cost(response)` 的场景，都应显式传 `model=` 参数，防止 provider 返回版本化 model name 导致定价查询失败。

---

## D073：Cockpit Widget 1 颜色 token 映射（MarketRegimeWidget）

**日期**：2026-04-25（F201-c Sprint Contract D1）
**触发**：`tokens.css` 只有 `--color-regime-*` 系列，无独立的 sector/index state token；design-spec §Widget 1 描述了 state 着色需求。

**决策**：sector state / index state 全部复用现有 `--color-regime-*` 系列，不新增 token。映射表如下：

| 维度 | 枚举值 | 复用 token |
|------|--------|-----------|
| Sector state | Strong | `--color-regime-risk-on` |
| Sector state | Constructive | `--color-regime-constructive` |
| Sector state | Neutral | `--color-regime-neutral` |
| Sector state | Weak | `--color-regime-defensive` |
| Sector state | Defensive | `--color-regime-risk-off` |
| Index state | Bullish / Leading | `--color-regime-risk-on` |
| Index state | Constructive | `--color-regime-constructive` |
| Index state | Neutral | `--color-regime-neutral` |
| Index state | Weak | `--color-regime-defensive` |
| Index state | Defensive | `--color-regime-risk-off` |
| Subscore 进度条 | ≥80% / ≥60% / ≥40% / ≥20% / <20% | risk-on / constructive / `--color-log-warn` / regime-defensive / regime-risk-off |

**影响**：`MarketRegimeWidget.tsx`（`indexStateColor` / `sectorStateColor` / `subscoreBarColor` 三个 helper 函数）。


---

## D074：F209-a schema 字段命名 = camelCase

**日期**：2026-04-25（F209-a Sprint Contract §6 D-1）
**触发**：Pydantic schema 字段命名应与 API-CONTRACT 示例字面一致，但 features.json AC 原写"schema 内部 snake_case，router 边界转换"，与实际 router 实现（不做 camel↔snake 转换）冲突。

**决策**：`MarketNarratorInput/Output` 和 `SetupExplainerInput/Output` 所有字段名直接采用 **camelCase**，与 API-CONTRACT.md line 1733-1734 示例完全一致。

**理由**：
1. F208-c `routers/ai.py` 把 `body.input` 原样传给 `pair.input_schema(**input_dict)`，无 camel↔snake 自动转换。
2. 本 sprint 范围"不改 gateway/router 框架"，无法在不动 router 的前提下支持 snake_case schema。
3. LiteLLM `response_format=Pydantic class` 以 Pydantic 字段名生成 JSON schema，schema 字段名即 LLM 输出字段名，camelCase 保持与前端零阻抗。

**放弃了什么**：features.json AC 描述的"schema 内部 snake_case"。该方案需要 router 改造（在 `routers/ai.py` 做 camel↔snake 自动转换），归档为 v2 改进项（可参考 Pydantic v2 `model_config.alias_generator = to_camel` 方案）。

**影响**：`backend/app/ai/schemas/market_narrator.py`、`setup_explainer.py`（新建，字段名全 camelCase）。

---

## D075：F209-b sector state 5→3 归一化在前端做

**日期**：2026-04-25（F209-b Sprint Contract §5 D-3，用户已确认）
**触发**：`CockpitRegimeData.RegimeSector.state` 有 5 个值（`Strong / Constructive / Weak / Defensive / Neutral`），但后端 `MarketNarratorInput.sectors[].state` schema 只接受 3 个值（`Strong / Neutral / Weak`）。若直接传 5 值会被 backend 422 拒绝。

**决策**：归一化逻辑放在 `MarketRegimeWidget.tsx`（私有函数 `normalizeSectorState`），不暴露到 `aiApi.ts`，不修改后端 schema：
- `Strong` / `Constructive` → `Strong`
- `Weak` / `Defensive` → `Weak`
- `Neutral` → `Neutral`

**理由**：
1. 改后端 `MarketNarratorInput` 接受 5 值会破坏 F209-a 的 Pydantic 校验约束，影响 LLM JSON schema 生成。
2. `aiApi.ts` 作为通用 AI 客户端，不应内嵌 market_narrator 专属归一化逻辑；其他 task type（如 F209-c setup_explainer）有不同的输入 schema。
3. 前端归一化函数小且可测（S14.6 有显式 regression 覆盖），改动范围最小。

**放弃了什么**：在后端扩展 schema 接受所有 5 值（改动后端 + 迁移，影响面更大）；或在 `aiApi.ts` 内做通用 5→3 映射（破坏通用性假设）。

**影响**：`frontend/src/cockpit/widgets/MarketRegimeWidget.tsx`（`normalizeSectorState` 私有函数）。测试覆盖在 `MarketRegimeWidget.test.tsx §S14.6`。



---

## D076：F206-c1 nextAction rationale 气泡在 v1.9 不实现

**日期**：2026-04-26（F206-c1 Sprint Contract §2 设计偏离，用户已确认）
**触发**：design-spec §Widget 7 §1057 描述"点击文字弹气泡说明 rationale"，但 `GET /api/cockpit/positions` 返回的 Position 对象不含 `rationale` 字段（仅有 nextAction 枚举：hold / raise_stop / reduce / exit）。

**决策**：v1.9 简化为彩色 chip，不弹气泡：
- hold → "Watch"（`--color-action-watch`，灰）
- raise_stop → "Add"（`--color-action-add`，蓝）
- reduce → "Reduce"（`--color-action-reduce`，橙）
- exit → "Sell"（`--color-action-sell`，红）

**理由**：
1. API 未返回 rationale 字段，前端无数据来源，无法实现气泡内容。
2. F207 `GET /api/cockpit/actions/today` 将聚合完整 rationale（规则引擎 + AI 解释），届时在 ActionListWidget 中提供该交互更自然。
3. 保持 F206-c1 范围聚焦（4 生产文件），不额外拉 F207 依赖。

**放弃了什么**：v1.9 的 rationale 气泡交互（design-spec §1057 原始描述）。该功能归档至 F207 scope。

**影响**：`frontend/src/cockpit/widgets/_positionListRow.tsx`（NextAction chip 实现），`docs/设计/design-spec.md §Widget 7`（偏离注释已写入）。

---

## D060-a：PendingOrder Triggered 后 v1.9 不自动创建 Position

**日期**：2026-04-26（F206-c2 Sprint Contract §7 决策，用户已确认）
**触发**：design-spec §Widget 8 §1172 / component-plan §450 留有"Triggered 后自动创建 Position"的待决策项，F206-c2 Generator 阶段落地。

**决策**：v1.9 中，用户点击 `[Triggered]` 按钮后：
1. 弹 AlertDialog 确认文案："已在券商手动下单？将把订单标记为 TRIGGERED（不会自动创建 Position）"
2. 用户确认 → `PATCH /api/cockpit/pending-orders/{id}` body `{ status: 'TRIGGERED' }`
3. 成功后 invalidate `['cockpit-pending-orders']`，**不** invalidate `['cockpit-positions']`
4. 弹 toast 提示用户："已标记为 TRIGGERED，可在 Positions widget 手工录入实际持仓"

**理由**：
1. 自动创建 Position 需要后端在 `pending_order_service` 内开启事务：PATCH status + INSERT position + 回填 entryDate / entryPrice / shares。失败回滚逻辑复杂，且 PendingOrder 的 entryPrice 是"计划触发价"，不是实际成交价，自动复制会导致数据失真。
2. 手动双录虽然多一步，但给用户机会填入实际成交价格，更符合复盘准确性要求。
3. 前端只改 status，0 后端工作量，F206-c2 范围保持聚焦。

**放弃了什么**：Triggered 后一键自动在 Positions widget 中创建 Position 记录（design-spec §1172 原始描述）。如后续用户反馈手工双录是痛点，可开 F206-d 或归入 F207 ActionList 的统一动作流。

**影响**：`frontend/src/cockpit/widgets/_pendingOrderRow.tsx`（Triggered mutation 实现），`docs/设计/design-spec.md §Widget 8`（待决策 #3 标注已落地）。

---

## D075：F207-a ActionService 设计决策（Q1-Q8）

**日期**：2026-04-27（F207-a Sprint Contract §7，用户已确认）
**触发**：F207-a Generator 实施阶段，8 个技术决策点已在 Sprint Contract 协商阶段与用户逐一确认。

**Q1 — raise_stop 触发条件**：复用 `compute_next_action`（R ≥ 2.0），不引入 swing_low 检测。swing_low 精度延至未来 sprint，届时只需改 `position_action_rules.py`，F207 不需要动。

**Q2 — tighten_stop 触发口径**：regime ∈ {DEFENSIVE, RISK_OFF} 时对所有 OPEN positions 全局发送一条 tighten_stop 动作。一次 `MarketRegimeRepository.get_latest()` 查询，遍历每个 position 各发一条；rationale 引用 regime 值。

**Q3 — cancel_order 触发口径**：ticker 当日最新 `setup_snapshot.setup_type == "BROKEN"`。`SetupSnapshotRepository.get_latest_for_tickers()` 已返回最新一行，直接读 setup_type。

**Q4 — stable_position 归属栏**：`stable_position` → noAction；monitor 只出现 `approaching_trigger`。与 API-CONTRACT 兼容（noAction 行说明成立）。

**Q5 — reduce_before_earnings 阈值**：`days_until_earnings ≤ 2` 个自然日（含 0），与 `position_action_rules.compute_next_action` 当前阈值一致。

**Q6 — Widget 槽位**：ActionListWidget x:0 y:16 w:12 h:6（全宽，Positions+PendingOrders 下方），F207-b sprint 实施。

**Q7 — stop breached + regime DEFENSIVE 同时满足**：优先 raise_stop（个体硬信号 > 全局软信号）。理由：stop breached 是 ticker 个体硬信号，"立即处置"语义更强；tighten_stop 是全局建议，可以等 raise_stop 执行完再统一评估。

**Q8 — pending_order distance > 3% 且 setup 非 BROKEN**：不出现在任何栏（避免噪音）。pending order 距离很远时已在 PendingOrdersWidget 可见，ActionList 只关心"可能要动手的"。

**影响**：`backend/app/services/cockpit/action_service.py`（rule engine 实现），`backend/app/routers/cockpit/actions.py`（endpoint + schema）。

---

## D077：F207-b ActionListWidget 前端设计决策（Q1-Q8）

**日期**：2026-04-27（F207-b Sprint Contract §7，用户已确认）
**触发**：F207-b Generator 实施阶段，8 个前端技术决策点已在 Sprint Contract 协商阶段与用户逐一确认。

**Q1 — 单栏空时是否渲染空标题**：整段不渲染（紧凑）。`_actionListSection.tsx` 头部 `if (items.length === 0) return null`。三栏全空时 widget 容器改用 `data-testid="empty-state"` 显示"暂无今日动作"。

**Q2 — refs 字段前端类型**：弱类型 `Record<string, unknown>`，与后端弱契约一致。hover tooltip 拼 `JSON.stringify(refs)` 供调试用。不做 per-actionType discriminated union，避免后端扩 actionType 时前端编译失败。

**Q3 — AI Daily Brief 区域**：完全不渲染 DOM，仅留代码注释挂载点 `{/* AI Daily Brief 挂载点 — F209/F211 v2.0 */}`。F209/F211 时直接在注释位置插入，无回退成本。

**Q4 — actionType label 中英文**：全英文（"Raise Stop" / "Cancel Order" / "Reduce (Earnings)" / "Tighten Stop" / "Approaching Trigger" / "Stable"）。与现有 widget header（"Pending Orders" / "Setup Monitor"）保持一致；空态文案保持中文。

**Q5 — 行点击触发区**：整行（`onClick` 绑到行 div），与 `SetupMonitorWidget` 一致。光标 `cursor: pointer`。不限定只点 ticker 列。

**Q6 — hover tooltip 实现**：native `title` 属性，与 `SetupMonitorWidget` 一致。不引入 shadcn Tooltip（避免增加文件数；`title` 内容含 rationale + refs JSON 换行拼接）。

**Q7 — 同 ticker 多条 action 前端去重**：不去重，按后端原样 1 行 1 条。与 F207-a §6 "position 和 pending_order 是两个生命周期实体"一致。

**Q8 — empty-state 文案**："暂无今日动作"。与 PendingOrdersWidget "暂无 pending order" 风格一致（中文空态文案）。

**影响**：`frontend/src/cockpit/lib/api/cockpitActionsApi.ts`（类型定义），`frontend/src/cockpit/widgets/_actionListSection.tsx`（行渲染 + label 映射），`frontend/src/cockpit/widgets/ActionListWidget.tsx`（容器 + 4 状态），`frontend/src/cockpit/CockpitRegistry.ts`（manifest 注册）。

---

## D078 — universe 表持久化 screener 快照字段；ADV 不在此层算

**日期**：2026-04-27（F205-a Sprint Contract，用户已确认）

**背景**：F205 Pool Builder 需要 sector / industry / price / volume 数据做 funnel 过滤和 widget 展示。在 API 端点每次实时调用 screener 会造成额外 FMP 请求且延迟高；pool_service 需要在月级 universe 数据基础上做多步 filter，最好在 SELECT 时就能读到这些字段。

**决策**：在 `market_scan_universe` 表新增 4 列（`sector` / `industry` / `last_price` / `last_volume`），在现有月级 universe refresh 时一并从 FMP screener 响应中解析写入。

**关键约束**：

1. **`last_price` / `last_volume` 是快照，不是实时数据**：字段值只在月级 refresh 时更新，不支持实时展示；widget 不得将这两列直接作为"当前价格"展示。
2. **ADV（20 日均美元成交量）不在此层计算**：`last_volume` 是 refresh 当天的单日成交量，不等同于 advMin filter 所需的 20 日均美元成交量。F205-b 的 `advMin` filter 走 trend 子集 EOD 计算，与 `last_volume` 无直接关系。
3. **缺字段降级为 null，不跳过 ticker**：FMP ETF 行常缺 sector/industry，强制要求会导致 universe 行数下降。解析时字段缺失或类型异常 → 存 null，ticker 保留。
4. **字段级降级计数写入 SystemLog**：`universe_refresh_service` 在每次 refresh 的 OK 日志末尾追加 `sector_missing=N` 等计数，供人工或后续监控发现 FMP schema 变化。

**影响**：`backend/alembic/versions/015_f205a_universe_extra_fields.py`（新建），`backend/app/models/market_scan_universe.py`，`backend/app/repositories/market_scan_universe_repository.py`，`backend/app/services/universe_refresh_service.py`。

---

## D079 — pool_helpers：FMP financial-growth 来源、RS mid-rank 算法、fail-open 策略、双实现技术债

**日期**：2026-04-27（F205-b Sprint Contract，用户已确认）

**背景**：F205 Pool Builder 漏斗需要 revenue YoY 增长率（基本面筛选）和 RS percentile（相对强度排序）。setup_service.py 已有内联版 RS 计算，pool 漏斗的 RS 范围是 trend 子集（数百 ticker），需要 population-agnostic 的纯函数版本。

**决策 1：FMP revenue growth 来源**

- 使用 FMP `/stable/financial-growth?period=annual&limit=1` 作为 revenue YoY 来源
- `period=annual` 而非 `quarterly`：pool funnel 做年维度基本面筛选，季报数据波动大；年报稳定性更好
- `limit=1`：只需最近一年数据，减少传输量
- `get_financial_growth` 返回 raw FMP dict（`revenueGrowth` 字段为 decimal，如 0.0202 = 2.02%）；`extract_revenue_growth_yoy_pct` 负责 ×100 转换，两步解耦便于测试

**决策 2：RS 百分位算法 — mid-rank**

- `compute_rs_percentile_map` 使用 mid-rank 公式：`(below + 0.5 × ties) / n × 100`
- `setup_service._percentile_rank` 使用 strictly-below 公式：`below / n × 100`（历史遗留，int 截断）
- 两套公式已知不同。mid-rank 是统计上更正确的选择（ties 获得其占据 rank 的平均值，避免系统性低估）
- F205-b Sprint Contract 的测试用例（#8/9 期望 16.67、50.0、83.33）明确指定 mid-rank 为规范行为
- **dedup 是已知技术债**：不在本 sprint 范围内修改 setup_service.py（避免 F202-a 回归风险）；建议在 F205-c 完成且 pool 漏斗稳定后，开独立技术债 sprint 统一为 mid-rank

**决策 3：fail-open（passes_fundamental_sanity）**

- `growth_yoy_pct=None`（FMP 数据缺失）→ `passes_fundamental_sanity` 返回 `True`
- 理由：FMP ETF / 小市值股的 financial-growth 数据偶有缺失；因 vendor 数据缺失直接淘汰整个 ticker 会产生静默的假阴性，与 pool funnel 的目标（找出有潜力的 ticker）矛盾
- 监控对策：F205-c PoolService 应在漏斗日志中统计 `growth_data_missing=N`，供后续发现 FMP schema 变化

**决策 4：pool_helpers 是纯函数模块**

- 无 IO、无 logger、无 SQLAlchemy、无 httpx；不 import 任何 `app.*` 模块
- 由 F205-c PoolService 负责编排：调 FmpClient、查 DB、组装 population、调用这些纯函数
- 纯净度由 AST 静态检查（`test_pool_helpers_f205b.py` test #17）在 CI 中持续验证

**影响**：`backend/app/external/fmp_client.py`（新增 `get_financial_growth`），`backend/app/services/cockpit/pool_helpers.py`（新建），`backend/tests/test_pool_helpers_f205b.py`（新建），`backend/tests/test_fmp_client.py`（追加用例）。

---

## D080 — PoolService：ADV 单日代理、忽略 trendScoreMin、POOL_TREND_CAP、非 watchlist null setup 字段

**日期**：2026-04-27
**Feature**：F205-c PoolService + GET /api/cockpit/pool

**决策 1：ADV = 单日 dollar volume 代理（技术债）**

- 实现：`tradable` 层过滤条件 = `last_price × last_volume ≥ advMin`（单日代理）
- 真 20d ADV 需要 universe 内每个 ticker 拉 20 天 bars（≥1500 ticker × 20 calls = 大量 FMP 请求），冷启动不可接受
- `last_volume` 已在 F205-a 写入 universe 表；单日量作为粗筛已够用，偏严不偏松
- **技术债**：建议 F205-x 在 `market_scan_universe` 表加 `avg_dollar_volume_20d` 字段，由 `universe_refresh_service` 每日计算

**决策 2：trendScoreMin 参数接受但忽略（技术债）**

- `trend` 层 = tradable ∩ 最新 `market_breakout_scans` 出现；`trendScoreMin` 参数校验范围（0–5）但 service 内部不使用
- 理由：`trend_score(0–5)` 只在 `setup_snapshots` 表针对 watchlist 计算（F202-a 范围）；对 pool 全集实时计算 trend_score 需要给每个 ticker 拉 200d bars + 5 阶 MA ladder，相当于把 setup_service 改造为 population-agnostic，超出本 sprint 范围
- F106 扫描器已过 ma150/slope/volume 阈值筛选，被扫到的 ticker = "趋势良好"；用"在最新 breakout_scans 中出现"作为二元 proxy 工程性价比最高
- **技术债**：真正的 pool-wide trend_score 推到 F205-x 或独立 sprint，需扩 setup_service 或新 service

**决策 3：POOL_TREND_CAP = 200（market_cap 降序截断）**

- trend 子集 > 200 ticker → 按 `universe.market_cap` 降序保留前 200 进入 RS 层
- 理由：FMP token bucket 稳态 5 calls/s；200 ticker × 2 FMP 调用 = 400 calls；6 并发下预估 30–40s（vs 串行 ~80s），勉强在前端 timeout 60s 内。800+ ticker 不截断则单次请求 ~5min，不可接受
- market_cap 降序截断：大盘股优先，符合 P1 用户场景
- `POOL_TREND_CAP` 和 `_FMP_MAX_WORKERS = 6` 作为 `pool_service.py` 顶层常量

**决策 4：非 watchlist ticker 的 setup 字段返回 null（技术债）**

- `setupType / trendScore / distanceToPivotPct` 仅对 watchlist ticker（`stocks.is_active=true`）从 `setup_snapshots` 读取；非 watchlist 全部返回 `null`
- `suggestedAction` 默认 `"watch"`（非 watchlist）
- `inWatchlist = ticker ∈ active_stocks`，前端据此控制"+ Add to Watchlist"按钮状态
- **技术债**：扩展到 pool 全集需要 setup_service 改造，推到 F205-d 之后的独立 sprint

**FMP 并发模型（补充说明）**

- RS 层和 fundamental 层均使用 `ThreadPoolExecutor(max_workers=6)` 并发调用 FMP
- 限流由 `fmp_client._FmpRateLimiter` 进程级 singleton（token bucket 300 rpm + Semaphore(6)）统一兜底；service 层不重复实现
- `max_workers=6` 接受"pool 请求期间挤占其他 FMP 消费者"的取舍（pool 是用户主动触发的高优先级查询）
- SPY closes 在 RS 层串行获取（主线程单次调用），之后所有 trend ticker bars 并发拉取

**影响**：`backend/app/services/cockpit/pool_service.py`（新建），`backend/app/routers/cockpit/pool.py`（新建），`backend/app/routers/cockpit/__init__.py`（注册），`backend/app/schemas/cockpit/pool.py`（新建），`backend/tests/test_pool_service.py`（新建），`backend/tests/test_cockpit_pool_router.py`（新建）。

---

## D081：Pool 漏斗 RS + Fundamental 层改为周级缓存（F205-e）

**背景**：F205-d 验收发现每次 filter 改动触发全量 FMP 调用（~30s），体验不可接受。

**决策**：RS percentile（FMP get_daily_bars）和 fundamental revenue growth（FMP get_financial_growth）两层改为预计算，结果存入 `cockpit_pool_cache` 表，每周一 06:30 UTC 重建（APScheduler cron）。PoolService 不再调用 FMP，直接读 DB。

**关键参数确认（F205-e 用户确认）**：

| # | 问题 | 选择 |
|---|------|------|
| Q1 | Cache 范围 | A：仅 trend-passing tickers（~50 个）|
| Q2 | Cron 时机 | A：每周一 06:30 UTC |
| Q3 | Cache miss 行为 | A：返回空 funnel + WARN 日志 |
| Q4 | 缓存 ma50/last_close | A：是 |
| Q5 | 手动触发 | B：`POST /api/admin/refresh-pool-cache` |

**权衡**：
- Q1=A（trend-only）vs Q1=B（全 universe）：trend tickers 仅 ~50 个，FMP 调用量从 1200 calls/周 → ~100 calls/周。代价是 cache 里的 percentile 相对 trend 总体计算，非全 universe 排名。
- Cache miss（Q3=A）：首次部署或 rebuild 失败后 pool 返回空结果，需手动触发 rebuild。
- Cron Mon 06:30 UTC：避开 setup_cron (22:30)、earnings_cron (05:30)、universe_cron（月初 05:00）。

**预期效果**：GET /api/cockpit/pool filter 改动响应时间 30s → < 500ms。

**影响文件**：`alembic/versions/016_f205e_pool_cache.py`（新建），`app/models/cockpit_pool_cache.py`（新建），`app/services/cockpit/pool_cache_service.py`（新建），`app/services/cockpit/pool_service.py`（修改，删除 FMP 调用），`app/services/refresh_job.py`（新增 cron），`app/routers/admin.py`（新建，Q5=B），`tests/test_pool_service.py`（重写 fixture + 新增 PoolCacheService 测试组）。

---

## D075：F211-a2 per-task model override（D064 增量）

**日期**：2026-04-28
**触发**：F211 三 task 实际调用中，`news_summarizer`（长上下文）/ `journal_assistant` monthly（推理密集）/ `candidate_ranker`（高频）希望脱离三 tier 单端点，按 task 切到不同 provider/cost。

**决策**：
1. 新 .env 字段 `AI_TASK_OVERRIDES_JSON`，单 JSON dict，key = task_type，value = `{model, base_url?, api_key?, input_cost_per_1m?, output_cost_per_1m?}`。
2. `routing.resolve()` 签名升级为返回 `ResolvedRoute` frozen dataclass（tier/model/base_url/api_key/custom_input_cost/custom_output_cost）；override 命中（model 非空）→ 全字段透传；否则走 D064 三 tier 兜底。`resolve_tier()` / `resolve_model()` 旧 API 保留，零回归。
3. `gateway._call_litellm` 新签名 `(route: ResolvedRoute, input_dict, output_schema)`：透传 `api_base=route.base_url` 给 litellm；若 override 含自定义 cost，直接传 `input_cost_per_token` / `output_cost_per_token` 给 `litellm.completion()`，`completion_cost(completion_response=response)` 自动使用这些值（官方 SDK Custom Pricing 路径，context7 验证）。**不使用 `register_model` 全局 dict**（避免线程锁 + 全局状态）。
4. JSON 解析失败、非 dict、register 失败：**log warning，整体 fallback 到 tier 默认**，不抛异常 — fail-soft 优先于 fail-fast，保证现有 .env 用户零感知。

**放弃**：
- 方案 B：每 task 独立 6 个 .env 变量（`AI_NEWS_MODEL` / `AI_NEWS_BASE_URL` …）。放弃：7 task × 5 字段 = 35 变量，污染 .env，增 task 要改 Settings 类。
- 方案 C：admin endpoint + UI 切 model。放弃：个人投资工具定位，重启改 .env 已足够；增 endpoint 引入鉴权/审计成本。
- 方案 D：override 写进 `cockpit_params.py`。放弃：违反 D070 line 1527（AI 模型走 .env 不进 cockpit_params.py）。
- 方案 E：`register_model` 全局注入 cost 后 `completion_cost(response)` 读取。放弃（context7 验证时发现更优路径）：直接传 `input/output_cost_per_token` 给 `completion()` 是官方文档的 SDK Custom Pricing 推荐路径，response 内携带 cost 参数，无需全局状态/锁，且语义更清晰。

**影响**：
- `backend/app/config.py`：增 `ai_task_overrides_json: str = ""`
- `backend/app/ai/routing.py`：新 `ResolvedRoute` dataclass + `_parse_overrides` + `resolve()` 新签名
- `backend/app/ai/gateway.py`：`_call_litellm` 新签名透传 `api_base`；直接 cost params 传 litellm
- `.env.example`：追加 AI Gateway 完整注释段 + `AI_TASK_OVERRIDES_JSON` 示例
- D064 段落不需要重写，本 D075 作为增量决策

**未来扩展点**：
- 若需要 LiteLLM Router 多模型 fallback，扩展 `ResolvedRoute` 加 `fallbacks: list[str]`，gateway 改用 `litellm.Router.completion`。本 sprint 不做。
- 若需要 `extra_headers` / `timeout` / `max_retries`，a3 sprint 扩展 `ResolvedRoute` 字段。

## D082：F211-d1 close hook 异步策略 + ai_review 列形态
日期：2026-04-29 | Feature: F211-d1

**方案**：
1. PATCH /api/cockpit/positions/{id} OPEN→CLOSED 触发 FastAPI `BackgroundTasks`，不阻塞响应
2. BackgroundTask 内开新 SQLAlchemy session（不复用请求 session）
3. journal_entries 加 ai_review (Text/JSON 字符串) + ai_review_memo_id (Integer, no DB FK)
4. 平仓自动 INSERT/复用 SELL journal_entry（同 ticker+date 的 SELL 复用，避免重复打 LLM）
5. 任何 AI 错误（Provider / Schema / Guardrail / Budget）→ ai_review 留 null，positions 已 CLOSED 不回滚

**理由**：
- 异步：journal_assistant complex tier ~5–15s，不能阻塞 PATCH 响应
- Text 列：与 ai_memos.input_json/output_json 一致，避开 SQLite JSON 类型移植性问题
- 无 FK：D069 ai_memos 180 天滚动清理，FK 会阻塞清理；ai_review_memo_id 接受 dangling
- 复用 SELL entry：避免同一交易多次平仓尝试时重复打 LLM 烧 budget

**对应代码**：`position_service._trade_review_background`, `journal_review_service.JournalReviewService.trade_review_for_position`

**注**：Sprint Contract 原规划 D076，因 D076 已被占用改为 D082。

---

## D083：F211-d2 月度复盘 cron 策略
日期：2026-04-29 | Feature: F211-d2

**方案**：
1. 月度复盘输出**仅落 ai_memos**（不写 journal_entries，不新增表/迁移/action 类型）
2. cron 时间：每月 1 号 06:00 UTC（universe 05:00 之后 1h 错峰）
3. 0 trades 月份：主动跳过 gateway（MonthlyReviewPayload min_length=1，空列表会 schema 报错），log INFO，return None
4. 重入幂等：依赖 AiGateway memo dedup（input_hash + 24h TTL + schema_version=v1），不加标记位
5. 失败不重试：tick 顶层 try/except swallow，与 refresh_job 现有 7 个 cron tick 一致，下月自然再来
6. closedTrades 上限 100 条，ORDER BY closed_at ASC（最早 100 条，早期更有归因价值）

**理由**：
- 仅落 ai_memos：避免新增 action 类型 / schema 迁移，依赖 D069 180 天滚动清理保证存储不膨胀
- 月初 06:00 UTC：universe refresh 05:00 在前，避免并发争锁；早于 scanner 06:15，月初 API 正常
- 跳过 0 trades：主动检测比依赖 schema 报错更清晰，避免 warning log 的噪声
- 不重试：月度复盘错过则下月补，低频触发（1 次/月）不值得引入 tenacity / APScheduler reschedule 复杂性

**放弃了什么**：
- 新表 monthly_reviews（+迁移 +表 +FK，超 sprint 范围）
- journal_entries 新增 action='MONTHLY_REVIEW'（+迁移 +schema 变更）
- Redis lock 幂等（无 Redis 依赖，系统单用户，重入概率极低）
- 重试机制（月度频率不值得 tenacity 复杂度）

**对应代码**：`journal_review_service.JournalReviewService.monthly_review_for_month`, `refresh_job._journal_monthly_tick`, `refresh_job._previous_month_utc`

**注**：Sprint Contract 原规划 D077，因 D077 已被占用（F207-b）改为 D083。

---

## D084：F213-a DeepSeek 通过 per-task override 接入，不进 settings 字段

**日期**：2026-05-07
**Feature**：F213-a News Article Auto-Translate 后端 schema

**背景**：F213 News 翻译任务选用 DeepSeek（deepseek-v4-flash 或 OpenAI 兼容路径），其 base_url / api_key 与主力 OpenAI 端点不同。D075 (F211-a2) 已建立 `AI_TASK_OVERRIDES_JSON` 机制可按 task_type 注入自定义 model/base_url/api_key/cost，无需改 Settings 类。

**决策**：

1. **不在 `app/config.py` 增加 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL` 等独立字段**。
   - 理由：D075 `AI_TASK_OVERRIDES_JSON` 已可覆盖 model + base_url + api_key + cost，增加独立字段是冗余且会污染 Settings 命名空间；每加一个 provider 就加若干字段，不可扩展。

2. **`translate_article` 在 `_TASK_TIER` 注册为 `"default"` tier**（gateway 正常走 tier 逻辑兜底），部署时在 `.env` 写 `AI_TASK_OVERRIDES_JSON` 覆盖 model/base_url/api_key；如果未配置 override，fallback 到 `settings.ai_model_default`（OpenAI），功能仍可用但翻译质量可能下降。

3. **DeepSeek 接入路径（部署时选其一）**：
   - 原生路径：`"model": "deepseek/deepseek-v4-flash"`（LiteLLM 原生 provider，需 LiteLLM ≥ 1.x 且已注册 deepseek provider）
   - OpenAI 兼容路径（推荐，可靠性更高）：`"model": "openai/deepseek-v4-flash", "base_url": "https://api.deepseek.com", "api_key": "sk-..."`
   - 两条路径在 `routing.resolve()` 中均通过 `base_url` 透传 LiteLLM，代码无需分支。

4. **不注册 guardrail**：翻译输出为中文文本，现有 BANNED_PHRASES 体系专为英文 LLM 金融建议设计；为纯翻译结果添加 guardrail 会造成误伤（如"忽略止损"可能出现在新闻正文的翻译中）。

**放弃**：
- 方案 A：新增 `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` settings 字段。放弃：D075 已有更通用机制，重复引入强约定。
- 方案 B：guardrail 检测翻译输出。放弃：翻译任务是原文的结构化映射，BANNED_PHRASES 命中率高但精度极低，误伤概率大于防护价值。

**参考**：D064（tier 路由）/ D069（ai_memos 去重）/ D075（per-task override 机制）

---

## D085：F215-a RISK_ON 单笔风险上限从 1.5% 调整为 1.25%

**日期**：2026-05-12
**Feature**：F215-a Risk cap + EMA 10/21

**背景**：SRS 框架第十节明确规定单笔风险上限 ≤ 1.25%。原 `cockpit_params.py` 中 `RISK_ON` 档位为 1.5%，系统性超出设计边界，会在最积极的市场状态下使用过大仓位。

**决策**：将 `REGIME.SINGLE_TRADE_RISK_PCT["RISK_ON"]` 从 `1.5` 改为 `1.25`。其余四档（CONSTRUCTIVE 1.0% / NEUTRAL 0.75% / DEFENSIVE 0.5% / RISK_OFF 0%）保持不变。

**影响**：下次 `MarketRegimeService.compute_and_store()` 运行后，新快照的 `single_trade_risk_pct` 将自动写入 1.25，无需 DB migration。

**放弃**：保持 1.5%（不符合 SRS 约束，且在 RISK_ON 状态下会系统性高估仓位大小）。

---

## D086：F215-a cockpit chart 新增 EMA 10/21 序列，与 SMA 共存

**日期**：2026-05-12
**Feature**：F215-a Risk cap + EMA 10/21

**背景**：SRS 框架中 EMA10/EMA21 用于"退出规则 trailing stop"（价格跌破 EMA21 出场），SMA 用于"趋势分类"（Stage 分析）。两者职责不同，需要在 chart 上同时可见。

**决策**：
1. `chart_service.py` 新增 `_compute_ema_series(bars, period)` 纯函数，α=2/(period+1)，seed=SMA(period)，与 `_compute_ma_series` 同层。
2. `get_chart()` 在 `mas` 同级返回 `emas` dict，周期固定由 `CHART.DEFAULT_EMAS=[10,21]` 控制，不开放查询参数。
3. 前端 `CockpitChartWidget` 用 `LineStyle.Dashed` 渲染 EMA，复用 MA 颜色 token，零新 CSS 变量。

**放弃**：
- 合并 EMA/SMA 为统一参数（两者语义不同，混用会降低可读性）
- 开放 `?emas=` 查询参数（当前无动态需求，固定周期足够，避免接口过度泛化）

**影响**：`backend/app/ai/schemas/translate_article.py`（新建）/ `backend/app/ai/schemas/__init__.py`（+1 import + REGISTRY 行）/ `backend/app/ai/routing.py`（+1 _TASK_TIER 行）

---

## D087：F215-b Volume Accumulation 三件套定义

**日期**：2026-05-13
**Feature**：F215-b Volume Accumulation 三件套

**决策**：在 `setup_service.py` 新增 3 个纯函数，计算方式如下：

| 字段 | 函数 | 逻辑 |
|------|------|-------|
| `volume_zscore` | `_compute_volume_zscore` | (last_vol − mean50) / std50；std==0 或 bars<51 → None |
| `obv_trend` | `_compute_obv_trend` | obv[-1] vs obv[-21]，相对变化 > ±2% → UP/DOWN，否则 FLAT；obv_base==0 或 bars<21 → None |
| `up_down_volume_ratio` | `_compute_up_down_volume_ratio` | 50 窗口内上涨日成交量之和 / 下跌日成交量之和；无下跌日 → None |

所有参数集中在 `cockpit_params.py` 的 `VOL_ACC_*` 常量组（window/lookback/flat_pct/breakout 阈值）。

**放弃**：
- 使用 talib 或 pandas（避免引入重依赖；纯 Python 实现可测且足够）
- 向 API 暴露可配置参数（固定参数对当前需求足够，避免接口复杂化）

**影响**：`setup_snapshots` 表新增 3 列（alembic 018），`SetupItemResponse` schema 新增 3 字段，前端 `SetupMonitorWidget` 新增 Vol Z 列。

---

## D088：F215-b BREAKOUT 吸筹门槛升级

**日期**：2026-05-13
**Feature**：F215-b Volume Accumulation 三件套

**背景**：BREAKOUT 形态中区分"真突破"（高成交量 + 买方主导）和"假突破"（低量、双向成交）。不加量能门槛会让无吸筹的价格突破触发 BREAKOUT 信号。

**决策**：在 `_classify_setup_type` 的 BREAKOUT 分支新增量能门槛（D088）：
- `vol_zscore ≥ 1.5`（突破日成交量显著高于 50 日均量）
- `up_down_volume_ratio ≥ 1.2`（50 日窗口内买方成交量占主导）
- 任一不满足（包括 None 短历史）→ 直接降级为 NONE，**不 fall-through 到 PULLBACK/RECLAIM**

两个阈值在 `cockpit_params.py` 以 `VOL_ACC_BREAKOUT_Z_MIN=1.5` / `VOL_ACC_BREAKOUT_UD_MIN=1.2` 集中管理。

**放弃**：
- 降级为 PULLBACK（语义不匹配，量能不足的 BREAKOUT 应被完全排除而非重新分类）
- 使用单一指标（量能 z-score 和 U/D ratio 互补，z-score 检测突破日，U/D 检测蓄势期）

**影响**：`_classify_setup_type` 签名新增 `vol_zscore` / `ud_ratio` 两个可选参数，调用方 `compute_and_store_all` 传入。

---

## D089：F215-b 历史快照不回填量能字段

**日期**：2026-05-13
**Feature**：F215-b Volume Accumulation 三件套

**决策**：alembic 018 升级后，存量 `setup_snapshots` 行的 3 个量能字段保持 NULL，不执行回填。下次 `compute_and_store_all()` 运行时自动写入新快照。

**放弃**：回填存量数据（增加迁移复杂度 + 历史快照本身仅用于展示历史状态，非实时决策依据）。

**影响**：无额外 migration 脚本，迁移后首次扫描即生效。

---

## D090：F216-a Weekly 聚合采用 ISO 周分组，week date 跟随实际最后交易日

**日期**：2026-05-14
**Feature**：F216-a Weekly Aggregation Service

**背景**：周线 bar 的 `date` 字段需要一个命名约定。计划草稿写的是"week_end_date=周五"，但美股节假日（如感恩节周四休市后周五提前收盘）会导致当周最后实际交易日不是周五。

**决策**：`aggregate_daily_to_weekly` 以 `bar.date.isocalendar()[:2]`（ISO year, ISO week）为分组键，每个 weekly bar 的 `date` 取**该 ISO 周内最后一个实际交易日的日期**，不强制对齐到周五。

分组键选 ISO week 而非自然周（周日起），是因为 ISO week 与交易所日历对齐（周一开盘），跨年周（如 2025-12-29~2026-01-04）也能正确归属 iso_year=2025 W53 or 2026 W01。

**放弃**：强制 `week_end_date = 本周周五`（计划原始方案）。理由：
- 短周（周五休市）时周五无实际成交，bar.date=周五 会与 lightweight-charts 周线显示约定错位
- 强制映射需要额外的"上一个/下一个有效交易日"逻辑，引入复杂度

**影响**：`WeeklyBarDict.date` 语义锁定为"本周末日实际交易日"。F216-b stage 分类器、F216-c 前端 widget 均以此字段渲染 x 轴。本决策写入 Sprint Contract NP2。

---

## D091：F216-b Weekly Stage 量化判定细则（Stan Weinstein Stage 1-4）

**日期**：2026-05-14
**Feature**：F216-b Weekly Stage Classifier + 持久化

**背景**：Stan Weinstein Stage Analysis 是定性框架，需要将"走平"、"上行"、"分配"、"下跌"四阶段量化为可计算的指标与阈值，以支持自动分类。

**决策（NP1 全部采用推荐默认值，已用户 2026-05-14 确认）**：

| 参数 | 值 | 含义 |
|------|-----|------|
| `MIN_WEEKS_FOR_CLASSIFICATION` | 30 | < 30 周无 30wMA，直接返回 UNKNOWN |
| `SLOPE_LOOKBACK_WEEKS` | 5 | OLS 用最后 N+1=6 个 30wMA 点 |
| `STAGE1_FLAT_TOL_PCT` | 2.0 | |slope_30w| ≤ 2% → "走平" |
| `STAGE1_PRICE_BAND_PCT` | 3.0 | |close - ma30|/ma30 ≤ 3% → 价格在 30wMA 附近 |
| `STAGE2_SLOPE_MIN_PCT` | 0.5 | slope_30w > 0.5% → 30wMA 有效上行 |
| `STAGE3_FLAT_TOL_PCT` | 2.0 | 同 Stage 1（Stage 3 靠"穿越次数"区分） |
| `STAGE3_CROSSING_LOOKBACK_WEEKS` | 10 | 统计过去 10 周穿越次数 |
| `STAGE3_MIN_CROSSINGS` | 3 | ≥ 3 次穿越 = "反复震荡" |
| `STAGE4_SLOPE_MIN_PCT` | 0.5 | slope_30w < -0.5% → 30wMA 有效下行 |

**分类优先级**（避免 Stage 1 / Stage 3 互判）：Stage 2 → Stage 4 → Stage 1 → Stage 3 → UNKNOWN。明显趋势（2/4）优先于震荡（1/3）；Stage 1 在 Stage 3 之前（Stage 1 是更严格的"价格带内"条件，Stage 3 需额外满足"多次穿越"）。

**slope_30w 单位**：`%/周`（`beta / mean(y) * 100`）。`STAGE2_SLOPE_MIN_PCT=0.5` 含义：30wMA 每周上升 ≥ 0.5%，折合年化约 +25%，符合 Weinstein 对 Stage 2 "明显上行" 的定性描述。

**UNKNOWN 保留策略（NP7）**：数据不足（< 30 周）、ma30=None、或不满足任一 Stage 规则时，写入 `stage=0`（UNKNOWN）。F216-d 的 setup_service 以 `stage == 0` 判定 `ready_signal=false`，无歧义。

**参数回顾承诺**：上述参数为初始值，在 F216 全 phase（a-e）验收后、实盘运行 4-8 周后，基于实际 stage 分布（UNKNOWN 占比 / Stage 2 召回率）回顾调参。调参不需改代码，只更新 `CockpitWeeklyStageParams` 字段 `default` 值。

**放弃**：
- 动态阈值（基于历史分布自适应）— 增加不可解释性，与 Weinstein 原书精神矛盾
- 连续型 Stage 得分（0-1 区间）— 前端映射复杂，F216-d gate 逻辑更难写
- Stage 3 用"价格超出 30wMA 一定百分比"替代"穿越计数" — 穿越计数更直接对应 Weinstein 对 Stage 3 "股价在 30wMA 附近反复穿插"的描述

---

## D092：F216-b 引入 numpy — 范围、版本约束与使用边界

**日期**：2026-05-14
**Feature**：F216-b Weekly Stage Classifier + 持久化

**背景**：`slope_30w` 用 OLS 线性回归计算。可选方案：端点法（1 行，无依赖）、纯 Python OLS（8 行）、`numpy.polyfit`（1 行，~25MB 依赖）。用户 2026-05-14 选 B-2（引入 numpy）。

**决策**：

```toml
# backend/pyproject.toml
"numpy>=2.0,<3"  # 解析到 v2.4.4（uv lock 2026-05-14）
```

- context7 查询确认（v2.3.1 文档）：`np.polyfit(x, y, deg=1)` 返回 `[beta, intercept]`，API 在 2.x 与 1.x 行为一致，无 breaking changes
- 使用形式：`beta, _intercept = np.polyfit(x, y, 1)`；`slope_30w = beta / y.mean() * 100`
- 启动成本：`import numpy as np` 一次性 ~50ms，可忽略

**numpy 使用边界（强制）**：
- 允许：`backend/app/services/cockpit/` 数值计算层（slope/std/regression 等）
- 禁止：router 层、repository 层、models 层
- 验证方式：`grep -r "import numpy\|from numpy" backend/app` 应只有 1 个命中（`weekly_stage_service.py`）

**为什么选 B-2（numpy）而非纯 Python OLS**：
1. 单行表达（`np.polyfit(x, y, 1)[0]`），可读性高
2. 为 Phase C（ATR z-score 当前手写）/ Phase D（repricing 数值计算）预埋基础设施，避免未来多次引入依赖的 review 成本
3. 缩短 `SLOPE_LOOKBACK_WEEKS` 后（如 3 周），OLS 相对端点法的抗噪优势显著
4. numpy 2.x 已成 Python 生态事实标准，依赖风险极低

---

## D093：F216-d2 weekly_stage 作为 ready_signal 第 8 条 AND 门

**日期**：2026-05-14
**Feature**：F216 Cockpit Phase B — Weekly Stage Layer（sub-sprint d2）

**决策**：在 `_compute_ready_signal` 原 7 条 AND 门基础上加 `weekly_stage == 2` 第 8 条；NULL/0/1/3/4 一律视为不满足；门禁由 `SETUP.READY_REQUIRE_STAGE2` (default=True) 控制。

**原因**：Stan Weinstein Stage 框架认为 Stage 2 (Advancing) 是唯一具备系统性正期望的阶段；Stage 3 顶部分布 + Stage 4 下跌中触发的 BREAKOUT/RECLAIM 胜率历史显著偏低。把 stage 接进 ready_signal 让 setup_monitor 自动屏蔽这两段，用户只看 Stage 2 的有效信号。

**放弃了什么**：
- 把 stage 一并降级 setup_type=NONE：会抹掉 watch/wait 中间态，用户失去"setup 存在但暂不可 enter"的视野（NP-G 否决）
- 增加 suggested_action='stage_gate' 中间态：前端 enum/排序/map 全要同步改，冲击超 d2 scope（NP-H 否决）
- NULL/0 → 跳过门禁的宽松路径：与 ready_signal 7 条 AND 门"NULL 即不满足"的语义不一致，且违背 acceptance criteria 第 8 条（NP-C 否决）

**影响**：
- ready_signal=True 标的预期减少 30-50%（设计意图，文档化）
- 冷启动当天 weekly_stage cron 未跑前所有 ticker 的 ready=False（与 F215-b volume_zscore 短历史 pattern 一致）
- 前端 SetupMonitorWidget 后续 d3 加 WS 列展示 stage（让用户看到"为何 ready=false"）

**回滚方式**：env 或代码层把 `SETUP.READY_REQUIRE_STAGE2` 置 False，无 schema / migration 回滚需求

**放弃**：
- 端点法 `(ma[-1] / ma[-(N+1)] - 1) * 100` — 只用 2 个点，单周异常值影响大
- 纯 Python OLS — 功能等价但无法复用，Phase C/D 需另行引入 numpy

---

## D094：F216-e weekly_stage cron 时段选址与 ordering 策略

**日期**：2026-05-15
**Feature**：F216 Cockpit Phase B — Weekly Stage Scheduler Cron（sub-sprint e）

**决策 1：cron 时段 22:20 UTC**

选定 `weekly_stage_cron_hour=22 / minute=20`（工作日 mon-fri），即 regime ETF refresh（22:15）之后 5 分钟、setup snapshot scan（22:30）之前 10 分钟。

理由：
- features.json acceptance_criteria L10 明文约定"22:20 UTC, mon-fri"
- weekly_stage 的 `compute_and_store_all` 是纯本地 DB 查询 + numpy OLS，active_stocks ~25 标的实测 <10s，10 分钟缓冲提供 60x 安全余量
- setup 在 22:30 起跑时能读到当天最新 weekly_stage_snapshots；即使本日 weekly_stage 超时，`get_latest_for_tickers` 不限 scan_date，setup 读上一个工作日的 stage 值，返回 NULL→ready=False（D093 语义兜底）
- 备选 22:25（regime+10min）与 acceptance criteria 文字不一致；21:35 过早（daily_bars 21:30 refresh 仍在进行，weekly_chart 依赖 daily_bars）

**决策 2：ordering 策略 — wall-clock 时间间隔，不引入同步链**

选择通过 cron 时间错峰（22:15 / 22:20 / 22:30）达成 regime → weekly_stage → setup 的执行顺序，不引入任何同步依赖或事件链。

理由：
- 与既有 refresh→regime→setup 链条策略完全一致（21:30 / 22:15 / 22:30），新增 cron 仅插入现有时间轴的空隙，无需修改调度框架
- APScheduler 3.x 无原生 job dependency API；引入 prefect/dagster 等编排器违反 sprint B5 排除范围，且大幅增加运维复杂度
- 若 weekly_stage 异常拖延至 22:25+，setup 22:30 读昨日 stage 值，返回 ready=False（D093 保守语义），数据短暂陈旧但系统不崩溃

放弃了：
- 在 `_weekly_stage_tick` 结尾同步调用 `SetupService.compute_and_store_all()`：强耦合、单一职责破坏、setup_cron 配置失效
- BlockingScheduler 强制串行：需重写整个 scheduler 模式，超出 sprint scope

---

## D095：F217 Phase C — Capitulation 替换 PULLBACK + 分类器优先级升级

**日期**：2026-05-15
**Feature**：F217 Cockpit Phase C — Capitulation Reversal 严格重写

### 决策 1：从 `SetupSnapshot.setup_type` 枚举完全移除 `PULLBACK`，引入 `CAPITULATION`

**当前实现的问题**（语义错位证据）：

- 旧 `SETUP_PULLBACK` 判定逻辑（v2.2 前 `setup_service._is_pullback`）：`MA150 < close < MA50` 且 `close ≈ MA21`（回踩短均线）
- SRS § 五 Setup 4 "Capitulation Reversal" 语义：**投降式抛售反转** — 连续下跌中出现极端放量 + 大 range + 收盘脱离最低 + 次日不创新低 + higher low + RS 止跌
- 两者描述的**不是同一现象**：PULLBACK 是上升趋势中的低风险 entry，CAPITULATION 是下跌末端的反转 entry，对应的胜率分布、止损位置、目标空间、持仓节奏完全不同
- 把它们共用一个 `setup_type` 字段，会导致 AI ranker / journal / 持仓后复盘统计的语义被污染（一个标的两个语义混淆），且 DecisionPanel 无法展示 CAPITULATION 特有的 evidence chips

### 决策 2：7 条 AND 门严格判定（取阈值的依据）

`setup_service._is_capitulation_reversal(bars, rs_line)` 要求同时满足：

| # | 条件 | 阈值 | 依据 |
|---|------|------|------|
| 1 | 连续下跌 | 过去 5–10 日 close 累计跌幅 ≥ **10%** | SRS § 五 Setup 4 直接引用；和 EXTENDED（过度延伸）门槛 ±5–7% 拉开档次 |
| 2 | 极端放量 | Vol z-score ≥ **2.5** | 复用 F215-b `_compute_volume_zscore`（50 日窗）；2.5 σ 对应 ~99 百分位单日放量，区别于 BREAKOUT 的 1.5 σ 吸筹门槛（D088） |
| 3 | 大 range | `true_range ≥ 2 × ATR14` | 复用 chart_service.py:43-73 `_compute_atr`；2× ATR 反映极端波动日 |
| 4 | 收盘脱底 | `close` 位于当日 high-low 区间的 **上 1/3** | SRS"收盘脱离最低"白话翻译；阈值 1/3 是常见技术分析 reversal day 边界 |
| 5 | 次日不创新低 | 当日之后 1–2 日 `low > 当日 low` | 投降日 + 后续不破底确认；尾部数据不足时允许 None 跳过此条（不视为失败） |
| 6 | higher low | 当前 low > 过去 30 日内倒数第二个 swing low | 新增辅助函数 `_detect_swing_lows(bars, lookback=30)` 找局部低点；higher low 是结构反转的最小证据 |
| 7 | RS 止跌 | RS line 在过去 5 日**未创新低** | 复用 `_compute_rs_line` 或 setup_service.py:286-329 RS 计算；CAPITULATION 不要求 RS 转强，只要求停止恶化 |

### 决策 3：`_classify_setup_type` 优先级 — CAPITULATION 高于 BREAKOUT/RECLAIM

新优先级：`BROKEN → EXTENDED → EARNINGS_DRIFT → CAPITULATION → BREAKOUT → RECLAIM → NONE`

**理由**：CAPITULATION 的核心前提是"连续下跌 ≥ 10%"，与 BREAKOUT（已突破 pivot）和 RECLAIM（重夺 50MA）的"价格在 MA 之上"状态互斥；若同一日同标的同时被两个分支命中（理论上罕见，但浮点边界可能发生），应优先识别为 CAPITULATION，因为它的语义更具底部反转的特殊性，hard-coded 顺序避免歧义。

### 决策 4：历史 `setup_snapshots.setup_type=PULLBACK` 行**软删而非硬删**

F217-b alembic 021 不 `DELETE FROM setup_snapshots WHERE setup_type='PULLBACK'`。

**两种软删方案二选一**（在 F217-b Sprint Contract 拍板）：

- 方案 A（推荐）：新增 `legacy: Boolean default=false`列，把历史 PULLBACK 行 `UPDATE SET legacy=true`，setup_service 查询时 `WHERE legacy=false`
- 方案 B：保留 `purge_legacy_pullback()` repository 方法，定时归档到 `setup_snapshots_archive` 表

**理由**：历史快照是回测 / 复盘 / Journal 关联 的数据来源，删除会破坏可追溯性；同时枚举 CHECK 约束（如 SQLite TEXT/PostgreSQL ENUM）会因历史值不合法而 migration 失败 — 软删通过保留行 + flag 字段绕开。

### 决策 5：API 兼容 — `capitulationEvidence` 字段**可选**而非必填

`GET /api/cockpit/decision/{ticker}` 响应在所有 setupType 下都返回 `capitulationEvidence` 字段，但**仅当 `setupType=CAPITULATION` 时为非 null 对象**（含 `volZscore`/`drop5dPct`/`reversalDay`），其它 setupType 一律 `null`。

**理由**：保持响应 schema 稳定（前端 TS 类型可写成 `capitulationEvidence: {...} | null`，不需要做 optional key 处理），同时避免在 BREAKOUT/RECLAIM 等正向 setup 上误展示 chips。

### 决策 6：`user_settings.preferred_setups` 默认值 `["BREAKOUT", "PULLBACK"]` → `["BREAKOUT", "CAPITULATION"]`

F217-b alembic 021 还需 `UPDATE user_settings SET preferred_setups = ...` 把现有行 JSON 数组中的 `"PULLBACK"` 字符串替换为 `"CAPITULATION"`（如果存在）。新建用户的默认值同步改为 `["BREAKOUT", "CAPITULATION"]`。

**理由**：avoid 出现"用户偏好里有 PULLBACK 但 setup_type 已无此值"的 dangling reference；用 CAPITULATION 作为替换默认值符合"用户偏好底部反转 setup"的合理预设。

### 放弃了什么

- **保留 PULLBACK 枚举，新增 CAPITULATION 并行**：会引入"两个 setup 都命中怎么办"的歧义，且 PULLBACK 当前判定逻辑已被证明与 SRS 错位，没有保留价值（用户已确认 2026-05-15）
- **硬删 setup_snapshots 历史 PULLBACK 行**：丢失审计 + 回测数据；与项目"快照表保留 60 天"的策略冲突
- **CAPITULATION 优先级低于 BREAKOUT/RECLAIM**：会导致罕见边界情况（同时命中）的语义歧义，hard-coded 优先级更清晰
- **`capitulationEvidence` 在所有 setup 都返回真实数据**：会导致 BREAKOUT/RECLAIM 上展示 chips 误导用户；统一返回 null 更安全
- **把 `_is_capitulation_reversal` 7 条门做成 score（M/N 阈值）**：失去 SRS 设计的"严格底部反转"语义；用户已明确要稀疏触发（每月几只）作为设计意图

### 影响

- **DATA-MODEL.md** §SetupSnapshot：setup_type 枚举表更新、`_classify_setup_type` 优先级业务规则新增、BREAKOUT 降级 fall-through 文字同步
- **API-CONTRACT.md**：`setupType` 枚举说明更新、BREAKOUT 降级文字同步、`GET /api/cockpit/decision/{ticker}` 响应追加 `capitulationEvidence`、`user_settings.preferredSetups` 默认值更新
- **F217-b alembic 021** 实施职责：(a) setup_snapshots 历史 PULLBACK 行软删 (b) user_settings JSON 字段值迁移 (c) 视 DB 是否启用 ENUM/CHECK 决定迁移策略（SQLite 无原生 ENUM，PostgreSQL 需 `ALTER TYPE`）
- **F215-b D088** 文字依赖：BREAKOUT 降级 fall-through 描述同步（不改语义）
- **F216-d2 D093**（ready_signal 8 门）**不受影响**：weekly_stage gate 与 setup_type 解耦，CAPITULATION 也会经过同样的 ready_signal 评估（CAPITULATION 在 Stage 4 触发的概率最高，符合 SRS 投降底特征 — Stage 2 要求让大部分 CAPITULATION 在 ready_signal 上是 false，这是设计意图）
- **F202/F203 已完成 feature**：无代码改动，但 setupType 枚举切换会影响其前端 TypeScript 类型联合（F217-c sub-sprint 同步更新）

### 回滚方式

- 文档层：DATA-MODEL/API-CONTRACT/DECISIONS 经 git revert 回滚
- 代码层：F217-a Generator 阶段未触发任何 DB schema 改动，可直接 revert commit；alembic 021（F217-b）有 downgrade 路径（恢复 legacy 字段、把 setup_type 行 legacy=false 还原，但**新写入的 CAPITULATION 行无法自动转回 PULLBACK** — 因为它们语义不同；回滚需手动处理或接受数据丢失）
- 配置层：无 env flag 控制 CAPITULATION 启停；若需临时禁用，可在 `cockpit_params.SETUP.CAPITULATION_ENABLED=False` 让 `_classify_setup_type` 跳过该分支（如未实现此 flag，则纯代码 revert）

---

## D096：F218 Phase D — Repricing Trigger 5 类框架与 evidence_json 单列设计

**日期**：2026-05-18
**Feature**：F218 Cockpit Phase D — Repricing Trigger 完整框架（5 类）
**SRS 依据**：《慢交易系统框架》§ 十一 Repricing Trigger / `/Users/wonderer/.claude/plans/featrue-dev-replicated-goblet.md` §Phase D

**决策**：
1. Repricing Trigger 框架由 5 类 detector 组成：`EARNINGS_ACCEL` / `MARGIN_EXPANSION` / `NEW_PRODUCT` / `SECTOR_CYCLE` / `BALANCE_INFLECTION`
2. 单表 `repricing_triggers` 持久化所有 5 类，`trigger_type` 字段区分；`evidence` 字段使用 **JSON 单列**（`evidence_json: Text`）而非分表 / 分字段
3. service 内 `RepricingTriggerService.compute_and_store_all_triggers(date)` 串行调用 5 个 `_detect_*` 函数（非并发，便于错误隔离与日志归因）
4. 唯一键 `(ticker, trigger_type, detected_date)` — 同一标的同一类型每日至多一条；同类型多次触发用 `detected_date` 区分
5. soft expire 模型：detector re-scan 未命中 → `active=true → false`（保留审计，年度后硬删 active=false 行）
6. `confidence` 字段 0.0-1.0；初版用简化策略（默认 0.5；强命中 0.8），细化逻辑留给 D4b NLP 升级或 sizing 调优阶段

**原因**：
- **5 类是 SRS 明确分类**：基本面（T1 EPS / T2 Margin）+ 产业（T3 Product / T4 Sector）+ 资产负债（T5 Balance Sheet）三大端，正交不重叠，覆盖 SRS § 十一 全部 trigger 类型
- **JSON 单列 vs 5 张子表**：5 类 evidence schema 差异极大（数组 / 字符串列表 / 时间序列对象 / 标量），分表会需要 5 个 repository + service 内 5 条独立查询路径；JSON 单列 + service 层 dataclass 反序列化 = 统一查询路径，未来加第 6 类 trigger 只需新 dataclass 不动 schema
- **串行 vs 并发 detector**：5 个 detector 总耗时预估 < 10s（T1/T4 纯 DB 查询、T2/T5 缓存表读、T3 关键词扫描）；并发收益微小但调试 / 失败隔离 / 日志归因复杂度显著上升
- **soft expire vs 硬删**：保留 active=false 行支持回测"trigger 持续时长"、"何时失效"等问题，是慢交易框架的核心审计能力；年度硬删（365 天）平衡审计深度与表体积

**放弃了什么**：
- **方案 B：5 张子表（trigger_earnings_accel / trigger_margin_expansion / ...）** — 放弃因为：(a) 5 类查询逻辑（按 ticker / 按 active）需要 union 5 表，性能反而差 (b) 加第 6 类 trigger 需要新建表 + alembic migration 而非加 dataclass (c) "全市场 active triggers" widget 查询逻辑爆炸
- **方案 C：evidence 拆为定长字段（如 metric_1_name / metric_1_value / ...）** — 放弃因为：(a) 不同 trigger evidence 字段数差异大（T3 关键词命中可能 N 条、T1 固定 6 个数字），定长字段浪费 + 不直观 (b) 失去类型语义，反查时需要 trigger_type 才能解释字段含义
- **方案 D：detector 并发执行** — 放弃因为：cron 每日 1 次场景下耗时不敏感，串行的调试与监控收益更高
- **方案 E：硬删过期 trigger（不保留 active=false）** — 放弃因为：丢失历史 trigger 失效 timeline 的审计能力，不符合慢交易框架长周期复盘需求

**影响**：
- **DATA-MODEL.md** §RepricingTrigger 新增（含 evidence_json schema 按 trigger_type 区分表）
- **API-CONTRACT.md** §Cockpit Repricing Triggers 新增 2 endpoint（evidence 字段 service 层反序列化 + camelCase 转换后返回）
- **ARCHITECTURE.md** 新增 §Cockpit Repricing Trigger Service 模块章节（service 调度链 + 5 detector 顺序 + cron 22:40 UTC）
- **F215 / F216 / F217**：零影响（只读复用 EarningsEventRepository / `_compute_rs_percentile` / SECTOR_ETFS）
- **alembic 022**：创建 `repricing_triggers` 表
- **`backend/app/services/cockpit/repricing_trigger_service.py`**：新建 service 模块
- **`backend/app/repositories/repricing_trigger_repository.py`**：新建 repository

---

## D097：F218 Phase D — FMP 新增 endpoint 接入 + quota + 缓存策略

**日期**：2026-05-18（修正 2026-05-18 — 见文末 §修正记录）
**Feature**：F218 D3 T2 Margin Expansion / D6 T5 Balance Sheet Inflection
**前置决策**：D034（FMP /stable/ 端点映射）/ D065（earnings-calendar 接入）

**决策**（已含 2026-05-18 修正）：
1. FMP 新增 3 endpoint 接入（不是 4，T2/T5 共享 cash-flow）：
   - `/stable/income-statement?symbol={ticker}&period=quarter&limit=8`（季度利润表，T2 detector — 用于 gross/op/net margin 计算，**取代原计划 key-metrics-ttm + ratios quarterly**）
   - `/stable/balance-sheet-statement?symbol={ticker}&period=quarter&limit=8`（季度资产负债表，T5 detector 主用 + T2 roic 近似公式分母复用）
   - `/stable/cash-flow-statement?symbol={ticker}&period=quarter&limit=8`（季度现金流，**T2/T5 共享**：T2 用于 fcf_margin，T5 用于 FCF 拐点判定）
2. 数据获取时机：**复用 weekly pool rebuild cron（周一 06:30 UTC）**，对 cockpit pool 内 ~50 ticker 串行调用 3 endpoint
3. 缓存表设计：T2 数据落 `stock_key_metrics_quarterly`（NP-sd-2：去重键 `(ticker, fiscal_quarter)`，fiscal_quarter 拼接 FMP `period` + " " + `fiscalYear`，如 "Q2 2026"）；T5 数据落 `stock_fundamentals_quarterly`（同样去重键）
4. upsert 语义：null 字段不擦除既有值（避免 FMP 暂时缺数据时数据丢失）；非 null 字段完整覆盖
5. **margin / fcf / fcf_margin / roic 全部在 service 层从原始财务数字计算**（修正后强化）：
   - `gross_margin = grossProfit / revenue`（income-statement）
   - `op_margin = operatingIncome / revenue`（income-statement）
   - `net_margin = netIncome / revenue`（income-statement）
   - `fcf = netCashProvidedByOperatingActivities + investmentsInPropertyPlantAndEquipment`（cash-flow；capex 已为负值故加号）
   - `fcf_margin = fcf / revenue`
   - **`roic ≈ netIncome / (totalStockholdersEquity + totalDebt - cashAndShortTermInvestments)`** —— 近似公式（D097 修正 2026-05-18，因 Starter `/key-metrics?period=quarter` 不可用）；非标准 ROIC 但提供方向性信号；任一输入 null 或分母 ≤ 0 → null
6. `net_debt` 在 service 层计算（`total_debt - cash`）而非 FMP 返回；任一输入 null → net_debt = null（与 5 同思路）
7. FMP endpoint 常量集中在 `backend/app/external/fmp_client.py` 顶部声明：**`FMP_EP_INCOME_STATEMENT` / `FMP_EP_BALANCE_SHEET` / `FMP_EP_CASH_FLOW`**（既有 `FMP_EP_KEY_METRICS_TTM` 保留供 F104 估值用，与 F218 无关）

**原因**：
- **复用 weekly cron vs 独立 daily job**：quota 估算 3 endpoint × ~50 ticker × 周 1 次 ≈ 150 calls/week，FMP Starter 300 req/min 完全无压力；季度数据本身周级刷新足够（季度公司变化频率 ≤ 周级），独立 daily job 浪费 quota 且制造冗余调度
- **`(ticker, fiscal_quarter)` 去重键 vs `(ticker, period_end_date)`**：FMP 同一财季 `period_end_date` 偶有调整（重述财报 / 财季截止日历微调），用 fiscal_quarter 字符串作为业务主键更稳定，避免 upsert 时漂移成多行
- **null 不擦除策略**：F204 earnings-calendar 已采用相同策略（D065），保持 FMP 接入模块一致性；避免 FMP 偶发性数据缺失污染历史数据
- **margin / roic service 层计算**：原始字段（revenue / grossProfit / netIncome / totalDebt / cash 等）从 income-statement + balance-sheet + cash-flow 均能取到；service 层计算便于后续按需求微调（如改 fcf 定义、roic 加入税务调整）
- **endpoint 常量集中**：与 D034 既有 FMP 常量管理一致，未来 FMP 改路径只改一处
- **T2/T5 共享 cash-flow**：避免对同 ticker 抓 2 次 cash-flow（FMP 单次 quota 浪费 + 时间窗口不一致风险）；pool rebuild 内单 ticker 单次抓取，分别 upsert 进 2 张缓存表

**放弃了什么**：
- **方案 B：独立 daily refresh job（晚于 earnings cron）** — 放弃因为 quota 浪费 + 调度链冗余 + 季度数据日级粒度无意义
- **方案 C：`(ticker, period_end_date)` 联合去重键** — 放弃因为 FMP 财季 end date 偶有调整导致 upsert 漂移，已知风险
- **方案 D：T2/T5 各自独立缓存表（按 endpoint 1:1 拆 N 表）** — 放弃因为 detector 内合并使用，分多表反而需要 join，2 张缓存表（按 detector 用途分）更符合查询模式
- **方案 E：net_debt 直接存 FMP 计算结果（如果 FMP 有的话）** — 放弃因为 FMP 不直接返回，且 service 计算成本低 + 可控
- **方案 F：F218 推迟等订阅升级以拿到标准 ROIC 与 ratios quarterly** — 放弃因为：(a) 升级订阅是付费动作，超 F218 范围决策权限 (b) income-statement + balance-sheet + cash-flow 原始字段足以计算所有 margin + roic 近似值，业务信号方向性已足够 (c) D4b NLP 升级也是独立 issue 同等待，整体框架先 ship 后迭代
- **方案 G：T2 detector 不做 roic，只看 margin** — 放弃因为 SRS § 十一 T2 明确把"ROIC 改善"列为 margin 扩张的强化共振信号，删除会损失语义；近似公式即使不标准也优于完全缺失

**影响**：
- **DATA-MODEL.md** §StockKeyMetricsQuarterly + §StockFundamentalsQuarterly 新增（修正版含 service 层计算公式）
- **ARCHITECTURE.md** FMP 端点映射表追加 3 行 + Endpoint 常量集中段追加 3 个 `FMP_EP_*`
- **alembic 022**（与 D096 同迁移）：创建 2 张缓存表 + uq 索引（schema 不变，已落地）
- **`backend/app/external/fmp_client.py`**：新增 3 endpoint client 方法（`get_income_statement_quarterly` / `get_balance_sheet_quarterly` / `get_cash_flow_quarterly`）
- **`backend/app/repositories/key_metrics_repository.py`** + **`fundamentals_repository.py`**：新建 2 repository（fundamentals 由 d6a 落地，key_metrics 由 d3a 落地）
- **weekly pool rebuild service**：在 cockpit pool 完成后追加 3 endpoint 串行抓取 + 2 表 upsert 步骤（cash-flow 单次抓取分别 upsert）
- **FMP rate limit 不变**（D034 token bucket 300/min + burst 50 仍适用）

**修正记录（2026-05-18 — 触发起因 F218-d3a contract 起草前 live probe）**：

D097 原文（2026-05-18 早些时候）写"FMP 4 endpoint：key-metrics-ttm + ratios quarterly + balance-sheet + cash-flow"。F218-d3a contract 起草前用 FMP_API_KEY 实际 live probe 发现：
- `/stable/key-metrics?period=quarter` → **HTTP 402 Premium**（Starter 不覆盖）
- `/stable/ratios?period=quarter` → **HTTP 402 Premium**（Starter 不覆盖）
- `/stable/income-statement?period=quarter` → ✅ 工作（含 revenue / grossProfit / operatingIncome / netIncome / fiscalYear / period 等所有计算 margin 所需字段）
- `/stable/balance-sheet-statement?period=quarter` → ✅ 工作
- `/stable/cash-flow-statement?period=quarter` → ✅ 工作

修正方向（用户 Q1/Q2/Q3 确认 2026-05-18）：
1. **T2 数据源 endpoint 改为 income-statement**：从 grossProfit / operatingIncome / netIncome / revenue 计算 3 个 margin
2. **roic 改 service 层近似公式**（保留字段，业务方向性信号优先于标准定义）：`netIncome / (totalStockholdersEquity + totalDebt - cashAndShortTermInvestments)`，复用 d6a 已抓的 balance-sheet 字段，零额外 quota
3. **endpoint 从 4 收敛到 3**：T2/T5 共享 cash-flow（T2 fcf_margin + T5 FCF 拐点），单次抓取分别 upsert
4. **quota 估算 200 calls/week → 150 calls/week**（更省）

修正不影响范围：
- alembic 022（已 done @ F218-d1）：表结构未变（fcf_margin / roic 字段保留），不需要新迁移
- 对外 API-CONTRACT.md：cockpit/repricing-triggers 2 endpoint 与 evidence_json schema 完全不变
- F218-d1（done）/ F218-d2（done）的代码：完全不影响（T1 EARNINGS_ACCEL 用 earnings_events，不依赖 d3a/d6a 路径）

教训：D097 原起草未做 live probe，凭 FMP 公开文档假设端点可用（公开文档不区分订阅等级）。这与 D035 → D036 修正路径同源（D035 假设 `/stable/ratios-ttm` 含估值 TTM，S3 live smoke 才发现需要走 `/stable/key-metrics-ttm`）。**新约定**：D034 之后任何"假设 FMP endpoint 可用"的决策，必须在落地前 24 小时内做一次 live probe（可在 contract 起草阶段做），不接受"按公开文档应该可用"的推理

---

## D098：F218 D4a — T3 New Product 关键词扫描 vs NLP 取舍（D4b 升级路径）

**日期**：2026-05-18
**Feature**：F218 D4a T3 New Product / Platform Shift detector
**SRS 依据**：《慢交易系统框架》§ 十一 T3 New Product

**决策**：
1. T3 detector 本期采用 **D4a 关键词扫描**：扫描 `news_cache` 过去 30 日 news headlines，命中关键词集合 `{launch, unveil, introduce, release, AI, platform, new product}` ≥ 2 次 → 触发
2. 关键词集合作为常量集中在 `backend/app/services/cockpit/repricing_trigger_service.py` 顶部声明，便于调参
3. evidence 字段包含命中关键词清单 + 对应 news_links（最多 5 条，便于前端跳转）
4. **明确不实施 D4b**（NLP 升级 / 嵌入相似度 / LLM 标签）— 作为独立 issue 排期，不在 F218 范围
5. 接受 D4a 高 recall 低 precision 的取舍：T3 trigger 可能假阳，但与 T1/T2/T4/T5 同时命中时形成多 trigger 高 conviction 信号

**原因**：
- **快速上线 vs 完美精度**：D4a 关键词扫描可在 2-3 文件内实现（service + repo + 单测）；D4b NLP 升级需新引入嵌入 / LLM 调用 / token 成本 / 性能评估，至少 2-3 个 sub-sprint 工作量
- **多 trigger 共振抵消假阳风险**：SRS 框架本身要求"多 trigger 共振 → 高 conviction"，单 T3 触发不直接驱动决策；假阳 T3 在无 T1/T2/T4/T5 支撑时不会进入 ready_signal 优先级
- **关键词集合保守选择**：7 个关键词均为 product launch / platform shift 高频词，AI 时代命中率会偏高（接受作为时代特征）
- **D4b 独立 issue**：NLP 升级独立技术栈（embedding model / LLM gateway 已有 AiGateway 可复用），适合作为独立 epic 排期而非 F218 子任务

**放弃了什么**：
- **方案 B：D4a + D4b 同 feature 实施** — 放弃因为：(a) F218 已含 7-9 sub-sprint 工作量，再加 NLP 升级超出单 release 范围 (b) NLP 升级有独立技术风险（嵌入模型选型 / cost / 性能），需要独立 spike (c) 阻塞 F218 整体 ship
- **方案 C：T3 完全不做（等 D4b 一次到位）** — 放弃因为：(a) 失去 F218 完整 5 类框架的语义对齐 SRS (b) 关键词扫描已能识别 NVDA H100 / TSLA Cybertruck / META AI Llama 等近年明显 product launch 案例（验证可行性） (c) D4b 排期不明，T3 长期缺位
- **方案 D：扫描全文 news body 而非 headlines** — 放弃因为：(a) news_cache 当前只稳定保留 headlines + 摘要，全文非必有 (b) 全文 false positive 风险大幅上升（关键词在历史回顾、产品评测中频繁出现）
- **方案 E：精确关键词扩展到 30+ 个（覆盖更多产品类型）** — 放弃因为：关键词集合是常量，随时可加；初版保守 7 个便于观察命中分布

**影响**：
- **DATA-MODEL.md** §RepricingTrigger 中 NEW_PRODUCT evidence_json schema 已含 `keyword_hits` / `news_links` / `scan_window_days`
- **`backend/app/services/cockpit/repricing_trigger_service.py`**：常量 `NEW_PRODUCT_KEYWORDS` + `_detect_new_product` 方法
- **F218 acceptance**：D4b NLP 升级**不在 F218 验收范围**；T3 假阳率作为运行后观察项，必要时调参或加入 D4b 排期
- **后续 D4b epic（独立 feature）**：建议在 F218 上线 2-3 个月后基于实际数据评估是否启动；候选技术包括 embedding 相似度（OpenAI text-embedding-3-small）或 AiGateway LLM 分类（task_type=news_classifier）

---

## D099：CockpitChartWidget — stale canvas 问题修复（isError guard effect）

**日期**：2026-05-20
**文件**：`frontend/src/cockpit/widgets/CockpitChartWidget.tsx`

**背景（Bug 描述）**：
用户切换到 DB 中不存在的 ticker（如 SPYG）时，CockpitChart 有时会继续显示**前一个 ticker 的图表**，而不是切换到 "Failed to load chart data" 空状态。

**根本原因**：
主 `useEffect` 依赖 `[chartQuery.data]`。当 ticker 切换时：
- 若之前 ticker 有数据（`dataA`），切换后 `chartQuery.data` 从 `dataA` → `undefined`，cleanup 正常触发，`chart.remove()` 被调用 ✓
- 但存在边缘情况：React 先卸载含 `ref` 的 container div（因 `chartQuery.isSuccess` 变 false），再异步运行 cleanup；若 `chart.remove()` 因竞态未正确执行，旧 canvas 仍挂在已卸载的 DOM 节点里，但视觉上因为旧 DOM 可能短暂保留而可见。
- 另一条路径：两次连续切换到非 DB ticker，`chartQuery.data` 始终为 `undefined`（未变化），cleanup 永远不触发。

**决策**：
1. 新增 `chartRef = useRef<IChartApi | null>(null)` — 跨 effect 持久持有 chart 实例
2. 主 effect 在创建 chart 后立即 `chartRef.current = chart`；cleanup 里同步置 `chartRef.current = null`
3. 新增独立 `useEffect([chartQuery.isError])`：若 `isError === true` 且 `chartRef.current` 非 null，主动调用 `chartRef.current.remove()` 并清空所有 series ref

**放弃了什么**：
- **方案 A：始终渲染 container div（隐藏/显示而非挂卸）** — 可完全避免 containerRef 竞态，但需要重构条件渲染逻辑，改动范围更大，且当前 lightweight-charts 在 display:none 容器里有 ResizeObserver 问题
- **方案 B：在主 effect 里监听 `[chartQuery.data, chartQuery.isError]`** — 会导致 `isError` 变化时触发完整的 chart 重建逻辑（因为 effect 会重新运行），无谓开销

**影响**：
- 仅修改 `CockpitChartWidget.tsx`，不影响其他 widget
- `chartRef` 作为内部实现细节，不暴露到组件外部

---

## D100：F219 — MACD 体系裁剪到 divergence，其余冗余不实现

**决定**：在已有 `trend_score` / `vol_zscore` / `weekly_stage` 体系下，MACD 的 line/signal 交叉、0 轴判定、histogram 加速全部冗余。仅保留 divergence（价 vs MACD 背离）一个用途：bearish divergence 作持仓早衰报警，bullish divergence 作 CAPITULATION 辅助证据（不进 7-AND 门）。

**放弃了什么**：
- MACD line/signal 交叉信号 — 与 trend_score MA 阶梯重叠
- 0 轴过滤 — 不启用，bearish/bullish 不强制 MACD 正负
- histogram 加速 — 在 vol_zscore + OBV trend 体系下冗余
- `?macd_fast=...` 查询参数开放 — 硬编码 12/26/9 不允许外部调参

**影响**：`setup_snapshots.macd_divergence` 列仅存 `'bearish'/'bullish'/NULL`，不暴露 MACD 序列原始值；不接入 CockpitChart overlay 和 DecisionPanel AI 区块。

---

## D101：F219 — MACD divergence 检测算法选型（简单极值法 vs swing-pivot）

**决定**：采用"lookback=20 内末位极值 vs 反向极值"简单规则。bearish：closes[-1] == max(closes[-20:]) AND macd_line[-1] < max(macd_line[-20:])；bullish：对称。不采用 swing-pivot 识别的更复杂版本。

**放弃了什么**：
- swing-pivot 版本 — 精度更高但实现复杂，引入 peak/valley 定义歧义；lookback=20 与 EXTENDED 分类同量级已够用
- 0 轴过滤辅助条件 — 协商点 NP-2 决定不启用，保持逻辑最简

**影响**：`MIN_BARS_REQUIRED=50`（SLOW=26 + SIGNAL=9 + LOOKBACK=20 上下界保护）；macd_line 末尾任何 None（短历史）→ 返回 None；同时满足两个方向的病态情况→ None，不抛异常。参数 12/26/9 硬编码在 `CockpitMACDParams` 类，不可通过 query 参数覆盖。

---

## D102：F219-b — 不抽 MacdDivergenceBadge 组件

**决定**：`macdDivergence` 的视觉渲染直接 inline 在 `_positionListRow.tsx`（⚠️ emoji span）和 `SetupMonitorWidget.tsx`（'MACD+' chip span），不抽共享组件。

**放弃了什么**：单独 `MacdDivergenceBadge` 组件——F219-b 仅 2 处使用，且两处表现形式不同（emoji vs 文字 chip），CockpitChart overlay / DecisionPanel 经 F219 contract 明确排除，无任何下游复用点；抽组件会成为虚假抽象。

**影响**：若未来真的有第 3 处复用，再抽即可；CLAUDE.md "三处相似才抽象"原则在此成立。

---

## D103：F219-b — MACD divergence 触发规则收紧（NP-3）

**决定**：PositionList 仅 `status === 'OPEN' && macdDivergence === 'bearish'` 显示 ⚠️；SetupMonitor 仅 `setupType === 'CAPITULATION' && macdDivergence === 'bullish'` 显示 'MACD+'。

**放弃了什么**：
- PositionList 显示 CLOSED 持仓的 bearish 标识 — 已平仓持仓显示 ⚠️ 会被误读为历史问题报警，无操作价值
- SetupMonitor 非 CAPITULATION 行显示 'MACD+' — 会被误读为进了 ready gate，与 8-AND gate 语义冲突
- PositionList 显示 bullish chip — 持仓 widget 没有 CAPITULATION 上下文，bullish 信号在此无意义

**影响**：4 个"不渲染"路径均有对应单元测试覆盖（S14-2/3 + M2/3）。

---

## D104：F220 — 正常化 P/E 平均有效税率防循环（税率自身边界筛种子）

> ⚠️ **DEPRECATED（2026-06-10）**：F220-a 自算正常化 P/E 方案放弃，P/E 改用 FMP raw `priceToEarningsRatioTTM`（现状 F104 已透传）。本决策（税率防循环）失去落地对象，作废留档。原因：5 票实测显示 raw 对 4/5 已准且自动处理货币，自算反引入货币 bug + 阈值不普适。详见 [验收记录](../验收/v2.6-F220-a1-acceptance.md)。

**日期**：2026-06-10

**决定**：计算税后营业利润 NOPAT 所用的"平均有效税率"，其"正常季"判定**用税率自身边界独立筛选**——仅取 `incomeBeforeTax > 0` 且 `0 ≤ rate ≤ 0.50` 的季（rate = incomeTaxExpense / incomeBeforeTax），取最近 ≤4 季均值。**绝不复用净利润异常判定**来选税率正常季。无可信种子（全季 IBT≤0 或越界）→ 税率 None → 整体降级（degradeReason=`no_tax_seed`），**不用法定 21% 兜底**。

**原因**：异常季判定依赖 NOPAT，NOPAT 依赖税率——若税率"正常季"也用净利润异常判定来选，形成**循环依赖**（设计文档点名最易写错处）。改用税率自身合理边界独立筛种子破环：DUOL Q3'25 一次性递延税资产转回会使该季 effective rate 落到负值/越界 → 自动从均值剔除，达成"排除被污染季"意图而无循环。返回 `taxRateSourceQuarters` 满足可追溯。

**放弃了什么**：
- 复用净利润异常判定筛税率正常季——循环依赖，设计文档明确禁止
- 法定 21% 兜底——遵设计文档：无可信税率宁可降级也不用假设值，避免给出"看似精确实则编造"的正常化 P/E
- 单季税率——1 季易受噪声，取 ≤4 季均值更稳

**影响**：F220-a `compute_normal_tax_rate(quarters)` 纯函数 + **硬要求回归单测**（污染季畸高/畸低/越界被剔除、均值仅来自正常季）；degradeReason 新增 `no_tax_seed`；API `traceability.avgEffectiveTaxRate` + `taxRateSourceQuarters`。

---

## D105：F220 — 市值自算口径（Diluted × price）+ P/(FCF−SBC) 自洽红旗

> ⚠️ **F220-b 推翻（2026-06-12）**：本决策两个支柱均失效——
> 1. **自洽红旗 `sbcSensitiveFlag` 砍掉**：红旗规则锚在 `normalizedPe`，而正常化 P/E 方案已于 2026-06-10 整体 deprecated（F220-a/a1/a2/c），锚恒 null，红旗永不亮，形同虚设 → 直接删除，不进 schema/类型/代码。
> 2. **市值改用 FMP `marketCap`**：自算口径的唯一理由是「与 normalizedPe 的 diluted EPS 口径自洽」；normalizedPe 已废，自洽前提消失。`pFcfRaw / pFcfAdj` 改用 schema 顶层 `marketCap`（FMP key-metrics-ttm，已在 get_fundamentals 拉取）—— 极简零额外调用，且 ADR/JPY/DKK 货币自动正确（自算 Diluted×price 有货币错配坑）。
>
> F220-b 最终口径以 [API-CONTRACT §fundamentals「F220-b 落地修订」](API-CONTRACT.md) 为准；下方原决策正文仅留档。

**日期**：2026-06-10

**决定**：P/(FCF−SBC) 双版本与自洽红旗所用的市值 = **最新季 `weightedAverageShsOutDil`（Diluted）× 当前价（自算）**，与正常化 EPS 口径自洽；**不用** FMP key-metrics-ttm 的 `marketCap`。红旗规则：`|pFcfAdj − normalizedPe| / normalizedPe > 0.40` → `sbcSensitiveFlag = true`。

**原因**：normalizedPe 的分母是 diluted EPS（基于 weightedAverageShsOutDil）。若 P/(FCF−SBC) 用 FMP 的 basic / 期末口径 marketCap，两个估值指标口径分叉，自洽检验（gap>40% 红旗）失真。自算市值保证两者同口径，gap 才有信号意义。

**放弃了什么**：FMP key-metrics-ttm.marketCap 作自洽计算输入（口径不一致，破坏自洽）。schema 顶层 `marketCap` **仍保留** FMP 值（向后兼容 + 一般展示），自算市值仅用于 traceability 语义内（R7 口径分叉，不暴露为顶层字段避免二义）。

**影响**：F220-b `compute_p_fcf(last4, market_cap=diluted×price)`；`traceability.dilutedShares` 暴露口径；API 说明标注口径分叉。

---

## D106：F220 — 成员门控（仅 watchlist+pool）+ 同日缓存 + pool 只读访问边界

**日期**：2026-06-10

**决定**：正常化字段仅对 ticker ∈ watchlist(active) 或 trend pool 计算；非成员 → 正常化字段 None + `degradeReason="out_of_scope"`，原始 TTM 指标照常返回。计算结果走 same-day `daily_payload_cache`（每票每日最多一次真实计算 + FMP 季报调用）。trend pool 成员判断走**只读 repository 访问 pool_cache 表**，**不** import cockpit service 逻辑（守 workbench↛cockpit 依赖层级规则）。F220-e analyst-estimates weekly cron（周一 07:00 UTC）同样只覆盖 watchlist+pool。

**原因**：正常化计算需拉季报（FMP 配额）+ live 计算（延迟）。对全市场任意 ticker 都算会爆配额 / 拖延迟。门控把成本限于小集合（watchlist+pool ~几十票），同日缓存再砍重复请求。冷门股不触发（R3 缓解）。

**放弃了什么**：
- 覆盖全市场任意 ticker（配额 + 延迟不可控）
- workbench 直接 import cockpit pool service 做成员判断（违反依赖层级，改走只读 repository 数据访问）

**影响**：get_fundamentals 门控编排短路；normalized_pe_history / analyst_estimate_snapshots 覆盖天然限于成员，历史稀疏（R4 留待 F220-f）；**待查-1** = pool 成员只读 repository 入口（F220-a 实现确认）。

> ✅ **F220-b 落地（2026-06-12）**：成员门控正式落到 `pFcfRaw / pFcfAdj` —— `is_member = (stock active) or _is_pool_member(ticker)`，非成员两字段 null 且不调 `get_cash_flow_quarterly`（省 FMP 季报配额）。**待查-1 坐实**：pool 成员判断直读 `CockpitPoolCache` model（`app.models.cockpit_pool_cache`，`stock_detail_service._is_pool_member`），**不新建 repository、不 import cockpit service**——守 workbench↛cockpit 依赖层级。

---

## D107：F220 — 降级显式"不可用"不回退 raw + fail-open + 辅助信号不进主锚

> ⚠️ **DEPRECATED（2026-06-10）**：F220-a 正常化方案放弃，决策**反转**——P/E 主位**直接用 FMP raw** `priceToEarningsRatioTTM`（本决策原则恰是"绝不回退 raw"，现已不适用）。作废留档。详见 [验收记录](../验收/v2.6-F220-a1-acceptance.md)。

**日期**：2026-06-10

**决定**：正常化算不出（季报<4 → `insufficient_quarters` / 正常化EPS≤0 → `negative_normalized_eps` / 无税率种子 → `no_tax_seed` / 无当前价 → `no_price`）→ normalizedPe=None，前端主位显示"—"+ degradeReason tooltip，**绝不回退原始 `priceToEarnings`**。fail-open：季报拉取失败/不足 → 正常化字段 None + degradeReason，endpoint 仍 200，原始 P/S/PEG/ROCE/FCF/raw P/E 照常。`epsAcceleration` / `estimateRevision` 仅作质量表**辅助信号**，不进①正常化 P/E / P/(FCF−SBC) 主锚数值。

**原因**：原始 GAAP P/E 正是 F220 要规避的失真源（DUOL raw ~13× 假象便宜）。算不出时回退 raw 等于把用户推回陷阱。显式标"不可用"+原因（可追溯）比给一个误导值更诚实。fail-open 保证新功能不拖垮既有 Fundamentals widget。

**放弃了什么**：
- 降级回退 raw P/E（把失真源当兜底，违背 feature 初衷）
- 算不出时 endpoint 报错（会拖垮整个 widget，改 fail-open 200 + 原始指标照常）
- 把 epsAcceleration / estimateRevision 纳入主锚加权（动量 / 预期是参考维度，混入会污染去噪后的估值锚）

**影响**：degradeReason 枚举（5 值 + null）；前端主位降级渲染 + tooltip + `<details>` 追溯折叠区；P/(FCF−SBC) 始终并列展示供参考（即便 normalizedPe 降级）。


