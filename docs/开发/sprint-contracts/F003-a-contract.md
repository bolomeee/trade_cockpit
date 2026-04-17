# Sprint Contract：F003-a 数据刷新核心（Repository + Service）

> 日期：2026-04-17 | 状态：草案
> 引用文档：
>   DATA-MODEL.md#daily-bar / #system-log
>   features.json#F003
>   ARCHITECTURE.md（Polygon tier / rate limit）

> F003 拆分三段：
> - **F003-a（本 Contract）**：数据刷新核心 —— DailyBar/SystemLog repository + DataRefreshService（不接 API、不接调度）
> - **F003-b**：API + APScheduler + watchlist add_stock 钩子
> - **F003-c**：前端 Refresh Data 按钮 + 状态轮询

---

## 本次实现范围

**包含**：

- **DailyBarRepository**（`repositories/daily_bar_repository.py`）
  - `get_latest_date(stock_id) -> date | None`：最新 bar 日期（用于判断增量起点）
  - `bulk_upsert(stock_id, bars: list[BarDTO])`：按 `(stock_id, date)` 唯一约束插入或忽略（历史数据不可变，跳过冲突）
  - `prune_to_window(stock_id, max_rows=250)`：删除早于最近 250 条的记录
  - `count_bars(stock_id) -> int`（已在 StockRepository，但 daily-bar 语义上属于本 repo；本 sprint 不挪动，只读）

- **SystemLogRepository**（`repositories/system_log_repository.py`）
  - `create(level, source, message, detail=None) -> SystemLog`
  - `purge_older_than(days=7)`：删除 `created_at < now - 7d`
  - `list_recent(limit=500, level=None) -> list[SystemLog]`（F008 会用，本 sprint 顺带提供）

- **DataRefreshService**（`services/data_refresh_service.py`）
  - `backfill_stock(stock_id, days=250) -> RefreshResult`
    - 用 PolygonClient.get_daily_aggs 拉取 `today - days` 到 `today` 的日线
    - 转换 polygon agg → BarDTO（timestamp ms → date；ohlcv 映射）
    - 调用 `DailyBarRepository.bulk_upsert`
    - 调用 `SignalService.recompute_for_stock(stock_id)` 重算信号
    - 更新 `Stock.last_refreshed_at`
  - `increment_stock(stock_id) -> RefreshResult`
    - 读 `get_latest_date`；若无 → 视为 backfill
    - 拉 `(latest_date + 1)` 到 `today`；insert → `prune_to_window(250)` → recompute
  - `refresh_all(stock_ids: list[int]) -> BatchResult`
    - 顺序遍历（Polygon 客户端已有 token-bucket 限流）
    - 单只失败：写 SystemLog(level=ERROR, source="data_refresh", message, detail=traceback)；继续下一只；计数 failed+1
    - 成功：写 SystemLog(level=OK, source="data_refresh", message=f"{ticker} refreshed (N bars)")
    - 返回 `{total, completed, failed, errors: [{ticker, error}]}`
  - `purge_old_logs()`：调用 `SystemLogRepository.purge_older_than(7)`（供 F003-b 调度器在每日 job 末尾调用，本 sprint 先实现）

- **数据结构**（内联于 service 文件，不单独起 schemas）
  - `BarDTO = TypedDict { date: date, open: float, high: float, low: float, close: float, volume: int }`
  - `RefreshResult = { stock_id, ticker, bars_added, status: "ok"|"error", error?: str }`
  - `BatchResult = { total, completed, failed, errors: list[dict] }`

**明确排除（本次不做）**：

- HTTP 路由 `/api/data/refresh` 与 `/api/data/status` → F003-b
- 内存 Job 状态跟踪器（refresh_job.py）与异步触发 → F003-b
- APScheduler 每日调度 → F003-b
- `add_stock` 触发 backfill 的钩子 → F003-b（service 方法本身在本 sprint 实现，F003-b 只做调用）
- 前端 UI → F003-c
- MarketIndex（SPX/NDX/TNX）刷新 → F006（DataRefreshService 本次只处理 watchlist DailyBar）

---

## 预计修改文件（6 个）

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/repositories/daily_bar_repository.py` | 新增 | get_latest_date / bulk_upsert / prune_to_window |
| 2 | `backend/app/repositories/system_log_repository.py` | 新增 | create / purge_older_than / list_recent |
| 3 | `backend/app/services/data_refresh_service.py` | 新增 | backfill_stock / increment_stock / refresh_all / purge_old_logs |
| 4 | `backend/tests/test_daily_bar_repository.py` | 新增 | upsert 幂等 / 窗口裁剪 / last_date |
| 5 | `backend/tests/test_system_log_repository.py` | 新增 | create / purge 7 天阈值 / list |
| 6 | `backend/tests/test_data_refresh_service.py` | 新增 | mock PolygonClient + 真 SQLite：backfill / increment / 单只失败隔离 / 成功后 signal 重算 |

（附带：完成后若 Polygon agg 字段名有不确定点，追加 DECISIONS D021 记录映射约定。不计入 6 文件清单。）

---

## 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `bulk_upsert` 对同一 `(stock_id, date)` 重复插入不报错、不产生重复行（幂等） | 单元 | pytest + SQLite |
| 2 | `bulk_upsert` 仅插入新日期，已存在的行保持不变（历史不可变） | 单元 | pytest + SQLite |
| 3 | `prune_to_window(stock_id, 250)` 在 300 条 bar 时删除最旧的 50 条，剩 250 条最近数据 | 单元 | pytest + SQLite |
| 4 | `get_latest_date` 在无数据时返回 None | 单元 | pytest + SQLite |
| 5 | `SystemLogRepository.create(level, source, message)` 持久化且 `created_at` 自动填充 | 单元 | pytest + SQLite |
| 6 | `purge_older_than(7)` 删除 `created_at < now - 7d` 的行，新记录保留 | 单元 | pytest + SQLite（用 freezegun 或直接插入旧 created_at） |
| 7 | `backfill_stock(stock_id, 250)`：mock PolygonClient 返回 250 条 agg，断言 DailyBar 行数 = 250、`Stock.last_refreshed_at` 更新 | 集成 | pytest + mock |
| 8 | `backfill_stock` 成功后，SignalService.recompute_for_stock 被调用（断言 Signal 行被写入） | 集成 | pytest + mock |
| 9 | `increment_stock`：已有 200 条 bar，mock 返回 5 条新 agg → 最终 205 条（未触发 prune，因 <250） | 集成 | pytest + mock |
| 10 | `increment_stock`：已有 250 条 bar，mock 返回 3 条新 agg → 最终 250 条（prune 到窗口） | 集成 | pytest + mock |
| 11 | `refresh_all([s1, s2, s3])`，s2 抛 PolygonError：s1/s3 正常完成，BatchResult `{completed:2, failed:1}`，SystemLog 表多出 1 条 ERROR 记录 | 集成 | pytest + mock |
| 12 | `refresh_all` 每只股票成功后写一条 `level=OK` SystemLog，message 含 ticker 与 bars_added | 集成 | pytest + mock |
| 13 | Polygon agg 字段映射：`timestamp (ms)` → `date`（UTC 日期），`o/h/l/c/v` → `open/high/low/close/volume` | 单元 | pytest（纯转换函数） |

E2E 不适用：F003-a 无 UI、无 HTTP。UI & 端到端刷新流程在 F003-c 的 E2E 中覆盖。

---

## Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] `uv run pytest backend/tests/test_daily_bar_repository.py` 全绿
- [ ] `uv run pytest backend/tests/test_system_log_repository.py` 全绿
- [ ] `uv run pytest backend/tests/test_data_refresh_service.py` 全绿
- [ ] `uv run pytest backend/tests`（全量回归）全绿，F001/F002 相关测试未受影响
- [ ] 数据库字段命名对齐 DATA-MODEL.md（`stock_id` / `date` / `open/high/low/close/volume` / `level/source/message/detail/created_at`）
- [ ] DailyBar 表保留 250 天窗口（任何 prune 后 `count == min(actual, 250)`）
- [ ] SystemLog 保留 7 天（purge 后 `created_at >= now - 7d`）
- [ ] `backfill_stock` 与 `increment_stock` 幂等（重复调用不改变最终状态）
- [ ] 单只股票失败不影响其他股票（`refresh_all` 的隔离性）
- [ ] PolygonClient 调用数 ≤ watchlist 长度（每只股票单次 API 调用；rate-limit 由 client 内部处理）
- [ ] 无 `print(...)` / 无 `TODO` 遗留
- [ ] 新增函数单体 ≤ 50 行
- [ ] 魔法数提取为常量：250（DailyBar 窗口）/ 7（SystemLog 保留天数）
- [ ] 无硬编码 Polygon API key；全部走 `PolygonClient`
- [ ] DECISIONS.md 如有新决策（Polygon agg 字段映射）追加 D021

---

👤 用户确认本 Contract 后，开发开始。
