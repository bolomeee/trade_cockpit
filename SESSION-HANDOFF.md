# SESSION-HANDOFF — F217-c2c needs_review → acceptance 集中验收

> 更新：2026-05-18 | 触发方：feature-dev Evaluator 模式完成
> 前一节：F217-c2c Generator 模式（3 commits 落地）
> 本节产出：F217-c2c Evaluator 通过 → needs_review
> 下一节：开 Sonnet 新 session，运行 acceptance skill 集中验收 c2a / c2b / c2c

---

## 1. 本 session 输出

- **3 commits 落地**：
  - `4e050ee` `refactor(F217-c2c): remove PULLBACK from frontend SetupType unions`（6 文件）
  - `fd0615e` `chore(F217-c2c): remove --color-setup-pullback token`（1 文件）
  - `8e14086` `docs(F217-c2c): update design-spec for PULLBACK → CAPITULATION`（2 文件）
- **features.json 更新**：
  - `_pipeline_status.active_sprint_phase`：contract_agreed → **needs_review**
  - `F217.sub_sprints.F217-c2c`：contract_agreed → **needs_review**
  - iteration_history 追加 c2c needs_review 条目
- claude-progress.txt 追加 2026-05-18 c2c done 条目
- SESSION-HANDOFF.md 本文

---

## 2. 当前状态

| 资产 | 状态 |
|------|------|
| `_pipeline_status.active_sprint` | **F217-c2c** |
| `_pipeline_status.active_sprint_phase` | **needs_review** |
| `F217.sub_sprints.F217-c2a` | needs_review（待 acceptance）|
| `F217.sub_sprints.F217-c2b` | needs_review（待 acceptance）|
| `F217.sub_sprints.F217-c2c` | **needs_review** ← 本次输出 |
| F217 父 feature | in_progress（C1 invariant：c2a/c2b/c2c 全 done 才升）|
| SetupType union | **已不含 PULLBACK** — TS 编译期禁止 PULLBACK 字面量 |
| `--color-setup-pullback` token | **已删除** |
| design-spec.md | **已更新至最终态**（color 表 / ASCII mockup / popover / v2.2.0 偏离说明）|

---

## 3. Evaluator 自检结果

| 检查 | 结果 |
|------|------|
| T1 `pnpm tsc --noEmit` | ✅ 0 错误 |
| T2 src PULLBACK 字面量 | ✅ 0 命中 |
| T3 cockpit PULLBACK/pullback | ✅ 唯一命中 = L17 backend schema（合同明确不动）|
| T4 `setup-pullback` | ✅ 0 命中 |
| T5 design-spec PULLBACK | ⚠️ 3 命中（均在 v2.2.0 偏离说明历史文字，合同 §1.8 要求，非活跃枚举）|
| T6 capitulation test | ✅ 7/7（含 'UNKNOWN' fallback test）|
| T8 全量回归 | ✅ 22/28 suites = c2b 基线，0 新增失败 |
| T10 CAPITULATION in schemas | ✅ _pendingOrderFormSchemas L6 命中 |
| T12 backend 0 commits | ✅ HEAD~3 HEAD 无 backend 变更 |
| T13 `__tests__` 仅 1 文件 | ✅ capitulation.test.tsx |
| T14 3 commits 落地 | ✅ refactor + chore + docs |

**T5 说明**：design-spec.md 中 3 处 PULLBACK 命中全在新增的 v2.2.0 偏离说明块（合同 §1.8 明确要求追加），是历史对比记录而非活跃枚举用法。合同 §3 T5 与 §1.8 存在细微矛盾，接受现状。

---

## 4. 下一步任务（开 Sonnet 新 session）

### 4.1 恢复指令

```
F217-c2c Evaluator 已通过，phase = needs_review。
读取 SESSION-HANDOFF.md，
运行 acceptance skill 集中验收 F217 c2a / c2b / c2c 三 sub-sprint。
```

### 4.2 acceptance 流程

触发 `acceptance` skill，范围：F217 c2a / c2b / c2c 三 sub-sprint。

acceptance 通过后：
- sub_sprints.F217-c2a/c2b/c2c 升 `done`
- F217 父 feature 升 `done`（C1 invariant 满足）
- features.json `_pipeline_status.active_sprint` 清空或推进至下一 feature
- 生成 `docs/验收/v2.2.0-F217-c2c-acceptance.md`
- iteration_history 追加 acceptance 条目

---

## 5. 遗留注意事项

- **AiSetupExplainerPopover L17 `setup: 'pullback' | 'breakout' | ...`** 保留：backend `setup_explainer` AI task input schema（F211 归口），c2c 不动。前端 setupType union 已无 PULLBACK，mapping 中 'pullback' 分支不再可达，是"前端无法传入但 backend 仍可接受"的安全过渡态。后续清理开 F217-c3 / F221。

- **SetupMonitorWidget §S pre-existing test 失败**（SetupMonitorWidget.test.tsx 15 失败，含 S1/S2/S3/S7-S11/R11）：根因是 SetupMonitorWidget.tsx import AiSetupExplainerPopover 但全文 0 个 `<AiSetupExplainerPopover>` JSX 命中，widget 未渲染该 popover。NP-c2c-7=A：独立 sprint 处理（候选 F217-c3 或 F218）。

- **三处 inline SetupType union 复本**（cockpitPoolApi.ts L32 / _pendingOrderRow.tsx L60 / SetupTypeBadge.tsx union）：c2c 后三处内容一致（7 枚举 + null），下次有 setup_type 变更时手工同步 3 处。建议在 DECISIONS.md 追加 D097 说明。

---

## 6. 引用文档

- Sprint Contract c2c: [docs/开发/sprint-contracts/F217-c2c-contract.md](docs/开发/sprint-contracts/F217-c2c-contract.md)
- Feature 节点: [docs/需求/features.json](docs/需求/features.json) `F217.sub_sprints`
- 进度日志: [claude-progress.txt](claude-progress.txt)
- 设计规格（已更新）: [docs/设计/design-spec.md](docs/设计/design-spec.md)
