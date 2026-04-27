# SESSION-HANDOFF

> 更新：2026-04-27 | 阶段：F205-c ✅ done → F205-d（前端 widget）planned
> 项目：MA150 Tracker → Cockpit
> 当前 active_sprint：**F205-d**（PoolBuilderWidget 前端）

---

## 已完成内容

### F205-a ✅ done
universe 表扩字段：sector / industry / last_price / last_volume

### F205-b ✅ done
- `FmpClient.get_financial_growth(symbol)` — FMP `/stable/financial-growth`
- `backend/app/services/cockpit/pool_helpers.py` — 5 个纯函数
- 31 个单元测试 + 5 个 FMP client 测试
- D079 落档

### F205-c ✅ done（本 session 完成）

**新增文件（6/6）**：
| 文件 | 说明 |
|------|------|
| `backend/app/schemas/cockpit/pool.py` | PoolFunnel / PoolItem / PoolData / PoolResponse |
| `backend/app/services/cockpit/pool_service.py` | PoolService 5 层漏斗 + ThreadPoolExecutor 6-并发 |
| `backend/app/routers/cockpit/pool.py` | GET /api/cockpit/pool（参数校验 + PoolService 调用）|
| `backend/app/routers/cockpit/__init__.py` | 注册 pool_router（修改）|
| `backend/tests/test_pool_service.py` | 10 单元测试（#8–#10c/#16–#18）|
| `backend/tests/test_cockpit_pool_router.py` | 16 集成测试（#1–#7/#11–#15/#19–#21）|

**决策**：D080 落档（ADV 单日代理 / 忽略 trendScoreMin / POOL_TREND_CAP=200 / 非 watchlist null setup 字段）

**测试结果**：820 passed（+26），0 失败，Evaluator 自检全部通过。

---

## 当前状态

| 项 | 值 |
|---|---|
| active_sprint | F205-d |
| active_sprint_phase | planned |
| F205-c phase | needs_review |
| 全量回归 | 820 passed |

---

## F205-d 概要（下一个 sprint）

**目标**：PoolBuilderWidget 前端，消费 `GET /api/cockpit/pool`。

**后端接口**：
```ts
// API response 结构（已实现）
GET /api/cockpit/pool?marketCapMin=...&priceMin=...&rsPercentileMin=...&limit=50
{
  data: {
    funnel: { tradable, trend, rs, fundamental, action },
    items: [{
      ticker, name, sector, price,
      trendScore,        // null for non-watchlist
      rsPercentile,
      setupType,         // null for non-watchlist
      distanceToPivotPct, // null for non-watchlist
      distanceTo50maPct,
      earningsDate, daysUntilEarnings,
      revenueGrowthYoy,
      suggestedAction,  // "watch" for non-watchlist
      inWatchlist
    }]
  }
}
```

**已知约束**（来自 D080 + design-spec.md）：
- `trendScore` / `setupType` / `distanceToPivotPct` 对非 watchlist 为 null → 表格列显示 "—"
- pool 请求可能 30–40s → widget 需要 60s timeout + loading state
- `+ Add to Watchlist` 按钮 → 调 F003 watchlist API（已有）

---

## 关键文件参考

| 用途 | 路径 |
|------|------|
| API 接口（已实现）| `docs/系统设计/API-CONTRACT.md` §GET /api/cockpit/pool |
| Pool Service | `backend/app/services/cockpit/pool_service.py` |
| Pool Router | `backend/app/routers/cockpit/pool.py` |
| 视觉规格 | `docs/设计/design-spec.md` §Pool Builder |
| 功能调度 | `docs/需求/features.json` §F205-d |
| Widget 注册模式 | `src/workbench/WidgetRegistry.ts` |
| 现有 Widget 示例 | `src/workbench/widgets/` |

---

## 下一 Session 恢复指令

**开新 session，粘贴**：

> 继续开发 F205-d，读取 SESSION-HANDOFF.md。
> F205-c 后端已完成（GET /api/cockpit/pool 就绪）。
> 进入 F205-d Sprint Contract 阶段，先读 design-spec.md §Pool Builder + API-CONTRACT.md §GET /api/cockpit/pool，
> 然后起草 F205-d Sprint Contract（PoolBuilderWidget 前端实现）。
