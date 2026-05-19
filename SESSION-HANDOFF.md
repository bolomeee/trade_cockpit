# SESSION-HANDOFF — F218-d3b Sprint Contract ✅ confirmed → 下一步 Generator 模式开发

> 生成：2026-05-19 (Opus 4.7) | 用途：下一 session 进入 F218-d3b Generator 模式（建议切 Sonnet 4.6）
> Skill 链：feature-dev A-1 Contract（F218-d3b ✅ 本 session 协商通过） → **本 handoff** → feature-dev A-2 Generator

---

## 1. 当前状态快照

**Feature**：F218 Cockpit Phase D — Repricing Trigger 完整框架（5 类）
**Sub-sprint**：F218-d3b — T2 MARGIN_EXPANSION detector 实装（10 个 sub-sprint 第 6 个）
**Phase**：`contract_agreed` ✅
**Active sprint**（features.json `_pipeline_status`）：`F218-d3b`
**Sprint Contract**：[docs/开发/sprint-contracts/F218-d3b-contract.md](docs/开发/sprint-contracts/F218-d3b-contract.md) — `status: confirmed` (2026-05-19)
**8 项关键决策**：NP-d3b-1 ~ NP-d3b-8 全部按推荐确认

**Sub-sprint 进度**：
- F218-d1: ✅ done（service skeleton + 5 占位）
- F218-d2: ✅ done（T1 EARNINGS_ACCEL 实装）
- F218-d3a: ✅ done（T2 数据层 — income-statement + key_metrics 表 + pool_cache 集成）
- **F218-d3b: 🟡 contract_agreed**（T2 detector 实装 — 本 sprint）
- F218-d4 ~ F218-d7b: ⬜ design_needed（6 个待开发）

---

## 2. Sprint Contract 摘要

### 实现范围（2 文件，远低于 6 文件上限）

| # | 文件 | 改动 |
|---|------|------|
| 1 | `backend/app/services/cockpit/repricing_trigger_service.py` | 修改：import KeyMetricsRepository / `__init__` 注入 `self._key_metrics` / 新增 T2 常量段 6 行 / 替换 `_detect_margin_expansion` 实装 / 新增 2 个模块级 helpers (`_eval_margin_arm`、`_round_or_none`) |
| 2 | `backend/tests/test_repricing_trigger_margin_expansion.py` | 新建:10 测试 / 3 class（TestEvalMarginArm ×3 / TestDetectMarginExpansion ×6 / TestMarginExpansionEndToEnd ×1）|

### T2 触发语义（DATA-MODEL.md §1098/§1159 + D096/D097）

- 读最近 ≥ 6 季 `stock_key_metrics_quarterly`（按 period_end_date DESC），不足 6 行 → return None
- **Gross 臂**：(Q0.gross_margin − Q-4.gross_margin) ≥ **200bp** AND (Q-1.gross_margin − Q-5.gross_margin) ≥ **200bp**
- **FCF 臂**：双 YoY 都 ≥ **300bp**（d3b 期间 fcf_margin 全 NULL → 永不命中；d6a 上线后零修改激活）
- 任一字段 None → 跳过该臂（不抛错）；两臂全空 → return None
- 两臂同命中 → `trigger_metric=gross_margin`（D096 偏好）
- confidence：触发臂 Q0 YoY ≥ **400bp** → 0.8；否则 0.5

### evidence_json schema（最终落地版）

```json
{
  "gross_margin_trend": [0.42, 0.44, 0.46],
  "fcf_margin_trend":   [null, null, null],
  "quarters":           ["2025Q3", "2025Q4", "2026Q1"],
  "trigger_metric":     "gross_margin",
  "expansion_bp":       400
}
```

`gross_margin_trend` = [Q-2, Q-1, Q0] 绝对 margin；`fcf_margin_trend` 在 d3b 期间永远全 None。

---

## 3. 开发顺序（Generator 模式 4 步，不得跳步、不得颠倒）

### Step 1：T2 常量段 + helpers + KeyMetricsRepository 注入
位置：`backend/app/services/cockpit/repricing_trigger_service.py`
- 顶部 import 段追加 `from app.repositories.key_metrics_repository import KeyMetricsRepository`
- `T1_DEFAULT_CONFIDENCE = 0.5` 之后空一行追加 T2 常量段（6 个常量，前缀 `T2_*`）
- `RepricingTriggerService.__init__` 末尾追加 `self._key_metrics = KeyMetricsRepository(db)`
- 文件末尾紧跟 `_quarter_label` 追加 2 个模块级函数 `_eval_margin_arm` 与 `_round_or_none`
- 最小验证：`uv run python -c "from app.services.cockpit.repricing_trigger_service import _eval_margin_arm, _round_or_none, T2_GROSS_THRESHOLD_BP"`
- WIP commit: `wip(F218-d3b): T2 constants + helpers + KeyMetricsRepo injection`

### Step 2：替换 `_detect_margin_expansion` 实装
位置：同 `repricing_trigger_service.py`
- 删除 `return None` 占位
- 按 Contract §1.1.4 伪码完整实装（~30 行）：read 6 rows → 双臂 eval → trigger_metric / expansion_bp / confidence 计算 → 构造 evidence dict → 返回 DetectorResult
- 不动其他 4 个占位 detector
- 最小验证：`uv run pytest tests/test_repricing_trigger_skeleton.py tests/test_repricing_trigger_earnings_accel.py -v`（d1+d2 既有测试仍全绿）
- WIP commit: `wip(F218-d3b): _detect_margin_expansion implementation`

### Step 3：编写 10 个测试
位置：`backend/tests/test_repricing_trigger_margin_expansion.py`（新建）
- 3 class 分组：
  - `TestEvalMarginArm`：M1–M3（辅助函数 happy / 未过阈 / None 字段参数化）
  - `TestDetectMarginExpansion`：M4–M9（gross 低置信 / gross 高置信 / fcf 单臂 / 两臂同命中 gross 优先 / 单季 YoY 不过 / 三场景 return None 参数化）
  - `TestMarginExpansionEndToEnd`：M10（service `compute_and_store_all_triggers` upsert + soft expire）
- M4 内嵌 M11 evidence_json 5 键结构断言
- Helpers：`_km(db, ...)` 直接 INSERT；`_insert_6_seasons_for_t2(db, ticker, gross_series, fcf_series=None)`；复用 d2 的 `_stock`
- 最小验证：`uv run pytest tests/test_repricing_trigger_margin_expansion.py -v` 全绿
- WIP commit: `wip(F218-d3b): T2 detector tests (10/10 pass)`

### Step 4：Evaluator 自检 + 回归 + 收尾 commit
- 逐条勾选 Contract §4 自检清单（含代码质量 4 项）
- 全量后端回归：`cd backend && uv run pytest` — 允许 9 个 pre-existing failures，**不得新增**
- 通过后调用 **consistency-check skill (mode=interactive)** 校验 C1/C4/C5（铁律 2：F218-d3b 升 done 后不得自动把父 F218 升 done — sibling 还有 7 个未 done）
- 更新 features.json：sub_sprints.F218-d3b → done；iteration_history 追加 done 条目
- 更新 claude-progress.txt
- 最终 commit（squash wip 可选，默认保留细粒度）: `feat(F218-d3b): T2 MARGIN_EXPANSION detector implementation`

---

## 4. 强制约束（Generator 模式）

- ⚠️ **禁用 `git add -A`** — 按 Contract §2 文件清单显式 add（2 文件）
- ⚠️ **铁律 2**：sub_sprint 升 done 时**不得**直接把 F218 父 feature 升 done；父 status 由 consistency-check C1 invariant 自动决定（sibling 全 done 才升）
- ⚠️ **测试门禁**：phase 不得从 `in_progress` 跳过 `testing` 直接到 `needs_review`
- ⚠️ **不动**任何系统设计文档（ARCHITECTURE / DATA-MODEL / API-CONTRACT / DECISIONS 已 confirmed @ 2026-05-18，本 sprint 严格落地，无新增 drift）
- ⚠️ **不动**任何前端文件（widget / API client / design-spec / tokens — 全部 d7b 范围）
- ⚠️ **不接** FMP cash-flow / balance-sheet endpoint（d6a 范围）

---

## 5. 引用文档（开发时必查）

- [Sprint Contract](docs/开发/sprint-contracts/F218-d3b-contract.md) — 本 sprint 唯一权威
- [DATA-MODEL.md §RepricingTrigger 1080–1129](docs/系统设计/DATA-MODEL.md) — evidence_json schema / confidence 规则
- [DATA-MODEL.md §StockKeyMetricsQuarterly 1132–1183](docs/系统设计/DATA-MODEL.md) — detector 读取契约 §1159
- [DECISIONS.md D096/D097](docs/系统设计/DECISIONS.md)
- [F218-d2-contract.md](docs/开发/sprint-contracts/F218-d2-contract.md) — T1 实装样板（YoY 计算 / quarter label / fail-out 模式）
- [F218-d3a-contract.md](docs/开发/sprint-contracts/F218-d3a-contract.md) — 数据层契约（fiscal_quarter 格式 / KeyMetricsRepository API）
- [backend/app/services/cockpit/repricing_trigger_service.py](backend/app/services/cockpit/repricing_trigger_service.py) — 当前 service（d1 skeleton + d2 T1 实装；T2 占位返 None 待替换）
- [backend/app/repositories/key_metrics_repository.py](backend/app/repositories/key_metrics_repository.py) — 数据层 API（`get_recent_for_ticker(ticker, limit=8)`）

---

## 6. 下一 session 恢复指令

复制以下指令到新 session（建议 Sonnet 4.6）：

```
继续开发 F218-d3b，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F218-d3b-contract.md，
进入 Generator 模式，从开发步骤 1（T2 常量段 + helpers + KeyMetricsRepo 注入）开始。
```

---

## 7. 未决事项

无。8 项关键决策（NP-d3b-1 ~ NP-d3b-8）全部按推荐确认；evidence_json schema 已锁定；Contract status=confirmed。
