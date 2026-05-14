# Sprint Contract：F106-c 多信号 Widget（前端）

> 日期：2026-04-21 | 状态：**反向补契约**
> 依赖：F106-a ✅ / F106-b ✅（前端类型定义、API 过滤、响应字段已由后端落地）
> 引用文档：
>   API-CONTRACT.md#GET-/api/market/breakouts（`?type=` + 新字段）
>   components/ui/tabs.tsx（shadcn 官方 Tabs，新引入组件）
>   features.json#F106#acceptance_criteria[7]（"widget 改用 shadcn Tabs"）

---

## 本次实现范围（Sprint C：前端 Widget 改造）

### 1. `frontend/src/components/ui/tabs.tsx`（新建）
- shadcn/ui 官方 Tabs 组件（Radix 封装），参照 `/shadcn-ui/ui` 官方文档
- 导出 `Tabs / TabsList / TabsTrigger / TabsContent`
- 样式 token 对齐既有 shadcn 组件（与 `button.tsx / table.tsx` 风格一致）
- 不引入 shadcn-cli 产物外的额外依赖

### 2. `frontend/src/types/market.ts`（修改）
- 新类型 `SignalType = 'legacy_crossover' | 'a1_stage_breakout' | 'a2_slope_flip' | 'b2_ma_pullback'`
- `BreakoutItem` 追加：
  - `signalType: SignalType`
  - `slopeValue: number`
  - `volume: number | null`
  - `volumeRatio20: number | null`

### 3. `frontend/src/lib/api/market.ts`（修改）
- `getBreakouts(types?: readonly SignalType[]): Promise<BreakoutSnapshot>`
- `types` 非空 → 拼 `?type=xx,yy`；为空/未传 → 不带 query string，走后端默认

### 4. `frontend/src/workbench/widgets/MarketBreakoutWidget.tsx`（修改）
- Widget 根节点改为 `<Tabs>`，两个 Tab：
  - `stage`（"Breakout"）→ 请求 `a1_stage_breakout,a2_slope_flip`
  - `pullback`（"Pullback"）→ 请求 `b2_ma_pullback`
- legacy 不暴露 UI（仅 API `?type=legacy_crossover` 可访问）
- 抽 `BreakoutPane` 子组件承接 useQuery，`queryKey: ['breakouts', typesKey]`，typesKey 为排序拼接串，保证缓存隔离
- 表头按 Tab 动态：
  - stage 页：`Ticker / Company / Signal / Close / % Above MA150 / Vol×20d / +`
  - pullback 页：`Ticker / Company / Close / % Above MA150 / Vol×20d / +`（只有一种 signal，Signal 列隐藏）
- 行 key 改为 `${ticker}-${signalType}`（同 ticker 可在 A1+A2 同时出现）
- `SIGNAL_LABEL` 映射枚举到 UI 展示名（`A1 Breakout / A2 Slope Flip / B2 Pullback`）
- `volumeRatio20` 空值显示 `—`，非空显示 `2.34×`
- 加入 watchlist 按钮尺寸从 `h-6 w-6` 收紧为 `h-5 w-5`
- 空态文案按 Tab 差异：stage 页 `No stage breakouts today`、pullback 页 `No pullback bounces today`
- Widget 容器复用 v1.1.0 widget 内部间距规范（`marginTop: -5 / marginLeft: -5 / gap-1`）

---

## 明确排除

- 后端核心 / API（已在 F106-a / F106-b）
- widget title 底色 / TopNav 布局（归 F109，另立 sprint）
- 新 widget 类别登记（v1.2.0 已有 `scanner` 类别，无需改 WidgetRegistry）

---

## 预计修改文件（共 4 个）

| # | 文件 | 类型 | 改动 |
|---|---|---|---|
| 1 | `frontend/src/components/ui/tabs.tsx` | 新建 | shadcn Tabs 组件 |
| 2 | `frontend/src/types/market.ts` | 修改 | `SignalType` + `BreakoutItem` 4 字段 |
| 3 | `frontend/src/lib/api/market.ts` | 修改 | `getBreakouts(types?)` 可选过滤 |
| 4 | `frontend/src/workbench/widgets/MarketBreakoutWidget.tsx` | 修改 | Tabs 改造 + 动态表头 + signal 标签 |

---

## 可测试的完成标准

> ⚠️ 2026-04-22 降级（反向补契约 Evaluator 阶段）：
> 项目前端当前无 vitest / @testing-library/react 基建，#3–#8 的 6 条 RTL 单元测试项目暂不具备执行能力。
> 经用户确认（F106-c Evaluator：选项 B），移除单元测试门禁，改为 typecheck+build+docker 手工 E2E 三条硬门禁。
> 前端单测基建延迟到 v1.4 统一规划（见 DECISIONS.md#D048），届时 F106-c/F107/F108/F109 一并补测。

| # | 标准 | 层级 |
|---|---|---|
| 1 | 首次挂载默认 Tab 为 Breakout；请求 URL `?type=a1_stage_breakout,a2_slope_flip` | 手工 + devtools |
| 2 | 切到 Pullback Tab → 请求 URL `?type=b2_ma_pullback`；表头无 Signal 列 | 手工 + devtools |
| 3 | 同 ticker 在 A1 + A2 同时命中 → 两行独立显示，key 不冲突（无 React key warning）| ~~单元~~ → 手工回归 |
| 4 | `volumeRatio20 = null` 显示 `—`；非 null 显示 `N.NN×` | ~~单元~~ → 代码审查 |
| 5 | 空态按 Tab 差异：stage 空态 `No stage breakouts today`；pullback 空态 `No pullback bounces today` | ~~单元~~ → 代码审查 |
| 6 | `scanDate === null` → 两 Tab 都显示 `Waiting for today's scan` | ~~单元~~ → 代码审查 |
| 7 | `+` 按钮点击不冒泡触发行 `setSelectedSymbol` | ~~单元~~ → 代码审查（stopPropagation 存在） |
| 8 | Query cache key 按 Tab 隔离：切换不复用对方数据 | ~~单元~~ → 代码审查（`typesKey` 作 queryKey 一部分） |
| 9 | `pnpm --filter frontend typecheck` 通过 | 静态（硬门禁）|
| 10 | `pnpm --filter frontend build` 通过 | 静态（硬门禁）|
| 11 | E2E：docker 部署环境下两 Tab 均正常显示（假定后端已有数据）| E2E（硬门禁）|

---

## Evaluator 自检清单

- [x] `pnpm --filter frontend typecheck` 通过（tsc -b）
- [x] `pnpm --filter frontend build` 通过（vite build 483ms）
- [x] shadcn Tabs 严格按 Context7 `/shadcn-ui/ui` 最新 registry：`radix-ui` barrel 包 + `data-slot` + `group/tabs` + cva `default/line` variants
- [x] docker compose 环境两 Tab 请求 URL 正确（2026-04-22 日志验证：`?type=a1_stage_breakout,a2_slope_flip` 与 `?type=b2_ma_pullback` 均 200）
- [x] 无 `console.error` 遗留（代码审查确认）
- [x] Widget 内部 padding 与其他 widget 一致（marginTop -5 / marginLeft -5 / gap-1，与 F109 规范对齐）
- [ ] features.json `F106.phase` 流转到 `needs_review`（F106-c 验收通过后由主 feature 汇总）

### 代码质量检查
- [x] 无内联 signal_type 字面量字符串（通过 `SignalType` 类型 + `TAB_SIGNALS` 常量）
- [x] `BreakoutPane` 子组件承接 useQuery，`MarketBreakoutWidget` 只剩 Tabs 外壳
- [x] `typesKey = [...signalTypes].sort().join(',')` 排序后拼接

### Lint 修复记录
- tabs.tsx 原 `export { ..., tabsListVariants }` 被删（react-refresh/only-export-components），内部使用不变

### 回归测试
- 运行前端全部既有 vitest / playwright（若有）
- docker compose 起环境，手动验收 acceptance 第 9 条（"两 Tab 正常显示"）

---

⚠️ **反向补契约**：shadcn Tabs 是新引入组件，需要 Evaluator 确认 `tabs.tsx` 内容与官方 Context7 最新文档一致，**不得使用训练数据记忆**（CLAUDE.md 规则）。
