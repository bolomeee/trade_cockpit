---
feature: F004
name: 信号总览 SignalBoard
phase: contract_agreed
agreed_at: 2026-04-17
---

# F004 Sprint Contract

## 范围

**包含**：
- 前端 `GET /api/signals` API 客户端 + 类型（`SignalBoardItem`）
- SignalBoard 切换数据源到 `/api/signals`（符合 API-CONTRACT 约定），删除掉对 `/api/watchlist` 的依赖
- SignalCard 补充 closePrice 展示（design-spec §SignalCard line 70）
- 点击 SignalCard → 打开 `StockDetailModal`（最小壳：Header ticker + Badge + 公司名 + 4 指标占位；内容留 F005 填充）
- Modal 不改变 URL（纯本地 state）
- 移动端响应式验证（已有 grid-cols-1 / md:2 / lg:3）

**排除**：
- Modal 内的 PriceChart / PullbackHistory / Fundamentals（F005）
- `/api/signals/:ticker`、`/api/stocks/:ticker/chart` 等详情接口调用（F005）
- 删除交互调整（F001-c 已实现，保留原样；delete 成功后 invalidate `['signals']` + `['watchlist']`）

## 预计修改文件（6 个）

1. `frontend/src/types/signal.ts` — 新建
2. `frontend/src/lib/api/signals.ts` — 新建
3. `frontend/src/components/features/dashboard/SignalBoard.tsx` — 修改
4. `frontend/src/components/features/dashboard/SignalCard.tsx` — 修改
5. `frontend/src/components/features/dashboard/StockDetailModal.tsx` — 新建
6. `frontend/src/pages/Dashboard.tsx` — 修改

## 完成标准

| # | 标准 | 层级 |
|---|------|------|
| 1 | `GET /api/signals` 返回按优先级排序的列表，前端直接渲染 | 集成 |
| 2 | SignalCard 显示 ticker / 公司名 / closePrice / distance / SignalBadge，Price 用 numeric font | 单元 |
| 3 | 4 种信号（BREAKOUT/BUY_ZONE/NEUTRAL/INSUFFICIENT）颜色正确 | 单元 |
| 4 | 排序：BREAKOUT → BUY_ZONE → NEUTRAL → INSUFFICIENT | 单元 |
| 5 | 点击 SignalCard 打开 Modal，Modal 显示 ticker 的 header；URL 不变 | E2E |
| 6 | 关闭 Modal（X + backdrop + ESC）正常 | E2E |
| 7 | 删除按钮仍可用且阻止事件冒泡 | 手动/RTL |
| 8 | 移动端（<768px）1 列布局 | 视觉 |
| 9 | 空/加载/错误状态不回归 | E2E |
| 10 | `/api/signals` 失败时显示 ErrorState + 重试 | 集成 |

## Evaluator 自检清单

- [ ] frontend 单元测试通过（pnpm test）
- [ ] 无 console.error / TS 报错
- [ ] 字段命名对齐 API-CONTRACT
- [ ] 颜色/字号仅用 tokens.css 变量
- [ ] Modal 不改 URL
- [ ] 移动端 SignalBoard 1 列、桌面 3 列
- [ ] Lint pass；无死代码、无魔法值
- [ ] 回归：F001/F002/F003 功能仍正常
