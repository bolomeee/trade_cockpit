# SESSION-HANDOFF.md

> 生成时间：2026-04-19
> 当前分支：`feat/workbench-refactor`
> 刚完成：**Phase 4（根路由切换 + 清理老 pages + TopNav 简化）+ widget UI 精修 + 搜索修复 + Fundamentals 重设计 + ChartWidget 标题**
> 用户已验收 ✅
> 下一步：Phase 5（`React.lazy` code-split → CHANGELOG → 合 main → tag v1.1.0）

---

## 本 Session 完成的内容

### 1. Phase 4：路由切换 + 清理
- `App.tsx`：`/` → Workbench（取代 Dashboard），移除 `/workbench` 临时路由；ResetLayoutButton 条件改为 `pathname === '/'`；`/journal` `/logs` 独立页保留
- 删除：`pages/Dashboard.tsx`、`stock-detail/StockDetailModal.tsx`、`stock-detail/StockDetailHeader.tsx`、`workbench/widgets/JournalWidget.tsx`、`workbench/widgets/LogsWidget.tsx`
- `WidgetRegistry.ts`：移除 `journal.list` / `logs.list`；`WidgetCategory` 去 `'logs'`，保留 `'sma150' | 'journal'`
- `useLayoutStore` persist key `v4 → v5`
- `TopNav`：`NAV_LINKS` 移除 Dashboard 链接，保留 Journal / Logs

### 2. Widget UI 精修
- `WidgetShell.tsx`：handle 条保留 widget 标题文本（之前误删已恢复）+ 右侧关闭按钮
- **各 widget 内部去重复 card 包装 + 去重复标题**：
  - `FundamentalsCard.tsx`：去 card 外壳 + 去 "Fundamentals" h3 + 去 Mock Data badge
  - `PullbackHistoryCard.tsx`：去 card 外壳 + 去 "Pullback History" h3
  - `JournalQuickAddCard.tsx`：去 card 外壳 + 去 "Trade Journal" h3
  - `AddStockCard.tsx`：去 card 外壳 + 去 "Add Stock" h3
- **WatchlistWidget**：改用 shadcn `Table`（Ticker / Name / Signal / Close / % MA150 / 删除列），替代原来的 SignalBoard 卡片网格
- 新增 `components/ui/table.tsx`（`pnpm dlx shadcn@latest add table`）
- 删：`SignalBoard.tsx`、`SignalCard.tsx`（无引用）

### 3. AddStock 搜索修复（root cause）
- **症状**：输入 "O" / "OXY" / "orcl" 搜不到 OXY / Oracle
- **根因**：Polygon `search=` 参数是 ticker/name 子串匹配但按 ticker 字母排序，首页 10 条全是 A 开头 ETF
- **修复** `backend/app/external/polygon_client.py::search_tickers`：
  - 先 ticker 前缀匹配（`ticker_gte=Q, ticker_lt=_next_prefix(Q)`）
  - 空结果时 fallback 到 `search=Q`（覆盖按公司名搜索）
  - 新增 `_next_prefix` 工具
- 前端 `AddStockCard.tsx`：去掉 `onKeyDown` Enter 触发，改 `useEffect` + 200ms debounce 实时搜索；placeholder 改 `Search ticker or name (e.g. OXY)`

### 4. Fundamentals widget 重设计
- 用户要求：双列 shadcn Table，每列 "metric name"（左对齐）+ "metric value"（右对齐）；P/E, P/S, PEG, ROCE, FCF
- `FundamentalsCard.tsx`：2-col grid，左列 [P/E, P/S, PEG]，右列 [ROCE, FCF]
- 前端 `Fundamentals` 类型新增 `roce?: number | null`
- ROCE 真实算法 = EBIT / (Total Assets − Total Current Liabilities)，**延至 F103 真实财报接入**；当前后端 `_mock_fundamentals` 加 sha1 衍生的 mock ROCE（0.05–0.40 / 5%–40%）
- `backend/app/schemas/stock_detail.py`：Fundamentals 加 `roce: float | None = None`

### 5. ChartWidget 标题 overlay
- 图表左上角 overlay ticker（18px bold）+ 公司名（14px regular 灰色）
- 公司名从已缓存的 `getSignals` query 匹配，零额外 API 调用
- `pointer-events: none` 不挡图表交互

### 6. 文档
- **DECISIONS.md 新增 2 条**：
  - **D032** Fundamentals 维持 mock + ROCE mock 占位 + 真实财报延至 F103
  - **D033** 非 watchlist ticker 的 chart preview 延到首个"含外部 ticker 的 widget"立项时设计
- **features.json**：
  - F101 → `done`；F102 → `needs_review`
  - 新增 **F103**（P1, `design_needed`）Fundamentals 真实财报接入

---

## 当前状态

### Pipeline
| 阶段 | 状态 |
|------|------|
| Phase 0–3.5 | ✅ done（历史） |
| Phase 4 路由切换 + 清理 + UI 精修 | ✅ done（用户已验收） |
| Phase 5 code-split + v1.1.0 tag | ⬜ next |

### features.json
| Feature | phase |
|---------|-------|
| F100 Workbench 框架 | `done` |
| F101 SMA150 widget 迁移 | `done` |
| F102 路由切换 + 清理 | `needs_review` → 下次 session commit 后可 `done` |
| F103 Fundamentals 真实财报接入 | `design_needed`（新增，v1.1.0 后排期） |

### 环境快照
- git branch：`feat/workbench-refactor`；本 session 全部改动**未 commit**（下一步应分 3–4 个逻辑 commit 再发版）
- localStorage key：`ma150.workbench.layouts.v5`
- 路由：`/` (Workbench) / `/journal` / `/logs`
- Workbench 默认 5 widget：Chart / Fundamentals / Pullback / Watchlist / QuickAdd
- backend Fundamentals 全 mock，`roce` 5%–40% 范围随机；source 字段 `"mock"`

---

## 下一步 Phase 5 任务

1. **commit 分组**（本 session 未 commit）
   建议：
   - `refactor(workbench): phase 4 - / → Workbench, drop Dashboard/Modal, trim TopNav`
   - `refactor(widgets): drop duplicate card wrappers + titles, switch watchlist to shadcn table`
   - `fix(search): polygon ticker prefix match + live debounce`
   - `feat(fundamentals): 2-col table layout + mock ROCE + chart widget header`
   - `docs: add D032/D033, feature F103`
2. **浏览器验收**：`pnpm dev` 走一遍（默认 5 widget 可见 / Watchlist 点击联动 Chart+Fund+Pullback / AddStock 实时搜索 / QuickAdd → /journal 同步 / Reset Layout / /journal /logs 独立页）
3. **code-split**：`App.tsx` 用 `React.lazy(() => import('@/workbench/Workbench'))` + `Suspense`，目标 initial bundle < 500KB
4. **CHANGELOG.md** 写 v1.1.0 条目（走 project-commiter skill）
5. **features.json**：F102 → `done`；v1.1 iteration `status → done` + `released_tag: v1.1.0`
6. **合 main** + tag `v1.1.0`

---

## 未决事项 / 风险

1. **关闭 widget 的恢复**：仅 Reset Layout 全量恢复，无 picker。v1.2 再做
2. **bundle size**：Phase 5 `React.lazy` 后才低于 500KB
3. **F103（真实财报）**：v1.1.0 发版后评估优先级；ROCE 等 5 指标当前全 mock，用户已认可
4. **外部 ticker preview**：等首个含外部 ticker 的 widget（News/Scan/AI）立项时再决 UX（D033）

---

## 下一个 Session 继续指令

```
Phase 4 用户已验收。下一步：
1. 按 handoff 建议分 3–5 个 commit 打包
2. 浏览器走一遍验收清单
3. Workbench 做 React.lazy code-split
4. 走 project-commiter 发 v1.1.0（CHANGELOG + tag）
```
