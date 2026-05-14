# Sprint Contract：F105-a3 扫描服务层 + 独立 cron（Market Breakout Scanner）

> 日期：2026-04-21 | 状态：草案
> 依赖：F105-a1 ✅ done · F105-a2 🔍 needs_review（本 Sprint 复用其新增客户端方法）
> 引用文档：
>   DECISIONS.md#D038（universe 月级刷新） · #D039（SMA 主路径 + EOD fallback） · #D040（最新快照覆盖写） · #D042（scanner 独立 cron）
>   DATA-MODEL.md#MarketScanUniverse · #MarketBreakoutScan
>   ARCHITECTURE.md#环境配置（L213–219 cron env vars） · #外部数据源映射（FMP screener / sma）
>   backend/app/services/signal_engine.py（F002 纯函数 `compute_ma150_series` / `compute_slope`，直接复用）
>   backend/app/services/market_refresh_service.py（per-symbol 隔离 + SystemLog 模式）
>   backend/app/services/refresh_job.py（现有 APScheduler 单例注册模式）

---

## 本次实现范围

**包含**：

### 1. `UniverseRefreshService`（新文件）
- `refresh() -> UniverseRefreshResult`
  - 调 `fmp.get_screener_universe()`（默认 50B 阈值、NYSE/NASDAQ/AMEX）
  - 将每个原始 dict 适配为 `UniverseUpsertRow(ticker, company_name, exchange, market_cap)`；缺字段/market_cap 非法的行跳过不入库但计入 `skipped` 计数
  - `repo.upsert_many(rows, now=now)`；成功写 `SystemLog(OK, source="universe_refresher", "universe refreshed N rows (skipped=K)")`
  - 任何 screener 外部错误：不做 partial upsert（`get_screener_universe` 已保证"三次调用全通过才返回"）；异常被顶层 `run()` 捕获记 `ERROR` log 并返回 `status="error"`
- 返回 `@dataclass UniverseRefreshResult(status: "ok"|"error", upserted: int, skipped: int, error: str|None)`
- 源常量：`LOG_SOURCE = "universe_refresher"`

### 2. `MarketScannerService`（新文件）
- `LOG_SOURCE = "market_scanner"`
- `run_scan(scan_date: date | None = None) -> ScannerResult`
  - `scan_date` 默认 `datetime.now(timezone.utc).date()`；`scanned_at = datetime.now(timezone.utc)`
  - **冷启动**：`universe_repo.count() == 0` 时先触发 `UniverseRefreshService(self.db, self.fmp).refresh()`；refresh 失败直接返回 `status="error"`（不扫描）
  - `latest = universe_repo.latest_refresh_time()`；`active = universe_repo.list_active(since=latest)`（`last_seen_at >= latest` 把当次 refresh 命中的全部行取出，掉出的历史行不参与扫描 — D038）
  - 逐 ticker：
    - `payload = fmp.get_ma150_series_or_eod(ticker)` → `{source, bars}`
    - **首次**遇到 `source == "eod_fallback"`：整次扫描只写一条 `SystemLog(WARN, "market_scanner", "SMA endpoint unavailable, falling back to EOD")`（避免刷屏；后续相同 source 不重复写）
    - 按 `date` 升序排；`closes = [float(b["close"])]`；
      - `source == "sma"`：`ma_series = [float(b["sma"]) if b.get("sma") is not None else None for b in sorted_bars]`
      - `source == "eod_fallback"`：`ma_series = compute_ma150_series(closes)`（复用 F002）
    - 判定 breakout（D039 + feature acceptance）：
      - 至少 2 根 bar；`close_today`=最后一根，`close_prev`=倒数第二；`ma_today / ma_prev` 同理；任何 `None` → skip（不命中，非错误）
      - 规则全部满足才命中：
        1. `close_prev < ma_prev` 且 `close_today >= ma_today`（向上穿越）
        2. `pct_above = (close_today - ma_today) / ma_today * 100 <= 10.0`
        3. `slope = compute_slope([最后 20 个非 None ma_series 点]); slope > 0`
    - 命中：append 一条 `BreakoutScanRow(scan_date, ticker, company_name, close_today, ma_today, pct_above, slope, market_cap, scanned_at)`（`company_name / market_cap` 来自 universe 行）
    - 单 ticker 抛异常（FMP / 解析 / 计算）：记 `SystemLog(ERROR, "market_scanner", f"{ticker} scan failed: {exc}", detail=traceback)`，`failed += 1`，继续下一 ticker
  - **全失败保护（D040）**：若 `len(active) > 0` 且 `scanned_ok == 0 and failed > 0`（一只股票也没扫成功）→ **不调用 `replace_scan`**，保留旧快照；记 `ERROR` 汇总日志
  - 否则调 `breakout_repo.replace_scan(rows=hits)`（hits 可为空，表示"今日无命中"，覆盖旧快照为空）
  - 记 `SystemLog(OK, "market_scanner", f"scan complete: hits=N scanned={ok} failed={failed} fallback={bool(fallback_used)}")`
  - 返回 `ScannerResult(status, total: int, scanned: int, hits: int, failed: int, fallback_used: bool, scan_date, scanned_at)`

### 3. `refresh_job.py`（修改）
- 新增两个 job id：`ma150_market_scanner`、`ma150_universe_refresh`
- 两个新 tick 函数：`_scanner_tick(session_factory, fmp_factory)` / `_universe_tick(session_factory, fmp_factory)` — 结构仿 `_scheduler_tick`，顶层 try/except 记 `logger.error`（防御性；service 内部已写 SystemLog ERROR）
- 扩展 `start_scheduler(...)`：在同一个 `BackgroundScheduler` 内追加两个 `CronTrigger`：
  - Scanner：`CronTrigger(day_of_week="mon-fri", hour=settings.scanner_cron_hour, minute=settings.scanner_cron_minute, timezone="UTC")` — 工作日，对齐既有 watchlist refresh 的 mon-fri 语义
  - Universe：`CronTrigger(day=settings.universe_cron_day, hour=settings.universe_cron_hour, minute=settings.universe_cron_minute, timezone="UTC")` — 月度
- 保持既有 `SCHEDULER_JOB_ID` 与 `DAILY_REFRESH_CRON` 不变（不破坏 F003 测试）
- 不在 tick 内复用 `RefreshJobManager`（该 Manager 专门服务 watchlist refresh 的进度状态；scanner 内部 <90s 同步跑完即可，无需对外暴露进度）：直接在 tick 内开 session、构造 service、调 `run_scan()` / `refresh()`，顶层捕获异常

### 4. `backend/tests/conftest.py`（trivial edit）
- `FakeFMP` 追加：
  - `screener_universe_result: list[dict] = []`；`screener_universe_exc: Exception | None`；`screener_universe_calls: int`
  - `ma150_results: dict[str, dict]`（`{"AAPL": {"source": "sma", "bars": [...]}}`）；`ma150_exc: dict[str, Exception]`；`ma150_calls: list[str]`
  - 对应方法 `get_screener_universe(...)` / `get_ma150_series_or_eod(symbol)` 签名与 `FmpClient` 一致
- 保持既有字段不动，不影响其他测试

### 5. `backend/tests/test_universe_refresh_service.py`（新）
覆盖：
- `refresh_success_upserts_rows_and_logs_ok`：三只股票进入，计数正确，SystemLog OK 含 `upserted/skipped`
- `refresh_skips_invalid_rows`：包含缺 `symbol`、`marketCap=None`、`marketCap=字符串` 的行 → 跳过且计 skipped，合法行入库
- `refresh_fmp_failure_logs_error`：`fake_fmp.screener_universe_exc = RuntimeError("fmp down")` → 返回 `status="error"`，SystemLog ERROR 含异常消息，universe 表不新增行
- `refresh_upsert_idempotent`：两次 refresh 相同 ticker，行数不变，`market_cap` 覆盖为最新值（走 a1 repo 语义的冒烟）

### 6. `backend/tests/test_market_scanner_service.py`（新）
覆盖：
- `scan_cold_start_triggers_universe_refresh`：universe 表空 + fake_fmp 已装 screener 结果 + ma150 结果 → `run_scan` 结果 `status="ok"`；universe 表被填；`SystemLog` 至少含一条 `universe_refresher OK`
- `scan_cold_start_universe_failure_aborts`：universe 空、screener 抛异常 → `status="error"`，不调用 `get_ma150_series_or_eod`（断言 `fake_fmp.ma150_calls == []`），不写 breakout_scans
- `scan_happy_path_hits_breakout_rule_sma_source`：universe 两只（AAPL/MSFT）；AAPL 序列满足穿越（prev_close<prev_ma，today_close≥today_ma，pct≤10，slope>0）→ 命中；MSFT 收盘远高于 MA（pct=20%）→ 不命中；表中 1 行，`company_name / market_cap` 来自 universe
- `scan_rejects_pct_above_10_percent`：构造 pct=12% 的 SMA 序列 → 不命中
- `scan_rejects_negative_slope`：MA 序列单调下降（slope<0） → 不命中
- `scan_rejects_no_crossover`：`close_prev >= ma_prev` → 不命中
- `scan_eod_fallback_source_computes_ma_locally_and_logs_warn_once`：同一扫描内两只 ticker 都是 eod_fallback → 只一条 WARN SystemLog；MA150 通过本地算（构造 ≥150 根 bar 的序列）命中
- `scan_per_ticker_failure_isolated`：MSFT 抛异常 → SystemLog ERROR 含 ticker + 异常消息；AAPL 命中仍写入；`failed=1, scanned=1, hits=1`
- `scan_total_failure_preserves_old_snapshot`：先 seed 一次旧快照（3 行）；再安排所有 universe ticker 均 raise → 不触发 `replace_scan`（旧 3 行保留）；返回 `status="error"` 或带 `failed=N, hits=0` 的完成态（以实现为准，断言旧快照 row 数 == 3）
- `scan_empty_hits_still_overwrites`：所有 ticker 成功但均不满足条件 → `replace_scan([])` 被调用，旧快照被清空（若先 seed 过旧快照则断言 count==0）
- `scan_uses_universe_row_company_and_market_cap`：universe 中 `company_name="Apple Inc."`、`market_cap=3e12` → 命中行字段与 universe 一致（不信任 fmp bars 里的 company 信息）
- `scan_refresh_job_registers_scanner_and_universe_jobs`：调 `start_scheduler(..., autostart=False)` → `sched.get_job("ma150_market_scanner")` / `get_job("ma150_universe_refresh")` 均存在；trigger 字段与 settings 一致；既有 `ma150_daily_refresh` 仍在

---

## 明确排除（不在本 Sprint）
- `GET /api/market/breakouts` router / schema / schema 测试（F105-a4）
- `GET /api/stocks/:ticker/chart` on-demand fallback（F105-b）
- 前端 MarketBreakoutWidget（F105-c）
- `ScannerResult` 的 HTTP 响应包装（留到 a4 router 层）
- 扫描并发优化（token bucket 已足够，不拆线程池）
- 调度失败告警通道（SystemLog 已足以 v1.2 需求）

---

## 预计修改文件（共 6 个，含 1 个 trivial 测试 fixture 扩展）

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/services/universe_refresh_service.py` | 新增 | `UniverseRefreshService` + `UniverseRefreshResult` + `LOG_SOURCE` |
| 2 | `backend/app/services/market_scanner_service.py` | 新增 | `MarketScannerService` + `ScannerResult` + 纯函数 `_build_ma_series / _detect_breakout` |
| 3 | `backend/app/services/refresh_job.py` | 修改 | 追加 2 个 CronTrigger + 2 个 tick 函数；既有 daily refresh 不动 |
| 4 | `backend/tests/conftest.py` | 修改（trivial） | `FakeFMP` 追加 2 字段 + 2 方法（screener / ma150） |
| 5 | `backend/tests/test_universe_refresh_service.py` | 新增 | 4 条用例 |
| 6 | `backend/tests/test_market_scanner_service.py` | 新增 | 12 条用例（含 cron 注册） |

👤 用户确认后进入开发。

---

## 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `UniverseRefreshService.refresh` 调用 `fmp.get_screener_universe` 一次，结果 upsert 到 `market_scan_universe`；写 OK SystemLog | 单元 | pytest + FakeFMP + db_session |
| 2 | 跳过无效行（缺 symbol / marketCap 非法），不中断；`skipped` 计数正确 | 单元 | pytest |
| 3 | screener 抛异常 → service 捕获，记 ERROR SystemLog，返回 `status="error"`；universe 表无新增 | 单元 | pytest |
| 4 | `MarketScannerService.run_scan` universe 表空时先 refresh；成功后继续扫描 | 单元 | pytest |
| 5 | universe refresh 失败 → 扫描直接中止，`get_ma150_series_or_eod` 未被调用 | 单元 | pytest |
| 6 | Breakout 判定全规则（穿越 + pct≤10 + slope>0）正确；任一违反不命中 | 单元 | pytest（4 个 reject 用例） |
| 7 | SMA source 直接用 FMP 的 `sma` 字段；EOD fallback source 用 `compute_ma150_series` 本地算 | 单元 | pytest |
| 8 | 同次扫描内 `eod_fallback` 只记一条 WARN（去重） | 单元 | pytest |
| 9 | 单 ticker 失败不影响其他 ticker；记录 ERROR SystemLog | 单元 | pytest |
| 10 | 全部 ticker 失败（≥1 且 scanned_ok=0）→ 保留旧快照（不调 `replace_scan`） | 单元 | pytest |
| 11 | 全部成功但无命中 → 仍调 `replace_scan([])` 覆盖旧快照为空 | 单元 | pytest |
| 12 | `BreakoutScanRow.company_name / market_cap` 来自 universe 表，不信任 FMP bars 数据 | 单元 | pytest |
| 13 | `start_scheduler` 注册 `ma150_market_scanner`（工作日）+ `ma150_universe_refresh`（月度），既有 `ma150_daily_refresh` 保留 | 单元 | pytest（autostart=False 后 `sched.get_job`） |
| 14 | `pytest backend/tests/` 全量回归全绿（F001–F105-a2 无回归） | 集成 | pytest |
| 15 | `mypy backend/app/services/` 严格通过（新增两服务文件无类型错误） | 静态 | mypy（项目既有标准） |

---

## Evaluator 自检清单

- [ ] `pytest backend/tests/test_universe_refresh_service.py` 全绿（4 条）
- [ ] `pytest backend/tests/test_market_scanner_service.py` 全绿（12 条）
- [ ] `pytest backend/tests/` 全量回归全绿（F001–F105-a2）
- [ ] `mypy backend/app/services/universe_refresh_service.py backend/app/services/market_scanner_service.py backend/app/services/refresh_job.py` 严格通过
- [ ] `MarketScannerService.run_scan` 单函数 ≤ 50 行（否则拆内部 helper）
- [ ] 无硬编码魔法值：`50_000_000_000`（universe 阈值）/ `10.0`（pct 上限）/ `20`（slope 窗口） 均来自参数默认或 signal_engine 既有常量；不重复定义
- [ ] 所有外部调用的 per-ticker 异常被 `except Exception` 捕获并写 SystemLog，不让单只股票失败冒泡
- [ ] `replace_scan` 只在至少有一只股票 scan 成功（scanned_ok > 0）或 active universe 为空时才调用（D040 防清空）
- [ ] `SystemLog.source` 严格使用 `"market_scanner"` / `"universe_refresher"` 常量（无拼写漂移）
- [ ] `refresh_job.py` 既有 `DAILY_REFRESH_CRON` / `SCHEDULER_JOB_ID` / `manager` 对外签名无改动（`market_refresh.py` 的两条 wiring 测试继续通过）
- [ ] `start_scheduler` 对同一 sched 调用两次仍返回原实例（幂等语义未破坏）
- [ ] `features.json` F105.subtasks.F105-a3.phase 流转 `contract_agreed → in_progress → testing → needs_review`
- [ ] claude-progress.txt 追加 F105-a3 完成记录
- [ ] DECISIONS.md 无需新增条目（本 Sprint 执行 D038/D039/D040/D042）

### 代码质量检查
- [ ] Lint：项目未配 linter，以 mypy + pytest 为准
- [ ] 无死代码 / 无 print / 无未捕获 await
- [ ] 无重复代码（breakout 检测逻辑单一出口；per-ticker 循环只写一次）
- [ ] 单函数 ≤ 50 行；超过立即拆私有 helper

### 回归测试
- 当前 feature 全绿后运行 `pytest backend/tests/` 全量
- 新增失败若由 a3 引入 → 打回 Generator；预先存在则标注并上报用户

---

👤 确认此 Contract 后开始开发。
