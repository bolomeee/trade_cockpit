# 验收记录：F105-a2 FMP 客户端扩展

**日期**：2026-04-21
**Sprint Contract**：docs/开发/sprint-contracts/F105-a2-contract.md
**Commit**：5b6d2af

## 技术门禁

- ✅ tests/test_fmp_client.py 36/36（含 a2 新增 10 条）
- ✅ backend/tests/ 全量回归 223/223
- ✅ 下游 F105-a3（scanner service）已基于 a2 完成并通过验收，反向佐证 a2 接口稳定

## 交付物核对

| 项 | 检查 | 结果 |
|---|---|---|
| 端点常量 | `FMP_EP_SCREENER=/company-screener`、`FMP_EP_SMA=/technical-indicators/sma` | ✅ |
| 方法 | `get_company_screener_page` / `get_screener_universe` / `get_sma_series` / `get_ma150_series_or_eod` | ✅ 全部存在 |
| fallback | 402/403/404 → EOD；500 透传 | ✅（单元测试覆盖）|
| config 字段 | `scanner_cron_hour=6 / scanner_cron_minute=15 / universe_cron_day=1 / universe_cron_hour=5 / universe_cron_minute=0` | ✅ 默认值与 ARCHITECTURE L215–219 一致 |
| .env.example | 5 条 cron env var 齐全 | ✅ |

## 过程备注

- Live smoke（需真实 FMP_API_KEY）未在本次 acceptance 再跑；a3 scanner 基于 a2 已通过完整扫描链路运行，等价佐证。
- a4 发布前发现 a2 一直挂 needs_review，本次统一收尾，无遗留改动。

## 结论

验收通过，phase → done。
