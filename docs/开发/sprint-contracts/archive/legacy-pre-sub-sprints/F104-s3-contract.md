# Sprint Contract：F104-S3 Fundamentals 真实接入（D035 扩展）

> 日期：2026-04-19 | 状态：待确认
> 引用：F104-s1/s2/s2c | DECISIONS D034（数据源迁移 FMP）、D035（ratios-ttm 字段错位，需补 key-metrics-ttm）

---

## 本次实现范围

**包含**：
1. `FmpClient` 新增 `get_key_metrics_ttm(symbol)` 方法，命中 `/stable/key-metrics-ttm`
2. `StockDetailService.get_fundamentals` 去 mock，合并 `key-metrics-ttm` 为主（估值/回报/FCF/marketCap）+ `ratios-ttm` 辅助（若 key-metrics-ttm 缺字段兜底）的真实接入；`source` 改为 `"fmp"`
3. `stocks` router 将 `FmpClient` 注入 `StockDetailService`
4. `schemas/stock_detail.py` Fundamentals 各数值字段改 `float | None`，符合 API-CONTRACT null 语义
5. `API-CONTRACT.md` 字段来源从 `ratios-ttm.xxxTTM` 修正为 `key-metrics-ttm.xxxTTM`（D035）
6. `DECISIONS.md` D035 正式落盘
7. 单元测试（FakeFMP 扩展）+ 集成测试（test_stock_detail 切 fake_fmp）+ live smoke（key-metrics-ttm 字段存在性验证）
8. 前端不改。Evaluator 阶段仅做回归：确认浏览器请求 `/fundamentals` 返回真实数据且不崩（`FundamentalsCard` 已兼容 null）

**明确排除**：
- 前端 Fundamentals 类型 `number → number | null` 修正（D034 约束不改前端类型；`FundamentalsCard.formatRatio` 已有 null 容错）
- 前端 "Mock Data banner" 清理：代码扫描确认前端从未渲染过此 banner，无需改动
- 数据库变更：无
- Polygon 遗留代码清理：S4 范围（如有）

---

## 预计修改文件（10 个，方案 B 例外，经用户确认）

| # | 文件 | 改动 |
|---|------|------|
| 1 | `backend/app/external/fmp_client.py` | +`FMP_EP_KEY_METRICS_TTM` 常量，+`get_key_metrics_ttm()` |
| 2 | `backend/tests/test_fmp_client.py` | +3 cases：正常返回、空返回 None、与 ratios-ttm 路径隔离 |
| 3 | `backend/tests/test_fmp_live_smoke.py` | +1 case：`test_live_key_metrics_ttm_aapl`，断言含 `peRatioTTM` / `marketCapTTM` |
| 4 | `backend/tests/conftest.py` | `FakeFMP` 新增 `key_metrics_results` dict + `get_key_metrics_ttm()` |
| 5 | `backend/app/services/stock_detail_service.py` | 注入 `FmpClient`；实现真实 fundamentals 合并；删除 `_mock_fundamentals`；`source="fmp"` |
| 6 | `backend/app/routers/stocks.py` | `get_stock_detail_service` 注入 fmp 依赖 |
| 7 | `backend/app/schemas/stock_detail.py` | `priceToEarnings/priceToSales/peg/roce/freeCashFlow/marketCap` 改 `float \| None` |
| 8 | `backend/tests/test_stock_detail.py` | fundamentals 3 个测试重写为注入 `fake_fmp.key_metrics_results` / `ratios_results` |
| 9 | `docs/系统设计/API-CONTRACT.md` | §GET /api/stocks/:ticker/fundamentals：字段来源更新为 `key-metrics-ttm.*TTM`；说明段补充 D035 |
| 10 | `docs/系统设计/DECISIONS.md` | 追加 D035 决策正文 |

---

## 字段映射（FMP 响应 → API 字段）

**主端点：`/stable/key-metrics-ttm`**（2026-04-19 FMP 实际 shape）

| API 字段 | FMP 字段 | null 语义 |
|---|---|---|
| priceToEarnings | `peRatioTTM` | 负/缺失 → null |
| priceToSales | `priceToSalesRatioTTM` | 缺失 → null |
| peg | `pegRatioTTM` | 增长率 ≤0 或缺失 → null |
| roce | `returnOnCapitalEmployedTTM` | 缺失 → null |
| freeCashFlow | `freeCashFlowTTM`（若存在，直接取）；否则 ratios-ttm `freeCashFlowPerShareTTM × /stable/quote.sharesOutstanding` 兜底 | 分量全缺失 → null |
| marketCap | `marketCapTTM` | 缺失 → null |

**MVP 实现简化**：先只调用 `key-metrics-ttm`，不走 ratios-ttm/quote 兜底；freeCashFlow 直接取 `freeCashFlowTTM`。若 smoke 显示该字段缺失，再在 Generator 阶段补兜底分支（届时报告用户）。

---

## 可测试的完成标准

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| 1 | `FmpClient.get_key_metrics_ttm("AAPL")` 正常 shape 返回第一条 dict | 单元 | pytest + FakeClock + httpx MockTransport |
| 2 | `FmpClient.get_key_metrics_ttm("ZZZZ")` 空数组返回 None | 单元 | 同上 |
| 3 | `get_key_metrics_ttm` 请求路径为 `/key-metrics-ttm` 且带 `symbol=...&apikey=...` | 单元 | MockTransport 捕获 request |
| 4 | `StockDetailService.get_fundamentals("AAPL")` 映射 FakeFMP 注入数据到 API 字段，`source="fmp"` | 集成 | FastAPI TestClient + fake_fmp |
| 5 | key-metrics 某字段缺失时该 API 字段为 null，其他字段正常 | 集成 | 同上 |
| 6 | ticker 不在 watchlist → 404 `NOT_FOUND` | 集成 | 同上 |
| 7 | Fundamentals schema 接受 null 字段、按 camelCase 序列化 | 集成 | 同上 |
| 8 | live smoke：`/stable/key-metrics-ttm?symbol=AAPL` 返回非空，含 `peRatioTTM`、`marketCapTTM` | E2E（live，默认跳过）| pytest -m live |
| 9 | 全量回归 172/172 通过（新增 cases 后 N/N）；0 regression | 全量 | `uv run pytest` |
| 10 | 前端 `FundamentalsWidget` 手动冒烟：浏览器访问 AAPL，值正常显示，空字段显示 `—` | 手动 | dev server |

---

## Evaluator 自检清单

- [ ] 单元测试全部通过
- [ ] 集成测试全部通过
- [ ] 全量回归无 regression
- [ ] live smoke 人工本地跑一次（或在 pyproject 默认跳过下验证）
- [ ] `FmpClient.get_key_metrics_ttm` 路径/params/错误处理与既有方法风格一致
- [ ] `source="fmp"` 落在响应中
- [ ] Schemas nullable 字段在 null 情况下 200 OK，不报 422
- [ ] API-CONTRACT.md 的字段映射与代码一致（D035 已修订）
- [ ] DECISIONS.md D035 正文已落盘
- [ ] 无硬编码 apikey，新增代码无 console.error / print 遗留
- [ ] `_mock_fundamentals` / `FUNDAMENTALS_MOCK_SOURCE` 已删除无残留引用
- [ ] Lint（ruff / mypy 若配置）通过

---

## 开发顺序

1. API-CONTRACT.md 修订（字段来源 + 说明段）→ 让用户确认契约
2. DECISIONS.md D035 正文
3. FmpClient.get_key_metrics_ttm
4. test_fmp_client.py 单元测试
5. conftest.py FakeFMP 扩展
6. schemas/stock_detail.py nullable
7. stock_detail_service.py 真实实现
8. routers/stocks.py DI
9. test_stock_detail.py 集成测试重写
10. test_fmp_live_smoke.py key-metrics case
11. Evaluator：回归 + 手动浏览器冒烟

---

## 风险

- **R1**：live smoke 可能发现 `freeCashFlowTTM` 不在 key-metrics-ttm → 触发兜底分支实现（+1 次 ratios-ttm / quote 调用）。若发生，Generator 阶段停止并报告。
- **R2**：API-CONTRACT 的改动属于 system-design 协议范畴，严格应由 system-design skill 更新。本 Sprint 做为 D035 的执行层修订（字段映射级别，非结构变更），完成后 frontmatter 若需 `needs_update` 由用户确认。
