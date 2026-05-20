# SESSION-HANDOFF — F218-d7b contract_agreed → 下一步 Generator 模式

> 生成：2026-05-20 (Opus 4.7) | 用途：下一 session 进入 feature-dev A-2 Generator
> 触发：用户全 A 确认 NP-d7b-1~7，Sprint Contract 转 confirmed

---

## 1. 当前状态

| 字段 | 值 |
|------|-----|
| `_pipeline_status.active_sprint` | **F218-d7b** |
| `_pipeline_status.active_sprint_phase` | **contract_agreed** |
| `F218.phase` | in_progress |
| `F218.active_sub_sprint` | F218-d7b |
| `F218.active_sprint_phase` | contract_agreed |
| `F218.sub_sprints["F218-d7a"]` | done ✅ |
| `F218.sub_sprints["F218-d7b"]` | **contract_agreed** ✅ |

---

## 2. F218-d7b Sprint Contract 摘要

**文档**：[F218-d7b-contract.md](docs/开发/sprint-contracts/F218-d7b-contract.md)（status=confirmed）

**目标**：闭合 Phase D 全栈环 — 前端消费 d7a 已上线的 2 endpoint，落地 RepricingTriggerWidget + DecisionPanel chip 区。

**预计修改文件清单（10 文件，4 新建 + 6 修改，用户授权 10 文件例外同 F217-c2c）**：

| # | 文件 | 性质 | LOC | 步骤所属 |
|---|------|------|-----|---------|
| 1 | `frontend/src/cockpit/lib/api/cockpitRepricingApi.ts` | 新建 | ~80 | Step 1 |
| 2 | `frontend/src/cockpit/lib/api/__tests__/cockpitRepricingApi.test.ts` | 新建 | ~140 | Step 1 |
| 3 | `frontend/src/styles/tokens.css` | 修改 | +7 | Step 2 |
| 4 | `frontend/src/cockpit/widgets/RepricingTriggerWidget.tsx` | 新建 | ~220 | Step 3 |
| 5 | `frontend/src/cockpit/widgets/__tests__/RepricingTriggerWidget.test.tsx` | 新建 | ~280 | Step 3 |
| 6 | `frontend/src/cockpit/CockpitRegistry.ts` | 修改 | +10 | Step 4 |
| 7 | `frontend/src/cockpit/widgets/DecisionPanelWidget.tsx` | 修改 | +60 | Step 5 |
| 8 | `frontend/src/cockpit/widgets/__tests__/DecisionPanelWidget.test.tsx` | 修改 | +120 | Step 5 |
| 9 | `docs/设计/design-spec.md` | 修改 | +90 | Step 6 |
| 10 | `docs/设计/component-plan.md` | 修改 | +2 | Step 6 |

**完成标准**：23 新测试 + DecisionPanel 既有 ~30 测试无回归 + lint/typecheck 通过 + consistency-check (C1/C4/C5) 全清。

---

## 3. 已确认决策（NP-d7b-1~7 全 A）

| # | 决策点 | 落定值 |
|---|--------|--------|
| NP-d7b-1 | 5 类 trigger 色板 | 绿 #15803d / 青 #0891b2 / 桃 #db2777 / 琥珀 #d97706 / 紫 #7c3aed（避开既有 setup/signal token 冲突） |
| NP-d7b-2 | widget 默认布局 | `x:6 y:43 w:6 h:10`（与 Weekly Stage 同行右半） |
| NP-d7b-3 | DecisionPanel chip 区位置 | header 行下方常驻区，body 状态分支之前 |
| NP-d7b-4 | 分页策略 | v1.0 limit=100 + "显示 N / 总 M" 文本，v2.0 再扩展虚拟滚动 |
| NP-d7b-5 | chip 简称 | EarningsAccel / MarginExp / NewProduct / SectorCycle / BalanceInflect |
| NP-d7b-6 | refresh 按钮 | title bar 右上角图标按钮（仿 PoolBuilderWidget） |
| NP-d7b-7 | 开发顺序 | vertical slice 优先（API → widget → registry → chip → 文档 → 测试） |

---

## 4. 开发顺序（Generator 模式，7 步）

每步通过最小验证后立即 **wip commit**（规则 7 强制，按文件名显式 add，禁 `-A`）：

### Step 1：API client + 类型 + 单测（文件 1, 2）
- 实装 `cockpitRepricingApi.ts`：5 类 evidence union + 2 函数 + URLSearchParams
- 写 6 个单测（A1-A6：upper / no-params / with-params / empty / 422 / TypeScript narrow）
- 验证：`pnpm test cockpitRepricingApi`
- wip commit：`wip(F218-d7b): step1 API client + 6 tests`

### Step 2：5 类 trigger 色 token（文件 3）
- `tokens.css` 追加 5 个 `--color-trigger-*`（在既有 `--color-setup-*` 块后）
- 验证：visual diff（无具体测试，但 widget 渲染会消费）
- wip commit：`wip(F218-d7b): step2 trigger color tokens`

### Step 3：RepricingTriggerWidget + 单测（文件 4, 5）
- 实装 widget：表格 + filter Select + refresh 按钮 + 5 状态机
- 提取 helper：`summarizeEvidence(t)` + `TRIGGER_COLOR_TOKEN` map
- 写 9 个单测（B1-B9）
- 验证：`pnpm test RepricingTriggerWidget`
- wip commit：`wip(F218-d7b): step3 widget + 9 tests`

### Step 4：CockpitRegistry 注册（文件 6）
- 追加 `'cockpit.repricing-trigger'` manifest
- 扩展 `CockpitWidgetCategory` union 加 `'repricing'`
- 写 2 个测试（D1-D2）
- 验证：dev server 启动看到 widget 在 cockpit 页可见
- wip commit：`wip(F218-d7b): step4 registry + 2 tests`

### Step 5：DecisionPanel chip 区 + 单测增量（文件 7, 8）
- 在 DecisionPanelWidget 内插入 `RepricingChipRow` helper component
- 调用 `useQuery(['cockpit-repricing-ticker', ticker], ...)`
- 5 状态分支：null ticker / empty triggers / loading / error / data
- chip 视觉：5 类色 token 16% alpha 背景 + shadcn Tooltip evidence 摘要
- 写 6 个增量测试（C1-C6），既有 ~30 测试无回归
- 验证：`pnpm test DecisionPanelWidget`
- wip commit：`wip(F218-d7b): step5 DecisionPanel chip + 6 tests`

### Step 6：文档内联（文件 9, 10）
- `design-spec.md`：§Widget 6 DecisionPanel 补 "Repricing chip 区" 子段 + 新增 §Widget X RepricingTrigger（参考 WeeklyStageChartWidget 模板）
- `component-plan.md`：cockpit widgets 表追加一行
- wip commit：`wip(F218-d7b): step6 docs inline sync`

### Step 7：Evaluator 收尾
- 全量前端测试：`pnpm test`
- lint：`pnpm lint`
- typecheck：`pnpm typecheck`
- 浏览器手动验（E1/E2）：cockpit 页可见 widget + DecisionPanel chip 联动
- consistency-check (mode=interactive scope=F218) 全清
- 更新 features.json：F218-d7b → needs_review
- 最终 commit：`feat(F218-d7b): Repricing Trigger 前端 widget + DecisionPanel chip 区`

---

## 5. 关键技术约束（不可违反）

- **6 文件原则例外**：本 sprint 10 文件用户已授权（同 F217-c2c），但 Generator 期间禁止再加文件；如确实需要再加，停止报告
- **禁 `git add -A`**：每次 commit 按文件名显式 add，参照上表清单
- **wip commit 不可省**：每 step 通过最小验证后立即 commit，避免长 context 丢失整个 sprint
- **DecisionPanel 既有 ~30 测试无回归**：Step 5 改动需严格控制在最小侵入（仅 insert chip 区，不动既有 if/else 分支）
- **API client 类型严格**：5 类 evidence union 不用 `any` 兜底，narrow 必须靠 `switch (trigger.triggerType)`
- **color token 必须用变量**：widget / chip 内 color 全部 `var(--color-trigger-*)`，不写硬编码
- **字段命名**：API 返回 camelCase（API-CONTRACT.md 已定义），前端类型直接 camelCase，禁中间层 snake_case 转换
- **空状态契约**：单 ticker / 全市场两个 endpoint 都返 200 空数组（不抛 404），前端按此分支

---

## 6. 引用文档

- [F218-d7b Sprint Contract](docs/开发/sprint-contracts/F218-d7b-contract.md) — 完整规格 + AC + 自检清单
- [API-CONTRACT.md §1988-2106](docs/系统设计/API-CONTRACT.md) — 2 endpoint 契约
- [DATA-MODEL.md §1080-1129](docs/系统设计/DATA-MODEL.md) — RepricingTrigger + 5 类 evidence schema
- [design-spec.md §1000-1047](docs/设计/design-spec.md) — DecisionPanelWidget 既有规格（chip 区将插入位置）
- [component-plan.md §339-352](docs/设计/component-plan.md) — cockpit widgets 注册表
- [SetupMonitorWidget.tsx](frontend/src/cockpit/widgets/SetupMonitorWidget.tsx) — 表格 widget 样板
- [cockpitPoolApi.ts](frontend/src/cockpit/lib/api/cockpitPoolApi.ts) — API client URLSearchParams 样板
- [F218-d7a-contract.md](docs/开发/sprint-contracts/F218-d7a-contract.md) — 上游 sprint 输出

---

## 7. 下一 session 启动指令

**复制以下指令到新 session（推荐 Sonnet 4.6）**：

```
继续开发 F218-d7b，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F218-d7b-contract.md，
进入 feature-dev A-2 Generator 模式，从 Step 1（cockpitRepricingApi.ts + 6 单测）开始。
每步通过最小验证后立即 wip commit（按文件名显式 add，禁 git add -A）。
```

---

## 8. 收官路径（d7b 完成后）

1. d7b Evaluator 全绿 → sub_sprints["F218-d7b"] = needs_review
2. consistency-check C1：sub_sprints 全升 done/needs_review 时父 F218 保持 in_progress
3. 触发 acceptance skill（F218-d7b needs_review）
4. acceptance 通过 → sub_sprints["F218-d7b"] = done
5. consistency-check C1 自动触发 → 父 F218 → done（**Phase D 整体收官，cockpit 4 支柱齐全**）
6. 下一目标：cockpit-vs-srs-framework 改善计划 4 阶段全部完成（Phase A/B/C/D），考虑 v2.4 → v2.5 release
