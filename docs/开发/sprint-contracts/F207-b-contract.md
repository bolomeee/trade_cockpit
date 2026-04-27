# Sprint Contract：F207-b — ActionListWidget（前端三栏动作清单）

> 状态：草案，待用户确认 | 起草：2026-04-27
> 父 Feature：F207 Daily Action List Widget（v1.9 Cockpit P1）
> 拆分：F207-a ✅（后端 rule engine + endpoint）/ **F207-b（本 sprint，前端 ActionListWidget）**
> 依赖：
>   - F207-a ✅（`GET /api/cockpit/actions/today` 已上线，返回 `{ asOfDate, mustAct, monitor, noAction }`）
>   - F206-c2 ✅（`PendingOrdersWidget` 已注册到 `COCKPIT_WIDGET_REGISTRY`，本 sprint 在其下方追加 ActionList）
>   - 既有：`useCockpitStore.setSelectedTicker` / `--color-action-{must,monitor,noaction}-bg` tokens / `apiFetch` / `react-query` / `vitest + RTL`
>
> 引用文档：
>   - API-CONTRACT.md §GET /api/cockpit/actions/today（line 1584-1644：响应 schema + actionType 枚举表）
>   - design-spec.md §Widget 9 ActionListWidget（line 1088-1119：分栏 UI、配色、交互）
>   - F207-a 合约 §1.1.2（refs 字段集 / rationale 模板，已固定）
>   - DECISIONS.md D060（cockpit RGL 独立 Registry）/ D063（不复用 workbench）/ D074（camelCase）
>   - 模板参考：
>     - `frontend/src/cockpit/widgets/PendingOrdersWidget.tsx`（容器骨架 + 4 状态 + react-query staleTime 30s）
>     - `frontend/src/cockpit/widgets/_pendingOrderRow.tsx`（行级子组件 + style token 引用风格）
>     - `frontend/src/cockpit/widgets/SetupMonitorWidget.tsx`（`setSelectedTicker(ticker)` 联动 + `title=` tooltip）
>     - `frontend/src/cockpit/lib/api/cockpitPendingOrdersApi.ts`（API client + camelCase 类型）
>     - `frontend/src/cockpit/lib/api/__tests__/cockpitPendingOrdersApi.test.ts`（client unit test 模板）
>     - `frontend/src/cockpit/widgets/__tests__/PendingOrdersWidget.test.tsx`（vitest + RTL fetch stub 模板）

---

## 0. 背景与定位

F207 后端 rule engine 已落地（F207-a），输出 `mustAct / monitor / noAction` 三数组。本 sprint 把数据接到前端 widget：**三栏卡片样式**、点击 ticker 联动 chart/decision、hover 显示完整 rationale，最后注册到 `COCKPIT_WIDGET_REGISTRY`。

**核心难点**：
1. 三栏背景色已有 token，但 widget 内部分区高度自适应 + 空栏处理（某栏无数据时整段不渲染 vs 渲染空标题）—— §7 Q1 决策。
2. `refs` 字段是弱类型 dict，actionType 不同字段集不同。前端要不要做 typed 区分？—— §7 Q2 决策（直接照原样作为 hover 调试信息附加显示）。
3. 设计稿里"AI Daily Brief 折叠区"是 v2.0 范畴，明确 **F207-b 不做**；保留挂载点占位（注释）以减少 F209/F211 改动量 —— §7 Q3 决策。
4. 已有持仓 widgets 用 native `title=` 做 tooltip（见 `SetupMonitorWidget.tsx:269`），保持一致，**不引入 shadcn Tooltip**（避免增加文件数）。

**关键约束**：

1. **API client 函数签名固定**：
   ```ts
   export function getTodayActions(): Promise<TodayActionsPayload>
   ```
   `TodayActionsPayload` 即响应 `data` 部分（`{ asOfDate, mustAct, monitor, noAction }`），与 `getPendingOrders` 一致让 `apiFetch` 自动剥 `data`。

2. **类型严格按 F207-a 已落地的响应**：
   - `actionType` 用 `Literal` union 类型（6 个值），便于 widget 内 switch label 映射
   - `refs` 类型为 `Record<string, unknown>`（弱类型，与后端弱契约一致；§7 Q2）
   - 前端**不**根据 actionType 反推 refs 字段集（否则一旦后端扩 actionType 就会编译失败）；只在 hover 时把 `JSON.stringify(refs)` 拼到 tooltip 末尾给开发自检用

3. **selectedTicker 联动**：行任意位置点击都触发 `setSelectedTicker(ticker)`（与 SetupMonitorWidget 一致），不限定只点 ticker 列。光标 `cursor: 'pointer'`。

4. **空态分级**：
   - 三栏全空（fetch 成功但 `mustAct.length=0 && monitor.length=0 && noAction.length=0`）→ 整 widget 显示空态文案 "暂无今日动作"（§7 Q1 决策 a：粗粒度空态）
   - 单栏空 → 该栏整段不渲染（不显示空标题）
   - fetch 失败 / loading → 与 PendingOrdersWidget 完全一致的错误 banner / Skeleton

5. **as_of_date 显示**：右上角，原样 ISO `YYYY-MM-DD`，灰色 caption（与设计稿 `2026-04-24` 一致）。fetch 失败 / loading 时不显示日期。

6. **Widget 注册槽位**：`x:0 y:16 w:12 h:6`，`minW:6 minH:4`（F207-a §7 Q6 已确认）。位于 PositionList + PendingOrders 那一行（y:8 h:8）的正下方，全宽。

7. **react-query 缓存**：`queryKey: ['cockpit-actions-today']`，`staleTime: 30 * 1000`（与 pending-orders / positions 对齐）。无 mutation，不需要 invalidate 链路。

---

## 1. 实现范围

### 1.1 包含

#### 1.1.1 `frontend/src/cockpit/lib/api/cockpitActionsApi.ts`（新建，~50 行）

```ts
import { apiFetch } from '@/lib/api/client'

export type ActionType =
  | 'raise_stop'
  | 'cancel_order'
  | 'reduce_before_earnings'
  | 'tighten_stop'
  | 'approaching_trigger'
  | 'stable_position'

export type ActionItem = {
  ticker: string
  actionType: ActionType
  rationale: string
  refs: Record<string, unknown>
}

export type TodayActionsPayload = {
  asOfDate: string         // ISO 'YYYY-MM-DD'
  mustAct: ActionItem[]
  monitor: ActionItem[]
  noAction: ActionItem[]
}

export function getTodayActions(): Promise<TodayActionsPayload> {
  return apiFetch<TodayActionsPayload>('/cockpit/actions/today')
}
```

**说明**：
- 与 `cockpitPendingOrdersApi.ts` 风格完全一致（`apiFetch` 自动剥 `data`）。
- `ActionType` union 后续 widget 内 label 映射用，不导出到其他模块（避免横向耦合）。

#### 1.1.2 `frontend/src/cockpit/widgets/_actionListSection.tsx`（新建，~110 行）

单栏渲染组件 + actionType label 映射 + 行点击逻辑。

```tsx
import type { ActionItem, ActionType } from '../lib/api/cockpitActionsApi'

export type ActionSectionVariant = 'must' | 'monitor' | 'noaction'

const SECTION_TITLE: Record<ActionSectionVariant, string> = {
  must: 'Must Act',
  monitor: 'Monitor',
  noaction: 'No Action',
}

const SECTION_BG: Record<ActionSectionVariant, string> = {
  must: 'var(--color-action-must-bg)',
  monitor: 'var(--color-action-monitor-bg)',
  noaction: 'var(--color-action-noaction-bg)',
}

const ACTION_LABEL: Record<ActionType, string> = {
  raise_stop: 'Raise Stop',
  cancel_order: 'Cancel Order',
  reduce_before_earnings: 'Reduce (Earnings)',
  tighten_stop: 'Tighten Stop',
  approaching_trigger: 'Approaching Trigger',
  stable_position: 'Stable',
}

type Props = {
  variant: ActionSectionVariant
  items: ActionItem[]
  onTickerClick: (ticker: string) => void
}

export function ActionListSection({ variant, items, onTickerClick }: Props) {
  if (items.length === 0) return null   // §7 Q1 决策：空栏整段不渲染
  return (
    <section
      data-testid={`action-section-${variant}`}
      style={{
        background: SECTION_BG[variant],
        borderRadius: '4px',
        padding: '8px 10px',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
      }}
    >
      <div
        style={{
          fontSize: 'var(--font-size-caption)',
          fontWeight: 'var(--font-weight-medium)',
          color: 'var(--color-text-secondary)',
        }}
      >
        {SECTION_TITLE[variant]} ({items.length})
      </div>
      {items.map((item, idx) => (
        <div
          key={`${item.ticker}-${item.actionType}-${idx}`}
          data-testid={`action-row-${variant}-${item.ticker}`}
          onClick={() => onTickerClick(item.ticker)}
          title={`${item.rationale}\n\n${JSON.stringify(item.refs)}`}
          style={{
            display: 'grid',
            gridTemplateColumns: '60px 160px 1fr',
            gap: '8px',
            alignItems: 'baseline',
            padding: '2px 0',
            cursor: 'pointer',
            fontSize: 'var(--font-size-caption)',
          }}
        >
          <span style={{ fontWeight: 'var(--font-weight-medium)' }}>{item.ticker}</span>
          <span style={{ color: 'var(--color-text-secondary)' }}>{ACTION_LABEL[item.actionType]}</span>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {item.rationale}
          </span>
        </div>
      ))}
    </section>
  )
}
```

**关键点**：
- 行用 CSS Grid 三列：ticker(60px) / actionType label(160px) / rationale(剩余)。rationale 用 `text-overflow: ellipsis` 单行裁剪，hover 用 native `title` 显示完整原文 + refs JSON。
- onClick 直接绑到整行（不仅 ticker 列），与 SetupMonitorWidget 一致。
- `data-testid` 命名 `action-row-{variant}-{ticker}`，测试可定位。
- 空栏 `return null` —— widget 容器不渲染该 section。

#### 1.1.3 `frontend/src/cockpit/widgets/ActionListWidget.tsx`（新建，~110 行）

容器组件：fetch + 4 状态 + 三个 section 组合。

```tsx
import { useQuery } from '@tanstack/react-query'
import { Skeleton } from '@/components/ui/skeleton'
import { useCockpitStore } from '../store/cockpitStore'
import { getTodayActions } from '../lib/api/cockpitActionsApi'
import { ActionListSection } from './_actionListSection'

export function ActionListWidget() {
  const setSelectedTicker = useCockpitStore((s) => s.setSelectedTicker)

  const query = useQuery({
    queryKey: ['cockpit-actions-today'],
    queryFn: getTodayActions,
    staleTime: 30 * 1000,
    retry: false,
  })

  const containerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    padding: '10px',
    gap: '8px',
    overflow: 'auto',
    fontSize: 'var(--font-size-body)',
    color: 'var(--color-text-primary)',
  }

  return (
    <div style={containerStyle}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 'var(--font-weight-medium)' }}>Today&apos;s Actions</span>
        {query.data?.asOfDate && (
          <span
            data-testid="action-as-of-date"
            style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-text-muted)' }}
          >
            {query.data.asOfDate}
          </span>
        )}
      </div>

      {/* Body */}
      {query.isLoading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} style={{ height: '40px', width: '100%' }} />
          ))}
        </div>
      ) : query.isError ? (
        <div
          data-testid="error-banner"
          style={{ color: 'var(--color-destructive)', fontSize: 'var(--font-size-caption)', padding: '8px 0' }}
        >
          加载失败，请稍后重试
        </div>
      ) : query.data && query.data.mustAct.length === 0
            && query.data.monitor.length === 0
            && query.data.noAction.length === 0 ? (
        <div
          data-testid="empty-state"
          style={{
            color: 'var(--color-text-muted)',
            fontSize: 'var(--font-size-caption)',
            padding: '16px 0',
            textAlign: 'center',
          }}
        >
          暂无今日动作
        </div>
      ) : query.data ? (
        <>
          <ActionListSection variant="must" items={query.data.mustAct} onTickerClick={setSelectedTicker} />
          <ActionListSection variant="monitor" items={query.data.monitor} onTickerClick={setSelectedTicker} />
          <ActionListSection variant="noaction" items={query.data.noAction} onTickerClick={setSelectedTicker} />
          {/* AI Daily Brief 挂载点 — F209/F211 v2.0 */}
        </>
      ) : null}
    </div>
  )
}
```

**关键点**：
- 4 状态：loading / error / 全空（粗粒度 `empty-state`）/ 正常。
- Header 右上 `data-testid="action-as-of-date"` 仅在 success 时渲染。
- `setSelectedTicker` 通过 `useCockpitStore` 取（与 `SetupMonitorWidget.tsx:48` 完全一致）。
- AI Brief 挂载点用注释占位，不渲染 DOM。

#### 1.1.4 `frontend/src/cockpit/CockpitRegistry.ts`（修改，+5 行）

```diff
+import { ActionListWidget } from './widgets/ActionListWidget'

 export const COCKPIT_WIDGET_REGISTRY: Record<string, CockpitWidgetManifest> = {
   ...
   'cockpit.pending-orders': { ... },
+  'cockpit.action-list': {
+    id: 'cockpit.action-list',
+    title: "Today's Actions",
+    component: ActionListWidget,
+    defaultLayout: { x: 0, y: 16, w: 12, h: 6, minW: 6, minH: 4 },
+    category: 'action',
+  },
 }
```

`category: 'action'` 已在 `CockpitWidgetCategory` union 中预留，不需要改类型。

#### 1.1.5 `frontend/src/cockpit/lib/api/__tests__/cockpitActionsApi.test.ts`（新建，~80 行）

| # | 用例 | 断言 |
|---|---|---|
| A1 | `getTodayActions()` → GET `/api/cockpit/actions/today`，无 query string | `expect(global.fetch).toHaveBeenCalledWith('/api/cockpit/actions/today', undefined)` |
| A2 | 响应剥壳：返回值就是 `data` 部分（`asOfDate / mustAct / monitor / noAction`） | 断言每个字段都在返回值上，并对应 mock 数据 |
| A3 | 空数组场景：`mustAct=[] / monitor=[] / noAction=[]` 不抛错 | 返回值为 3 个 `[]` + `asOfDate` |
| A4 | 字段全为 camelCase（`asOfDate / mustAct / noAction / actionType`）| 断言这些 key 存在；snake_case 同名 key 不存在 |
| A5 | `actionType` 全 6 枚举值能被原样反序列化 | 单条断言：mock 各种 actionType（raise_stop / cancel_order / reduce_before_earnings / tighten_stop / approaching_trigger / stable_position）→ 返回值 actionType 完全一致 |

#### 1.1.6 `frontend/src/cockpit/widgets/__tests__/ActionListWidget.test.tsx`（新建，~250 行）

**测试矩阵（10 用例）**：

| # | 场景 | 断言 |
|---|---|---|
| W1 | loading 态 | 有 3 个 Skeleton；无 `action-as-of-date` |
| W2 | success 全空（三栏都 0） | 有 `data-testid="empty-state"` 文案 "暂无今日动作"；无任何 `action-section-*` |
| W3 | error 态 | 有 `data-testid="error-banner"` 文案 "加载失败，请稍后重试" |
| W4 | success 含 1 mustAct.raise_stop | 有 `action-section-must`；行内 ticker / "Raise Stop" / rationale 全部出现；无 `action-section-monitor / -noaction` |
| W5 | success 含 1 monitor.approaching_trigger + 1 noAction.stable_position（mustAct 空）| 有 monitor / noaction 两 section，**无** must section |
| W6 | success 三栏齐全各 1 条 | 三 section 都渲染；section 顺序为 must → monitor → noaction（DOM order） |
| W7 | section 标题包含计数 `Must Act (1)` | grep 文本 |
| W8 | 点击行任意位置 → `setSelectedTicker(ticker)` 被调用 | mock store action，断言 `toHaveBeenCalledWith('AAPL')` |
| W9 | hover tooltip：行 `title` 属性同时包含 rationale 文本和 refs JSON 子串 | `expect(row.getAttribute('title')).toContain('R-multiple')`、`expect(row.getAttribute('title')).toContain('"positionId":')` |
| W10 | header 右上 asOfDate 渲染 ISO 字符串 | `expect(screen.getByTestId('action-as-of-date').textContent).toBe('2026-04-24')` |

**Section label 映射独立用例（合并进 W4-W6 中断言）**：actionType 6 枚举 → label 映射全部覆盖（`Raise Stop / Cancel Order / Reduce (Earnings) / Tighten Stop / Approaching Trigger / Stable`）。

**fixture 模式**（mirror `PendingOrdersWidget.test.tsx`）：
```ts
function makeAction(overrides: Partial<ActionItem> = {}): ActionItem { ... }
function makeOkResponse(payload: TodayActionsPayload) { ... }
function makeFetch(payload: TodayActionsPayload | null, statusCode = 200) { ... }
function renderWidget(fetchFn?: typeof fetch) { ... }
```

`useCockpitStore` mock：用 `vi.mock('../../store/cockpitStore', ...)` 返回 `{ setSelectedTicker: vi.fn() }`，并在 W8 中导入 spy 断言。

### 1.2 排除（本 sprint 不做）

| 排除项 | 何时做 | 原因 |
|---|---|---|
| AI Daily Brief 折叠区（`POST /api/ai/contradiction_detector` 调用 + UI） | F209 / F211 v2.0 | design-spec §1119 明确"v2.0 feature-dev 阶段细化" |
| `refs` 字段 typed Pydantic-style 区分（per-actionType union） | 等设计稿对 hover/卡片细节明确后再决定 | F207-a 也按弱类型落地，前后端一致避免 over-eng |
| 行级 typed 子组件（`_actionRow.tsx`） | 当前需求合在 section 内即可（每行 6-7 个元素） | 拆分会增加文件数（已在 6 文件硬上限），收益不足 |
| Cockpit 端联动逻辑变更（如点 ticker 同时切 Decision Panel）| F207-a 行为以 setSelectedTicker 为准；其他 widget 已订阅 | 范围外 |
| Storybook / 视觉回归 | 项目当前无 Storybook | — |
| 多 ticker 一行同时显示多个 actionType 折叠 | 当前后端可能给同一 ticker 同时发多条（如 stop breached 持仓）| 后端已固定每条 1 actionType；UI 也按 1 行 1 actionType 直观渲染，不去重 |
| Widget 拖拽 / resize 行为定制 | RGL 默认即可 | — |

---

## 2. 预计修改文件（共 6 个）

| # | 文件路径 | 改动 | 说明 |
|---|---|---|---|
| 1 | `frontend/src/cockpit/lib/api/cockpitActionsApi.ts` | 新建 | API client + 类型 |
| 2 | `frontend/src/cockpit/widgets/_actionListSection.tsx` | 新建 | 单栏渲染 + actionType label 映射 |
| 3 | `frontend/src/cockpit/widgets/ActionListWidget.tsx` | 新建 | 容器 + 4 状态 + react-query |
| 4 | `frontend/src/cockpit/CockpitRegistry.ts` | 修改 | 注册 `cockpit.action-list` manifest |
| 5 | `frontend/src/cockpit/lib/api/__tests__/cockpitActionsApi.test.ts` | 新建 | 5 client 单元用例 |
| 6 | `frontend/src/cockpit/widgets/__tests__/ActionListWidget.test.tsx` | 新建 | 10 widget 用例 |

✅ 在 6 文件上限内（6/6）。

⚠️ 风险点：若开发中发现 `_actionListSection.tsx` 与 widget 容器逻辑无法解耦或 label 常量需要外部复用，**需要新文件时必须停止报告**，不擅自扩到第 7 个文件。

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---|---|---|
| S1 | `getTodayActions()` GET `/api/cockpit/actions/today`，response 自动剥 `data` | 单元（API client） | vitest + fetch stub |
| S2 | 响应类型严格 camelCase（`asOfDate / mustAct / noAction / actionType`） | 单元 | vitest |
| S3 | 6 个 actionType 枚举均能反序列化无丢字段 | 单元 | vitest |
| S4 | loading 态：3 个 Skeleton，header 不显示 asOfDate | RTL | vitest + RTL |
| S5 | error 态：`data-testid="error-banner"` 出现 + 文案 "加载失败" | RTL | vitest + RTL |
| S6 | 三栏全空 → `empty-state` 显示 "暂无今日动作"，无 section | RTL | vitest |
| S7 | 单栏空（如 mustAct=[]）→ 该 section 不渲染（无 `action-section-must`） | RTL | vitest |
| S8 | 三栏齐全 → DOM 顺序为 must → monitor → noaction，每栏标题含 `(N)` 计数 | RTL | vitest |
| S9 | actionType label 映射 6 枚举全覆盖（Raise Stop / Cancel Order / Reduce (Earnings) / Tighten Stop / Approaching Trigger / Stable） | RTL | vitest |
| S10 | 行点击 → `setSelectedTicker(ticker)` 被调用 | RTL | vitest spy |
| S11 | 行 `title` 属性同时包含 rationale 与 refs JSON | RTL | vitest |
| S12 | header 右上 asOfDate 显示 ISO `YYYY-MM-DD` | RTL | vitest |
| S13 | `cockpit.action-list` manifest 注册到 `COCKPIT_WIDGET_REGISTRY`，`defaultLayout = { x:0, y:16, w:12, h:6, minW:6, minH:4 }`，`category='action'` | 静态 | grep + 类型检查 |
| S14 | 三栏背景使用 token `--color-action-{must,monitor,noaction}-bg`（无硬编码颜色） | 静态 | grep |
| S15 | TypeScript 通过（`pnpm tsc --noEmit`） | 静态 | tsc |
| S16 | `pnpm lint` 通过，本 sprint 新文件 0 warning | 静态 | eslint |
| S17 | 全量回归：`pnpm test` 前端全套通过，无新失败 | 回归 | vitest |

---

## 4. Evaluator 自检清单

开发完成后逐条 ✓：

- [ ] API client 单元测试 5/5 通过
- [ ] Widget 单元测试 10/10 通过
- [ ] `pnpm test` 前端全量回归通过（无新失败）
- [ ] `pnpm tsc --noEmit` 0 错误
- [ ] `pnpm lint` 本 sprint 新文件 0 warning
- [ ] 字段命名严格符合 API-CONTRACT.md（asOfDate / mustAct / monitor / noAction / actionType / refs）
- [ ] 三栏背景色全部使用 CSS 变量（无硬编码 `#xxx` / `rgba()`）
- [ ] selectedTicker 联动验证（mock spy 调用）
- [ ] hover tooltip 同时含 rationale + refs JSON
- [ ] manifest 注册位置正确（`x:0 y:16 w:12 h:6`）
- [ ] AI Daily Brief 仅留注释占位，未渲染 DOM
- [ ] 6 个 actionType label 映射完整且 i18n 占位（直接英文，与现有 widget 一致）
- [ ] 无 `console.error` / `console.log` 遗留
- [ ] 本 sprint 决策（§7）已写入 DECISIONS.md
- [ ] 浏览器 dev server 实际跑过：mock 后端三栏数据，三种空态、点击联动、hover 文案、ResetLayout 后 widget 出现 — 全部观察确认（开发与部署工作流约定 — 用 `pnpm dev` localhost:5173）

---

## 5. 开发顺序

```
1. 写 cockpitActionsApi.ts（types + getTodayActions）
   → 单元 A1-A5 跑通
   → wip(F207-b): actions api client
2. 写 _actionListSection.tsx（label 常量 + 行渲染）
   → wip(F207-b): action-list section component
3. 写 ActionListWidget.tsx（容器 + 4 状态）
   → 接 react-query + useCockpitStore
   → wip(F207-b): action-list widget container
4. 注册到 CockpitRegistry.ts
   → wip(F207-b): register action-list manifest
5. 写 ActionListWidget.test.tsx 10 用例
   → 全跑通
   → wip(F207-b): widget tests
6. 全量回归 pnpm test
7. tsc --noEmit + lint
8. dev server 浏览器实跑（mock 后端 3 种数据态：空 / 单栏 / 三栏齐全）
9. 写 DECISIONS.md（本 sprint 决策追加，§7）
10. Evaluator 自检 → phase=needs_review
11. 最终 commit feat(F207-b)
```

---

## 6. 风险与决策点

| 风险 | 影响 | 缓解 |
|---|---|---|
| 后端 6 actionType 枚举与前端 label 映射对不上 | UI 显示原始 snake_case | label 映射用 `Record<ActionType, string>`（TS exhaustive check）；后端扩枚举时 TS 立刻报错强制更新 |
| `refs` 字段未来扩展破坏 hover JSON 的可读性 | 仅影响调试 tooltip，不影响主流程 | 弱类型 `Record<string, unknown>` + JSON.stringify 容错 |
| widget h:6 高度太矮，三栏齐全时滚动 | 设计偏离 | 容器 `overflow: auto`，与其他 widget 一致；用户可拖拽放大 |
| `category: 'action'` 类型已在 union 但未实际使用 | 无影响 | 直接复用现有 union，不动类型 |
| AI Daily Brief 占位区设计变更 | F209/F211 改造工作量 | 仅留注释，不留 DOM 节点；F209 实施时再加，无回退成本 |
| 用户 localStorage 已有旧 layout 不含 ActionList | 用户感知"widget 没出现" | 与 F206-c2 一致：用户点 Reset Layout 触发；无自动 schema 升级（F206-c2 已验证此行为可接受） |

---

## 7. 决策记录（用户确认后写入 DECISIONS.md）

| Q | 决策点 | 选项 | **建议** | 落点 |
|---|---|---|---|---|
| Q1 | 单栏空时是否渲染空标题 | (a) 整段不渲染（推荐：紧凑）/ (b) 渲染 "Must Act (0)" 灰色标题 | **(a)** | `_actionListSection.tsx` 头部 `if (items.length === 0) return null` |
| Q2 | `refs` 字段前端是否做 typed union | (a) 弱类型 `Record<string, unknown>`（与后端一致）/ (b) per-actionType discriminated union | **(a)** | API client 类型定义；后端扩 actionType 时无前端编译失败风险 |
| Q3 | AI Daily Brief 区域 | (a) 完全不渲染（推荐）/ (b) 渲染折叠空壳"功能即将上线" | **(a)** | 仅留代码注释挂载点；F209/F211 时再加 |
| Q4 | actionType label 中英文 | (a) 全英文（"Raise Stop"）/ (b) 中文 / (c) 双语 | **(a)** | 与现有 widget header（"Pending Orders" / "Setup Monitor"）一致；空态文案保持中文 |
| Q5 | 行点击触发区 | (a) 整行（推荐，与 SetupMonitorWidget 一致）/ (b) 只点 ticker 列 | **(a)** | `_actionListSection.tsx` `onClick` 绑到行 div |
| Q6 | hover tooltip 实现 | (a) native `title` 属性（推荐，与 SetupMonitorWidget 一致）/ (b) 引入 shadcn Tooltip 组件 | **(a)** | 不增加文件数 / 不引入新依赖；`title` 内容含 rationale + refs JSON |
| Q7 | 同 ticker 多条 action（如持仓 stable + 加仓 order approaching）是否前端去重 | (a) 不去重，按后端原样 1 行 1 条 / (b) 同 ticker 折叠 | **(a)** | 与 F207-a §6 风险表"position 和 pending_order 是两个生命周期实体"一致 |
| Q8 | empty-state 文案 | "暂无今日动作" / "今日无操作" / 英文 | **"暂无今日动作"** | 与 PendingOrdersWidget "暂无 pending order" 风格一致（中文空态文案） |

---

👤 用户确认本 Contract（含 §7 Q1-Q8 决策）后，按 skill 流程：
1. 更新 features.json `F207.sub_sprints.F207-b = "contract_agreed"`，`active_sprint_phase = "contract_agreed"`，feature `phase` 保持 `needs_review`（F207-a 已 done，F207-b 是后端完成后的前端续作）
2. 追加 claude-progress.txt（Contract 协商完成）
3. 生成 SESSION-HANDOFF.md，包含 Contract 摘要 + 开发顺序 + 下 session 恢复指令
4. **停止当前 session**，建议用户用 Sonnet 开新 session 以"继续开发 F207-b，Contract 已确认"恢复并进入 Generator 模式
