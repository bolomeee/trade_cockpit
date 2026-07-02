---
status: confirmed
feature: F222
sub_sprint: F222-c
date: 2026-07-02
confirmed_at: 2026-07-02
---

# F222-c Sprint Contract — Watchlist 颜色标记：前端接入（`ColorTagButton` + `WatchlistWidget`）

> 生成：2026-07-02 | 状态：草案 → 待确认
> Feature：[F222](../../需求/features.json) Watchlist 颜色标记
> Sub-sprint：F222-c（共 3 个 sub-sprint 的第 3 个，最后一个；frontend）
> 前置：F001 done（Watchlist 管理已上线）；F222-a done（`GET /api/signals` 读路径，`SignalBoardItem.labelColor` 已可用）；F222-b done（`PUT /api/watchlist/{ticker}/color` 写路径已跑通）；system-design 阶段已完成 DATA-MODEL / API-CONTRACT / design-spec 全部更新
> 下游：F222 整体转 `needs_review`，等待 acceptance（a+b+c 全部 done 后）
>
> 引用文档：
> - [API-CONTRACT.md §Watchlist `PUT /api/watchlist/{ticker}/color`](../../系统设计/API-CONTRACT.md) — 请求/响应/错误码
> - [API-CONTRACT.md §Signals `GET /api/signals`](../../系统设计/API-CONTRACT.md) — `labelColor` 字段位置
> - [design-spec.md §F222](../../设计/design-spec.md) — token 表 + `ColorTagButton`/`ColorTagPopover` 视觉规格
> - [component-plan.md §F222](../../设计/component-plan.md) — 两组件 props/职责边界
> - [DECISIONS.md D110](../../系统设计/DECISIONS.md) — 字段/挂载点/token 设计决策
> - [F222-b-contract.md](F222-b-contract.md) — 同 feature 前序 sub-sprint，本合同结构对齐

---

## 0. 背景与定位

F222（Watchlist 颜色标记）因预计修改文件数（14 个，backend 9 + frontend 5）超出 6-file 上限，拆分为 3 个 sub-sprint：F222-a（backend 读路径，done）→ F222-b（backend 写路径，done）→ F222-c（frontend，本合约）。

F222-a/b 已经把读写两条路径在后端跑通（`GET /api/signals` 带 `labelColor`；`PUT /api/watchlist/{ticker}/color` 可写入）。本 sprint 是最后一块拼图：前端渲染色块按钮、Popover 选色交互、调用写接口、缓存刷新、CSV 导出携带颜色列。完成后 F222 三个 sub-sprint 全部 done，触发 acceptance。

---

## 1. 实现范围

### 1.1 `frontend/src/styles/tokens.css` 新增 3 个 token

在现有别名 token 区块（`--color-setup-*` / `--color-earnings-*` 所在分组）新增：

```css
--color-label-red: var(--color-change-negative);
--color-label-yellow: var(--color-log-warn);
--color-label-blue: var(--color-signal-breakout);
```

- 全部别名到既有 token，不新增 hex（D110 已定）。
- `null`（无色）不设 token，前端直接用 `var(--color-border)` 渲染空心圆环。
- `tokens-dark.css` **不改动**（D110/D109 惯例：饱和语义色不设 dark 覆盖）。

### 1.2 `frontend/src/types/signal.ts` 新增 `LabelColor` 类型 + 字段

```ts
import type { SignalType } from './watchlist'

export type { SignalType }

export type LabelColor = 'red' | 'yellow' | 'blue' | null

export interface SignalBoardItem {
  ticker: string
  name: string
  signalType: SignalType
  date: string | null
  closePrice: number | null
  ma150Value: number | null
  distancePct: number | null
  slopePositive: boolean | null
  slopeValue: number | null
  labelColor: LabelColor
}
```

`LabelColor` 定义在 `signal.ts`（不是 `watchlist.ts`）：该字段语义上属于 `GET /api/signals` → `SignalBoardItem`（D110 已确认读路径挂在这里，`WatchlistItem` 不含此字段）。`lib/api/watchlist.ts` 和 `ColorTagButton.tsx` 均从 `@/types/signal` 导入该类型。

### 1.3 `frontend/src/lib/api/watchlist.ts` 新增 `updateColor`

```ts
import type { LabelColor } from '@/types/signal'

export function updateColor(
  ticker: string,
  color: LabelColor,
): Promise<{ ticker: string; labelColor: LabelColor }> {
  return apiFetch(`/watchlist/${encodeURIComponent(ticker)}/color`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ color }),
  })
}
```

与 `removeStock` 同款模式：`apiFetch` 已自动解包 `data`，返回类型直接是业务对象，不包一层 envelope。

### 1.4 `frontend/src/components/features/dashboard/ColorTagButton.tsx`（新建）

单文件内包含 `ColorTagButton`（默认导出）+ 内部私有子组件 `ColorTagPopover`（不单独导出，不单开文件）。理由：`estimated_files_changed` 只为这两个组件预留 1 个文件位；二者强耦合（Popover 只服务于这一个 Button，无独立复用场景），拆文件不产生实际收益。

**Props**（对齐 component-plan.md）：
```ts
interface ColorTagButtonProps {
  ticker: string
  color: LabelColor
  onChange: (color: LabelColor) => void
}
```

**视觉**（对齐 design-spec.md）：
- 触发按钮：圆形，直径 14px，`--radius-full`。`color` 为 `red`/`yellow`/`blue` 时实心填充对应 `--color-label-*`；`null` 时空心圆环，`1.5px solid var(--color-border)`，不填充。
- Popover 内容：4 个同规格色块横排（红/黄/蓝/无色），`--spacing-2` 内边距与色块间距；当前选中色块外描边 `2px solid var(--color-ring)`，offset 2px。

**交互**：
- 点击触发按钮打开 Popover；点击任一色块立即调用 `onChange(color)` 并关闭 Popover——用 `radix-ui` 的 `Popover as PopoverPrimitive`，色块用 `<PopoverPrimitive.Close asChild>` 包裹（Radix 原语自带的关闭机制，靠 context 触发，不需要组件自己加 `useState` 管 `open`）。共享文件 `components/ui/popover.tsx` 未导出 `PopoverClose`，本次**不改**该共享文件，直接在 `ColorTagButton.tsx` 内联从 `radix-ui` 引入 `Popover as PopoverPrimitive`（与 `components/ui/popover.tsx` 自身的引入方式一致）。
- **事件隔离**（新发现的技术点，design-spec 未提及）：`WatchlistWidget` 每行整体有 `onClick={onSelect}`（点击行打开个股详情）。React 的合成事件冒泡走 React 树而非 DOM 树，Radix `PopoverContent` 虽然通过 `Portal` 挂到 DOM 外层，但点击事件仍会沿 React 树冒泡到 `TableRow`。因此：
  - 触发按钮的外层容器需要 `onClick={(e) => e.stopPropagation()}`（阻止"点击色块 = 同时打开详情"）
  - `PopoverContent` 根节点同样需要 `onClick={(e) => e.stopPropagation()}`（阻止"点击 Popover 内色块 = 同时打开详情"）
  - 两处隔离都封装在 `ColorTagButton.tsx` 内部，`WatchlistWidget.tsx` 调用方无需关心，直接内联渲染即可。

**a11y**：触发按钮 `aria-label={\`颜色标记 ${ticker}\`}`；4 个色块分别 `aria-label="标记红色"` / `"标记黄色"` / `"标记蓝色"` / `"清除标记"`（同一时刻只有一个 Popover 打开，色块 label 不需要带 ticker 区分）。

**不包含**：持久化请求本身（父组件传入 `onChange`，由 `WatchlistWidget` 的 mutation 调用 API + 处理成功/失败）。

### 1.5 `frontend/src/workbench/widgets/WatchlistWidget.tsx` 接入

**`WatchlistRow` 内新增 mutation**：
```ts
const colorMutation = useMutation({
  mutationFn: (color: LabelColor) => updateColor(ticker, color),
  onSuccess: invalidate,          // 复用行内已有的 invalidate()（同 deleteMutation 共用）
  onError: (err) => {
    if (err instanceof ApiError && err.code === 'NOT_FOUND') {
      invalidate()                // 镜像 deleteMutation 的 NOT_FOUND 处理：该行数据已过期，静默刷新即可
      return
    }
    toast('颜色标记更新失败，请重试')   // 用户已确认：sonner toast，其余错误场景（422/502/网络失败）统一走这里
  },
})
```

**Ticker 单元格渲染**（`ColorTagButton` 内联在 ticker 文字左侧，同一个 flex 容器）：
```tsx
<TableCell className="font-bold">
  <div className="flex items-center gap-1.5">
    <ColorTagButton
      ticker={ticker}
      color={stock.labelColor}
      onChange={(color) => colorMutation.mutate(color)}
    />
    {ticker}
  </div>
</TableCell>
```
（点击隔离已封装在 `ColorTagButton` 内部，此处无需额外 `stopPropagation`。）

**`exportCsv` 新增颜色列**：
```ts
function exportCsv(stocks: SignalBoardItem[]) {
  const rows = stocks.map(
    (s) => `${s.ticker},"${s.name.replace(/"/g, '""')}",${s.labelColor ?? 'none'}`,
  )
  const csv = ['ticker,name,color', ...rows].join('\n')
  // ... 其余不变
}
```
用户已确认：列追加在 `name` 之后；未标记（`null`）行写字面值 `none`。

**其他**：`import { toast } from 'sonner'`、`import { updateColor } from '@/lib/api/watchlist'`、`import { ColorTagButton } from '@/components/features/dashboard/ColorTagButton'`、`import type { LabelColor } from '@/types/signal'` 新增到文件顶部 import 区。若 `w-14` 的 Ticker 列因新增色块按钮显示拥挤，允许微调该列宽度值——这是新增必需 UI 的直接连带调整，不算超出 Contract 范围。

### 1.6 `frontend/src/workbench/widgets/__tests__/WatchlistWidget.test.tsx`（新建）

当前 `WatchlistWidget` 无任何既有测试覆盖。本文件**只覆盖颜色标记相关行为**，不补齐 delete/import/add 等既有功能的回归测试（不在本 sprint 范围内，YAGNI，避免 scope creep）。参考 `ChartWidget.test.tsx` 的 mock 模式（`vi.mock` API 模块 + `QueryClientProvider` 包裹渲染）。

覆盖场景：

| # | 场景 | 期望 |
|---|------|------|
| TC1 | `labelColor: null` 的行 | 渲染空心圆环触发按钮（非实心） |
| TC2 | `labelColor: 'red'` 的行 | 渲染实心红色触发按钮 |
| TC3 | 点击触发按钮 | 弹出 Popover，可见 4 个色块（红/黄/蓝/无色） |
| TC4 | 点击"标记红色" | 调用 `updateColor(ticker, 'red')`；Popover 关闭 |
| TC5 | 点击触发按钮 / Popover 内任一色块 | 不触发 `onSelectStock`（即不调用 `setSelectedSymbol`，不打开个股详情） |
| TC6 | `updateColor` 成功 | 触发 `signals` query 失效重新拉取（缓存刷新） |
| TC7 | `updateColor` 返回 `ApiError('NOT_FOUND', ...)` | 静默 invalidate，不调用 `toast` |
| TC8 | `updateColor` 返回其他错误（如 `VALIDATION_ERROR` / 网络失败） | 调用 `toast()` |
| TC9 | 点击"导出 CSV" | 生成内容包含表头 `ticker,name,color`；`labelColor: null` 行的颜色列为 `none`，`labelColor: 'red'` 行为 `red` |

### 1.7 明确排除（本 sprint 不做）

- 任何后端文件改动 —— 读写路径已在 F222-a/F222-b 完成，本 sprint 不碰
- `WatchlistWidget` 既有功能（搜索添加、CSV 批量导入、删除）的补充测试 —— 不在本次范围，YAGNI
- 批量设置颜色的前端交互（多选批量打标）—— 需求未提出，不做
- DATA-MODEL.md / API-CONTRACT.md / design-spec.md / component-plan.md 文档改动 —— system-design 阶段已完整覆盖，本 sprint 无需再改
- `tokens-dark.css` —— D110/D109 惯例决定不设 dark 覆盖

---

## 2. 预计修改文件（共 6 个）

| 文件路径 | 改动类型 | 说明 |
|---------|---------|------|
| `frontend/src/styles/tokens.css` | 修改 | 新增 `--color-label-red/yellow/blue` 3 个别名 token |
| `frontend/src/types/signal.ts` | 修改 | 新增 `LabelColor` 类型 + `SignalBoardItem.labelColor` 字段 |
| `frontend/src/lib/api/watchlist.ts` | 修改 | 新增 `updateColor(ticker, color)` |
| `frontend/src/components/features/dashboard/ColorTagButton.tsx` | 新增 | `ColorTagButton` + 内部 `ColorTagPopover` |
| `frontend/src/workbench/widgets/WatchlistWidget.tsx` | 修改 | 接入 `ColorTagButton` + mutation + CSV 导出加颜色列 |
| `frontend/src/workbench/widgets/__tests__/WatchlistWidget.test.tsx` | 新增 | TC1–TC9，覆盖颜色标记相关行为 |

👤 用户确认文件列表合理后，方可进入开发。

> 备注：`features.json` 的 `F222.estimated_files_changed` 已在本次协商中同步补上 `tokens.css`（原列表遗漏此文件，是 D110 已预期但未落到清单的疏漏）。

---

## 3. 文档同步

已在 system-design 阶段（F222 立项时）全部同步，**本 sprint 开发前无需再改任何设计文档**：

- API-CONTRACT.md §Signals：`labelColor` 字段已写入响应示例
- API-CONTRACT.md §Watchlist：`PUT .../color` 完整定义已写入（F222-b 已消费）
- design-spec.md §F222：token 表 + `ColorTagButton`/`ColorTagPopover` 视觉规格已写入
- component-plan.md §F222：两组件 props/职责边界已写入
- DECISIONS.md D110：字段/挂载点/token 设计决策已记录

**本 sprint 新增的技术决策**（协商中已与用户确认，Evaluator 通过后追加 DECISIONS.md 新条目，不在此时先改）：
1. Popover 关闭机制：直接用 `radix-ui` 的 `Popover.Close`，不改共享 `ui/popover.tsx`，不加本地 `open` state
2. 错误提示：非 `NOT_FOUND` 错误统一走 `sonner` `toast()`；`NOT_FOUND` 静默 invalidate（镜像 delete 逻辑）
3. CSV 颜色列：追加在 `name` 之后；`null` 行写字面值 `none`
4. 事件冒泡隔离：触发按钮容器 + `PopoverContent` 根节点均需 `stopPropagation`，防止色块点击穿透到行的 `onSelect`

唯一例外：若 Generator 阶段发现实现细节与已写文档不符，按规则 5 停下改文档再继续，不得静默偏离。

---

## 4. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | Watchlist 每行 ticker 左侧显示色块按钮，`null` 为空心态 | 单元 | Vitest + Testing Library |
| 2 | 点击色块弹出 Popover，4 色块单选，点击任一立即生效并关闭 | 单元 | Vitest + Testing Library |
| 3 | 点击色块（触发按钮或 Popover 内）不触发行的 `onSelectStock` | 单元 | Vitest + Testing Library |
| 4 | 选色后调用 `PUT /api/watchlist/{ticker}/color`，成功后本地缓存刷新 | 单元 | Vitest + Testing Library（mock API） |
| 5 | 选色请求失败：`NOT_FOUND` 静默刷新；其他错误弹 toast | 单元 | Vitest + Testing Library |
| 6 | 导出 CSV 每行携带颜色列，`null` → `none`，位置在 `name` 之后 | 单元 | Vitest + Testing Library |
| 7 | 刷新页面后颜色标记保持不变 | 验证性，无需新代码 | 人工/E2E 抽查——数据来自 `GET /api/signals` 的 `labelColor`，F222-a 已保证持久化，本条只需确认前端正确渲染该字段（TC1/TC2 已覆盖） |
| 8 | CSV 批量导入 / Quick Add 新增 ticker 默认无色 | 验证性，无需新代码 | 人工/E2E 抽查——DB 默认值 `null` + `GET /api/signals` 透传，F222-a 已保证；前端只是如实渲染 |
| 9 | 全量前端测试套件无新增失败 | 回归 | `npm test` (Vitest) |

---

## 5. 已确认的协商点

本 sprint 有 4 处推断性技术决策，均已在协商中与用户确认（详见 §3 "本 sprint 新增的技术决策"）：

1. **`ColorTagPopover` 不单开文件**，作为 `ColorTagButton.tsx` 内部子组件——来源：`estimated_files_changed` 只预留 1 个文件位 + 两组件无独立复用场景，技术选择无产品行为分歧，未单独征询用户。
2. **错误提示方式**——用户选择：sonner toast（design-spec.md 未定义错误态，此为文档空白的补充）。
3. **CSV 空值表示**——用户选择：字面值 `none`（acceptance_criteria 未定义具体格式）。
4. **Popover 关闭机制 + 事件冒泡隔离**——纯实现细节，不影响外部可观察行为，按唯一技术合理方案执行，未单独征询用户。

---

## 6. Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] `cd frontend && npm test -- WatchlistWidget` 全通过（含新增 TC1–TC9）
- [ ] `cd frontend && npm test` 全量回归无新增失败
- [ ] `cd frontend && npm run build`（或项目配置的 typecheck 命令）通过，无 TS 类型错误
- [ ] API 调用格式符合 API-CONTRACT.md §Watchlist `PUT .../color`（请求体 `{color}`，路径含 ticker）
- [ ] 字段命名符合 DATA-MODEL.md / API-CONTRACT.md（`labelColor` camelCase）
- [ ] UI 对照 design-spec.md §F222 逐条检查（色块尺寸、token 用法、Popover 布局、选中态描边）
- [ ] 颜色值全部使用 `--color-label-*` token，无硬编码 hex
- [ ] 无 console.error 遗留
- [ ] 本次技术决策（§3 四项）已追加到 DECISIONS.md
- [ ] **实现范围严格等于本 Contract §1**（无超出、无遗漏；尤其未误动后端文件、未补齐 WatchlistWidget 既有功能的测试）
- [ ] **修改文件严格等于本 Contract §2 清单**（6 个，无新增无遗漏）
- [ ] features.json `F222.sub_sprints['F222-c']`：Generator 开始时 `contract_agreed` → `in_progress`；Evaluator 通过后 → `done`

---

## 7. 完成后的衔接

- F222-c `done` → 触发 consistency-check C1：检查 sibling sub_sprint（F222-a done / F222-b done）—— 三者全部 done，父 feature F222 允许升级为 `needs_review`（不是 `done`，需等 acceptance）
- F222 整体转入 acceptance：对照 5 条 `acceptance_criteria` 做最终验收（含真实前后端联调，非 mock）
- acceptance 通过后 F222 才可标记 `done`

---

👤 **待用户确认。** 确认后将执行：Step 3（frontmatter → confirmed；features.json 的 `sub_sprints`/`_pipeline_status.active_sprint` 更新；追加 claude-progress.txt；更新 SESSION-HANDOFF.md）→ Step 4（git commit）→ Step 5（输出新 session 指令并停止，本 session 不进入 Generator）。
