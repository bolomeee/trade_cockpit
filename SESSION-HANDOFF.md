# SESSION-HANDOFF.md

> 更新时间：2026-04-26
> 阶段：F206-a needs_review → 准备 F206-b

---

## 当前状态

**Pipeline 位置**：F206-a 开发完成，等待用户验收（needs_review）

**分支**：`cockpit`
**最新 commit**：`7cdd33d` feat(F206-a): Position 数据层 + CRUD

**v1.9 Cockpit P1 开发计划**（按优先序）：
1. **F206 Position Manager**
   - ✅ **F206-a Position 后端**（`needs_review`，等待验收）
   - ⬜ F206-b PendingOrder 后端 + Summary 聚合（待 a 验收后开工）
   - ⬜ F206-c 前端两 Widget + Form Dialog（待 b 完成）
2. F205 Pool Builder Widget（待 F206 后开工）
3. F207 Daily Action List Widget（依赖 F206 + F202 ✅）

---

## F206-a 完成内容摘要

**目标**：Position 数据层 + 后端 CRUD（4 endpoints + 实时计算字段），不含 PendingOrder / Summary / 前端

**交付文件（14 个）**：
| 文件 | 类型 |
|------|------|
| `backend/alembic/versions/013_f206a_positions.py` | 新建 |
| `backend/app/models/position.py` | 新建 |
| `backend/app/models/__init__.py` | 修改 |
| `backend/app/repositories/position_repository.py` | 新建 |
| `backend/app/schemas/cockpit/position.py` | 新建 |
| `backend/app/services/cockpit/position_service.py` | 新建 |
| `backend/app/services/cockpit/position_action_rules.py` | 新建 |
| `backend/app/services/cockpit/position_sizer.py` | 新建 |
| `backend/app/routers/cockpit/positions.py` | 新建 |
| `backend/app/routers/cockpit/__init__.py` | 修改 |
| `backend/tests/test_position_f206a_schema.py` | 新建（§A 8 用例）|
| `backend/tests/test_position_f206a_repo.py` | 新建（§B 5 用例）|
| `backend/tests/test_position_f206a_service.py` | 新建（§C 12 用例）|
| `backend/tests/test_position_f206a_integration.py` | 新建（§D 10 用例）|

**测试结果**：
- F206-a 专项：35/35 ✅
- 全量回归：657/657 ✅（原 627 + 新增 30）

**4 个 API Endpoints**：
- `GET /api/cockpit/positions?status=open|closed|all`
- `POST /api/cockpit/positions` → 201
- `PATCH /api/cockpit/positions/{id}`
- `DELETE /api/cockpit/positions/{id}`

**关键实现约定**（F206-b 需继承）：
- D041 last_close fallback：watchlist → `daily_bars` 批量 SQL；非 watchlist → 串行 FMP，失败降级 null
- `position_action_rules.compute_next_action()` — F207 可直接 import 同一函数
- `position_sizer.compute_shares()` — D066 公式
- D074 camelCase：Pydantic `to_camel` alias_generator，snake_case 字段对应 DB 层

---

## 用户验收指令（F206-a）

按 `docs/系统设计/API-CONTRACT.md §Cockpit Positions` 验收：

```bash
# 启动后端
cd backend && uv run uvicorn app.main:app --reload

# POST 创建 watchlist position（如 NVDA 在 watchlist）
curl -X POST http://localhost:8000/api/cockpit/positions \
  -H "Content-Type: application/json" \
  -d '{"ticker":"NVDA","entryPrice":850,"entryDate":"2026-04-01","shares":33,"stopPrice":820,"setupType":"BREAKOUT"}'
# 预期：201，含 id / rMultiple / lastClose / recommendedShares

# GET 列表
curl "http://localhost:8000/api/cockpit/positions?status=open"

# PATCH 移动 stop
curl -X PATCH http://localhost:8000/api/cockpit/positions/{id} \
  -H "Content-Type: application/json" \
  -d '{"stopPrice":830}'

# PATCH status=CLOSED 缺 closedAt → 422
curl -X PATCH http://localhost:8000/api/cockpit/positions/{id} \
  -H "Content-Type: application/json" \
  -d '{"status":"CLOSED"}'

# DELETE
curl -X DELETE http://localhost:8000/api/cockpit/positions/{id}
```

---

## 下一步：F206-b（验收通过后）

**恢复指令**（新 session）：
> F206-a 已完成验收，准备开发 F206-b（PendingOrder 后端 + Risk Summary 聚合）。
> 读取 SESSION-HANDOFF.md，进入 feature-dev Sprint Contract 协商阶段。

**F206-b 预计内容**：
- `pending_orders` 表（Alembic 014）
- PendingOrder ORM / Repo / Schema / Service / Router（对称 F206-a 结构）
- Risk Summary 聚合（`openRiskPct` / `totalExposurePct` / `pendingRiskPct` / counts）
- APScheduler EXPIRED 自动转换

---

## 未决事项

无。Q1–Q4 均已按默认方案落地：
- Q1：不加 fmpErrors 到 response.meta（容错降级）
- Q2：position_sizer.py 新建（已含 unit test）
- Q3：setupType 限定 7 枚举
- Q4：entryDate 不允许未来日期
