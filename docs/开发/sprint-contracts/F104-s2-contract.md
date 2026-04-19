# Sprint Contract：F104-S2 服务层 + 既有测试全量迁移至 FMP

> 日期：2026-04-19 | 状态：待确认
> 引用文档：
>   - ARCHITECTURE.md#外部数据源fmp-stable-端点映射d034
>   - DECISIONS.md#D034
>   - API-CONTRACT.md（market.overview、stocks.chart-data、fundamentals）
>   - F104-s1-contract.md（已完成，产出 FmpClient + fake_fmp fixture）

---

## 本次实现范围

**包含**：
- 后端生产代码 4 个 service + DI 胶水 4 文件，全量从 `PolygonClient` 切到 `FmpClient`
- `DataRefreshService._fetch_and_persist`：`get_daily_aggs` → `get_daily_bars`；新写 `_fmp_bar_to_dto`（按 `{date, open, high, low, close, volume}` 取字段），删除旧的 `_agg_to_bar`/`_get` 时间戳处理逻辑
- `MarketRefreshService._fetch_index`：`get_index_recent_aggs(symbol)` → `get_index_recent_bars(_DB_TO_FMP_INDEX[symbol])`，内部记录 DB↔FMP 符号映射（`SPX→^GSPC`, `NDX→^NDX`）；`prev_close` 逻辑从 timestamp 排序改为 ISO 日期字符串排序
- `MarketRefreshService._fetch_treasury`：按 FmpClient 契约读 `{date, year10, prev_date, prev_year10}`（替换旧的 `yield_10_year` 字段名）
- `WatchlistService.search_tickers` / `backfill_stock`：`polygon` → `fmp`；`search_tickers` 返回的 hit 字段映射保持由 router/前端侧适配（本 sprint 不改 API 响应 schema）
- `refresh_job.PolygonFactory` 重命名为 `FmpFactory`，签名保持 `Callable[[], FmpClient]`
- `main.py` / `routers/data.py` / `dependencies.py` / `external/__init__.py`：import 与工厂函数统一改名（`get_polygon_client` → `get_fmp_client`，`_polygon_factory` → `_fmp_factory`）
- `conftest.py`：`client` fixture 的 `dependency_overrides` 从 `get_polygon_client` 切到 `get_fmp_client`；删除 `FakePolygon` 类与 `mock_polygon` fixture（由 `fake_fmp` 统一承担）
- 既有 4 个测试文件全量切到 `fake_fmp`：
  - `test_watchlist_api.py`：`mock_polygon` → `fake_fmp`，`_polygon_hit` 按 FMP `search-symbol` 真实字段重写（`symbol / name / exchangeFullName / exchangeShortName / currency`），保留断言语义
  - `test_data_api.py`：`_attach_aggs` → `_attach_bars`（FMP dict 形态）
  - `test_market_refresh.py`：`FakeMarketPolygon` → 直接用 `fake_fmp`；bar 形态 `{date, close}`；删除底部 2 个 `PolygonClient` HTTP 层 unit test（已被 `test_fmp_client.py` 覆盖）
  - `test_data_refresh_service.py`：`mock_polygon` → `fake_fmp`，bar dict 形态
- `test_logs_api.py` 中的 `source="polygon"` 字面量改为 `"fmp"`（文案，保持语义一致）

**明确排除（归 S2c / S3）**：
- `@pytest.mark.live` 真实联网 smoke test（归 S2c）
- 删除 `FmpFactory` 中对 deprecated `polygon_client.py` 的任何动作（保留 D034 回滚锚点）
- Fundamentals 前端 Mock Data banner 清理（归 S3）
- `config.py` 的 `polygon_api_key` 字段清理（D034 回滚锚点）

---

## 预计修改文件清单（13 个，方案 B 已豁免 6 文件规则）

| # | 文件 | 改动 | 说明 |
|---|------|------|------|
| 1 | `backend/app/dependencies.py` | 修改 | `get_polygon_client` → `get_fmp_client`；注入 `FmpClient` 到 `WatchlistService` |
| 2 | `backend/app/main.py` | 修改 | scheduler 的 `_polygon_factory` → `_fmp_factory` |
| 3 | `backend/app/routers/data.py` | 修改 | factory 依赖改名 |
| 4 | `backend/app/external/__init__.py` | 修改 | 导出 `FmpClient`，保留 `PolygonClient`（标注 deprecated） |
| 5 | `backend/app/services/watchlist_service.py` | 修改 | `self.polygon` → `self.fmp`，`POLYGON_MATCH_LIMIT` → `FMP_MATCH_LIMIT`（常量改名） |
| 6 | `backend/app/services/data_refresh_service.py` | 修改 | `get_daily_aggs` → `get_daily_bars`；`_agg_to_bar` → `_fmp_bar_to_dto`（读 date 字符串 + OHLCV） |
| 7 | `backend/app/services/market_refresh_service.py` | 修改 | 新增 `_DB_TO_FMP_INDEX` 映射；`_fetch_index`/`_fetch_treasury` 按新字段契约重写 |
| 8 | `backend/app/services/refresh_job.py` | 修改 | 类型别名 `PolygonFactory` → `FmpFactory` |
| 9 | `backend/tests/conftest.py` | 修改 | 删 `FakePolygon`/`mock_polygon`；`client` fixture override `get_fmp_client` |
| 10 | `backend/tests/test_watchlist_api.py` | 修改 | `mock_polygon` → `fake_fmp`，`_polygon_hit` → `_fmp_hit` |
| 11 | `backend/tests/test_data_api.py` | 修改 | `_attach_aggs` → `_attach_bars`；所有 `mock_polygon` 引用改名 |
| 12 | `backend/tests/test_market_refresh.py` | 修改 | 删 `FakeMarketPolygon` + 2 个 PolygonClient HTTP 层 unit test；用 `fake_fmp` |
| 13 | `backend/tests/test_data_refresh_service.py` | 修改 | `mock_polygon` → `fake_fmp`，bar dict 形态 |
| 14 | `backend/tests/test_logs_api.py` | 修改 | 文案 `"polygon"` → `"fmp"`（2 处） |

实际净 14 文件；按方案 B 合并一次完成。

---

## 关键数据形态变更（高风险点）

### daily bars（stock EOD）
| 项 | 旧（Polygon Agg） | 新（FMP dict） |
|---|-------------------|---------------|
| 日期字段 | `timestamp` (ms, UTC epoch) | `date` (ISO `"YYYY-MM-DD"`) |
| OHLCV | `open/high/low/close/volume` | 同名 |
| 排序 | 由 `list_aggs` 返回升序 | FMP `historical-price-eod/full` 返回**降序**，service 必须显式 sort by date asc |

### index bars（SPX/NDX）
- 旧：`list_aggs("I:SPX", ...)` 返回 Agg 列表
- 新：`get_index_recent_bars("^GSPC", days=10)` 返回 FMP bar dict 列表（与 daily bars 同形态）
- service 需要 DB↔FMP 符号映射表：`{"SPX": "^GSPC", "NDX": "^NDX"}`

### TNX
- 旧：`{yield_10_year, date, prev_yield_10_year}`
- 新：`{year10, date, prev_year10, prev_date}`（FmpClient 已封装）

---

## 可测试的完成标准

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| 1 | `WatchlistService.search_tickers` 通过 `fake_fmp.search_tickers` 接收调用并返回 FMP 格式 hit，response schema 不变 | 集成 | pytest + TestClient |
| 2 | `WatchlistService.backfill_stock` 新建 stock 时调用 `fake_fmp.get_daily_bars` 并写入 DailyBar | 集成 | pytest |
| 3 | `DataRefreshService.backfill_stock` 对 FMP 降序 bar 列表排序后持久化，最新日期在 DB 中正确 | 单元 | pytest + fake_fmp |
| 4 | `DataRefreshService.increment_stock` 在 `from_date > today` 的 no-op 分支下仍然 commit 时间戳 | 单元 | pytest |
| 5 | `MarketRefreshService._fetch_index("SPX")` 调用 `fake_fmp.get_index_recent_bars("^GSPC", days=10)`（断言映射后的 symbol） | 单元 | pytest + fake_fmp |
| 6 | `MarketRefreshService._fetch_treasury` 读 `year10/prev_year10` 字段写入 MarketIndex.TNX | 单元 | pytest + fake_fmp |
| 7 | `change_pct` 计算在新字段下仍等于 `(close - prev_close) / prev_close * 100`，3 条市场指标写入完整 | 集成 | pytest |
| 8 | `POST /api/watchlist` 端到端（fake_fmp 驱动）创建 stock + 触发 backfill + 生成 DailyBar 行，状态码 200 | 集成 | TestClient |
| 9 | `POST /api/data/refresh` + `GET /api/data/refresh/status` 在 fake_fmp 下走完 in_progress → completed 状态机 | 集成 | TestClient |
| 10 | `GET /api/market/overview` 返回 SPX/NDX/TNX 三条（fake_fmp 驱动 refresh 后） | 集成 | TestClient |
| 11 | `grep -r "polygon_client" backend/app/` 结果只剩 `external/__init__.py` 的 deprecated re-export（或 0 处） | 契约 | 脚本 |
| 12 | `grep -r "FakePolygon\|mock_polygon" backend/tests/` 结果为 0 | 契约 | 脚本 |
| 13 | 全量 pytest（174+ cases）回归 0 失败 | 回归 | `cd backend && uv run pytest` |
| 14 | `test_fmp_client.py` 的 20 个 unit test 无回归 | 回归 | pytest |

---

## Evaluator 自检清单

- [ ] `cd backend && uv run pytest -v` 全绿（当前基线 174 cases）
- [ ] `grep -rn "from app.external.polygon_client" backend/app/` 结果仅限 `external/__init__.py`（deprecated re-export）或 0 处
- [ ] `grep -rn "FakePolygon\|mock_polygon\|PolygonFactory\|get_polygon_client" backend/` 结果为 0
- [ ] `grep -rn "get_daily_aggs\|get_index_recent_aggs\|yield_10_year" backend/app/` 结果为 0
- [ ] `polygon_client.py` 顶部 DEPRECATED 注释仍在（S1 产出，不得误删）
- [ ] 新增 `_DB_TO_FMP_INDEX` 常量位于 `market_refresh_service.py` 顶部且仅包含 SPX/NDX 两条
- [ ] `data_refresh_service.py` 中 bar 转换按 ISO 日期字符串解析，无 `fromtimestamp` 遗留
- [ ] API-CONTRACT.md 对外响应 schema 未改（字段名 / 类型 / envelope 一致）
- [ ] DECISIONS.md 无需新增（S2 纯执行 D034，未引入新决策）
- [ ] 代码质量：无 `print`、无死 import、无注释掉的代码块
- [ ] `uv run ruff check backend/app backend/tests`（若项目已配）零新增告警
- [ ] 全量回归：174/174 通过（含新迁移测试）；若有"预先存在"失败，单独标注

---

👤 用户确认本 Contract 后，Generator 开始开发。
