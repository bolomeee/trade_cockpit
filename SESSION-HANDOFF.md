# SESSION-HANDOFF — F218-d5 ✅ done → 下一步 F218-d6a contract 协商

> 生成：2026-05-20 (Sonnet 4.6) | 用途：下一 session 进入 F218-d6a contract 协商

---

## 1. 当前状态

| 字段 | 值 |
|------|-----|
| `_pipeline_status.active_sprint` | **F218-d6a** |
| `_pipeline_status.active_sprint_phase` | **design_needed** |
| `F218.phase` | in_progress |
| `F218.sub_sprints["F218-d5"]` | **done** |
| `F218.sub_sprints["F218-d6a"]` | design_needed |
| 前置依赖 | F218-d1/d2/d3a/d3b/d4/d5 全部 done |

---

## 2. F218-d5 完成摘要

**已实装（3 文件，3 wip + 1 feat commits）**：

| 文件 | 改动 |
|------|------|
| `backend/app/services/cockpit/cockpit_params.py` | `CockpitSharedParams` 新增 `SECTOR_TO_ETF: dict[str, str]`（11 项，FMP Title Case → XL* ETF） |
| `backend/app/services/cockpit/repricing_trigger_service.py` | +imports / +T4 常量段 7 行（含 `T4_SMA_FETCH_DAYS=280`）/ `_detect_sector_cycle` 55 行实装 / 4 helpers / 模块级 `_close_on_or_before` |
| `backend/tests/test_repricing_trigger_sector_cycle.py` | 新建：10 测试 / 3 class（S1-S10）全绿 |

**关键实施偏差（已修正）**：
- Contract 伪码 `earliest = scan_date - 120`（RS lookback）与 NP-d5-9 "≈280 calendar days"（SMA200）不一致。实际用 `T4_SMA_FETCH_DAYS=280`，向正确方向修正。

**测试结果**：
- 新增 10 tests：10/10 ✅
- d1-d5 回归（75 tests）：75/75 ✅
- 全量后端：9 pre-existing failures（与 d4 baseline 一致），无新增 ✅

**consistency-check (mode=interactive)**：severe=0 medium=0 minor=0，全清 ✅

---

## 3. F218 整体进度（10 sub-sprint）

| Sub-sprint | 状态 | 说明 |
|------------|------|------|
| F218-d1 | ✅ done | 框架（service skeleton + repricing_triggers 表 + 5 占位）|
| F218-d2 | ✅ done | T1 EARNINGS_ACCEL detector |
| F218-d3a | ✅ done | T2 数据层（income-statement + key_metrics 表 + pool_cache）|
| F218-d3b | ✅ done | T2 MARGIN_EXPANSION detector |
| F218-d4 | ✅ done | T3 NEW_PRODUCT detector（D4a 关键词扫描）|
| F218-d5 | ✅ done | T4 SECTOR_CYCLE detector（RS rotation + SMA200 gate）|
| **F218-d6a** | 🟡 **design_needed** | **T5 数据层（balance-sheet + cash-flow + fundamentals 表 + pool_cache）— 下一步** |
| F218-d6b | ⬜ design_needed | T5 BALANCE_INFLECTION detector |
| F218-d7a | ⬜ design_needed | cron + router + 2 endpoint |
| F218-d7b | ⬜ design_needed | 前端 widget + DecisionPanel badge + 内联 design-spec 4 文档 |

---

## 4. 下一步：F218-d6a Contract 协商

**范围**：T5 数据层 plumbing（不含 detector，detector 留给 d6b）

参考 d3a 模式（T2 数据层），d6a 预期包含：
- FMP `/balance-sheet-statement?period=quarter` + `/cash-flow-statement?period=quarter` client 方法（d3a 分别 fail-open）
- `stock_fundamentals_quarterly` 表（model + alembic 024）— DATA-MODEL §FundamentalsQuarterly
- `FundamentalsRepository`（null-not-erase upsert）
- `compute_fundamentals_row_from_balance_cash` 纯函数（pool_helpers.py 追加）
- `PoolCacheService.rebuild()` 末尾追加 `_rebuild_fundamentals` 步骤
- 预估 6-7 文件（参考 d3a 7 文件超额授权模式）

**⚠️ 协商前必读**：
- `DATA-MODEL.md` §StockFundamentalsQuarterly（字段权威）
- `DECISIONS.md` §D097（FMP endpoint 修正记录：/stable/balance-sheet-statement + /stable/cash-flow-statement，与 income-statement 同用 Starter tier；已确认 ~150 calls/week）
- `ARCHITECTURE.md` §Cockpit Repricing Trigger Service（T5 数据获取端点描述）
- d3a Sprint Contract（模板参考）：`docs/开发/sprint-contracts/F218-d3a-contract.md`

---

## 5. 下一 Session 恢复指令

**复制以下指令到新 session（建议 Sonnet 4.6）**：

```
继续开发 F218，当前活跃 sprint 是 F218-d6a（design_needed）。
读取 SESSION-HANDOFF.md，进入 feature-dev skill，
协商 F218-d6a Sprint Contract（T5 数据层：balance-sheet + cash-flow + fundamentals 表 + pool_cache）。
```

---

## 6. 未决事项

无。F218-d5 全部决策（NP-d5-1~10）已实装，无遗留待决。
