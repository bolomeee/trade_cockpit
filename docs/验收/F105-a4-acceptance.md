# 验收记录：F105-a4 GET /api/market/breakouts

**日期**：2026-04-21
**Sprint Contract**：docs/开发/sprint-contracts/F105-a4-contract.md
**Commit**：4e78dd0

## 技术门禁

- ✅ tests/test_market_api.py 9/9 通过（含新增 5 条）
- ✅ backend/tests/ 全量回归 223/223 通过
- ✅ mypy 目标文件（routers/market.py、schemas/market.py）0 错
- ✅ Sprint Contract 自检清单全部打勾

## 业务逻辑确认

| # | 检查项 | 结论 |
|---|---|---|
| V1 | 响应外层 `{data, message:"success"}` | ✅（test_breakouts_response_envelope_shape）|
| V2 | data 顶层字段 `{scanDate, scannedAt, items, total}` | ✅ |
| V3 | items[] 字段集 camelCase | ✅（test_breakouts_returns_latest_snapshot_sorted_asc）|
| V4 | 价格字段 2 位小数 | ✅（test_breakouts_rounds_prices_to_two_decimals）|
| V5 | marketCap 整数 | ✅ |
| V6 | 空态 `scanDate/scannedAt=null` | ✅（test_breakouts_empty_returns_null_scan_date）|
| V7 | 多 scan_date 时只返回最新 | ✅（test_breakouts_only_latest_scan_date）|

## 过程备注

- curl :8000 初次 404，根因：宿主机 :8000 被另一项目 `cuotiben_backend` 占用；stock_portal-backend 容器未映射端口。非代码问题。
- 5 条集成测试覆盖了全部 acceptance_criteria，采信 pytest 结果直接通过。

## 结论

验收通过，phase → done。
