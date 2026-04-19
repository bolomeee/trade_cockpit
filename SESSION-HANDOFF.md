# SESSION-HANDOFF.md

> 生成时间：2026-04-19
> 当前分支：`feat/workbench-refactor`
> 刚完成：**Phase 3（5 widget 迁移）+ Phase 3.5（Workbench UI 精修）**
> 下一步：Phase 4（根路由切换 + 清理老 pages + TopNav 简化）

---

## 本 Session 完成的内容

### Phase 3：5 个 widget 迁移（commit `99d0c30`）
- **WatchlistWidget**：复用 `SignalBoard` + `AddStockCard`；`onSelectStock` → `setSelectedSymbol(ticker)` 驱动 Chart/Fundamentals/Pullback widget 联动
- **JournalWidget**：复用 `JournalTable` + `JournalFilterCard` + `JournalEntryDialog`；Filter 与 `+ New Entry` 同排，Table 外包 `overflow-x-auto`
- **LogsWidget**：复用 `LogLevelFilter` + `LogsTable`，同样 Table 外包 `overflow-x-auto`
- **MarketOverviewWidget**：薄包 `MarketOverviewBar`（已在 Phase 3.5 删除，见下）
- **QuickAddWidget**：直接包 `JournalQuickAddCard`
- **WidgetRegistry**：新增 5 manifest，删 `demo.controls` + `DemoWidget.tsx`；`WidgetCategory` 去掉 `'demo'`
- **useLayoutStore persist key `v2 → v3`**：老布局自动失效

### Phase 3.5：Workbench UI 精修（尚未 commit）
1. **MarketOverviewWidget 删除**（用户要求）
   - `MarketOverviewWidget.tsx` 删除、Registry 去除 `market.overview`、category 去 `'market'`
   - persist key `v3 → v4` 避免老布局引用已删 id
   - 其余 7 widget 默认布局上移填补空位
2. **Workbench 顶栏清理**
   - 删除 `<h1>Workbench</h1>` 与旧"重置布局"按钮
   - 新建 `ResetLayoutButton.tsx`（复用 `RefreshButton` 样式：32px 高/相同 border/radius/字号，图标 `RotateCcw`）
   - `App.tsx` 用 `useLocation` 检测 `/workbench`，在 `MarketOverviewBar` 外层 `position: relative` 容器右侧（`right: var(--spacing-6)`）绝对定位渲染重置按钮，和 10Y Treasury 同行右对齐
3. **WidgetShell 视觉精简**
   - 标题栏高度 `h-9 (36px)` → `h-[18px]`（减半）
   - 标题字体 `text-sm font-semibold` → `text-xs`（去粗体、缩小）
   - padding `px-3` → `px-2`
   - 右上角加 `X` 关闭按钮（`onMouseDown/onClick stopPropagation` 防拖拽冲突），`onClose` 回调从 layout 过滤掉该 id
   - 圆角 `rounded-lg (8px)` → `rounded (4px)`（减半）
4. **Grid margin 减半**：`[12, 12]` → `[6, 6]`

### 验收
- `pnpm build` 零 TS 错误（bundle 773KB / gzip 239KB，仍待 Phase 5 code-split）
- 未在浏览器实测；下一 session 开始建议 `pnpm dev` 走一遍（关闭 widget → 重置布局恢复；点 Watchlist 股票 → Chart/Fund/Pullback 联动）

---

## 当前状态

### Pipeline
| 阶段 | 状态 |
|------|------|
| Phase 0 文档对齐 | ✅ done |
| Phase 1 框架脚手架 | ✅ done |
| Phase 2 拆 StockDetailModal | ✅ done |
| Phase 3 迁移列表 widget | ✅ done（`99d0c30`） |
| Phase 3.5 UI 精修 | ✅ done（待 commit） |
| Phase 4 路由切换 + 清理 | ⬜ next |
| Phase 5 验收 + 发 v1.1.0 | ⬜ |

### features.json
| Feature | phase |
|---------|-------|
| F100 Workbench 框架 | `done` |
| F101 SMA150 widget 迁移 | `needs_review` |
| F102 路由切换 + 清理 | `design_needed` |

### 环境快照
- git branch：`feat/workbench-refactor` · `99d0c30` + 未 commit（Phase 3.5）
- localStorage key：`ma150.workbench.layouts.v4`（v1/v2/v3 已废弃）
- MarketOverviewBar 仍由 `App.tsx` 全局渲染（所有路由可见），不再作为 widget
- Workbench 可见 7 widget：Chart / Fundamentals / Pullback / Watchlist / QuickAdd / Journal / Logs

---

## 下一步 Phase 4 任务

**目标**：Workbench 接管根路由 `/`；保留 `/journal` `/logs` 作为独立页；清理 Dashboard 和 Modal。

### 用户确认的范围（2026-04-19）
- **保留独立路由**：`/journal` `/logs` 继续存在，TopNav 保留这两个链接
- **Workbench 首页 widget**：Chart / Fundamentals / Pullback / Watchlist / QuickAdd（共 5 个）
- **Workbench 不放 JournalWidget / LogsWidget**（独立页已覆盖）
- **QuickAddWidget 保留**（首页快捷录入一笔 journal，与独立 Journal 页并存）

### 执行步骤

1. **路由切换（App.tsx）**
   - `/` → Workbench（取代 Dashboard）
   - `/journal` → Journal（不变）
   - `/logs` → Logs（不变）
   - 移除 `/workbench` 临时路由
   - `ResetLayoutButton` 显示条件从 `pathname === '/workbench'` 改为 `pathname === '/'`

2. **删除 Workbench 里的 Journal/Logs widget**
   - 删 `src/workbench/widgets/JournalWidget.tsx`
   - 删 `src/workbench/widgets/LogsWidget.tsx`
   - `WidgetRegistry.ts` 移除 `journal.list` / `logs.list`；category `'logs'` 若只剩一个用户可去（或保留）
   - `useLayoutStore` persist key `v4 → v5`

3. **删除老文件**
   - `src/pages/Dashboard.tsx`
   - `src/components/features/stock-detail/StockDetailModal.tsx`（先 grep 确认只有 Dashboard 引用）

4. **TopNav 改造**
   - 移除 Dashboard 链接，保留 Journal / Logs
   - 首页 `/` 的激活样式：Journal/Logs 链接在 `/` 时都不激活（`NavLink end` 行为默认已满足）
   - 保留 Refresh Data 按钮

5. **验证**
   - `pnpm build` 零 TS 错误
   - 浏览器：`/` 显示 Workbench 5 widget；`/journal` `/logs` 独立页正常；点 Watchlist ticker → Chart/Fund/Pullback 联动；QuickAdd 提交后 `/journal` 能看到新条目
   - `pnpm dev` 先跑一遍再 commit

6. **features.json**：F101 → `done`，F102 → `in_progress`

### Phase 5 预告
- `React.lazy(Workbench)` code-split → bundle < 500KB
- CHANGELOG.md v1.1.0 条目
- 合 main → tag v1.1.0

---

## 未决事项 / 风险

1. **关闭的 widget 恢复**：目前唯一入口是"重置布局"（全部恢复）。Phase 5 前考虑加 widget picker（部分恢复）
2. **StockDetailModal 删除前**：grep 确认除 `Dashboard.tsx` 外无引用
3. **bundle size**：Phase 5 前 `React.lazy`
4. **Workbench widget 数量收敛**：用户确认首页只保留 5 个（Chart/Fund/Pullback/Watchlist/QuickAdd），Journal/Logs 回归独立页

---

## 下一个 Session 继续指令

```
继续 workbench 重构 Phase 4：根路由切换 + 清理老 pages + TopNav 简化。
先读 SESSION-HANDOFF.md，然后按"Phase 4 任务"逐条执行。
```
