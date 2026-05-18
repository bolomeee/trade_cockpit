---
status: confirmed
drafted_at: 2026-05-18
confirmed_at: 2026-05-18
sprint: F217-c2c
parent_feature: F217
---

# F217-c2c Sprint Contract — Union 收紧 -PULLBACK + 8 文件清理 + design-spec 更新

> 生成：2026-05-18 | 状态：草案 → 待用户确认
> Feature：[F217](docs/需求/features.json) Phase C — Capitulation Reversal 严格重写
> Sub-sprint：F217-c2c（前端 PULLBACK 收尾，与 backend b4 同形态）
> 前置：
>   - F217-c2a needs_review @ 2026-05-18（frontend additive CAPITULATION 渲染，6 文件落地）
>   - F217-c2b needs_review @ 2026-05-18（5 测试 fixture PULLBACK→CAPITULATION 迁移，10 处字面量替换）
>   - `SetupType` union 仍含 `'PULLBACK'`（待本 sprint 收紧）
>   - 所有 cockpit `__tests__/` 已无 PULLBACK 字面量（c2b commit 22c8aab 完成）
> 下游：F217 父 feature acceptance（c2a/c2b/c2c 三 sub-sprint 集中验收）

> 引用文档：
> - [API-CONTRACT.md](docs/系统设计/API-CONTRACT.md) §Cockpit Setup Monitor L1184 — `setupType` 枚举：`BREAKOUT / CAPITULATION / RECLAIM / EARNINGS_DRIFT / EXTENDED / BROKEN / NONE`（**已无 `PULLBACK`**，c1 完成时已对齐）
> - [DATA-MODEL.md](docs/系统设计/DATA-MODEL.md) §SetupSnapshot — `setup_type` 枚举同上
> - [DECISIONS.md](docs/系统设计/DECISIONS.md) §D095 — PULLBACK 历史移除，CAPITULATION 严格按 SRS § 五 Setup 4 重写
> - [F217-c2a-contract.md](docs/开发/sprint-contracts/F217-c2a-contract.md) — c2a additive 范围（CAPITULATION 加但保留 PULLBACK）
> - [F217-c2b-contract.md](docs/开发/sprint-contracts/F217-c2b-contract.md) — c2b fixture 迁移范围
> - [SESSION-HANDOFF.md](SESSION-HANDOFF.md) §3.2 — c2c 8 文件清单（用户授权超 6）

---

## 0. 拆分背景

原 F217-c2（前端 16 文件远超 6 上限）二次拆分（用户 2026-05-18 确认 NP-c2-1=A）：

- c2a ✅ needs_review：additive CAPITULATION 渲染（6 文件）
- c2b ✅ needs_review：5 测试 fixture PULLBACK→CAPITULATION 迁移（5 文件）
- **c2c（本 sprint）**：union 收紧 -PULLBACK + 8 文件清理 + design-spec 更新（8 文件，**已授权超 6**，与 backend b4 + NP-b3-1=A 同模式）

c2c 是 PULLBACK 退场最后一步。完成后：
- 前端 SetupType 类型联合不再含 PULLBACK，TS 编译期禁止 PULLBACK 字面量
- 旧 `--color-setup-pullback` token 退场，CAPITULATION 单独持有 `#8b5cf6`
- design-spec.md 完整描述最终态（无 PULLBACK 行 / SetupTypeBadge 7 枚举 / popover 渲染条件）

---

## 1. 本次实现范围

**包含**（8 个文件的 PULLBACK 引用清除 + 必要的 CAPITULATION 补齐）：

### 1.1 `frontend/src/cockpit/lib/api/setupMonitorApi.ts`
- **L5 删 `| 'PULLBACK'`**（union 收紧；其他 7 枚举保留）

### 1.2 `frontend/src/cockpit/components/SetupTypeBadge.tsx`
- **L3 删 `| 'PULLBACK'`**（本地 SetupType union；c2a 已加 'CAPITULATION'）
- **L14 删 `PULLBACK: 'var(--color-setup-pullback)',`** TYPE_COLORS 条目（c2a 已加 `CAPITULATION: 'var(--color-setup-capitulation)'`）
- **L24 删 `PULLBACK: 'PULLBACK',`** TYPE_LABELS 条目（c2a 已加 `CAPITULATION: 'CAP_REV'`）

### 1.3 `frontend/src/cockpit/lib/api/cockpitPoolApi.ts`
- **L32 inline union 删 `'PULLBACK'`**（PoolItem.setupType 改为 `'BREAKOUT' | 'RECLAIM' | 'EARNINGS_DRIFT' | 'EXTENDED' | 'BROKEN' | 'NONE' | null`）
- **NP-c2c-1 决策同步**：union 不加 CAPITULATION（PoolItem 是 cockpit pool 列表项，与 SetupType 全局 union 在 setupMonitorApi 已收敛；pool 不感知 CAPITULATION 自然走 null 分支，与现行 PULLBACK 同处理 — 待用户确认是否加。**草案推荐：不加，与 setupMonitorApi 的 SetupType 全局类型保持不一致是历史 anti-pattern，但 c2c 不引入新偏离**）⚠️ 见 §2 决策细节

### 1.4 `frontend/src/cockpit/widgets/_pendingOrderRow.tsx`
- **L60 inline union 删 `'PULLBACK'`**（同 1.3 处理）
- ⚠️ 见 §2 NP-c2c-3 决策（是否替换为 import 全局 SetupType）

### 1.5 `frontend/src/cockpit/dialogs/_pendingOrderFormSchemas.ts`
- **L6 删 `{ value: 'PULLBACK', label: 'PULLBACK' },`** dropdown 选项
- **同步加 `{ value: 'CAPITULATION', label: 'CAP_REV' },`**（NP-c2c-1=A：保持 dropdown 与 backend 枚举一致，c1 已让 backend 支持 CAPITULATION setup_type；不加则前端无法用 dropdown 创建 CAPITULATION 类型 pending order）
- 插入位置：紧邻 BREAKOUT 后（与 SetupTypeBadge 配色排序对齐：BREAKOUT → CAPITULATION → RECLAIM → EARN_DRFT → EXTENDED → BROKEN）⚠️ 见 §2 NP-c2c-1 决策

### 1.6 `frontend/src/cockpit/components/AiSetupExplainerPopover.tsx`
- **L17 SetupExplainerInput.setup union 不动**（`'pullback' | 'breakout' | 'reversal' | 'range' | 'gap_fill'` 是 backend setup_explainer AI task 的 input enum，归 backend 管控；本 sprint 不动 backend）
- **L32 Props.setupType 删 `'PULLBACK'`，加 `'CAPITULATION'`**：`'BREAKOUT' | 'RECLAIM' | 'CAPITULATION'`（NP-c2c-2=A：与 mapping 同步）
- **L42-46 mapping 改写**：
  ```ts
  const setup: 'breakout' | 'reversal' = (
    p.setupType === 'BREAKOUT' ? 'breakout' :
    p.setupType === 'CAPITULATION' ? 'reversal' :
    'reversal'
  )
  ```
  - 删 `p.setupType === 'PULLBACK' ? 'pullback' :` 分支
  - 加 `p.setupType === 'CAPITULATION' ? 'reversal' :` 分支（NP-c2-3=A：CAPITULATION 在 backend AI input 中归到 'reversal' 语义）
  - RECLAIM 仍走 'reversal' fallback（保持现状）
- **L42 局部类型 `'breakout' | 'pullback' | 'reversal'` 删 `'pullback'`** → `'breakout' | 'reversal'`

### 1.7 `frontend/src/styles/tokens.css`
- **L85 删 `--color-setup-pullback: #8b5cf6;`**（NP-c2c-5=A 保 #8b5cf6 不调色：c2a L90 已落 `--color-setup-capitulation: #8b5cf6`，PULLBACK 退场无视觉冲突）
- 注释 L83 `Cockpit Setup Type` 上下文保留（描述域未变）

### 1.8 `docs/设计/design-spec.md`（NP-c2c-4=C 全更新粒度）

- **L732 删 `Setup: PULLBACK` 表行**（color table 7 枚举对齐 SetupTypeBadge）
- **L731-737 加 `Setup: CAPITULATION` 表行**（紧邻 BREAKOUT 后）：
  ```markdown
  | Setup: CAPITULATION | `--color-setup-capitulation` | `#8b5cf6`（紫） | `SetupSnapshot.setup_type` |
  ```
- **L767 文字描述更新**：
  - 原文：`7 枚举 → 配色：BREAKOUT/PULLBACK/RECLAIM/EARNINGS_DRIFT/EXTENDED/BROKEN/NONE`
  - 改为：`7 枚举 → 配色：BREAKOUT/CAPITULATION/RECLAIM/EARNINGS_DRIFT/EXTENDED/BROKEN/NONE`
- **L988 popover 偏离说明更新**：
  - 原文：`仅 BREAKOUT / PULLBACK / RECLAIM 三种 setup 显示按钮`
  - 改为：`仅 BREAKOUT / CAPITULATION / RECLAIM 三种 setup 显示按钮`
- **L906 ASCII mockup**：`CRWD ... PULLBACK 0.80%` → `CRWD ... CAP_REV 0.80%`（与 TYPE_LABELS.CAPITULATION 渲染对齐）
- **L972 ASCII mockup**：`CRWD PULLBACK A ...` → `CRWD CAP_REV A ...`
- **L1088 ASCII mockup**：`CRWD PULLBACK 342.50` → `CRWD CAP_REV 342.50`
- **追加偏离说明**（doc footer 或对应 SetupTypeBadge 章节）：
  ```markdown
  > ⚠️ v2.2.0 F217 PULLBACK → CAPITULATION 替换（2026-05-18 完成）
  > 原始 Setup 枚举含 PULLBACK（MA21 回踩近似）；
  > 实际实现：SRS § 五 Setup 4 严格 Capitulation Reversal（7 条 AND 门），
  > token 与 label 同步替换：--color-setup-pullback / 'PULLBACK' label → --color-setup-capitulation / 'CAP_REV' label。
  > 见 DECISIONS.md §D095。
  ```

**明确排除（本次不做）**：

- backend 任何改动（c1 + b 系列已完成；c2c 纯 frontend + docs）
- 数据库 / schema 改动（alembic 021 已在 b1 落地）
- `__tests__/` 任何改动（c2b 完成）⚠️ 例外见 §1.9
- 新建测试文件（c2a 的 `DecisionPanelWidget.capitulation.test.tsx` 已落）
- `SetupMonitorWidget.tsx` 改动（含 NP-c2c-3=A：未渲染 popover 是独立议题）
- §S Setup Explainer Popover 11 个 pre-existing test 失败修复（NP-c2c-7=A：根因是 widget 未渲染 popover，超出 union 收紧范围）
- `--color-setup-capitulation` 色值调整（NP-c2c-5=A）
- 修改 `setup_explainer` AI task input enum（L17 `SetupExplainerInput.setup` 不动，backend 归口）
- `MarketBreakoutWidget` / `PullbackHistoryCard` / `PullbackWidget` / `PullbackEntry` 类型（**这些是 MA pullback signal / sma150 模块的 pullback 概念，与 SetupType.PULLBACK 不同语义，不在范围**）

### 1.9 测试文件例外：`DecisionPanelWidget.capitulation.test.tsx`

c2b Evaluator 报告显示该文件 L169/L171 仍含 PULLBACK 字面量（NP-c2b-2=A 保留：SetupTypeBadge fallback test 验证未知 setupType 时的渲染行为）。本 sprint 起 SetupType union 不再含 PULLBACK，TS 编译期会拒绝此处字面量。

- **决策（NP-c2c-8）**：
  - 选项 A：将 L169/L171 改为 `as any` cast 保留 fallback test 语义（验证未知值的兜底渲染）
  - 选项 B：将 L169/L171 改为另一个未在 union 中的字符串（例：`'UNKNOWN'`）保留 fallback test 语义
  - 选项 C：删除该 fallback test（PULLBACK union 退场后失去意义，但 SetupTypeBadge 仍有 `TYPE_LABELS[value] ?? value` fallback 逻辑需覆盖）
  - **推荐：B**（明确语义"未知 setup 类型走 fallback"，无 `any` 逃逸；改 1 处字符串字面量）
- 此例外不破坏 §1 的"不动 __tests__/"原则：c2b 完成时已知 c2c 必动此 1 文件，属计划内调整

⚠️ NP-c2c-8 与其他 NP 一起待用户确认；若选 B，c2c 范围变为 **9 文件**（仍在用户授权超 6 区间内）。

---

## 2. 预计修改文件（共 9 个 — 含 NP-c2c-8=B 推荐方案）

| # | 文件路径 | 改动类型 | 改动点数 | 说明 |
|---|---------|---------|---------|------|
| 1 | `frontend/src/cockpit/lib/api/setupMonitorApi.ts` | 修改 | 1 处 | L5 删 PULLBACK union 行 |
| 2 | `frontend/src/cockpit/components/SetupTypeBadge.tsx` | 修改 | 3 处 | L3 union / L14 TYPE_COLORS / L24 TYPE_LABELS 三条 PULLBACK 删除 |
| 3 | `frontend/src/cockpit/lib/api/cockpitPoolApi.ts` | 修改 | 1 处 | L32 inline union 删 PULLBACK |
| 4 | `frontend/src/cockpit/widgets/_pendingOrderRow.tsx` | 修改 | 1 处 | L60 inline union 删 PULLBACK |
| 5 | `frontend/src/cockpit/dialogs/_pendingOrderFormSchemas.ts` | 修改 | 2 处 | L6 删 PULLBACK option + 新增 CAPITULATION option |
| 6 | `frontend/src/cockpit/components/AiSetupExplainerPopover.tsx` | 修改 | 3 处 | L32 Props union -PULLBACK +CAPITULATION / L42 局部 union -'pullback' / L44 mapping -PULLBACK +CAPITULATION→'reversal' |
| 7 | `frontend/src/styles/tokens.css` | 修改 | 1 处 | L85 删 --color-setup-pullback |
| 8 | `docs/设计/design-spec.md` | 修改 | 7 处 | L732 删 PULLBACK 表行 + 新增 CAPITULATION 表行 / L767 文字描述更新 / L988 popover 偏离说明更新 / L906/L972/L1088 ASCII mockup 字面量 / 追加 v2.2.0 偏离说明 |
| 9 | `frontend/src/cockpit/widgets/__tests__/DecisionPanelWidget.capitulation.test.tsx` | 修改 | 2 处 | L169/L171 PULLBACK 字面量改为 'UNKNOWN'（NP-c2c-8=B fallback test 语义保留）|

👤 用户确认 9 文件清单合理后，方可进入开发。

### 决策细节（NP-c2c 系列）

**NP-c2c-1（_pendingOrderFormSchemas 删 PULLBACK 后是否加 CAPITULATION）**：
- 选项 A：删 PULLBACK + 加 CAPITULATION（dropdown 完整支持 backend 枚举）
- 选项 B：仅删 PULLBACK（用户无法用 dropdown 创建 CAPITULATION pending order）
- **推荐：A**（c1 已让 backend 支持 CAPITULATION setup_type，前端 dropdown 不加则功能不可达；插入位置紧邻 BREAKOUT 后与 SetupTypeBadge 排序对齐）

**NP-c2c-2（AiSetupExplainerPopover Props union 加 CAPITULATION 还是仅删 PULLBACK）**：
- 选项 A：删 PULLBACK + 加 CAPITULATION（与 mapping CAPITULATION→'reversal' 同步，union 完整）
- 选项 B：仅删 PULLBACK，不加 CAPITULATION（mapping 中 CAPITULATION 分支死代码）
- **推荐：A**（HANDOFF §3.2 表述 "Props -PULLBACK + mapping CAPITULATION→'reversal'" 暗示 union 必须含 CAPITULATION 才能让 mapping 路径可达）

**NP-c2c-3（_pendingOrderRow 和 cockpitPoolApi 的 inline union 是否替换为 import 全局 SetupType）**：
- 选项 A：保持 inline union（仅删 PULLBACK，不改设计模式）
- 选项 B：替换为 `import type { SetupType } from '../lib/api/setupMonitorApi'`（消除重复类型定义）
- **推荐：A**（B 改动超出 union 收紧范围，属重构议题；现有 3 处 inline union（cockpitPoolApi / _pendingOrderRow / SetupTypeBadge）均独立维护，c2c 不引入新偏离）
- 注：c2c 后 cockpitPoolApi.ts L32 / _pendingOrderRow.tsx L60 / SetupTypeBadge.tsx L3 / setupMonitorApi.ts L3 四处 SetupType union 完全一致（7 枚举 + null），是良好的可观察一致性；下次有 setup_type 变更时这 4 处需同步更新

**NP-c2c-4（design-spec.md 更新粒度）**：
- 选项 A：仅更新 color 表行 + L767 chips/枚举描述（最小集）
- 选项 B：A + 更新 L906/L972/L1088 ASCII mockup 中 PULLBACK 字面量
- 选项 C：A + B + L988 popover 描述更新 + 追加 v2.2.0 偏离说明
- **推荐：C**（最终态完整描述，避免文档"半旧不新"；ASCII mockup 是设计纪律，需与代码 label 渲染一致）

**NP-c2c-5（删 --color-setup-pullback 后 capitulation 是否调色）**：
- 选项 A：保持 #8b5cf6（c2a 落地色值，design-spec 也是 #8b5cf6）
- 选项 B：调整为新色（如 #6d28d9 深紫，区分于 MA20 紫）
- **推荐：A**（c2a Evaluator 已通过 #8b5cf6 视觉确认；PULLBACK 退场后无视觉冲突；调色超 c2c 范围）

**NP-c2c-6（commit 粒度）**：
- 选项 A：3 commits（src 类型清理 / tokens.css / design-spec.md）
- 选项 B：1 commit（refactor(F217-c2c): remove PULLBACK union + design-spec）
- 选项 C：9 wip commits 每文件一个
- **推荐：A**（清晰分层 + 便于 git bisect；design-spec doc 与 code 分开提交便于回滚 doc 不回滚 code）
- 三 commits 顺序：
  1. `refactor(F217-c2c): remove PULLBACK from frontend SetupType unions` — 文件 1-6（src 类型 + mapping）
  2. `chore(F217-c2c): remove --color-setup-pullback token` — 文件 7（tokens.css）
  3. `docs(F217-c2c): update design-spec for PULLBACK → CAPITULATION` — 文件 8 + 文件 9（design-spec.md + capitulation.test.tsx fallback fixture）

**NP-c2c-7（是否顺带修复 §S Setup Explainer Popover 11 个 pre-existing 失败）**：
- 选项 A：不修复（保留 pre-existing 状态，独立 sprint 处理）
- 选项 B：c2c 顺带分析根因并修复（可能需改 SetupMonitorWidget 渲染 popover，超 8 文件上限）
- 选项 C：c2c 完成后另开 F217-c3 / F218 处理
- **推荐：A**（根因排查：SetupMonitorWidget L16 import 但全文未渲染 `<AiSetupExplainerPopover>`，可能是 F209-c 实现偏离遗留；属另一议题，需独立分析；c2c 范围聚焦 union 收紧）
- 副作用：c2c 完成后 AiSetupExplainerPopover Props 从 `'BREAKOUT'|'PULLBACK'|'RECLAIM'` 改为 `'BREAKOUT'|'RECLAIM'|'CAPITULATION'`，但因 widget 未实际渲染该 popover，运行时无影响

**NP-c2c-8（DecisionPanelWidget.capitulation.test.tsx L169/L171 PULLBACK 字面量处理）**：
- 选项 A：`as any` cast 保留 fallback test 语义
- 选项 B：改为 `'UNKNOWN'` 字面量保留 fallback test 语义
- 选项 C：删除该 fallback test
- **推荐：B**（明确"未知 setup 类型走 fallback"语义；无 `any` 逃逸；改 1 处字符串字面量；SetupTypeBadge `TYPE_LABELS[value] ?? value` 兜底逻辑仍被覆盖）
- 注：c2b 完成时 NP-c2b-2=A 保留 L169/L171 是基于"union 仍含 PULLBACK"前提；c2c 收紧 union 后此前提失效，必须调整

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| T1 | `pnpm tsc --noEmit` 0 错误（src 9 文件 + 1 测试文件改动后 TS 编译通过） | 静态 | tsc |
| T2 | `grep -rn "'PULLBACK'\\|\"PULLBACK\"" frontend/src/cockpit/{components,widgets,dialogs,lib}/` 0 命中（src 层 setup-type PULLBACK 字面量完全清除） | 静态 | grep |
| T3 | `grep -rn "PULLBACK\\|pullback" frontend/src/cockpit/` 命中仅限：DecisionPanelWidget.capitulation.test.tsx 改写后的 'UNKNOWN' 字面量（**应为 0**）/ 其他无（确认 fixture 已迁移） | 静态 | grep |
| T4 | `grep -rn "setup-pullback" frontend/src/` 0 命中（CSS token 已删，无引用残留） | 静态 | grep |
| T5 | `grep -n "PULLBACK\\|setup-pullback" docs/设计/design-spec.md` 0 命中（doc 完全清除） | 静态 | grep |
| T6 | `pnpm test -- DecisionPanelWidget.capitulation` 全过（NP-c2c-8=B 改写后 fallback test 仍验证未知值走 `TYPE_LABELS[value] ?? value` 兜底） | 单元 | vitest |
| T7 | `pnpm test -- SetupTypeBadge` 全过（如有专属测试；否则该 case 在 widget 集成测试中覆盖） | 单元 | vitest |
| T8 | 全量 `pnpm test` 通过数 ≥ c2b 基线（22/28 suites 通过 = 17 pre-existing failures）；0 新增失败 | 回归 | vitest |
| T9 | SetupTypeBadge 渲染 CAPITULATION value 时：`color: var(--color-setup-capitulation)` + `label: 'CAP_REV'`（c2a 已落，本 sprint 不应破坏） | 静态 + 视觉 | grep + 手动 |
| T10 | _pendingOrderFormSchemas 新增 CAPITULATION option 在 dropdown 中可选（`grep -n "CAPITULATION" frontend/src/cockpit/dialogs/_pendingOrderFormSchemas.ts` 命中 L7 新增行） | 静态 | grep |
| T11 | AiSetupExplainerPopover Props.setupType 接受 CAPITULATION：`pnpm tsc --noEmit` 不报错（c2a setupType union 已含 CAPITULATION，本 sprint Props 同步） | 静态 | tsc |
| T12 | backend 0 改动：`git diff --stat HEAD~ -- backend/` 空 | 静态 | git diff |
| T13 | `__tests__/` 改动仅限 capitulation.test.tsx 1 文件：`git diff --name-only HEAD~ -- frontend/src/**/__tests__/` 仅显示该 1 文件 | 静态 | git diff |
| T14 | git status 工作区清；3 commits 落地（refactor + chore + docs） | 静态 | git status / git log |

---

## 4. 开发顺序（3 个语义层 commit）

| Step | 内容 | 验证 | commit |
|------|------|------|--------|
| 0 | `grep -rn "'PULLBACK'\\|\"PULLBACK\"" frontend/src/cockpit/` 枚举所有 PULLBACK 命中点（应 6 处 src + 2 处 capitulation.test.tsx fallback），对照 §1 清单 100% 覆盖 | grep 结果对照 §2 表 | （不 commit） |
| 1 | 改文件 1-6（src 类型清理）：<br>1. setupMonitorApi.ts L5 -PULLBACK<br>2. SetupTypeBadge.tsx L3/L14/L24 -PULLBACK<br>3. cockpitPoolApi.ts L32 -PULLBACK<br>4. _pendingOrderRow.tsx L60 -PULLBACK<br>5. _pendingOrderFormSchemas.ts L6 -PULLBACK +CAPITULATION<br>6. AiSetupExplainerPopover.tsx L32/L42/L44 -PULLBACK +CAPITULATION→'reversal' | `pnpm tsc --noEmit` 0 错误 | `refactor(F217-c2c): remove PULLBACK from frontend SetupType unions` |
| 2 | 改文件 7（tokens.css）：L85 删 `--color-setup-pullback: #8b5cf6;` | `grep -n "setup-pullback" frontend/src/` 0 命中 | `chore(F217-c2c): remove --color-setup-pullback token` |
| 3 | 改文件 8（design-spec.md）：color 表 PULLBACK 行 → CAPITULATION 行 / L767 文字 / L988 popover 偏离 / L906/L972/L1088 ASCII mockup / 追加 v2.2.0 偏离说明<br>改文件 9（capitulation.test.tsx）：L169/L171 PULLBACK → 'UNKNOWN' fallback fixture | `grep -n "PULLBACK\\|setup-pullback" docs/设计/design-spec.md` 0 命中 + `pnpm test -- DecisionPanelWidget.capitulation` 全过 | `docs(F217-c2c): update design-spec for PULLBACK → CAPITULATION` |
| 4 | 全量回归 `pnpm test` 对照 c2b 基线（22/28 suites 通过，17 pre-existing failures） | 0 新增失败 | （不 commit） |
| 5 | Evaluator 自检（§5） | git status 清；3 commits 落地 | （Evaluator 模式无 commit） |

**Step 1 commit 命令**（显式列文件，禁 -A）：
```bash
git add \
  frontend/src/cockpit/lib/api/setupMonitorApi.ts \
  frontend/src/cockpit/components/SetupTypeBadge.tsx \
  frontend/src/cockpit/lib/api/cockpitPoolApi.ts \
  frontend/src/cockpit/widgets/_pendingOrderRow.tsx \
  frontend/src/cockpit/dialogs/_pendingOrderFormSchemas.ts \
  frontend/src/cockpit/components/AiSetupExplainerPopover.tsx
git commit -m "refactor(F217-c2c): remove PULLBACK from frontend SetupType unions"
```

**Step 2 commit 命令**：
```bash
git add frontend/src/styles/tokens.css
git commit -m "chore(F217-c2c): remove --color-setup-pullback token"
```

**Step 3 commit 命令**：
```bash
git add \
  docs/设计/design-spec.md \
  frontend/src/cockpit/widgets/__tests__/DecisionPanelWidget.capitulation.test.tsx
git commit -m "docs(F217-c2c): update design-spec for PULLBACK → CAPITULATION"
```

**说明**：3 commit 分层（src refactor / token chore / docs+fallback fixture）便于按层 review 与 bisect。

---

## 5. Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

### 静态检查
- [ ] T1：`pnpm tsc --noEmit` 0 错误
- [ ] T2：`grep -rn "'PULLBACK'\\|\"PULLBACK\"" frontend/src/cockpit/{components,widgets,dialogs,lib}/` 0 命中
- [ ] T3：`grep -rn "PULLBACK" frontend/src/cockpit/` 0 命中（capitulation.test.tsx 已改 'UNKNOWN'）
- [ ] T4：`grep -rn "setup-pullback" frontend/src/` 0 命中
- [ ] T5：`grep -n "PULLBACK\\|setup-pullback" docs/设计/design-spec.md` 0 命中
- [ ] T12：`git diff --stat HEAD~3 -- backend/` 空（HEAD~3 因 3 commits）
- [ ] T13：`git diff --name-only HEAD~3 -- frontend/src/**/__tests__/` 仅 capitulation.test.tsx

### 测试
- [ ] T6：`pnpm test -- DecisionPanelWidget.capitulation` 5/5 tests 通过（T1-T5 c2a 落地的 capitulation 渲染 test + fallback test）
- [ ] T7：`pnpm test -- SetupTypeBadge` 全过（若有专属 spec）
- [ ] T8：`pnpm test` 全量 通过 / 失败 / 跳过数对照 c2b 基线（22/28 suites = 17 pre-existing failures），0 新增失败
- [ ] T11：AiSetupExplainerPopover Props.setupType=CAPITULATION 实例化不报 TS 错误

### 视觉/语义
- [ ] T9：SetupTypeBadge value=CAPITULATION 渲染 `color: var(--color-setup-capitulation)` + label `'CAP_REV'`
- [ ] T10：_pendingOrderFormSchemas dropdown 含 `{ value: 'CAPITULATION', label: 'CAP_REV' }`，不含 PULLBACK option

### 文档同步
- [ ] design-spec.md color 表 7 行 setup-* 与 SetupTypeBadge TYPE_COLORS / tokens.css 三向一致
- [ ] design-spec.md L767 文字描述 7 枚举与 SetupType union（setupMonitorApi.ts）一致
- [ ] design-spec.md L988 popover 偏离说明与 AiSetupExplainerPopover Props.setupType 三枚举一致
- [ ] design-spec.md 追加 v2.2.0 F217 偏离说明（与 DECISIONS.md §D095 互相引用）

### 代码质量
- [ ] 无新增死代码（c2c 是删除 + 重命名，不应引入新 import / 函数）
- [ ] 无注释残留 PULLBACK 字面量（除非作为偏离对比说明，本 sprint 仅 design-spec 偏离说明保留）
- [ ] AiSetupExplainerPopover L42 局部 union `'breakout' | 'reversal'` 是有效 TS 类型，无 `as` 强转
- [ ] _pendingOrderFormSchemas CAPITULATION option 插入位置在 BREAKOUT 后（与 SetupTypeBadge 配色排序对齐）

### 回归
- [ ] `pnpm test` 全量跑：通过数 ≥ 22 suites、新增失败 = 0
- [ ] 如出现 §S Setup Explainer Popover 测试通过/失败状态变化（基线 11 fail）：报告用户，分析根因
- [ ] 如出现 c2a 6 文件中任一 token / Badge / chips 渲染回归：打回 Generator

### consistency-check
- [ ] Evaluator 通过后**强制**调用 consistency-check skill (mode=interactive) 校验：
  - C1：F217-c2c 升 needs_review 后，sibling 状态：c2a needs_review / c2b needs_review / c2c needs_review — **F217 父 feature 保持 in_progress**（acceptance 跑过 3 个 sub-sprint 才能升 done）
  - C4：F217-c2c 在 iteration_history 应有 needs_review 条目
  - C5：F217-c2c 在 sub_sprints 字段中存在（已确认 design_needed）

---

## 6. 回滚策略

- **3 commits 独立回滚**：
  - 回滚 docs commit（doc fixture only）：不影响代码运行
  - 回滚 tokens.css commit：恢复 `--color-setup-pullback` token，PULLBACK 引用立即恢复视觉（但 src 类型已退场，运行时无 PULLBACK 字面量）
  - 回滚 src refactor commit：恢复 PULLBACK union，类型与 c2a/c2b 完整闭包恢复
- **逆序回滚**：`git revert HEAD HEAD~1 HEAD~2`（一次撤 3 commits 回 c2b 状态）
- 不涉及 DB / schema 改动（c2c 纯 frontend + docs）
- 不影响 backend（c1 已落 + b 系列已固化）

---

## 7. Git Commit 规范

- 3 commits 类型：`refactor` / `chore` / `docs`，不用 `feat`（c2c 不引入新功能，是收尾清理）
- 禁用 `git add -A`，显式列文件名（防止跨 sprint 污染）
- commits 顺序固定：refactor → chore → docs（src 改动落地后再清理 token 再更新文档，与依赖关系一致：doc 描述代码当前状态）

---

## 8. 风险与注意

- **PULLBACK 字面量在 `frontend/src/types/stockDetail.ts` / `market.ts` / `MarketBreakoutWidget.tsx` / `PullbackHistoryCard.tsx` / `PullbackWidget.tsx` 等 sma150 模块仍存在**：这些是 **MA pullback signal** / **PullbackEntry** 概念，与 SetupType.PULLBACK 是不同语义实体（不同 API、不同 widget），**严格不在 c2c 范围**。Evaluator T2/T3 grep 路径限定 `frontend/src/cockpit/` 避免误判。
- **`SetupMonitorWidget` import AiSetupExplainerPopover 未使用**：实测 `<AiSetupExplainerPopover>` JSX 0 命中。该 widget 渲染 setup row 时未挂载 explainer popover，这是 §S 11 个 pre-existing failures 的根因。NP-c2c-7=A 决策：c2c 不处理，独立 sprint。**但 c2c 改 Props union 后**，未使用的 import 在 `pnpm tsc --noEmit` 仍通过（unused import 是 lint 警告非 TS 错误），无回归。
- **`SetupExplainerInput.setup` (L17) 含 `'pullback'` 不删**：这是 backend `setup_explainer` AI task 的 input schema 字段，归 backend 管控（属 F211 AI schema 范围）。c2c 不动 backend，因此前端类型保留 `'pullback'` 字面量；mapping 函数 (L42-46) 中也不再触达此分支（前端 setupType union 已无 PULLBACK），属"前端无法传入但 backend 仍可接受"的安全过渡态。后续若要清理 backend 端，开 F217-c3 或 F221（独立 sprint）。
- **`_pendingOrderFormSchemas` 新增 CAPITULATION option 视觉对齐**：label 用 'CAP_REV'（与 SetupTypeBadge TYPE_LABELS.CAPITULATION 一致）；dropdown 排序紧邻 BREAKOUT 后（与 design-spec.md L731 color 表排序对齐）。
- **`as const` 与字面量类型保留**：无 sprint c2b 类似的 `as const` 注意点；c2c 改 union 时无 tuple readonly 需求。
- **design-spec.md ASCII mockup 字面量长度**：原 `PULLBACK` 8 字符，新 `CAP_REV` 7 字符；mockup 行可能因长度变化影响列对齐。**改动时保持原列宽**（在 PULLBACK 后多 1 空格补齐 8 字符）或接受 1 字符偏移（mockup 是示意，非渲染规格）。**推荐：补 1 空格保列宽**，避免 mockup 字符表错位影响阅读。
- **`AiSetupExplainerPopover` mapping CAPITULATION→'reversal'**：与 NP-c2-3=A 决策一致 — Capitulation Reversal 在 backend AI input 中归到 'reversal' 语义（投降反转 = reversal 大类），不动 backend setup_explainer 枚举。
- **c2a 的 PULLBACK token 引用**：c2a 落地时为了 backward compat 保留了 SetupTypeBadge.tsx L14 `PULLBACK: 'var(--color-setup-pullback)'`。c2c Step 1 删除此 L14 行 + Step 2 删除 tokens.css L85 token 定义，二者必须同 PR 内完成（中间态会有 `var(--color-setup-pullback)` 无定义引用，CSS 解析为空字符串导致 PULLBACK badge 渲染默认色）。**Step 1 与 Step 2 不可拆分到不同 sprint**，但 commit 顺序可控：Step 1 先 → Step 2 后（src 删引用 → token 删定义，确保中间态无未引用的 token）。
- **NP-c2c-3=A inline union 保留偏离**：cockpitPoolApi.ts L32 / _pendingOrderRow.tsx L60 仍维护 inline SetupType union 复本（与 setupMonitorApi.ts 的全局 SetupType 不复用 import）。c2c 后这 3 处 union 完全一致（7 枚举 + null），但下次有 setup_type 变更时仍需手工同步 3 处。**建议在 DECISIONS.md 追加 D097**（或合并到 D095）说明此可观察偏离，便于未来 setup_type 变更扫描。

---

## 9. Sprint 完成后 sub_sprints 状态预期

- `F217.sub_sprints.F217-c2c`: `design_needed` → `contract_agreed`（本 contract 确认后）→ `in_progress` → `testing` → `needs_review`
- `F217.sub_sprints.F217-c2a`: 保持 `needs_review`（等 acceptance 才能升 done）
- `F217.sub_sprints.F217-c2b`: 保持 `needs_review`（等 acceptance）
- `_pipeline_status.active_sprint`: F217-c2b → F217-c2c
- `_pipeline_status.active_sprint_phase`: needs_review → contract_agreed → ... → needs_review
- F217 父 feature：保持 `in_progress`（C1 invariant：c2a/c2b/c2c 三 sub-sprint 全 done 才允许升 done；acceptance 集中验收三 sub-sprint 后才升）

---

## 10. Acceptance 衔接

c2c needs_review 后：
- 触发 acceptance skill 集中验收 c2a / c2b / c2c 三 sub-sprint（同一 release F217 范围）
- acceptance 通过后：
  - sub_sprints.F217-c2a/c2b/c2c 升 `done`
  - F217 父 feature 升 `done`（C1 invariant 满足）
  - features.json `_pipeline_status.active_sprint` 清空或推进至下一 feature
  - iteration_history 追加 acceptance 条目（参考 c1 acceptance 模式：docs/验收/v2.2.0-F217-c1-acceptance.md）

---

👤 用户确认本 Contract 后，本 session **强制停止**，开 Sonnet 新 session 进入 Generator 模式从 §4 Step 0 grep 验证开始。

---

## 待用户确认的关键决策汇总

| NP | 议题 | 推荐 | 影响 |
|----|------|------|------|
| c2c-1 | _pendingOrderFormSchemas 加 CAPITULATION option | A 加 | 文件 5 改动 +1 处 |
| c2c-2 | AiSetupExplainerPopover Props union 加 CAPITULATION | A 加 | 文件 6 改动语义 |
| c2c-3 | inline union 是否重构为 import 全局 SetupType | A 保持 inline | 不引入 c2c 范围外重构 |
| c2c-4 | design-spec.md 更新粒度 | C 全更新（含 ASCII mockup） | 文件 8 改 7 处 |
| c2c-5 | --color-setup-capitulation 是否调色 | A 保 #8b5cf6 | 0 改动 |
| c2c-6 | commit 粒度 | A 3 commits（refactor/chore/docs） | git history 分层 |
| c2c-7 | 是否顺带修复 §S 11 pre-existing | A 不修 | 范围聚焦 |
| c2c-8 | capitulation.test.tsx L169/171 PULLBACK fallback fixture | B 改 'UNKNOWN' | +1 文件（共 9 文件） |

**如全部按推荐 → 9 文件，3 commits**。
