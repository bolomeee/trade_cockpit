# Sprint Contract：F210-c — DecisionPanel "Generate AI Plan" 集成

> 状态：草案，待用户确认 | 起草：2026-04-26
> 父 Feature：F210 AI Candidate Ranker + Trade Plan Generator（v2.0 Cockpit P2 critical-tier）
> 兄弟：F210-a ✅ done（schemas + guardrail + REGISTRY） / F210-b ✅ done（SetupMonitor AI 排序 top 3）/ **F210-c（本 sprint，收尾）**
> 依赖：
>   - F210-a ✅（trade_plan Pydantic schema + D068 guardrail entry/stop/size + BANNED_PHRASES + REGISTRY 注册 + critical tier 路由）
>   - F209-b ✅（`callAiTask<TIn, TOut>` 通用客户端 + `ApiError.code/status` 错误识别）
>   - F209-c / F210-b ✅（前端 4 状态渲染 + react-query 24h 缓存 + ✕ 关闭 + cache 徽章 + AI 区不影响主体的隔离模式）
>   - F203 ✅（`GET /api/cockpit/decision/{ticker}` 返回 11 字段 deterministic quote + `deterministicHash` 锚点）
>
> 引用文档：
>   - API-CONTRACT.md §POST /api/ai/{task_type}（line 1655-1734，含 §Guardrail F210 trade_plan 专属 line 1707-1709，409 AI_GUARDRAIL_VIOLATION line 1720/1729）
>   - API-CONTRACT.md §GET /api/cockpit/decision/{ticker}（11 字段 quote + deterministicHash line 1207）
>   - design-spec.md §Widget 6 DecisionPanelWidget（line 978-1026，AI Trade Plan 区已在 line 1000-1007 + 1022 描述完整，含红 banner / Guardrail passed 文案）
>   - data-mapping.md §Cockpit-6.c AI Trade Plan（line 648-660，6 条字段映射齐全）
>   - features.json#F210（acceptance_criteria AC2/AC3/AC6）+ #F210.sub_phases.F210-c（scope）
>   - backend/app/ai/schemas/trade_plan.py（11 字段 TradePlanInput / 5 字段 TradePlanOutput / `guardrail()` post-validate / BANNED_PHRASES 6 条）
>   - DECISIONS.md D064（critical tier）/ D068（F210 guardrail）/ D069（24h 缓存）/ D074（camelCase）
>   - frontend/src/cockpit/components/AiCandidateRankerSection.tsx（F210-b 模板：useQuery + 5 状态 + ✕ 关闭 + cache 徽章；本 sprint 形态对称复用）
>   - frontend/src/cockpit/widgets/DecisionPanelWidget.tsx（注入点；现有 4 状态：empty / loading / 422 / 404 / error / data 共 6 分支）
>   - frontend/src/cockpit/lib/api/cockpitDecisionApi.ts（CockpitDecisionData 11 + 5 字段类型，含 deterministicHash）
>   - frontend/src/cockpit/lib/api/aiApi.ts（callAiTask + AiTaskResponse + AiMeta）

---

## 0. 背景与定位

F210-a 落地 trade_plan 后端（critical tier，post-validate guardrail 强制 entry/stop/size 三字段等于输入）。F210-b 落地 SetupMonitor 的 candidate_ranker UI。本 sprint 收尾 F210，实现 DecisionPanel 内的 trade_plan 集成：

1. **触发**：DecisionCard 渲染成功（`data` 存在）后，在 widget 底部追加 AI Trade Plan 区，含 `[Generate AI Plan]` 按钮。
2. **输入**：从 `decision` query data 直接抽取 11 字段，构造 `TradePlanInput`（**不再发起额外 decision 请求**，避免 race；input 完全派生于 react-query 已缓存的 decision data）。
3. **输出**：渲染 `memo` 段落 + `management[]` 编号列表 + Guardrail status（成功 → "✓ Guardrail passed"）+ cache 徽章。
4. **核心错误**：409 `AI_GUARDRAIL_VIOLATION` 时显示**红色 banner** "AI 输出被拦截 — 数字不匹配"（与 design-spec.md line 1022 措辞一致）。其他错误（502 / 429 / 500）显示"AI 暂不可用"。

**设计上的关键约束**：

1. **AI 区是可选增强**：失败/未点击时，DecisionCard / OverrideForm / Recompute / Save as PendingOrder 全部不受影响。
2. **缓存键派生于 deterministicHash**：相同 hash → 相同 trade_plan 输出（服务端 24h ai_memos dedupe）。前端 queryKey 用 `[ticker, deterministicHash]`，hash 变 → 新请求；override 调整后 decision 重算 → hash 变 → AI 区"过期"自动隐藏（详见 §4.x 处理）。
3. **触发：点击**（与 F209-c "?" / F210-b "AI 排序" 一致）。无 hover；无 widget 级 cooldown。
4. **缓存**：服务端 ai_memos 24h dedupe；前端 `staleTime: 24*60*60*1000` + `gcTime: 24*60*60*1000`。
5. **结果可关闭**：result panel 提供 ✕ 按钮，关闭仅隐藏 UI（react-query 缓存保留）；再次点击按钮重新展开（命中缓存即时返回）。
6. **隔离不破坏主体**：AI section 渲染容错（即使 schema 字段缺失也不抛错，仅显示 fallback）。
7. **deterministicHash 变化的语义**：用户修改 override → decision 重算 → hash 改变 → AI section 已展开但显示"deterministic 输入已变化，请重新生成"提示（关闭按钮 + 重生成按钮入口归一为再次点击主按钮）。

---

## 1. 实现范围

### 1.1 包含

#### 1.1.1 `frontend/src/cockpit/components/AiTradePlanSection.tsx`（新建，~250 行）

可复用的 section 组件，封装"按钮 + 5 状态 result panel"。Props：

```ts
type Props = {
  decision: CockpitDecisionData       // 已成功加载的 decision quote（DecisionPanelWidget 在 data 存在分支才挂载本组件）
}
```

**类型与输入构造（仅在按钮点击后执行）**：

```ts
import { callAiTask, type AiTaskResponse } from '../lib/api/aiApi'
import type { CockpitDecisionData } from '../lib/api/cockpitDecisionApi'
import type { SetupType, SetupQuality, EarningsRisk } from '../lib/api/setupMonitorApi'

export type TradePlanInput = {
  ticker: string
  setupType: SetupType                                 // 7 值，与 schema 一致
  setupQuality: 'A' | 'B' | 'C' | null                 // schema 接受 null
  entry: number                                        // gt=0
  stop: number                                         // gt=0
  target2r: number                                     // gt=0
  target3r: number                                     // gt=0
  size: number                                         // ge=1
  rewardRisk: number                                   // ge=0
  accountRiskPct: number                               // ge=0 le=100
  earningsRisk: EarningsRisk                           // SAFE/CAUTION/DANGER
  deterministicHash: string                            // min_length=8
}

export type TradePlanOutput = {
  memo: string                                         // 1-600 chars
  management: string[]                                 // 1-5 items
  entry: number                                        // === input.entry（guardrail）
  stop: number                                         // === input.stop
  size: number                                         // === input.size
}
```

**字段映射（CockpitDecisionData → TradePlanInput）**：

| schema 字段 | 来源 | 备注 |
|---|---|---|
| `ticker` | `decision.ticker` | 直传 |
| `setupType` | `decision.setupType` | 7 值与 schema 一致 |
| `setupQuality` | `decision.setupQuality` | A/B/C；DATA-MODEL 允许 null，schema 接受 null |
| `entry` | `decision.entryPrice` | **重命名**：前端 entryPrice → schema entry |
| `stop` | `decision.stopPrice` | **重命名**：前端 stopPrice → schema stop |
| `target2r` | `decision.target2r` | 直传 |
| `target3r` | `decision.target3r` | 直传 |
| `size` | `decision.suggestedShares` | **重命名**：前端 suggestedShares → schema size |
| `rewardRisk` | `decision.rewardRisk` | 直传 |
| `accountRiskPct` | `decision.accountRiskPct` | 直传（已是 0-100 区间，0.99 / 1.0 等典型值） |
| `earningsRisk` | `decision.earningsRisk` | SAFE/CAUTION/DANGER 直传 |
| `deterministicHash` | `decision.deterministicHash` | 直传（min 8 chars，DATA-MODEL 是 SHA-256 hex） |

> **注意**：schema 不接收 `target2r/target3r/rewardRisk/accountRiskPct/earningsRisk` 的可选语义，全部必填且 gt 0 / ge 0；当 decision 数据为 404 / 422 状态时，本组件**不挂载**（DecisionPanelWidget 仅在 data 存在分支才渲染本 section）。

**useQuery 行为（点击触发）**：

```ts
const [open, setOpen] = useState(false)

// 缓存键：ticker + deterministicHash
// 同 hash 复点 0 网络；override 后 decision 重算 → hash 变 → 新 queryKey → 新请求（自动）
const { data, isLoading, isFetching, error } = useQuery({
  queryKey: ['ai', 'trade_plan', decision.ticker, decision.deterministicHash],
  queryFn: () =>
    callAiTask<TradePlanInput, TradePlanOutput>(
      'trade_plan',
      buildTradePlanInput(decision),
    ),
  enabled: open,
  staleTime: 24 * 60 * 60 * 1000,
  gcTime: 24 * 60 * 60 * 1000,
  retry: false,
})

// 当 hash 变化（用户调 override 后），若 panel 仍开着 → 自动 refetch（react-query 行为）
// 不需要手动失效：queryKey 变了就是新查询
```

**渲染 — 6 状态（按优先级）**：

| # | 状态 | 渲染 |
|---|------|------|
| 1 | 关闭（`!open`） | 仅显示 `[Generate AI Plan]` 按钮 |
| 2 | 加载（`isLoading || (isFetching && !data)`） | 顶栏（标题 + ✕） + 2 个 Skeleton（memo 块占位 + management 列表占位）|
| 3 | 409 Guardrail violation | **红 banner**：`background: var(--color-error)15` 浅红底 + `color: var(--color-error)` 文案 "AI 输出被拦截 — 数字不匹配"，附 ✕ 关闭按钮 |
| 4 | 其他错误（502 / 429 / 500 等任意非 409 ApiError） | "AI 暂不可用"（`var(--color-text-secondary)`） + ✕ 关闭按钮 |
| 5 | 成功 | 顶栏（"AI Trade Plan" + Guardrail passed badge + cache 徽章 + ✕） + Memo 段落 + Mgmt 列表 |
| 6 | 数据存在但 `data.deterministicHash` 与当前 `decision.deterministicHash` 不一致（理论不发生，因 queryKey 已含 hash → 数据自然失效；保险起见 defensive 检查 — 见 §4 R1） | "deterministic 输入已变化，请重新生成" + ✕ |

**触发按钮**：

```tsx
<button
  data-testid="ai-plan-trigger"
  aria-label="Generate AI trade plan"
  onClick={() => setOpen(o => !o)}
  style={{
    padding: '6px 12px',
    borderRadius: '4px',
    border: '1px solid var(--color-border)',
    background: open ? 'var(--color-signal-breakout)' : 'var(--color-input-background)',
    color: open ? 'var(--color-text-on-dark)' : 'var(--color-text-primary)',
    cursor: 'pointer',
    fontSize: 'var(--font-size-caption)',
    fontWeight: 'var(--font-weight-medium)',
  }}
>
  Generate AI Plan
</button>
```

**Guardrail passed badge**（成功态顶栏内 inline）：

```tsx
<span
  data-testid="ai-plan-guardrail-passed"
  style={{
    fontSize: 'var(--font-size-badge)',
    color: 'var(--color-success)',
    fontWeight: 'var(--font-weight-medium)',
  }}
>
  ✓ Guardrail passed
</span>
```

**Cache 徽章**：`data.meta.cacheHit === true` 时 "Cached"；否则 "Generated · {modelUsed}"（与 F210-b 一致）。

**Memo 段落**：

```tsx
<p
  data-testid="ai-plan-memo"
  style={{
    fontSize: 'var(--font-size-caption)',
    color: 'var(--color-text-primary)',
    lineHeight: 'var(--line-height-normal)',
    margin: '6px 0',
    whiteSpace: 'pre-wrap',
  }}
>
  {data.output.memo}
</p>
```

**Management 列表**：

```tsx
<ol
  data-testid="ai-plan-management-list"
  style={{
    margin: 0,
    paddingLeft: '20px',
    fontSize: 'var(--font-size-caption)',
    color: 'var(--color-text-primary)',
  }}
>
  {data.output.management.map((rule, i) => (
    <li key={i} data-testid={`ai-plan-management-item-${i}`} style={{ padding: '2px 0' }}>
      {rule}
    </li>
  ))}
</ol>
```

#### 1.1.2 `frontend/src/cockpit/widgets/DecisionPanelWidget.tsx`（修改，~+8 行）

变更点（最小化）：

1. import `AiTradePlanSection`
2. 在 `data ? (...)` 分支的 `DecisionCard + OverrideForm` flex 容器**外**追加：

   ```tsx
   {data && (
     <div data-testid="ai-plan-divider" style={{ borderTop: '1px solid var(--color-border)', paddingTop: '8px', marginTop: '4px' }}>
       <AiTradePlanSection decision={data} />
     </div>
   )}
   ```

   位置：在 Header 区下、container 内的最末（容器原本是 flex column，本 section 自然挂在底部，scroll overflow 由 container 已设置）。

3. **不动**：empty state / loading / 422 / 404 / 一般 error 分支（这些状态下 decision data 不存在，不挂 AI section，自然隔离）。

#### 1.1.3 `frontend/src/cockpit/widgets/__tests__/DecisionPanelWidget.test.tsx`（修改 / 扩展，~+250 行）

新增测试 §T — AI Trade Plan（12 用例，路由 fetch mock 区分 `/cockpit/decision/` 与 `/ai/trade_plan`）：

| # | 用例 | 类型 |
|---|------|------|
| T1 | decision 加载成功 → 默认未点击：`[Generate AI Plan]` 按钮渲染，**未发起** `/ai/trade_plan` 请求 | 单元 |
| T2 | empty state（无 ticker） → 不渲染 AI section（按钮不存在） | 单元 |
| T3 | 404 / 422 / 一般 error 状态 → 不渲染 AI section | 单元 |
| T4 | 点击按钮 → 发 `POST /api/ai/trade_plan`，body.input 含 11 字段（ticker / setupType / setupQuality / entry / stop / target2r / target3r / size / rewardRisk / accountRiskPct / earningsRisk / deterministicHash），值与 mockDecision 严格相等（注意：entry=entryPrice / stop=stopPrice / size=suggestedShares 字段重命名） | 集成 |
| T5 | body.input 不包含多余字段（如 effectiveRiskPct / regimeCap / userSettingCap / earningsDate / riskPerShare / positionValue 6 字段） | 集成 |
| T6 | 加载期间显示 2 个 Skeleton；不重复发请求 | 集成 |
| T7 | 200 成功 → 渲染 memo / management 编号列表（n 项） / "✓ Guardrail passed" / cache 徽章 "Generated · {modelUsed}" | 集成 |
| T8 | 200 成功且 `meta.cacheHit=true` → cache 徽章显示 "Cached" | 集成 |
| T9 | 409 AI_GUARDRAIL_VIOLATION → 红 banner "AI 输出被拦截 — 数字不匹配"；不渲染 memo/management；DecisionCard 仍正常 | 集成 |
| T10 | 502 AI_PROVIDER_ERROR → "AI 暂不可用"；DecisionCard 仍正常；Override Form 仍可输入 | 集成 |
| T11 | 关闭再打开（同 ticker, hash）→ fetch 计数 = 1（react-query 缓存命中） | 集成 |
| T12 | 用户调 override → debounce 触发 decision refetch（不影响 AI 缓存）；当新 decision 返回新的 deterministicHash 时，AI section 仍开着 → queryKey 变 → 自动 refetch `/ai/trade_plan` 一次（验证 fetch 计数从 N 变 N+1） | 集成 |

> 测试架构：扩 `makeDecisionFetch` → `makeRoutedFetch`（按 URL prefix 路由 `/cockpit/decision/` vs `/ai/trade_plan`），保持 §S3-S8/S17 既有用例不变（继续用 `makeDecisionFetch` 实例或 `makeRoutedFetch({ aiStatus: 'unused' })` 兼容包装）。

---

### 1.2 排除（明确不做）

- ❌ **不动 backend**（F210-a 已落地 trade_plan + guardrail；本 sprint 仅前端）
- ❌ **不动 aiApi.ts / cockpitDecisionApi.ts**（已是通用客户端 + 11 字段类型齐全）
- ❌ **不动 SetupMonitorWidget / AiCandidateRankerSection**（F210-b 完成，互不干扰）
- ❌ **不加 `[Report]` 按钮**（design-spec.md line 1153 提到"v2.0 后续决定"，不在 F210 acceptance 内）
- ❌ **不动 store / 路由 / WidgetShell 框架**
- ❌ **不动 Save as PendingOrder 行为**（F206 范围）
- ❌ **不实现 AI Contradictions section**（F211 范围，design-spec.md line 1009-1012 占位）
- ❌ **不写 e2e**（集成测试已覆盖；e2e 留 acceptance 阶段视觉确认）
- ❌ **不动 design-spec.md / data-mapping.md**（设计稿 §Widget 6 + §Cockpit-6.c 已完整描述本 sprint 全部行为，规则 8 不触发）
- ❌ **不实现 retry 按钮 / cooldown / 持久化 result**（与 F210-b 一致）
- ❌ **不在 AI section 内做"重新计算 deterministic"或"对比模式"**（hash 变 → 自动 refetch 已是预期）

---

## 2. 预计修改文件清单（共 3 个，**远低于** 6 文件上限）

| 路径 | 操作 | 预计行数变化 |
|------|------|-------------|
| `frontend/src/cockpit/components/AiTradePlanSection.tsx` | 新建 | +250 |
| `frontend/src/cockpit/widgets/DecisionPanelWidget.tsx` | 修改 | +8 |
| `frontend/src/cockpit/widgets/__tests__/DecisionPanelWidget.test.tsx` | 修改 | +250 |

**附加（不计入 6 文件上限，规则 8 **不**触发 — 设计稿与映射均已就绪）**：
- 无文档回写

> 若开发中发现 `AiTradePlanSection` 行数偏高（>300），考虑抽 `ManagementList` / `MemoBlock` 子组件（仍在同一文件内，避免新增文件）。

---

## 3. 完成标准（每条可测试）

| # | 完成标准 | 测试层级 | 工具 |
|---|---------|---------|------|
| C1 | decision 加载成功后 `[Generate AI Plan]` 按钮渲染；未点击不发请求 | 单元 | vitest + RTL |
| C2 | decision 处于 empty / loading / 422 / 404 / error 状态时**不**渲染 AI section（按钮不存在） | 单元 | vitest + RTL |
| C3 | 点击按钮发 `POST /api/ai/trade_plan`，body 为 `{ input: {...11 字段}, noCache: false }`，字段名严格符合 backend `TradePlanInput` schema（entryPrice→entry / stopPrice→stop / suggestedShares→size 三处重命名正确） | 集成 | vitest + fetch mock |
| C4 | body.input 不含 effectiveRiskPct / regimeCap / userSettingCap / earningsDate / riskPerShare / positionValue 6 字段（schema `extra: forbid` 会 422 拒绝多余字段） | 集成 | vitest + fetch mock |
| C5 | 加载期间显示 2 个 Skeleton 且按钮处于 active 视觉态 | 集成 | vitest + RTL |
| C6 | 成功响应渲染 memo 段落 / management 编号列表（按 `data.output.management.length` 渲染对应 li） / "✓ Guardrail passed" badge / cache 徽章 | 集成 | vitest + RTL |
| C7 | `meta.cacheHit=true` → cache 徽章 "Cached"；`false` → "Generated · {modelUsed}" | 集成 | vitest + RTL |
| C8 | 409 AI_GUARDRAIL_VIOLATION → 红 banner "AI 输出被拦截 — 数字不匹配"（包含此文案 substring）；DecisionCard / OverrideForm 仍正常渲染 | 集成 | vitest + RTL |
| C9 | 502 AI_PROVIDER_ERROR → "AI 暂不可用"；DecisionCard 仍正常；Override Form 输入仍可改 | 集成 | vitest + RTL |
| C10 | 同 (ticker, deterministicHash) 关闭再开 → fetch 调用计数 = 1（react-query 缓存命中） | 集成 | vitest + fetch spy |
| C11 | override 调整 → decision refetch 返回新 hash → AI section 已展开时自动 refetch trade_plan 一次（fetch 计数从 N 变 N+1，且新请求 body.input.deterministicHash 等于新 hash） | 集成 | vitest + fetch spy |
| C12 | 类型检查通过 `pnpm tsc --noEmit` | 工程 | tsc |
| C13 | Lint 通过 `pnpm lint`（无新增 warning） | 工程 | eslint |
| C14 | 全量回归：所有 frontend 测试通过（cockpit + workbench + 共享，含 F210-b §R / F209-c §S / DecisionPanel §S3-S8/S17） | 回归 | vitest run |

---

## 4. 开发顺序（Generator 模式严格执行）

```
1. 确认 DATA-MODEL.md 无需改动 → ✅
2. 确认 API-CONTRACT.md 已涵盖 → ✅（F210-a 已涵盖 trade_plan task_type + guardrail + 409 错误码）
3-6. 跳过（前端 sprint）
7. 单元测试 + 集成测试 → 与 step 8 交叠
8. 前端组件 →
   8a. 新建 AiTradePlanSection.tsx（含类型 + buildInput + useQuery + 5 状态 + Guardrail badge / 红 banner / Memo / Mgmt）
   8b. DecisionPanelWidget.tsx 集成（仅 data 分支挂载，加 divider）
   8c. DecisionPanelWidget.test.tsx 扩展 §T 12 用例（含 makeRoutedFetch 路由 mock）
   8d. 写完 8a-c 后跑 `pnpm test` 验证 §T 全绿 + 既有 §S3-S8/S17 + F210-b §R + F209-c §S 全部无回归
9. tsc + lint 全绿
10. Evaluator 模式自检
```

每步通过最小验证后立即 wip commit（显式 add，禁用 `-A`）：
- step 8a → `wip(F210-c): trade plan section component`
- step 8b → `wip(F210-c): decision panel integration`
- step 8c → `wip(F210-c): tests §T green`

最终（Evaluator 通过后） → `feat(F210-c): DecisionPanel AI trade plan + guardrail banner`

---

## 5. Evaluator 自检清单

- [ ] 单元测试：T1 / T2 / T3 全部通过
- [ ] 集成测试：T4-T12 全部通过
- [ ] Guardrail 红 banner（T9）文案包含 "AI 输出被拦截" 与 "数字不匹配"（与 design-spec.md line 1022 措辞一致）
- [ ] AI section 在 decision 非 success 状态下完全不渲染（T2 / T3）
- [ ] body.input 字段名严格符合 backend `TradePlanInput` schema：11 字段 + entry/stop/size 三处重命名（T4 / T5）
- [ ] body.input 无多余字段（schema `extra: forbid`，T5 验证）
- [ ] cache 缓存命中时 fetch 计数不增（T10 / T11）
- [ ] override 触发新 hash 时 AI 自动 refetch（T12）
- [ ] 类型检查：`cd frontend && pnpm tsc --noEmit` 无错
- [ ] Lint：`cd frontend && pnpm lint` 无新增 warning
- [ ] 全量回归：`cd frontend && pnpm test --run` 全部测试仍绿（含 F209-c §S / F210-b §R / DecisionPanel §S3-S8/S17）
- [ ] 颜色 / 字体 / 间距全部走 `var(--*)`，无硬编码 hex / px（除已定义 token 引用）
- [ ] ✕ 关闭按钮仅设 `open=false`（不 invalidate query，缓存保留）
- [ ] DecisionCard / OverrideForm / Recompute / Save as PendingOrder 与 AI section 完全隔离（C8/C9 验证）
- [ ] 无 console.error 遗留
- [ ] `git status` 无遗留未提交改动

---

## 6. 开放问题（需用户确认或采用默认）

| # | 问题 | 默认 | 备选 |
|---|------|------|------|
| Q1 | AI section 是否始终挂载（render but `enabled: open && data != null`） vs 仅 `data` 分支挂载？后者意味着 query 实例随 decision 状态频繁 mount/unmount，可能丢 cache。前者要把 decision 选填化，typing 复杂 | **仅 `data` 分支挂载**（更简单；react-query 的 `gcTime: 24h` 在 unmount 后保留缓存 24h，重新 mount 命中相同 queryKey 仍是 cache hit；T11 验证此行为） | 始终挂载，组件内判断 `decision != null` |
| Q2 | 红 banner 文案：用 design-spec line 1022 "AI 输出被拦截 — 数字不匹配" vs line 1006 "Guardrail violation - AI output rejected" vs line 1153 同左？措辞不统一 | **采用 line 1022 中文版** "AI 输出被拦截 — 数字不匹配"（最近更新、最具体、与用户语言一致） | 英文版 / 折中"AI Plan rejected — guardrail mismatch" |
| Q3 | 红 banner 是否附 `[Report]` 按钮？design-spec.md line 1153 提到"v2.0 后续决定" | **不附**（设计明示后续决定，且无 backend endpoint 接收 report） | 附按钮但 disabled + tooltip "F211 阶段启用" |
| Q4 | 加载期间 Skeleton 数量与形态？memo 是段落（多行），management 是列表（最多 5 项） | **2 个 Skeleton**：一个 60px 高（memo 占位） + 一个 80px 高（mgmt 列表占位），简洁 | 1+5 = 6 个 Skeleton（精准映射输出结构） |
| Q5 | 用户在 AI section 已展开 + 已成功显示后调 override → decision 新 hash 到达。AI section 应：a) 立即 refetch 显示新结果；b) 保留旧结果直到用户手动重生成；c) 显示"已过期"提示 + 重生成按钮 | **a) 立即 refetch**（react-query 默认行为，queryKey 变就是新 query；与"deterministic 输入即输出"语义一致；T12 验证）。staleTime 24h 保护无关重渲染 | b 需手动控制 enabled；c 需额外 state，UI 复杂度↑ |
| Q6 | divider 与 AI section 之间：在 widget container 内（与 Decision/Override 同 padding） vs 突出显示（独立 card 浅底色） | **同 container 内**（最小化 layout 干扰；上方加 1px border-top 即可视觉分组） | 浅底色 card（更突出但占空间） |
| Q7 | management 列表用 `<ol>` vs `<ul>` vs custom `①②` 编号？design-spec line 1004 显示 "①②"  | **`<ol>` 自然编号 1./2./3.**（语义化，无需特殊字符；与 design-spec ①② 是视觉示意而非强约束） | custom prefix `①②③` 字符 |
| Q8 | 颜色 token：design-spec 未明示红 banner 用什么 token；项目 tokens.css 定义了 `--color-error: #d4183d` 但未定义 `--color-signal-danger`（DecisionPanelWidget.tsx line 364 使用了未定义 token，黑色显示，是 pre-existing bug） | **使用 `--color-error`**（已定义、语义化）；不修复既有 line 364 的 pre-existing bug（不在 sprint 范围） | 同样使用未定义 `--color-signal-danger` 保持"一致"（错上加错） |

> 默认采上表方案；如需备选方案请明确指出。

---

## 7. 风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| `decision.deterministicHash` 与 backend guardrail 计算的 hash 不一致（如 backend 公式更新但前端未同步），导致首次成功的 trade_plan 被 409 拒绝 | 低 | 用户看到红 banner 但 decision 显示正常，体验混乱 | F210-a 已 e2e 验证 hash 计算锁定 D068；本 sprint 不涉及 hash 计算，仅传递 |
| 字段重命名遗漏（entryPrice/stopPrice/suggestedShares → entry/stop/size）导致 schema 422 | 中 | 点击后所有用户都看 "AI 暂不可用" | T4 / T5 严格验证 body 字段名；类型 `TradePlanInput` 显式定义 9 + 2 = 11 字段名 |
| `decision.setupQuality === null` 时 schema 接受（`Literal[A,B,C] \| None`）但 frontend type `SetupQuality` 是否包含 null 需确认 | 低 | typescript 编译错 | 检查 `setupMonitorApi.ts` 的 `SetupQuality` 定义；若不含 null，`as 'A'\|'B'\|'C'\|null` 强转 |
| AI 输出的 `entry/stop/size` 等于 input 但 management 列表为 0 项 | 低 | render 空列表 | schema `min_length=1` 已强制；若仍发生 → schema validation 应 502 不返回 200，由 backend 处理 |
| 用户在 AI section 加载中调 override → decision refetch → hash 变 → trade_plan queryKey 变 → 中途取消旧请求 + 启新请求 | 中 | 双 spinner 闪烁 | react-query 默认行为，UX 可接受；fetch 计数测试 T12 处理 |
| 测试中 `makeRoutedFetch` 与既有 `makeDecisionFetch` 共存复杂度 | 中 | 测试代码膨胀 | 引入 `makeRoutedFetch({ decisionStatus, aiStatus, aiPayload })` 工厂，§S 测试切换为 `makeRoutedFetch({ decisionStatus: 200 })` 兼容包装 |
| `--color-error` (defined) vs `--color-signal-danger` (undefined) 选择争议 | 低 | 视觉不一致 | 默认 `--color-error`（Q8）；不修复 pre-existing bug |
| `target2r=0` / `target3r=0`（schema `gt=0` 拒绝）当 decision 数据异常时 | 低 | 422 报错 → "AI 暂不可用" | F203 已保证 target 字段在 success 分支恒 > 0；本 sprint 不挂载在异常分支（C2） |
| widget 容器高度紧（DecisionPanelWidget 默认 6 行高），AI section 展开后 overflow | 中 | 用户需要滚动 | container 已是 `overflow: auto`；section 默认收起 |

---

## 8. F210 收尾后状态预览（不属本 sprint）

F210-c done 后，F210 整体进入 acceptance：
- 后端：trade_plan + candidate_ranker 两 task_type 齐全（critical tier）
- 前端：SetupMonitor "AI 排序" + DecisionPanel "Generate AI Plan" 两入口齐全
- 验收门：features.json#F210 acceptance_criteria AC1-AC6 全部 covered
  - AC1（schema 齐全） → F210-a ✅
  - AC2（critical tier 路由） → F210-a ✅
  - AC3（trade_plan entry/stop/size 等于 deterministic） → F210-a guardrail ✅ + F210-c T8/T9 验证
  - AC4（candidate_ranker ≤ 20） → F210-a + F210-b ✅
  - AC5（top 3 + reason） → F210-b ✅
  - AC6（DecisionPanel memo + management 列表） → **F210-c（本 sprint）**

下一 feature：F211（contradiction_detector + news_summarizer + journal_assistant）。

---

确认 Contract 后我会：
1. 更新 `features.json`：`F210.sub_phases.F210-c.phase` = `contract_agreed`、`F210.sub_phases.F210-c.contract` 路径填入；`_pipeline_status.active_sprint = "F210-c"` / `active_sprint_phase = "contract_agreed"`
2. 更新 `claude-progress.txt`（追加 F210-c Contract 协商记录）
3. 生成新 `SESSION-HANDOFF.md`（覆盖 F210-b done 那份，下一步指向 F210-c Generator）
4. **停止**，建议你在新 session 开 Sonnet 进入 Generator 模式
