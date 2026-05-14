# Sprint Contract：F203-c — CockpitChart 前端 Widget

> 状态：contract_agreed | 起草：2026-04-25 | 确认：2026-04-25
> 父 Feature：F203 Decision Panel
> 兄弟：F203-a ✅ / F203-b1 ✅ / F203-b2 ✅ / F203-d ⬜
> 引用文档：
>   - design-spec.md §Widget 4 CockpitChartWidget
>   - component-plan.md §CockpitChartWidget / §ChartHorizontalLine
>   - API-CONTRACT.md §GET /api/cockpit/chart/{ticker} + §GET /api/cockpit/decision/{ticker}
>   - DECISIONS.md D063（独立组件，不复用 workbench `ChartWidget`）

---

## 1. 实现范围（包含 / 排除）

**包含**：
- 新建 `CockpitChartWidget.tsx`：订阅 `cockpitStore.selectedTicker`；selectedTicker 变化触发 `GET /api/cockpit/chart/{ticker}`；selectedTicker 为空时显示空态文案
- 主图（约 80% 高度）：Candlestick + MA10/21/50/150/200 多线 + AVWAP 紫线（anchor 不为 null 时绘制）
- 副图（约 20% 高度）：Volume histogram（up/down 半透明，复用 `--color-change-positive/negative`）
- entry / stop / target2r / target3r 四条横线：联合 `GET /api/cockpit/decision/{ticker}`（F203-b2 已上线），在主图通过 lightweight-charts `createPriceLine` 叠加
  - entry 实线（`--color-chart-entry`）、stop 虚线（`--color-chart-stop`）、target2r/target3r 点线（`--color-chart-target`）
  - decision 请求失败或 404 / 422 → chart 仍可渲染（只是没有横线），不阻断
- Header：`Chart · {ticker} · {setupType} · {quality}`（左）+ MA 颜色 legend（右）
- 新建 `cockpitChartApi.ts`：封装 chart 端点，类型与 API-CONTRACT camelCase 对齐
- 新建 `cockpitDecisionApi.ts`：封装 decision 端点（提前抽出，F203-d 复用）
- Registry 注册 `cockpit.cockpit-chart`
- React Query：
  - `['cockpit-chart', ticker, masKey, days]` staleTime 5min
  - `['cockpit-decision', ticker]` staleTime 1min

**排除（明确不做，留 F203-d）**：
- DecisionPanelWidget（含 Override Form / Recompute / userSettings 表单）
- Risk% override 控件
- D|W timeframe 切换（v1.9 才做，本 Sprint 仅 D）
- MA toggle UI（本 Sprint 固定 5 条 MA；toggle 留 v1.9）
- Setup annotation 文本气泡（design-spec §1167 → 不做）
- Earnings marker ▼（依赖 `/api/cockpit/earnings`，留 F204 widget）
- ATR 序列绘制（数据已返回，但不绘制；预留给 v1.9 ATR 参考带）

---

## 2. 预计修改文件（共 4 个）

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `frontend/src/cockpit/lib/api/cockpitChartApi.ts` | 新建 | `getCockpitChart(ticker, mas?, days?, anchor?)` + 类型 |
| 2 | `frontend/src/cockpit/lib/api/cockpitDecisionApi.ts` | 新建 | `getCockpitDecision(ticker, overrides?)` + 类型 |
| 3 | `frontend/src/cockpit/widgets/CockpitChartWidget.tsx` | 新建 | 主组件（lightweight-charts + 5 MA + AVWAP + Volume + 4 priceLines） |
| 4 | `frontend/src/cockpit/CockpitRegistry.ts` | 修改 | 注册 `cockpit.cockpit-chart` 一行 manifest |

> 4 文件，远低于 6 文件上限。

> ⚠ `tokens.css` 中 `--color-chart-entry/stop/target` 与 `--color-chart-avwap` 若缺失，作为 §5 步骤 1 单独补齐，不计入 4 文件。

---

## 3. 完成标准（可测试）

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| S1 | `cockpitChartApi.getCockpitChart('NVDA')` 默认参数 → `GET /cockpit/chart/NVDA?mas=10,21,50,150,200&days=250`；mas/days/anchor 自定义时拼接 query | 单元 | vitest + msw / fetch mock |
| S2 | `cockpitDecisionApi.getCockpitDecision('NVDA', { entryOverride: 851, riskPctOverride: 0.5 })` → query `entryOverride=851&riskPctOverride=0.5`；override 字段省略时不出现 | 单元 | vitest |
| S3 | `CockpitChartWidget`：selectedTicker=null → 空态文案 "请从 Setup Monitor 选择一只股票"，不发请求 | 集成 | RTL + msw |
| S4 | selectedTicker='NVDA' → loading 骨架；fetch 成功后 chart 实例创建一次，candles/volume/avwap/5 条 MA 系列均 add | 集成 | RTL + spy on `createChart` |
| S5 | decision 端点成功 → `createPriceLine` 调用 4 次（entry/stop/target2r/target3r），title 含价格 | 集成 | spy / series mock |
| S6 | decision 端点 404 → chart 主图正常渲染，不调用 `createPriceLine` | 集成 | RTL + msw |
| S7 | selectedTicker NVDA → CRWD：旧 chart `remove()`，新 chart 重建 | 集成 | RTL |
| S8 | 容器 resize → 调用 chart `applyOptions({ width, height })`（ResizeObserver 接线正确） | 集成 | RTL + ResizeObserver mock |
| S9 | Registry：`COCKPIT_WIDGET_REGISTRY['cockpit.cockpit-chart']` 存在，category='chart'，defaultLayout x=4 y=0 w=5 h=10 minW=4 minH=8 | 单元 | vitest |
| S10 | 颜色：所有颜色读取 `tokens.css` 变量，无硬编码 hex | 静态 | grep |
| S11 | 全量回归：`pnpm -C frontend test` 全过；`pnpm -C frontend run lint` 无新增 warning；`pnpm -C frontend run build` 通过 | 回归 | vitest + eslint + tsc |

---

## 4. Evaluator 自检清单

### 文件存在性
- [ ] 4 个文件全部存在，路径与 §2 一致
- [ ] 未触碰 F203-d 范围（无 DecisionCardWidget / UserSettingsForm / userSettingsApi）

### D063 合规
- [ ] `CockpitChartWidget.tsx` 不 import `components/features/stock-detail/PriceChart.tsx`
- [ ] 不 import 任何 workbench widget 模块
- [ ] lightweight-charts 直接 import，自己创建 chart 实例

### Schema / 字段命名
- [ ] api client 类型字段全 camelCase，与 API-CONTRACT 一致
- [ ] decision 类型：`entryPrice` / `stopPrice` / `target2r` / `target3r` / `setupType` / `setupQuality`

### 设计合规
- [ ] entry 实线、stop 虚线、target2r/3r 点线
- [ ] AVWAP 单独 lineSeries，紫色（`--color-chart-avwap` 或 fallback）
- [ ] Volume histogram 独立 priceScale，up/down 取 `--color-change-positive/negative` + alpha
- [ ] Header 文案 `Chart · {ticker} · {setupType} · {quality}`
- [ ] 空 / 加载 / 失败 三个状态都有 UI

### React Query
- [ ] queryKey 与 component-plan §489 一致
- [ ] decision 单独 queryKey `['cockpit-decision', ticker]`
- [ ] 切 ticker 自动 refetch

### 代码质量
- [ ] 单文件 < 350 行
- [ ] 无 console.log
- [ ] 无未用 import
- [ ] useEffect cleanup 调用 `chart.remove()`

### 测试
- [ ] S1–S11 全过

---

## 5. 开发顺序

1. 检查 `tokens.css` 是否含 `--color-chart-entry/stop/target` 与 `--color-chart-avwap`；缺失则补齐
2. 写 `cockpitChartApi.ts`
3. 写 `cockpitDecisionApi.ts`
4. 写 `CockpitChartWidget.tsx`：
   1. 容器 + ResizeObserver
   2. createChart + Candlestick + Volume
   3. 5 条 MA LineSeries
   4. AVWAP LineSeries
   5. decision query → 4 条 priceLine
5. `CockpitRegistry.ts` 注册
6. 单元 + 集成测试
7. `pnpm -C frontend run lint && pnpm -C frontend test && pnpm -C frontend run build`
8. Evaluator 自检
9. `git commit -m "feat(F203-c): CockpitChart 前端 Widget（chart + decision 联合 + 4 priceLines）"`

---

## 6. 风险与取舍

- **双 query 并行**：chart 与 decision 独立 fetch，decision 失败仅丢横线，不阻断主体。
- **切 ticker 重建实例**：销毁 + 重建（避免 5 MA + AVWAP updateData 复杂度）；250 bars 量级无性能压力。
- **MA 颜色阶梯**：MA21/50/200 用阶梯灰（design-spec §933）；缺失变量第 1 步补齐。
- **jsdom 限制**：lightweight-charts S4/S5/S7/S8 用 spy 断言 API 调用，不做视觉断言。

---

## 7. 已确认条款（2026-04-25）

1. ✅ F203-c 只做 CockpitChartWidget（含 entry/stop/target 横线），DecisionPanel/UserSettings 留 F203-d
2. ✅ 不绘制 ATR / Earnings marker / Setup annotation 气泡
3. ✅ 不做 D|W 切换、不做 MA toggle UI
4. ✅ decision 失败容忍（仅丢横线）
5. ✅ tokens.css 缺失变量补齐作为 §5 步骤 1，不计入 4 文件
6. ✅ 测试策略 spy 断言

---

## 8. 下一 Session 恢复指令

```
继续开发 F203-c，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F203-c-contract.md，
进入 Generator 模式，从开发步骤 1 开始。
```
