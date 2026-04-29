---
status: confirmed
confirmed_at: 2026-04-22
last_modified_by: feature-dev F111-a on-demand 当日缓存 (D055)
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
