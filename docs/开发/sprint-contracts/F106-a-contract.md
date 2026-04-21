# Sprint Contract：F106-a 多信号扫描核心（后端）

> 日期：2026-04-21 | 状态：**反向补契约**（代码已写未 commit，Contract 作为 Evaluator 度量尺）
> 依赖：F105-a5 ✅ done（FMP 共享限流器、ThreadPool 扫描、MarketScannerService 骨架）
> 引用文档：
>   DATA-MODEL.md#marketbreakoutscan（已为 F106 扩展 signal_type / volume / volume_ratio_20、唯一键改 scan_date+ticker+signal_type）
>   DECISIONS.md#D045（F106 单表多 signal_type 数据模型）
>   docs/需求/SIGNAL-CATALOG.md（A1/A2/B2 规则语义，P0 范围）
>   docs/需求/features.json#F106（9 条 acceptance_criteria）

---

## 本次实现范围（Sprint A：核心计算层）

### 1. `backend/app/services/scanner_params.py`（新建）
- 集中声明所有阈值 / 窗口 / 信号类型常量
- 信号类型枚举：`SIGNAL_LEGACY_CROSSOVER / SIGNAL_A1_STAGE_BREAKOUT / SIGNAL_A2_SLOPE_FLIP / SIGNAL_B2_MA_PULLBACK`
- `ALL_SIGNAL_TYPES` 四元组、`DEFAULT_API_SIGNAL_TYPES`（legacy 不默认返回）
- 共享：`FETCH_WINDOW_CALENDAR_DAYS = 90`、`SCAN_WORKER_COUNT = 6`
- A1：`A1_HORIZONTAL_WINDOW_DAYS=60 / A1_HORIZONTAL_RANGE_PCT=5.0 / A1_VOLUME_RATIO_MIN=1.5 / A1_VOLUME_AVG_WINDOW=20 / A1_REQUIRE_SLOPE_NONNEGATIVE=True`
- A2：`A2_FLIP_LOOKBACK_DAYS=30`（斜率窗口复用 `signal_engine.SLOPE_WINDOW=20`）
- B2：`B2_MA_SHORT_WINDOW=5 / B2_PROXIMITY_PCT=2.0 / B2_EXPANSION_DELTA_PCT=0.5 / B2_LOOKBACK_DAYS=10`
- Legacy：`LEGACY_PCT_ABOVE_MA_LIMIT=10.0`

### 2. `backend/app/services/market_scanner_service.py`（修改）
- `_evaluate_breakout` 拆分为 `_evaluate_all_rules(ctx) -> list[BreakoutScanRow]`；一次 FMP 调用内对同一 bar 序列并行跑 4 条规则，每命中产出一行
- 抽 `_BarCtx` dataclass（不可变）：预计算 `closes / volumes / ma_series / ma5_series / slope_today / pct_above_today / volume_ratio_today`，4 个 detector 共享
- 4 个独立 detector 函数：
  - `_detect_legacy_crossover(ctx) -> BreakoutScanRow | None`：保留原 F105 规则（prev_close<prev_ma / close≥ma / pct≤10 / slope>0）
  - `_detect_a1_stage_breakout(ctx)`：MA150 过去 60 日 max/min 比≤5% + 今日首次上穿 + 今日 vol ≥ 20 日均量 × 1.5 + slope≥0
  - `_detect_a2_slope_flip(ctx)`：今日 slope>0 且近 30 日内曾存在某日 slope≤0 + close>MA150
  - `_detect_b2_ma_pullback(ctx)`：slope>0 + 近 10 日内 min((MA5-MA150)/MA150)≤2% + 今日 gap ≥ min+0.5% + MA5>MA150
- `ScannerResult` 追加 `hits_by_type: dict[str, int]`，结束日志按 signal_type 分列
- `SCAN_WORKER_COUNT` / `PCT_ABOVE_MA_LIMIT` 移除本地常量，改读 `scanner_params`
- 每 ticker 的 `hits_for_ticker` 列表替换单 hit 返回；`hits.extend(...)` 聚合
- 失败隔离语义（D040）不变：所有 ticker 都失败 → 不清空旧快照

### 3. `backend/app/models/market_breakout_scan.py`（修改）
- 字段追加：`signal_type: Mapped[str]`（不可空，默认值仅用于迁移回填）、`volume: Mapped[int | None]`、`volume_ratio_20: Mapped[float | None]`
- 唯一键从 `(scan_date, ticker)` 改为 `(scan_date, ticker, signal_type)`
- 索引保留 `(scan_date,)` 以支持"按 scan_date 取最新快照"

### 4. `backend/app/repositories/market_breakout_repository.py`（修改）
- `replace_scan(rows)` 支持多 signal_type 并存；overwrite 语义按 `scan_date` 单位（仍 delete by scan_date → insert）
- 新增 `list_by_scan_date(scan_date, signal_types: Iterable[str] | None)`：按 signal_type 过滤，None 表示全取
- `latest_scan_date()` 行为不变（取 max）

### 5. `backend/alembic/versions/003_f106_signal_type_and_volume.py`（新建）
- upgrade：
  1. ALTER TABLE `market_breakout_scans` 加 `signal_type TEXT NOT NULL DEFAULT 'legacy_crossover'`、`volume INTEGER NULL`、`volume_ratio_20 REAL NULL`
  2. DROP 旧 UNIQUE `(scan_date, ticker)`，CREATE 新 UNIQUE `(scan_date, ticker, signal_type)`（SQLite 用 batch_alter_table）
  3. 既有数据全部回填为 `legacy_crossover`（通过 server_default 完成）
- downgrade：反向移除新增字段 + 还原唯一键

---

## 明确排除（归 F106-b / F106-c）

- 路由层改造 `GET /api/market/breakouts` `?type=` 参数（→ F106-b）
- schemas 追加字段（→ F106-b）
- fmp_client `get_ma150_series_or_eod` 的 SMA 窗口扩大、volume 字段取回（→ F106-b）
- 前端任何改动（→ F106-c）

---

## 预计修改文件（共 5 个）

| # | 文件 | 类型 | 改动 |
|---|---|---|---|
| 1 | `backend/app/services/scanner_params.py` | 新建 | 全部阈值 + 信号类型常量 |
| 2 | `backend/app/services/market_scanner_service.py` | 修改 | 4 条 detector + `_BarCtx` + hits_by_type |
| 3 | `backend/app/models/market_breakout_scan.py` | 修改 | 加 3 字段 + 改唯一键 |
| 4 | `backend/app/repositories/market_breakout_repository.py` | 修改 | `list_by_scan_date` + `replace_scan` 兼容 |
| 5 | `backend/alembic/versions/003_f106_signal_type_and_volume.py` | 新建 | schema 迁移 |

---

## 可测试的完成标准

| # | 标准 | 层级 |
|---|---|---|
| 1 | 单次扫描对每个 ticker 评估 4 条规则，FMP 调用次数不变（仍 1 次/ticker）| 集成 |
| 2 | 同一 ticker 同一 scan_date 可产生多条记录，signal_type 各异；唯一键 `(scan_date, ticker, signal_type)` | 集成 |
| 3 | A1 detector：mock bars 满足"60 日 MA150 flat + 今日首次上穿 + vol×1.5" → 返回 a1 hit；缺任一条件 → None | 单元 |
| 4 | A2 detector：mock "过去 30 日存在 slope≤0 + 今日 slope>0 + close>MA150" → 返回 a2 hit | 单元 |
| 5 | B2 detector：mock "slope>0 + 10 日内 MA5-MA150 贴近≤2% + 今日反弹+0.5%" → 返回 b2 hit | 单元 |
| 6 | Legacy detector：F105 原 3 条既有测试仍绿（pct≤10 / 斜率>0 / 上穿）| 回归 |
| 7 | `hits_by_type` 聚合准确：4 个 signal 命中数与 `ScannerResult.hits` 总数对齐 | 单元 |
| 8 | Alembic `upgrade head` → 老数据全部回填为 `legacy_crossover`，新唯一键生效 | 集成 |
| 9 | Alembic `downgrade -1` 可回滚 | 集成 |
| 10 | 所有阈值改动只需改 `scanner_params.py`，不需动 detector 代码 | 手工检查 |
| 11 | `pytest backend/tests/` 全量回归全绿 | 集成 |

---

## Evaluator 自检清单

- [ ] `pytest backend/tests/test_market_scanner_service.py` 全绿（含 4 条规则新增用例）
- [ ] 每个 detector 至少 2 条 unit test（正向命中 + 边界 miss）
- [ ] `pytest backend/tests/` 全量回归全绿
- [ ] `alembic upgrade head` 对空库、对 v1.2.0 存量数据均成功；`alembic downgrade -1` 成功
- [ ] `_BarCtx` 为不可变 dataclass；所有 detector 不产生副作用
- [ ] `scanner_params` 所有常量有单元或类型注解，命名清晰
- [ ] 无硬编码阈值残留（grep `1.5 / 2.0 / 60 / 30 / 10 / 20 / 5.0` 在 `market_scanner_service.py` 中只出现在对 `scanner_params` 的引用）
- [ ] features.json `F106.phase` 流转 `contract_agreed → in_progress → testing → needs_review`
- [ ] claude-progress.txt 追加 F106-a 完成记录
- [ ] DECISIONS.md 已含 D045（F106 数据模型），无需新增

### 代码质量检查
- [ ] 无死代码 / 无 print
- [ ] 每个 detector ≤ 50 行
- [ ] 4 detector 共用 `_BarCtx`，不重复计算 MA5 / slope
- [ ] 异常处理：ticker 级异常隔离（既有 D040 语义）保持

### 回归测试
- 当前 feature 绿后跑 `pytest backend/tests/`
- 新增失败若由 F106-a 引入 → 打回 Generator

---

⚠️ **反向补契约特殊说明**
本 Contract 在代码已落地后补写。Evaluator 阶段的核心任务是**补齐测试覆盖**（现有 `test_market_scanner_service.py` 0 处 F106 断言），而非从零实现。测试写完后若暴露代码缺陷，按常规打回 Generator 修复。
