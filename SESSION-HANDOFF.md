# SESSION-HANDOFF — F217-b2 needs_review，等待验收

> 生成：2026-05-16
> 上一阶段：F217-b2 Generator + Evaluator 完成 @ 2026-05-16
> 当前 phase：`needs_review`
> 下一阶段：acceptance skill 验收 F217-b2，通过后进 F217-b3 Sprint Contract 协商

---

## 1. F217-b2 Sprint Contract 摘要

**目标**：在 6 个 Pydantic schema 的 setup_type Literal 中**插入 `"CAPITULATION"`**，**保留 `"PULLBACK"`**（向后兼容窗口，b4 才删）。纯加性、纯类型层、无 DB 改动、无运行时风险。

**完整 Contract**：[docs/开发/sprint-contracts/F217-b2-contract.md](docs/开发/sprint-contracts/F217-b2-contract.md)

### 实现范围（6 文件，全部修改无新建）

| # | 文件 | Literal 形式 | 修改位置 |
|---|------|-------------|---------|
| 1 | `backend/app/schemas/cockpit/position.py` | 模块别名 `_VALID_SETUP_TYPES` | L11-13 |
| 2 | `backend/app/schemas/cockpit/pending_order.py` | 模块别名 `_VALID_SETUP_TYPES` | L10-12 |
| 3 | `backend/app/ai/schemas/trade_plan.py` | 内联 Literal（`TradePlanInput.setupType`） | L45 |
| 4 | `backend/app/ai/schemas/candidate_ranker.py` | 内联 Literal（`CandidateInput.setupType`） | L42 |
| 5 | `backend/app/ai/schemas/contradiction_detector.py` | 模块别名 `_SETUP_TYPE` | L41 |
| 6 | `backend/app/ai/schemas/journal_assistant.py` | 模块别名 `_SETUP_TYPE` | L52 |

每个 Literal 元组形如：
```python
Literal["BREAKOUT", "PULLBACK", "CAPITULATION", "RECLAIM", "EARNINGS_DRIFT", "EXTENDED", "BROKEN", "NONE"]
```
即在 `"PULLBACK"` 后**紧邻插入** `"CAPITULATION"`（NP-b2-2=A 一致性约束）。

### 协商点（用户确认）

| # | 议题 | 决议 |
|---|------|------|
| NP-b2-1 | 是否新建专属测试文件 | **A**：不新建（守 6 文件上限；b3 fixture 迁移自然覆盖；T3/T4 用 REPL 入 Evaluator 报告） |
| NP-b2-2 | CAPITULATION 在 Literal 中的位置 | **A**：紧邻 PULLBACK 之后（最小 diff，b4 删 PULLBACK 同位对齐） |
| NP-b2-3 | 是否抽共享 Literal 别名模块 | **A**：保留现状重复（YAGNI，跨包依赖代价） |
| NP-b2-4 | 是否同步更新 4 个 AI SYSTEM_PROMPT | **A**：不动（prompt 行为合约属 F217-c 范畴） |

### 排除（不在本 sprint）

- ❌ 测试 fixture 批量去 PULLBACK → F217-b3
- ❌ 从 Literal 删 PULLBACK 字面量收紧 → F217-b4（必须 b3 完成后）
- ❌ 前端 chips / 紫色 badge / decision_service capitulationEvidence 填充 → F217-c
- ❌ user_settings.preferred_setups JSON 默认值迁移 → F217-c 或独立微 sprint
- ❌ CAPITULATION_ENABLED feature flag → 不引入

---

## 2. 开发顺序（Generator 模式逐步执行）

> ⚠️ 禁用 `git add -A`。每步显式列文件名。

| Step | 文件 | wip commit message |
|------|------|---------------------|
| 1+2 合并 | cockpit/position.py + cockpit/pending_order.py | `wip(F217-b2): cockpit schemas Literal +CAPITULATION (keep PULLBACK)` |
| 3 | ai/trade_plan.py | `wip(F217-b2): trade_plan Literal +CAPITULATION` |
| 4 | ai/candidate_ranker.py | `wip(F217-b2): candidate_ranker Literal +CAPITULATION` |
| 5 | ai/contradiction_detector.py | `wip(F217-b2): contradiction_detector Literal +CAPITULATION` |
| 6 | ai/journal_assistant.py | `wip(F217-b2): journal_assistant Literal +CAPITULATION` |
| 7 | 全量回归 + final | `feat(F217-b2): Pydantic schemas Literal +CAPITULATION (PULLBACK kept for b3 window)` |

每 step 最小验证（详见 Contract §4）：`python -c "from … import …; print(get_args(...))"` 应含 `'CAPITULATION'` 与 `'PULLBACK'`。

---

## 3. Evaluator 测试矩阵（T1-T7）

| # | 描述 | 类型 |
|---|------|------|
| T1 | 6 文件 import 不报错 | 静态 |
| T2 | 现有 PULLBACK 字面量仍接受（向后兼容窗口未关） | 集成（pytest -k "PULLBACK or pullback"） |
| T3 | cockpit schemas (4 类) 接受 setup_type='CAPITULATION' | REPL → Evaluator 报告 |
| T4 | 4 个 AI schema input 接受 setupType='CAPITULATION' | REPL → Evaluator 报告 |
| T5 | grep 验证 6 处 `Literal[…CAPITULATION…]` 存在 | 静态（grep \| wc -l = 6） |
| T6 | grep 验证 6 处仍含 `"PULLBACK"` 字面量 | 静态 |
| T7 | 全量回归 0 新增失败 | 集成（pytest backend/tests/ -x） |

自检清单详见 Contract §3。

---

## 4. 项目当前状态快照

```
F217 — phase: in_progress (Cockpit Phase C — Capitulation Reversal 严格重写)
 ├── F217-a   — done ✅ (后端 setup_service 7 AND 门 + 34 pure tests)
 ├── F217-b1  — done ✅ (DB 层 legacy 列 + PULLBACK 软删)
 ├── F217-b2  — contract_agreed 📝 ← 本次协商完成，等待 Generator
 ├── F217-b3  — design_needed (测试 fixture 去 PULLBACK, 6 files)
 ├── F217-b4  — design_needed (Pydantic Literal 删 PULLBACK 收紧)
 └── F217-c   — design_needed (前端 chips + 紫色 badge)
```

`_pipeline_status`: active_sprint=F217-b2, active_sprint_phase=contract_agreed, development=in_progress

---

## 5. 风险提示（给下一 session）

1. **6 文件命中上限，无 buffer**：如 Generator 期间发现 Contract §2 之外的遗漏 Literal 定义点，**停下来二次协商**，不得自行扩张到第 7 文件
2. **Literal 顺序一致性**：6 处必须全部按 NP-b2-2=A 顺序（紧邻 PULLBACK 之后），便于 b4 删 PULLBACK 时 diff 对齐
3. **不动 SYSTEM_PROMPT / guardrail / BANNED_PHRASES**：本 sprint 严格只动 Literal 元组本身，其它字符不变
4. **预存失败基线**：F217-b1 评估期已记录 8 条预存失败（test_regime_f201a/b、test_schema、test_ai_schemas_f209、test_ai_schemas_f211a1 R5/R6、test_decision_f215b AlembicRoundtrip、test_fmp_client）— b2 Evaluator T7 回归对比这条基线，0 新增失败即过
5. **PULLBACK 暂保留**：本 sprint 完成后 PULLBACK 仍是 valid Literal — 所有现存 PULLBACK fixture 继续通过，b3 才迁移、b4 才删
6. **CAPITULATION 写入路径**：F217-a 后 setup_service 已能写 setup_snapshots.setup_type='CAPITULATION'，b1 DB 层已支持。本 sprint 只是让"Pydantic 校验路径接收 CAPITULATION 不被拒"

---

## 6. 下一 Session 恢复指令

```
继续开发 F217-b2，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F217-b2-contract.md，
进入 Generator 模式，从 §4 开发顺序 Step 1+2（cockpit schemas）开始。
```

建议用 **Sonnet** 开新 session（Literal 扩展是机械改动，不需要 Opus 推理深度）。
