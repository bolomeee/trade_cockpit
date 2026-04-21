# Sprint Contract：F105-b `/api/stocks/:ticker/chart` on-demand fallback

> 日期：2026-04-21 | 状态：已确认
> 依赖：F105-a1 ✅ done（`signal_engine.compute_ma150_series` 复用）
> 引用文档：
>   API-CONTRACT.md#GET-/api/stocks/:ticker/chart（L285–343，服务端行为分支规范）
>   DECISIONS.md#D041（on-demand fallback 设计）
>   backend/app/services/stock_detail_service.py（既有 `get_chart` 待扩展）
>   backend/app/services/signal_engine.py#compute_ma150_series（复用 MA150 计算）
>   backend/app/external/fmp_client.py#get_daily_bars（复用 EOD 拉取，无需新方法）

---

## 决策收口

- **错误码方案 A**：API-CONTRACT.md 将 `EXTERNAL_SERVICE_ERROR` 统一改为 `EXTERNAL_API_ERROR`（与现网代码 + test_stock_detail:225 一致）
- **fallback 触发条件 B2**：`stock is None` **或** `stock.is_active=False` 都走 fallback。语义：Scanner 场景里 ticker 一旦被点，都应能看图；inactive 的历史回踩数据在 fallback 路径下不显示（`pullbackMarkers=[]`）

---

## 本次实现范围

### 1. `backend/app/services/stock_detail_service.py`（修改）
- `get_chart(raw_ticker)` 拆两个分支：
  - `stock` 存在且 `is_active=True` → 原逻辑完全不变（本地 DailyBar + Signal.ma150_value + Pullback 表）
  - `stock is None` 或 `stock.is_active=False` → **on-demand fallback**：
    1. `today = date.today()`；`from_d = today - timedelta(days=400)`
    2. `bars = self.fmp.get_daily_bars(ticker_upper, from_d, today)`
    3. `bars == []` → `raise APIError("NOT_FOUND", f"ticker {ticker} not found", 404)`
    4. `httpx.HTTPError` → `raise APIError("EXTERNAL_API_ERROR", ..., 502)`
    5. 规范化 + 按 date 升序排序（FMP 返回倒序），截取尾部 250 根作为 `bars_asc`
    6. `ma_series = compute_ma150_series([b["close"] for b in bars_asc])`；组装 `ma150` 列表时跳过 None（前 149 天）
    7. `pullbackMarkers=[]`
    8. 返回与现有分支字段集一致的 dict
- 抽私有方法 `_assemble_chart_payload(ticker, bars_asc, ma150_points, pullback_markers) -> dict`，两分支共用构造出口（避免重复）
- 不新增 fmp_client 方法；`get_daily_bars` 已覆盖

### 2. `backend/tests/test_stock_detail.py`（修改）
- **删除** `test_detail_endpoints_404_when_ticker_inactive` 中的 chart 断言（inactive ticker 现在走 fallback，不再 404）。其他 endpoint（pullbacks / fundamentals）仍 404，保留这部分断言
- **修改**：上述测试拆分或收窄为只覆盖 pullbacks / fundamentals 两条
- **追加 4 条**：
  - `test_chart_fallback_for_unknown_ticker`：ticker 不在 stocks 表，`fake_fmp.daily_bars_results` seed 200 根 → 200，返回 ticker=大写、bars 升序、ma150 前 149 根不输出、`pullbackMarkers == []`
  - `test_chart_fallback_for_inactive_ticker`：stocks 表中 `is_active=False` 一行 + seed FMP bars → 同样走 fallback，返回 200
  - `test_chart_fallback_empty_fmp_returns_404`：FMP 返回空 list → 404 `NOT_FOUND`
  - `test_chart_fallback_fmp_http_error_returns_502`：`fake_fmp.daily_bars_exc = httpx.HTTPError("boom")` → 502 `EXTERNAL_API_ERROR`

### 3. `backend/tests/conftest.py` 可能微调
- 现有 `FakeFMP.get_daily_bars` 无异常注入字段，需追加 `daily_bars_exc: Exception | None = None`；调用时若非 None 则 raise。一次性小改动，不影响既有测试

### 4. `docs/系统设计/API-CONTRACT.md`（修改）
- L342 `EXTERNAL_SERVICE_ERROR` → `EXTERNAL_API_ERROR`（只改这一处）

---

## 明确排除
- DailyBar / Pullback 写库（D041 明示不写）
- 缓存层（D041 明示不加）
- fallback 路径下计算 pullback markers（契约级固定空数组）
- fmp_client 新增方法（直接复用 `get_daily_bars`）
- 前端（F105-c）

---

## 预计修改文件（共 4 个）

| # | 文件 | 改动 |
|---|---|---|
| 1 | `backend/app/services/stock_detail_service.py` | `get_chart` 拆分支 + `_assemble_chart_payload` |
| 2 | `backend/tests/test_stock_detail.py` | 调整 inactive 用例 + 追加 4 条 fallback 用例 |
| 3 | `backend/tests/conftest.py` | `FakeFMP` 追加 `daily_bars_exc` 字段 |
| 4 | `docs/系统设计/API-CONTRACT.md` | 错误码名称修正 |

---

## 可测试的完成标准

| # | 标准 | 层级 |
|---|---|---|
| 1 | watchlist active ticker 行为与现状字节级一致（既有 3 条 chart 测试不修改仍绿）| 集成 |
| 2 | 表里没有的 ticker → fallback 200，返回 bars/ma150/空 pullbackMarkers | 集成 |
| 3 | 表里有但 inactive → 同样 fallback 200 | 集成 |
| 4 | FMP 返回空 → 404 `NOT_FOUND` | 集成 |
| 5 | FMP httpx.HTTPError → 502 `EXTERNAL_API_ERROR` | 集成 |
| 6 | fallback 路径 MA150 对齐：前 149 天跳过；返回 ma150 长度 == len(bars) - 149 | 集成 |
| 7 | fallback 路径 bars 按日期升序 | 集成 |
| 8 | `pytest backend/tests/` 全量回归全绿 | 集成 |
| 9 | mypy `services/stock_detail_service.py` 严格通过 | 静态 |
| 10 | API-CONTRACT.md 错误码已改名（grep 无 `EXTERNAL_SERVICE_ERROR` 残留）| 手工 |

---

## Evaluator 自检清单

- [ ] `pytest backend/tests/test_stock_detail.py` 全绿
- [ ] `pytest backend/tests/` 全量回归全绿
- [ ] mypy `services/stock_detail_service.py` 严格通过
- [ ] `_assemble_chart_payload` 为两分支唯一出口，无字段漂移
- [ ] fallback 分支只捕获 `httpx.HTTPError`，其他异常透传
- [ ] 单函数 ≤ 50 行
- [ ] 无硬编码：400/250/150 均有既有常量 `CHART_WINDOW_DAYS / MA150_PERIOD` 或新增 `CHART_FALLBACK_LOOKBACK_DAYS = 400` 常量
- [ ] features.json F105.subtasks.F105-b.phase 流转 `contract_agreed → in_progress → testing → needs_review`
- [ ] claude-progress.txt 追加 F105-b 完成记录
- [ ] DECISIONS.md 无需新增条目（落实 D041，非新决策）

### 代码质量检查
- [ ] 无死代码 / 无 print
- [ ] 两分支对外返回字段集严格相同
- [ ] 错误处理完整（HTTPError 转 APIError，非 HTTP 异常透传）

### 回归测试
- 当前 feature 绿后跑 `pytest backend/tests/`
- 新增失败若由 b 引入 → 打回 Generator

---

👤 A + B2 已确认，进入 Generator。
