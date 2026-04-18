# SESSION-HANDOFF.md

> 生成时间：2026-04-18
> 当前分支：`feat/workbench-refactor`
> 刚完成：**Phase 2（StockDetailModal → 3 个 widget）**
> 下一步：Phase 3（Watchlist / Journal / Logs / MarketOverview / QuickAdd widget 迁移）

---

## 本 Session 完成的内容

### Phase 2（commit `f96ce4f`）：SMA150 Detail widget 拆分
- **PriceChart 响应式改造** (`components/features/stock-detail/PriceChart.tsx`)
  - 去掉硬编码 `height: 302`，去掉 `height` prop
  - `ResizeObserver` 同时监听容器宽高，`chart.applyOptions({ width, height })` 自适应
  - `StockDetailModal` 改用固定 `height`（而非 `minHeight`）给图表提供确定高度，保持原弹窗效果不变
- **3 个 SMA150 widget**（`src/workbench/widgets/`）
  - `ChartWidget`：`useQuery(['chart', symbol])` → 改造后的 PriceChart
  - `FundamentalsWidget`：包 `FundamentalsCard`
  - `PullbackWidget`：包 `PullbackHistoryCard`
  - 共享空态组件 `EmptySymbol.tsx`（"请在 Watchlist 中选择一只股票"）
- **DemoWidget 修正**：从硬编码 `AAPL/MSFT/NVDA` 改为读真实 `GET /api/watchlist`（否则点不到 watchlist 外的 ticker 会 404）
- **WidgetRegistry**：替换 demo.a/b/c → `sma150.chart` / `sma150.fundamentals` / `sma150.pullbacks`，保留 `demo.controls`（DemoWidget）做临时选股
- **useLayoutStore** persist key `v1 → v2`，老布局自动失效
- **vite proxy** `localhost:8000 → 127.0.0.1:8000`（避开 IPv6 与其他 docker 容器冲突）
- **features.json**：F100 → done，F101 → in_progress
- **验收**：`pnpm build` 零 TS 错误；浏览器实测 watchlist ticker 点击 → 3 widget 同步拉数据 + resize 正常

### 联调踩坑记录（不影响代码，记录一下避免复发）
- 宿主机 `localhost:8000` 被另一个 docker 容器 `cuotiben_backend` 占住（0.0.0.0:8000 bind），vite 代理会走 IPv6 `::1` 命中它，导致所有 API 返回 `cuotiben_math API` 的 404。
- 解决办法：vite.config.ts 代理改 `127.0.0.1`。或 `docker stop cuotiben_backend`。
- 本地后端启动命令（需在 backend/ 目录保持运行）：
  ```
  uv run uvicorn app.main:app --reload --port 8000
  ```

---

## 当前状态

### Pipeline
| 阶段 | 状态 |
|------|------|
| Phase 0 文档对齐 | ✅ done（`681a988`） |
| Phase 1 框架脚手架 | ✅ done（`d7ea3d6`） |
| Phase 2 拆 StockDetailModal | ✅ done（`f96ce4f`） |
| Phase 3 迁移列表 widget | ⬜ next |
| Phase 4 路由切换 + 清理 | ⬜ |
| Phase 5 验收 + 发 v1.1.0 | ⬜ |

### features.json 状态
| Feature | phase |
|---------|-------|
| F100 Workbench 框架 | `done` |
| F101 SMA150 widget 迁移 | `in_progress`（Chart/Fundamentals/Pullback 已完成；Watchlist/Journal/Logs/MarketOverview/QuickAdd 待做） |
| F102 路由切换 + 清理 | `design_needed` |

### 环境快照
- git branch：`feat/workbench-refactor` · HEAD：`f96ce4f` · main 合入需等 Phase 5
- 后端：本地 uvicorn 监听 `127.0.0.1:8000`（非宿主机 `localhost`，见踩坑记录）
- 前端：`pnpm dev` 起在 5173（或 5174，视端口占用）；`/workbench` 可用；老路由 `/` `/journal` `/logs` 继续工作
- localStorage key：`ma150.workbench.layouts.v2`（v1 已废弃）
- 已知非阻塞问题：
  - `pnpm lint` 2 个 pre-existing 警告（button.tsx / JournalEntryForm.tsx）
  - bundle 超 500KB 阈值（769KB raw / 238KB gzip），Phase 5 前 code-split

---

## 下一步 Phase 3 任务

**目标**：把 v1.0.0 剩余 UI 全部迁成 widget，使 `/workbench` 功能等价于老 Dashboard + Journal + Logs 三页。

### 需要做的事（按依赖顺序）

1. **WatchlistWidget**（`src/workbench/widgets/WatchlistWidget.tsx`）
   - 包现有 `SignalBoard` + `AddStockCard` 或重写精简版
   - 点击某股票 → `useAppStore.setSelectedSymbol(ticker)` → 驱动 Chart/Fundamentals/Pullback widget 同步
   - 完成后可删掉临时 `demo.controls`（DemoWidget）
2. **JournalWidget**（`src/workbench/widgets/JournalWidget.tsx`）
   - 复用 `JournalTable` + `JournalFilterCard` + `JournalEntryDialog`
   - 考虑窄宽度下 Table 横向滚动不溢出 WidgetShell
3. **LogsWidget**（`src/workbench/widgets/LogsWidget.tsx`）
   - 复用 `/logs` 页面现有 Table + Level toggle filter
4. **MarketOverviewWidget**（`src/workbench/widgets/MarketOverviewWidget.tsx`）
   - 包 `MarketOverviewBar` 组件
5. **QuickAddWidget**（`src/workbench/widgets/QuickAddWidget.tsx`）
   - 包 `JournalQuickAddCard`
6. **更新 WidgetRegistry**：加 5 个新 manifest，重排默认布局，删 `demo.controls`
7. **验证**：
   - `/workbench` 至少可见 8 种 widget 同屏
   - 数据流：点 WatchlistWidget 股票 → Chart/Fundamentals/Pullback 同步
   - Journal 新建/编辑 Dialog 在 widget 内正常弹出
   - Logs filter 切换在 widget 内正常

### 关键文件参考
- 现有 Dashboard：`src/pages/Dashboard.tsx`（作为组装参考，不删除）
- 现有 Journal：`src/pages/Journal.tsx`
- 现有 Logs：`src/pages/Logs.tsx`
- 现有 SignalBoard：`src/components/features/dashboard/SignalBoard.tsx`（点击触发的地方需改为 `setSelectedSymbol`）
- 计划文档：`~/.claude/plans/tranquil-mixing-lollipop.md` Phase 3 章节

---

## 未决事项 / 风险

1. **SignalBoard onClick 改造**：原实现打开 `StockDetailModal`，widget 版本应改为 `setSelectedSymbol`。老 Dashboard 还在用 Modal，需兼容（或 Phase 4 同一起清）
2. **Journal/Logs widget 的响应式**：Table 在 widget 窄宽下可能挤压，需加横向滚动或精简列
3. **bundle size**：Phase 5 前必须 `React.lazy(Workbench)` code-split
4. **开发环境稳定性**：注意本地 uvicorn 要保持运行，别误关终端（已记录在踩坑段）

---

## 下一个 Session 继续指令

```
继续 workbench 重构 Phase 3：迁移 Watchlist/Journal/Logs/MarketOverview/QuickAdd 5 个 widget。
先读 SESSION-HANDOFF.md，然后按"Phase 3 任务"逐条执行。
```
