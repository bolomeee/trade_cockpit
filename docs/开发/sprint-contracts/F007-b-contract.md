---
feature_id: F007-b
feature_name: 交易日志 Journal — 前端列表 + 筛选 + 删除
status: done
created_at: 2026-04-17
completed_at: 2026-04-17
---

# Sprint Contract：F007-b

## 范围

**本次包含**：
- `types/journal.ts`：`Action` / `JournalEntry` / `JournalListResponse` 类型
- `lib/api/journal.ts`：`getJournal(filter)` / `deleteJournal(id)`；基于现有 apiFetch
- `pages/Journal.tsx`：替换占位；react-query 拉数据、管理 filter 与删除流程
- `components/features/journal/ActionBadge.tsx`：5 枚举 → `--color-action-*` token
- `components/features/journal/JournalTable.tsx`：Table 渲染 + Row 展开（Row 内联在本文件）+ 空/加载/错误三态 + 每行 Delete icon
- `components/features/journal/JournalFilterCard.tsx`：Ticker / Action 两个受控 Select + Clear Filters

**本次排除**：
- `+ New Entry` 按钮（渲染但禁用，F007-c 接入）
- Edit icon（F007-c 接入）
- JournalEntryDialog / JournalEntryForm（F007-c）
- Dashboard JournalQuickAddCard（F007-d）
- 新增 shadcn 基础组件（select/label），F007-c 再引入；本 Sprint 的 FilterCard 用原生 `<select>` 配合 tokens 样式，保持最小依赖

**设计偏离声明（本 Sprint 内）**：
- FilterCard 的 Ticker / Action 下拉：design-spec 描述 shadcn Select，本 Sprint 降级为原生 `<select>`。偏离将在本 Sprint 结束时回写 design-spec（偏离块），待 F007-c 正式引入 shadcn Select 后可替换。

## 预计修改文件（6 个）

- `frontend/src/types/journal.ts`（新建）
- `frontend/src/lib/api/journal.ts`（新建）
- `frontend/src/pages/Journal.tsx`（重写）
- `frontend/src/components/features/journal/ActionBadge.tsx`（新建）
- `frontend/src/components/features/journal/JournalTable.tsx`（新建，含 Row）
- `frontend/src/components/features/journal/JournalFilterCard.tsx`（新建）

## 数据流

```
Journal.tsx
  ├── useQuery(['journal'])          → getJournal() 全量拉取
  ├── useMemo filter(ticker/action)  → 前端过滤（设计指定）
  ├── useMutation deleteJournal      → 成功后 invalidate ['journal']
  └── AlertDialog（shadcn，已存在）   → 删除二次确认
```

tickerOptions 从 `useQuery(['watchlist'])` 去重得到。

## 接口对齐

- `GET /api/journal` 返回 `{ items, total, limit, offset }`；MVP 场景全量拉（不分页）
- `DELETE /api/journal/:id` 返回 `{ id, deleted }`；失败抛 ApiError

## 完成标准

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| 1 | /journal 页面成功拉数据后渲染 TopNav + MarketOverviewBar（共享）+ HeaderRow + FilterCard + Table | E2E 视觉 | preview |
| 2 | Table 行按 date DESC 排序；显示 Date / Ticker(粗) / ActionBadge / Price / Position(右对齐，null→"—") | E2E 视觉 | preview |
| 3 | ActionBadge 5 枚举颜色分别等于 --color-action-* token 值 | 手动 | preview_inspect |
| 4 | Row chevron 展开后显示 Reason / Reference / Stop Loss / Target Price；再次点击折叠 | E2E 交互 | preview_click |
| 5 | 空状态：无记录时 Table 区显示 EmptyState（复用 common/EmptyState） | 视觉 | preview |
| 6 | 加载状态：请求中 Table Card 内 5 行 Skeleton | 视觉 | preview |
| 7 | 错误状态：mock 失败时显示 ErrorState + Retry，点击 Retry 调 refetch | 交互 | preview |
| 8 | FilterCard：Ticker Select 选项 = watchlist 去重 ticker；Action Select 含 All + 5 枚举 | 交互 | preview_click |
| 9 | Filter 选中后 Table 即时过滤；Clear Filters 还原 | 交互 | preview_click |
| 10 | Delete icon 点击 → AlertDialog 二次确认 → 确认后 DELETE 调用 → 行消失 | 交互 | preview_click |
| 11 | + New Entry 按钮渲染，disabled（F007-c 才启用） | 视觉 | preview |
| 12 | 无 TS 错误，pnpm build 通过 | 构建 | pnpm build |

## Evaluator 自检清单

- [ ] 全部 12 条完成标准通过
- [ ] 颜色/间距/字号全部使用 tokens.css 变量，无硬编码
- [ ] 字段名严格 camelCase，匹配 API-CONTRACT
- [ ] 组件职责边界匹配 component-plan（Table 不获取数据，Page 拉数据并管理 Dialog/Delete）
- [ ] 无 console.error / console.warn 残留
- [ ] 函数 ≤ 50 行，无死代码，无重复逻辑
- [ ] 设计偏离（原生 select）已在 design-spec.md 对应章节追加偏离块
- [ ] pnpm build 通过，全量前端 lint 无新增 warning
- [ ] 回归：Dashboard / Stock Detail 等既有功能不受影响（通过 preview 快速巡检）

## 风险 / 注意

- **tickerOptions 数据源**：页面同时发两个 query（journal + watchlist），watchlist 在多页共享缓存，无性能问题
- **AlertDialog**：已存在 `components/ui/alert-dialog.tsx`，直接使用
- **Position 单位**："股数"，用户可自行心算成本；不在本 Sprint 做 price × qty
- **Row 内联**：按 6 文件上限要求，JournalRow 不单开文件，作为 JournalTable 的内部子组件
