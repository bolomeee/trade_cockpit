# 验收记录：F105-b /api/stocks/:ticker/chart on-demand fallback

**日期**：2026-04-21
**Sprint Contract**：docs/开发/sprint-contracts/F105-b-contract.md
**Commit**：c4077e3

## 决策收口

- 错误码：统一使用 `EXTERNAL_API_ERROR` (502)（方案 A，文档跟随现网代码）
- Fallback 触发：`stock is None` **或** `is_active=False` 均走（方案 B2）

## 技术门禁

- ✅ tests/test_stock_detail.py 16/16（原 12 + 新增 4 条 fallback 用例）
- ✅ backend/tests/ 全量回归 227/227
- ✅ mypy 目标文件无新增错误（仅 1 处 Column[date] 遗留，非本 Sprint 引入）

## 业务逻辑确认

| # | 场景 | 预期 | 结论 |
|---|---|---|---|
| V1 | watchlist active ticker 请求 chart | 原路径（本地 DailyBar + Signal + Pullback） | ✅ 既有 3 条测试未修改仍绿 |
| V2 | 不在表中 ticker 请求 chart | 200，fallback 返回 bars + ma150 + 空 pullbackMarkers | ✅ test_chart_fallback_for_unknown_ticker |
| V3 | inactive ticker 请求 chart（B2） | 200，fallback 返回 | ✅ test_chart_fallback_for_inactive_ticker |
| V4 | FMP 空返回 | 404 NOT_FOUND | ✅ test_chart_fallback_empty_fmp_returns_404 |
| V5 | FMP httpx.HTTPError | 502 EXTERNAL_API_ERROR | ✅ test_chart_fallback_fmp_http_error_returns_502 |
| V6 | fallback 路径 MA150 对齐 | 前 149 根不输出；ma150 长度 = bars 长度 - 149 | ✅ 测试中显式断言 |
| V7 | fallback 路径 bars 顺序 | date 升序（即使 FMP 返回倒序） | ✅ 测试中显式断言 |

## 过程备注

- 未手动 curl，采信 TestClient 集成测试（等价端到端）；FMP 外呼链路在 F001/F104 阶段已验过。
- 文档同步：API-CONTRACT.md L342、DECISIONS.md D041 错误码统一为 `EXTERNAL_API_ERROR`。

## 结论

验收通过，phase → done。
