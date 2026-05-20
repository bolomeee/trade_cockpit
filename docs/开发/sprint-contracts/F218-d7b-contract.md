---
status: confirmed
drafted_at: 2026-05-20
confirmed_at: 2026-05-20
sprint: F218-d7b
parent_feature: F218
file_count_authorization: 10-file exception (user-approved 2026-05-20, same precedent as F217-c2c)
np_decisions: NP-d7b-1/2/3/4/5/6/7 全部 A（用户 2026-05-20 一次性确认）
---

# F218-d7b Sprint Contract — Repricing Trigger 前端 widget + DecisionPanel chip 区

> 生成：2026-05-20 | 状态：已确认 → 进入 Generator（下个 session）
> Feature：[F218](docs/需求/features.json) Cockpit Phase D — Repricing Trigger 完整框架（5 类）
> Sub-sprint：F218-d7b（Phase D 10 sub-sprint 第 10 个 / 最后一个；前端闭环）
> 前置：F218-d7a done（cron 22:40 UTC + 2 endpoint 已上线，HTTP 出口可消费）
> 下游：无（d7b 收官后 F218 整体 sub_sprints 全 done → consistency-check C1 触发父 feature 升 done 待 acceptance）

> 引用文档：
> - [API-CONTRACT.md](docs/系统设计/API-CONTRACT.md) §Cockpit Repricing Triggers 1988-2106（2 endpoint 完整契约 / triggerType 枚举 / evidence 5 类形态 / 错误响应）
> - [DATA-MODEL.md](docs/系统设计/DATA-MODEL.md) §RepricingTrigger 1080-1129（5 类 evidence_json schema / confidence 0.0-1.0）
> - [design-spec.md](docs/设计/design-spec.md) §Widget 6 DecisionPanelWidget 1000-1047（chip 区将插入位置参考） / §Workbench v1.8 Cockpit 帧 660-706（CockpitGrid 12 col 布局）
> - [component-plan.md](docs/设计/component-plan.md) §Cockpit Widget 组件 339-352（widget 注册表 + 命名约定）
> - [F218-d7a-contract.md](docs/开发/sprint-contracts/F218-d7a-contract.md) — 上游 sprint 完成清单
> - [tokens.css](frontend/src/styles/tokens.css) — `--color-setup-*` / `--color-signal-*` 现有体系（5 类 trigger 新增 token 仿同模式）
> - [cockpitPoolApi.ts](frontend/src/cockpit/lib/api/cockpitPoolApi.ts) — API client URLSearchParams 模式样板
> - [cockpitDecisionApi.ts](frontend/src/cockpit/lib/api/cockpitDecisionApi.ts) — 类型定义 + apiFetch 用法样板
> - [SetupMonitorWidget.tsx](frontend/src/cockpit/widgets/SetupMonitorWidget.tsx) — 表格 widget 样板（行点击 → cockpitStore.setSelectedTicker）
> - [DecisionPanelWidget.tsx](frontend/src/cockpit/widgets/DecisionPanelWidget.tsx) — header 行下方将插入 chip 区

---

## 0. 背景与定位

d7a 把后端环（cron + router）闭合后，前端仍无法消费 trigger 数据。d7b 把"消费 + 展示"两件事接线，闭合 Phase D 全栈环：

- **API client**：包一层 `cockpitRepricingApi.ts`，把 2 endpoint 暴露为 React Query 友好的纯函数
- **独立 widget**：`RepricingTriggerWidget.tsx` 表格展示全市场 active triggers，提供 triggerType filter + 行点击 → cockpitStore.setSelectedTicker 联动
- **DecisionPanel chip 区**：持仓 ticker 切换时拉 `/repricing-triggers/{ticker}`，命中 ≥1 显示 5 类彩色 chip（hover 显 evidence 概要）
- **5 类 trigger 色板**：在 `tokens.css` 新增 5 个 `--color-trigger-*` token，widget 与 chip 共用
- **文档内联同步**：design-spec.md 新增 §Widget X RepricingTrigger + DecisionPanel chip 区描述；component-plan.md cockpit widgets 表新增一行（NP-init-4=A 内联模式）

d7b 不动后端、不动 cron、不动 endpoint 契约、不动其他 widget。

---

## 1. 实现范围

### 1.1 API client（`frontend/src/cockpit/lib/api/cockpitRepricingApi.ts`，新建）

类型定义：

```ts
export type TriggerType =
  | 'EARNINGS_ACCEL'
  | 'MARGIN_EXPANSION'
  | 'NEW_PRODUCT'
  | 'SECTOR_CYCLE'
  | 'BALANCE_INFLECTION'

export type EarningsAccelEvidence = {
  epsYoyGrowth: number[]
  revenueYoyGrowth: number[]
  quarters: string[]
}
export type MarginExpansionEvidence = {
  grossMarginTrend: number[]
  fcfMarginTrend: number[]
  quarters: string[]
  triggerMetric: 'gross_margin' | 'fcf_margin'
  expansionBp: number
}
export type NewProductEvidence = {
  keywordHits: Record<string, number>
  newsLinks: Array<{ title: string; url: string; publishedAt: string }>
}
export type SectorCycleEvidence = {
  sector: string
  rsHistory: number[]
  priceVs200d: number
}
export type BalanceInflectionEvidence = {
  netDebtTrend: number[]
  fcfTrend: number[]
  quarters: string[]
  triggerMetric: 'net_debt' | 'fcf'
}
export type TriggerEvidence =
  | EarningsAccelEvidence
  | MarginExpansionEvidence
  | NewProductEvidence
  | SectorCycleEvidence
  | BalanceInflectionEvidence

export type RepricingTrigger = {
  triggerType: TriggerType
  detectedDate: string
  confidence: number
  evidence: TriggerEvidence
  computedAt: string
}
export type RepricingTriggerWithTicker = RepricingTrigger & { ticker: string }

export type TickerTriggersPayload = {
  ticker: string
  triggers: RepricingTrigger[]
}
export type AllTriggersPayload = {
  triggers: RepricingTriggerWithTicker[]
  totalCount: number
  computedAt: string
}
```

函数：

```ts
export function getTickerRepricingTriggers(ticker: string): Promise<TickerTriggersPayload>
export type GetAllActiveTriggersOptions = {
  triggerType?: TriggerType
  limit?: number  // 默认不传 = 后端 100，上限 500
}
export function getAllActiveTriggers(opts?: GetAllActiveTriggersOptions): Promise<AllTriggersPayload>
```

实现要点：
- 用 `apiFetch<T>` + `URLSearchParams`（参照 cockpitPoolApi.ts）
- ticker 在调用前 `toUpperCase()`（后端虽然也做，前端 cache key 稳定）
- 422 / 404 让 apiFetch 抛 ApiError，由调用方处理

### 1.2 RepricingTriggerWidget（`frontend/src/cockpit/widgets/RepricingTriggerWidget.tsx`，新建）

视觉规格（详见 §1.6 design-spec.md 内联更新）：

```
┌─RepricingTriggerWidget Shell─────────────────────────────────┐
│ Repricing Triggers · 47 active  [All ▾]              [⟳]    │ ← title + filter + refresh
├──────────────────────────────────────────────────────────────┤
│ Ticker  Trigger              Date        Conf  Evidence      │
│ NVDA    🟦 MARGIN_EXPANSION  2026-05-15  0.80  gross +900bp  │
│ TSLA    🟪 BALANCE_INFLECTION 2026-05-14  0.50  net_debt ↓   │
│ AAPL    🟩 EARNINGS_ACCEL    2026-05-13  0.80  eps yoy 78%   │
│ ...                                                          │
└──────────────────────────────────────────────────────────────┘
```

- **数据源**：`useQuery(['cockpit-repricing-all', triggerType], () => getAllActiveTriggers({ triggerType }))`，`staleTime: 5 * 60 * 1000`（cron 每日跑一次，5 分钟内复用合理）
- **filter**：title 行右侧 shadcn `Select`（5 类 + "All" = 6 选项），切换时 react-query refetch
- **表格列**：Ticker（mono 字体） / Trigger（chip：色块 + 简称缩写如 "EarningsAccel" / "MarginExp" / "NewProduct" / "SectorCycle" / "BalanceInflect"） / Date（YYYY-MM-DD） / Conf（保留 2 位小数） / Evidence（按 triggerType 渲染 1 行概要，详见 §1.5）
- **行交互**：行点击 → `cockpitStore.setSelectedTicker(ticker)`；hover 整行 `--color-muted` 背景
- **排序**：按后端返回顺序（`detectedDate` 倒序 + 同日 `confidence` 倒序），不在前端再排
- **总数显示**：title "Repricing Triggers · 47 active"，N = payload.totalCount（filter 后总数）
- **refresh 按钮**：右上角图标按钮，refetch 当前 query
- **状态机**：
  - 正常：渲染表格
  - 空（`totalCount === 0`）：EmptyState "今日全市场无 active trigger（cron 每日 22:40 UTC 后刷新）"（`--color-text-secondary`）
  - 加载：SkeletonCard（复用既有）
  - 错误：`<p style={color: --color-text-secondary}>加载失败，请稍后重试</p>` + retry 按钮
- **不实现**：分页（v1.0 用 limit=100 上限；超过 100 显示 "显示 100 / 总 N"，v2.0 再扩展）

### 1.3 注册到 CockpitRegistry（`frontend/src/cockpit/CockpitRegistry.ts`，修改）

新增 `category: 'repricing'`（CockpitWidgetCategory union 扩展），并新增 manifest：

```ts
'cockpit.repricing-trigger': {
  id: 'cockpit.repricing-trigger',
  title: 'Repricing Triggers',
  component: RepricingTriggerWidget,
  defaultLayout: { x: 6, y: 43, w: 6, h: 10, minW: 4, minH: 6 },
  category: 'repricing',
},
```

布局位置：与 Weekly Stage（`x:0 y:43 w:6 h:10`）并列同一行右半，y=43 接续既有底部布局。

### 1.4 DecisionPanel chip 区（`frontend/src/cockpit/widgets/DecisionPanelWidget.tsx`，修改）

插入位置：header 行（`{headerTitle}`，第 367-378 行）下方、body 状态分支之前，插入 chip 容器 div：

```tsx
<RepricingChipRow ticker={ticker} />
```

`RepricingChipRow` 作为本文件内 helper component（不单独抽 sub-component 以控制 d7b 文件数）：
- 调用 `useQuery(['cockpit-repricing-ticker', ticker], () => getTickerRepricingTriggers(ticker), { staleTime: 5 * 60 * 1000, enabled: ticker != null })`
- 加载 / 错误 → 渲染 `null`（chip 区静默，不阻碍主面板）
- `triggers.length === 0` → 渲染 `null`（API 契约：空数组属正常态，不报错）
- `triggers.length > 0` → 渲染 chip flex 行：每个 trigger 一个 chip
  - chip 视觉：`8px` 高，`6px 8px` 内边距，圆角 `4px`，背景 `var(--color-trigger-{type})` 16% alpha，文字 `var(--color-trigger-{type})`，字体 `--font-size-caption`
  - chip 文字：简称（EarningsAccel / MarginExp / NewProduct / SectorCycle / BalanceInflect）
  - hover：tooltip 显 evidence 单行概要（同 §1.5 widget 表格 Evidence 列规则）；shadcn `Tooltip` 实现
- 不影响既有 22 错误 / 404 / loading / data 分支逻辑，仅作为 header 下方独立区域

### 1.5 Evidence 摘要规则（widget 表格列 + chip hover tooltip 共用）

| triggerType | 摘要模板 | 示例 |
|-------------|---------|------|
| EARNINGS_ACCEL | `eps yoy {last}%` | `eps yoy 78%` |
| MARGIN_EXPANSION | `{triggerMetric} +{expansionBp}bp` | `gross +900bp` / `fcf +550bp` |
| NEW_PRODUCT | `{N} keywords / {M} news` | `3 keywords / 5 news` |
| SECTOR_CYCLE | `{sector} RS {first}→{last}` | `XLK RS 35→68` |
| BALANCE_INFLECTION | `{triggerMetric} ↓ {pct}%` 或 `fcf flip +` | `net_debt ↓ 21%` / `fcf flip +` |

摘要逻辑写为本地 helper `summarizeEvidence(t: RepricingTrigger): string`，在 widget 文件内。

### 1.6 tokens.css（修改，新增 5 token）

在既有 `--color-setup-*` 块之后追加：

```css
/* F218 Repricing Trigger 5 类色板（widget chip + DecisionPanel chip 共用） */
--color-trigger-earnings-accel: #15803d;     /* green-700, 业绩加速 */
--color-trigger-margin-expansion: #0891b2;   /* cyan-600, 毛利扩张 */
--color-trigger-new-product: #db2777;        /* pink-600, 新产品周期 */
--color-trigger-sector-cycle: #d97706;       /* amber-600, sector 轮动 */
--color-trigger-balance-inflection: #7c3aed; /* violet-600, 资产负债拐点 */
```

颜色避开既有 `--color-setup-*`/`--color-signal-*` 冲突（review：earnings setup pink 已占 #ec4899 → trigger new_product 用 #db2777 更深一档；capitulation purple 已占 #8b5cf6 → trigger balance_inflection 用 #7c3aed 更深一档）。

提供 helper：

```ts
// 在 widget 文件顶部，仿 weeklyStageTokens.ts 模式
export const TRIGGER_COLOR_TOKEN: Record<TriggerType, string> = {
  EARNINGS_ACCEL: 'var(--color-trigger-earnings-accel)',
  MARGIN_EXPANSION: 'var(--color-trigger-margin-expansion)',
  NEW_PRODUCT: 'var(--color-trigger-new-product)',
  SECTOR_CYCLE: 'var(--color-trigger-sector-cycle)',
  BALANCE_INFLECTION: 'var(--color-trigger-balance-inflection)',
}
```

### 1.7 文档内联更新（design-spec.md / component-plan.md，修改）

**design-spec.md**：
- §Widget 6 DecisionPanelWidget 章节追加 chip 区描述（在「数据源」段下方加 "Repricing chip 区" 子段）
- 在 §Widget 7+（具体编号待定）后追加 `## Widget X：RepricingTriggerWidget（F218）`，完整规格 ≈ 80 行，参照既有 WeeklyStageChartWidget 模版

**component-plan.md**：
- §Cockpit Widget 组件表（行 343-351）追加一行：`RepricingTriggerWidget | F218 | GET /api/cockpit/repricing-triggers + GET /api/cockpit/repricing-triggers/{ticker}（chip 区共用）`

---

## 2. 预计修改文件清单（共 10 个 — 用户已授权超 6 例外，同 F217-c2c 模式）

| # | 文件 | 性质 | LOC 预估 |
|---|------|------|---------|
| 1 | `frontend/src/cockpit/lib/api/cockpitRepricingApi.ts` | 新建 | ~80 |
| 2 | `frontend/src/cockpit/widgets/RepricingTriggerWidget.tsx` | 新建 | ~220 |
| 3 | `frontend/src/cockpit/CockpitRegistry.ts` | 修改 | +10 |
| 4 | `frontend/src/cockpit/widgets/DecisionPanelWidget.tsx` | 修改 | +60 |
| 5 | `frontend/src/styles/tokens.css` | 修改 | +7 |
| 6 | `frontend/src/cockpit/lib/api/__tests__/cockpitRepricingApi.test.ts` | 新建 | ~140 |
| 7 | `frontend/src/cockpit/widgets/__tests__/RepricingTriggerWidget.test.tsx` | 新建 | ~280 |
| 8 | `frontend/src/cockpit/widgets/__tests__/DecisionPanelWidget.test.tsx` | 修改 | +120 |
| 9 | `docs/设计/design-spec.md` | 修改 | +90 |
| 10 | `docs/设计/component-plan.md` | 修改 | +2 |

**总计：4 新建 + 6 修改**。

---

## 3. 完成标准（Evaluator 测试用例）

| # | 测试描述 | 层级 | 工具 |
|---|---------|------|------|
| **A. API client（cockpitRepricingApi.test.ts）** | | | |
| A1 | `getTickerRepricingTriggers('nvda')` 调用 `/cockpit/repricing-triggers/NVDA`（自动 upper），返回 TickerTriggersPayload | 单元 | vitest + msw |
| A2 | `getAllActiveTriggers()` 不传参 → 调用 `/cockpit/repricing-triggers`（无 query string） | 单元 | vitest + msw |
| A3 | `getAllActiveTriggers({ triggerType: 'MARGIN_EXPANSION', limit: 50 })` → URL 含 `?triggerType=MARGIN_EXPANSION&limit=50` | 单元 | vitest + msw |
| A4 | 后端返回空 `triggers: []` + `totalCount: 0` → 函数返回该结构（不抛错） | 单元 | vitest + msw |
| A5 | 后端返回 422 → 抛 ApiError，status=422 | 单元 | vitest + msw |
| A6 | TypeScript：5 类 evidence union 在 narrow（switch on triggerType）后类型正确 | 编译时 | tsc |
| **B. RepricingTriggerWidget（RepricingTriggerWidget.test.tsx）** | | | |
| B1 | mount 时调用 `getAllActiveTriggers()` 一次，渲染骨架屏 | 单元 | RTL + msw |
| B2 | 返回 3 行 triggers → 渲染 3 行表格，列顺序 ticker/trigger/date/conf/evidence 正确 | 单元 | RTL |
| B3 | filter 切换 "MARGIN_EXPANSION" → query 重新发起，URL 含 triggerType 参数 | 单元 | RTL + msw |
| B4 | 行点击 → cockpitStore.setSelectedTicker 被调用一次（mock store） | 单元 | RTL + vi.fn |
| B5 | 空状态：totalCount=0 → 渲染 "今日全市场无 active trigger..." EmptyState | 单元 | RTL |
| B6 | 错误状态：网络错误 → 渲染 "加载失败，请稍后重试" + retry 按钮 | 单元 | RTL |
| B7 | refresh 按钮点击 → query refetch | 单元 | RTL |
| B8 | 5 类 trigger chip 色 token 渲染正确（assert inline style 含 `var(--color-trigger-*)`） | 单元 | RTL |
| B9 | evidence 摘要：MARGIN_EXPANSION 渲染 "gross +900bp" / EARNINGS_ACCEL 渲染 "eps yoy 78%" / 等 5 类各覆盖 1 例 | 单元 | RTL |
| **C. DecisionPanel chip 区（DecisionPanelWidget.test.tsx 增量）** | | | |
| C1 | ticker=null → chip 区不渲染（空 ticker 整 widget empty state 优先） | 单元 | RTL |
| C2 | ticker='NVDA' 且 API 返回 2 triggers → 渲染 2 个 chip，颜色对应 token | 单元 | RTL + msw |
| C3 | ticker='AAPL' 且 API 返回空数组 → chip 区不渲染（null），decision 主面板正常 | 单元 | RTL + msw |
| C4 | API 加载中 → chip 区 null（不阻塞 SkeletonCard） | 单元 | RTL + msw |
| C5 | API 错误 → chip 区 null（静默） | 单元 | RTL + msw |
| C6 | hover chip → tooltip 显 evidence 概要 | 单元 | RTL + userEvent |
| **D. Registry / 集成** | | | |
| D1 | `COCKPIT_WIDGET_REGISTRY['cockpit.repricing-trigger']` 存在，category='repricing' | 单元 | vitest |
| D2 | `getCockpitDefaultLayout()` 输出包含新 widget 的 LayoutItem | 单元 | vitest |
| **E. 视觉对齐 / 回归** | | | |
| E1 | Evaluator 手动浏览器跑（mock cron 数据塞 2 条 trigger）→ widget 表格在 Cockpit 页可见 | 手动 | dev server |
| E2 | Evaluator 浏览器手动验：选中持仓 ticker → DecisionPanel chip 渲染正确 | 手动 | dev server |
| E3 | 既有 110 cockpit 前端测试全绿（DecisionPanelWidget 既有 + SetupMonitor + 等等） | 集成 | vitest |
| E4 | 全量前端 lint 通过（pnpm lint），无新增 warning | 集成 | eslint |
| E5 | 全量前端 typecheck 通过（pnpm typecheck） | 集成 | tsc |

**预估测试总数**：A6 + B9 + C6 + D2 = **23 新增测试** + DecisionPanel 既有 ~30 测试不退化。

---

## 4. 自检清单（Evaluator 模式使用）

- [ ] 23 新测试全部通过
- [ ] DecisionPanelWidget 既有测试无回归
- [ ] 全量前端测试通过（pnpm test）
- [ ] Lint 通过，无新增 warning
- [ ] TypeScript typecheck 通过
- [ ] CockpitRegistry 新 manifest 在 Cockpit 页可见可拖拽
- [ ] 5 类 trigger 颜色对照 §1.6 与既有 setup/signal token 无视觉冲突
- [ ] evidence 5 类摘要按 §1.5 规则渲染正确
- [ ] design-spec.md / component-plan.md 已同步内联更新
- [ ] DECISIONS.md 无需追加（本 sprint 无新决策点，色板选择属于设计选择不达决策门槛）
- [ ] phase 顺序：in_progress → testing → needs_review，不跳步
- [ ] consistency-check (mode=interactive) 通过（C1 校验：d7b done 后 sub_sprints 全 done → 父 F218 待 acceptance）

---

## 5. 待用户裁决的开放点（NP-d7b-*）

⚠️ **本合约确认前请逐项裁决，未决项默认按推荐值落定**。

### NP-d7b-1：5 类 trigger 色板取值
- **推荐 A**：§1.6 提议的 5 色（绿/青/桃/琥珀/紫），避开既有 setup/signal 冲突
- **B**：复用既有 setup 色板（earnings pink + capitulation violet + …），减少 token 数量但视觉语义混淆
- **C**：你自定义另一组色板（请直接列出）

### NP-d7b-2：widget 默认布局位置
- **推荐 A**：`x:6 y:43 w:6 h:10`（Weekly Stage 右半，底部新行）
- **B**：`x:0 y:53 w:12 h:8`（独立新行宽屏，更醒目但占空间）
- **C**：你指定其他坐标

### NP-d7b-3：DecisionPanel chip 区位置
- **推荐 A**：header 行下方、body 状态分支之前，作为常驻区
- **B**：放在 DecisionCard 内部右上角（节省垂直空间但与 AI plan / contradictions 段并列时视觉拥挤）
- **C**：折叠区（默认折叠，命中 ≥1 才自动展开）

### NP-d7b-4：表格分页策略
- **推荐 A**：v1.0 用 limit=100 上限，超 100 显示 "显示 100 / 总 N"，v2.0 再扩展虚拟滚动
- **B**：v1.0 直接接 limit=500（API 上限），不分页（依赖 cron 出量级评估，按 sub_sprint_notes 预期"每日全市场 5 类合计数十至百量级"应足够）
- **C**：v1.0 实装分页（page size 25 + 上下页按钮，每翻页重发 query）

### NP-d7b-5：chip 简称命名
- **推荐 A**：EarningsAccel / MarginExp / NewProduct / SectorCycle / BalanceInflect（10-13 字符，紧凑）
- **B**：业绩加速 / 毛利扩张 / 新产品 / Sector 轮动 / 资产拐点（中文，更直观但与既有 setup type 英文不一致）
- **C**：你指定其他文案

### NP-d7b-6：refresh 按钮位置
- **推荐 A**：widget title bar 右上角图标按钮（仿 PoolBuilderWidget）
- **B**：不实装手动 refresh，依赖 react-query staleTime 自动 refetch（5 分钟过期）
- **C**：title bar 右侧加 "Last refresh: HH:MM" 文本 + refresh 按钮

### NP-d7b-7：开发顺序
- **推荐 A**：API client → widget 独立跑通 → registry 注册 → DecisionPanel chip 区 → 文档内联 → 测试补全（先跑通最小 vertical slice，再补 cross-cut）
- **B**：tokens.css → API client + 类型 → widget UI 骨架 → DecisionPanel chip 骨架 → 两侧 evidence 摘要 helper 共用 → 测试补全（共用基础先打牢，UI 后续再接）

---

## 6. 风险与对冲

| 风险 | 概率 | 对冲 |
|------|------|------|
| 10 文件单 sprint context 失控 | 中 | 规则 7 强制每 step wip commit；按 NP-d7b-7 顺序分 7 step；Generator 模式严格按 step 推进 |
| DecisionPanel 现有 421 行被改坏 | 中 | 改动仅插入 1 个 helper component 调用（§1.4 设计为最小侵入）；E3 既有测试无回归门禁 |
| 5 类色板与既有 token 视觉冲突 | 低 | §1.6 已 review 避开 #ec4899/#8b5cf6 复用；NP-d7b-1 用户最后确认 |
| evidence 5 类形态在 v2.0 后端扩展时 union 不兼容 | 低 | 类型独立 `TriggerEvidence` union，扩展时只需补一类；本 sprint 与后端 d1-d6b 当前 schema 1:1 对齐 |
| 测试 mock 数据组装繁琐 | 中 | 提供 `__fixtures__/repricingTriggers.ts`（不计入 10 文件，作为测试内 fixture inline 即可，避免新增独立 fixture 文件） |

---

## 7. 完成后的状态推进

1. Evaluator 全绿 → 更新 `features.json` `F218.sub_sprints["F218-d7b"]` → `needs_review`
2. **强制**调用 consistency-check skill (mode=interactive)：
   - C1：sub_sprints 全 done 后才能升父 → d7b 升 needs_review 时 F218 父 phase 保持 in_progress（不升 done，等 acceptance）
   - C4：iteration_history 补 F218-d7b 记录
   - C5：sub_sprints["F218-d7b"] entry 存在 ✓
3. consistency-check 全清 → 输出 SESSION-HANDOFF.md → 通知用户进 acceptance
4. acceptance 通过 → F218-d7b → done，进而 consistency-check C1 触发父 F218 → done（Phase D 整体收官）

---

## 8. 不在本 sprint 范围（明确排除）

- 后端任何变更（cron / endpoint / detector / repo / FMP 数据源）
- AI 集成（trigger 的 AI 总结 / brief，留 v2.0）
- evidence 详情弹窗（chip hover tooltip 单行即止，详情待 v2.0）
- 历史 trigger 时间序列展示（仅 `active=true` 当前态，历史回看待 v2.0）
- T3 NEW_PRODUCT 的 news link 点击跳外站（chip hover tooltip 显文字即止，跳转待 v2.0）
- DecisionPanel chip 区的可点击行为（hover only；点击交互留 v2.0）
- 全量 e2e 测试（vitest 单元 + 集成已足够覆盖；e2e 留 acceptance 阶段手动跑）
