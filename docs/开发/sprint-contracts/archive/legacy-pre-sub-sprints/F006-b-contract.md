---
feature_id: F006-b
feature_name: Market overview API 路由
status: draft
created_at: 2026-04-17
---

# Sprint Contract：F006-b

## 范围

**本次包含**：
- `schemas/market.py`：`MarketIndexOut`（symbol / name / close / prevClose / changePct / date，camelCase 响应）
- `routers/market.py`：`GET /api/market/overview` → 返回 `ResponseEnvelope[list[MarketIndexOut]]`，按 SPX→NDX→TNX 顺序
- `main.py`：include market router
- 测试：空数据 / 仅部分 symbol / 全量 / 字段命名 / camelCase 验证

**本次排除**：
- 前端 MarketOverviewBar（→ F006-c）
- 手动触发 refresh 端点（不在 API-CONTRACT 中，EOD 调度 + 手动 `/api/data/refresh` 触发 job 时会级联刷 market）

## 预计修改文件（4 个）

- `backend/app/schemas/market.py`（新建）
- `backend/app/routers/market.py`（新建）
- `backend/app/main.py`（修改：include router）
- `backend/tests/test_market_api.py`（新建）

## 完成标准

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| 1 | `GET /api/market/overview` 空表返回 `{data: [], message: "success"}` 200 | 集成 | TestClient |
| 2 | 有 SPX/NDX/TNX 数据时按固定顺序返回三条 | 集成 | TestClient |
| 3 | 响应字段严格 camelCase：symbol / name / close / prevClose / changePct / date | 集成 | TestClient |
| 4 | date 序列化为 `YYYY-MM-DD` 字符串 | 集成 | TestClient |
| 5 | prev_close / change_pct 为 null 时序列化为 null（而非缺省） | 集成 | TestClient |
| 6 | 只有 SPX 一条数据时返回长度 1，不编造 NDX/TNX | 集成 | TestClient |
| 7 | 全量回归 pytest 全过 | 回归 | pytest |

## Evaluator 自检清单

- [ ] 单元 + 集成 + 回归全过
- [ ] 响应格式对齐 API-CONTRACT.md#market 示例
- [ ] 字段大小写对齐前端约定（camelCase）
- [ ] router 已在 main.py include
- [ ] 无 console.error / logger.error
- [ ] 代码质量：函数 ≤ 50 行，无死代码

