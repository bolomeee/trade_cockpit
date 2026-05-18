---
status: confirmed
drafted_at: 2026-05-18
confirmed_at: 2026-05-18
sprint: F217-c2b
parent_feature: F217
---

# F217-c2b Sprint Contract — 5 测试 fixture PULLBACK → CAPITULATION 迁移

> 生成：2026-05-18 | 状态：草案 → 待用户确认
> Feature：[F217](docs/需求/features.json) Phase C — Capitulation Reversal 严格重写
> Sub-sprint：F217-c2b（前端测试 fixture 迁移，与 backend b3 同形态）
> 前置：
>   - F217-c2a done @ 2026-05-18（frontend additive CAPITULATION 渲染，6 文件落地）
>   - `SetupType` union 已含 `'CAPITULATION'`（仍含 `'PULLBACK'`，c2c 才收紧）
>   - `SetupTypeBadge` CAPITULATION case + 紫色 token 已落
> 下游：F217-c2c（union 收紧 -PULLBACK + 8 文件清理 + design-spec 更新）

> 引用文档：
> - [API-CONTRACT.md](docs/系统设计/API-CONTRACT.md) §Cockpit Setup Monitor L1184 — `setupType` 枚举：`BREAKOUT / CAPITULATION / RECLAIM / EARNINGS_DRIFT / EXTENDED / BROKEN / NONE`（**移除 `PULLBACK`**）。`preferredSetups` 共用同一枚举（L1095 示例 `["BREAKOUT","CAPITULATION"]`）
> - [DATA-MODEL.md](docs/系统设计/DATA-MODEL.md) §SetupSnapshot — `setup_type` 枚举同上
> - [DECISIONS.md](docs/系统设计/DECISIONS.md) §D095 — PULLBACK 历史移除，CAPITULATION 严格按 SRS § 五 Setup 4 重写
> - [F217-c2a-contract.md](docs/开发/sprint-contracts/F217-c2a-contract.md) — c2a 排除项第 7 条明确：5 测试 fixture 迁移属 c2b 范围
> - [SESSION-HANDOFF.md](SESSION-HANDOFF.md) §3.2 — c2b 范围列表

---

## 0. 拆分背景

原 F217-c2（前端 16 文件远超 6 上限）二次拆分（用户 2026-05-18 确认 NP-c2-1=A）：

- c2a ✅ done：additive CAPITULATION 渲染（6 文件）
- **c2b（本 sprint）**：5 测试 fixture PULLBACK → CAPITULATION 迁移（5 文件，纯 test layer，无 src 改动）
- c2c：union 收紧 -PULLBACK + 8 文件清理 + design-spec（8 文件，已授权超 6）

c2b 与 backend b3（test fixture PULLBACK→CAPITULATION）同形态：纯测试层数据替换，运行时代码不动。

c2a 故意保留 PULLBACK union 是为给 c2b 留迁移空间 —— c2b 完成后所有 test fixture 已无 PULLBACK 引用，c2c 才可安全删 union。

---

## 1. 本次实现范围

**包含**（5 个 test 文件的 PULLBACK 字面量迁移）：

1. `SetupMonitorWidget.test.tsx`：
   - L78：`makeItem` fixture `setupType: 'PULLBACK'` → `'CAPITULATION'`（MSFT 行，与 backend SetupSnapshot 新枚举对齐）
   - L173：`REGIME_DATA.preferredSetups: ['BREAKOUT', 'PULLBACK']` → `['BREAKOUT', 'CAPITULATION']`
   - L589 注释 / L590 it 名称 / L595 button name：S2 test case 整体改名 `PULLBACK` → `CAPITULATION`（顺带：MSFT 行渲染的 `aria-label` 跟随 setupType 走，期望文本同步迁移）
2. `MarketRegimeWidget.test.tsx`：
   - L88：`preferredSetups: ['BREAKOUT', 'PULLBACK'] as const` → `['BREAKOUT', 'CAPITULATION'] as const`
3. `DecisionPanelWidget.test.tsx`：
   - L722：`preferredSetups: ['BREAKOUT', 'PULLBACK']` → `['BREAKOUT', 'CAPITULATION']`
   - （**注**：L13 / L401 / L686 现已是 `setupType: 'BREAKOUT'`，无 PULLBACK fixture，符合 HANDOFF §3.2 备注"已是正确值，核查后无需改"）
4. `cockpitApis.test.ts`：
   - L128：`preferredSetups: ['BREAKOUT', 'PULLBACK']` → `['BREAKOUT', 'CAPITULATION']`
5. `cockpitPoolApi.test.ts`：
   - L40：`setupTypes: 'BREAKOUT,PULLBACK'` 入参 → `'BREAKOUT,CAPITULATION'`
   - L47：URL-encoded assertion `'setupTypes=BREAKOUT%2CPULLBACK'` → `'setupTypes=BREAKOUT%2CCAPITULATION'`

**明确排除（本次不做）**：

- src/ 下任何运行时代码改动（`SetupType` union / Badge / Widget / Api 文件等）
- `SetupType` union 收紧删 PULLBACK（c2c）
- `_pendingOrderRow.tsx` / `_pendingOrderFormSchemas.ts` / `AiSetupExplainerPopover.tsx` 改动（c2c）
- `tokens.css` 删 `--color-setup-pullback`（c2c）
- `docs/设计/design-spec.md` 更新（c2c）
- 新建任何 test 文件（`DecisionPanelWidget.capitulation.test.tsx` 已在 c2a 落地）
- 修改 test 套件结构（describe/beforeEach/fixture helpers）
- backend 任何改动
- `SetupMonitorWidget.test.tsx` 其他 SETUP_MONITOR_FIXTURE 7 个 setupType 行（除 MSFT 外 6 个：BREAKOUT/RECLAIM/EARNINGS_DRIFT/EXTENDED/BROKEN/NONE，全部保持原值）

---

## 2. 预计修改文件（共 5 个，未到 6 上限）

| # | 文件路径 | 改动类型 | 改动点数 | 说明 |
|---|---------|---------|---------|------|
| 1 | `frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx` | 修改 | 5 处 | L78 fixture / L173 preferredSetups / L589 注释 / L590 it 名 / L595 button name；统一替换 `PULLBACK` → `CAPITULATION` |
| 2 | `frontend/src/cockpit/widgets/__tests__/MarketRegimeWidget.test.tsx` | 修改 | 1 处 | L88 preferredSetups |
| 3 | `frontend/src/cockpit/widgets/__tests__/DecisionPanelWidget.test.tsx` | 修改 | 1 处 | L722 preferredSetups |
| 4 | `frontend/src/cockpit/lib/api/__tests__/cockpitApis.test.ts` | 修改 | 1 处 | L128 preferredSetups |
| 5 | `frontend/src/cockpit/lib/api/__tests__/cockpitPoolApi.test.ts` | 修改 | 2 处 | L40 入参 / L47 URL assertion |

👤 用户确认 5 文件列表合理后，方可进入开发。

### 决策细节（NP-c2b 系列）

**NP-c2b-1（SetupMonitorWidget S2 test case 重命名是否在范围）**：
- L78 fixture 改 setupType 后，渲染的 button `aria-label` 由组件 `Explain ${ticker} ${setupType} setup` 拼接，会自动变 `'Explain MSFT CAPITULATION setup'`。如不同步改 L595 expect 字符串，S2 必失败。
- 选项 A：**完整同步**（L78 + L589 注释 + L590 it 名 + L595 expect）—— 4 个位置在同一 test case 内的统一字面量迁移，原子改动
- 选项 B：仅改 L78 不改其他，让 S2 失败 / 重写一个 CAPITULATION test 在 c2c
- **推荐：A**（fixture 迁移本就是改测试，连带 expect 字面量同步是题中应有之义，不算超范围；保留 S2 占位语义不变："非 BREAKOUT 但仍渲染 explain ? button 的 setup 类型 smoke test"）

**NP-c2b-2（DecisionPanelWidget.capitulation.test.tsx 是否需要触碰）**：
- 该文件 c2a 新建，fixture 本就用 `setupType: 'CAPITULATION'`，无 PULLBACK 字面量
- 选项：A 不动 / B 顺带 review 是否有遗漏 PULLBACK
- **推荐：A 不动**（c2a Evaluator 已通过，重复 review 浪费 token；grep 验证一次即可，见 §3 T5）

**NP-c2b-3（DecisionPanelWidget.test.tsx 主体 mockDecision 是否需查 setupType=PULLBACK）**：
- HANDOFF §3.2 已注："mockDecision.setupType: 'BREAKOUT'（已是正确值，核查是否需改）"
- grep 结果：L13 / L401 / L686 均为 BREAKOUT，全文唯一 PULLBACK 在 L722 preferredSetups
- **推荐：仅改 L722，核查通过**

**NP-c2b-4（test 文件其他 PULLBACK 字符串注释/文档是否同步）**：
- grep `__tests__/.*PULLBACK` 五个文件之外是否还有遗漏：c2a 新建的 `DecisionPanelWidget.capitulation.test.tsx` 无；其他 test 文件 (`ActionListWidget`, `CockpitChartWidget`, `PendingOrdersWidget`, `PoolBuilderWidget`, `PositionListWidget`, `WeeklyStageChartWidget`, `cockpitActionsApi`, `cockpitPendingOrdersApi`, `cockpitPositionsApi`, `aiApi`, `userSettingsApi`) 全部 0 命中（c2a Evaluator 已 grep）
- **推荐：5 文件清单为完整闭包，无遗漏**

**NP-c2b-5（fixture 改为 CAPITULATION 后 SetupTypeBadge label 期望）**：
- c2a 已落 `TYPE_LABELS.CAPITULATION = 'CAP_REV'`
- SetupMonitorWidget.test.tsx S2 test 仅断言 button aria-label（基于 setupType 字面量，非 label）；未直接断言 badge 视觉文字
- MarketRegimeWidget.test.tsx 渲染 preferredSetups chips 时是否含 'PULLBACK' 文本断言？需 grep 确认
- **推荐：开发前先 grep `'PULLBACK'` in 5 文件 100% 确保已枚举所有断言点**（§4 Step 0）

**NP-c2b-6（commit 粒度）**：
- 选项 A：5 文件分 5 wip commits（与 c2a 6 步 commit 风格一致）
- 选项 B：1 个原子 commit "fix(F217-c2b): test fixture PULLBACK → CAPITULATION"（纯 fixture 迁移，逻辑等价）
- **推荐：B 单 commit**（理由：5 处改动均为同一语义的字面量替换，无中间状态可独立验证；split 反而增加 review 噪音。每步独立验证只在跨层改动时有价值。c2b 不引入新代码路径，bisect 价值低）

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| T1 | 5 文件改动后，`pnpm test`（vitest）**当前 sprint 涉及的 5 个测试文件**全部 0 失败（c2a 的 28/29 基线 S4 pre-existing 排除）：SetupMonitorWidget / MarketRegimeWidget / DecisionPanelWidget / cockpitApis / cockpitPoolApi | 单元 + 集成 | vitest |
| T2 | `grep -rn "'PULLBACK'\\|\"PULLBACK\"" frontend/src/cockpit/{widgets,lib}/__tests__/` 0 命中（除 `SetupMonitorWidget.test.tsx` 中允许残留的非 PULLBACK setup label test 上下文，需逐个 review） | 静态 | grep |
| T3 | `pnpm tsc --noEmit` 0 type 错误（`setupType: 'CAPITULATION'` 应被 union `\| 'CAPITULATION'`（c2a 已落）接受） | 静态 | tsc |
| T4 | SetupMonitorWidget.test.tsx S2 改名后 `it('S2: CAPITULATION row renders ? button')` 通过，断言 `'Explain MSFT CAPITULATION setup'` aria-label 命中（运行时组件渲染逻辑无改动，纯字符串拼接验证） | 单元 | vitest |
| T5 | `DecisionPanelWidget.capitulation.test.tsx` 不变（grep 字节级别对比 c2a 落地后版本，确保未被误碰） | 静态 | git diff |
| T6 | 全量回归：`pnpm test` 0 新增失败（基线为 c2a Evaluator 报告：28/29 通过，S4 pre-existing）；若 c2b 后总通过数 > 28，说明 c2b 顺带修复了某 test 失败（应排查原因，可能 c2a 漏改） | 回归 | vitest |
| T7 | src/ 下任何运行时代码 0 改动：`git diff --stat HEAD~ -- frontend/src` 应仅显示 `__tests__/` 路径下的文件 | 静态 | git diff |
| T8 | backend / docs / design-spec / tokens.css / features.json src 字段 0 改动：`git status` 显示 c2b 涉及文件仅在 frontend/src/cockpit/{widgets,lib}/__tests__/ 5 个 path | 静态 | git status |

---

## 4. 开发顺序（单步原子改动 + 1 final commit）

| Step | 内容 | 验证 | commit message |
|------|------|------|---------------|
| 0 | `grep -rn "'PULLBACK'\\|\"PULLBACK\"" frontend/src/cockpit/{widgets,lib}/__tests__/` 枚举所有 PULLBACK 命中点，对照 §1.1-5 清单 100% 覆盖；如有遗漏点 → 停止报告用户 | grep 结果对照 §2 表 | （不 commit） |
| 1 | 同时改 5 个文件的 PULLBACK 字面量（参考 §1.1-5）。次序：(1) cockpitPoolApi.test.ts → (2) cockpitApis.test.ts → (3) MarketRegimeWidget.test.tsx → (4) DecisionPanelWidget.test.tsx → (5) SetupMonitorWidget.test.tsx（最复杂留最后，5 处改动） | `pnpm tsc --noEmit` 0 错误 | （不 commit） |
| 2 | `pnpm test -- SetupMonitorWidget MarketRegimeWidget DecisionPanelWidget cockpitApis cockpitPoolApi` 5 个文件本地跑过 | 5 个文件全部 0 失败 | （不 commit） |
| 3 | `pnpm test` 全量回归对照 c2a 基线（28/29，S4 pre-existing） | 0 新增失败 | （不 commit） |
| 4 | Evaluator 自检（§5） + final commit | git status 清；显式 `git add` 5 文件名 | `fix(F217-c2b): test fixture PULLBACK → CAPITULATION` |

**说明**：c2b 是纯 fixture 字面量迁移，无中间可独立验证的逻辑层级，不分 wip commits。单一 commit 便于回滚 + review。

**禁用 `git add -A`**：显式列出 5 个 test 文件路径。

```bash
git add \
  frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx \
  frontend/src/cockpit/widgets/__tests__/MarketRegimeWidget.test.tsx \
  frontend/src/cockpit/widgets/__tests__/DecisionPanelWidget.test.tsx \
  frontend/src/cockpit/lib/api/__tests__/cockpitApis.test.ts \
  frontend/src/cockpit/lib/api/__tests__/cockpitPoolApi.test.ts
git commit -m "fix(F217-c2b): test fixture PULLBACK → CAPITULATION"
```

---

## 5. Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] T1：5 个 test 文件全部 0 失败（`pnpm test -- <file>` 逐个跑）
- [ ] T2：`grep -rn "PULLBACK" frontend/src/cockpit/{widgets,lib}/__tests__/` 命中数 ≤ 0（5 个改动文件中 PULLBACK 字面量完全清除）
- [ ] T3：`pnpm tsc --noEmit` 0 错误
- [ ] T4：SetupMonitorWidget S2 case 改名后断言 `'Explain MSFT CAPITULATION setup'` 命中
- [ ] T5：`git diff HEAD~ -- frontend/src/cockpit/widgets/__tests__/DecisionPanelWidget.capitulation.test.tsx` 空（c2b 未触碰 c2a 新建文件）
- [ ] T6：全量 `pnpm test` 通过数 ≥ 28（c2a 基线），失败数 ≤ 1 且仅为 S4 pre-existing
- [ ] T7：`git diff --stat HEAD~` 仅显示 5 个 `__tests__/` 路径，无 src/ 运行时代码改动
- [ ] T8：`git status` 工作区清，无遗留未提交文件
- [ ] src 层 `SetupType` union 未改（grep `setupMonitorApi.ts` 中 `'PULLBACK'` 应仍存在 — c2c 才删）
- [ ] tokens.css `--color-setup-pullback` 未删
- [ ] design-spec.md 字节级别未改
- [ ] backend 0 改动（`git diff HEAD~ -- backend/` 空）

### 代码质量检查
- [ ] 无新增死代码（c2b 只替换字符串，无新增 import / 函数）
- [ ] 无注释残留旧 PULLBACK 字面量（除非作为对比说明，本 sprint 无此需求）
- [ ] 字符串替换无 typo（CAPITULATION 拼写一致，大小写正确）
- [ ] URL encoding 一致：`setupTypes=BREAKOUT%2CCAPITULATION` 大小写与 `%2C` 编码正确

### 回归测试
- [ ] `pnpm test` 全量跑：通过 / 失败 / 跳过数 对照 c2a 基线表（28/29，S4 pre-existing 仍允许）
- [ ] 如出现新失败（基线外的 fail），打回 Generator
- [ ] 如出现 S4 由 fail → pass（"修复了未预期的失败"）：报告用户，可能 c2a 漏改的 PULLBACK 在 c2b 被修

---

## 6. 回滚策略

- 单 commit 回滚：`git revert <commit>` 即可，5 文件原子还原
- 不涉及 DB / 不涉及 schema / 不涉及 src 运行时
- 回滚后系统回到 c2a done 状态，正常运行（PULLBACK fixture 在 c2a union 仍保留，向后兼容工作）
- 不破坏 c2c 依赖：c2c 必须在 c2b 完成（test 已无 PULLBACK 引用）后才能收紧 union；若 c2b 回滚，c2c 暂缓

---

## 7. Git Commit 规范

- **单 commit**（无 wip，纯 fixture 迁移无中间状态）：
  ```bash
  git add \
    frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx \
    frontend/src/cockpit/widgets/__tests__/MarketRegimeWidget.test.tsx \
    frontend/src/cockpit/widgets/__tests__/DecisionPanelWidget.test.tsx \
    frontend/src/cockpit/lib/api/__tests__/cockpitApis.test.ts \
    frontend/src/cockpit/lib/api/__tests__/cockpitPoolApi.test.ts
  git commit -m "fix(F217-c2b): test fixture PULLBACK → CAPITULATION"
  ```
- 不用 `feat`：c2b 不引入功能，是 fixture 迁移（test 层），`fix` 类型更贴切
- **禁用 `-A`**

---

## 8. 风险与注意

- **c2a-PULLBACK 残留依赖**：c2a 故意保留 `SetupType` union 含 `'PULLBACK'` + `SetupTypeBadge` 三处 PULLBACK entry + `tokens.css --color-setup-pullback`。本 sprint 不动 src，故所有 PULLBACK 残留正常工作；任何此期间引用 PULLBACK 的代码（例：手动测试创建 PULLBACK fixture）仍可编译运行。c2c 才统一删 PULLBACK。
- **S2 test 语义变化**：原 S2 "PULLBACK row renders ? button" 改名 "CAPITULATION row renders ? button"。语义角色相同（非 BREAKOUT 的 explain-supported setup 类型 smoke test），仅 setup 类型变。无功能回归风险。
- **S4 pre-existing failure**：c2a Evaluator 报告 S4 `/Decision · NVDA/` 文本不匹配为预存失败。c2b 不修复 S4（不在范围），但需确保通过数 ≥ 28 / 失败数 ≤ 1。如 c2b 后 S4 仍失败但其他 27 个通过，符合基线。
- **`as const` 语法保留**：MarketRegimeWidget.test.tsx L88 `['BREAKOUT', 'PULLBACK'] as const` 改为 `['BREAKOUT', 'CAPITULATION'] as const`，保留 `as const`（类型推导为 readonly tuple，移除会改变 TS 类型）。
- **URL encoding 验证敏感**：cockpitPoolApi.test.ts L47 断言 `'setupTypes=BREAKOUT%2CCAPITULATION'`，`%2C` 是 `,` 的 percent-encoded 形式（来自 `encodeURIComponent`），大小写敏感。如断言改成 `%2c`（小写）会失败。
- **fixture-only 改动 vs union 收紧的边界**：c2b 后 test fixture 不再引用 PULLBACK，但 `SetupType` union 仍含 PULLBACK，故 src 中如有运行时 PULLBACK fallback 路径（如 SetupTypeBadge `TYPE_LABELS.PULLBACK` 引用）仍存在 —— 这是 c2a 设计的过渡态，c2b 完成后该过渡态仍维持，c2c 一次性切干净。
- **新增 fixture 不属本 sprint**：c2b 仅替换现有 fixture 字面量，不引入新 CAPITULATION 专属断言场景（如 capitulationEvidence 字段 fixture 是 c2a 范围，已在 `DecisionPanelWidget.capitulation.test.tsx` 落地）。

---

## 9. Sprint 完成后 sub_sprints 状态预期

- `F217.sub_sprints.F217-c2b`: `design_needed` → `contract_agreed`（本 contract 确认后）→ `in_progress` → `testing` → `needs_review`
- `F217.sub_sprints.F217-c2a`: 保持 `needs_review`（等 acceptance 才能升 done；c2b 不影响 c2a 状态）
- `F217.sub_sprints.F217-c2c`: 保持 `design_needed`
- `_pipeline_status.active_sprint`: F217-c2a → F217-c2b
- `_pipeline_status.active_sprint_phase`: needs_review → contract_agreed → ... → needs_review
- F217 父 feature：保持 `in_progress`（C1 invariant：所有 c2 子 sprint done 后才升）

---

👤 用户确认本 Contract 后，本 session **强制停止**，开 Sonnet 新 session 进入 Generator 模式从 Step 0 grep 验证开始。
