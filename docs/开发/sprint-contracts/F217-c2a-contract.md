---
status: confirmed
drafted_at: 2026-05-18
confirmed_at: 2026-05-18
sprint: F217-c2a
parent_feature: F217
---

# F217-c2a Sprint Contract — Cockpit Phase C 前端 CAPITULATION 渲染（additive）

> 生成：2026-05-18 | 状态：草案 → 待用户确认
> Feature：[F217](docs/需求/features.json) Phase C — Capitulation Reversal 严格重写
> Sub-sprint：F217-c2a（C5-front additive，新增 CAPITULATION 渲染，保留 PULLBACK 向后兼容）
> 前置：
>   - F217-a/b1/b2/b3/b4/c1 全部 done @ 2026-05-15 ~ 2026-05-18
>   - backend `GET /api/cockpit/decision/{ticker}` 已能返回 `capitulationEvidence: { volZscore, drop5dPct, reversalDay } | null`（c1 done）
>   - 后端 setup_type=CAPITULATION 已可由 setup_service 产出
> 下游：F217-c2b（5 测试 fixture 迁移）→ F217-c2c（union 收紧 -PULLBACK + 清理 + design-spec）

> 引用文档：
> - API-CONTRACT.md §Cockpit Setup Monitor — `setupType` 枚举含 `CAPITULATION`
> - API-CONTRACT.md §Cockpit Decision (GET /api/cockpit/decision/{ticker}) L1390-1424 — `capitulationEvidence: { volZscore, drop5dPct, reversalDay } | null`（仅 setupType=CAPITULATION 时非 null）
> - DATA-MODEL.md §SetupSnapshot — setup_type 枚举（含 CAPITULATION）
> - DECISIONS.md §D095 子决策 5（API 字段可选 / 仅 CAPITULATION 时非 null）
> - design-spec.md §设计 token — 紫色 `#8b5cf6`（c2c 同步 setup color 表 + chips 视觉规格，本 sprint 仅落 tokens.css 新增 token）
> - 现有 chip 样式参考：`DecisionPanelWidget.tsx` line 80-93 Earnings 区块（inline `<span>` label-value pair + `var(--font-size-caption)` + `var(--color-text-muted)`）

---

## 0. 拆分背景（c2 → c2a / c2b / c2c）

原 F217-c2 估计"前端 9-11 文件"在 2026-05-18 协商时预扫描确认共 **16 文件** 远超 6 上限，二次拆分（用户确认）：

- **c2a（本 sprint）**：additive CAPITULATION 渲染（6 文件，PULLBACK 暂保留，与 backend b2 同形态）
- **c2b**：5 测试 fixture PULLBACK→CAPITULATION 迁移（与 backend b3 同形态）
- **c2c**：union 收紧 -PULLBACK + cockpitPoolApi/_pendingOrderRow/_pendingOrderFormSchemas/AiSetupExplainerPopover + tokens.css 删旧 token + design-spec.md（8 文件，用户已授权超 6 同 b3 NP-b3-1=A 模式）

NP-c2 系列（用户 2026-05-18 全部按推荐确认）：
- NP-c2-1=A：3-way 拆分
- NP-c2-2=A：design-spec.md 放 c2c（本 sprint **不动** design-spec）
- NP-c2-3=A：（c2c 范围）AiSetupExplainerPopover mapping CAPITULATION→'reversal'
- NP-c2-4=A：tokens.css c2a 新增 `--color-setup-capitulation` 保 pullback；c2c 删 pullback
- NP-c2-5=A：DecisionPanelWidget chips 复用现有 inline `<span>` 标签-值样式（不新建 EvidenceChip 组件）
- NP-c2-6=A：（c2c 范围）8 文件用户授权超 6

---

## 1. 本次实现范围

**包含**：
1. `cockpitDecisionApi.ts` 新增 `CapitulationEvidence` 类型 + `CockpitDecisionData.capitulationEvidence?: CapitulationEvidence | null`
2. `setupMonitorApi.ts` `SetupType` union **追加** `'CAPITULATION'`（PULLBACK 保留，向后兼容）
3. `SetupTypeBadge.tsx` 在 `SetupType` 本地 union + `TYPE_COLORS` + `TYPE_LABELS` 三处 **追加** CAPITULATION（PULLBACK 三个 entry 全保留），CAPITULATION 颜色引用新 token `var(--color-setup-capitulation)`，label 用 `CAPITULATE`（≤8 字符贴合现有 EARN_DRFT 模式 — 见 §决策细节 NP-c2a-2）
4. `DecisionPanelWidget.tsx` 在 `data` 存在且 `data.setupType === 'CAPITULATION'` 且 `data.capitulationEvidence` 非 null 时，在 Earnings 行下方插入 **3 个 chip 行**（Vol z-score / Drop 5d / Reversal day），样式复用现有 `rowStyle` + `labelStyle` + `valueStyle`（line 26-43），形态参考 line 80-93 Earnings 区块
5. `tokens.css` `:root` 段在 `--color-setup-broken: ...` 行之后 **新增** `--color-setup-capitulation: #8b5cf6;`（PULLBACK token 暂留，c2c 删）
6. 新建 `__tests__/DecisionPanelWidget.capitulation.test.tsx` 覆盖 T1-T5：CAPITULATION setup 显示 3 chips / 非 CAPITULATION 不显示 / capitulationEvidence=null 不显示 / 数值格式化正确 / Reversal day=false 时 chip 渲染（值"否"）

**明确排除（本次不做）**：
- 收紧 `SetupType` union 删除 `PULLBACK`（c2c）
- 收紧 `SetupTypeBadge.tsx` 删除 PULLBACK case + 三个 entry（c2c）
- `cockpitPoolApi.ts` inline union -PULLBACK +CAPITULATION（c2c）
- `_pendingOrderRow.tsx` inline union -PULLBACK +CAPITULATION（c2c）
- `_pendingOrderFormSchemas.ts` 下拉选项 -PULLBACK +CAPITULATION（c2c）
- `AiSetupExplainerPopover.tsx` Props.setupType + mapping 改动（c2c）
- 5 测试 fixture（SetupMonitorWidget / MarketRegimeWidget / DecisionPanelWidget / cockpitApis / cockpitPoolApi）PULLBACK→CAPITULATION（c2b）
- `tokens.css` 删 `--color-setup-pullback`（c2c）
- `docs/设计/design-spec.md` setup color 表 + chips 视觉规格新增（c2c）
- backend 任何改动（c1 已落地）
- 新建 EvidenceChip / Chip 通用组件（NP-c2-5=A）
- 重命名 `--color-setup-pullback` 直接为 `--color-setup-capitulation`（NP-c2-4=A 已拒，避免 SetupTypeBadge PULLBACK case 在 c2a 保留期间 token ref 失效）

---

## 2. 预计修改文件（共 6 个 — 命中 6 上限，无 buffer）

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `frontend/src/cockpit/lib/api/cockpitDecisionApi.ts` | 修改 | 新增 `export type CapitulationEvidence = { volZscore: number; drop5dPct: number; reversalDay: boolean }`；`CockpitDecisionData` 末尾添 `capitulationEvidence?: CapitulationEvidence \| null`（与 c1 backend `model_dump(by_alias=True)` 输出对齐）。 |
| 2 | `frontend/src/cockpit/lib/api/setupMonitorApi.ts` | 修改 | `SetupType` union 单行追加 `\| 'CAPITULATION'`（位置紧邻 `'PULLBACK'` 行后，与 backend b2 镜像 diff）。PULLBACK 不删（c2c 范围）。 |
| 3 | `frontend/src/cockpit/components/SetupTypeBadge.tsx` | 修改 | 本地 `SetupType` union 追加 `\| 'CAPITULATION'`；`TYPE_COLORS` 添 `CAPITULATION: 'var(--color-setup-capitulation)'`；`TYPE_LABELS` 添 `CAPITULATION: 'CAPITULATE'`（8 字符 ≤ 现有 EARN_DRFT 长度）。三处保留 PULLBACK entry 不动。 |
| 4 | `frontend/src/cockpit/widgets/DecisionPanelWidget.tsx` | 修改 | 在 `data.earningsRisk` 区块（line 80-93）之后 **新增** capitulation evidence 渲染：`{data.setupType === 'CAPITULATION' && data.capitulationEvidence && ( <> 3 rows </>)}`。三行复用现有 `rowStyle` + `labelStyle` + `valueStyle`：(1) `Vol z-score` / `{evidence.volZscore.toFixed(2)}` (2) `Drop 5d` / `{fmtPct(evidence.drop5dPct / 100)}`（注：backend 返回百分比数值如 -12.4 表示 -12.4%，fmtPct 接受 fraction，需除 100；或直接 `${evidence.drop5dPct.toFixed(1)}%`） (3) `Reversal day` / `{evidence.reversalDay ? '是' : '否'}`。无额外样式抽象、无 chip 组件、无新 token。 |
| 5 | `frontend/src/styles/tokens.css` | 修改 | `:root` 段在 line 89 `--color-setup-broken: var(--color-change-negative);` 之后插入 `--color-setup-capitulation: #8b5cf6;`（紫色，与 design-spec D095 指定一致）。`--color-setup-pullback` 暂留（c2c 删）。 |
| 6 | `frontend/src/cockpit/widgets/__tests__/DecisionPanelWidget.capitulation.test.tsx` | 新建 | 5 测试 T1-T5（详见 §3）。沿用现有 `DecisionPanelWidget.test.tsx` 的 vitest + @testing-library/react fixture 模式（mock `getCockpitDecision` query）。 |

👤 用户确认 6 文件列表合理后，方可进入开发。

### 决策细节

**NP-c2a-1（数值格式化 drop_5d_pct）**：backend 返回 `drop_5d_pct: -12.4`（已是百分比单位的 number，API-CONTRACT L1422 明确"single-digit decimal"）。c2a 选择 inline `${evidence.drop5dPct.toFixed(1)}%` 渲染（最简，零外部依赖），而非 fmtPct(× / 100)。**推荐：inline `.toFixed(1)%`**。

**NP-c2a-2（CAPITULATION badge label）**：现有 EARN_DRFT 模式表明长 label 截缩到 8 字符以内适配 badge 宽度。选项：(a) `CAPITULATE`（10 字符，过长）/ (b) `CAPIT`（5 字符，可读性差）/ (c) `CAPITULA`（8 字符，刻意截断丑） / (d) **`CAPITUL`（7 字符）**/ (e) `CAP_REV`（7 字符，与 SRS 命名 "Capitulation Reversal" 一致）。**推荐：(e) `CAP_REV`**（保留语义，与 EARN_DRFT 同构）。

**NP-c2a-3（test 文件命名）**：vitest 自动 glob `**/*.test.tsx`。文件名 `DecisionPanelWidget.capitulation.test.tsx`（与现有 `DecisionPanelWidget.test.tsx` 分开，避免 c2b 改 fixture 时影响 c2a 新写 case）。**推荐保持 `.capitulation.test.tsx` 命名**。

**NP-c2a-4（DecisionPanelWidget chip 插入位置）**：(a) Earnings 行之后、deterministicHash 之前（推荐，与 Earnings 同区块）/ (b) Header 之后、Entry/Stop 之前（与 setupType/setupQuality 邻近）/ (c) deterministicHash 之后（末尾）。**推荐：(a)**（chip 是 setup-specific evidence，与 Earnings 同性质）。

**NP-c2a-5（CapitulationEvidence 是否标 `null` 严格区分 vs 缺省）**：backend pydantic 默认 None → JSON `null`，c1 已验证 alias 序列化输出 `capitulationEvidence: null`（非 undefined）。c2a 类型用 `capitulationEvidence?: CapitulationEvidence | null` 兼容 null 和 undefined，renderer 用 `&& data.capitulationEvidence` 截短判断。**推荐：可选+nullable 都允许**。

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| T1 | `CapitulationEvidence` 类型可从 `cockpitDecisionApi.ts` import；与 backend `model_dump(by_alias=True)` JSON 兼容（camelCase 字段名 volZscore/drop5dPct/reversalDay） | 单元（类型层） | TS 编译 + vitest type assertion |
| T2 | DecisionPanelWidget 在 `setupType='CAPITULATION'` 且 `capitulationEvidence={volZscore:2.71, drop5dPct:-12.4, reversalDay:true}` 时渲染 3 个 row：(1) `Vol z-score` / `2.71` (2) `Drop 5d` / `-12.4%` (3) `Reversal day` / `是` | 单元 | vitest + @testing-library/react |
| T3 | DecisionPanelWidget 在 `setupType='BREAKOUT'` 时**不**渲染 3 chips（即使 capitulationEvidence 字段意外存在） | 单元 | vitest |
| T4 | DecisionPanelWidget 在 `setupType='CAPITULATION'` 但 `capitulationEvidence=null` 时**不**渲染 3 chips（防御 backend 异常） | 单元 | vitest |
| T5 | DecisionPanelWidget 在 `setupType='CAPITULATION'` 且 `reversalDay=false` 时 Reversal day chip 显示 `否`（false 分支） | 单元 | vitest |
| T6 | SetupTypeBadge `value='CAPITULATION'` 渲染含 `CAP_REV` label + 紫色 `var(--color-setup-capitulation)` 背景；`value='PULLBACK'` 仍保留紫色 + `PULLBACK` label 渲染（向后兼容） | 单元 | vitest |
| T7 | tokens.css `--color-setup-capitulation` 解析为 `#8b5cf6`（grep 验证；运行时 `getComputedStyle` 可选） | 静态 | grep + 可选 jsdom |
| T8 | 全量回归：`pnpm test`（vitest）跑现有 `DecisionPanelWidget.test.tsx` + `SetupMonitorWidget.test.tsx` + 其余前端测试 0 新增失败（PULLBACK fixture 仍工作因 union 未收紧） | 回归 | vitest |
| T9 | TS 编译 `pnpm tsc --noEmit`（或 `pnpm build`）0 type 错误 | 静态 | tsc |

---

## 4. 开发顺序（6 步，每步对应 1 wip commit）

每完成一步且最小验证通过，按 §7 显式 `git add <本步文件>` + `git commit -m "wip(F217-c2a): <step>"`。

| Step | 内容 | 验证 | wip commit message |
|------|------|------|---------------------|
| 1 | `tokens.css` 新增 `--color-setup-capitulation: #8b5cf6;` | grep 验证存在 + 不破坏其他 token | `wip(F217-c2a): tokens.css add capitulation color` |
| 2 | `cockpitDecisionApi.ts` 新增 `CapitulationEvidence` 类型 + `CockpitDecisionData.capitulationEvidence?` | `pnpm tsc --noEmit` 0 错误 | `wip(F217-c2a): cockpitDecisionApi CapitulationEvidence type` |
| 3 | `setupMonitorApi.ts` `SetupType` 追加 `\| 'CAPITULATION'` | `pnpm tsc --noEmit` 0 错误 | `wip(F217-c2a): setupMonitorApi SetupType +CAPITULATION` |
| 4 | `SetupTypeBadge.tsx` 三处追加 CAPITULATION（union / TYPE_COLORS / TYPE_LABELS） | `pnpm tsc --noEmit` 0 错误 + REPL 渲染 `<SetupTypeBadge value="CAPITULATION" />` 看不报错 | `wip(F217-c2a): SetupTypeBadge +CAPITULATION case` |
| 5 | `DecisionPanelWidget.tsx` 在 Earnings 区块后新增 3 chip 行（CAPITULATION + evidence 非空守卫） | 本地 `pnpm dev` 跑一个有 CAPITULATION setup 的 ticker，目视检查 3 chips 渲染（如无真实数据，跳到 Step 6 用 test 覆盖） | `wip(F217-c2a): DecisionPanelWidget 3 chips render` |
| 6 | 新建 `__tests__/DecisionPanelWidget.capitulation.test.tsx` T1-T5 + T6 SetupTypeBadge case + `pnpm test` 全过 | `pnpm test -- DecisionPanelWidget.capitulation` 5 tests pass + 全量回归 T8 0 新增失败 | `wip(F217-c2a): T1-T6 capitulation render tests` |
| 7 | Evaluator 自检（§5）+ T9 tsc 全过 + final commit | git status 清；`git add` 显式 6 文件名 | `feat(F217-c2a): frontend CAPITULATION additive render` |

**禁用 `git add -A`**，每步按上表文件显式 add。

---

## 5. Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] T1：`CapitulationEvidence` 类型可 import；字段名与 API-CONTRACT camelCase 一致
- [ ] T2-T5：`__tests__/DecisionPanelWidget.capitulation.test.tsx` 5 tests 全过
- [ ] T6：SetupTypeBadge CAPITULATION + PULLBACK 双 case 渲染正确（PULLBACK 向后兼容未破）
- [ ] T7：tokens.css `--color-setup-capitulation: #8b5cf6` grep 命中
- [ ] T8：全量 vitest 回归 0 新增失败（基线对齐 c1 done 后的最新 frontend 测试套件）
- [ ] T9：`pnpm tsc --noEmit` 0 type 错误
- [ ] API 响应字段名与 API-CONTRACT.md L1396-1424 一致（`capitulationEvidence` / `volZscore` / `drop5dPct` / `reversalDay`）
- [ ] PULLBACK 未删除：grep `'PULLBACK'` 在 6 个修改文件中应仍存在于 setupMonitorApi.ts + SetupTypeBadge.tsx（c2c 才删）
- [ ] tokens.css `--color-setup-pullback` 未删除（c2c 才删）
- [ ] design-spec.md 字节级别不变（c2c 才更新）
- [ ] 无 backend 改动（grep `backend/` 在本 sprint diff 应空）
- [ ] git status 清，6 文件全 commit
- [ ] WIP commits + 1 final feat commit 都在分支上

### 代码质量检查
- [ ] 无死代码（新增类型 / token / chip render 全部被引用）
- [ ] 无硬编码颜色（`#8b5cf6` 只出现在 tokens.css 一处，组件全用 `var(--color-setup-capitulation)`）
- [ ] 无重复样式（chip rowStyle/labelStyle/valueStyle 复用现有，不新建 styles）
- [ ] 无 console / debugger 遗留
- [ ] 函数长度合理（DecisionPanelWidget 新增 chip 块 < 15 行）
- [ ] 渲染保护：`data.capitulationEvidence && (...)` 守卫覆盖 null/undefined 双分支
- [ ] vitest 0 新增 warning（jsdom）

### 回归测试
- [ ] `pnpm test`（vitest）全量跑：当前 feature + 全量基线对齐
- [ ] 如全量回归出现预存失败（非本 sprint 引入）→ 记录到 Evaluator 报告，不阻塞 needs_review

---

## 6. 回滚策略

发现破坏性回归时按以下顺序回滚：

1. `git revert <feat-commit>` 删除 c2a 全部 6 文件改动（最快，因为 c2a 是 additive，回滚后系统回到 c1 done 状态，backend evidence API 仍存在但前端不渲染 chips，无破坏）
2. 单独回滚一个 wip commit：可选 `git revert <wip-commit>` 针对某个具体文件（如 chip 渲染坏了但 token 没问题）
3. 不需要 DB 迁移
4. 不破坏 c2b/c2c 依赖：c2b/c2c 必须在 c2a 完成后才进入，回滚后下游也未启动

---

## 7. Git Commit 规范

- **WIP（每步）**：`git add <本步文件>` + `git commit -m "wip(F217-c2a): <step>"`，**禁用 `-A`**
- **Final**：
  ```bash
  git add \
    frontend/src/styles/tokens.css \
    frontend/src/cockpit/lib/api/cockpitDecisionApi.ts \
    frontend/src/cockpit/lib/api/setupMonitorApi.ts \
    frontend/src/cockpit/components/SetupTypeBadge.tsx \
    frontend/src/cockpit/widgets/DecisionPanelWidget.tsx \
    frontend/src/cockpit/widgets/__tests__/DecisionPanelWidget.capitulation.test.tsx
  git commit -m "feat(F217-c2a): frontend CAPITULATION additive render"
  ```
- 不 squash wip commits（默认保留细粒度便于 bisect）

---

## 8. 风险与注意

- **PULLBACK 向后兼容**：本 sprint 故意保留 `'PULLBACK'` in `SetupType` union / `SetupTypeBadge.tsx` 三处 entry / tokens.css `--color-setup-pullback` token。c2b 测试 fixture 仍用 PULLBACK 可正常编译。c2c 才统一删 PULLBACK。误删 PULLBACK 会破坏 c2b 依赖链。
- **chip 数值单位陷阱**：backend `drop_5d_pct` 已是百分比 number（如 `-12.4` 表示 `-12.4%`），c2a 直接 `${value.toFixed(1)}%` 渲染。**勿** 误调 `fmtPct(value / 100)` 或 `fmtPct(value)`（fmtPct 接受 fraction 不是 percent）。test 应明确 assert `'-12.4%'` 而非 `-0.124%` 或 `-12.4000%`。
- **CAPITULATION 数据稀疏**：F217 SRS 设计意图触发频率 "每月几只"，本 sprint test 用合成 fixture 覆盖即可，不依赖真实数据。
- **AiSetupExplainerPopover 不在范围**：当前 SetupMonitorWidget 只 `import AiSetupExplainerPopover` 但 grep 无 JSX 使用，dead import 不影响 c2a。c2c 会改 Props.setupType + mapping（CAPITULATION→'reversal' NP-c2-3=A）。
- **token 同色性**：`--color-setup-capitulation: #8b5cf6` 与现有 `--color-setup-pullback: #8b5cf6` 同色值（紫色）。c2a 期间两个 token 并存，SetupTypeBadge PULLBACK case 引用旧 token、CAPITULATION case 引用新 token，UI 上紫色 badge 不区分 — 这是过渡期可接受现象（c2b 测试 fixture 用 PULLBACK 仍触发紫色，符合预期；c2c 删 PULLBACK 后只剩 CAPITULATION 紫）。
- **设计稿同步推迟**：design-spec.md 的紫色 + chips 视觉规格在 c2c 写最终态。本 sprint 不动 design-spec。
- **EvidenceChip 组件被拒**：NP-c2-5=A，不新建组件。如未来 chips 增多（如 F218 Repricing Trigger 新证据 chip），届时再考虑抽组件（YAGNI）。

---

👤 用户确认本 Contract 后，本 session **强制停止**，开 Sonnet 新 session 进入 Generator 模式从 Step 1 开始。
