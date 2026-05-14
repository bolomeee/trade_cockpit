---
feature_id: F006-a
feature_name: 后端数据层 + Polygon 扩展（SPX/NDX/TNX）
status: draft
created_at: 2026-04-17
---

# Sprint Contract：F006-a

## 范围

**本次包含**：
- `PolygonClient` 扩展：`get_index_previous_close(symbol)`（走 `get_previous_close_agg`，自动加 `I:` 前缀）、`get_treasury_10y_latest()`（httpx 直连 `/fed/v1/treasury-yields`，massive SDK 未封装）
- `MarketIndexRepository`：`upsert(symbol, name, date, close, prev_close, change_pct)` + `list_latest_by_symbol()`（每个 symbol 返回最新 1 条，共 3 条）+ `prune_to_window(5)`
- `MarketRefreshService`：刷新 SPX/NDX/TNX → 计算 change_pct → upsert → 5 日修剪 → SystemLog
- `refresh_job.py`：EOD 每日任务执行完股票刷新后，追加执行 `MarketRefreshService.refresh_all()`（失败不影响股票刷新；独立 try/except + ERROR 日志）

**本次排除**：
- API 路由 `GET /api/market/overview`（→ F006-b）
- 前端 MarketOverviewBar（→ F006-c）

## 预计修改文件（5 个）

- `backend/app/external/polygon_client.py`（修改：+2 方法，引入 httpx）
- `backend/app/repositories/market_index_repository.py`（新建）
- `backend/app/services/market_refresh_service.py`（新建）
- `backend/app/services/refresh_job.py`（修改：worker 内挂接 market refresh）
- `backend/tests/test_market_refresh.py`（新建：repo + service + polygon mock 综合测试）

## 非显而易见的技术决策（会追加 DECISIONS.md）

- **D0xx：TNX 数据源走 httpx 直连**
  massive SDK 未封装 `/fed/v1/treasury-yields`；用 `httpx` 直接调用，API key 走 query param `?apiKey=...`（Polygon 标准鉴权）。保留在 `PolygonClient` 内以统一鉴权与 rate limit 入口。
- **D0xx：SPX/NDX 使用 `I:` 前缀经 `get_previous_close_agg` 获取**
  massive 无专用 index 方法，indices 与 aggregates 端点共用，symbol 加 `I:` 前缀即可。

## 完成标准

| # | 标准 | 测试层级 | 工具 |
|---|------|---------|------|
| 1 | `PolygonClient.get_index_previous_close("SPX")` 返回含 close/prev_close 的对象，内部调用 `get_previous_close_agg("I:SPX")` | 单元 | pytest + monkeypatch |
| 2 | `PolygonClient.get_treasury_10y_latest()` 调用 `/fed/v1/treasury-yields?limit=2&sort=date.desc`，返回 `(date, close, prev_close)` | 单元 | pytest + httpx mock（respx 或 MonkeyPatch httpx.Client） |
| 3 | `MarketIndexRepository.upsert` 对同一 (symbol, date) 为 update 而非 insert；不同 date 新增 | 单元 | pytest + in-memory sqlite |
| 4 | `list_latest_by_symbol()` 返回 SPX/NDX/TNX 各自最新 1 条共 3 条 | 单元 | pytest |
| 5 | `prune_to_window(5)` 只保留每个 symbol 最近 5 条 | 单元 | pytest |
| 6 | `MarketRefreshService.refresh_all()` 调用 polygon 3 次（SPX/NDX/TNX），写入 3 条记录；change_pct = (close - prev_close) / prev_close * 100（TNX 特殊：以百分点 yield 本身的相对变化） | 集成 | pytest + mock PolygonClient |
| 7 | 单个 symbol 失败不阻塞其他 symbol；失败写 ERROR 日志，成功写 OK 日志 | 集成 | pytest + 注入异常 |
| 8 | `refresh_job` 在 `_run` 中股票刷新完成后调用 market refresh；market 失败不标记整体 job failed | 集成 | pytest + 替换 MarketRefreshService |
| 9 | 全量回归：`uv run pytest` 全过 | 回归 | pytest |

## Evaluator 自检清单

- [ ] 单元 + 集成测试全过
- [ ] 字段命名与 DATA-MODEL.md MarketIndex 完全一致（symbol / date / close / prev_close / change_pct）
- [ ] symbol 枚举仅限 SPX / NDX / TNX
- [ ] 5 日窗口策略落地
- [ ] `httpx` 已加入 backend/pyproject.toml（若尚未存在）
- [ ] 无 console.error / logger.error 遗留（正常路径）
- [ ] DECISIONS.md 已追加 2 条（TNX 直连 HTTP、SPX/NDX I: 前缀）
- [ ] 代码质量：无死代码、无硬编码魔法值、函数 ≤ 50 行
- [ ] 全量回归通过
