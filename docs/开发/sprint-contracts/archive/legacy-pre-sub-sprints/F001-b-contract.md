# Sprint Contract：F001-b Frontend Watchlist 读取展示

**Feature**：F001-b
**日期**：2026-04-17
**前置**：F001-a ✅（`GET /api/watchlist` 已就绪，38 个测试通过）
**新依赖**：`@tanstack/react-query`（用户 2026-04-17 批准）

---

## 范围

### 包含
- 安装 `@tanstack/react-query`，在 `main.tsx` 接入 `QueryClientProvider`
- `lib/api/client.ts`：原生 `fetch` 封装，统一解析 `{ data, error }` 响应格式
- `lib/api/watchlist.ts`：`getWatchlist()` 类型安全调用
- `types/watchlist.ts`：`WatchlistItem` / `LatestSignal` TypeScript 类型（对齐 API-CONTRACT camelCase）
- `SignalBadge`：5 状态（BREAKOUT / BUY_ZONE / NEUTRAL / INSUFFICIENT / null→INSUFFICIENT），只用 `--color-signal-*` token
- `SignalCard`：展示 ticker / name / price / distance / SignalBadge；`latestSignal === null` 时 price/distance 显示 `—`
- `SignalBoard`：grid 3列（desktop）→ 2列（tablet）→ 1列（mobile），按 signal 优先级排序（BREAKOUT > BUY_ZONE > NEUTRAL > INSUFFICIENT）
- `EmptyState` / `ErrorState`：全局通用组件
- `Dashboard.tsx`：接入 `useQuery(['watchlist'])`，切换 loading / empty / error / ready 四种状态
  - loading：4 个 Skeleton 占位（同 SignalCard 尺寸）
  - empty：EmptyState，文案"还没有自选股，从右侧 Add Stock 开始吧"
  - error：ErrorState，文案"数据加载失败"+ 重试按钮
  - ready：SignalBoard

### 排除
- AddStockCard / 搜索框 / POST /api/watchlist（F001-c）
- 删除交互（F001-c）
- TopNav / MarketOverviewBar（F003 / F006）
- 点击 SignalCard 打开 Modal（F005）
- 真实信号数据（F002 未做，latestSignal 目前始终 null）
- Vitest 自动化测试（未配置，超出本次范围）

---

## dataStatus 可视化规则

| dataStatus | latestSignal | SignalBadge 显示 |
|------------|-------------|----------------|
| `"loading"` | null | INSUFFICIENT |
| `"insufficient"` | null | INSUFFICIENT |
| `"ready"` | 有值 | 按 signalType |

---

## 预计修改文件（10 个，F001-a 协商时已批准例外）

| 文件 | 操作 |
|------|------|
| `frontend/src/lib/api/client.ts` | 新建 |
| `frontend/src/lib/api/watchlist.ts` | 新建 |
| `frontend/src/types/watchlist.ts` | 新建 |
| `frontend/src/components/features/dashboard/SignalBoard.tsx` | 新建 |
| `frontend/src/components/features/dashboard/SignalCard.tsx` | 新建 |
| `frontend/src/components/features/dashboard/SignalBadge.tsx` | 新建 |
| `frontend/src/components/common/EmptyState.tsx` | 新建 |
| `frontend/src/components/common/ErrorState.tsx` | 新建 |
| `frontend/src/pages/Dashboard.tsx` | 修改 |
| `frontend/src/main.tsx` | 修改 |

---

## 完成标准

| # | 标准 | 验证方式 |
|---|------|---------|
| 1 | Watchlist 为空时，Dashboard 显示 EmptyState | 手验：GET /api/watchlist 返回 [] |
| 2 | Loading 状态显示 4 个 Skeleton | 手验：Network throttle / 断开后端 |
| 3 | 错误状态显示 ErrorState + 重试按钮，重试成功后恢复 ready | 手验：停止后端服务 → 点重试 |
| 4 | Ready 状态：AAPL 卡片显示 ticker/name/INSUFFICIENT Badge | 手验：已添加 AAPL 的环境 |
| 5 | SignalBadge 颜色严格使用 --color-signal-* token，无硬编码 hex | 代码审查 |
| 6 | 响应式：Desktop 3列 / Tablet 2列 / Mobile 1列 | 浏览器 DevTools 调整宽度 |
| 7 | pnpm build 无 TypeScript 错误 | 运行 pnpm build |

---

## Evaluator 自检清单

- [ ] GET /api/watchlist 请求路径正确（/api/watchlist，非 /watchlist）
- [ ] 4 种状态全部可视触发
- [ ] SignalBadge 无硬编码颜色值
- [ ] QueryClientProvider 已包裹根组件
- [ ] pnpm build 通过（零 TS 错误）
- [ ] console 无红色 error
- [ ] useQuery staleTime 设置为 30s（与 component-plan.md 一致）
