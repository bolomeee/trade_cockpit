# SESSION-HANDOFF — F217-c2a done → F217-c2b 待协商

> 更新：2026-05-18 | 触发方：feature-dev Generator + Evaluator 收尾
> 前一节：F217-c2a done (frontend CAPITULATION additive render)
> 当前节：F217-c2b design_needed (5 测试 fixture PULLBACK→CAPITULATION)

---

## 1. 已完成内容（本 session 输出）

### 1.1 F217-c2a Generator 全部完成
- 6 步 wip commits + 1 feat commit + 1 chore commit
- **6 文件精确命中（无 buffer）**：
  1. `frontend/src/styles/tokens.css` — 新增 `--color-setup-capitulation: #8b5cf6;`（line 90，pullback token 保留 line 85）
  2. `frontend/src/cockpit/lib/api/cockpitDecisionApi.ts` — `CapitulationEvidence` 类型 export + `CockpitDecisionData.capitulationEvidence?: CapitulationEvidence | null`
  3. `frontend/src/cockpit/lib/api/setupMonitorApi.ts` — `SetupType` 末尾追加 `| 'CAPITULATION'`（PULLBACK 保留）
  4. `frontend/src/cockpit/components/SetupTypeBadge.tsx` — 三处追加 CAPITULATION（local union / TYPE_COLORS `var(--color-setup-capitulation)` / TYPE_LABELS `'CAP_REV'`，PULLBACK 三 entry 全保留）
  5. `frontend/src/cockpit/widgets/DecisionPanelWidget.tsx` — Earnings 区块后插 3 chip 行（Vol z-score `.toFixed(2)` / Drop 5d `.toFixed(1)%` / Reversal day `是|否`），守卫 `setupType==='CAPITULATION' && capitulationEvidence`
  6. **新建** `frontend/src/cockpit/widgets/__tests__/DecisionPanelWidget.capitulation.test.tsx` — T1-T6 8 tests all pass

### 1.2 Evaluator 自检全过
- T1 CapitulationEvidence 类型可 import + camelCase 一致 ✅
- T2-T5 render 5 tests pass ✅
- T6 SetupTypeBadge CAPITULATION+PULLBACK 双 case ✅
- T7 tokens.css grep `--color-setup-capitulation: #8b5cf6` ✅
- T8 全量回归 28/29（S4 pre-existing failure，非本 sprint 引入）✅
- T9 pnpm tsc --noEmit 0 errors ✅
- PULLBACK 保留（setupMonitorApi + SetupTypeBadge 3 entry + tokens.css token）✅
- design-spec.md 字节未变 ✅
- 无 backend 改动 ✅

### 1.3 features.json 更新
- `_pipeline_status.active_sprint_phase`: contract_agreed → **needs_review**
- `F217.sub_sprints.F217-c2a`: contract_agreed → **needs_review**
- `F217.iteration_history` 追加 needs_review 条目
- `last_updated`: 2026-05-18

---

## 2. 当前状态

| 资产 | 状态 |
|------|------|
| `_pipeline_status.active_sprint` | F217-c2a |
| `_pipeline_status.active_sprint_phase` | **needs_review** |
| `F217.sub_sprints.F217-c2a` | **needs_review** |
| `F217.sub_sprints.F217-c2b` | design_needed |
| `F217.sub_sprints.F217-c2c` | design_needed |
| backend (F217-c1) | done |
| frontend c2a | **done** — 6 文件已落地 |
| frontend c2b | 未动 |
| frontend c2c | 未动 |
| design-spec.md | 未动（c2c 才更新） |

---

## 3. 下一步任务

### 3.1 恢复指令（开 Sonnet 新 session）

```
继续开发 F217-c2b，从 Sprint Contract 协商开始。
读取 SESSION-HANDOFF.md，进入 feature-dev skill，协商 F217-c2b Sprint Contract。
```

### 3.2 F217-c2b 范围（design_needed）

5 测试 fixture PULLBACK→CAPITULATION 迁移（与 backend b3 同形态）：

| 文件 | 改动 |
|------|------|
| `__tests__/SetupMonitorWidget.test.tsx` | fixture setupType `'PULLBACK'` → `'CAPITULATION'` |
| `__tests__/MarketRegimeWidget.test.tsx` | fixture setupType `'PULLBACK'` → `'CAPITULATION'` |
| `__tests__/DecisionPanelWidget.test.tsx` | `mockDecision.setupType: 'BREAKOUT'`（已是正确值，核查是否需改） |
| `__tests__/cockpitApis.test.tsx` | fixture PULLBACK → CAPITULATION |
| `__tests__/cockpitPoolApi.test.tsx` | fixture PULLBACK → CAPITULATION |

注：union 在 c2a 已追加 CAPITULATION（保 PULLBACK），所以 fixture 迁移后两者都编译通过。c2c 才收紧删 PULLBACK。

### 3.3 F217-c2c 范围（design_needed，8 文件用户已授权超 6）

- setupMonitorApi.ts `-PULLBACK` from union
- SetupTypeBadge.tsx `-PULLBACK` case + 引用切 capitulation token
- cockpitPoolApi.ts inline union `-PULLBACK`
- _pendingOrderRow.tsx inline union `-PULLBACK`
- _pendingOrderFormSchemas.ts dropdown `-PULLBACK`
- AiSetupExplainerPopover.tsx Props.setupType + mapping `CAPITULATION→'reversal'`
- tokens.css 删 `--color-setup-pullback`
- docs/设计/design-spec.md setup color 表 + chips 视觉规格

---

## 4. 未决事项 / 注意

- c2a pre-existing failure S4 (`/Decision · NVDA/` 文本不匹配) 存在于回归基线，c2b/c2c 不引入新失败即可
- AiSetupExplainerPopover.tsx dead import（grep 无 JSX 使用），c2c 处理
- F217 父 feature 仍 in_progress（c2a/c2b/c2c 全 done 后才升 done，需 acceptance 跑过）
- backend 已无任何动作（F217-c1 done，前端独立推进）

---

## 5. 引用文档

- Sprint Contract c2a: [docs/开发/sprint-contracts/F217-c2a-contract.md](docs/开发/sprint-contracts/F217-c2a-contract.md)
- Feature 节点: [docs/需求/features.json](docs/需求/features.json) `F217.sub_sprints`
- API-CONTRACT: [docs/系统设计/API-CONTRACT.md](docs/系统设计/API-CONTRACT.md) §Cockpit Decision
- 进度日志: [claude-progress.txt](claude-progress.txt)
