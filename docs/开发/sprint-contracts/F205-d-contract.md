# Sprint Contract：F205-d PoolBuilderWidget 前端

> 日期：2026-04-27 | 状态：已确认
> 父 Feature：F205 Pool Builder Widget（v1.9 Cockpit P1）
> 前置 Sprint：F205-a ✅ / F205-b ✅ / F205-c ✅（GET /api/cockpit/pool 已交付）
> 引用文档：
>   - `docs/系统设计/API-CONTRACT.md` §GET /api/cockpit/pool（行 1322–1388）
>   - `docs/设计/design-spec.md` §Widget 3：PoolBuilderWidget（行 872–902）
>   - `docs/设计/data-mapping.md` §Cockpit-3（行 439–488）
>   - `docs/设计/component-plan.md` §PoolBuilderWidget（行 416–419）+ §Cockpit-4 react-query 表（行 492）
>   - `docs/系统设计/DECISIONS.md` D080（非 watchlist 字段 null 显示规则）

---

## 0. Sprint 定位

F205 拆 4 子 sprint：F205-a ✅ → F205-b ✅ → F205-c ✅ → **F205-d（本 sprint）**。

本 sprint 完全在前端，**不**碰后端。最近邻参考组件：`SetupMonitorWidget`（同 cockpit 表格 widget 模式）。

---

## 1. 本次实现范围

### 1.1 新建 API client（`cockpitPoolApi.ts`）
- 类型：`PoolFilters` / `PoolFunnel` / `PoolItem` / `PoolData`
- 函数：`getCockpitPool(filters: PoolFilters): Promise<PoolData>`
- URL 拼接：传入字段拼为 query string；空字段不附加；`sectors` / `setupTypes` 用逗号分隔
- 60s timeout：通过 `AbortController` + `setTimeout`

### 1.2 新建 `PoolBuilderWidget.tsx`
- Funnel 5 段（横向）：tradable / trend / rs / fundamental / action，千分位显示
  - **段点击交互**：仅作高亮提示，**不切换表格内容**（后端只返回 action 层 items，前端无需切层）
- Filter Bar（默认展开，inline 一行）：marketCapMin / priceMin / advMin / trendScoreMin / rsPercentileMin / revenueGrowthYoyMin / sectors / setupTypes / limit
- 候选表列：Ticker / Name / Sector / Price / Trend / RS / Setup / Dist Pivot / Dist 50MA / Earnings (D-N) / Revenue Growth / Action / `[+]`
- `[+ Add]` 按钮 → `addStock(ticker)`（既有 `src/lib/api/watchlist.ts`）→ invalidate `['cockpit-pool']` + `['watchlist']`
- 4 种状态：loading / 空 / 错误 / 正常
- 非 watchlist 字段为 null 时显示 `—`（trendScore / setupType / distanceToPivotPct，对应 D080）
- react-query：staleTime 60_000ms

### 1.3 新建 `_poolFilterBar.tsx`
- 受控 props：`value: PoolFilters`、`onChange: (next: PoolFilters) => void`
- 内部 debounce 300ms 后回调 `onChange`（design-spec 第 901 行）
- 数字输入用 shadcn `Input type="number"`；sectors / setupTypes 用多选（暂用逗号分隔 input，简化）

### 1.4 修改 `CockpitRegistry.ts`
- 新增 `cockpit.pool-builder` manifest，category=`pool`
- defaultLayout：`{ x: 0, y: 22, w: 12, h: 10, minW: 6, minH: 6 }`（在 ActionList 下方独占一行）

### 1.5 测试
- `cockpitPoolApi.test.ts`：4 个用例
- `PoolBuilderWidget.test.tsx`：9–12 个组件用例

### 排除
- Funnel 段点击切换显示层级（需后端补返回各层 items；属 F205-e）
- AI 增强（v2.0 F210/F211）
- sectors / setupTypes 的多选 dropdown UI（用逗号分隔 input 简化；后续可换 shadcn 多选组件）
- 后端任何改动

---

## 2. 预计修改文件清单（共 6 个）

| # | 文件 | 状态 |
|---|------|------|
| 1 | `frontend/src/cockpit/lib/api/cockpitPoolApi.ts` | 新建 |
| 2 | `frontend/src/cockpit/widgets/PoolBuilderWidget.tsx` | 新建 |
| 3 | `frontend/src/cockpit/widgets/_poolFilterBar.tsx` | 新建 |
| 4 | `frontend/src/cockpit/CockpitRegistry.ts` | 修改 |
| 5 | `frontend/src/cockpit/widgets/__tests__/PoolBuilderWidget.test.tsx` | 新建 |
| 6 | `frontend/src/cockpit/lib/api/__tests__/cockpitPoolApi.test.ts` | 新建 |

✅ 6 ≤ 6 文件原则上限。

---

## 3. 完成标准（可测试）

| # | 标准 | 测试层级 | 工具 |
|---|------|---------|------|
| 1 | API client 默认无参时不附 query string（空对象） | 单元 | vitest mock fetch |
| 2 | API client 多 filter 同时传时正确 URL 编码（sectors 多选逗号分隔） | 单元 | vitest mock fetch |
| 3 | API client 60s timeout 通过 AbortSignal 触发 | 单元 | vitest fake timer |
| 4 | API client 错误响应（4xx/5xx）throw | 单元 | vitest |
| 5 | Widget loading 状态显示 Loading 文案 | 组件 | RTL queryByText |
| 6 | Widget funnel 全 0 + items 空 显示空态文案 | 组件 | RTL |
| 7 | Widget error 状态显示错误文案 | 组件 | RTL |
| 8 | Funnel 5 个数字千分位显示，点击段切换 active 高亮 | 组件 | RTL fireEvent |
| 9 | 候选表正确渲染所有列；非 watchlist 字段为 null 时显示 `—` | 组件 | RTL |
| 10 | Filter 改变 → 300ms debounce 后重新请求（fake timer 推进 < 300ms 不发） | 组件 | RTL + fake timer |
| 11 | `[+ Add]` 点击 → 调 addStock + invalidate `['cockpit-pool']` + `['watchlist']` | 组件 | RTL + mock |
| 12 | `inWatchlist=true` 行初始按钮即灰 `[✓ in watchlist]` | 组件 | RTL |
| 13 | Registry 注册 `cockpit.pool-builder`，`getCockpitDefaultLayout()` 包含该 id | 单元 | vitest |
| 14 | TypeScript 编译无错（`pnpm tsc --noEmit`） | lint | tsc |
| 15 | 前端全量回归无引入失败 | 回归 | `pnpm test` |

---

## 4. Evaluator 自检清单

- [ ] 单元测试全部通过（API client + Registry，#1–4 + #13）
- [ ] 组件测试全部通过（PoolBuilderWidget #5–12）
- [ ] TypeScript 编译无错
- [ ] 前端全量回归通过
- [ ] 字段名严格对照 API-CONTRACT.md（trendScore / rsPercentile / distanceToPivotPct / distanceTo50maPct / daysUntilEarnings / revenueGrowthYoy / suggestedAction / inWatchlist）
- [ ] 颜色/字体/间距全部走 token，无硬编码 hex
- [ ] 非 watchlist null 字段显示 `—`（对照 D080）
- [ ] react-query staleTime 60_000ms（component-plan §Cockpit-4）
- [ ] debounce 300ms（design-spec 第 901 行）
- [ ] `[+ Add]` 成功后同时 invalidate `['cockpit-pool']` + `['watchlist']`
- [ ] CockpitRegistry 新增一行注册，defaultLayout 不与现有 widget 严重重叠
- [ ] 无 console.error 遗留

### 代码质量检查
- [ ] Lint 通过，无新增 warning
- [ ] 无死代码
- [ ] 无硬编码魔法值（debounce / staleTime / timeout 提为命名常量）
- [ ] 函数 ≤ 50 行（拆分子组件如行渲染）
- [ ] 错误处理完整（fetch try-catch 不吞错）

---

## 5. 已确认的开放问题

1. **Funnel 段点击**：仅高亮，不切换表格内容。
2. **defaultLayout**：`{ x: 0, y: 22, w: 12, h: 10, minW: 6, minH: 6 }`。
3. **filter bar**：默认展开（inline 一行）。

---

## 6. 开发顺序（Generator 阶段）

1. 新建 `cockpitPoolApi.ts`（类型 + 函数 + 60s timeout）→ wip commit
2. 新建 `cockpitPoolApi.test.ts` 4 个用例 → 通过 → wip commit
3. 新建 `_poolFilterBar.tsx`（受控 + debounce）→ wip commit
4. 新建 `PoolBuilderWidget.tsx`（Funnel + 表 + Add 按钮）→ wip commit
5. 修改 `CockpitRegistry.ts` 注册 → wip commit
6. 新建 `PoolBuilderWidget.test.tsx` 9–12 个用例 → 通过 → wip commit
7. `pnpm tsc --noEmit` + `pnpm test` 全量回归 → Evaluator 自检 → 最终 commit `feat(F205-d): ...`

---
