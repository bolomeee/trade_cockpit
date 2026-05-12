# Sprint Contract：F206-c1 — PositionListWidget（持仓列表 + Risk Summary 顶条）

> 状态：drafted | 起草：2026-04-26
> 父 Feature：F206 Position Manager
> 兄弟：F206-a ✅ / F206-b1 ✅ / F206-b2 ✅ / F206-c1（本）/ F206-c2 ⬜（PendingOrders 前端，c1 之后）
> 引用文档：
>   - design-spec.md §Widget 7 PositionListWidget（行 1029–1058）
>   - component-plan.md §PositionListWidget / §PositionFormDialog（行 439–445、463–466）
>   - data-mapping.md §Cockpit-7（7.a Summary / 7.b 持仓行 / 7.c FormDialog）
>   - API-CONTRACT.md §GET/POST/PATCH/DELETE /api/cockpit/positions（行 1391–1531）
>   - DATA-MODEL.md §Entity: Position
>   - DECISIONS.md D060（cockpit RGL 独立 Registry）/ D063（不复用 workbench）

---

## 1. 实现范围（包含 / 排除）

**包含**：
- 新建 `cockpitPositionsApi.ts`：4 个 endpoint client + camelCase TypeScript 类型（Position / PositionSummary / GetPositionsResponse / PositionInput / PositionPatch）
- 新建 `PositionListWidget.tsx`：
  - **Risk Summary 顶条**（5 字段，按 §Cockpit-7.a 渲染）：openRiskPct / totalExposurePct / pendingRiskPct / positionsCount / pendingCount
  - **状态切换**（local state）：`open` / `closed` / `all`，对应 `?status=` 查询
  - **Open Positions 表**（按 §Cockpit-7.b 字段全量渲染）：Ticker / Entry / Last / Stop / R / P/L / Earn / Next
    - rMultiple / unrealizedPl 正绿负红（`--color-change-positive/negative`）
    - earnings 列：`EarningsRiskDot`（已存在共享组件）+ "D-{n}" 文本，daysUntilEarnings ≤ 0 显示 "—"
    - nextAction 列：4 态彩色 chip（hold→watch 灰、raise_stop→add 蓝、reduce→reduce 橙、exit→sell 红）
  - **行点击展开内联编辑**：stop / status / closedAt / closePrice / notes，保存 `PATCH /api/cockpit/positions/{id}`
  - **行右上 [✕] 删除**：AlertDialog 二次确认 → `DELETE`
  - **`[+ New Position]` 按钮**：弹 PositionFormDialog（mode='new'）
  - 状态：loading 骨架 / 错误 banner / 空（items=[] 时）/ 正常
- 新建 `PositionFormDialog.tsx`：
  - `react-hook-form` + `zod`：ticker 必填且大写、entryPrice > 0、stopPrice > 0、entryPrice > stopPrice、shares > 0、entryDate 必填；target2r/target3r/setupType/notes 可选
  - mode='new' / 'edit'，edit 模式预填 initialPosition
  - 仅 New 模式：从 `useCockpitStore.selectedTicker` 读取 ticker，并从 `['cockpit-decision', selectedTicker]` 读 `suggestedShares`，shares 输入下方灰字 `Cockpit 推荐 {n} shares`（无 selectedTicker 或无 decision 数据时不显示）
  - 提交：mode=new 调 POST，mode=edit 调 PATCH，成功后 onSaved → invalidate `['cockpit-positions']`
- 修改 `CockpitRegistry.ts`：
  - 注册 `cockpit.position-list` manifest（id / title='Positions' / category='position'）
  - defaultLayout 暂取 `{ x: 0, y: 8, w: 6, h: 8, minW: 4, minH: 6 }`（与已有 widget 错位，不与 chart/decision 冲突）
- React Query：
  - `['cockpit-positions', status]` staleTime 30s（与 component-plan §493 对齐）
  - mutation 成功后 invalidate `['cockpit-positions']`（所有 status 变体）
- 测试：
  - `__tests__/cockpitPositionsApi.test.ts`：4 个 client 函数 query/body 拼接 + 响应反序列化
  - `widgets/__tests__/PositionListWidget.test.tsx`：summary 渲染 / items 渲染 / 4 状态 / 行展开 PATCH / 删除 confirm flow / status 切换重 fetch / nextAction 颜色映射
  - `dialogs/__tests__/PositionFormDialog.test.tsx`：zod 校验失败案例（entry≤stop、shares≤0、ticker 缺失）/ POST 成功 invalidate / PATCH 成功 / suggestedShares 提示显示与隐藏

**排除（明确不做）**：
- PendingOrdersWidget / PendingOrderFormDialog / cockpitPendingOrdersApi（留 F206-c2）
- ActionListWidget（F207）
- nextAction 行弹气泡显示 rationale（design-spec §1057 提到，但 API 未返回 rationale 字段；v1.9 简化为彩色 chip，不弹气泡 — 写入设计偏离回写到 design-spec）
- D|W timeframe / MA toggle 等图表相关（与本 widget 无关）
- AI 子区（v2.0 范围）
- ESLint `no-restricted-imports` 规则配置（F200 框架的事，已存在）
- localStorage 布局 schema 升级（沿用 v1）

---

## 2. 预计修改文件（共 4 个生产文件 + 3 个测试文件）

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `frontend/src/cockpit/lib/api/cockpitPositionsApi.ts` | 新建 | 4 endpoint client + 类型 |
| 2 | `frontend/src/cockpit/widgets/PositionListWidget.tsx` | 新建 | Summary + 表格 + 内联编辑 + 删除 |
| 3 | `frontend/src/cockpit/dialogs/PositionFormDialog.tsx` | 新建 | new/edit 表单 + zod 校验 + suggestedShares 提示 |
| 4 | `frontend/src/cockpit/CockpitRegistry.ts` | 修改 | 注册 `cockpit.position-list` |
| T1 | `frontend/src/cockpit/lib/api/__tests__/cockpitPositionsApi.test.ts` | 新建 | api client 单测 |
| T2 | `frontend/src/cockpit/widgets/__tests__/PositionListWidget.test.tsx` | 新建 | widget 集成测试 |
| T3 | `frontend/src/cockpit/dialogs/__tests__/PositionFormDialog.test.tsx` | 新建 | dialog 集成测试 |

> 4 生产文件，远低于 6 文件上限。测试文件按既有 contract（F203-c 等）惯例不计入文件清单。
> `frontend/src/cockpit/dialogs/` 目录尚未存在，本 sprint 创建。

---

## 3. 完成标准（可测试）

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| S1 | `cockpitPositionsApi.getPositions('open')` → `GET /api/cockpit/positions?status=open`；status 'closed'/'all' 同样拼接；响应解构 `{ summary, items }` | 单元 | vitest + fetch mock |
| S2 | `createPosition(input)` → `POST` JSON body 字段命名全 camelCase（与 API-CONTRACT 对齐）；响应返回 Position | 单元 | vitest |
| S3 | `updatePosition(id, patch)` → `PATCH /api/cockpit/positions/{id}`；patch 中省略字段不出现在 body | 单元 | vitest |
| S4 | `deletePosition(id)` → `DELETE /api/cockpit/positions/{id}`；响应 `{ id, deleted }` | 单元 | vitest |
| S5 | PositionListWidget：fetch 成功 → 顶条 5 字段全部渲染（"Open Risk: 2.5%" / "Exposure: 45%" / "Pending: 1.0%" / "5 pos" / "2 ord"） | 集成 | RTL + msw |
| S6 | items 渲染：每行包含 ticker / entryPrice / lastClose / stopPrice / rMultiple / unrealizedPl / earningsRiskDot / nextAction chip | 集成 | RTL |
| S7 | rMultiple 正值 → 正绿（`--color-change-positive`）；负值 → 负红 | 集成 | RTL + computedStyle 或 className |
| S8 | nextAction 4 态 chip 颜色映射：hold→watch、raise_stop→add、reduce→reduce、exit→sell（按 token 名断言 className 或 inline style） | 集成 | RTL |
| S9 | 状态切换 [Open] → [Closed] → [All]：query refetch，URL `?status=` 跟随变更 | 集成 | RTL + msw |
| S10 | items=[] → 空态文案 "暂无持仓"；fetch 错误 → 错误 banner | 集成 | RTL + msw |
| S11 | 行点击展开：内联表单显示 stop / status / closedAt / closePrice / notes；保存 → `PATCH` 调用，成功后 invalidate `['cockpit-positions']` | 集成 | RTL + msw |
| S12 | 行 [✕] → AlertDialog 二次确认 → 确认后 `DELETE` 调用 + invalidate；取消则不调用 | 集成 | RTL |
| S13 | `[+ New Position]` → PositionFormDialog 打开，mode='new' | 集成 | RTL |
| S14 | PositionFormDialog 校验失败：ticker 空 / entryPrice ≤ 0 / stopPrice ≤ 0 / entryPrice ≤ stopPrice / shares ≤ 0 → 各自显示 zod 错误，提交按钮不触发 POST | 集成 | RTL |
| S15 | PositionFormDialog（new）有效提交 → POST 调用 body 字段命名 camelCase；成功 onSaved → invalidate `['cockpit-positions']` | 集成 | RTL + msw |
| S16 | PositionFormDialog（edit）预填 initialPosition；提交 → PATCH 调用 | 集成 | RTL + msw |
| S17 | suggestedShares 提示：selectedTicker='NVDA' 且 decision query 已缓存且含 suggestedShares=33 → 灰字显示 "Cockpit 推荐 33 shares"；selectedTicker=null 不显示 | 集成 | RTL + queryClient prime |
| S18 | Registry：`COCKPIT_WIDGET_REGISTRY['cockpit.position-list']` 存在，category='position'，defaultLayout 与 §1 一致；`getCockpitDefaultLayout()` 返回项含本 id | 单元 | vitest |
| S19 | 颜色：所有颜色读取 tokens.css 变量，无硬编码 hex | 静态 | grep |
| S20 | 全量回归：`pnpm -C frontend test` 全过；`pnpm -C frontend run lint` 无新增 warning；`pnpm -C frontend run build` 通过 | 回归 | vitest + eslint + tsc |

---

## 4. Evaluator 自检清单

### 文件存在性
- [ ] 4 生产文件 + 3 测试文件全部存在，路径与 §2 一致
- [ ] 未触碰 F206-c2 范围（无 PendingOrdersWidget / PendingOrderFormDialog / cockpitPendingOrdersApi）
- [ ] 未触碰其他兄弟（F207 ActionList / 任何 backend 文件）

### 边界合规（component-plan §Cockpit-6）
- [ ] 不 import 任何 `src/workbench/*` 模块
- [ ] 不 import `useAppStore`；只用 `useCockpitStore`
- [ ] 无硬编码 hex 颜色

### Schema / 字段命名
- [ ] api client 类型字段全 camelCase，与 API-CONTRACT 一致
- [ ] Position 类型字段：id/ticker/entryPrice/entryDate/shares/stopPrice/target2r/target3r/setupType/status/lastClose/rMultiple/unrealizedPl/positionValue/earningsDate/daysUntilEarnings/nextAction/closedAt/closePrice/createdAt/updatedAt
- [ ] Summary 字段：openRiskPct/totalExposurePct/pendingRiskPct/positionsCount/pendingCount

### 设计合规（design-spec §Widget 7 + data-mapping §Cockpit-7）
- [ ] Summary 顶条 5 字段渲染顺序与文案一致
- [ ] 4 个空 / 加载 / 错误 / 正常状态都有 UI
- [ ] nextAction 4 态颜色映射使用 token
- [ ] EarningsRiskDot 复用现有共享组件（不重新实现）
- [ ] rMultiple / unrealizedPl 正绿负红

### React Query
- [ ] queryKey 与 component-plan §493 对齐：`['cockpit-positions', status]`
- [ ] staleTime 30s
- [ ] POST/PATCH/DELETE 后 invalidate `['cockpit-positions']`（覆盖所有 status 变体）

### 设计偏离回写
- [ ] 已在 design-spec §Widget 7 的 nextAction 行追加偏离说明：v1.9 简化为彩色 chip，不弹 rationale 气泡（API 未返回 rationale；F207 actions/today 才聚合）
- [ ] DECISIONS.md 追加一条决策记录

### 代码质量
- [ ] 单文件 ≤ 350 行（widget 若超出，拆 sub-component）
- [ ] 无 console.log / console.error 遗留
- [ ] 无未用 import
- [ ] zod schema 与 TypeScript 类型同源（`z.infer`）

### 测试
- [ ] S1–S20 全过
- [ ] 全量回归：frontend 全部测试通过

---

## 5. 开发顺序

1. 创建目录 `frontend/src/cockpit/dialogs/` 和 `frontend/src/cockpit/dialogs/__tests__/`
2. 写 `cockpitPositionsApi.ts` + `__tests__/cockpitPositionsApi.test.ts` → vitest 通过
3. WIP commit：`wip(F206-c1): cockpitPositionsApi`
4. 写 `PositionFormDialog.tsx` + 测试 → vitest 通过
5. WIP commit：`wip(F206-c1): PositionFormDialog`
6. 写 `PositionListWidget.tsx` + 测试 → vitest 通过
7. WIP commit：`wip(F206-c1): PositionListWidget`
8. 修改 `CockpitRegistry.ts` 注册 manifest + 扩展 `__tests__/CockpitRegistry.test.ts` → vitest 通过
9. 设计偏离回写：design-spec §Widget 7 nextAction 段落 + DECISIONS.md 追加决策
10. WIP commit：`wip(F206-c1): registry + 偏离回写`
11. `pnpm -C frontend run lint && pnpm -C frontend test && pnpm -C frontend run build`
12. Evaluator 自检 → 全过
13. 最终 commit：`feat(F206-c1): PositionListWidget + Risk Summary + PositionFormDialog`

---

## 6. 风险与取舍

- **suggestedShares 来源**：read-only 依赖 `['cockpit-decision', selectedTicker]` 缓存。若用户在 PositionFormDialog 打开时 decision query 尚未发起或失败，提示行简单不显示，不主动触发 query（避免 c1 触发额外请求/失败处理复杂度）。
- **状态切换 query key**：用 `['cockpit-positions', status]`，open/closed/all 三个独立缓存。invalidate 时用 prefix 模糊匹配（`queryClient.invalidateQueries({ queryKey: ['cockpit-positions'] })`）。
- **行内联展开**：用 React local state 维护当前展开行 id（单展开模式）。表单字段为 patch 子集，提交后自动收起。
- **删除 AlertDialog**：用 shadcn `AlertDialog`，文案 "确认删除 {ticker} 持仓？此操作不可恢复"。
- **设计偏离（nextAction rationale）**：API 未返回 rationale 字段（仅枚举），design-spec §1057 描述的"点击文字弹气泡说明 rationale"在 v1.9 不实现；F207 完成后 ActionList 提供完整 rationale。需写入 design-spec 偏离段并加 DECISIONS 记录。
- **EarningsRiskDot 阈值**：复用 `cockpit/components/EarningsRiskDot.tsx`，按其现有 props 传 daysUntilEarnings；若组件未暴露 `null` 处理，daysUntilEarnings=null 时不渲染 dot，仅显示 "—"。

---

## 7. 待用户确认条款

1. F206-c1 只做 Position 相关 4 文件；PendingOrders 留 F206-c2
2. nextAction 不做 rationale 气泡（API 字段限制），偏离写入 design-spec + DECISIONS
3. defaultLayout 取 `{ x: 0, y: 8, w: 6, h: 8, minW: 4, minH: 6 }`（c2 后续选另一格位）
4. suggestedShares 提示仅消费已缓存的 decision query，不主动触发请求
5. 删除走 shadcn AlertDialog 二次确认

---

## 8. 下一 Session 恢复指令

```
继续开发 F206-c1，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F206-c1-contract.md，
进入 Generator 模式，从开发步骤 1 开始。
```
