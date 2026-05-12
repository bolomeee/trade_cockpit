# Sprint Contract：F210-b — SetupMonitor "AI 排序" 集成

> 状态：草案，待用户确认 | 起草：2026-04-25
> 父 Feature：F210 AI Candidate Ranker + Trade Plan Generator（v2.0 Cockpit P2 critical-tier）
> 兄弟：F210-a ✅ done（含 regime 5 值 hotfix 2853e3b）/ **F210-b（本 sprint）** / F210-c（DecisionPanel "Generate AI Plan"）
> 依赖：
>   - F210-a ✅（candidate_ranker schema + REGISTRY 注册 + critical tier 路由）
>   - F209-b ✅（`callAiTask<TIn, TOut>` 通用客户端 + ApiError 错误码识别）
>   - F209-c ✅（前端 4 状态渲染 / fetch 路由 mock / `e.stopPropagation()` 行点击隔离 — 模式直接复用）
>   - F202-c ✅（SetupMonitorWidget shell + items 数据源）
>   - F201 ✅（cockpitRegimeApi + `/api/cockpit/regime` regime/marketScore）
>
> 引用文档：
>   - API-CONTRACT.md §POST /api/ai/{task_type}（line 1655-1734）/ §GET /api/cockpit/regime / §GET /api/cockpit/setup-monitor
>   - design-spec.md §Widget 5 SetupMonitorWidget（line 945-973，**当前不含 "AI 排序" 描述 — 规则 8 触发回写**）
>   - data-mapping.md §Cockpit-5（line 538-585，**当前不含 AI candidate_ranker 映射 — 规则 8 触发新增 §5.c**）
>   - features.json#F210（acceptance_criteria AC4 / AC5）+ #F210-b（scope）
>   - backend/app/ai/schemas/candidate_ranker.py（输入/输出 schema 权威，regime 5 值已对齐）
>   - DECISIONS.md D064（critical tier）/ D069（24h 缓存）/ D074（camelCase）
>   - frontend/src/cockpit/components/AiSetupExplainerPopover.tsx（F209-c 模板：useQuery + 4 状态 + retry:false + staleTime/gcTime 24h）
>   - frontend/src/cockpit/widgets/SetupMonitorWidget.tsx（注入点）
>   - frontend/src/cockpit/lib/api/cockpitRegimeApi.ts（regime/marketScore 来源）

---

## 0. 背景与定位

F210-a 落地了 `POST /api/ai/candidate_ranker` 后端 schema（critical tier，无 guardrail，输入 1-20 candidates）。本 sprint 在 SetupMonitor widget 顶部追加 "AI 排序" 按钮，点击调用 candidate_ranker，把当前 items[] 的前 20 条按 schema 投影后送给 AI，渲染 top 3（ticker / rank / reason / action）于 widget 内的 result section。

**设计上的关键约束**：

1. **regime 双依赖**：candidate_ranker 输入既要 setup items（已在本 widget useQuery 中），还要 `regime + regimeScore`（来自 `/api/cockpit/regime`）。本 sprint 用 react-query 复用相同 query key（`['cockpit-regime']`）拿 MarketRegimeWidget 已加载的数据，避免重复请求；regime 未就绪时按钮 disabled。
2. **AI 区是可选增强**：失败/预算超限时显示文案，**不影响表格其余渲染、不影响 setSelectedTicker 联动**。
3. **截断责任在前端**：F210-a Q1 决策 — 服务端走 422 严格校验（`max_length=20`），前端入参前 `slice(0, 20)`；超 20 时在 result section 顶部加注 "已用前 20 条"（满足 features.json AC4 "在响应 meta 标记" 的语义层等价）。
4. **触发：点击**（与 F209-c "?" 按钮一致）。无 hover；无 widget 级 cooldown（24h 服务端缓存承担去重）。
5. **缓存**：服务端 `ai_memos` 24h 去重；前端 `staleTime: 24*60*60*1000` + `gcTime: 24*60*60*1000`。同一 (regime, items 集合) session 内复点 0 网络。
6. **结果可关闭**：result section 提供 "✕" 关闭按钮，关闭仅隐藏 UI（缓存保留）；再次点击 "AI 排序" 重新展开（命中缓存即时返回）。

---

## 1. 实现范围

### 1.1 包含

#### 1.1.1 `frontend/src/cockpit/components/AiCandidateRankerSection.tsx`（新建，~200 行）

可复用的 section 组件，封装"按钮 + 4 状态 result panel"。Props：

```ts
type Props = {
  items: SetupItem[]                          // 当前过滤后的 items（来自 widget useQuery）
  regime: RegimeLabel | null                  // null = regime 还在加载或失败 → 按钮 disabled
  regimeScore: number | null                  // 同上
}
```

**类型与输入构造（仅在按钮点击后执行）**：

```ts
import { callAiTask, type AiTaskResponse } from '../lib/api/aiApi'

export type CandidateInput = {
  ticker: string
  setupType: SetupType
  setupQuality: 'A' | 'B' | 'C' | null
  trendScore: number          // 0-5
  rsPercentile: number        // 0-100
  distanceToEntryPct: number  // 可负
  rewardRisk: number          // ≥0
  earningsRisk: 'SAFE' | 'CAUTION' | 'DANGER'
  readySignal: boolean
}

export type CandidateRankerInput = {
  regime: RegimeLabel
  regimeScore: number
  candidates: CandidateInput[]   // 1-20
}

export type RankedCandidate = {
  ticker: string
  rank: 1 | 2 | 3
  reason: string
  action: 'enter' | 'watch' | 'wait'
}

export type CandidateRankerOutput = {
  topCandidates: RankedCandidate[]   // 长度恒为 3
}
```

**字段映射（SetupItem → CandidateInput）**：

| schema 字段 | 来源 | 备注 |
|---|---|---|
| `ticker` | `item.ticker` | 直传 |
| `setupType` | `item.setupType` | 直传（schema 7 值与 SetupItem 一致）|
| `setupQuality` | `item.setupQuality` | A/B/C/null 直传 |
| `trendScore` | `item.trendScore` | 0-5（schema `ge=0 le=5`）|
| `rsPercentile` | `item.rsPercentile` | 0-100，整数→float OK |
| `distanceToEntryPct` | `item.distanceToEntryPct ?? 0` | schema 不限正负；null → 0（容错）|
| `rewardRisk` | `Math.max(item.rewardRisk ?? 0, 0)` | schema `ge=0`；null/负 → 0 |
| `earningsRisk` | `item.earningsRisk` | 直传 |
| `readySignal` | `item.readySignal` | 直传 |

**截断**：`items.slice(0, 20)` 在 build 时直接切片；记 `wasTruncated = items.length > 20`。

**useQuery 行为（点击触发）**：

```ts
const [open, setOpen] = useState(false)

// 缓存键设计：仅含 regime + 用户当前过滤的前 20 个 ticker（拼接），保证不同过滤 tab 各自独立缓存
const inputKey = useMemo(() => {
  const tickers = items.slice(0, 20).map(i => i.ticker).join(',')
  return `${regime ?? ''}|${tickers}`
}, [items, regime])

const { data, isLoading, isFetching, error, refetch } = useQuery({
  queryKey: ['ai', 'candidate_ranker', inputKey],
  queryFn: () => callAiTask<CandidateRankerInput, CandidateRankerOutput>(
    'candidate_ranker',
    buildCandidateRankerInput({ items, regime: regime!, regimeScore: regimeScore! }),
  ),
  enabled: open && regime != null && regimeScore != null && items.length >= 1,
  staleTime: 24 * 60 * 60 * 1000,
  gcTime: 24 * 60 * 60 * 1000,
  retry: false,
})
```

**渲染 — 5 状态**：

| 状态 | 渲染 |
|------|------|
| 关闭（`!open`） | 仅显示按钮 |
| 加载（`isLoading || isFetching && !data`） | 3 行 Skeleton（rank 1/2/3 行占位）|
| 错误（任意 ApiError） | "AI 排序暂不可用"（`var(--color-text-secondary)`） + ✕ 关闭按钮 |
| 空（items.length === 0） | 不发请求（按钮也 disabled），不进入 section |
| 成功 | 顶栏（"AI 排序 · top 3" 标题 + 截断标记 + cache 徽章 + ✕） + 3 行 ranked cards（# rank · ticker [actionBadge] · reason）|

**触发按钮**：

```tsx
<button
  data-testid="ai-rank-trigger"
  aria-label="AI rank top setups"
  onClick={() => setOpen(o => !o)}
  disabled={regime == null || regimeScore == null || items.length === 0}
  style={{
    padding: '4px 10px',
    borderRadius: '4px',
    border: '1px solid var(--color-border)',
    background: open ? 'var(--color-signal-breakout)' : 'var(--color-bg-secondary)',
    color: open ? 'var(--color-text-on-dark)' : 'var(--color-text-primary)',
    cursor: 'pointer',
    fontSize: 'var(--font-size-caption)',
    fontWeight: 'var(--font-weight-medium)',
    opacity: (regime == null || items.length === 0) ? 0.5 : 1,
  }}
>
  AI 排序
</button>
```

**Action Badge**（inline，三色枚举，避免新建组件）：

| action | 色 |
|---|---|
| `enter` | `var(--color-signal-breakout)` |
| `watch` | `var(--color-log-warn)` |
| `wait` | `var(--color-text-muted)` |

**Cache 徽章**：`data.meta.cacheHit === true` 时显示 "Cached"（`var(--color-text-muted)` 小字）；否则显示 "Generated · {modelUsed}"。

#### 1.1.2 `frontend/src/cockpit/widgets/SetupMonitorWidget.tsx`（修改，~+15 行）

变更点（最小化）：

1. 新增 `useQuery` 加载 regime（key `['cockpit-regime']` 与 MarketRegimeWidget 一致，复用缓存；`staleTime` 同步 5min）：
   ```ts
   import { getCockpitRegime } from '../lib/api/cockpitRegimeApi'
   const { data: regimeData } = useQuery({
     queryKey: ['cockpit-regime'],
     queryFn: getCockpitRegime,
     staleTime: 5 * 60 * 1000,
   })
   ```
2. 在 Filter Tabs 行的右侧追加按钮容器（同行右浮），挂 `<AiCandidateRankerSection />`：
   ```tsx
   <AiCandidateRankerSection
     items={items}
     regime={regimeData?.regime ?? null}
     regimeScore={regimeData?.marketScore ?? null}
   />
   ```
   **注意**：`regimeScore` 在前端字段名是 `marketScore`（cockpitRegimeApi 命名），传给 schema 的 `regimeScore` 字段，本组件内做适配。
3. 当 `open=true` 且有 result/error 时，组件自身在按钮**正下方**用绝对定位 / 或行内 `<div>`（默认行内）渲染 result panel；**不破坏 table 区**。

> **布局定位**：result panel 行内插入到 Filter Tabs 与 Table 之间（widget 内部从上至下：Header / Filter Tabs / [AI Result Panel inline，仅 open 时存在] / Table）。绝对定位 popover 方案受 widget 高度限制易溢出，行内 push down 表格更友好。

#### 1.1.3 `frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx`（修改 / 扩展，~+220 行）

新增测试 §R — AI Candidate Ranker（11 用例，复用 F209-c `makeRoutedFetch` 路由 mock）：

| # | 用例 | 类型 |
|---|------|------|
| R1 | items 加载 + regime 加载完成 → "AI 排序" 按钮渲染且 enabled | 单元 |
| R2 | regime 加载中（无数据） → 按钮 disabled | 单元 |
| R3 | items 为空（empty filter）→ 按钮 disabled | 单元 |
| R4 | 点击按钮 → 调 `POST /api/ai/candidate_ranker`，body.input.regime 等于 regimeData.regime / body.input.regimeScore 等于 regimeData.marketScore | 集成 |
| R5 | 点击按钮 → body.input.candidates 长度 = min(items.length, 20)；超 20 时只取前 20 | 集成 |
| R6 | 点击按钮 → 字段映射正确：candidates[0] 含 ticker/setupType/setupQuality/trendScore/rsPercentile/distanceToEntryPct/rewardRisk/earningsRisk/readySignal 9 字段，无 stockName / volumeStatus 等多余字段 | 集成 |
| R7 | 加载期间显示 3 个 Skeleton；不再次发请求 | 集成 |
| R8 | 成功响应渲染 top 3，每行含 rank / ticker / actionBadge / reason | 集成 |
| R9 | items.length > 20 时 result 顶栏显示截断标记（如 "Top 20 / N"）| 集成 |
| R10 | 502 AI_PROVIDER_ERROR → "AI 排序暂不可用" + 行点击 setSelectedTicker 仍正常 | 集成 |
| R11 | 关闭再打开（同 inputKey）→ fetch 调用计数 = 1（react-query 缓存命中）| 集成 |

> 测试架构沿用 F209-c：`makeRoutedFetch` 按 URL 路由，`/cockpit/setup-monitor` 返回 fixture，`/cockpit/regime` 返回 fixture，`/ai/candidate_ranker` 按场景返回 200/502。

---

### 1.2 排除（明确不做）

- ❌ **不动 backend**（F210-a 已落地，regime 5 值已 hotfix）
- ❌ **不动 aiApi.ts**（已是通用客户端）
- ❌ **不动 cockpitRegimeApi.ts**（沿用 marketScore 字段名，组件内适配）
- ❌ **不动 setupMonitorApi.ts**（字段已齐全）
- ❌ **不加 widget 级 Refresh / cooldown 按钮**（缓存承担去重）
- ❌ **不加 hover 触发**（features.json 优先，与 F209-c 一致）
- ❌ **不动 store / 路由 / WidgetShell 框架**
- ❌ **不写 e2e**（集成测试已覆盖；e2e 留 acceptance 阶段视觉确认）
- ❌ **不动 DecisionPanel**（属 F210-c）
- ❌ **不修改 setup_explainer 模式**（与 F209-c 共存，互不干扰）
- ❌ **不加 result 持久化**（关闭组件即从 UI 移除，仅靠 react-query 缓存）

---

## 2. 预计修改文件清单（共 3 个，**远低于** 6 文件上限）

| 路径 | 操作 | 预计行数变化 |
|------|------|-------------|
| `frontend/src/cockpit/components/AiCandidateRankerSection.tsx` | 新建 | +200 |
| `frontend/src/cockpit/widgets/SetupMonitorWidget.tsx` | 修改 | +15 |
| `frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx` | 修改 | +220 |

**附加（不计入 6 文件上限，规则 8 触发的回写）**：
- `docs/设计/design-spec.md` Widget 5 §（line 945-973）— 在 v2.0 增强段补一段 "AI 排序" 按钮 + result section 描述（约 +10 行）
- `docs/设计/data-mapping.md` §Cockpit-5 — 新增 §5.c "AI Candidate Ranker"（约 +20 行，输入/输出字段映射表）

---

## 3. 完成标准（每条可测试）

| # | 完成标准 | 测试层级 | 工具 |
|---|---------|---------|------|
| C1 | regime / items 就绪时按钮 enabled；任一未就绪 disabled | 单元 | vitest + RTL |
| C2 | 点击按钮发 `POST /api/ai/candidate_ranker`，body 为 `{ input: { regime, regimeScore, candidates: [...]}, noCache: false }`，candidates 长度 ≤ 20 且字段精确为 9 字段集合 | 集成 | vitest + fetch mock |
| C3 | 加载期间显示 3 个 Skeleton；按钮处于 active 视觉态 | 集成 | vitest + RTL |
| C4 | 成功响应渲染 top 3：每行 rank（1/2/3）/ ticker / action badge（enter/watch/wait 三色）/ reason 文本 | 集成 | vitest + RTL |
| C5 | items.length > 20 时 result 顶栏显示截断标记 | 集成 | vitest + RTL |
| C6 | items.length === 0（filter 后空集）按钮 disabled，不发请求 | 单元 | vitest + RTL |
| C7 | 502 错误显示"AI 排序暂不可用"，行点击 setSelectedTicker 仍正常 | 集成 | vitest |
| C8 | 同 (regime, ticker 集合) 关闭再开 → fetch 计数 = 1（react-query 缓存命中）；改变 filter 后 inputKey 变化触发新请求 | 集成 | vitest + fetch spy |
| C9 | regimeData.marketScore 适配为 input.regimeScore（字段名转换） | 集成 | vitest |
| C10 | 类型检查通过 `pnpm tsc --noEmit` | 工程 | tsc |
| C11 | Lint 通过 `pnpm lint`（无新增 warning）| 工程 | eslint |
| C12 | 全量回归：所有 frontend 测试通过（cockpit + workbench + 共享）| 回归 | vitest run |
| C13 | design-spec.md Widget 5 已补 "AI 排序" 描述（规则 8 回写） | 文档 | grep |
| C14 | data-mapping.md 新增 §Cockpit-5.c | 文档 | grep |

---

## 4. 开发顺序（Generator 模式严格执行）

```
1. 确认 DATA-MODEL.md 无需改动 → ✅
2. 确认 API-CONTRACT.md 已涵盖 → ✅（F210-a 已涵盖 candidate_ranker）
3-6. 跳过（前端 sprint）
7. 单元测试 + 集成测试 → 与 step 8 交叠
8. 前端组件 →
   8a. 新建 AiCandidateRankerSection.tsx（含类型 + buildInput + useQuery + 5 状态渲染）
   8b. SetupMonitorWidget.tsx 集成 regime useQuery + 挂载 section
   8c. SetupMonitorWidget.test.tsx 扩展 §R 11 用例
   8d. 写完 8a-c 后跑 `pnpm test` 验证 §R 全绿 + 既有 §S（F209-c）无回归
9. design-spec / data-mapping 回写（规则 8 强制）
10. tsc + lint 全绿
11. Evaluator 模式自检
```

每步通过最小验证后立即 wip commit（显式 add，禁用 `-A`）：
- step 8a → `wip(F210-b): candidate ranker section component`
- step 8b → `wip(F210-b): widget integration + regime fetch`
- step 8c → `wip(F210-b): tests §R green`
- step 9 → `chore(F210-b): design-spec + data-mapping for AI rank`

最终（Evaluator 通过后） → `feat(F210-b): SetupMonitor AI rank top 3`

---

## 5. Evaluator 自检清单

- [ ] 单元测试：R1-R3 / R6 全部通过
- [ ] 集成测试：R4-R5 / R7-R11 全部通过
- [ ] 缓存测试 R11 / C8 通过
- [ ] 类型检查：`cd frontend && pnpm tsc --noEmit` 无错
- [ ] Lint：`cd frontend && pnpm lint` 无新增 warning
- [ ] 全量回归：`cd frontend && pnpm test --run` 所有 tests 仍绿（含 F209-c §S 11 用例）
- [ ] API body 字段名严格符合 backend `CandidateRankerInput` schema（9 字段 candidate 子集 / regime 5 值之一 / regimeScore 0-100）
- [ ] regime / regimeScore 来自 `getCockpitRegime()` 而非硬编码
- [ ] items.slice(0, 20) 在前端发请求前完成（不依赖后端截断）
- [ ] action badge 三色全部走 `var(--*)`，无硬编码 hex
- [ ] cache 徽章按 `meta.cacheHit` 切换文案
- [ ] ✕ 关闭按钮仅设 `open=false`（不 invalidate query，缓存保留）
- [ ] 行点击 `onClick → setSelectedTicker` 不被 result section 干扰（`e.stopPropagation()` 仅在按钮上需要 — 此处按钮在表外，理论无需，但保留 defensive）
- [ ] design-spec.md Widget 5 已补 AI 排序段（grep "AI 排序" 命中）
- [ ] data-mapping.md §Cockpit-5.c 已添加（grep "5.c\|candidate_ranker" 命中）
- [ ] 无 console.error 遗留
- [ ] `git status` 无遗留未提交改动

---

## 6. 开放问题（需用户确认或采用默认）

| # | 问题 | 默认 | 备选 |
|---|------|------|------|
| Q1 | items 是否过滤掉 EXTENDED/BROKEN/NONE 再送 AI？schema 7 值都接受，但这 3 类不可操作，可能浪费 AI 预算 | **不过滤**，全部 slice(0, 20) 后送（让 AI 自己排，可能给 enter/watch/wait 有意义信号；F210-a schema 已显式接受 7 值，符合"前端不挑活"） | 仅送 BREAKOUT/PULLBACK/RECLAIM/EARNINGS_DRIFT 4 类（actionable subset）；EXTENDED/BROKEN/NONE 排除 |
| Q2 | result panel 与 Filter Tabs 同行右侧按钮 vs 独占新行？ | **同行右侧**（节省纵向空间，与 ResetLayoutButton 风格一致） | 新行（更突出但占空间） |
| Q3 | result panel 渲染位置？ | **行内 push down 表格**（widget 内部从上至下：Header / Tabs / Result Panel / Table） | popover 浮动（受 widget 边界限制易溢出） |
| Q4 | 错误态是否提供"重试"按钮？ | **否**（与 F209-c 一致，错误即止；用户可关闭后重新点击触发 refetch） | 提供 retry 按钮调 `refetch()` |
| Q5 | items 排序后 inputKey 是否稳定？widget 内已按 suggestedAction 排序 → tickers 顺序受 sort 影响。换 filter tab 时 inputKey 自然变化是预期行为吗？| **是**，filter 切换 → inputKey 变化 → 新请求是合理的（不同 filter 是不同任务）；同 filter 内 items 顺序稳定（actionOrder map 是确定的）| 改 inputKey 用 `[...tickers].sort().join(',')` 顺序无关 |

> 默认采上表方案；如需备选方案请明确指出。

---

## 7. 风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| `getCockpitRegime` 在 SetupMonitorWidget 内独立 useQuery 与 MarketRegimeWidget 重复请求 | 低 | 重复网络（react-query 同 key 自动去重） | queryKey `['cockpit-regime']` 全局共享，相同 staleTime 5min；测试 R4 验证只发一次 |
| inputKey 拼接含逗号导致测试 fixture 边界字符串相等性误判 | 低 | 缓存命中错误 | 测试 R11 用 fetch spy 计数验证而非字符串比较 |
| filter 切换造成 inputKey 频繁变化 → 缓存利用率低 | 中 | 用户感知慢 | 服务端 `ai_memos` 24h dedupe 兜底；前端 staleTime 24h，session 内同 filter 复点 0 网络 |
| AI 输出 `topCandidates[].ticker` 不在当前 items 集合内（LLM 编造） | 中 | UI 渲染孤立 ticker，点击无联动 | 渲染容错（即使没匹配也直显文本）；不在 ticker 上挂 setSelectedTicker 联动（F210-c 阶段考虑） |
| F210-a schema 的 `setupQuality: 'A' \| 'B' \| 'C' \| null` 与 frontend `SetupQuality` 一致 ✅ | — | — | 直传 |
| EXTENDED/BROKEN/NONE 行 `entryPrice/stopPrice` 可能为 0 → schema 不校验 entry/stop（candidate_ranker 无这两字段），无问题 | 低 | — | — |
| widget 高度紧（widget 默认 5 行高），插入 result panel 后表格区被挤压 | 中 | 用户视觉差 | result panel 默认收起，仅 open 时占位；3 行 ranked cards 高度约 90px |

---

## 8. F210-c 骨架预览（不属本 sprint，仅供拆分确认）

**核心**：DecisionPanelWidget 接入 `POST /api/ai/trade_plan`：
- 新建 `AiTradePlanSection.tsx`（按钮 + 4 状态 + memo 段 + management 列表 + Guardrail 红 banner / 通过 ✓）
- `DecisionPanelWidget.tsx` 在 Decision Card 下方追加该 section，从 `decision` query 取 11 字段构造 input
- 测试扩展 ~12 用例（含 409 AI_GUARDRAIL_VIOLATION 红 banner、memo / management 渲染、cache 命中）

预计 3 文件，与 F210-b 风格对称。

---

确认 Contract 后我会：
1. 更新 features.json：F210-b.phase = `contract_agreed`；`_pipeline_status.active_sprint = "F210-b"` 等字段
2. 更新 claude-progress.txt（追加 Contract 协商 + regime hotfix 记录）
3. 生成新 SESSION-HANDOFF.md（覆盖 F209-c / F210-a 完成那份，下一步指向 F210-b Generator）
4. **停止**，建议你在新 session 开 Sonnet 进入 Generator 模式
