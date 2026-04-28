# Sprint Contract：F211-b — DecisionPanel Contradictions 区前端

> 状态：草案，待用户确认 | 起草：2026-04-28
> 父 Feature：F211 AI Contradiction Detector + News Summarizer + Journal Assistant
> 拆分位置：F211-a1 ✅ done / F211-a2 ✅ done / **F211-b（本 sprint）** / F211-c / F211-d
> 依赖：
>   - F208-c ✅（POST /api/ai/{task_type} 统一 endpoint，本 sprint 直接复用 callAiTask）
>   - F211-a1 ✅（contradiction_detector schema + REGISTRY + guardrail 已注册）
>   - F211-a2 ✅（per-task model override 基建，本 sprint 不动后端）
>   - F210-b ✅（AiTradePlanSection 已落地，是本 sprint 的结构与样式直接参考）
> 引用文档：
>   - design-spec.md line 1009-1014（DecisionPanelWidget 中 "AI Contradictions（v2.0，F211）" 区块设计）
>   - design-spec.md line 1119（AI Brief 折叠态默认收起；展开时调 `POST /api/ai/contradiction_detector`）
>   - component-plan.md line 348（DecisionPanelWidget 数据源：`POST /api/ai/contradiction_detector`）
>   - component-plan.md line 456（v2.0 AI Daily Brief 折叠区：默认收起；展开时调 contradiction_detector）
>   - API-CONTRACT.md line 1660-1718（POST /api/ai/{task_type} 通用 endpoint + meta 字段）
>   - backend/app/ai/schemas/contradiction_detector.py（input/output Pydantic schema 权威，前端类型与之 1:1 映射）
>   - frontend/src/cockpit/components/AiTradePlanSection.tsx（结构 / state machine / cache badge / token 使用模板）
>   - frontend/src/cockpit/lib/api/aiApi.ts（callAiTask 已通用化，无需扩展）
>   - frontend/src/cockpit/lib/api/cockpitDecisionApi.ts（CockpitDecisionData 字段表）
>   - frontend/src/cockpit/lib/api/setupMonitorApi.ts（trendScore / rsPercentile / readySignal 来源）
>   - frontend/src/cockpit/lib/api/cockpitRegimeApi.ts（regime / marketScore 来源）

---

## 0. 背景与定位

F211-a1/a2 已完成后端基建：`contradiction_detector` task_type 的 Pydantic schema 已注册，POST `/api/ai/contradiction_detector` 可直接调用。F211-b 在 DecisionPanelWidget 内补齐前端展示，对照 design-spec line 1009-1014：

```
│  ── AI Contradictions（v2.0，F211）────────────────────────── │
│  ⚠ Earnings in 28d (LOW)                                     │
│  ⚠ R:R 2.0 (MEDIUM, prior resistance ~870)                   │
│  Recommendation: Open at 75% sized                            │
```

参考 F210-b 落地的 AiTradePlanSection：默认 collapsed → 用户点 trigger → useQuery enabled → POST → 渲染列表 + recommendation。形态、cache 策略、关闭按钮、错误状态全部对齐 trade_plan 区块，避免视觉破碎。

**关键约束**：
1. **不动后端**：schema / endpoint / guardrail 已就绪，本 sprint 0 行后端代码改动。
2. **lazy 触发**：默认 collapsed，避免每次 selectedTicker 切换都打 LLM（D069 月预算考虑）。
3. **input 来源混合**：contradiction_detector input schema 需要 13 个字段，`CockpitDecisionData` 只能提供其中 8 个；剩余 5 个（trendScore / rsPercentile / readySignal / regime / regimeScore）从 setupMonitor + regime 两个 react-query cache 读取。**不**新增专用 endpoint。
4. **缺数据降级**：当 setupMonitor 中找不到当前 ticker（用户从 Chart 选了 scan 范围外的 ticker）→ trigger 按钮 disabled + tooltip 提示。
5. **不引入新依赖**：复用 `@tanstack/react-query` / `@/components/ui/skeleton` / 现有 token 变量。

---

## 1. 实现范围

### 1.1 包含

#### A. 新建 `AiContradictionsSection.tsx`（第 1 文件）

位置：`frontend/src/cockpit/components/AiContradictionsSection.tsx`
模板参考：`AiTradePlanSection.tsx`（同目录、同 props 形态）

**Props**：
```typescript
type Props = {
  decision: CockpitDecisionData
}
```

**内部读取的额外 react-query cache（不新增 fetch 触发，复用 SetupMonitorWidget / MarketRegimeWidget 已挂载的 queries）**：

| 数据 | queryKey | 读取方式 | 用途 |
|------|----------|---------|------|
| setupMonitor items | `['setup-monitor', undefined]` 或 `['setup-monitor']` | `useQuery({ enabled: open, ... })` 同 key 复用 cache | 找 `items.find(i => i.ticker === decision.ticker)` 取 trendScore / rsPercentile / readySignal |
| cockpitRegime | `['cockpit-regime']` | 同上 | 取 `regime` + `marketScore`（→ regimeScore） |

> **实施细节**：先用 `useQueryClient().getQueryData()` 探测；若两份 cache 任一缺失，trigger 按钮 disabled + `title="等待 Setup Monitor / Regime 数据加载"`。打开后再用 `useQuery` 主动拉取（与已有 widget 同 key，react-query 自动 dedupe，不会双发 request）。

**Input builder**：
```typescript
function buildContradictionInput(
  decision: CockpitDecisionData,
  setupItem: SetupItem,        // 必须存在，否则不渲染 trigger
  regime: CockpitRegimeData,   // 必须存在
): ContradictionDetectorInput {
  return {
    ticker: decision.ticker,
    setupType: decision.setupType,
    setupQuality: decision.setupQuality,
    trendScore: setupItem.trendScore,
    rsPercentile: setupItem.rsPercentile,
    entry: decision.entryPrice,
    stop: decision.stopPrice,
    target2r: decision.target2r,
    rewardRisk: decision.rewardRisk,
    accountRiskPct: decision.accountRiskPct,
    earningsRisk: decision.earningsRisk,        // null OK
    daysToEarnings: calcDaysUntil(decision.earningsDate),  // null OK
    regime: regime.regime,
    regimeScore: regime.marketScore,
    readySignal: setupItem.readySignal,
  }
}
```

> **calcDaysUntil 共享**：当前 DecisionPanelWidget.tsx 内有同名 helper（line 23）。本 sprint **重构**：把它从 widget 文件中提取到新 `AiContradictionsSection.tsx`（或更上层的 `cockpit/lib/utils/dates.ts`）后，DecisionPanelWidget.tsx 改 import。**实施时**优先方案 A（提到 lib/utils/dates.ts 让两边都 import），因 F211-c News bar 也大概率需要类似日期计算。

**State machine**（沿用 AiTradePlanSection 的 6 态）：

| 态 | 触发 | 渲染 |
|----|------|------|
| **closed**（默认） | 初始 | `<button>Generate AI Contradictions</button>`（与 trade plan trigger 同样 outline 按钮风格）；如果 setupItem 或 regime 缺失，按钮 disabled + tooltip |
| **loading** | open && (isLoading \|\| (isFetching && !data)) | header + 2 行 Skeleton（短行 = recommendation；长矩形 = contradictions list） |
| **error**（非 409） | error && !is409 | "AI 暂不可用" + close 按钮（沿用 trade_plan 错误样式） |
| **error 409** | guardrail violation | 红色 banner "AI 输出被拦截"（contradiction_detector 当前无 hash guardrail，但保留 409 处理路径以与 trade_plan 一致） |
| **success — 有矛盾** | data.output.contradictions.length > 0 | header + cache badge + 列表 + recommendation |
| **success — 无矛盾** | data.output.contradictions.length === 0 | header + cache badge + recommendation 单行（"No major contradictions"） |

**列表项视觉规范**：

每条 contradiction 渲染一行：

```
⚠ {text}  [SEVERITY_TAG]
```

- 前缀：`⚠`（HIGH/MEDIUM）/ `·`（LOW），用 inline span
- text：`var(--font-size-caption)`，`var(--color-text-primary)`
- severity tag：右对齐的 inline badge（高度 16px，padding 0 6px，圆角 2px，font-size badge）
  - HIGH → 背景 `color-mix(in srgb, var(--color-error) 20%, transparent)`，前景 `var(--color-error)`
  - MEDIUM → 背景 `color-mix(in srgb, var(--color-signal-warning) 20%, transparent)`，前景 `var(--color-signal-warning)`
  - LOW → 背景 `color-mix(in srgb, var(--color-text-muted) 12%, transparent)`，前景 `var(--color-text-secondary)`

> **token 校验前置**：开发步骤 1 必须 `grep --color-signal-warning frontend/src/styles/tokens.css`（或对应 token 文件）确认存在。若不存在 → 改用 `--color-warning` / `--color-amber` 等已存在 token，并在本 contract 实施段加备注。

**Recommendation 行**：列表下方留 6px 间距，渲染 `Recommendation: {output.recommendation}`，font-size body，color text-primary。空列表时仍显示此行（AI 兜底为 "No major contradictions"）。

**queryKey**：`['ai', 'contradiction_detector', decision.ticker, decision.deterministicHash]`

理由：与 AiTradePlanSection 一致；后端 ai_memos 用完整 input_hash 去重，前端 24h cache 防误触发。`trendScore` 等次要字段变化时 deterministicHash 不会变，前端读旧值；该限制与 F210-b 已有的 trade_plan 一致，留作 F211-d 月度复盘后整体优化窗口（非本 sprint 范围）。

**staleTime / gcTime**：`24 * 60 * 60 * 1000`（与 trade_plan 一致）。

**类型定义**（写在 component 文件内部，参考 AiTradePlanSection 的 TradePlanInput / TradePlanOutput）：

```typescript
type Severity = 'LOW' | 'MEDIUM' | 'HIGH'
type ContradictionType = 'earnings_risk' | 'reward_risk' | 'trend_quality' | 'extension' | 'regime_misfit' | 'volume' | 'other'

type ContradictionItem = {
  type: ContradictionType
  severity: Severity
  text: string
}

type ContradictionDetectorInput = { /* 见 input builder */ }

type ContradictionDetectorOutput = {
  contradictions: ContradictionItem[]
  recommendation: string
}
```

**导出**：`export function AiContradictionsSection(props: Props): JSX.Element`

#### B. 修改 `DecisionPanelWidget.tsx`（第 2 文件）

位置：`frontend/src/cockpit/widgets/DecisionPanelWidget.tsx`
改动范围：≤30 行 diff

1. import `AiContradictionsSection`
2. 在 line 393-399 的 AiTradePlanSection 块后追加：
   ```tsx
   <div
     data-testid="ai-contradictions-divider"
     style={{ borderTop: '1px solid var(--color-border)', paddingTop: '8px', marginTop: '4px' }}
   >
     <AiContradictionsSection decision={data} />
   </div>
   ```
3. **可选** 把 `calcDaysUntil` helper 抽到 `cockpit/lib/utils/dates.ts`（见 §1.1.A 的 calcDaysUntil 共享段）。

> **实施时机**：步骤 2 完成 component 内 logic 之前先做 helper 抽取（步骤 0），防止两个文件各自定义同名函数 drift。

#### C. 修改 `DecisionPanelWidget.test.tsx`（第 3 文件）

位置：`frontend/src/cockpit/widgets/__tests__/DecisionPanelWidget.test.tsx`
新增测试 case ≥ 7 条（与 §3 测试用例 1:1）

#### D. 新建 `cockpit/lib/utils/dates.ts`（第 4 文件，conditional）

仅在采用 §1.1.A "calcDaysUntil 共享方案 A" 时新建。内容仅 1 个 helper：

```typescript
export function calcDaysUntil(dateIso: string | null): number | null {
  if (!dateIso) return null
  const ms = new Date(dateIso + 'T00:00:00Z').getTime() - Date.now()
  return Math.round(ms / 86400000)
}
```

> 若开放问题 Q3 决定不抽公共 helper（用 inline 复制），本文件不新建，文件总数从 5 降到 4。默认采纳抽取。

#### E. 更新 `features.json`（第 5 文件）

- `sub_sprints["F211-b"]` 由 `design_needed` → `contract_agreed`（A-1 阶段）
- `iteration_history` 追加 1 条 contract_agreed 记录

### 1.2 排除（明确不在本 sprint）

- F211-c News 页 AI 摘要 bar（独立 sprint）
- F211-d 平仓 hook + journal_entries.ai_review 迁移（独立 sprint）
- 新增任何后端文件 / endpoint / schema 改动
- 任何与 ActionListWidget "AI Daily Brief" 折叠区相关的实现（design-spec line 1119 提到，但属于 F207 后续迭代或 F211-d 范围，本 sprint 不实施）
- 任何修改 SetupMonitorWidget / MarketRegimeWidget queryKey 或 queryFn 的工作（仅复用，不动）
- 设计偏离回写 / DECISIONS 新增（除非开发期间发现意外）

---

## 2. 预计修改文件清单（共 5 个，含 1 个 conditional）

| # | 路径 | 状态 | 说明 |
|---|------|------|------|
| 1 | `frontend/src/cockpit/components/AiContradictionsSection.tsx` | 新建 | 主组件，~250 行 |
| 2 | `frontend/src/cockpit/widgets/DecisionPanelWidget.tsx` | 修改 | 引入 + 渲染 + helper 引用切换；~10 行 diff |
| 3 | `frontend/src/cockpit/widgets/__tests__/DecisionPanelWidget.test.tsx` | 修改 | +7 case，~250 行新增 |
| 4 | `frontend/src/cockpit/lib/utils/dates.ts` | 新建（conditional） | calcDaysUntil helper 提取，~6 行；若 Q3 默认采纳此方案则建，否则跳过 |
| 5 | `docs/需求/features.json` | 修改 | sub_sprints + iteration_history |

总计：5 文件（≤6 文件上限 ✅）；若放弃 helper 抽取（Q3 不默认）则 4 文件。

---

## 3. 测试用例 / 完成标准

| # | 测试描述 | 层级 | 工具 | 备注 |
|---|---------|------|------|------|
| 1 | closed 态：渲染 "Generate AI Contradictions" trigger 按钮 | 单元（widget test） | vitest + RTL | data-testid="ai-contradictions-trigger" |
| 2 | trigger 点击 → 进入 loading → 显示 skeleton | 单元 | vitest + RTL | mock callAiTask 慢响应 |
| 3 | success 有矛盾：列表渲染 N 条 + recommendation；severity tag 颜色正确（HIGH/MEDIUM/LOW 三类各 1 条） | 单元 | RTL + getComputedStyle 断言 inline style | data-testid="ai-contradictions-item-{i}" + "ai-contradictions-recommendation" |
| 4 | success 无矛盾：contradictions=[] 时只渲染 "No major contradictions" recommendation 行 | 单元 | RTL | 不出现 list item |
| 5 | error 502：渲染 "AI 暂不可用" + close 按钮 | 单元 | RTL + ApiError mock | 关闭按钮回到 closed 态 |
| 6 | error 409：渲染红色 guardrail banner（即使 contradiction_detector 当前无 hash guardrail，路径要保留） | 单元 | RTL + ApiError(409) mock | 与 trade_plan 一致 |
| 7 | setupMonitor 中不含当前 ticker → trigger 按钮 disabled + title "需 Setup Monitor 数据" | 单元 | RTL | data-testid="ai-contradictions-trigger" 仍存在但 disabled 属性 true |
| 8 | DecisionPanelWidget 完整渲染流：data 加载完成后能看到 trade_plan + contradictions 两个 section（divider 都在） | 集成（widget test） | RTL | 现有测试套件追加 |
| 9 | 全量回归：现有 vitest 套件 0 回归（含 DecisionPanelWidget 现有测试 + AiTradePlanSection 间接覆盖） | 回归 | `pnpm vitest run` | 必须 |
| 10 | TypeScript 编译通过：`pnpm tsc --noEmit` 0 error | 类型 | tsc | 必须 |

> **不写**：playwright e2e（cockpit 现状未配 e2e，与 F210-b 同；走 vitest + RTL 已足够覆盖交互）。

### Evaluator 自检清单

- [ ] 6 + 1 个组件状态全部 RTL 测试覆盖（closed / loading / error 502 / error 409 / success-with / success-empty / disabled）
- [ ] DecisionPanelWidget 完整渲染流测试通过（含 contradictions divider）
- [ ] severity tag 三种颜色对照 design-spec line 1009-1014 所述风格 + tokens.css 实存 token
- [ ] cache badge 复用 trade_plan 现有逻辑（cacheHit=true → "Cached"；否则 `Generated · {modelUsed}`）
- [ ] queryKey 含 deterministicHash → 切换 ticker 重新触发 fetch
- [ ] setupMonitor / regime cache 缺失时 trigger 正确 disable
- [ ] daysToEarnings 计算与 DecisionCard 现有显示（D-{n}）一致（来自共享 helper 验证）
- [ ] component-plan.md 已记载 `POST /api/ai/contradiction_detector` 为 DecisionPanelWidget 数据源（line 348），无需更新文档
- [ ] design-spec.md line 1009-1014 的视觉描述全部呈现（AI Contradictions header / 两条警告 / Recommendation 行）
- [ ] 全量 vitest 0 回归
- [ ] tsc --noEmit 0 error
- [ ] biome check 0 新增 warning（项目 lint 命令）
- [ ] 无 console.error / console.warn 遗留（开发期临时打印必须删）
- [ ] 无硬编码颜色（必须走 token CSS variable）
- [ ] 函数 ≤50 行（否则拆分）

---

## 4. 开放问题（默认方案，确认后执行）

| Q# | 问题 | 默认方案 | 替代 |
|----|------|----------|------|
| Q1 | trigger 按钮文案？ | "Generate AI Contradictions"（与 "Generate AI Plan" 句式平行） | "Detect Contradictions" / "Show AI Risk Audit" |
| Q2 | 列表项前缀？HIGH/MEDIUM 用 ⚠，LOW 用 ·（中点） | 同左 | 全部用 ⚠；或全部不带前缀只靠 severity tag 区分 |
| Q3 | calcDaysUntil 是否抽到 lib/utils/dates.ts？ | **抽**（DRY；F211-c 大概率复用） | 不抽，AiContradictionsSection 内复制一份；总文件数减 1 |
| Q4 | severity tag 用 token？ | HIGH=`--color-error`，MEDIUM=`--color-signal-warning`，LOW=`--color-text-muted/secondary` | 如果 `--color-signal-warning` 不存在 → 在步骤 1 切换到 `--color-warning` / `--color-amber` 等已存 token |
| Q5 | setupMonitor 当前 filter 状态 → 影响 cache 复用 | 用 queryKey `['setup-monitor', undefined]`（默认无 filter）；若 SetupMonitorWidget 当前用 filters，cache miss 时再触发一次无 filter 的拉取 | 抽专用 hook 让两个 widget 共享同一个无 filter 全集查询；本 sprint 不动，留作后续 |
| Q6 | contradiction_detector 当前后端无 hash guardrail，前端是否仍处理 409？ | **保留** 409 分支（与 trade_plan 模板一致；未来后端如加 guardrail，前端零改动） | 不保留，error 502 单分支处理所有错误 |
| Q7 | "Recommendation:" 前缀文案？ | `Recommendation: {output.recommendation}`（design-spec line 1014 原文） | 简化为单行无前缀 |
| Q8 | 是否在 trigger 旁加 token cost 预览？ | 不加（cache badge 在 success 态展示已足够；trigger 态展示会让用户犹豫） | 加小字 "≈ $0.001"（需后端额外字段 / 前端硬编码） |
| Q9 | 是否限制 contradictions 列表最大显示条数？ | 不限制（schema 已限 max=5，无需前端再 cap） | 限制 3 + "… N more" |
| Q10 | divider 与 AI Trade Plan 之间的视觉间距？ | 复用 AI Trade Plan divider 同款（borderTop + 8px padding-top + 4px margin-top） | 加大间距 / 隐藏 divider 让两个 section 视觉合并 |

> 所有 Q 默认采纳。Q4 / Q5 中 token / cache 假设须在开发步骤 1 实测验证；任何不一致 → 停止报告。

---

## 5. 开发顺序（A-2 Generator 模式遵循）

1. **预检**（≤30 min）
   - `grep` 确认 `--color-signal-warning` / `--color-error` / `--color-text-muted` 在 tokens.css 实存
   - `grep` 确认 `setup-monitor` / `cockpit-regime` queryKey 在现有 widget 中的精确写法
   - 读取 backend/app/ai/schemas/contradiction_detector.py 全文，对照 §1.1.A 类型定义
2. **helper 抽取**：新建 `cockpit/lib/utils/dates.ts`，DecisionPanelWidget.tsx import 切换；手动 vitest 跑 widget 既有测试 0 回归后 wip commit
3. **AiContradictionsSection 骨架**：closed + disabled 两态 + props + queryKey 占位
4. **类型定义 + input builder**：与 backend schema 对齐
5. **state machine 完整化**：loading / success-with / success-empty / error / 409 五态
6. **severity tag 视觉**：grep token → 实施 inline style
7. **DecisionPanelWidget 集成**：import + 渲染 divider + section
8. **测试**：扩展 DecisionPanelWidget.test.tsx 覆盖 §3 7 个新 case + 1 个集成 case
9. **Evaluator 模式**：跑全套 vitest + tsc + biome；自检清单逐条打勾
10. **更新 features.json + 最终 commit + SESSION-HANDOFF**

每完成 2-3 步骤做一次 wip commit（按 Generator 规则 7）。

---

## 6. 不在本 sprint 范围内的提醒

- **F211-c News 页 AI 摘要 bar**：独立 sprint，需要碰 News.tsx（cockpit 外的 F112 遗留页面），范围与文件耦合关系完全不同，本 sprint 完成后单独协商
- **F211-d 月度 cron + journal_entries.ai_review 迁移**：涉及 Alembic migration + scheduler，由独立 sprint 落地
- **AiContradictionsSection 在 ActionListWidget 的复用**：design-spec line 1119 / component-plan line 351 提到 ActionListWidget 也会调 contradiction_detector 用于 "AI Daily Brief"，但属于 F207 增强或 F211-d 后续迭代，本 sprint **不**做 component 复用准备（保持 DecisionPanel 内部组件而非 shared）；若后续需复用，提取到 `cockpit/components/shared/` 的工作量一日内可完成

---

## 7. 完成后状态

- features.json：`sub_sprints["F211-b"]` → `done`，新增 iteration_history 1 条
- 父 feature F211：保持 in_progress（c/d 仍未做）
- F211 5 段进度：a1 ✅ + a2 ✅ + b ✅ + c ⬜ + d ⬜
