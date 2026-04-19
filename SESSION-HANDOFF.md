# SESSION-HANDOFF.md

> 生成时间：2026-04-19
> 当前分支：`feat/workbench-refactor`
> 刚完成：**Phase 3（Watchlist / Journal / Logs / MarketOverview / QuickAdd widget 迁移）**
> 下一步：Phase 4（根路由切换 + 清理老 pages + TopNav 简化）

---

## 本 Session 完成的内容

### Phase 3：5 个 widget 迁移
- **WatchlistWidget**（`src/workbench/widgets/WatchlistWidget.tsx`）
  - 复用 `SignalBoard` + `AddStockCard`
  - `onSelectStock` 改为 `setSelectedSymbol(ticker)` → 驱动 Chart/Fundamentals/Pullback widget 联动
  - 空/加载/错误三态保留
- **JournalWidget**（`src/workbench/widgets/JournalWidget.tsx`）
  - 复用 `JournalTable` + `JournalFilterCard` + `JournalEntryDialog`
  - Filter 与 `+ New Entry` 按钮同排；Table 外包 `overflow-x-auto` 避免窄宽溢出
- **LogsWidget**（`src/workbench/widgets/LogsWidget.tsx`）
  - 复用 `LogLevelFilter` + `LogsTable`，Table 外包 `overflow-x-auto`
- **MarketOverviewWidget**（`src/workbench/widgets/MarketOverviewWidget.tsx`）
  - 薄包 `MarketOverviewBar`（41.78px 高度适配 widget h=2）
- **QuickAddWidget**（`src/workbench/widgets/QuickAddWidget.tsx`）
  - 直接包 `JournalQuickAddCard`
- **WidgetRegistry 重写**：
  - 新增 5 个 manifest，删除 `demo.controls`（DemoWidget.tsx 已删除）
  - `WidgetCategory` 去掉 `'demo'`
  - 默认布局（12 列）：
    - MarketOverview: y=0 w=12 h=2
    - Chart: y=2 x=0 w=8 h=8
    - Fundamentals: y=2 x=8 w=4 h=4
    - Pullbacks: y=6 x=8 w=4 h=4
    - Watchlist: y=10 x=0 w=8 h=8
    - QuickAdd: y=10 x=8 w=4 h=8
    - Journal: y=18 w=12 h=8
    - Logs: y=26 w=12 h=6
- **useLayoutStore persist key `v2 → v3`**：老布局自动失效，避免引用已删除的 `demo.controls`
- **features.json**：F101 → `phase: needs_review`（待 Phase 4 一起验收）
- **验收**：`pnpm build` 零 TS 错误（bundle 772KB / gzip 239KB，仍待 Phase 5 code-split）

---

## 当前状态

### Pipeline
| 阶段 | 状态 |
|------|------|
| Phase 0 文档对齐 | ✅ done（`681a988`） |
| Phase 1 框架脚手架 | ✅ done（`d7ea3d6`） |
| Phase 2 拆 StockDetailModal | ✅ done（`f96ce4f`） |
| Phase 3 迁移列表 widget | ✅ done（本 session） |
| Phase 4 路由切换 + 清理 | ⬜ next |
| Phase 5 验收 + 发 v1.1.0 | ⬜ |

### features.json 状态
| Feature | phase |
|---------|-------|
| F100 Workbench 框架 | `done` |
| F101 SMA150 widget 迁移 | `needs_review` |
| F102 路由切换 + 清理 | `design_needed` |

### 环境快照
- git branch：`feat/workbench-refactor`（未 commit，见"下一步"第 0 步）
- 后端：本地 uvicorn 监听 `127.0.0.1:8000`
- 前端：`/workbench` 可用；老路由 `/` `/journal` `/logs` 继续工作
- localStorage key：`ma150.workbench.layouts.v3`（v1/v2 已废弃）
- 已知非阻塞问题：
  - `pnpm lint` 2 个 pre-existing 警告
  - bundle 超 500KB 阈值（772KB raw / 239KB gzip），Phase 5 前 code-split

---

## 下一步 Phase 4 任务

**目标**：Workbench 接管根路由 `/`，清理老 pages 和 StockDetailModal，TopNav 简化。

### 需要做的事（按依赖顺序）

0. **先 commit Phase 3**（如果接手者看到未 commit 的改动）：
   ```
   git add -A && git commit -m "refactor(workbench): phase 3 - migrate watchlist/journal/logs/market/quickadd widgets"
   ```
1. **App.tsx 路由切换**：
   - `/` 渲染 Workbench（现为 Dashboard）
   - `/journal`、`/logs` redirect 到 `/`
   - 移除 `/workbench` 临时路由（或保留 alias）
2. **删除老 pages 和 Modal**：
   - `src/pages/Dashboard.tsx`
   - `src/pages/Journal.tsx`
   - `src/pages/Logs.tsx`
   - `src/components/features/stock-detail/StockDetailModal.tsx`（确认无 widget 引用后删）
3. **TopNav 简化**：
   - 移除 Dashboard / Journal / Logs 路由链接
   - 保留 Refresh Data 按钮
4. **验证**：
   - `/` 直接渲染 Workbench 默认布局
   - 访问 `/journal` `/logs` 自动跳 `/`
   - `pnpm build` 零 TS 错误
   - 浏览器实测：所有 widget 功能正常，点 Watchlist 股票 → Chart/Fund/Pullback 联动
5. **features.json**：F101 → `done`, F102 → `in_progress`

### Phase 5 预告
- `React.lazy(Workbench)` code-split，bundle < 500KB
- CHANGELOG.md v1.1.0 条目
- 合 main → tag v1.1.0

---

## 未决事项 / 风险

1. **StockDetailModal 删除前**：确认除了 Dashboard.tsx 没有其他引用（Phase 4 前 grep 一次）
2. **老路由 redirect**：使用 `<Navigate to="/" replace />` 还是 404，需决策（倾向 redirect）
3. **TopNav refresh 按钮**：依赖 `useRefreshStatus` 查看是否还需路由感知
4. **bundle size**：Phase 5 前 `React.lazy`

---

## 下一个 Session 继续指令

```
继续 workbench 重构 Phase 4：根路由切换 + 清理老 pages + TopNav 简化。
先读 SESSION-HANDOFF.md，然后按"Phase 4 任务"逐条执行。
```
