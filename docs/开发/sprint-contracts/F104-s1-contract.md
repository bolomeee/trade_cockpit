# Sprint Contract：F104-S1 FMP 客户端 + 测试替身

> 日期：2026-04-19 | 状态：已确认（2026-04-19）
> 引用文档：
>   ARCHITECTURE.md#外部数据源fmp-stable-端点映射d034 | DECISIONS.md#D034 | SESSION-HANDOFF.md Sprint 1

---

## 本次实现范围

**包含**：
- 新建 `backend/app/external/fmp_client.py`：httpx REST 客户端，封装 5 个方法：`search_tickers` / `get_daily_bars` / `get_index_recent_bars` / `get_treasury_10y_latest` / `get_ratios_ttm`
- 顶部集中声明 endpoint 常量（FMP_BASE + 6 个路径常量，见 ARCHITECTURE.md）
- Token bucket rate limiter：300/min，burst 50，阻塞等待；429 退避 1s 重试一次
- `config.py` 新增 `fmp_api_key`；`polygon_api_key` 保留（作回滚锚点）
- `.env.example` 新增 `FMP_API_KEY=` 行
- `polygon_client.py` 顶部加 `# DEPRECATED (D034): 回滚锚点，不再被服务层导入` 注释块
- `test_polygon_client.py` 重命名为 `test_fmp_client.py`，重写为 FMP 客户端的单元测试
- `conftest.py` 新增 `fake_fmp` fixture（接口与 `FakePolygon` 对齐，为 S2 全量迁移做准备），`FakePolygon` 暂不删除

**明确排除（本次不做）**：
- 任何 service/router/dependencies 层改动（归 S2）
- 既有 162 个 pytest 的 fake_fmp 迁移（归 S2）
- fundamentals 真实接入 + 前端 Mock Data banner 清理（归 S3）
- `polygon_client.py` 文件删除（D034 回滚路径要求保留）
- live smoke test（归 S2）

---

## 预计修改文件（6 个净文件）

| 文件路径 | 改动类型 | 说明 |
|---------|---------|------|
| `backend/app/external/fmp_client.py` | 新增 | FMP httpx 客户端 + 5 方法 + 300/min token bucket |
| `backend/app/config.py` | 修改 | `fmp_api_key` 字段 |
| `backend/app/external/polygon_client.py` | 修改 | 顶部 DEPRECATED 注释（不改行为） |
| `backend/tests/test_fmp_client.py` | 新增（替代旧文件） | FMP 客户端单测 |
| `backend/tests/test_polygon_client.py` | 删除 | 重命名到上一行 |
| `backend/tests/conftest.py` | 修改 | 新增 FakeFMP + `fake_fmp` fixture |
| `.env.example` | 修改 | `FMP_API_KEY=` |

> rename 视为 1 文件净变更，合计 **6 净文件**，符合 6 文件上限。

---

## 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `FmpClient()` 无 `FMP_API_KEY` 时抛 `RuntimeError("FMP_API_KEY not set")` | 单元 | pytest |
| 2 | `search_tickers(q)` 先调 `/stable/search-symbol?query=q&apikey=...`；空结果时 fallback 调 `/stable/search-name` | 单元 | pytest + httpx mock |
| 3 | `get_daily_bars("AAPL", from, to)` 调 `/stable/historical-price-eod/full?symbol=AAPL&from=...&to=...&apikey=...`，返回原始 list | 单元 | pytest + httpx mock |
| 4 | `get_index_recent_bars("^GSPC", days=10)` 调 `/stable/historical-price-eod/full` 传正确 symbol + 日期窗口 | 单元 | pytest + httpx mock |
| 5 | `get_treasury_10y_latest()` 调 `/stable/treasury-rates`，返回 `{date, year10, prev_date, prev_year10}` | 单元 | pytest + httpx mock |
| 6 | `get_ratios_ttm("AAPL")` 调 `/stable/ratios-ttm?symbol=AAPL`，原样返回第一条记录 | 单元 | pytest + httpx mock |
| 7 | 前 50 次调用（burst）不触发 sleep | 单元 | pytest + FakeClock |
| 8 | 第 51 次在 burst 用完后应按 token bucket 等待（refill interval = 60/300 = 0.2s） | 单元 | pytest + FakeClock |
| 9 | token 用尽，经过 60s 后再次恢复到 burst 容量，后续 50 次调用不 sleep | 单元 | pytest + FakeClock |
| 10 | 首次 429 响应会退避 1s 重试一次；重试仍 429 抛 `httpx.HTTPStatusError` | 单元 | pytest + httpx mock + FakeClock |
| 11 | 非 200/非 429 错误直接抛 `httpx.HTTPStatusError`，不重试 | 单元 | pytest + httpx mock |
| 12 | `conftest.py` 的 `fake_fmp` fixture 提供上述 5 方法的 programmable stub，接口签名与真实 FmpClient 一致 | 契约 | pytest（import-only） |
| 13 | `polygon_client.py` 顶部含 `DEPRECATED (D034)` 字样，但 import、类、方法全部保持可用（既有 162 个测试不回归） | 回归 | `pytest backend/tests/`（不含 test_fmp_client 新增部分，S2 才整体迁移） |

---

## Evaluator 自检清单

- [ ] `cd backend && uv run pytest tests/test_fmp_client.py -v` 全绿
- [ ] `cd backend && uv run pytest` 全量回归（既有 162 tests 不失败；test_polygon_client 已删除不计入）
- [ ] 新增 `fake_fmp` fixture 存在、可 import，但未被其他测试消费（S2 任务）
- [ ] `grep -r "from app.external.polygon_client" backend/app/` 结果与迁移前一致（service 层 S2 才断开依赖）
- [ ] `grep "DEPRECATED" backend/app/external/polygon_client.py` 命中顶部注释
- [ ] `.env.example` 含 `FMP_API_KEY=` 行
- [ ] `fmp_client.py` 顶部有 endpoint 常量集中声明块，与 ARCHITECTURE.md 的 7 个常量一一对应
- [ ] 无 `print` / `TODO-fixme` 遗留
- [ ] `uv run ruff check backend/app/external/fmp_client.py backend/tests/test_fmp_client.py`（若项目已配）零新增告警
- [ ] DECISIONS.md 无需追加新决策（本 S1 全部落在 D034 范围内）

---

👤 用户确认本 Contract 后，开发开始。
