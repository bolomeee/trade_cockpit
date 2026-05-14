---
feature: F005-a
name: 后端 stock detail 接口
status: contract_agreed
agreed_at: 2026-04-17
---

# F005-a Sprint Contract：后端 stock detail 接口

## 范围

**包含**：
- `GET /api/stocks/{ticker}/chart`：最近 250 日 OHLCV + 对齐 MA150 + pullbackMarkers
- `GET /api/stocks/{ticker}/pullbacks`：Pullback 详情，按日期倒序
- `GET /api/stocks/{ticker}/fundamentals`：Mock 基本面（source="mock"）
- 三接口统一 ticker 校验（不在 active watchlist → 404 NOT_FOUND）
- Pydantic schema、PullbackRepository、StockDetailService、集成测试

**排除**：前端组件（F005-b）、PriceChart 与 lightweight-charts（F005-c）、真实 Fundamentals 数据源

## 预计修改文件（5）

| 路径 | 动作 |
|------|------|
| backend/app/schemas/stock_detail.py | 新建 |
| backend/app/repositories/pullback_repository.py | 新建 |
| backend/app/services/stock_detail_service.py | 新建 |
| backend/app/routers/stocks.py | 修改，追加 3 路由 |
| backend/tests/test_stock_detail.py | 新建 |

## 关键实现约束

1. MA150 对齐：复用 `signals.ma150_value`，不重算
2. pullbackMarkers：从 `pullbacks` 表读，裁剪到 chart 窗口
3. Fundamentals：source="mock"，值可由 ticker 派生，updatedAt=today
4. camelCase 响应，复用现有 ResponseEnvelope + APIError

## 测试用例

| # | 验收点 | 层级 |
|---|--------|------|
| 1 | /chart 返回 bars 升序 + ma150 对齐 + pullbackMarkers | 集成 |
| 2 | /chart bars<150 时 ma150 为空列表 | 集成 |
| 3 | /chart 只返回最近 250 日 | 集成 |
| 4 | /pullbacks 按日期倒序，return_30d 可 null | 集成 |
| 5 | /fundamentals 返回 mock 数据 | 集成 |
| 6 | ticker 不存在 → 404 NOT_FOUND | 集成 |
| 7 | ticker 存在但 is_active=False → 404 | 集成 |
| 8 | 响应字段严格对齐 API-CONTRACT | 集成 |
| 9 | PullbackRepository.list_by_stock 单元 | 单元 |

## Evaluator 自检

- [ ] 9 条测试全过
- [ ] 全量 pytest 无新增失败
- [ ] API 响应对照 API-CONTRACT.md L290-L394
- [ ] ORM 字段与 DATA-MODEL.md 一致
- [ ] 无硬编码魔法值（250/150 为常量）
- [ ] 无死代码
