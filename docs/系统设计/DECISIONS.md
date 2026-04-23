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
