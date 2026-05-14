# Sprint Contract：F105-a2 FMP 客户端扩展（Market Breakout Scanner）

> 日期：2026-04-20 | 状态：草案
> 依赖：F105-a1 ✅ done
> 引用文档：
>   ARCHITECTURE.md#外部数据源-fmp-stable-端点映射（L281–325，screener / sma 两新端点）
>   ARCHITECTURE.md#环境配置（L208–220，cron env vars）
>   DECISIONS.md#D038（universe 月级刷新） · #D039（SMA 主路径 + EOD fallback） · #D042（独立 scanner cron）
>   DATA-MODEL.md#MarketScanUniverse（仅作为下游 a3 读取参考，本 Sprint 不涉及 ORM）

---

## 本次实现范围

**包含**：

1. **`fmp_client.py` 新增 2 个端点常量**（顶部模块级声明，风格对齐既有 D034 常量组）：
   - `FMP_EP_SCREENER = "/company-screener"`
   - `FMP_EP_SMA = "/technical-indicators/sma"`

2. **`fmp_client.py` 新增 3 个公开方法 + 1 个透明 fallback 组合方法**：
   - `get_company_screener_page(market_cap_gte: int, exchange: str, *, is_etf: bool = False, is_actively_trading: bool = True, limit: int = 500) -> list[dict]`
     - 单次调用单个交易所；`exchange` 取 `"NYSE" | "NASDAQ" | "AMEX"`；参数 `marketCapMoreThan / exchange / isEtf / isActivelyTrading / limit`（严格对齐 ARCHITECTURE L292）；返回 FMP 原始 list（透传字段）
   - `get_screener_universe(market_cap_gte: int = 50_000_000_000, exchanges: tuple[str, ...] = ("NYSE", "NASDAQ", "AMEX"), limit_per_exchange: int = 500) -> list[dict]`
     - 三次调用 `get_company_screener_page` 后合并、按 `symbol` 去重（首次出现保留）；返回去重后的 list；调用失败直接抛（不吞错）
   - `get_sma_series(symbol: str, period_length: int = 150, from_date: str | date | None = None, to_date: str | date | None = None, timeframe: str = "1day") -> list[dict]`
     - 请求 `/technical-indicators/sma`，参数 `symbol / periodLength / timeframe / from / to`；`from_date/to_date` None 时传默认值（`to=today`, `from=today-35 日历天`，留 25 交易日余量，与 D039 "最近 25 交易日窗口" 对齐）
     - 返回 FMP 原始 list（每项含 `date/open/high/low/close/volume/sma`）；响应非 list 时返回 `[]`（沿用 `get_daily_bars` 防御性风格）
   - `get_ma150_series_or_eod(symbol: str) -> dict`
     - **透明 fallback**（D039 L786）：先尝试 `get_sma_series(period_length=150)`；若抛出 `httpx.HTTPStatusError` 且 `response.status_code in {402, 403, 404}` → 改走 `get_daily_bars(symbol, today-260 日历天, today)`（约 180 交易日，够 MA150+20 日斜率）
     - 返回 `{"source": "sma" | "eod_fallback", "bars": list[dict]}`；调用方（F105-a3 scanner service）读取 `source` 字段决定是否写 SystemLog WARN
     - 除上述明确的 fallback 状态码外，其他异常（500/连接错误/非 JSON）继续抛出

3. **`config.py` 新增 5 个 Settings 字段**（默认值对齐 ARCHITECTURE L215–219 的 .env 文档）：
   ```python
   scanner_cron_hour: int = 6
   scanner_cron_minute: int = 15
   universe_cron_day: int = 1
   universe_cron_hour: int = 5
   universe_cron_minute: int = 0
   ```
   所有字段均可通过 `.env` 覆盖（pydantic-settings 自动 case-insensitive 映射）。

4. **`.env.example` 追加** 5 个 cron env var + 注释，与 ARCHITECTURE L213–219 一字不差。

5. **单元测试 `tests/test_fmp_client.py` 追加**：
   - `test_get_company_screener_page_endpoint_and_params`：验证 path = `FMP_EP_SCREENER`；params 包含 `marketCapMoreThan=50000000000, exchange=NYSE, isEtf=false, isActivelyTrading=true, limit=500, apikey`
   - `test_get_company_screener_page_bool_serialization`：验证 `isEtf/isActivelyTrading` 序列化为 `"false"/"true"` 小写字符串（pydantic/FMP 约定）
   - `test_get_screener_universe_merges_three_exchanges_and_dedupes`：三次 MockTransport 返回 `[AAPL, MSFT] / [AAPL, GOOG] / [TSLA]` → 结果 = `[AAPL, MSFT, GOOG, TSLA]`；httpx 请求次数 = 3
   - `test_get_sma_series_endpoint_and_params`：验证 path / `periodLength=150 / timeframe=1day / from / to` 全部正确传参
   - `test_get_sma_series_default_window`：`from_date/to_date` 省略时，`to` = today isoformat，`from` = `today - timedelta(days=35)` isoformat（用 freezegun 或 monkeypatch `datetime.now` 固定时间）
   - `test_get_ma150_series_or_eod_primary_sma`：SMA 200 返回 payload → `source="sma"`, `bars` 为 SMA 列表；httpx 请求次数 = 1
   - `test_get_ma150_series_or_eod_fallback_on_402`：SMA 返回 402 → 自动改请 EOD 端点 → `source="eod_fallback"`, `bars` 为 EOD 列表；httpx 请求次数 = 2（SMA 不做 429 重试流程——402/403/404 直接跳 fallback）
   - `test_get_ma150_series_or_eod_fallback_on_403`：403 同上
   - `test_get_ma150_series_or_eod_no_fallback_on_500`：500 → 按既有 `_request` 流程抛 `HTTPStatusError`（不触发 EOD fallback）
   - `test_get_ma150_series_or_eod_honors_rate_limiter`：清空 bucket 后调用，验证 sleep 行为与既有 `test_call_after_burst_sleeps_until_refill` 等价（复用 FakeClock）

6. **Live smoke 追加 `tests/test_fmp_live_smoke.py`**：
   - `test_live_screener_large_caps`：调 `get_screener_universe()` → 返回长度 ≥ 50，首项含 `symbol / companyName / exchange / marketCap` 字段，全部 `marketCap >= 50_000_000_000`
   - `test_live_sma_aapl_150`：调 `get_sma_series("AAPL")` → 长度 ≥ 15，首项含 `date / close / sma` 字段；若 Starter 不支持该端点（402/403/404）→ test 记录 `pytest.skip("SMA endpoint not available on this tier; a3 will fallback via get_ma150_series_or_eod")` 并断言 `get_ma150_series_or_eod("AAPL")["source"] == "eod_fallback"` 可正常返回 ≥ 180 根 EOD

**明确排除（不在本 Sprint）**：
- `UniverseRefreshService` / `MarketScannerService` / scanner cron 注册（F105-a3）
- `SystemLog` WARN 落库（F105-a3 内由 service 层写，`fmp_client` 只在返回值里标记 `source`）
- `GET /api/market/breakouts` router / schema（F105-a4）
- `GET /api/stocks/:ticker/chart` on-demand fallback（F105-b，独立子任务）
- `signal_engine.py` 的扫描封装（F105-a3 复用既有纯函数即可）

---

## 预计修改文件（共 5 个）

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/external/fmp_client.py` | 修改 | 2 常量 + 3 公共方法 + 1 fallback 组合方法 |
| 2 | `backend/app/config.py` | 修改 | 新增 5 个 Settings 字段（cron 配置） |
| 3 | `.env.example` | 修改 | 追加 5 个 cron env var 样例（对齐 ARCHITECTURE L213–219） |
| 4 | `backend/tests/test_fmp_client.py` | 修改 | 追加 10 条单元测试（见上表） |
| 5 | `backend/tests/test_fmp_live_smoke.py` | 修改 | 追加 2 条 live smoke（含 SMA 降级 skip 逻辑） |

👤 用户确认后进入开发。

---

## 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `get_company_screener_page` 命中 `/company-screener`，params 含 `marketCapMoreThan/exchange/isEtf/isActivelyTrading/limit` 全字段 | 单元 | pytest + httpx.MockTransport |
| 2 | `get_screener_universe` 调用三次（NYSE/NASDAQ/AMEX），按 `symbol` 去重合并 | 单元 | pytest + MockTransport |
| 3 | `get_sma_series` 命中 `/technical-indicators/sma`，`periodLength=150`，`timeframe=1day`，`from/to` 按 35 日历天默认窗口 | 单元 | pytest + monkeypatch datetime |
| 4 | `get_ma150_series_or_eod` 正常路径返回 `{"source":"sma",...}` | 单元 | pytest + MockTransport |
| 5 | 402/403/404 触发透明 EOD fallback，返回 `{"source":"eod_fallback",...}`，调用方无感知 | 单元 | pytest + MockTransport |
| 6 | 500 / 非 fallback 错误码按原 `_request` 流程抛出，不走 fallback | 单元 | pytest |
| 7 | 新方法全部走现有 `_acquire` token-bucket；连续调用超 burst 触发 sleep | 单元 | pytest + FakeClock |
| 8 | `settings.scanner_cron_hour / scanner_cron_minute / universe_cron_day / universe_cron_hour / universe_cron_minute` 能被 `.env` 覆盖（写入临时 env 后重新加载 Settings 验证） | 单元 | pytest + monkeypatch |
| 9 | `.env.example` 存在全部 5 个新 env var，注释与 ARCHITECTURE 一字不差 | 手工 diff | grep |
| 10 | Live smoke：screener 返回 ≥ 50 条大市值美股，全部 `marketCap >= 5e10` | live | pytest -m live（手动） |
| 11 | Live smoke：SMA 端点可用则返回有效序列；不可用（402/403/404）则自动 fallback 到 EOD 且 ≥ 180 根 bar | live | pytest -m live（手动） |
| 12 | `pytest backend/tests/` 全量回归全绿（F001–F105-a1 无回归） | 集成 | pytest |

---

## Evaluator 自检清单

- [ ] `pytest backend/tests/test_fmp_client.py` 全绿（含 10 条新增）
- [ ] `pytest backend/tests/` 全量回归全绿（F104/F105-a1/既有 FMP wrapper 测试均通过）
- [ ] `mypy backend/app/external/fmp_client.py` 严格通过（新增方法返回类型精确到 `list[dict]` / `dict`）
- [ ] Live smoke：用户持 FMP_API_KEY 手动执行 `uv run pytest -m live -k "screener or sma or ma150"`，全部通过或明确 skip（SMA 不支持时走 fallback）
- [ ] `fmp_client.py` 新增代码无硬编码 magic value：50_000_000_000 作为参数默认值可覆盖；260/35 日历天窗口注释说明来自 D039
- [ ] `get_ma150_series_or_eod` 只捕获 `httpx.HTTPStatusError`，只对 `{402, 403, 404}` 触发 fallback（不扩大到 5xx，避免掩盖真实外部故障）
- [ ] `get_screener_universe` 去重顺序可预测（首次出现保留），便于下游稳定
- [ ] `config.py` 5 个新字段类型为 `int`，默认值与 ARCHITECTURE L215–219 完全一致
- [ ] `.env.example` 追加内容与 ARCHITECTURE L213–219 注释逐字对齐
- [ ] DECISIONS.md 无需新增条目（本 Sprint 只是 D038/D039/D042 的执行）
- [ ] claude-progress.txt 追加 F105-a2 完成记录
- [ ] features.json `F105.subtasks.F105-a2.phase` 从 `contract_agreed` → `in_progress` → `testing` → `needs_review`

### 代码质量检查
- [ ] Lint：项目未配 linter，以 mypy + pytest 为准
- [ ] 无死代码 / 无硬编码 magic value / 无重复代码（两个 fallback 分支都复用既有 `get_daily_bars`）
- [ ] 单函数 ≤ 50 行
- [ ] 错误处理：`HTTPStatusError` 只在 fallback 分支被捕获并明确处理；其他异常透传

### 回归测试
- 当前 feature 全绿后运行 `pytest backend/tests/` 全量；列表对比前后通过数
- 若出现新失败：判定是否 a2 引入 → 是则打回 Generator，否则标注预先存在并上报用户

---

👤 确认此 Contract 后开始开发。
