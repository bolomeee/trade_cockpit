# Sprint Contract：F209-b — Market Narrator 前端集成（MarketRegimeWidget AI Notes）

> 状态：草案，待用户确认 | 起草：2026-04-25
> 父 Feature：F209 Market Narrator + Setup Explainer（v2.0 Cockpit P2 AI 层）
> 兄弟：F209-a ✅ needs_review（schema + 注册 + envelope 已就位） / **F209-b（前端 Market Narrator，本 sprint）** / F209-c（Setup Explainer popover，复用 aiApi.ts）
> 依赖：F209-a ✅（POST /api/ai/market_narrator 可用）+ F201-c ✅（MarketRegimeWidget shell 已落地）
> 引用文档：
>   - API-CONTRACT.md §POST /api/ai/{task_type}（line 1655-1734：统一 envelope / 错误码 / market_narrator I-O 示例）
>   - DATA-MODEL.md §AiMemo（cached_at 字段权威；前端不直接读 DB）
>   - design-spec.md §Widget 1 MarketRegimeWidget（line 808-822：AI Market Notes 区 wireframe + 交互）
>   - data-mapping.md §Cockpit-1.e（line 407-417：字段绑定）+ §Cockpit-AI-Wrapper（line 776-797：错误响应统一映射）
>   - DECISIONS.md D064（LiteLLM 单一动态 endpoint）/ D069（ai_memos 双用途，TTL + schema_version）/ D074（schema 字段 camelCase）
>   - features.json#F209-b acceptance_criteria（7 条）
>   - backend/app/ai/schemas/market_narrator.py（输入/输出 Pydantic schema 权威）

---

## 0. 背景与定位

F209-a 后端已完成：`POST /api/ai/market_narrator` 接受 API-CONTRACT line 1733 例 input、返回 line 1734 例 output、含 BANNED_PHRASES guardrail、错误码 422/502/429/409 全覆盖。

本 sprint 在 **不改 MarketRegimeWidget 现有 4 区块（ScoreHero / SubscoresGrid / IndicesCard / SectorHeatmap）任何渲染逻辑** 的前提下，于 widget 容器底部增加第 5 区块 **AI Market Notes**，并新增通用 AI 客户端 `aiApi.ts` 供 F209-c 复用。

设计上的关键约束：
1. AI 区是 **可选增强**——失败/超预算时显示占位文案，不污染上方 deterministic 区域。
2. Refresh 按钮 **24h 缓存窗** 由 server-side `ai_memos` 处理；前端 1h cooldown 仅是 UX 防抖，不替代 server cache。
3. 输入构造完全来自 widget 已有 `data: CockpitRegimeData`（无新接口、无新 store），按 backend MarketNarratorInput schema 整形。

---

## 1. 实现范围

### 1.1 包含

#### 1.1.1 `frontend/src/cockpit/lib/api/aiApi.ts`（新建）

通用 AI 客户端，封装 `POST /api/ai/{task_type}`：

```ts
// 类型
export type AiMeta = {
  modelUsed: string
  tier: string
  tokensIn: number
  tokensOut: number
  costUsd: number
  latencyMs: number
  cacheHit: boolean
}

export type AiTaskResponse<TOut> = {
  memoId: number
  taskType: string
  schemaVersion: string
  output: TOut
  meta: AiMeta
}

// 主方法
export async function callAiTask<TIn, TOut>(
  taskType: string,
  input: TIn,
  opts?: { noCache?: boolean }
): Promise<AiTaskResponse<TOut>>
```

实现要点：
- 使用 `apiFetch<AiTaskResponse<TOut>>(\`/ai/${taskType}\`, { method: 'POST', body: JSON.stringify({ input, noCache: !!opts?.noCache }), headers: { 'Content-Type': 'application/json' } })`
- 不在 client 层做 schema 校验（信任后端 Pydantic 校验）
- 不做错误转化——`apiFetch` 抛 `ApiError`，调用方按需处理 `error.code` ∈ { AI_PROVIDER_ERROR, AI_SCHEMA_ERROR, AI_BUDGET_EXCEEDED, AI_GUARDRAIL_VIOLATION, VALIDATION_ERROR }

同文件追加 market_narrator 专用类型（供 widget 直接引用，避免 widget 自己写 type）：

```ts
export type MarketNarratorInput = {
  regime: 'RISK_ON' | 'CONSTRUCTIVE' | 'NEUTRAL' | 'DEFENSIVE' | 'RISK_OFF'
  marketScore: number
  subscores: {
    spyTrend: number
    qqqTrend: number
    iwmBreadth: number
    sectorParticipation: number
    riskAppetite: number
    volatilityStress: number
  }
  sectors: Array<{
    symbol: string
    closePct: number
    state: 'Strong' | 'Neutral' | 'Weak'
  }>
}

export type MarketNarratorOutput = {
  headline: string
  summary: string
  riskPosture: 'aggressive' | 'balanced' | 'cautious' | 'defensive'
  preferredSetups: string[]
  avoid: string[]
  warnings: string[]
}
```

> 注：后端 schema 仅认 `Strong/Neutral/Weak` 三个 sector state；CockpitRegimeData 的 `SectorState` 有 5 个值（含 `Constructive`/`Defensive`）。需要写一个 5→3 的归一化映射函数 `normalizeSectorState(s: SectorState): 'Strong'|'Neutral'|'Weak'`：`Strong→Strong / Constructive→Strong / Weak→Weak / Defensive→Weak / Neutral→Neutral`。该函数放在 widget 文件内（私有，仅本处使用），不暴露到 aiApi.ts。

#### 1.1.2 `frontend/src/cockpit/widgets/MarketRegimeWidget.tsx`（修改）

在现有 widget 渲染 tree 末尾追加 `<AiMarketNotes data={data} />` 子组件（紧贴 SectorHeatmap 之后）。新增内部组件：

- `<AiMarketNotes data={CockpitRegimeData}>`：
  - 内部 `useMutation`（react-query）调 `callAiTask<MarketNarratorInput, MarketNarratorOutput>('market_narrator', input, { noCache: true })`
  - 自动首次触发：组件挂载且 `data` 就绪时，调一次（noCache=false，让后端 24h 缓存生效）
    - 实现方式：用 `useQuery` 而非 `useMutation`，queryKey `['ai', 'market_narrator', regimeDate]`，`enabled: !!data`，`staleTime: 60*60*1000`（1h），`gcTime: 24*60*60*1000`，`retry: false`
    - 手动 Refresh 按钮调 `refetch()` 时显式传 `noCache=true`：通过 mutationFn 模式 + `queryClient.setQueryData` 写回；或用 `useQuery` + 状态变量 `forceNoCache`，refetch 前置 true，回调后置 false
    - **采用方案**：单 `useQuery` + `forceNoCache` ref。queryFn 闭包读 ref 决定 noCache。
  - **Refresh 按钮 disabled 条件（OR 任一即 disabled）**：
    1. `isLoading` 或 `isFetching`（防双击）
    2. `dataUpdatedAt > 0 && Date.now() - dataUpdatedAt < 60*60*1000`（前端 1h cooldown）
    3. `error` 且最近一次错误是 `AI_BUDGET_EXCEEDED`（429，本月预算耗尽，refetch 也无意义）
- 子组件渲染分支：
  - **加载态**（`isLoading` 或 `isFetching` 且无 `data`）：3 个 `<Skeleton>`（headline 1 行 + summary 2 行 + warnings 1 行）
  - **错误态**（`error` 存在）：单行灰字 "AI 暂不可用"（`var(--color-text-secondary)`，`font-size-label`）。错误码用于 button disabled 判断，不在区块内显示具体错误原因（避免污染主区）。
  - **正常态**（有 `data`）：
    - 区块标题 "AI Market Notes"（`font-size-label` + `--color-text-secondary` + `marginBottom 6px`）
    - Headline：`font-size-body` 600 weight，`var(--color-text-primary)`，`marginBottom 4px`
    - Summary：`font-size-body` 400 weight，`var(--color-text-secondary)`，`line-height 1.5`，`marginBottom 6px`
    - Warnings 列表（output.warnings 非空时）：每条独立 chip，背景 `var(--color-log-warn)` mix 25%，前缀 "⚠️ "，`font-size-label`
    - Refresh 按钮：右上对齐（区块内 flex header），`<Button size="sm" variant="ghost">`，文案 "↻ Refresh"，loading 时 spinner
- 上方 4 区块**不变**——AI 失败时仅本区显示占位，其他区域照常渲染。

#### 1.1.3 `frontend/src/cockpit/lib/api/__tests__/aiApi.test.ts`（新建）

§A — 单元测试：
- A1：成功调用 → fetch 被以 `/api/ai/market_narrator` POST 调用，body 含 `input` + `noCache: false`
- A2：`noCache: true` 透传到 body
- A3：返回 `data.output` 解包给调用方（response shape 完整：memoId / taskType / schemaVersion / output / meta）
- A4：502 AI_PROVIDER_ERROR → 抛 ApiError(code="AI_PROVIDER_ERROR", status=502)
- A5：429 AI_BUDGET_EXCEEDED → 抛 ApiError(code="AI_BUDGET_EXCEEDED", status=429)
- A6：422 VALIDATION_ERROR → 抛 ApiError(code="VALIDATION_ERROR", status=422)
- A7：网络错误（fetch reject）→ 抛 Error（非 ApiError）

#### 1.1.4 `frontend/src/cockpit/widgets/__tests__/MarketRegimeWidget.test.tsx`（修改）

在现有 test 末尾追加 §S14（AI Market Notes 集成）：
- S14.1：`/api/cockpit/regime` 200 + `/api/ai/market_narrator` 200 → 渲染 headline / summary / warnings 文本（findByText）
- S14.2：`/api/cockpit/regime` 200 + AI 502 → 上方 4 区块正常渲染（CONSTRUCTIVE 标签可见），AI 区显示 "AI 暂不可用"
- S14.3：`/api/cockpit/regime` 200 + AI 429 BUDGET_EXCEEDED → AI 区"AI 暂不可用" + Refresh 按钮 disabled
- S14.4：Refresh 按钮 cooldown：mock fetch 第一次返回 AI 数据，立即点击 Refresh → 按钮 disabled（cooldown 内）
- S14.5：Refresh 触发后 mutation body 含 `noCache: true`（捕获 fetch 调用 args 校验）
- S14.6：sector state 归一化：CockpitRegimeData 含 `Constructive` / `Defensive` 状态 → AI request body 中 sectors[].state 仅出现 `Strong`/`Neutral`/`Weak`

测试 helper：扩展 `renderWidget()` 的 fetch mock 为路由式（按 URL 分发响应），避免单一 mock 污染。

### 1.2 明确排除（本次不做）

- ❌ "Cached · {age}" 文案（design-spec / data-mapping 提及，但 features.json AC 未要求；server `meta.cacheHit` 仍记录，前端目前不展示）
- ❌ schemaVersion 不匹配的"AI 输出可能已过期"提示（data-mapping §Cockpit-AI-Wrapper 提及，本 sprint 客户端 SCHEMA_VERSION 常量不引入）
- ❌ Tooltip 显示 modelUsed / tokens / cost（data-mapping 提及为可选，本 sprint 不做）
- ❌ AI 区域错误的具体细分文案（统一显示"AI 暂不可用"，不区分 502/429/网络）
- ❌ 重试按钮（错误态没有"重试"按钮，依赖 1h cooldown 后用户主动 Refresh）
- ❌ F209-c Setup Explainer popover（独立 sprint，复用本 sprint 的 aiApi.ts）
- ❌ MarketRegimeWidget 现有 4 区块的任何调整

---

## 2. 预计修改文件（共 4 个，未超 6 上限）

| 文件路径 | 改动类型 | 说明 |
|---------|---------|------|
| `frontend/src/cockpit/lib/api/aiApi.ts` | 新建 | 通用 callAiTask + market_narrator I-O 类型 |
| `frontend/src/cockpit/widgets/MarketRegimeWidget.tsx` | 修改 | 末尾追加 `<AiMarketNotes>` 子组件（约 +120 行） |
| `frontend/src/cockpit/lib/api/__tests__/aiApi.test.ts` | 新建 | §A 7 个单测 |
| `frontend/src/cockpit/widgets/__tests__/MarketRegimeWidget.test.tsx` | 修改 | 末尾追加 §S14 6 个集成测试 + 路由式 fetch mock helper |

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `callAiTask('market_narrator', input)` 默认 `noCache: false` 发起 POST `/api/ai/market_narrator`，body 含 input | 单元 | vitest + fetch stub |
| 2 | `callAiTask(..., { noCache: true })` body.noCache === true | 单元 | vitest |
| 3 | 502/429/422 错误响应 → 抛 ApiError，code 字段对应错误码 | 单元 | vitest |
| 4 | MarketRegimeWidget 正常路径：regime + AI 双 200 → headline/summary/warnings 渲染 | 集成 | vitest + RTL |
| 5 | AI 502 失败：4 区块正常 + AI 区"AI 暂不可用"占位 | 集成 | vitest + RTL |
| 6 | AI 429 BUDGET_EXCEEDED：占位 + Refresh disabled | 集成 | vitest + RTL |
| 7 | Refresh 1h cooldown：成功后立即点击 → 按钮 disabled | 集成 | vitest + RTL |
| 8 | Refresh 触发的 request body 含 `noCache: true` | 集成 | vitest + RTL |
| 9 | sector state 归一化：5 值映射为 3 值后传给后端 | 集成 | vitest + RTL（mock fetch 捕获 body） |
| 10 | UI 颜色 / 字体走 tokens.css 变量，无硬编码 hex / px size | 代码审查 | grep 检查 |
| 11 | 全量回归：`pnpm vitest run` 整个 frontend test suite 通过，无新增失败 | 回归 | vitest |

---

## 4. Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] §A aiApi 单元测试 7/7 通过
- [ ] §S14 widget 集成测试 6/6 通过
- [ ] §S1-S13 既有测试 0 回归
- [ ] frontend 全量 `pnpm vitest run` 通过
- [ ] backend 全量 `uv run pytest tests/` 仍 587 通过（前端 sprint 不应影响后端，作 sanity check）
- [ ] 文件清单 4 个，未越界
- [ ] aiApi.ts 不含任何 widget 专属逻辑（保持通用，F209-c 可复用）
- [ ] MarketRegimeWidget 现有 4 区块代码 0 行改动（diff 检查）
- [ ] 无 console.error 遗留（S13 测试沿用）
- [ ] 颜色 / 字体 / 尺寸全部走 `var(--color-*)` / `var(--font-size-*)`，无 `#xxx` / `12px` 字面量
- [ ] sector state 归一化函数有显式测试覆盖
- [ ] Refresh cooldown 通过 react-query `dataUpdatedAt` 实现，未引入 setInterval
- [ ] 所有错误状态显示"AI 暂不可用"统一文案
- [ ] 本 sprint 无新外部依赖（不动 package.json）
- [ ] features.json#F209-b phase = needs_review，last_updated 更新
- [ ] DECISIONS.md 视情况追加（若出现非显然技术决策）

---

## 5. 关键技术决策（先列待用户确认）

1. **Refresh cooldown 由前端单独实现**：1h 客户端冷却 + 后端 24h server cache 双层。理由：减轻 server 压力 + 防双击；后端 cacheHit 仍透传但前端不展示。
2. **错误统一文案**：不细分 502/429/网络具体原因。理由：features.json AC 第 5 条明确"AI 输出失败时显示 'AI 暂不可用' 占位"。
3. **sector state 5→3 归一化在前端做**：因后端 schema 仅 3 值。映射规则：Strong/Constructive→Strong；Weak/Defensive→Weak；Neutral→Neutral。理由：传 5 值会被 backend 422 拒掉，前端归一比改后端 schema 影响面小。
4. **react-query 模式而非 useMutation**：自动初次 fetch + 手动 refetch 都通过 `useQuery` + `forceNoCache` ref 实现。理由：react-query 已是项目主路径；`dataUpdatedAt` 直接给 cooldown 用，无需自管 timer。
5. **不引入新依赖**。Skeleton / Button 已在 `@/components/ui/`。

---

## 6. 开发顺序

1. Step 1：`aiApi.ts` 新建 + §A 单测（先稳定 client 层）→ wip commit
2. Step 2：MarketRegimeWidget `<AiMarketNotes>` 子组件骨架（loading / error / empty 状态外壳）→ wip commit
3. Step 3：sector state 归一化 + useQuery 集成 + Refresh 按钮 + cooldown 逻辑 → wip commit
4. Step 4：§S14 集成测试 6 case → wip commit
5. Step 5：Evaluator §3 全量回归 + §4 自检逐条 → 最终 feat commit
6. Step 6：features.json + claude-progress.txt + 必要时 DECISIONS.md → 单独 chore commit

---

👤 用户确认本 Contract 后，开发开始。
