# Sprint Contract：F203-d — Decision Panel Widget + UserSettings Dialog

> 状态：contract_agreed | 起草：2026-04-25 | 确认：2026-04-25
> 父 Feature：F203 Decision Panel
> 兄弟：F203-a ✅ / F203-b1 ✅ / F203-b2 ✅ / F203-c ✅
> 引用文档：
>   - design-spec.md §Widget 6 DecisionPanelWidget + §UserSettingsDialog
>   - component-plan.md §DecisionPanelWidget + §UserSettingsDialog + §Cockpit-4 queryKey
>   - API-CONTRACT.md §GET /api/cockpit/decision/{ticker}（F203-b2 已上线）
>   - API-CONTRACT.md §GET/PUT /api/cockpit/user-settings（F203-b1 已上线）
>   - DATA-MODEL.md §UserSettings（字段默认值/校验范围）
>   - DECISIONS.md D066（user_settings 单行 + 仓位公式）

---

## 1. 实现范围（包含 / 排除）

**包含**：

### DecisionPanelWidget（主组件）
- 订阅 `useCockpitStore.selectedTicker`
- `selectedTicker = null` → 空态文案"请在 Setup Monitor 或 Chart 选择一只股票"
- `selectedTicker` 变化 → `GET /api/cockpit/decision/{ticker}` via react-query
  - queryKey `['cockpit-decision', ticker, { entryOverride, stopOverride, riskPctOverride }]`
  - staleTime 30s（与 component-plan §Cockpit-4 一致）
- **Decision Card（左半）只读展示 decision 返回字段**：
  - Entry / Stop / Target 2R / Target 3R / Risk/share / Suggested shares / Position $ / Account Risk %
  - Earnings：`EarningsRiskDot` 复用 + "D-{daysUntil}" 或 "SAFE"（F202-c 的 `earningsRisk` 字段已经在 decision 响应内；若没有 earnings 字段则静默隐藏）
  - 末行 `deterministicHash: 7f2a9b...`（前 8 位 + 省略号；灰色 caption）
- **Override Form（右半）**：
  - 3 个 number input：`entryOverride` / `stopOverride` / `riskPctOverride`
  - onChange debounce 500ms → 触发 react-query refetch（通过 queryKey 变化）
  - `Effective Risk%` 只读显示（= `decision.effectiveRiskPct`），下方灰字注记 `= min(regime X, user Y, override Z)`
  - `[↻ Recompute]` 按钮：立刻 `refetch()`，无视 debounce
- **Header**：`Decision · {ticker} · {setupType} · {setupQuality}`
- **四态 UI**：空态（无 ticker）/ loading 骨架 / 正常 / 错误
  - 404 → "无 setup 数据，可手动 override entry/stop"（输入框继续可用，允许 override 触发重算）
  - 422 → 红字 "entry 必须大于 stop"
  - 其他错误 → 普通错误文案

### UserSettingsDialog
- shadcn `Dialog`；mount 时 `GET /api/cockpit/user-settings`（queryKey `['cockpit-user-settings']`，staleTime Infinity）
- `react-hook-form` + `zod`，5 字段：`accountSize` / `maxExposurePct` / `singleTradeRiskPct` / `defaultRiskPerTradePct` / `baseCurrency`（Select：USD / CNY / HKD 等，默认 USD）
- zod 校验：
  - `accountSize > 0`
  - `maxExposurePct ∈ [0, 100]`
  - `singleTradeRiskPct ∈ [0, 5]`
  - `defaultRiskPerTradePct ∈ [0, 5]`
  - 非法字段下方红字提示
- 提交 `PUT /api/cockpit/user-settings` → 成功后 `invalidateQueries(['cockpit-user-settings'])` + `invalidateQueries(['cockpit-decision'])`
- Dialog 底部 `[Cancel]` / `[Save Settings]`
- 文案遵循 design-spec §UserSettingsDialog（"实际 risk% = min(regime 推荐, 上方设置, 单次 override)"）

### API client `userSettingsApi.ts`
- `getUserSettings(): Promise<UserSettings>`
- `updateUserSettings(patch: Partial<UserSettings>): Promise<UserSettings>`
- 类型 camelCase 严格对齐 API-CONTRACT

### TopNav 齿轮按钮
- `/cockpit` 路由下，紧邻 `<CockpitResetLayoutButton />` 追加 `[⚙ Settings]` 按钮
- 按钮 onClick → `setOpen(true)`，挂载 `<UserSettingsDialog open onClose />`
- 其他路由不渲染（复用现有 `showCockpitReset` 判断）

### Registry
- 注册 `cockpit.decision-panel`，category `decision`
- defaultLayout：`x=9 y=0 w=3 h=10 minW=3 minH=8`（右侧与 CockpitChart 并排；用户可拖动）

**排除（明确不做，留后续 feature）**：
- `[Save as PendingOrder]`（依赖 F206 PendingOrdersWidget，本 Sprint 不做；占位 UI 也不放，避免误触）
- AI Trade Plan 区 / [Generate AI Plan] 按钮（v2.0 F210）
- AI Contradictions 区（v2.0 F211）
- 双击图表 priceLine 打开 mini DecisionPanel（v2.0 增强）
- 多币种实际换算（只存 baseCurrency 字段，不做换算显示）
- 在图表上联动绘制 override 后的 entry/stop 横线（F203-c 的 CockpitChartWidget 自己监听 `['cockpit-decision', ticker]`，本 Sprint 不改动 CockpitChartWidget）

---

## 2. 预计修改文件（共 5 个）

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `frontend/src/cockpit/lib/api/userSettingsApi.ts` | 新建 | GET / PUT + 类型 |
| 2 | `frontend/src/cockpit/components/UserSettingsDialog.tsx` | 新建 | Dialog + form + PUT + invalidate |
| 3 | `frontend/src/cockpit/widgets/DecisionPanelWidget.tsx` | 新建 | Decision Card + Override Form + Recompute |
| 4 | `frontend/src/cockpit/CockpitRegistry.ts` | 修改 | 注册 `cockpit.decision-panel` |
| 5 | `frontend/src/components/features/topnav/TopNav.tsx` | 修改 | `/cockpit` 下增加齿轮按钮 + 挂载 Dialog |

> 5 文件，低于 6 文件上限。

⚠ 如 override 输入组件需复用通用 `NumberInput`（项目暂无），本 Sprint 直接使用 shadcn `<Input type="number">`，不单独抽封装（避免超 6 文件）。

---

## 3. 完成标准（可测试）

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| S1 | `userSettingsApi.getUserSettings()` → `GET /api/cockpit/user-settings`；返回字段 camelCase | 单元 | vitest + msw |
| S2 | `userSettingsApi.updateUserSettings({ accountSize: 120000 })` → `PUT` body `{ accountSize: 120000 }`（仅传入字段） | 单元 | vitest + msw |
| S3 | `DecisionPanelWidget`：`selectedTicker=null` → 显示空态文案，不发 decision 请求 | 集成 | RTL + msw |
| S4 | `selectedTicker='NVDA'` → loading 骨架 → 成功后渲染 Entry/Stop/Target 2R/3R/Risk per share/Suggested shares/Position $/Account Risk %/Effective Risk%/deterministicHash（前 8 位） | 集成 | RTL + msw |
| S5 | 输入 `entryOverride=855` → 500ms 内不 refetch；500ms 后触发 refetch，queryKey 包含 `entryOverride: 855` | 集成 | RTL + vi.useFakeTimers |
| S6 | 点击 `[Recompute]` → 立即 refetch，不等 debounce；override 字段继续保留输入 | 集成 | RTL |
| S7 | decision 端点 404 → 显示 "无 setup 数据" 提示 + override 输入框仍可用；输入 override 后触发带 override 的 refetch | 集成 | RTL + msw |
| S8 | decision 端点 422（entry ≤ stop）→ 显示红字 "entry 必须大于 stop" | 集成 | RTL + msw |
| S9 | `UserSettingsDialog` mount → `GET /user-settings` 一次；表单初值与响应字段对齐 | 集成 | RTL + msw |
| S10 | zod 校验：`accountSize=0` / `maxExposurePct=101` / `singleTradeRiskPct=6` 三种非法 → 提交按钮阻止或字段下红字 | 集成 | RTL |
| S11 | 合法提交 → `PUT` body 仅含 dirty 字段；成功后 invalidate `['cockpit-user-settings']` 和 `['cockpit-decision']`（DecisionPanel 自动 refetch） | 集成 | RTL + msw spy on queryClient.invalidateQueries |
| S12 | `TopNav` 在 `/cockpit` 路由下渲染 `[⚙ Settings]` 按钮；其他路由（如 `/` Workbench、`/journal`）不渲染 | 集成 | RTL with MemoryRouter |
| S13 | 点击齿轮 → Dialog 打开；`[Cancel]` → 关闭；`[Save Settings]` 成功 → 关闭 | 集成 | RTL |
| S14 | Registry：`COCKPIT_WIDGET_REGISTRY['cockpit.decision-panel']` 存在，category='decision'，defaultLayout w=3 h=10 minW=3 minH=8 | 单元 | vitest |
| S15 | 颜色/间距全部读 `tokens.css` 变量，无硬编码 hex | 静态 | grep |
| S16 | 全量回归：`pnpm -C frontend test` 全过；`pnpm -C frontend run lint` 无新增 warning；`pnpm -C frontend run build` 通过 | 回归 | vitest + eslint + tsc |

---

## 4. Evaluator 自检清单

### 文件存在性
- [ ] 5 个文件全部存在，路径与 §2 一致
- [ ] 未触碰 F203-c 范围（CockpitChartWidget / cockpitChartApi 未修改）
- [ ] 未触碰 F206 范围（无 PendingOrder 相关代码）

### Schema / 字段命名
- [ ] `userSettingsApi` 类型字段全 camelCase：`accountSize` / `maxExposurePct` / `singleTradeRiskPct` / `defaultRiskPerTradePct` / `baseCurrency` / `updatedAt`
- [ ] `DecisionPanelWidget` 使用 `cockpitDecisionApi`（F203-c 已建）的 camelCase 类型，未重新定义

### 设计合规（design-spec §Widget 6 / §UserSettingsDialog）
- [ ] Header 文案 `Decision · {ticker} · {setupType} · {setupQuality}`
- [ ] 左 Card / 右 Form 两列布局，窄宽时堆叠
- [ ] Effective Risk% 下方 caption 说明"= min(regime X, user Y, override Z)"
- [ ] `[Recompute]` 与 `[Save as PendingOrder]`（后者本 Sprint 不放）不出现在 UI
- [ ] 空 / loading / 正常 / 404 / 422 五个 UI 状态都覆盖
- [ ] Dialog 尺寸 480×520（或相近 shadcn 默认，不强制）
- [ ] Dialog 包含 5 字段 + Cancel + Save Settings，文案与 design-spec 对齐

### D066 合规
- [ ] PUT payload 仅含用户修改过的字段（`react-hook-form` dirtyFields）
- [ ] 不在前端计算 position size（全部取 decision 响应）

### React Query
- [ ] queryKey 与 component-plan §Cockpit-4 一致：`['cockpit-decision', ticker, overrides]` / `['cockpit-user-settings']`
- [ ] user-settings staleTime Infinity
- [ ] PUT 成功后 invalidate 两个 key
- [ ] decision override 通过 queryKey 驱动 refetch（不用手动 `refetch()`，除非 Recompute 按钮）

### 代码质量
- [ ] 单文件 < 350 行；DecisionPanelWidget 可能偏大，若超 350 行拆子组件 DecisionCard / OverrideForm（拆分只拆到同文件的内部子组件，不新建文件）
- [ ] 无 console.log / console.error
- [ ] 无未用 import
- [ ] debounce 不泄漏（useEffect cleanup 或 useDebouncedCallback）

### 测试
- [ ] S1–S16 全过

---

## 5. 开发顺序

1. `userSettingsApi.ts`：类型 + GET + PUT（+ msw mock 基础）
2. `UserSettingsDialog.tsx`：Dialog 骨架 + react-hook-form + zod schema + PUT + invalidate
3. `DecisionPanelWidget.tsx`：
   1. 订阅 `useCockpitStore.selectedTicker`
   2. Decision Card（只读字段渲染 + 四态）
   3. Override Form + debounce 500ms + queryKey 联动
   4. `[Recompute]` 按钮
4. `CockpitRegistry.ts` 注册 `cockpit.decision-panel`
5. `TopNav.tsx` 齿轮按钮 + Dialog open 状态（用 local `useState`，不进 store）
6. 单元 + 集成测试（msw handler 覆盖 GET/PUT user-settings + GET decision 200/404/422）
7. `pnpm -C frontend run lint && pnpm -C frontend test && pnpm -C frontend run build`
8. Evaluator 自检 → 全过后 commit：
   ```
   feat(F203-d): DecisionPanel Widget + UserSettings Dialog（override / recompute / risk 校验）
   ```

---

## 6. 风险与取舍

- **Dialog open 状态放哪**：放 TopNav 组件的 local `useState` 最简（齿轮按钮 + Dialog 同组件内），不引入新 store；代价是 Dialog 组件在非 cockpit 路由不会 mount，也不会预拉 user-settings（可接受，反而省请求）。
- **Override 与 CockpitChartWidget 联动**：两个 widget 共享 queryKey `['cockpit-decision', ticker, overrides]`，但 overrides 放在 DecisionPanel 的 local state，CockpitChartWidget 不会自动获取带 override 的 decision。v1.8 限定"图表横线始终用后端默认 entry/stop（无 override）"，避免耦合。若用户期望图表同步，v1.9 做全局 override store。**本 Sprint 明确不做此联动**，在 design-spec 偏离记录补一条。
- **PUT invalidate decision 的 ticker 选择**：invalidate 整个 `['cockpit-decision']` 前缀，所有 ticker 全刷新（react-query prefix match）。`baseCurrency` 变更也触发刷新（哪怕 decision 不返回 currency），可接受。
- **baseCurrency Select 选项**：design-spec 写 "USD ▼" 暗示 Select；本 Sprint 提供 `['USD']` 单选项（符合当前后端默认），留注释 `// v1.9 扩展 CNY/HKD`。若用户希望完整下拉，转为 S10 测试用例。
- **AccountSize 输入体验**：design-spec 用 `$100,000` 带千分位显示，但 `<input type="number">` 不支持千分位。本 Sprint 用纯 number，不加 mask（避免超出 5 文件）。若用户坚持 mask，转为跟进项。
- **Debounce 实现**：原生 `setTimeout` + useEffect cleanup 即可，不引入 lodash（`use-debounce` 已在 package.json 里？需 Generator 首步确认；没有则自己写）。

---

## 7. 已确认条款（2026-04-25）

1. ✅ `[Save as PendingOrder]` 按钮：**渲染但 disabled + tooltip "F206 上线后启用"**
   - 需要在 Evaluator 自检增补一条：按钮 disabled 且 hover 显示 tooltip
   - 在 design-spec.md §Widget 6 追加偏离记录："v1.8 期间按钮 disabled，F206 上线后启用"
2. ✅ 去掉 AI Plan / Contradictions 区（v2.0 再做，本 Sprint 完全不渲染）
3. ✅ 图表 priceLine 不跟 override 联动（v1.8 限定；v1.9 再评估）
4. ✅ `baseCurrency` Select 只提供 `USD` 单选项（代码注释 `// v1.9 扩展 CNY/HKD`）
5. ✅ `accountSize` 用纯 `<input type="number">`，不做千分位 mask
6. ✅ Dialog 采用 shadcn 默认宽度（不强制 480×520）
7. ✅ DecisionPanel defaultLayout `x=9 y=0 w=3 h=10 minW=3 minH=8`（与 CockpitChart `x=4 w=5` 并排占满 12 列）

### 补充 Evaluator 自检项（对应条款 1）

- [ ] `[Save as PendingOrder]` 按钮渲染且 `disabled`
- [ ] hover/focus 显示 tooltip "F206 上线后启用"（shadcn Tooltip 或原生 `title`）
- [ ] 按钮样式使用 disabled token（`--color-text-disabled` 等）

### 补充测试用例

- **S17**：`[Save as PendingOrder]` 按钮存在且 disabled；点击无副作用（无请求发出）（集成 / RTL）

---

## 9. 下一 Session 恢复指令

```
继续开发 F203-d，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F203-d-contract.md，
进入 Generator 模式，从开发步骤 1 开始。
```
