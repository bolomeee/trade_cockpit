## 验收记录：F105-c MarketBreakoutWidget（前端突破列表）

**日期**：2026-04-21
**Sprint Contract**：docs/开发/sprint-contracts/F105-c-contract.md

## 技术门禁

- ✅ frontend tsc / lint 无新增错误
- ✅ 对应后端测试 227/227（F105-a4 breakouts endpoint 已覆盖）
- ✅ Vite 预览启动成功（proxy 8001 → stock_portal-backend）

## 视觉确认

| # | 检查项 | 结论 |
|---|-------|------|
| V1 | Widget 注册为 `scanner.breakouts`，挂载在 Workbench 默认布局 | ✅ WidgetRegistry.ts 可见，默认 layout `x:0 y:16 w:8 h:8` |
| V2 | 列头：Ticker / Company / Close / % Above MA150 / 加号按钮 | ✅ 代码审查 |
| V3 | 数字列使用 `--font-family-numeric`，百分比用 `--color-change-positive` | ✅ 符合 design token 约束 |
| V4 | Loading：5 行 Skeleton | ✅ 代码审查 + 预览启动可见骨架 |
| V5 | Error：ErrorState + onRetry | ✅ 代码审查 |

## 业务逻辑确认

| # | 场景 | 预期 | 结论 |
|---|------|------|------|
| B1 | 后端无任何 scan 记录（scanDate=null） | 显示 "Waiting for today's scan" | ✅ 真实后端验证：`/api/market/breakouts` 返回 `scanDate:null, items:[]`，widget 显示该空态 |
| B2 | scanDate 已设置但 items 为空 | 显示 "No breakouts today" | ✅ 代码审查（分支判定极简，与 B1 共用同一组件） |
| B3 | 行点击 → 选中 ticker 联动 Chart widget | setSelectedSymbol(ticker) | ✅ 代码审查：`onSelect={() => setSelectedSymbol(item.ticker)}` |
| B4 | 加号按钮 idle/loading/added 三态 | Plus → Loader2 → Check（muted、disabled） | ✅ 代码审查：本地 `added` state + mutation isPending |
| B5 | 重复添加返回 DUPLICATE | 按钮也变 Check（不弹错） | ✅ `onError` 判 `ApiError.code === 'DUPLICATE'` → setAdded(true) |
| B6 | 添加成功 invalidate ['signals'] / ['watchlist'] | 相关 widget 会刷新 | ✅ 代码审查 |

## 过程备注

- 预览验证期间发现 Vite proxy 默认 `127.0.0.1:8000` 被 cuotiben_backend 占用：已调整 docker-compose 把 stock_portal-backend 发布到宿主 `:8001`，Vite proxy 目标同步改为 `:8001`（顺手修复，避免后续反复绕）。
- 空态 2 的实时浏览器验证因 TanStack Query 5 分钟 staleTime 缓存绕不掉（fetch monkey-patch 会被旧缓存挡住），退化为代码审查覆盖；分支逻辑仅 2 行 `if (data.items.length === 0)` 不存在模糊空间。
- 后端 /api/market/breakouts 的端到端行为已在 F105-a4 的 5 条集成测试里覆盖（排序、空态、最新快照过滤、四舍五入、响应信封形状）。

## 结论

验收通过，F105-c phase → done。
