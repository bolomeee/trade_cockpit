# Sprint Contract：F105-c 前端 MarketBreakoutWidget

> 日期：2026-04-21 | 状态：已确认
> 依赖：F105-a4 ✅ done（后端读端点）· F105-b ✅ done（chart fallback）
> 视觉：沿用 F105 notes 的 7 条"视觉沿用清单"（D043，无独立 design-spec）
> 引用：
>   API-CONTRACT.md#GET-/api/market/breakouts
>   frontend/src/workbench/widgets/WatchlistWidget.tsx（表格/按钮风格基准）
>   frontend/src/workbench/WidgetRegistry.ts（注册入口）

---

## 本次实现范围

1. `frontend/src/types/market.ts`：追加 `BreakoutItem` / `BreakoutSnapshot`
2. `frontend/src/lib/api/market.ts`：追加 `getBreakouts()`
3. `frontend/src/workbench/widgets/MarketBreakoutWidget.tsx`（新建）：
   - `useQuery(['breakouts'], getBreakouts, { staleTime: 5min })`
   - 空态：`scanDate==null → "Waiting for today's scan"`；`items==[] → "No breakouts today"`
   - 加载骨架 / 错误重试（对齐 Watchlist）
   - 表格列：Ticker / Company / Close / % Above MA150 / +
   - 行点击 `setSelectedSymbol(ticker)` 联动 ChartWidget（由 F105-b fallback 支撑）
   - `+` 按钮：shadcn Button ghost icon + lucide Plus，rounded-full；三态 idle / loading / added（`Check` 灰显）；`DUPLICATE` 也视为 added；`stopPropagation`
   - 默认按 `pctAboveMa150` 升序（后端已排序，前端不再排）
   - 移动端 `overflow-x-auto`
4. `frontend/src/workbench/WidgetRegistry.ts`：
   - `WidgetCategory` 扩展 `'scanner'`
   - 注册 `scanner.breakouts`，`defaultLayout={x:0,y:16,w:8,h:8,minW:5,minH:5}`

## 明确排除
- 手动触发扫描（契约无此端点）
- 回踩标记在 fallback 下显示（后端固定空）
- localStorage 自动迁移（D043 + F105 notes：手动 reset）
- 单元测试（项目无前端测试框架）

## 预计修改文件（4 个）
| # | 文件 | 改动 |
|---|---|---|
| 1 | `frontend/src/types/market.ts` | 追加类型 |
| 2 | `frontend/src/lib/api/market.ts` | 追加 helper |
| 3 | `frontend/src/workbench/widgets/MarketBreakoutWidget.tsx` | 新建 |
| 4 | `frontend/src/workbench/WidgetRegistry.ts` | 注册 + 新 category |

## 完成标准
| # | 标准 | 方式 |
|---|---|---|
| 1 | 空态文案准确 | preview |
| 2 | 表格列顺序与字段对齐 | preview |
| 3 | 行点击联动 ChartWidget | preview |
| 4 | + 按钮三态可见且不触发行点击 | preview |
| 5 | 默认 pctAboveMa150 升序 | preview |
| 6 | `tsc --noEmit` 0 错 | 静态 |
| 7 | `pnpm build` 成功 | 静态 |
| 8 | Workbench 其他 widget 不受影响 | preview |

## 自检
- [ ] `tsc --noEmit` 无错
- [ ] `pnpm build` 成功
- [ ] preview：widget 可渲染空态 / 列表 / 点击联动 / + 按钮三态
- [ ] features.json F105-c phase 流转 in_progress → testing → needs_review
- [ ] claude-progress.txt 追加

---

👤 已确认，进入 Generator。
