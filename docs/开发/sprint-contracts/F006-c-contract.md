---
feature_id: F006-c
feature_name: MarketOverviewBar 前端组件
status: draft
created_at: 2026-04-17
---

# Sprint Contract：F006-c

## 范围

**本次包含**：
- `types/market.ts`：`MarketIndexItem`（camelCase 对齐后端）
- `lib/api/market.ts`：`getMarketOverview()`
- `hooks/useMarketOverview.ts`：react-query 包装，refresh 完成时失效缓存（与 watchlist/signals 一致）
- `MarketOverviewBar.tsx`：共享条，41.78px 高，三组指标（S&P 500 / NASDAQ 100 / 10Y Treasury），状态 loading / empty / error / normal
- `App.tsx`：TopNav 下方挂载，所有路由共享
- `useRefreshStatus.ts`：补一行 invalidateQueries `['market','overview']` 保持一致体验

**本次排除**：
- 历史数据折线（DATA-MODEL 只保留 5 天，MVP 不做趋势图）

## 预计修改文件（6 个）

- `frontend/src/types/market.ts`（新建）
- `frontend/src/lib/api/market.ts`（新建）
- `frontend/src/hooks/useMarketOverview.ts`（新建）
- `frontend/src/components/features/market-overview/MarketOverviewBar.tsx`（新建）
- `frontend/src/App.tsx`（修改）
- `frontend/src/hooks/useRefreshStatus.ts`（修改：invalidate market overview）

（刚好 6 个，贴限）

## 设计映射

- 高度：41.78px；背景 `--color-background`；下边框 `--color-border`
- 居中三组（gap 32px）；每组：`name` + `close` + `changePct%`
- changePct 颜色：>= 0 用 `--color-change-positive`，< 0 用 `--color-change-negative`
- 字号 `--font-size-market-bar`(14.4px)
- TNX 的 close 显示为 `x.xx%`（yield 本身是百分数），SPX/NDX 显示两位小数 `x,xxx.xx`
- changePct 统一 `+0.39%` / `-0.41%`（带正号和两位小数）
- 加载：三组各显示 `—`（灰 `--color-text-secondary`），不跳 Skeleton（条太薄）
- 错误：不渲染整条（fallback 返回 null），避免破坏顶部布局；console.error 已有
- 空表：三组显示 `—`（与 loading 一致）

## 完成标准

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| 1 | 组件 mount 后调用 `/api/market/overview` 一次 | 手动 | preview + DevTools Network |
| 2 | 正常数据三组按 SPX/NDX/TNX 展示，涨跌颜色对应 token | 视觉 | preview_screenshot |
| 3 | 负变化颜色为红 | 视觉 | preview_screenshot |
| 4 | 页面切换 `/ ↔ /journal ↔ /logs` 时 Bar 始终存在 | 手动 | preview_click |
| 5 | 数值格式：TNX 显示 `4.25%`，SPX 显示 `5,200.50` | 视觉 | preview_snapshot |
| 6 | 全量 tsc + eslint 无新 warning | 静态 | pnpm build / lint |

## Evaluator 自检清单

- [ ] 组件渲染正常 / loading / 错误三态可观察
- [ ] 样式全部走 tokens（无硬编码颜色/字号，仅 41.78px 高度硬编码）
- [ ] 字段命名对齐后端 camelCase
- [ ] 切换路由 Bar 不卸载重载（挂在 App 根部）
- [ ] 回归：watchlist / signals 行为未受影响
- [ ] tsc 通过
