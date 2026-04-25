# Sprint Contract：F209-c — AI Setup Explainer Popover（SetupMonitor 每行）

> 状态：草案，待用户确认 | 起草：2026-04-25
> 父 Feature：F209 Market Narrator + Setup Explainer（v2.0 Cockpit P2 AI 层）
> 兄弟：F209-a ✅ done / F209-b ✅ done / **F209-c（本 sprint，最后一块 F209）**
> 依赖：F209-a ✅（POST /api/ai/setup_explainer 可用）+ F209-b ✅（aiApi.ts 通用客户端）+ F202-c ✅（SetupMonitorWidget shell）
> 引用文档：
>   - API-CONTRACT.md §POST /api/ai/{task_type}（line 1655-1734：统一 envelope / 错误码 / setup_explainer 在 7 task 枚举内）
>   - design-spec.md §Widget 5 SetupMonitorWidget（line 945-973：表格交互 + 每行 [?] 触发 setup_explainer）
>   - data-mapping.md line 778 / 981（setup_explainer hover 映射 + 错误统一）
>   - features.json#F209-c（acceptance_criteria 6 条）
>   - backend/app/ai/schemas/setup_explainer.py（输入/输出 Pydantic schema 权威）
>   - DECISIONS.md D064 / D069 / D074

---

## 0. 背景与定位

F209-a 后端已就位 `POST /api/ai/setup_explainer`，F209-b 已落地通用 `callAiTask<TIn, TOut>` 客户端 + ApiError 错误码识别。本 sprint 在 **不改 SetupMonitorWidget 已有 9 列渲染逻辑** 的前提下，于表格右侧追加第 10 列 `?` 按钮，点击展开 shadcn/ui Popover，调用 `setup_explainer` 并显示 label / quality / whyWatch / mainRisks。

设计上的关键约束：
1. AI 区是 **可选增强**，失败/超预算时 popover 内显示占位文案，**不影响行其他列、不影响 setSelectedTicker 联动**。
2. **24h 缓存** 由 server-side `ai_memos` 处理；前端 react-query `gcTime` 同步至 24h，session 内复点 0 网络。
3. **不加前端 cooldown**——每行 input 唯一（ticker + setupType），无 spam 风险。
4. **触发方式：点击** `?` 按钮（非 hover）——按 features.json acceptance_criteria 优先于 design-spec 描述；design-spec line 972 需打偏离标注（规则 8）。

---

## 1. 实现范围

### 1.1 包含

#### 1.1.1 `frontend/src/cockpit/components/AiSetupExplainerPopover.tsx`（新建）

可复用的 popover 组件，封装"按钮 + Popover + 内容渲染"。Props：

```ts
type Props = {
  ticker: string
  setupType: 'BREAKOUT' | 'PULLBACK' | 'RECLAIM'  // 仅 3 种被支持
  trendScore: number
  rsPercentile: number
  entryPrice: number   // > 0
  stopPrice: number    // > 0
}
```

**输入构造（仅在 popover 打开时执行）**：

```ts
function buildSetupExplainerInput(p: Props): SetupExplainerInput {
  const setup = (
    p.setupType === 'BREAKOUT' ? 'breakout' :
    p.setupType === 'PULLBACK' ? 'pullback' :
    'reversal'  // RECLAIM
  ) as const
  const trend =
    p.trendScore >= 60 ? 'up' :
    p.trendScore <= 40 ? 'down' :
    'sideways'
  return {
    ticker: p.ticker,
    trend,
    rs: p.rsPercentile,                  // int → float OK
    setup,
    risk: { entry: p.entryPrice, stop: p.stopPrice },
  }
}
```

**类型与调用**：

```ts
import { callAiTask, type AiTaskResponse } from '../lib/api/aiApi'

export type SetupExplainerInput = {
  ticker: string
  trend: 'up' | 'down' | 'sideways'
  rs: number
  setup: 'pullback' | 'breakout' | 'reversal' | 'range' | 'gap_fill'
  risk: { entry: number; stop: number }
}

export type SetupExplainerOutput = {
  label: string
  quality: 'A' | 'B' | 'C' | 'D'
  whyWatch: string
  mainRisks: string[]
}
```

> 注：`SetupExplainerInput`/`Output` 类型**就近定义在本组件文件**。理由：aiApi.ts 已是通用客户端，避免按 task 累积类型；F210/F211 各 task 同样在自己组件内定义类型。

**useQuery 行为**：

```ts
const { data, isLoading, isFetching, error } = useQuery({
  queryKey: ['ai', 'setup_explainer', ticker, setupType],
  queryFn: () => callAiTask<SetupExplainerInput, SetupExplainerOutput>(
    'setup_explainer',
    buildSetupExplainerInput(props),
  ),
  enabled: open,                        // 仅 popover 打开后请求
  staleTime: 24 * 60 * 60 * 1000,       // 24h，与服务端 ai_memos TTL 对齐
  gcTime: 24 * 60 * 60 * 1000,
  retry: false,
})
```

**渲染（4 个状态）**：

| 状态 | 渲染 |
|------|------|
| 加载（isLoading 或 isFetching）| 3 行 `Skeleton`（label 行 / whyWatch 段 / mainRisks 列表占位）|
| 错误（任意 ApiError）| 单行 `AI 暂不可用` (`var(--color-text-secondary)`) |
| 成功 | label（粗体）+ Quality 徽章 + whyWatch 段 + mainRisks 列表（• 项）|
| 关闭 | `enabled: open` 控制不发请求 |

**触发按钮**：

```tsx
<Popover open={open} onOpenChange={setOpen}>
  <PopoverTrigger asChild>
    <button
      aria-label={`Explain ${ticker} ${setupType} setup`}
      onClick={(e) => e.stopPropagation()}    // 阻止冒泡到 <tr> 的 setSelectedTicker
      style={{
        background: 'none', border: 'none', cursor: 'pointer',
        color: 'var(--color-text-muted)',
        fontSize: 'var(--font-size-caption)', padding: '2px 4px',
      }}
    >?</button>
  </PopoverTrigger>
  <PopoverContent align="end" sideOffset={4} style={{ width: 280 }}>
    {/* 4 状态渲染 */}
  </PopoverContent>
</Popover>
```

#### 1.1.2 `frontend/src/cockpit/widgets/SetupMonitorWidget.tsx`（修改）

变更点（最小化，不动既有逻辑）：

1. `<thead>` 追加第 10 列 `<Th width="5%">?</Th>`（`<Th width="14%">Ticker`不变，其余列宽各 -0.5%）
2. `<SetupRow>` 追加第 10 个 `<td>`：
   - 仅当 `setupType ∈ {BREAKOUT, PULLBACK, RECLAIM}` 且 `entryPrice > 0` 且 `stopPrice > 0` 时渲染 `<AiSetupExplainerPopover />`
   - 其他 setup（EARNINGS_DRIFT / EXTENDED / BROKEN / NONE）渲染空 `<td>`，保持列对齐
3. 不修改既有 `onClick → setSelectedTicker` 行为；按钮 `e.stopPropagation()` 隔离

> 列宽精确分配（合计 100%）：Ticker 14 / Setup 16 / Q 5 / Entry 11 / Stop 11 / R:R 7 / Dist 9 / RS 7 / Earn 8 / **? 5** / 余 7（缓冲）— 实际由 `tableLayout: fixed` 自动分摊，本 sprint **不重排已有列宽**，仅新增 `width="5%"` 第 10 列，其余 9 列保持现值（总和会从 91% 升至 96%，浏览器自适应填充剩余）。如视觉异常，按需微调 `Dist`/`RS` -1%。

#### 1.1.3 `frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx`（修改 / 扩展）

新增测试 §S — Setup Explainer Popover（11 用例，复用 F209-b `makeRoutedFetch` 路由 mock 模式）：

| # | 用例 | 类型 |
|---|------|------|
| S1 | BREAKOUT 行渲染 `?` 按钮 | 单元 |
| S2 | PULLBACK 行渲染 `?` 按钮 | 单元 |
| S3 | RECLAIM 行渲染 `?` 按钮 | 单元 |
| S4 | EARNINGS_DRIFT 行不渲染 `?` 按钮 | 单元 |
| S5 | EXTENDED 行不渲染 `?` 按钮 | 单元 |
| S6 | BROKEN 行不渲染 `?` 按钮 | 单元 |
| S7 | 点击 `?` 不触发 setSelectedTicker（stopPropagation）| 集成 |
| S8 | 点击 `?` 后调用 POST /api/ai/setup_explainer，body 含正确 input mapping（BREAKOUT→breakout / trend 映射 / risk）| 集成 |
| S9 | 加载期间 popover 显示 Skeleton | 集成 |
| S10 | 成功响应渲染 label / quality / whyWatch / mainRisks | 集成 |
| S11 | 错误响应（502 AI_PROVIDER_ERROR）显示"AI 暂不可用"，setSelectedTicker 行点击仍正常 | 集成 |

> 测试架构沿用 F209-b 经验：`makeRoutedFetch` 按 URL 路由，setup-monitor 接口返回 fixture，setup_explainer 按场景返回成功 / 错误。fixtures 用最小行集合（每个 setupType 1 行 = 7 行）。

---

### 1.2 排除（明确不做）

- ❌ **不改后端 `setup_explainer` schema**（不增加 EARNINGS_DRIFT / EXTENDED / BROKEN 枚举）
- ❌ **不加 widget 级 Refresh 按钮**（无 spam 风险，无需 cooldown）
- ❌ **不加 hover 触发**（features.json 优先；点击足够）
- ❌ **不动 setupMonitorApi.ts 类型**（trendScore / rsPercentile 字段保留 number/int）
- ❌ **不影响 deterministic 列（setup_type / setup_quality）**——AI 仅在 popover 内展示，不覆盖表格
- ❌ **不动 aiApi.ts**（已是通用客户端，无需扩展）
- ❌ **不写新 e2e**（集成测试覆盖已足够；e2e 留 acceptance 阶段视觉确认）
- ❌ **不动 store / 路由 / WidgetShell 框架**

---

## 2. 预计修改文件清单（共 3 个，**远低于** 6 文件上限）

| 路径 | 操作 | 预计行数变化 |
|------|------|-------------|
| `frontend/src/cockpit/components/AiSetupExplainerPopover.tsx` | 新建 | +130 |
| `frontend/src/cockpit/widgets/SetupMonitorWidget.tsx` | 修改 | +12 / -0 |
| `frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx` | 修改 | +220 |

**附加可能（不计入 6 文件上限，规则 8 触发的回写）**：
- `docs/设计/design-spec.md`：line 972 添加 1 段"实现偏离"标注（hover → click），约 +5 行

---

## 3. 完成标准（可测试，每条都能给出 ✅/❌ 结论）

| # | 完成标准 | 测试层级 | 工具 |
|---|---------|---------|------|
| C1 | BREAKOUT/PULLBACK/RECLAIM 行渲染 `?` 按钮，其余 4 种 setup 不渲染 | 单元 | vitest + RTL |
| C2 | `?` 按钮位置在 Earn 列右侧（第 10 列），不破坏既有列对齐 | 视觉 | preview_screenshot（acceptance 阶段）|
| C3 | 点击 `?` 调用 `POST /api/ai/setup_explainer`，body 为 `{ input: { ticker, trend, rs, setup, risk: { entry, stop } }, noCache: false }` 且 setup 字段为映射后小写枚举 | 集成 | vitest + fetch mock |
| C4 | 点击 `?` 不触发 `setSelectedTicker`（不改 selectedTicker store）| 集成 | vitest + zustand |
| C5 | 加载期间 popover 显示 Skeleton（3 个）| 集成 | vitest + RTL |
| C6 | 成功响应渲染 label / Quality 徽章 / whyWatch / mainRisks 列表 | 集成 | vitest + RTL |
| C7 | 502 错误显示"AI 暂不可用"，点击行其余区域 setSelectedTicker 正常 | 集成 | vitest + fetch mock |
| C8 | 同 ticker+setupType 二次打开同一 popover，react-query 缓存命中（fetch 调用计数 = 1）| 集成 | vitest + fetch spy |
| C9 | 类型检查通过 `pnpm tsc --noEmit` | 工程 | tsc |
| C10 | Lint 通过 `pnpm lint`（无新增 warning）| 工程 | eslint |
| C11 | 全量回归：所有 frontend 测试通过（cockpit + workbench + 共享）| 回归 | vitest run |
| C12 | design-spec.md line 972 已标注偏离（hover → click），符合规则 8 | 文档 | grep |

---

## 4. 开发顺序（Generator 模式严格执行）

```
1. 确认 DATA-MODEL.md 无需改动 → ✅（不动 DB）
2. 确认 API-CONTRACT.md 已涵盖 → ✅（F209-a 已涵盖 setup_explainer）
3. 数据库迁移 → ⏭ 跳过（无 schema 变更）
4. Repository → ⏭ 跳过（前端 sprint）
5. Service → ⏭ 跳过
6. API Route → ⏭ 跳过
7. 单元测试 + 集成测试 → 与 step 8 交叠（TDD 友好，先写关键 fixture）
8. 前端组件 →
   8a. 新建 AiSetupExplainerPopover.tsx（含类型 + buildInput + useQuery + 4 状态渲染）
   8b. SetupMonitorWidget.tsx 追加第 10 列 + 条件渲染按钮
   8c. SetupMonitorWidget.test.tsx 扩展 §S 11 用例
   8d. 写完 8a-c 后跑 `pnpm test` 验证 §S 全绿 + 既有用例无回归
9. design-spec.md 偏离标注（规则 8 强制）
10. tsc + lint 全绿
11. Evaluator 模式自检
```

每步通过最小验证后立即 wip commit（`git add` 显式列文件，禁用 `-A`）：
- step 8a → `wip(F209-c): popover component skeleton`
- step 8b → `wip(F209-c): widget integration`
- step 8c → `wip(F209-c): tests §S green`
- step 9 → `chore(F209-c): design-spec deviation note`

---

## 5. Evaluator 自检清单

- [ ] 单元测试：S1-S6 全部通过
- [ ] 集成测试：S7-S11 全部通过
- [ ] 缓存测试 C8 通过
- [ ] 类型检查：`cd frontend && pnpm tsc --noEmit` 无错
- [ ] Lint：`cd frontend && pnpm lint` 无新增 warning
- [ ] 全量回归：`cd frontend && pnpm test --run`，所有既有 tests 仍绿
- [ ] API body 字段名严格符合 backend `SetupExplainerInput` schema（小写 setup 枚举 / trend 字符串 / risk 对象嵌套）
- [ ] Quality 徽章复用 `SetupQualityBadge` —— ⚠️ 需确认：现有 SetupQualityBadge 接受 'A'|'B'|'C'|null，但 schema output quality 含 `'D'`。**决策点**：
  - 选项 A：扩展 `SetupQualityBadge` 接受 'D'（+1 文件 → 4 文件，仍 ≤ 6）
  - 选项 B：popover 内不复用 SetupQualityBadge，自行 inline 渲染 4 色 quality（无新文件）
  - **默认采 B**，理由：popover 是 AI 增强区，与 deterministic Setup Quality 语义不同，视觉上独立反而更清晰
- [ ] 颜色全部走 `var(--*)`，无硬编码 hex
- [ ] 无 console.error 遗留
- [ ] design-spec.md line 972 已加 hover → click 偏离标注
- [ ] `git status` 无遗留未提交改动

---

## 6. 开放问题（需用户确认或采用默认）

| # | 问题 | 默认 | 备选 |
|---|------|------|------|
| Q1 | trendScore 阈值（>=60 / <=40）是否合理？| 是（待启动后端时观察实际值域微调）| 改为 70/30 或 50/50 |
| Q2 | popover 内 Quality 徽章是否复用 SetupQualityBadge？| **B：inline 渲染**（避免改组件签名）| A：扩展 SetupQualityBadge 接受 'D' |
| Q3 | 第 10 列宽度 5% 是否够？| 是 | 视觉异常时 6%，相邻列减 1% |
| Q4 | popover `align="end"` 还是 `start`？| `end`（避免 popover 飞出表格右边界）| `start` |

> Q1/Q3 留作 acceptance 阶段视觉验证；Q2 采默认 B；Q4 采默认 end。

---

## 7. 风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| trendScore 实际值域不是 0-100 | 中 | 映射全失准 | step 8a 前用 `curl /api/cockpit/setup-monitor` 看 1 行实际值 |
| LLM 输出 quality='D'（罕见但 schema 允许）| 低 | 无对应徽章色 | 默认 B 方案 inline 渲染含 D |
| Popover Portal 与 react-grid-layout 拖拽 z-index 冲突 | 低 | popover 被遮 | shadcn PopoverContent 已 `z-50`，且 portal 渲染到 body |
| 表格行 `onClick` 与按钮 `onClick` 冒泡 | 中 | 误触 setSelectedTicker | `e.stopPropagation()` + 测试 C4 验证 |

---

确认 Contract 后我会：
1. 更新 features.json：F209-c.phase = `contract_agreed`
2. 更新 claude-progress.txt（追加 Contract 协商记录）
3. 生成新 SESSION-HANDOFF.md（覆盖 F209-b 那份）
4. **停止**，建议你在新 session 开 Sonnet 进入 Generator 模式
