# SESSION-HANDOFF.md

> 更新时间：2026-04-26
> 阶段：F206-b2 needs_review → F206 整体等待合并验收

---

## 当前状态

**Pipeline 位置**：F206-b2 Generator → Evaluator → needs_review ✅

**分支**：`cockpit`
**最新 commit**：`6c502ae` feat(F206-b2): risk summary + pending order expirer
**未提交**：无（仅 `backend/uv.lock` M，无关）

**v1.9 Cockpit P1 开发计划**：
1. **F206 Position Manager**
   - ✅ **F206-a Position 后端**（needs_review，待合并验收）
   - ✅ **F206-b1 PendingOrder 后端**（needs_review，待合并验收）
   - ✅ **F206-b2 Risk Summary + APScheduler EXPIRED**（needs_review，待合并验收）
   - ⬜ **F206-c 前端两 Widget + Form Dialog**（下一步）
2. F205 Pool Builder Widget（待 F206 整体完成后开工）
3. F207 Daily Action List Widget（依赖 F206 + F202 ✅）

---

## F206-b2 完成摘要

**实现内容**：
1. `GET /api/cockpit/positions` 响应增 `summary` 字段（5 数值字段）
2. APScheduler 周一-周五 22:35 UTC tick：扫描 ACTIVE pending_orders，`expiration_date < today` → EXPIRED

**测试结果**：
- §A 14 + §B 10 = 24 新用例，100% pass
- 全量回归：722/722 pass（698 + 24）
- F206-a 35 + F206-b1 41 = 76 既有用例全绿
- mypy / ruff 无新增 warning

**修改文件（7 个）**：

| 文件 | 类型 |
|------|------|
| `backend/app/schemas/cockpit/position.py` | 修改（+PositionSummary + _PositionListData.summary） |
| `backend/app/services/cockpit/position_service.py` | 修改（+_compute_summary + tuple 返回）|
| `backend/app/routers/cockpit/positions.py` | 修改（适配 tuple） |
| `backend/app/services/cockpit/pending_order_expirer.py` | 新建 |
| `backend/app/services/refresh_job.py` | 修改（+EXPIRED cron 常量 + tick） |
| `backend/tests/test_position_summary_f206b2.py` | 新建（§A 14 用例） |
| `backend/tests/test_pending_order_expirer_f206b2.py` | 新建（§B 10 用例） |

**关键决策（已按 contract 执行）**：
- Q1：summary 与 `?status=` 解耦（始终基于 OPEN/ACTIVE 快照）
- Q2：EXPIRED cron 用常量（不加 env）
- Q3：`list_positions` 返回 `tuple[PositionSummary, list[PositionItem]]`
- Q4：cron = `"35 22 * * 1-5"` UTC
- Q5：account_size 默认值 = 100000.0

---

## 下一步：F206 整体合并验收

F206-a / b1 / b2 三者均处于 needs_review，**不单独验收，统一合并验收**。

### 合并验收脚本（手动 curl 验证思路）

```bash
# 1. 创建 1 OPEN position
curl -X POST http://localhost:8000/api/cockpit/positions \
  -H "Content-Type: application/json" \
  -d '{"ticker":"NVDA","entryPrice":850,"entryDate":"2026-04-01","shares":33,"stopPrice":820}'

# 2. 创建 1 ACTIVE pending_order
curl -X POST http://localhost:8000/api/cockpit/pending-orders \
  -H "Content-Type: application/json" \
  -d '{"ticker":"AAPL","setupType":"BREAKOUT","entryPrice":180,"stopPrice":173,"shares":40}'

# 3. GET positions → 验证 data.summary 5 字段
curl http://localhost:8000/api/cockpit/positions | python3 -m json.tool

# 4. 创建 1 ACTIVE pending_order，expiration_date=昨天 → 手动调用 expirer
# 验证 PATCH /pending-orders/{id} 后 status=EXPIRED

# 5. 验证 APScheduler 含 cockpit_pending_orders_expirer job：
# GET http://localhost:8000/api/refresh/status 或查看 log
```

### 验收要点
- `data.summary.openRiskPct` = `(850-820)*33/100000*100` = **0.99**
- `data.summary.pendingRiskPct` = `(180-173)*40/100000*100` = **0.28**
- `data.summary.positionsCount` = **1**，`pendingCount` = **1**
- `GET ?status=all` → summary 不变（Q1 解耦验证）
- expiration_date=昨天的 ACTIVE order → `expire_due_pending_orders(db)` 后 status=EXPIRED

---

## 后续：F206-c 前端 Widget

F206-c 包含：
- **Position Widget**：Open Positions 表（ticker/entry/last/stop/R/size/unrealized P&L/earnings/next action）+ Risk Summary 顶条（5 字段）
- **PendingOrder Widget**：条件单列表（ticker/setup/entry/stop/risk/expiration/distance/status）+ Form Dialog（录入/编辑）

F206-c 需新协商 Sprint Contract，不在本 session 范围。

---

## 下一 session 恢复指令

### 若要验收 F206（整体）：
```
F206-a / b1 / b2 三个后端 sub-task 都已完成（needs_review）。
触发 acceptance skill，起草 F206 后端合并验收文档。
读取 SESSION-HANDOFF.md 获取验收脚本。
```

### 若要继续 F206-c 前端：
```
F206-b2 已完成（needs_review）。继续 F206-c 前端 Widget 开发。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/（如已有 F206-c contract）。
```
