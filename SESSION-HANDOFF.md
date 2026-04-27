# SESSION-HANDOFF

> 更新：2026-04-27 | 阶段：F205-c Sprint Contract 已确认，等待 Generator 开发
> 项目：MA150 Tracker → Cockpit
> 当前 active_sprint：**F205-c**（PoolService + GET /api/cockpit/pool）

---

## 已完成内容（直到本 session 结束）

### F205-a ✅ done
universe 表扩字段：sector / industry / last_price / last_volume

### F205-b ✅ done（最近一次发布）
- `FmpClient.get_financial_growth(symbol)` — FMP `/stable/financial-growth` 增量 endpoint
- `backend/app/services/cockpit/pool_helpers.py` — 5 个纯函数（compute_return_ratio_250d / compute_rs_percentile_map / compute_distance_to_50ma_pct / extract_revenue_growth_yoy_pct / passes_fundamental_sanity）
- 31 个单元测试 + 5 个 FMP client 测试，全部通过
- 全量回归 794 passed（758 → 794）
- D079 已落档（FMP financial-growth 来源 / RS mid-rank 算法 / fail-open / 双实现技术债）

### F205-c Sprint Contract ✅ 已确认（本 session）
Contract 文件：`docs/开发/sprint-contracts/F205-c-contract.md`

---

## 当前状态

| 项 | 值 |
|---|---|
| active_sprint | F205-c |
| active_sprint_phase | contract_agreed |
| 下一步 | 开新 session 进入 Generator 模式 |

---

## F205-c Sprint Contract 摘要

### 实现范围
把 F205-b 的 helpers + FMP 增量编排成完整漏斗，对外暴露 `GET /api/cockpit/pool`。

### 漏斗 5 层
| 层 | 数据源 | 过滤 |
|---|---|---|
| tradable | `market_scan_universe` | marketCap / price / `last_price*last_volume`（ADV 单日代理）/ sectors |
| trend | tradable ∩ 最新 `market_breakout_scans` | "被 F106 扫到"作为二元代理（**忽略 trendScoreMin**）|
| rs | FMP `get_daily_bars` 6 并发 + SPY closes | `compute_return_ratio_250d` → `compute_rs_percentile_map` → ≥ rsPercentileMin |
| fundamental | FMP `get_financial_growth` 6 并发 | `passes_fundamental_sanity`（None → fail-open D079）|
| action | fundamental ∩ setup_snapshots | 取 limit 条，按 RS 降序 |

**规模保护**：trend 子集 > 200 → 按 market_cap 降序截断到 200 进 RS 层（POOL_TREND_CAP）

**并发**：`ThreadPoolExecutor(max_workers=6)` 与全局 `_FmpRateLimiter` singleton（300 rpm + 6-槽 semaphore）协作

### 6 个文件清单
1. `backend/app/services/cockpit/pool_service.py`（新建）
2. `backend/app/routers/cockpit/pool.py`（新建）
3. `backend/app/routers/cockpit/__init__.py`（修改 — 注册一行）
4. `backend/app/schemas/cockpit/pool.py`（新建）
5. `backend/tests/test_pool_service.py`（新建）
6. `backend/tests/test_cockpit_pool_router.py`(新建)

### 5 项关键决策（已确认，落 D080）
1. **ADV 实现**：单日代理 `last_price × last_volume`（技术债 → F205-x）
2. **trendScoreMin**：参数接受但**忽略**；trend = breakout_scans 出现
3. **POOL_TREND_CAP=200**：market_cap 降序截断
4. **FMP 6 并发**：ThreadPoolExecutor(max_workers=6) + 全局 limiter；接受"挤占其他 FMP 消费者"
5. **缓存**：仅请求级 in-memory，不落 DB

### 非 watchlist ticker 字段映射
- `setupType / trendScore / distanceToPivotPct` → `null`
- `suggestedAction` → `"watch"` 默认
- `inWatchlist` → `false`（但仍可能在 items 列表里）

---

## 开发顺序（Generator 模式严格遵循）

```
1. 确认 DATA-MODEL.md / API-CONTRACT.md 无需改动（仅消费现有定义）
2. 新建 backend/app/schemas/cockpit/pool.py
   → wip commit: "wip(F205-c): pool schemas"
3. 新建 backend/app/services/cockpit/pool_service.py
   → wip commit: "wip(F205-c): PoolService"
4. 新建 backend/tests/test_pool_service.py（覆盖标准 #8–#10c, #16–#18）
   → 跑通 → wip commit: "wip(F205-c): pool service unit tests"
5. 新建 backend/app/routers/cockpit/pool.py + 修改 __init__.py 注册
   → wip commit: "wip(F205-c): pool router + register"
6. 新建 backend/tests/test_cockpit_pool_router.py（覆盖标准 #1–#7, #11–#15, #19–#21）
   → 跑通 → wip commit: "wip(F205-c): pool router integration tests"
7. 全量回归 `pytest backend/` → 通过（794 → 794+N）
8. 追加 DECISIONS.md D080
9. Evaluator 模式跑自检清单（contract §5）
10. 全部通过 → 最终 commit "feat(F205-c): pool service + GET /api/cockpit/pool"
   → phase: in_progress → testing → needs_review
```

---

## 未决事项

无。Contract 中所有决策已确认。

---

## 性能预期（用于 Evaluator 校准）

受 token bucket 5 calls/s 稳态约束：
- trend=50: ~5–10s
- trend=100: ~15–25s
- trend=200（cap）: ~30–40s（vs 串行 80s，约 2× 提升）

测试 #10b 用 mock latency 200ms × 30 ticker 计时断言：并发耗时 < 串行的 50%。

---

## 下一 Session 恢复指令

**开新 session（建议 Sonnet），粘贴**：

> 继续开发 F205-c，Sprint Contract 已确认。
> 读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F205-c-contract.md，
> 进入 Generator 模式，从开发步骤 1 开始。

---

## 关键文件参考（开发时打开）

| 用途 | 路径 |
|------|------|
| 本 sprint 合约（权威）| `docs/开发/sprint-contracts/F205-c-contract.md` |
| API 接口定义 | `docs/系统设计/API-CONTRACT.md` §GET /api/cockpit/pool（行 1322–1387）|
| F205-b 交付的 helpers | `backend/app/services/cockpit/pool_helpers.py` |
| FMP 增量方法 | `backend/app/external/fmp_client.py::get_financial_growth` |
| FMP 限流器（全局 singleton）| `backend/app/external/fmp_client.py::_FmpRateLimiter`（行 58–137）|
| 现有 cockpit router 风格参考 | `backend/app/routers/cockpit/setup.py` |
| 现有 service mock 测试风格 | `backend/tests/test_setup_service.py` |
| 现有 router 集成测试风格 | `backend/tests/test_cockpit_setup_router.py` |
