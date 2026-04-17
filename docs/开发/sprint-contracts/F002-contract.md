# Sprint Contract：F002 150MA 信号引擎

> 日期：2026-04-17 | 状态：草案
> 引用文档：
>   DATA-MODEL.md#daily-bar / #signal / #pullback
>   API-CONTRACT.md#signals
>   features.json#F002

> ⚠️ **6 文件上限豁免**：本 Sprint 预计修改 9 个文件（6 业务 + 3 测试），超出常规上限。
> 豁免理由：F002 是"纯计算 → 持久化 → 查询 → HTTP"的最小垂直切片；
> 拆分后 F002-a 无 UI/API 可感知，仅能靠 pytest 验收，调度开销 > 收益。
> API 层极薄（router ≈ 20 行、schema ≈ 10 行、main.py 加 1 行 include）。
> 3 个独立测试文件按层隔离（engine 纯单元 / service 集成 / api 集成），
> 定位粒度仍然清晰。豁免已经用户同意，追加 DECISIONS D015 记录。

---

## 本次实现范围

**包含**：
- **纯计算内核**（`signal_engine.py`）
  - MA150（简单移动平均，窗口=150）
  - 20 日线性回归斜率（最小二乘，对最近 20 个 MA150 值拟合 y = ax + b，取 a）
  - signal_type 判定：BREAKOUT / BUY_ZONE / NEUTRAL / INSUFFICIENT
    - 优先级：BREAKOUT > BUY_ZONE > NEUTRAL
    - BUY_ZONE 区间：`0 ≤ (close - MA150) / MA150 × 100% ≤ 5`
    - BREAKOUT：`斜率正 ∧ 前日 close < MA150_前日 ∧ 当日 close ≥ MA150_当日`
    - INSUFFICIENT：有效 bar < 150
  - distance_pct：`(close - MA150) / MA150 × 100%`（INSUFFICIENT 时为 None）
  - 回踩事件识别：遍历日序，发现"前日非 BUY_ZONE + 当日 BUY_ZONE"时产生一条 Pullback
  - 后续涨幅：对每条 Pullback 计算 `return_10d / return_20d / return_30d`，
    基准为触发日 close，数据不足时保持 None
- **持久化**（`signal_repository.py`）
  - 根据 stock_id 查询 DailyBar（按 date 升序）
  - Signal upsert（基于 (stock_id, date) 唯一约束）
  - 保留最近 250 天 Signal，旧数据清理（与 DailyBar 对齐）
  - Pullback upsert（基于 (stock_id, date) 唯一约束，只覆盖后续涨幅字段）
  - 查询：`list_latest_signals_for_active()` / `get_latest_signal(stock_id)` / `get_signal_history(stock_id, days)`
- **服务编排**（`signal_service.py`）
  - `recompute_for_stock(stock_id)`：读取 DailyBar → 计算 → 持久化 Signal + Pullback
  - `list_board()`：返回所有 active 股票最新信号，按优先级排序
  - `get_ticker_detail(ticker, days)`：返回单只股票 latest + history
- **HTTP 暴露**（`routers/signals.py` + `schemas/signal.py`）
  - `GET /api/signals`
  - `GET /api/signals/:ticker?days=30`（默认 30，最大 250）
  - 404：ticker 不在 watchlist / inactive
  - 响应字段严格对齐 API-CONTRACT.md（camelCase）

**明确排除（本次不做）**：
- 数据刷新调度（F003 负责）——F002 假设 DailyBar 已由 F003/其他来源填充；测试使用 fixture 构造 DailyBar
- 自动触发 recompute：本次不在"添加股票"或"刷新数据"事件中 hook 到 `recompute_for_stock`，留给 F003 集成
- SignalBoard UI 渲染（F004 负责）
- 个股详情 Modal（F005 负责）
- MarketIndex（F006 负责）
- 基本面数据、K 线图 chart endpoints（F005 负责）

---

## 预计修改文件（9 个，豁免生效）

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/services/signal_engine.py` | 新增 | 纯函数：ma150 / slope / classify / detect_pullbacks / compute_returns |
| 2 | `backend/app/repositories/signal_repository.py` | 新增 | DailyBar 读取 + Signal/Pullback upsert + 查询 + 250 天窗口裁剪 |
| 3 | `backend/app/services/signal_service.py` | 新增 | recompute_for_stock / list_board / get_ticker_detail |
| 4 | `backend/app/schemas/signal.py` | 新增 | Pydantic 响应 schema（camelCase alias） |
| 5 | `backend/app/routers/signals.py` | 新增 | GET /api/signals, GET /api/signals/:ticker |
| 6 | `backend/app/main.py` | 修改 | `app.include_router(signals.router)` |
| 7 | `backend/tests/test_signal_engine.py` | 新增 | 纯单元：构造价格序列，断言 ma150/slope/classification/pullback |
| 8 | `backend/tests/test_signal_service.py` | 新增 | 集成：真 DB，插入 DailyBar，recompute 后断言 Signal/Pullback 行 |
| 9 | `backend/tests/test_signals_api.py` | 新增 | API 集成：排序、404、字段名、days 裁剪 |

（附带：完成后在 DECISIONS.md 追加一条 D015，记录"6 文件上限豁免"与"斜率判定算法选型"。不计入 9 文件清单，属于文档类必做动作。）

---

## 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | 给定 200 根 bar（斜率正、close 位于 MA150 上方 2%），`classify()` 返回 `BUY_ZONE`，`distancePct ≈ 2.0` | 单元 | pytest |
| 2 | 给定斜率正、前日 close < MA150、当日 close ≥ MA150，`classify()` 返回 `BREAKOUT`（优先级高于 BUY_ZONE） | 单元 | pytest |
| 3 | 给定 MA150 最近 20 日呈明显下行，`classify()` 返回 `NEUTRAL`（即使 close 处于 0–5% 区间） | 单元 | pytest |
| 4 | 只有 140 根 bar 时返回 `INSUFFICIENT`，`ma150Value` 与 `distancePct` 均为 None | 单元 | pytest |
| 5 | 构造序列：非 BUY_ZONE → BUY_ZONE → BUY_ZONE → 非 BUY_ZONE → BUY_ZONE，`detect_pullbacks()` 恰好返回 2 条 | 单元 | pytest |
| 6 | 对已存在的 Pullback 调用 `compute_returns`：return_10d 等于 `(bar[t+10].close - bar[t].close) / bar[t].close × 100`，数据不足时为 None | 单元 | pytest |
| 7 | `recompute_for_stock(stock_id)` 运行两次，Signal/Pullback 不产生重复行（upsert 生效） | 集成 | pytest + 临时 SQLite |
| 8 | `recompute_for_stock` 后，Signal 表行数 ≤ 250（超出部分被裁剪） | 集成 | pytest + 临时 SQLite |
| 9 | `GET /api/signals` 返回 active 股票每只最新一条 signal，按 BREAKOUT→BUY_ZONE→NEUTRAL→INSUFFICIENT 排序 | 集成 | pytest + FastAPI TestClient |
| 10 | `GET /api/signals/:ticker` 含 `latest` 与 `history` 字段，字段全部 camelCase，日期格式 ISO-8601 | 集成 | pytest + TestClient |
| 11 | `GET /api/signals/:ticker?days=5` 返回 history 至多 5 条；超过 250 返回 422 | 集成 | pytest + TestClient |
| 12 | ticker 不在 watchlist（或 `is_active=false`）时返回 404 + `{error:{code:"NOT_FOUND"}}` | 集成 | pytest + TestClient |

E2E 不适用：F002 无 UI。UI 层验收在 F004（SignalBoard）/ F005（Modal）各自 sprint 的 E2E 中覆盖。

---

## Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] `uv run pytest backend/tests/test_signal_engine.py` 全绿
- [ ] `uv run pytest backend/tests/test_signal_service.py` 全绿
- [ ] `uv run pytest backend/tests/test_signals_api.py` 全绿
- [ ] `uv run pytest backend/tests`（全量回归）全绿，F001 相关测试未被破坏
- [ ] API 响应字段 100% 对齐 API-CONTRACT.md（camelCase；`signalType` 值 ∈ {BREAKOUT, BUY_ZONE, NEUTRAL, INSUFFICIENT}）
- [ ] 数据库字段命名对齐 DATA-MODEL.md（signal_type / ma150_value / distance_pct / slope_positive / slope_value / return_10d/20d/30d）
- [ ] 未对已有 Alembic migration 做破坏性修改（F002 只读写 `signals` / `pullbacks` / `daily_bars` 表，schema 已在 F000-a 建立，不需要新 migration）
- [ ] BREAKOUT 与 BUY_ZONE 同时满足时返回 BREAKOUT（优先级铁律）
- [ ] 信号历史查询仅返回存在的日期（无空洞行）
- [ ] `recompute_for_stock` 幂等（重复执行行数不变、字段不变）
- [ ] 无 `print(...)` / 无 `TODO` 遗留、无 `console.error`（后端不适用）
- [ ] 新增/修改函数无超过 50 行的函数体
- [ ] 无硬编码魔法数：150（MA 窗口）/ 20（斜率窗口）/ 5.0（buy-zone 上限）/ 250（窗口上限）作为命名常量
- [ ] Polygon API、外部网络调用数 = 0（F002 只读本地 DB）
- [ ] DECISIONS.md 追加 D015（6 文件豁免 + 斜率算法选型）

---

👤 用户确认本 Contract 后，开发开始。
