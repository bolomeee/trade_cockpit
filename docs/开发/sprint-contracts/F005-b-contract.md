---
feature: F005-b
name: 前端 Header/Pullback/Fundamentals + Modal 改造（移入 stock-detail/）
status: contract_agreed
agreed_at: 2026-04-17
---

# F005-b Sprint Contract

## 范围

- 将 StockDetailModal 从 dashboard/ 移到 stock-detail/（选项 B）
- 新子组件：StockDetailHeader、PullbackHistoryCard、FundamentalsCard
- Modal 改造：react-query 并发拉 signals/pullbacks/fundamentals；4 种状态
- PriceChart 留 Skeleton 占位，F005-c 接入

## 文件（8，含 2 结构移动）

| 路径 | 动作 |
|------|------|
| frontend/src/types/stockDetail.ts | 新建 |
| frontend/src/lib/api/stocks.ts | 修改（+3 fetch）|
| frontend/src/components/features/stock-detail/StockDetailModal.tsx | 新建 |
| frontend/src/components/features/stock-detail/StockDetailHeader.tsx | 新建 |
| frontend/src/components/features/stock-detail/PullbackHistoryCard.tsx | 新建 |
| frontend/src/components/features/stock-detail/FundamentalsCard.tsx | 新建 |
| frontend/src/pages/Dashboard.tsx | 修改（import 路径）|
| frontend/src/components/features/dashboard/StockDetailModal.tsx | 删除 |

## 约束

1. react-query useQueries，key 对齐 component-plan L222-L225
2. 4 状态：正常 / 加载 Skeleton / 部分错误（单卡 ErrorState）/ INSUFFICIENT（—）
3. Fundamentals Mock Badge 始终显示（source="mock"）
4. tokens-only，无硬编码
5. camelCase 字段

## 验收用例（preview_* 手动验证 + build/lint 门禁）

| # | 验收点 |
|---|--------|
| 1 | 打开 Modal 时并发请求 3 接口 |
| 2 | 正常数据：Header 4 指标 / Pullback Table / Fundamentals 4 指标 |
| 3 | 加载态：全部 Skeleton |
| 4 | 单接口失败：只该卡 ErrorState，其它正常 |
| 5 | INSUFFICIENT：Distance/MA150/Slope=— + Pullback 空态 |
| 6 | X/ESC/backdrop 关闭 Modal |
| 7 | Fundamentals Mock Badge 可见 |
| 8 | dashboard/StockDetailModal.tsx 已删除，Dashboard import 自 stock-detail/ |

## Evaluator 自检

- [ ] pnpm build 通过
- [ ] pnpm lint 无新增 warning
- [ ] preview 手动覆盖 8 用例
- [ ] 样式全走 tokens
- [ ] 无死代码 / console 残留
- [ ] PriceChart 区域留 Skeleton 占位（标 F005-c）
