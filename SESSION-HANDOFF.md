# SESSION-HANDOFF — F216-d3 needs_review，下一步：验收

> 生成时间：2026-05-15
> 当前分支：improve_against_plan
> 父 feature：F216 Cockpit Phase B — Weekly Stage Layer（in_progress）
> 本阶段：F216-d3 → needs_review（Evaluator 全清）
> 下一阶段：acceptance skill 验收 F216-d3

---

## 1. F216-d3 完成摘要

**目标**：SetupMonitorWidget 表格新增 "WS" 列，渲染 weekly_stage（1-4 + 圆点 + title 全名）。

**状态**：Evaluator 自检全清，consistency-check C1/C4/C5 全清，等待 acceptance。

**commits**：
- `856a2c8` wip(F216-d3): extract weeklyStageTokens + SetupItem.weeklyStage
- `70bb05f` wip(F216-d3): WS column + tests
- `ea65575` feat(F216-d3): WS column in SetupMonitorWidget（design-spec.md sync）

---

## 2. 改动文件（6 个，全按 Contract §2）

| 文件 | 改动 |
|------|------|
| `frontend/src/cockpit/lib/weeklyStageTokens.ts` | 新建（4 const + readStageColor helper） |
| `frontend/src/cockpit/widgets/WeeklyStageChartWidget.tsx` | 删本地 3 const → import weeklyStageTokens |
| `frontend/src/cockpit/lib/api/setupMonitorApi.ts` | SetupItem 加 weeklyStage: number \| null |
| `frontend/src/cockpit/widgets/SetupMonitorWidget.tsx` | thead/tbody 加 WS 列 + WeeklyStageCell + 列宽微调 |
| `frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx` | makeItem 加 weeklyStage:2 + §W W1-W7 测试 |
| `docs/设计/design-spec.md` | §Widget 5 ASCII mock + WS 规则 bullet |

---

## 3. 测试结果

| 范围 | 结果 |
|------|------|
| §W W1-W7 新增测试 | 7/7 全绿 |
| SetupMonitorWidget 全量 | 零新增失败（15 pre-existing 不变） |
| WeeklyStageChartWidget | 9/9 全绿（import 重构零变更） |
| 全量 vitest | 297 passed，无新增失败 |
| tsc --noEmit | 零错误 |
| lint | 零新 warning（15 error 全预先存在） |

---

## 4. features.json 当前状态

```
F216 sub_sprints:
  F216-a    done
  F216-b    done
  F216-c1   done
  F216-c2   done
  F216-d1   done
  F216-d2   done
  F216-d3   needs_review  ← 本次，等待 acceptance
  F216-e    design_needed

F216 phase: in_progress（C1：e 未完成，父不升 done）
```

---

## 5. 预先存在的失败（30 条，非本 sprint 引入）

- §R11：`data-testid="ai-rank-close"` 找不到
- §S1-S3：`?` button 渲染问题（Explain AAPL Breakout button 找不到）
- §S7-S11：AI Explainer Popover 系列

这些失败在 clean 分支（c5957e6）就存在，与 F216-d3 无关，不阻塞验收。

---

## 6. 下一步：acceptance

```
触发 acceptance skill，验收 F216-d3。
验收记录：docs/验收/v2.0-F216-d3-acceptance.md
```

验收重点：
- 启动 `pnpm dev`（前端）+ 后端 setup-monitor endpoint
- 对照 design-spec.md §Widget 5 验证 WS 列视觉：颜色 / 数字 / hover title
- 选 1-2 个真实 Stage=2 ticker 验证圆点为绿
- 选 1 个 weeklyStage=null 的 ticker 验证 "—"

---

## 7. 后续衔接

F216-d3 acceptance 通过后：
- 剩余：F216-e（refresh_job cron 编排，~2 文件，contract_needed）
- F216-e done → F216 父 feature 升 done → 触发 F216 整体 acceptance
