# SESSION-HANDOFF.md

> 生成时间：2026-04-18
> 当前分支：`feat/workbench-refactor`
> 刚完成：**Phase 1（Widget 框架脚手架）**
> 下一步：Phase 2（迁移 StockDetailModal 拆解为 3 个独立 widget）

---

## 本 Session 完成的内容

### Phase 0（commit `681a988`）：文档对齐
- `CLAUDE.md`：阶段 → v1.0.0 ✅ → v1.1.0 Workbench 重构；新增"加新 widget 标准流程"
- `docs/需求/PRD.md`：前置 v1.1 Workbench vision 章节（widget 类别、新增用户旅程 D/E、明确不做清单）
- `docs/系统设计/ARCHITECTURE.md`：技术栈表加 react-grid-layout + zustand；新增 Workbench Widget Framework 章节（manifest 契约、层级、原则）
- `docs/系统设计/DECISIONS.md`：D029（框架选型）、D030（zustand 跨 widget store）、D031（拆解 StockDetailModal）
- `docs/设计/design-spec.md`：前置 v1.1 Workbench section（全局结构、网格规格、WidgetShell 契约、默认布局表、响应式）
- `docs/需求/features.json`：version 1.1.0-dev；v1.1 iteration_log；F100/F101/F102 三个新 feature

### Phase 1（commit 待打）：Widget 框架脚手架
- **技术选型验证（Spike）**：react-grid-layout 2.2.3 兼容 React 19（peerDep 为 React 18+）；v2 是 TS 重写版，API 从 flat props 变为 `gridConfig` / `dragConfig` 配置对象 + `useContainerWidth()` hook；`@types/react-grid-layout` deprecated，v2 自带类型；`react-resizable` 不再是依赖
- **新依赖**：`react-grid-layout@2.2.3` + `zustand@5.0.12`（已入 `package.json`）
- **新代码**：
  - `src/workbench/WidgetRegistry.ts`：manifest 类型 + `WIDGET_REGISTRY` 映射 + `getDefaultLayout()`；当前注册 3 个 demo widget 占位
  - `src/workbench/WidgetShell.tsx`：标准外壳（标题栏 36px 作 drag handle + 内容区 overflow-auto）
  - `src/workbench/Workbench.tsx`：`useContainerWidth` 测宽 + `ReactGridLayout` 渲染 + 从 registry 查组件渲染到 Shell 内
  - `src/workbench/useLayoutStore.ts`：zustand + persist 中间件，key `ma150.workbench.layouts.v1`，版本号 1
  - `src/workbench/widgets/DemoWidget.tsx`：读写 `useAppStore.selectedSymbol` 的占位 widget，验证跨 widget 联动
  - `src/store/useAppStore.ts`：zustand 全局 client state，`selectedSymbol` + `setSelectedSymbol`
- **路由**：`src/App.tsx` 新增 `/workbench` 临时路由，老路由 `/` `/journal` `/logs` **不动**
- **验收**：
  - `pnpm build` 零 TS 错误；bundle 768KB raw / 238KB gzip（超 500KB 阈值，Phase 5 前做 code-splitting）
  - 浏览器实测通过：3 个 demo widget 渲染、拖拽 + resize 工作、刷新页面位置保留、重置布局按钮生效

---

## 当前状态

### Pipeline
| 阶段 | 状态 |
|------|------|
| Phase 0 文档对齐 | ✅ done（`681a988`） |
| Phase 1 框架脚手架 | ✅ done（待 commit） |
| Phase 2 拆 StockDetailModal | ⬜ next |
| Phase 3 迁移列表 widget | ⬜ |
| Phase 4 路由切换 + 清理 | ⬜ |
| Phase 5 验收 + 发 v1.1.0 | ⬜ |

### features.json 状态
| Feature | phase |
|---------|-------|
| F100 Workbench 框架 | `in_progress`（Phase 1 完成即等价 F100 核心完成，Phase 2 起属 F101） |
| F101 SMA150 widget 迁移 | `design_needed` |
| F102 路由切换 + 清理 | `design_needed` |

### 环境快照
- git branch：`feat/workbench-refactor` · HEAD（待打）：Phase 1 commit · main 合入需等 Phase 5
- 后端：未改动，v1.0.0 所有 endpoint 继续工作；pytest 162/162 基线
- 前端：`cd frontend && pnpm dev` → localhost:5173；新路由 `/workbench` 可访问；老路由 `/` `/journal` `/logs` 不受影响
- localStorage key：`ma150.workbench.layouts.v1`（zustand persist，schema version 1）
- 已知非阻塞问题：
  - `pnpm lint` 有 2 个 pre-existing 问题（`button.tsx` fast-refresh、`JournalEntryForm.tsx` watch() compiler 警告），v1.0.0 就有，不是 Phase 1 引入
  - bundle 超 500KB 阈值，Phase 5 前需用 `React.lazy(Workbench)` code-split

---

## 下一步 Phase 2 任务

**目标**：把 StockDetailModal 拆成 3 个独立 widget（`ChartWidget` / `FundamentalsWidget` / `PullbackWidget`），从 `useAppStore.selectedSymbol` 读 ticker，各自 fetch 数据。WatchlistWidget 点击 → `setSelectedSymbol` → 3 widget 同步刷新。

### 需要做的事

1. **改造 `PriceChart`**（关键风险点）：
   - 去掉硬编码 `height: 302px`（在 `components/features/stock-detail/PriceChart.tsx`）
   - 用 `ResizeObserver` 监听父容器尺寸，调 `chart.applyOptions({ width, height })` 让 lightweight-charts 自适应
   - 验证：在 widget 被 resize 时 K 线图不截断、不溢出
2. **创建 3 个 widget**（`src/workbench/widgets/`）：
   - `ChartWidget.tsx`：从 `useAppStore` 读 selectedSymbol → 调现有 `useStockChart` hook（如有）或 `useQuery(['chart', symbol])` → 渲染改造后的 PriceChart
   - `FundamentalsWidget.tsx`：包 `FundamentalsCard`
   - `PullbackWidget.tsx`：包 `PullbackHistoryCard`
   - 各自处理 `selectedSymbol === null` 的空态："请在 Watchlist 中选择一只股票"
3. **注册到 `WidgetRegistry.ts`**，替换掉 demo.a/b/c
4. **验证**：
   - 在 `/workbench` 页面看到 3 个 widget 分别渲染
   - 手动调 `setSelectedSymbol('AAPL')`（临时加个按钮或通过 DemoWidget）→ 3 widget 同步拉数据
   - resize widget → K 线图正确重排

### 关键文件路径
- 改造：`frontend/src/components/features/stock-detail/PriceChart.tsx`
- 新增：`frontend/src/workbench/widgets/{ChartWidget,FundamentalsWidget,PullbackWidget}.tsx`
- 修改：`frontend/src/workbench/WidgetRegistry.ts`（删 demo、加 3 个 SMA150 widget）
- 保留：`components/features/stock-detail/{FundamentalsCard,PullbackHistoryCard}.tsx`（widget 直接包裹复用）

### 相关参考
- 计划文档：`~/.claude/plans/tranquil-mixing-lollipop.md` 的 Phase 2 章节
- Phase 0 定下的设计契约：`docs/系统设计/DECISIONS.md` D031（拆解理由）
- 现有 Modal 数据流：`frontend/src/components/features/stock-detail/StockDetailModal.tsx`（作为迁移来源参考，不删除）

---

## 未决事项 / 风险

1. **WatchlistWidget 联动尚未做**：Phase 2 暂只支持通过 DemoWidget 手动触发 `setSelectedSymbol`，真正把 SignalBoard 的 onClick 接到 store 要到 Phase 3 做 `WatchlistWidget` 时
2. **PriceChart 响应式改造的内部细节**：lightweight-charts 在 Dialog 里用 window resize listener（D025）；widget 里改成 ResizeObserver 时需重新验证；Phase 2 做完要在多种 widget 尺寸下测一轮
3. **bundle size**：248KB gzip 可接受但已超阈值，Phase 5 前必须做 code-split
4. **是否开 Phase 2**：可以立即开，也可以在 main 上先 cherry-pick 合并 F100 核心（当前 workbench 框架），然后再回 feat 分支做 F101/F102。默认继续留在 feat 分支一气呵成

---

## 下一个 Session 继续指令

```
继续 workbench 重构 Phase 2：改造 PriceChart 响应式 + 拆 StockDetailModal 为 3 个 widget。
先读 SESSION-HANDOFF.md，然后按"Phase 2 任务"逐条执行。
```
