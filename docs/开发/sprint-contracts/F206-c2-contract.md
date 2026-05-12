# Sprint Contract：F206-c2 — PendingOrdersWidget（条件单计划列表 + 表单弹窗）

> 状态：confirmed | 起草：2026-04-26 | 确认：2026-04-28（用户全意 §7 6 项）
> 父 Feature：F206 Position Manager
> 兄弟：F206-a ✅ / F206-b1 ✅ / F206-b2 ✅ / F206-c1 ✅ / F206-c2（本 = F206 收尾）
> 引用文档：
>   - design-spec.md §Widget 8 PendingOrdersWidget（行 1062–1085）+ §「待 feature-dev 阶段细化的项 #3 PendingOrder Triggered 自动创建 Position」（行 1172）
>   - component-plan.md §PendingOrdersWidget / §PendingOrderFormDialog（行 446–451 / 468–470）+ §Cockpit-4 react-query 缓存策略（行 494）+ §Cockpit-5 目录结构
>   - data-mapping.md §Cockpit-8（行 741–767）
>   - API-CONTRACT.md §GET/POST/PATCH/DELETE /api/cockpit/pending-orders（行 1533–1581）
>   - DATA-MODEL.md §Entity: PendingOrder（行 560–589）
>   - DECISIONS.md D060（cockpit RGL 独立 Registry）/ D063（不复用 workbench）/ D067（pending_orders ticker 不 FK）/ D076（c1 设计偏离）
>   - 后端实现：`backend/app/services/cockpit/pending_order_service.py::_enrich`（distance/risk 计算口径）

---

## 1. 实现范围（包含 / 排除）

**包含**：

- 新建 `cockpitPendingOrdersApi.ts`：4 个 endpoint client + camelCase 类型
  - `PendingOrderStatus = 'ACTIVE' | 'TRIGGERED' | 'CANCELLED' | 'EXPIRED'`
  - `PendingOrderQueryStatus = 'active' | 'all' | 'triggered' | 'cancelled' | 'expired'`（API 大小写不敏感，前端常量统一小写）
  - `PendingOrder` 类型字段：id / ticker / setupType / entryPrice / stopPrice / shares / target2r / target3r / expirationDate / status / lastClose / distanceToTriggerPct / riskPct / notes / createdAt / updatedAt
  - `PendingOrderInput`（POST）/ `PendingOrderPatch`（PATCH，含 status 转换 + 其他可写字段）
  - 函数：`getPendingOrders(status)` / `createPendingOrder(input)` / `updatePendingOrder(id, patch)` / `deletePendingOrder(id)`
- 新建 `PendingOrdersWidget.tsx`：
  - 顶部按钮组：`[+ New Order]` + 状态切换 `[Active|All]`（local state，对应 `?status=`）
  - 表头：Ticker / Setup / Entry / Stop / Last / Dist / Risk% / Exp（按 design-spec §Widget 8 顺序）
  - 行渲染（拆到 `_pendingOrderRow.tsx`）：
    - `setupType` 用现有 `SetupTypeBadge` 共享组件
    - `distanceToTriggerPct`：`+/-` 前缀、2 位小数、`%` 后缀；按 **绝对值** 阈值上色 — `|x| > 5%` 灰（`--color-text-muted`）/ `1% ≤ |x| ≤ 5%` 默认 / `|x| < 1%` 加粗（`font-bold`）
    - `expirationDate` null → "—"
    - 行右侧按钮：`[Triggered]`（仅 ACTIVE 可见）/ `[Cancel]`（仅 ACTIVE 可见）/ `[Edit]`（任意状态可见，弹 PendingOrderFormDialog mode='edit'）/ `[✕]`（任意状态可见，AlertDialog 二次确认 → DELETE）
  - 4 状态：loading 骨架 / 错误 banner / 空 `data=[]` 时空态文案 "暂无 pending order" / 正常
- 新建 `_pendingOrderRow.tsx`：表行组件 + 颜色工具函数（`distanceClass`），与 widget 解耦便于测试
- 新建 `PendingOrderFormDialog.tsx`：
  - Props：`open` / `mode: 'new' | 'edit'` / `initialOrder?: PendingOrder` / `onClose()` / `onSaved()`
  - `react-hook-form` + `zod`：
    - ticker 必填、自动 toUpperCase
    - setupType 必填（dropdown 用与 c1 一致的 setup 枚举来源；若已有共享常量则复用，否则在本 schemas 文件内定义并标注，后续可抽出）
    - entryPrice > 0、stopPrice > 0、entryPrice > stopPrice
    - shares > 0
    - target2r / target3r 可选；若提供需 > entryPrice
    - expirationDate 可选；若提供必须 ≥ today（YYYY-MM-DD）
    - notes 可选
  - mode='new'：调 POST；mode='edit'：调 PATCH（仅提交脏字段）
  - 成功后 `onSaved()` → invalidate `['cockpit-pending-orders']`（覆盖所有 status 变体）
- 新建 `_pendingOrderFormSchemas.ts`：zod schemas + `z.infer` 同源类型 + `setupTypeOptions` 常量
- 修改 `CockpitRegistry.ts`：
  - 注册 `cockpit.pending-orders` manifest（id / title='Pending Orders' / category='position' / defaultLayout）
  - defaultLayout 取 `{ x: 6, y: 8, w: 6, h: 8, minW: 4, minH: 6 }`（与 c1 PositionList 同行右侧错位，不与 chart/decision 冲突）
- 行操作 mutation：
  - `[Triggered]`：弹 shadcn `AlertDialog` confirm 文案 "已在券商手动下单？将把订单标记为 TRIGGERED（不会自动创建 Position）" → `PATCH { status: 'TRIGGERED' }`，成功后 invalidate `['cockpit-pending-orders']` + 弹 toast "已标记为 TRIGGERED，可在 Positions widget 手工录入实际持仓"
  - `[Cancel]`：直接 `PATCH { status: 'CANCELLED' }`，无二次确认（reversible — 用户可重新创建）
  - `[Edit]`：弹 PendingOrderFormDialog mode='edit'，预填 initialOrder
  - `[✕]`：AlertDialog "确认删除 {ticker} 条件单？此操作不可恢复" → `DELETE`
- React Query：
  - `['cockpit-pending-orders', status]` staleTime 30s（与 component-plan §494 对齐）
  - mutation invalidate 用 prefix：`queryClient.invalidateQueries({ queryKey: ['cockpit-pending-orders'] })`
  - **不** invalidate `['cockpit-positions']`（D060-a 决策：v1.9 不联动自动创建 Position）
- 测试：
  - `__tests__/cockpitPendingOrdersApi.test.ts`：4 个 client 函数 query/body 拼接 + 字段反序列化
  - `widgets/__tests__/PendingOrdersWidget.test.tsx`：行渲染（含 SetupTypeBadge）/ distance 颜色 3 档 / Active↔All 切换 refetch / 4 状态 / Triggered confirm flow + toast / Cancel 直接 PATCH / Edit 弹 dialog / Delete confirm flow / 仅 ACTIVE 行显示 [Triggered][Cancel] 按钮
  - `dialogs/__tests__/PendingOrderFormDialog.test.tsx`：zod 校验失败案例 / new POST 成功 invalidate / edit PATCH 仅传脏字段 / expirationDate 历史日期校验失败 / setupType 缺失校验失败

**排除（明确不做）**：

- **PendingOrder Triggered 自动创建 Position**（design-spec §1172、component-plan §450 留待决策）：v1.9 不做。仅切 status，提示用户去 Positions widget 手工录入。决策落 D060-a + DECISIONS.md
- ActionListWidget（F207）
- DecisionPanel 触发的 `SaveAsPendingOrderConfirm`（F203 范围）
- PendingOrder 与 SetupSnapshot 联动校验（API 没建立 FK，前端不强制）
- D|W timeframe / 图表叠加
- AI 子区（v2.0 范围）
- localStorage 布局 schema 升级（沿用 v1，新增 widget 自动出现在新会话默认布局；老用户未持久化的 layout 中没有该 widget — 用户可点 Reset Layout 触发，c1 已验证）

---

## 2. 预计修改文件（共 6 个生产文件 + 3 个测试文件）

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `frontend/src/cockpit/lib/api/cockpitPendingOrdersApi.ts` | 新建 | 4 endpoint client + 类型 |
| 2 | `frontend/src/cockpit/widgets/PendingOrdersWidget.tsx` | 新建 | 顶部按钮 + 状态切换 + 表 + dialog 触发 |
| 3 | `frontend/src/cockpit/widgets/_pendingOrderRow.tsx` | 新建 | 行渲染 + 距离颜色映射工具 |
| 4 | `frontend/src/cockpit/dialogs/PendingOrderFormDialog.tsx` | 新建 | new/edit 表单 + zod 校验 |
| 5 | `frontend/src/cockpit/dialogs/_pendingOrderFormSchemas.ts` | 新建 | zod schemas + setup 选项常量 |
| 6 | `frontend/src/cockpit/CockpitRegistry.ts` | 修改 | 注册 `cockpit.pending-orders` |
| T1 | `frontend/src/cockpit/lib/api/__tests__/cockpitPendingOrdersApi.test.ts` | 新建 | api client 单测 |
| T2 | `frontend/src/cockpit/widgets/__tests__/PendingOrdersWidget.test.tsx` | 新建 | widget 集成测试 |
| T3 | `frontend/src/cockpit/dialogs/__tests__/PendingOrderFormDialog.test.tsx` | 新建 | dialog 集成测试 |

> 6 生产文件，**正好压在 6 文件上限**（与 c1 的 4 文件不同，c2 多出 row 拆分 + schemas 拆分以保持单文件 ≤ 350 行）。
> 测试文件按既有 contract 惯例不计入文件清单。
> 不在本 sprint 修改 `CockpitRegistry.test.ts`（c1 已建立测试模式，新增一行 manifest 用现有断言模式即可，规模可忽略；如确需扩展属边界修改，但不计入 6 文件清单 — 与 c1 contract 一致处理）。

---

## 3. 完成标准（可测试）

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| S1 | `getPendingOrders('active')` → `GET /api/cockpit/pending-orders?status=active`；`'all'` 同理；响应解构 `{ data, message }` 取 `data` 数组 | 单元 | vitest + fetch mock |
| S2 | `createPendingOrder(input)` → POST JSON body 全 camelCase（ticker / setupType / entryPrice / stopPrice / shares / target2r? / target3r? / expirationDate? / notes?）；响应反序列化为 `PendingOrder` | 单元 | vitest |
| S3 | `updatePendingOrder(id, patch)` → `PATCH /api/cockpit/pending-orders/{id}`；省略字段不出现在 body | 单元 | vitest |
| S4 | `deletePendingOrder(id)` → `DELETE /api/cockpit/pending-orders/{id}`；响应 `{ id, deleted }` | 单元 | vitest |
| S5 | PendingOrdersWidget：fetch 成功 → 表头 Ticker/Setup/Entry/Stop/Last/Dist/Risk%/Exp 全部渲染；行字段顺序匹配 | 集成 | RTL + msw |
| S6 | distance 颜色 3 档：`distanceToTriggerPct=8` → 灰；`=3` → 默认；`=0.5` → 加粗（`font-bold` className）；负值同样按绝对值处理（`-7` → 灰、`-0.4` → 加粗） | 单元 | RTL（行组件直测） |
| S7 | 状态切换 `[Active]` → `[All]`：query refetch，URL `?status=` 跟随变更；query key 切换为 `['cockpit-pending-orders', 'all']` | 集成 | RTL + msw |
| S8 | 行按钮可见性：仅 `status='ACTIVE'` 行渲染 `[Triggered]` 和 `[Cancel]`；`TRIGGERED/CANCELLED/EXPIRED` 行不渲染这两个按钮；`[Edit]` 和 `[✕]` 任意状态都渲染 | 集成 | RTL |
| S9 | `[Triggered]` 流程：点击弹 AlertDialog → 确认后 `PATCH { status: 'TRIGGERED' }` 调用 → 成功后 invalidate `['cockpit-pending-orders']` + toast 出现含 "TRIGGERED" 与 "Positions" 关键字；**未** invalidate `['cockpit-positions']` | 集成 | RTL + msw + queryClient spy |
| S10 | `[Cancel]` 流程：点击直接 `PATCH { status: 'CANCELLED' }`，无 dialog；成功后 invalidate `['cockpit-pending-orders']` | 集成 | RTL + msw |
| S11 | `[Edit]` 流程：点击弹 PendingOrderFormDialog mode='edit'，预填字段值（ticker、entryPrice 等） | 集成 | RTL |
| S12 | `[✕]` 流程：弹 AlertDialog（"确认删除 {ticker}…"）→ 确认后 `DELETE` 调用 + invalidate；取消则不调用 | 集成 | RTL |
| S13 | items=[] → 空态文案 "暂无 pending order"；fetch 错误 → 错误 banner | 集成 | RTL + msw |
| S14 | `[+ New Order]` → PendingOrderFormDialog 打开 mode='new'，所有字段空 | 集成 | RTL |
| S15 | PendingOrderFormDialog 校验失败：ticker 空 / setupType 未选 / entryPrice ≤ 0 / stopPrice ≤ 0 / entryPrice ≤ stopPrice / shares ≤ 0 / target2r ≤ entryPrice / expirationDate < today → 各自 zod 错误，提交按钮不触发请求 | 集成 | RTL |
| S16 | PendingOrderFormDialog（new）有效提交 → POST 调用 body camelCase；成功 onSaved → invalidate `['cockpit-pending-orders']` | 集成 | RTL + msw |
| S17 | PendingOrderFormDialog（edit）预填 initialOrder；只修改 stopPrice 后提交 → PATCH body 仅含 `{ stopPrice }`，不传未改字段（dirty fields 模式） | 集成 | RTL + msw |
| S18 | Registry：`COCKPIT_WIDGET_REGISTRY['cockpit.pending-orders']` 存在，category='position'，title='Pending Orders'，defaultLayout 与 §1 一致；`getCockpitDefaultLayout()` 返回项含本 id | 单元 | vitest |
| S19 | 颜色：所有颜色读取 tokens.css 变量或 token-bound Tailwind class，无硬编码 hex（grep `#[0-9a-fA-F]{3,6}` 在 c2 文件中 0 命中） | 静态 | grep |
| S20 | 全量回归：`pnpm -C frontend test` 全过；`pnpm -C frontend run lint` 无新增 warning；`pnpm -C frontend run build` 通过 | 回归 | vitest + eslint + tsc |

---

## 4. Evaluator 自检清单

### 文件存在性
- [ ] 6 生产文件 + 3 测试文件全部存在，路径与 §2 一致
- [ ] 未触碰 F207 ActionList / F203 SaveAsPendingOrderConfirm
- [ ] 未触碰 backend 任何文件

### 边界合规（component-plan §Cockpit-6）
- [ ] 不 import 任何 `src/workbench/*` 模块
- [ ] 不 import `useAppStore`；只用 `useCockpitStore`（c2 实际可能不需要 store；不用就行）
- [ ] 无硬编码 hex 颜色

### Schema / 字段命名
- [ ] api client 类型字段全 camelCase，与 API-CONTRACT.md §Pending Orders 完全一致
- [ ] PendingOrder 字段：id / ticker / setupType / entryPrice / stopPrice / shares / target2r / target3r / expirationDate / status / lastClose / distanceToTriggerPct / riskPct / notes / createdAt / updatedAt
- [ ] status 枚举大写四态：ACTIVE / TRIGGERED / CANCELLED / EXPIRED

### 设计合规（design-spec §Widget 8 + data-mapping §Cockpit-8）
- [ ] 表头顺序 Ticker/Setup/Entry/Stop/Last/Dist/Risk%/Exp
- [ ] expirationDate null → "—"
- [ ] dist 颜色 3 档按绝对值阈值
- [ ] 4 个空 / 加载 / 错误 / 正常状态都有 UI
- [ ] SetupTypeBadge 复用现有共享组件（不重新实现）

### React Query
- [ ] queryKey 与 component-plan §494 对齐：`['cockpit-pending-orders', status]`
- [ ] staleTime 30s
- [ ] POST/PATCH/DELETE 后 invalidate `['cockpit-pending-orders']`（覆盖所有 status 变体）
- [ ] **未** invalidate `['cockpit-positions']`（D060-a 决策：v1.9 不联动）

### 决策回写
- [ ] DECISIONS.md 追加 D060-a：v1.9 PendingOrder Triggered 后**不**自动创建 Position，仅切 status + toast 提示用户手工录入
- [ ] design-spec.md §Widget 8 「待 feature-dev 阶段细化的项 #3」 标注已决策（链接 D060-a）

### 代码质量
- [ ] 单文件 ≤ 350 行
- [ ] 无 console.log / console.error 遗留
- [ ] 无未用 import
- [ ] zod schema 与 TypeScript 类型同源（`z.infer`）

### 测试
- [ ] S1–S20 全过
- [ ] 全量回归：frontend 全部测试通过

---

## 5. 开发顺序

1. 写 `cockpitPendingOrdersApi.ts` + `__tests__/cockpitPendingOrdersApi.test.ts` → vitest 通过
2. WIP commit：`wip(F206-c2): cockpitPendingOrdersApi`
3. 写 `_pendingOrderFormSchemas.ts` + `PendingOrderFormDialog.tsx` + 测试 → vitest 通过
4. WIP commit：`wip(F206-c2): PendingOrderFormDialog`
5. 写 `_pendingOrderRow.tsx` → 单测（distance 颜色 3 档 + 按钮可见性）通过
6. WIP commit：`wip(F206-c2): _pendingOrderRow`
7. 写 `PendingOrdersWidget.tsx` + 测试 → vitest 通过
8. WIP commit：`wip(F206-c2): PendingOrdersWidget`
9. 修改 `CockpitRegistry.ts` 注册 manifest（如需扩展 `CockpitRegistry.test.ts` 增加断言，附带在同一步）
10. 决策回写：DECISIONS.md 追加 D060-a + design-spec.md §Widget 8 链接
11. WIP commit：`wip(F206-c2): registry + 决策回写`
12. `pnpm -C frontend run lint && pnpm -C frontend test && pnpm -C frontend run build`
13. Evaluator 自检 → 全过
14. 最终 commit：`feat(F206-c2): PendingOrdersWidget + PendingOrderFormDialog`（封 F206 收尾）

---

## 6. 风险与取舍

- **Triggered 不联动 Position（D060-a）**：v1.9 选择"手动二次录入"，避免引入 backend 联动事务（PATCH `pending-orders/{id}` 现仅改 status；自动创建 Position 需要后端在 service 层 begin 事务、复制字段、回填 entryDate、处理失败回滚）。c2 仅前端 toast 引导，简洁可靠。如果后续用户反馈手工双录痛点，再开 F206-d 或归入 F207 ActionList 的"raise stop / cancel order / open position"统一动作流。
- **distance 颜色按绝对值还是符号**：design-spec 写"> 5% / 1-5% / < 1%"未指明符号。后端口径 `distance = (entry - lastClose) / lastClose × 100` —— 正数表示"还要涨 x% 才触发 buy stop"，负数表示"已穿越"。无论方向，"接近触发"语义都是绝对值小。**采用绝对值阈值**。
- **Edit 模式范围**：API 允许 PATCH ticker / setupType / entryPrice / stopPrice / shares / target2r / target3r / expirationDate / notes / status。Edit dialog 表单覆盖前 9 个；status 不在表单内（status 切换走 [Triggered]/[Cancel] 行按钮，避免双入口）。
- **dirty fields PATCH**：用 `react-hook-form` 的 `formState.dirtyFields`，仅传修改字段，避免误覆盖（与 design-spec data-mapping 一致 — 服务端按 PATCH 语义只处理传入字段）。
- **TRIGGERED → ACTIVE 反向 PATCH 422**：API-CONTRACT 明示后端拒绝。Edit dialog 不暴露 status 字段，所以本 c2 不会触发；后端如果返回 422，前端走通用错误 banner。
- **无 EXPIRED 行删除按钮警告**：APScheduler 自动转 EXPIRED 后的行，删除是用户清理动作，照常允许 DELETE。
- **defaultLayout 冲突**：c1 占 `(0, 8) 6×8`，c2 取 `(6, 8) 6×8`。CockpitChart `(4, 0) 5×10`、Decision `(9, 0) 3×10` 都在第一行，不冲突。MarketRegime 和 SetupMonitor 也在第一行。
- **setupType 选项来源**：检查代码库是否已有共享 setup 枚举（如 SetupTypeBadge 内部），若有则复用；否则在 `_pendingOrderFormSchemas.ts` 内定义局部常量 + TODO 注释（"v1.9 后续可抽出至共享 const"）。Generator 阶段实查代码确认。

---

## 7. 待用户确认条款

1. **D060-a 决策**：v1.9 PendingOrder `[Triggered]` 后**不**自动创建 Position，仅切 status + toast 提示。OK 吗？
2. distance 颜色按 **绝对值** 阈值上色（`|x|>5` 灰 / `1≤|x|≤5` 默认 / `|x|<1` 加粗）。OK 吗？
3. Edit dialog 不暴露 status 字段；status 转换只走行按钮 `[Triggered]/[Cancel]`。OK 吗？
4. `[Cancel]` 直接 PATCH 无确认（design-spec 明确）；`[Triggered]` 弹确认 dialog 含 toast 引导。OK 吗？
5. defaultLayout 取 `{ x: 6, y: 8, w: 6, h: 8, minW: 4, minH: 6 }`（与 c1 PositionList 同行右侧）。OK 吗？
6. category 复用 `'position'`（不新增 `'order'`，避免改 `CockpitWidgetCategory` union 触发额外 lint）。OK 吗？

---

## 8. 下一 Session 恢复指令

```
继续开发 F206-c2，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F206-c2-contract.md，
进入 Generator 模式，从开发步骤 1 开始。
```
