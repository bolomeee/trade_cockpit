# Sprint Contract：F107-b2 前端 ChartWidget Vol/Float 比率显示

> 日期：2026-04-22 | 状态：草案
> 引用文档：
>   API-CONTRACT.md#GET /api/stocks/{ticker}/chart（含 `sharesFloat`，F107-b1 落地）
>   DECISIONS.md D049 / D052 / D053
>   features.json#F107-b2（acceptance_criteria / notes）
>   前置：F107-b1 done（47c70da）
>   后续：无（F107-b 系列收尾）

---

## 本次实现范围

**包含**：
1. `ChartData` 类型新增 `sharesFloat: number | null`，与后端 camelCase 对齐
2. 新建 `frontend/src/lib/format.ts`，抽出共用的 `formatPercent(value, { digits?, fallback? })`；将 `FundamentalsCard` 中的同名私有函数替换为共用版本（行为保持一致：`null/undefined → null` 由调用方决定展示）
3. `PriceChart` 新增可选 prop `onHoverChange?: (bar: ChartBar | null) => void`：
   - 通过 `chart.subscribeCrosshairMove` 获取当前 hover 的 bar（按时间戳匹配回原始 bar 对象）
   - 移出图表区域 / param.time == null → 回调 `null`
   - 回调函数用 `useRef` 持有最新值，effect 依赖只保持 `[data]`，不因父组件重渲染而重建 chart
4. `ChartWidget` 图例三行 MA 下方新增一行 `Vol/Float: X.XX%`：
   - 默认显示最新交易日（bars 最后一条）的 `volume / sharesFloat * 100`
   - hover 切换到 hover 到的 bar；离开回到最新
   - `sharesFloat == null` 或 `bars.length == 0` → 显示 `—`
   - 保留 `pointerEvents: 'none'`，不挡鼠标事件

**明确排除（本次不做）**：
- 不动后端（F107-b1 已落地）；不改 API-CONTRACT、DATA-MODEL、DECISIONS
- 不加 crosshair 时的 OHLC tooltip（超出 F107-b2 范围）
- 不做前端单元测试（D048 降级，延至 v1.4）
- 不做历史 shares_float（D052：所有 bar 用当前 float，保持 b1 语义）

---

## 预计修改文件（5 个，在 6 文件上限内）

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `frontend/src/types/stockDetail.ts` | 修改 | `ChartData` 增 `sharesFloat: number \| null` |
| 2 | `frontend/src/lib/format.ts` | 新建 | 导出 `formatPercent(value: number \| null \| undefined, opts?: { digits?: number; fallback?: string }): string`；默认 `digits=2`、`fallback='—'`；入参若为小数比例由调用方自行 `*100` 再传入，以保持调用显式 |
| 3 | `frontend/src/components/features/stock-detail/PriceChart.tsx` | 修改 | 新增 `onHoverChange?` prop；`subscribeCrosshairMove` 按时间戳 O(1) 反查 bar（预构 `Map<UTCTimestamp, ChartBar>`）；callback 用 `useRef` 保持稳定 |
| 4 | `frontend/src/workbench/widgets/ChartWidget.tsx` | 修改 | `useState<ChartBar \| null>` 持有 hover bar；`useMemo` 计算当前显示 bar（hover ?? latest）；渲染 `Vol/Float: …%` 行，使用 `formatPercent` |
| 5 | `frontend/src/components/features/stock-detail/FundamentalsCard.tsx` | 修改 | 移除本地 `formatPercent`，改 import 自 `@/lib/format`；调用点显式乘 100（因原实现是把小数比例转百分比），保持现有渲染字符串一致 |

**不计入文件数**：无文档/后端改动。

👤 用户确认文件列表合理后，方可进入开发。

---

## 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | 打开 ChartWidget，图例显示 `Vol/Float: X.XX%`，数值 = 最新 bar.volume / sharesFloat × 100，与后端响应一致 | E2E（浏览器） | preview + DevTools 对 `/chart` 响应 |
| 2 | hover K 线图中间某根 bar → 图例比率更新为该 bar 的 volume/sharesFloat；移出图表 → 回到最新 | E2E | preview_click / preview_eval 模拟 crosshair |
| 3 | 切换到 sharesFloat 为 null 的 ticker（例如 ETF 或 FMP 404 情景）→ 图例显示 `Vol/Float: —`，无 console.error | E2E | preview_console_logs |
| 4 | 快速连续切换 ticker 无 stale 残影（旧 hover 状态不带入新 ticker） | E2E | preview 手动切换 |
| 5 | `pnpm typecheck` 无新增错误；`pnpm build` 通过 | 编译 | `pnpm -C frontend typecheck && pnpm -C frontend build` |
| 6 | FundamentalsCard 百分比展示与 b2 前完全一致（ROCE 等行肉眼无变化） | 视觉回归 | preview 抓图对比 |

---

## Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] `pnpm -C frontend typecheck` 通过，无新增 warning
- [ ] `pnpm -C frontend build` 通过
- [ ] ChartWidget 显示 `Vol/Float` 行，数值与 `/chart` 响应对账一致
- [ ] hover 任意 bar → 比率更新；移出 → 回到最新
- [ ] sharesFloat=null 场景显 `—`，无 console.error
- [ ] 切换 ticker 无 stale hover 残影（hover state 跟随 data 重置）
- [ ] FundamentalsCard 百分比行展示不变（ROCE 等）
- [ ] `PriceChart` effect 依赖只有 `[data]`，onHoverChange 通过 ref 读取，不造成 chart 重建
- [ ] 颜色 / 字体 / 间距仅使用 CSS 变量或既有硬编码色（MA 色沿用 b1 既定，图例新行遵循 font-family-numeric、font-size 11、gap 2）
- [ ] 字段命名：前端 `sharesFloat` camelCase，与 API-CONTRACT.md 一致（DATA-MODEL 后端 snake_case 不受影响）
- [ ] 无 console.log / debugger 调试遗留；无死代码（FundamentalsCard 本地 formatPercent 已删除）
- [ ] 无硬编码魔法值（百分比精度 `digits=2` 作为 formatPercent 默认参数；`fallback='—'` 作为默认参数）

### 回归（浏览器层）
- [ ] 其他 widget（Watchlist / Fundamentals / Pullback / Scanner）渲染无回归
- [ ] PriceChart 在无 hover 订阅的其它场景（如未传 onHoverChange）行为不变

> 本 sprint 硬门禁 = `pnpm typecheck` + `pnpm build` + preview E2E 手工核验 + 代码审查（D048）。
