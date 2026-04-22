# Sprint Contract：F108 `/fundamentals` `/pullbacks` 放开到任意 ticker

> 日期：2026-04-21 | 状态：**反向补契约**
> 依赖：F105-b ✅ done（chart on-demand fallback，D041）
> 引用文档：
>   DECISIONS.md#D041（chart on-demand fallback 模式，本 sprint 沿用）
>   API-CONTRACT.md#GET-/api/stocks/:ticker/fundamentals / pullbacks
>   backend/app/services/stock_detail_service.py

---

## 背景

D041 在 F105-b 把 `/chart` 放开到非 watchlist ticker（on-demand 拉 FMP）。Scanner 让用户点击任意 ticker 看图成为常态场景，但 `/fundamentals` 与 `/pullbacks` 仍走 `_resolve_active_stock` → 不在 watchlist 或 is_active=False → 404。用户点 scanner 里的 ticker 切 Fundamentals 标签后直接报错，体验割裂。

**决策依据**：用户确认 D041 已覆盖该语义延伸，不需再走 system-design。本 sprint 补 DECISIONS.md D047 记录语义推广即可。

---

## 本次实现范围

### 1. `backend/app/services/stock_detail_service.py`（修改）
- `get_fundamentals(raw_ticker)`：
  - 移除 `_resolve_active_stock` 调用
  - 改为 `ticker = raw_ticker.strip().upper()`；空串 → `APIError("NOT_FOUND", "empty ticker", 404)`
  - 直接调 `self.fmp.get_ratios_ttm(ticker)` + `self.fmp.get_key_metrics_ttm(ticker)`
  - `httpx.HTTPError` → `APIError("EXTERNAL_API_ERROR", ..., 502)`（既有语义保留）
  - 返回 payload `ticker` 字段用 `ticker`（大写），不再用 `stock.ticker`
- `get_pullbacks(raw_ticker)`：
  - `ticker = raw_ticker.strip().upper()`
  - `stock = self.stocks.get_by_ticker(ticker)`
  - `stock is None or not stock.is_active` → **返回空 list**（而非 404；pullback 表只对 watchlist 维护，非 watchlist ticker 无历史可显示，与 chart fallback `pullbackMarkers=[]` 语义一致）
  - 原有分支保留：stock 存在且 active → 读 pullback 表

### 2. `backend/tests/test_stock_detail.py`（修改）
- 调整原 `test_detail_endpoints_404_when_ticker_inactive`（F105-b 已动过 chart 部分）：
  - **fundamentals** 分支：inactive / not-in-watchlist ticker 不再 404；改为 mock FMP 返回 ratios → 200，字段正确
  - **pullbacks** 分支：inactive / not-in-watchlist ticker 不再 404；返回 200 + 空 list
- 追加用例：
  - `test_fundamentals_for_unknown_ticker_hits_fmp`：FakeFMP seed ratios → 200 返回正常
  - `test_fundamentals_fmp_error_returns_502`：FMP 抛 httpx.HTTPError → 502 EXTERNAL_API_ERROR
  - `test_fundamentals_empty_ticker_returns_404`：请求 `/api/stocks//fundamentals` 或 trim 后空串
  - `test_pullbacks_for_unknown_ticker_returns_empty`：200 + items=[]
  - `test_pullbacks_for_inactive_ticker_returns_empty`：stock 存在但 is_active=False → 200 + []

### 3. `docs/系统设计/API-CONTRACT.md`（修改）
- `/api/stocks/:ticker/fundamentals`：
  - 原 404 语义（ticker 不在 watchlist）移除
  - 新 404 仅限"空 ticker"
  - 新 502 语义保持
  - 响应 `source: 'fmp'`、字段集不变
- `/api/stocks/:ticker/pullbacks`：
  - inactive / 非 watchlist ticker → 200 + 空 items 列表
  - 不再 404

### 4. `docs/系统设计/DECISIONS.md`（修改）
- 追加 **D047：F108 `/fundamentals` / `/pullbacks` 沿用 D041 on-demand 语义**
  - 背景：scanner 场景点击任意 ticker 需跨 widget 联动
  - 决策：fundamentals 直打 FMP；pullbacks 非 watchlist 返回空（不去查 FMP，因为 pullback 需要本地 180 天滚动窗口计算，on-demand 成本过高且语义不强）
  - 不重新走 system-design 的理由：与 D041 同族决策（on-demand fallback），D041 已通过系统设计确认

---

## 明确排除

- pullbacks 走 FMP on-demand 计算（本 sprint 不做；pullback 计算依赖 180 天 daily bars，on-demand 成本高且数据回看窗口短，明确返回空列表）
- 前端 FundamentalsWidget / PullbackWidget 的加载/空态文案改写（它们已经能处理空数据；若视觉需要差异化文案留给后续 UX 迭代）
- 新增 FMP 限流或缓存层（D044 共享 bucket 已覆盖）

---

## 预计修改文件（共 4 个）

| # | 文件 | 类型 | 改动 |
|---|---|---|---|
| 1 | `backend/app/services/stock_detail_service.py` | 修改 | `get_fundamentals` / `get_pullbacks` 放开 |
| 2 | `backend/tests/test_stock_detail.py` | 修改 | 调整既有 inactive 用例 + 追加 5 条 |
| 3 | `docs/系统设计/API-CONTRACT.md` | 修改 | fundamentals / pullbacks 两接口的 404 语义更新 |
| 4 | `docs/系统设计/DECISIONS.md` | 修改 | 追加 D047 |

---

## 可测试的完成标准

| # | 标准 | 层级 |
|---|---|---|
| 1 | 非 watchlist ticker `/fundamentals` → 200（FakeFMP seeded）| 集成 |
| 2 | inactive ticker `/fundamentals` → 200 | 集成 |
| 3 | 空 ticker（trim 后）`/fundamentals` → 404 | 集成 |
| 4 | FMP httpx error → 502 `EXTERNAL_API_ERROR` | 集成 |
| 5 | 非 watchlist ticker `/pullbacks` → 200 + items=[] | 集成 |
| 6 | inactive ticker `/pullbacks` → 200 + items=[] | 集成 |
| 7 | watchlist active ticker `/pullbacks` → 与 F102 原有行为字节级一致 | 回归 |
| 8 | watchlist active ticker `/fundamentals` → 与 F104-S3 原有行为一致 | 回归 |
| 9 | API-CONTRACT.md 两接口的 404 语义已更新 | 文档 |
| 10 | DECISIONS.md D047 含背景 / 决策 / 为何不走 system-design 三要素 | 文档 |
| 11 | `pytest backend/tests/` 全量回归全绿 | 集成 |

---

## Evaluator 自检清单

- [ ] `pytest backend/tests/test_stock_detail.py` 全绿
- [ ] `pytest backend/tests/` 全量回归全绿
- [ ] mypy `services/stock_detail_service.py` 严格通过
- [ ] `get_fundamentals` / `get_pullbacks` 两函数不再调 `_resolve_active_stock`（grep 确认）
- [ ] `_resolve_active_stock` 如果仍被 `get_chart` 外其它方法引用，保留；否则一并考虑是否删除（本 sprint 不强制删）
- [ ] API-CONTRACT.md 的 response / error 表述与实现一致
- [ ] D047 条目追加
- [ ] features.json F108.phase 流转 `contract_agreed → testing → needs_review`

### 代码质量检查
- [ ] `get_fundamentals` / `get_pullbacks` 各 ≤ 30 行
- [ ] 错误处理：仅捕获 `httpx.HTTPError`，其他异常透传
- [ ] 字段 `ticker` 统一返回大写 trim 后值

### 回归测试
- `pytest backend/tests/`
- 起环境：手工在 scanner 里点非 watchlist ticker → 切 Fundamentals / Pullbacks 标签，确认不再 404

---

⚠️ **反向补契约**：代码已落地，Evaluator 重点是补齐既有测试用例的更新（`test_detail_endpoints_404_when_ticker_inactive` 在 F105-b 已改过 chart 分支，本 sprint 需继续收窄到 fundamentals/pullbacks 分支的新语义）。
