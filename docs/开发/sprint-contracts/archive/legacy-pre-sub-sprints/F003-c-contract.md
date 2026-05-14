---
feature: F003-c
name: Frontend TopNav Refresh Data 按钮 + 状态轮询
status: draft
created: 2026-04-17
---

# Sprint Contract：F003-c

## 1. 范围

### 包含
- 抽出 TopNav 共享组件，右侧放置 "Refresh Data" 按钮和 "Last refresh: …" 文案
- RefreshButton：默认态 / 加载中态（图标旋转 + 禁用）
- `lib/api/data.ts`：封装 `POST /api/data/refresh` 和 `GET /api/data/status`
- `useRefreshStatus` hook：
  - 点击按钮 → POST → 立即开始 2s 间隔轮询 status
  - status 转为 `completed`/`failed` 时停止轮询
  - 完成后 invalidate `['watchlist']` query，SignalBoard 自动刷新
  - 页面挂载时主动 GET 一次 status，读取 `lastRefreshedAt` 作为 TopNav 初始显示

### 排除
- MarketOverview 条（属于 F004）
- 进度百分比展示（本次只用按钮态 + "Last refresh"，不显示 completed/total）
- 失败态的 Toast/Banner（仅切回按钮默认态 + console.error；全局错误通知后续统一做）
- 前端单元测试（项目未配置 vitest；靠 preview_* 浏览器验证）

## 2. 预计修改文件（5 个）
- `frontend/src/lib/api/data.ts`（新建）
- `frontend/src/hooks/useRefreshStatus.ts`（新建）
- `frontend/src/components/features/topnav/TopNav.tsx`（新建）
- `frontend/src/components/features/topnav/RefreshButton.tsx`（新建）
- `frontend/src/App.tsx`（修改：用 `<TopNav />` 替换内联 `<nav>`）

## 3. 完成标准

| # | 标准 | 测试层级 | 工具 |
|---|------|---------|------|
| 1 | TopNav 右侧展示 "Last refresh: HH:MM:SS AM" + Refresh Data 按钮（设计规格：32px 高、pill、lucide `RefreshCw` 图标） | 视觉 | preview_screenshot |
| 2 | 点击按钮 → POST /api/data/refresh 返回 202，按钮图标旋转 + 禁用 | 交互 | preview_click + preview_network |
| 3 | 点击后每 2s 轮询 GET /api/data/status；status=`in_progress` 时按钮保持旋转 | 交互 | preview_network |
| 4 | status=`completed` → 停止轮询，按钮恢复默认态，"Last refresh" 更新为最新时间 | 交互 | preview_snapshot + preview_network |
| 5 | 完成后 SignalBoard 重新 fetch `/api/watchlist`（react-query invalidate 可见于 network） | 集成 | preview_network |
| 6 | 轮询中重复点击按钮，返回 `status: "in_progress"` 被忽略（不发重复 POST） | 交互 | preview_click + preview_network |
| 7 | 初次进入页面，TopNav 先 GET /api/data/status 读取 `lastRefreshedAt` 展示；值为 null 时显示 "Last refresh: —" | 视觉 | preview_snapshot |
| 8 | 颜色 / 字号只用 tokens.css 变量，无硬编码 | 代码 | 阅读 |
| 9 | 现有路由跳转（Dashboard / Journal / Logs 激活态）行为不变 | 回归 | preview_click |
| 10 | `pnpm lint` + `pnpm build` 无新增 warning/error | 代码 | CLI |

## 4. Evaluator 自检清单

- [ ] 5 个预计文件以内
- [ ] 按钮默认 / loading / 悬停 态视觉对齐 design-spec 第 28–40 行
- [ ] 图标来自 `lucide-react`（`RefreshCw`），旋转用 Tailwind `animate-spin`
- [ ] `useRefreshStatus` 在 status 变成 completed 时清理轮询 timer（无泄漏）
- [ ] `useRefreshStatus` 使用 react-query 的 `queryClient.invalidateQueries`，不手动 refetch
- [ ] POST 发起时按钮立即禁用（不等响应），响应失败时恢复按钮 + console.error
- [ ] `/status` 响应字段 camelCase 读取（`lastRefreshedAt` / `jobId`）
- [ ] App.tsx nav 抽离后，三个链接激活态配色依然读自 `--color-nav-active` 等 token
- [ ] `pnpm lint` 无新增问题
- [ ] `pnpm build` 成功
- [ ] 浏览器回归：Journal / Logs 页面打开无报错

## 5. 非目标 / 风险
- **轮询 interval 硬编码 2s**：不做配置化；后续如需改为 SSE/WebSocket 再讨论。
- **TopNav 仅布局，不承担 MarketOverview**：F004 单独实现。
- **按钮在"刷新完成"瞬间的视觉过渡**：spec 未要求动画，直接切回默认态。
