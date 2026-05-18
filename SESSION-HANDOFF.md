# SESSION-HANDOFF.md — F217-c1 needs_review，待 acceptance

> 生成：2026-05-18
> 当前 Skill：feature-dev（Generator + Evaluator 完成）
> 当前 Feature：F217 — Cockpit Phase C Capitulation Reversal 严格重写
> 当前 Sub-sprint：**F217-c1**（C5-back 后端 capitulationEvidence 接口实装）→ **needs_review**

---

## 完成的内容

✅ **F217-c1 Generator 模式执行完成**（2026-05-18）

### Step 1：decision schema
- `backend/app/schemas/cockpit/decision.py` 新增 `CapitulationEvidence(_CamelModel)` 3 字段
- `drop_5d_pct` 显式 `Field(alias="drop5dPct")`（修复 `to_camel` 产 `drop5DPct` 大写 D 问题）
- `DecisionData.capitulation_evidence: CapitulationEvidence | None = None`

### Step 2：setup_service helper
- `backend/app/services/cockpit/setup_service.py` 新增 module-level `compute_capitulation_evidence(closes, highs, lows) -> dict | None`
- 复用 `_check_close_in_upper_bin` + `SETUP.CAPITULATION_CLOSE_UPPER_BIN`
- 3 个防御边界：bars<6 / closes[-6]=0 / 空列表 → 全返回 None
- `_is_capitulation_reversal` 函数体**未动**

### Step 3：T1-T4 pure tests
- `backend/tests/test_decision_f217c1.py` 新建，14 pure tests，0 失败

### Step 4：decision_service wiring
- `backend/app/services/cockpit/decision_service.py` 在 `setup_type=="CAPITULATION"` 时：
  - inline select DailyBar JOIN Stock，拉最近 6 行（`.desc().limit(6)` 后 reversed 转升序）
  - 调 `compute_capitulation_evidence`，配合 `snapshot.volume_zscore` 组 `CapitulationEvidence`
  - 任一前置失败（volume_zscore=None / bars<6 / helper=None）→ `capitulation_evidence=None`
- `test_decision_f203b2.py` 28/28 兼容性验证通过

### Step 5：T5-T8 集成测试
- 补充 T5-T8（6 tests），集成 db_session 真实 SQLite 测试
- 20/20 全部通过

### Step 6：Evaluator 自检 + T9 全量回归
- ruff：0 新增 warning（修复 F401 + E741×2）
- 全量回归：1115 passed / 8 预存失败 / 0 新增失败

### Step 7：Final commit
- `feat(F217-c1): backend capitulationEvidence wiring`（commit dcadcf6）

---

## 中断位置

**F217-c1 开发完毕，phase = needs_review**。

可直接运行 acceptance skill 进行验收，或先进入 F217-c2 Sprint Contract 协商（前端 chips+badge+token+design-spec）。

---

## Sprint Contract 执行状态

| 开发步骤 | 状态 |
|---------|------|
| DATA-MODEL 确认 | ✅（无改动） |
| API-CONTRACT 确认 | ✅（L1396-1424 已定义） |
| 数据库迁移 | ✅（不需要） |
| Step 1: decision.py schema CapitulationEvidence | ✅ |
| Step 2: setup_service.py compute_capitulation_evidence helper | ✅ |
| Step 3: test_decision_f217c1.py T1-T4 pure tests | ✅ |
| Step 4: decision_service.py evidence wiring | ✅ |
| Step 5: test_decision_f217c1.py T5-T8 集成 tests | ✅ |
| Step 6: Evaluator 自检 + 全量回归 T9 + ruff | ✅ |
| Step 7: Final feat commit | ✅ |

---

## 已创建/修改的文件（本 sprint）

| 文件 | 状态 |
|------|------|
| `backend/app/schemas/cockpit/decision.py` | 修改（CapitulationEvidence + capitulation_evidence 字段） |
| `backend/app/services/cockpit/setup_service.py` | 修改（compute_capitulation_evidence helper 新增） |
| `backend/app/services/cockpit/decision_service.py` | 修改（evidence wiring 分支） |
| `backend/tests/test_decision_f217c1.py` | 新建（T1-T8 20 tests） |

---

## 遗留决策

无。F217-c2 设计决策将在下一次 Sprint Contract 协商时处理。

---

## 关键约束提醒（F217-c2 参考）

- frontend `cockpitDecisionApi.ts` 类型需新增 `CapitulationEvidence` + `DecisionResponse.capitulationEvidence?: ...`
- 5 个测试 fixture（PULLBACK → CAPITULATION）在 c2 内联修复
- SetupTypeBadge.tsx 需新增 CAPITULATION 紫色 badge
- DecisionPanelWidget.tsx 在 setupType=CAPITULATION 时渲染 3 chips
- tokens.css 需重命名 `--color-setup-pullback` → `--color-setup-capitulation`
- design-spec.md setup color 表 + chips 视觉规格在 c2 同步更新

---

## 下一个 Session 继续的指令

```
# 选项 A：验收 F217-c1
触发 acceptance skill，验收 F217-c1。

# 选项 B：直接进入 F217-c2 Sprint Contract 协商
准备开发 F217-c2（前端 chips+badge+token+design-spec）。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F217-c1-contract.md，
进入 feature-dev Sprint Contract 协商，预扫描文件数（9-11 文件需评估是否拆 c2a/c2b）。
```
