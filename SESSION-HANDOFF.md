# Session 交接文档

**生成时间**：2026-05-15
**当前 Skill**：feature-dev (类型 A 主流程)
**完成进度**：F217-a 全部步骤完成 → phase=needs_review；待 consistency-check 后用户验收
**Sprint Contract**：[docs/开发/sprint-contracts/F217-a-contract.md](docs/开发/sprint-contracts/F217-a-contract.md)

---

## 项目背景

- **项目**：MA150 Tracker → Workbench → Cockpit
- **当前迭代**：v2.3（cockpit-vs-srs-framework 改善计划 Phase C：Capitulation Reversal 严格重写）
- **已发布**：v2.2.0（Phase B / F216 Weekly Stage Layer，2026-05-15 已发版）
- **本次目标**：F217 Phase C — 把 cockpit setup_service 的 SETUP_PULLBACK 近似（回踩 MA21）替换为 SRS § 五 Setup 4 严格定义的 SETUP_CAPITULATION（投降式抛售反转，7 条 AND 门）

---

## 当前状态：F217-a 已完成 → needs_review

### 完成的文件（6 个，命中 6 文件上限）

| # | 文件 | 变更 |
|---|------|------|
| 1 | `backend/app/services/cockpit/_indicators.py` | 新建；纯函数 `compute_wilder_atr(highs, lows, closes, period) -> list[float]` |
| 2 | `backend/app/services/cockpit/chart_service.py` | `_compute_atr_series` 委托 `compute_wilder_atr`（行为不变） |
| 3 | `backend/app/services/cockpit/cockpit_params.py` | 删 4 个 `PULLBACK_*` 字段；新增 10 个 `CAPITULATION_*` 字段；REGIME preferredSetups PULLBACK→CAPITULATION |
| 4 | `backend/app/services/cockpit/setup_service.py` | 实现 7 AND 门 `_is_capitulation_reversal`；删 `_is_pullback`；优先级 BROKEN→EXTENDED→EARNINGS_DRIFT→CAPITULATION→BREAKOUT→RECLAIM→NONE |
| 5 | `backend/tests/test_capitulation_reversal.py` | 新建；34 tests（T1-T14 全通过） |
| 6 | `backend/tests/test_setup_f202a.py` | `test_s4` fixture、`test_s15` 语义修正（PULLBACK→NONE） |

### 测试结果

- `ruff check`：0 errors（5 个目标文件）
- 全量回归：**1084 passed，7 failed（全部 pre-existing，0 新增）**
  - pre-existing failures（与 F217-a 无关）：
    - `test_ai_schemas_f209.py::TestEndpointIntegration::test_D1_market_narrator_success`
    - `test_ai_schemas_f211a1.py::TestRegistry::test_R5_contradiction_detector_resolves_default`
    - `test_ai_schemas_f211a1.py::TestRegistry::test_R6_news_summarizer_resolves_default`
    - `test_fmp_client.py::test_get_screener_universe_merges_three_exchanges_and_dedupes`
    - `test_regime_f201a.py::test_s14_cockpit_params_import_no_exception`（SHARED.INDEX_ETFS 4 vs 3，F216 引入）
    - `test_regime_f201b.py::TestRegimeApiEndpoint::test_s4_indices_has_exactly_3_items`（同上）
    - `test_schema.py::test_all_tables_created`（weekly_stage_snapshots 未加 EXPECTED_TABLES，F216-b 引入）

### 7 AND 门实现

| Gate | 说明 | 参数 |
|------|------|------|
| G1 | 5-10 日累计 close 跌幅 ≥ 10% | `CAPITULATION_DROP_LOOKBACK_MIN_DAYS=5`, `_MAX_DAYS=10`, `_DROP_PCT=10.0` |
| G2 | Volume z-score ≥ 2.5（复用 F215-b `_compute_volume_zscore`） | `CAPITULATION_VOL_Z_MIN=2.5` |
| G3 | TR ≥ ATR14 × 2.0 | `CAPITULATION_ATR_TR_MULTIPLIER=2.0` |
| G4 | close 位于当日 high-low 上 1/3（≥ 0.667） | `CAPITULATION_CLOSE_UPPER_BIN=0.333` |
| G5 | （NP2 设计：lookahead-safe，bar[-1]=今日，始终跳过） | `CAPITULATION_NO_NEW_LOW_LOOKAHEAD_DAYS=2` |
| G6 | today.low > 30 日内倒数第 2 个 swing low | `CAPITULATION_SWING_LOW_LOOKBACK=30` |
| G7 | RS line（close/SPY close）过去 5 日未创新低 | `CAPITULATION_RS_NO_NEW_LOW_DAYS=5` |

---

## 下一步任务

### F217-b：DB 枚举迁移（当前 phase=design_needed）

**核心工作**：
1. `alembic` migration 021：`setup_snapshots.setup_type` 枚举去 `PULLBACK` 加 `CAPITULATION`（前向 + 回滚均可执行）
2. `SetupSnapshotRepository.purge_legacy_pullback()` 方法：历史 `PULLBACK` 行软删（加 `legacy=True` 标记）或硬删
3. `SetupSnapshot` model `setup_type` 字段类型与新枚举一致
4. Integration tests：insert PULLBACK → call purge → assert 行被标记/移除
5. 预估文件：3-4 个

**依赖**：F217-a（已 done）→ F217-b 现在可进行 Sprint Contract 协商

### F217-c：前端 CAPITULATION badge（当前 phase=design_needed）

**核心工作**：
1. `cockpitDecisionApi.SetupType` 类型去 `PULLBACK` 加 `CAPITULATION`
2. `DecisionPanelWidget`：setupType=CAPITULATION 时展示 3 个 chip（Vol z-score / Drop 5d / Reversal day）
3. `SetupMonitorWidget`：CAPITULATION 紫色 badge（design-spec.md 需补 token #a78bfa）

**依赖**：F217-a + F217-b 完成后方可进行

---

## 未决事项

- F217-b Sprint Contract 待协商（建议新 session 开始）
- design-spec.md §Widget 5 紫色 badge token 待 F217-c Sprint Contract 确认
- F217 parent phase 升级（needs F217-a + F217-b + F217-c 全 done）

---

## 恢复指令（下一 session）

**若继续 F217-b Sprint Contract**：
```
读取 SESSION-HANDOFF.md + docs/需求/features.json（F217 条目）+ docs/系统设计/DATA-MODEL.md（SetupSnapshot 枚举）。
F217-a 已完成（needs_review），开始 F217-b Sprint Contract 协商。
参考 API-CONTRACT.md + DECISIONS.md §D095。
```

**若先做 F217-a consistency-check（如尚未完成）**：
```
调用 consistency-check skill，mode=interactive，检查 F217-a sub_sprint 一致性。
```
