# SESSION-HANDOFF.md

> 更新时间：2026-04-26
> 阶段：F206-b1 needs_review → 待 F206-b2 Sprint Contract 协商

---

## 当前状态

**Pipeline 位置**：F206-b1 Generator + Evaluator 全部通过，phase = needs_review

**分支**：`cockpit`
**最新 commit**：`d307408` feat(F206-b1): PendingOrder 数据层 + CRUD

**v1.9 Cockpit P1 开发计划**（按优先序）：
1. **F206 Position Manager**
   - ✅ **F206-a Position 后端**（needs_review，待合并验收）
   - 🔍 **F206-b1 PendingOrder 后端**（needs_review，本次完成）
   - ⬜ **F206-b2** Risk Summary 聚合 + APScheduler EXPIRED（下一步）
   - ⬜ **F206-c** 前端两 Widget + Form Dialog（待 b2 完成）
2. F205 Pool Builder Widget（待 F206 整体完成后开工）
3. F207 Daily Action List Widget（依赖 F206 + F202 ✅）

---

## F206-b1 完成摘要

**目标达成**：PendingOrder 完整后端 CRUD（4 endpoints + 实时计算字段 + 状态机）

**关键成果**：

| 层 | 文件 | 状态 |
|----|------|------|
| Migration | `alembic/versions/014_f206b1_pending_orders.py` | ✅ |
| ORM | `app/models/pending_order.py` | ✅ |
| 共享重构 | `app/services/cockpit/last_close_loader.py` | ✅ |
| Repository | `app/repositories/pending_order_repository.py` | ✅ |
| Schema | `app/schemas/cockpit/pending_order.py` | ✅ |
| Service | `app/services/cockpit/pending_order_service.py` | ✅ |
| Router | `app/routers/cockpit/pending_orders.py` | ✅ |
| 测试 | §A(12) + §B(5) + §C(12) + §D(12) = **41 用例** | ✅ |
| 全量回归 | **698/698**（657→698） | ✅ |
| Ruff lint | 无新增 warning | ✅ |

**4 个 API Endpoints**（全部可用）：
```
GET    /api/cockpit/pending-orders?status=active|all|ACTIVE|TRIGGERED|CANCELLED|EXPIRED
POST   /api/cockpit/pending-orders  → 201
PATCH  /api/cockpit/pending-orders/{id}
DELETE /api/cockpit/pending-orders/{id}
```

**实时计算字段**：
- `lastClose` — LastCloseLoader（D041 daily_bars → FMP fallback）
- `distanceToTriggerPct` = `(entry - lastClose) / lastClose × 100`，2 位小数，lastClose=null 时 null
- `riskPct` = `(entry - stop) × shares / account_size × 100`，2 位小数，不依赖市价

**状态机**：
- ACTIVE → {TRIGGERED, CANCELLED, EXPIRED}：允许
- ACTIVE → ACTIVE：允许（同状态修订字段）
- 终态 → 任何状态变更：422（包括互转）

**last_close_loader 重构**（Q1 落地）：
- 新建 `last_close_loader.py`，`PositionService` 和 `PendingOrderService` 共享
- F206-a 的 35 测试用例全部仍绿（回归保险通过）

---

## F206-b2 Sprint 目标（下一步）

**范围**：Risk Summary 聚合顶条 + APScheduler EXPIRED 自动转换

**核心内容**（来自原 F206-b 拆分方案）：
1. `GET /api/cockpit/positions` 响应添加 `summary` 字段（聚合 positions + pending_orders 的统计摘要）
2. APScheduler 定时任务：每日盘后检查 `expiration_date < today` 的 ACTIVE pending_orders → 自动转为 EXPIRED
3. 预计影响文件 9 个（含 scheduler 注册、聚合 service、修改 positions router）

**验收节点**：F206-b2 完成后，与 F206-a + F206-b1 合并验收（完整 PendingOrder 链路 + summary 顶条）

---

## 未决事项

- F206-a 和 F206-b1 均处于 needs_review，**不单独验收**，等 F206-b2 完工后合并验收
- F206-b2 Sprint Contract 需要新 session 协商（估计 9 文件，可在 6 文件原则限制内单 sprint 完成）

---

## 下一 session 恢复指令

```
读取 SESSION-HANDOFF.md，开始 F206-b2 Sprint Contract 协商。
F206-b1 已完成（needs_review），目标是 Risk Summary 聚合顶条 + APScheduler EXPIRED 自动转换。
```
