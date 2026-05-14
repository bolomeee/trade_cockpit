# Sprint Contract：F104-S2c FMP 真实联网 smoke test

> 日期：2026-04-19 | 状态：待确认
> 引用：F104-s1-contract.md（FmpClient 产出）| F104-s2-contract.md（服务层迁移完成）

---

## 本次实现范围

**包含**：
- `backend/pyproject.toml`：注册 `live` pytest marker，默认 `-m "not live"` 排除，CI / 手动跑 `pytest -m live` 触发
- `backend/tests/test_fmp_live_smoke.py`（新建）：≥5 个 `@pytest.mark.live` smoke test，直接命中 FMP `/stable/` 真实端点，验证 FmpClient 的 5 个公开方法 + 搜索 fallback 分支
- 所有 live test 在 `FMP_API_KEY` 未设置或为空时自动 skip，不阻塞普通 CI

**明确排除**：
- 前端 Fundamentals Mock Data banner 清理 / 真实接入（归 S3，需要前后端联动 + API-CONTRACT 确认）
- 修改 FmpClient（S1 已稳定）
- 修改服务层或既有 pytest（S2 已完成）

---

## 预计修改文件（2 个）

| # | 文件 | 改动 |
|---|------|------|
| 1 | `backend/pyproject.toml` | 在 `[tool.pytest.ini_options]` 新增 `markers = ["live: ..."]` 与 `addopts = "-m 'not live'"` |
| 2 | `backend/tests/test_fmp_live_smoke.py` | 新建，≥5 case |

---

## Smoke Test 清单（≥5 cases，覆盖 FmpClient 全部 5 方法 + 1 搜索 fallback 分支）

| # | 测试 | 方法 | 断言 |
|---|------|------|------|
| 1 | `test_live_search_symbol_aapl` | `search_tickers("AAPL")` | 结果非空；含 symbol=="AAPL" 的条目 |
| 2 | `test_live_search_name_fallback_apple` | `search_tickers("Apple Incorporated")` | 结果非空（symbol 分支空 → name fallback 返回） |
| 3 | `test_live_daily_bars_aapl_recent` | `get_daily_bars("AAPL", today-30d, today)` | 列表长度 > 0；首条含 date/open/high/low/close/volume |
| 4 | `test_live_index_recent_bars_gspc` | `get_index_recent_bars("^GSPC", days=10)` | 列表非空；含 close 字段 |
| 5 | `test_live_treasury_10y` | `get_treasury_10y_latest()` | 返回 dict 含 `date/year10/prev_date/prev_year10`；`year10` 为 float |
| 6 | `test_live_ratios_ttm_aapl` | `get_ratios_ttm("AAPL")` | 返回非 None dict，至少含 1 个常见 ratio 字段（如 `peRatioTTM`） |

所有 case：
- 模块级 `pytestmark = pytest.mark.live`
- 模块级 `pytest.importorskip` 或 `skipif(not os.getenv("FMP_API_KEY"), reason=...)` 保护
- 使用真实 `FmpClient()`，不注入 transport；接受 FMP 真实 rate 限制

---

## Evaluator 自检清单

- [ ] `cd backend && uv run pytest` 默认运行**不包含** live（仍 172/172）
- [ ] `cd backend && uv run pytest -m live` 在 `FMP_API_KEY=...` 时 6/6 全绿；无 key 时全部 skipped
- [ ] `grep -n "pytest.mark.live" tests/test_fmp_live_smoke.py` 命中模块级声明
- [ ] smoke test 文件无 httpx mock / transport 注入（违反"真实联网"语义）
- [ ] 无硬编码日期（使用 today - timedelta 相对窗口）
- [ ] pyproject.toml 的 `markers` 描述清晰、`addopts` 默认排除 live

---

👤 用户确认本 Contract 后开始。
