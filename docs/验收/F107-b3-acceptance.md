# 验收记录 — F107-b3 Fundamentals 增加 Float 绝对值显示

**日期**：2026-04-22
**Sprint Contract**：[F107-b3-contract.md](../开发/sprint-contracts/F107-b3-contract.md)
**Commit**：8ff7f7c `feat(F107-b3): /fundamentals + FundamentalsCard 增 sharesFloat`

## 结论

✅ **通过**。视觉、业务逻辑、边缘情况全部确认通过。

## 已确认项

### 视觉
- FundamentalsCard 仍是左右两列；右列顺序 ROCE → FCF → Float
- Float 单位 `14.66B`（AAPL 实测），格式 B 大写 / 2 位小数 / 无 `$`
- 数值字体加粗 + 右对齐，与其他指标同款 numeric font
- loading 时复用 Skeleton 占位

### 业务逻辑
- `GET /api/stocks/AAPL/fundamentals` 顶层返回 `sharesFloat: 14664480994`
- 24h 内重复请求命中 DB 缓存，无 FMP 调用（集成测试覆盖）
- DB miss 触发 FMP `/stable/shares-float` 回源并写回 stocks 表（集成测试覆盖）
- 同一 ticker 的 /chart + /fundamentals 共享同一 `stocks.shares_float` 缓存项

### 边缘情况
- FMP 调用失败 → sharesFloat = null，/fundamentals 仍 200（F107-b1 已建好该兜底路径）
- 非 watchlist / inactive ticker → null（D054，F108 再放开 on-demand）

## 测试结果
- 后端：`pytest tests/test_stock_detail.py -k fundamentals` → 6/6 通过
- 后端全量回归：264 通过 / 2 失败（pre-existing，F108 部分工作引入的 pullbacks 404→200，与 b3 无关）
- 前端 `pnpm build` → 通过（188ms）
- E2E 浏览器实测：AAPL 显示 `Float 14.66B`，无 console.error

## 关联变更
- API-CONTRACT.md：/fundamentals 字段表 + 响应示例追加 sharesFloat
- DECISIONS.md：D054 新增（fundamentals 复用 F107-b1 缓存路径）
