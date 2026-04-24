# F201-b Sprint Contract — Market Regime 接入层

> 创建：2026-04-24 | 状态：contract_agreed

---

## 目标

让 `GET /api/cockpit/regime` 可以返回 regime 打分 + SPY/QQQ/IWM 三大盘卡片 + 11 sector ETF heatmap。
同时建立 regime ETF 数据的每日定时刷新（22:15 UTC，weekdays）。

---

## 文件清单（7 生产 + 1 测试）

| # | 文件 | 操作 |
|---|------|------|
| 1 | `backend/app/repositories/market_index_repository.py` | 修改：WINDOW 5→260，新增 `REGIME_ETF_SYMBOLS`，新增 `upsert_batch` |
| 2 | `backend/app/services/market_refresh_service.py` | 修改：新增 `refresh_regime_etfs()` + ETF 名称/映射 |
| 3 | `backend/app/config.py` | 修改：`regime_cron_hour=22`，`regime_cron_minute=15` |
| 4 | `backend/app/services/refresh_job.py` | 修改：`REGIME_JOB_ID` + `_regime_tick` + 注册 cron |
| 5 | `backend/app/schemas/cockpit/regime.py` | 新建：`RegimeResponse` 及嵌套 schema |
| 6 | `backend/app/routers/cockpit/regime.py` | 新建：`GET /api/cockpit/regime` |
| 7 | `backend/app/routers/cockpit/__init__.py` | 修改：注册 regime router |
| 8 | `backend/tests/test_regime_f201b.py` | 新建：S1–S8 测试用例 |

---

## 关键设计决策

**D1 — WINDOW 扩展**
`MARKET_INDEX_WINDOW 5 → 260`。SPX/NDX/TNX 现有 ≤5 行，prune 行为不变。ETF 新 symbol 最多保留 260 行（覆盖 MA200 所需历史）。

**D2 — ETF 数据拉取策略**
`refresh_regime_etfs()` 每次拉取 400 个日历天（≈260 交易日），`upsert_batch` 所有 bar。FMP symbol = DB symbol（SPY→SPY，无需映射）。`prev_close` 由相邻 bar 内存计算，不查 DB。

**D3 — Regime Cron 定时**
`_regime_tick`（weekdays 22:15 UTC）= `MarketRefreshService.refresh_regime_etfs()` + `MarketRegimeService.compute_and_store(today)`。22:15 在主刷新（21:30）之后，保证 ETF 价格可用。

**D4 — GET 端点逻辑**
`MarketRegimeRepository.get_latest()` 返回 `None` → 404（冷启动）。有数据 → snapshot 字段 + `get_indices_and_sectors_state()` 实时 indices/sectors 合并返回。

---

## 验收标准（S1–S8）

| # | 测试 | 通过条件 |
|---|------|---------|
| S1 | GET /api/cockpit/regime 冷启动 | 返回 404 |
| S2 | 有 snapshot 时请求 | 200，regime/marketScore/subscores/computedAt 存在 |
| S3 | subscores 字段 | 与 snapshot 中 6 个 sub-score 字段精确匹配 |
| S4 | indices 数量 | 固定 3 条 (SPY/QQQ/IWM) |
| S5 | sectors 数量 | 固定 11 条 (SHARED.SECTOR_ETFS) |
| S6 | 缺 market_indices 数据时 | sectors close=null, state="Neutral"；indices close=null, aboveMa50=false |
| S7 | start_scheduler | 注册 REGIME_JOB_ID (22:15 UTC, mon-fri) |
| S8 | _regime_tick | 调用 refresh_regime_etfs + compute_and_store，异常不上抛 |

---

## 非目标

- 无新 Alembic 迁移（表结构 F201-a 已建）
- 不改 MarketRegimeService（`get_indices_and_sectors_state()` 已就绪）
- 无前端 widget（后续 sprint）
- 不为 SPX/NDX/TNX 新增历史行（仍为单行 upsert）
