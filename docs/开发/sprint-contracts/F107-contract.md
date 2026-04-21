# Sprint Contract：F107 股价图成交量 + 短期均线叠加

> 日期：2026-04-21 | 状态：**反向补契约**
> 依赖：F102（ChartWidget v1.1.0 已稳定）
> 引用文档：
>   design-spec.md#ChartWidget（本 Contract 要求新增 MA5/MA20 图例与 volume histogram 小节）
>   context7 `/tradingview/lightweight-charts`（HistogramSeries / 双 priceScale API）

---

## 本次实现范围

### 1. `frontend/src/components/features/stock-detail/PriceChart.tsx`（修改）
- 引入 `HistogramSeries`（lightweight-charts v5）
- candleSeries 主 priceScale 增加下边距：`scaleMargins: { top: 0.05, bottom: 0.25 }`
- 新增独立 `priceScaleId: 'volume'` 的 HistogramSeries：
  - `priceFormat: { type: 'volume' }`
  - `priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } })`（底部 20% 区域专用）
  - 颜色按 `close >= open ? upColor+'66' : downColor+'66'`（40% 透明度）
  - `priceLineVisible: false`、`lastValueVisible: false`
- 新增 `shortMaData(window, color)` 内部 helper，计算简单移动均线：
  - MA5：`#f59e0b`（橙）
  - MA20：`#8b5cf6`（紫）
  - 使用滚动窗口算法，O(N) 复杂度，不使用第三方 lib
  - 前 N-1 天跳过（不画点）
- 容器 style 加 `position: 'relative'`（为未来叠加标签留位，本 sprint 暂无使用）

### 2. `frontend/src/workbench/widgets/ChartWidget.tsx`（修改）
- Ticker 区块下增加均线图例 `<div>`：
  - `— MA5`（`#f59e0b`）
  - `— MA20`（`#8b5cf6`）
  - `— MA150`（token `--color-signal-breakout` fallback `#2962ff`）
  - 布局：`flex-direction: column / gap: 2 / fontSize: 11 / font-family: var(--font-family-numeric)`

### 3. `docs/设计/design-spec.md`（修改）
- ChartWidget 小节补充：
  - **均线图例**：左上角同时显示 MA5 / MA20 / MA150 三条均线的颜色标记
  - **成交量 Histogram**：图表底部 20% 区域独立绘制每日成交量柱，颜色跟随当日涨跌（涨=绿 40%，跌=红 40%）
  - **短均线颜色**：MA5 `#f59e0b`（橙）、MA20 `#8b5cf6`（紫）；这两个颜色不走 token，是 TradingView 社区约定的短期均线配色
- 小节标注 `(F107，v1.3 起)`

---

## 明确排除

- 后端改动（chart API schema 不变，bars 已含 volume 字段）
- MA5 / MA20 的信号判断逻辑（本 sprint 仅展示层）
- 图例 hover 互动 / 隐藏切换（未来 feature）

---

## 预计修改文件（共 3 个）

| # | 文件 | 类型 | 改动 |
|---|---|---|---|
| 1 | `frontend/src/components/features/stock-detail/PriceChart.tsx` | 修改 | +54 行：HistogramSeries + 两条短均线 |
| 2 | `frontend/src/workbench/widgets/ChartWidget.tsx` | 修改 | +15 行：MA 图例 |
| 3 | `docs/设计/design-spec.md` | 修改 | ChartWidget 小节补图例 / volume / 短均线颜色约定 |

---

## 可测试的完成标准

| # | 标准 | 层级 |
|---|---|---|
| 1 | Chart 底部 20% 区域显示成交量 Histogram | 手工 |
| 2 | Histogram 颜色：涨日用 upColor（~40% 透明），跌日用 downColor（~40% 透明）| 手工 |
| 3 | 图表上同时可见 3 条均线：MA5 橙、MA20 紫、MA150 蓝 | 手工 |
| 4 | MA5 / MA20 前 N-1 天不画点（无左端突刺）| 手工 |
| 5 | ChartWidget 左上角图例列出三条均线颜色标记 | 手工 |
| 6 | Ticker 空态、loading 态、error 态行为不变（F102 既有测试仍绿）| 回归 |
| 7 | 短均线颜色 `#f59e0b / #8b5cf6` 硬编码，DECISIONS 或 design-spec 已备注理由 | 文档 |
| 8 | `pnpm --filter frontend typecheck` + `build` 通过 | 静态 |
| 9 | design-spec.md ChartWidget 小节含 MA5/MA20/Volume 三条 | 文档 |

---

## Evaluator 自检清单

> 2026-04-22 反向补契约 Evaluator：测试门禁沿用 D048 降级（无 vitest 基建），硬门禁 = typecheck + build + docker 后端 payload + 手工视觉。

- [x] `pnpm --filter frontend typecheck` 通过（tsc -b）
- [x] `pnpm --filter frontend build` 通过（vite build 371ms）
- [x] docker 后端 `/api/stocks/AAPL/chart` 返回 250 bars（带 volume 字段）+ 101 MA150 points（payload 支撑 F107 视觉层）
- [x] design-spec.md 有 F107 备案段落（第 250-258 行，含 MA5/MA20/Volume/图例/颜色约定）
- [ ] 浏览器手工验证 5 项视觉（用户本地 Vite dev 或 docker 8080，建议 AAPL ticker）—— 交给用户验收阶段
- [x] 代码审查：PriceChart 切 ticker 时 useEffect cleanup `chart.remove()` 正确释放 series（第 176-179 行）
- [x] 代码审查：无 `console.error` 遗留

### 代码质量检查
- [x] `shortMaData`（PriceChart.tsx 第 128-150 行）为纯函数式实现：rolling window 单次 for 循环 O(N)，前 window-1 天不 push 点
- [x] 颜色常量（`#f59e0b / #8b5cf6`）集中在 `shortMaData` 调用处（第 151-152 行），两行相邻，不散落
- [x] lightweight-charts v5 API 使用正确：`createChart / CandlestickSeries / HistogramSeries / LineSeries / createSeriesMarkers` 导入 + 双 priceScale 用法（candleSeries 默认 priceScale scaleMargins，volumeSeries `priceScaleId: 'volume'`）与 Context7 `/tradingview/lightweight-charts` 最新文档一致

### 回归测试
- 前端 vitest 不适用（D048）
- F102 既有 ChartWidget 手工 smoke：切 ticker / 空态 / loading / error 四态 —— 交给用户验收阶段

---

⚠️ **反向补契约**：lightweight-charts 的双 priceScale 用法（volume 独立 id）需在 Evaluator 阶段用 Context7 验证 API 是否与 v5 最新一致。
