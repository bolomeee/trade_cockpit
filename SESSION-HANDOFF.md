# SESSION-HANDOFF.md

> 更新时间：2026-04-26
> 阶段：F206-b2 Sprint Contract 已确认（contract_agreed） → 待 Generator 模式开发

---

## 当前状态

**Pipeline 位置**：F206-b2 Sprint Contract 协商完成，5 个开放问题全部按默认值确认

**分支**：`cockpit`
**最新 commit**：`709fc2a` chore: update SESSION-HANDOFF for F206-b1 needs_review
**未提交**：`backend/uv.lock`（M）+ 新增 `docs/开发/sprint-contracts/F206-a-contract.md` / `F206-b1-contract.md` / `F206-b2-contract.md`（??）

**v1.9 Cockpit P1 开发计划**：
1. **F206 Position Manager**
   - ✅ **F206-a Position 后端**（needs_review，待合并验收）
   - ✅ **F206-b1 PendingOrder 后端**（needs_review，待合并验收）
   - 📋 **F206-b2 Risk Summary + APScheduler EXPIRED**（contract_agreed，下一步开发）
   - ⬜ **F206-c 前端两 Widget + Form Dialog**（待 b2 完成）
2. F205 Pool Builder Widget（待 F206 整体完成后开工）
3. F207 Daily Action List Widget（依赖 F206 + F202 ✅）

---

## F206-b2 Sprint Contract 摘要

**契约文件**：`docs/开发/sprint-contracts/F206-b2-contract.md`

**实现范围**：
1. `GET /api/cockpit/positions` 响应增 `summary` 字段（5 数值字段，按 API-CONTRACT.md line 1408-1413 口径）
2. APScheduler 周一-周五 22:35 UTC tick：扫描 ACTIVE pending_orders，`expiration_date < today` → EXPIRED

**Summary 5 字段口径**（始终基于 OPEN/ACTIVE，与 query.status 解耦）：
- `openRiskPct` = Σ (entry-stop) × shares / account_size × 100（OPEN positions）
- `totalExposurePct` = Σ position_value / account_size × 100（OPEN positions）
- `pendingRiskPct` = Σ (entry-stop) × shares / account_size × 100（ACTIVE pending_orders）
- `positionsCount` = OPEN 行数
- `pendingCount` = ACTIVE 行数（不含 TRIGGERED/CANCELLED/EXPIRED）

**5 个开放问题确认**：
| Q | 决策 |
|---|------|
| Q1 | summary 与 ?status= **解耦** |
| Q2 | EXPIRED cron 用**常量**（不加 env） |
| Q3 | `list_positions` 返回 **tuple[summary, items]** |
| Q4 | cron = `"35 22 * * 1-5"` UTC（weekdays 22:35） |
| Q5 | account_size 默认值 = **100000.0**（已 grep 确认） |

**待修改文件清单（7 个：5 业务 + 2 测试，符合 6 文件原则）**：

| # | 文件 | 类型 |
|---|------|------|
| 1 | `backend/app/schemas/cockpit/position.py` | 修改（+25 行：PositionSummary + _PositionListData.summary） |
| 2 | `backend/app/services/cockpit/position_service.py` | 修改（+70 行：_compute_summary + list_positions 返回 tuple） |
| 3 | `backend/app/routers/cockpit/positions.py` | 修改（+3 行：适配 tuple） |
| 4 | `backend/app/services/cockpit/pending_order_expirer.py` | 新建（~40 行） |
| 5 | `backend/app/services/refresh_job.py` | 修改（+30 行：注册 _pending_orders_expirer_tick） |
| 6 | `backend/tests/test_position_summary_f206b2.py` | 新建（§A 14 用例） |
| 7 | `backend/tests/test_pending_order_expirer_f206b2.py` | 新建（§B 10 用例） |

---

## 开发顺序（Generator 模式严格按此执行）

1. ✅ **grep account_size 默认值**（已完成 = 100000.0）
2. **修改 schema** `position.py`：新增 `PositionSummary` + 改 `_PositionListData` 含 `summary` 字段
   - **关键**：grep `_PositionListData(` 找到 F206-a/b1 显式构造点（router + 测试），补 `summary=...` 参数
   - → wip commit `wip(F206-b2): schema PositionSummary`
3. **新建 `pending_order_expirer.py`** + §B 前 8 用例（纯函数测试）
   - → wip commit `wip(F206-b2): expirer + unit tests`
4. **修改 `refresh_job.py`** 注册 expirer tick + §B 后 2 用例（scheduler 注册 + tick 异常捕获）
   - → wip commit `wip(F206-b2): scheduler tick`
5. **修改 `position_service.py`** 增 `_compute_summary` + 改 `list_positions` 返回 tuple
   - 跑 F206-a §D 集成测试确保不破
   - → wip commit `wip(F206-b2): summary aggregation`
6. **修改 `routers/cockpit/positions.py`** 适配 tuple 签名 + §A 14 用例（含 GET 集成）
   - → wip commit `wip(F206-b2): router + §A tests`
7. **全量回归** `uv run pytest` → 确认 ≥722 pass + F206-a/b1 全绿
8. Evaluator 自检（自检清单 + 代码质量 + 回归测试）
9. 通过即最终 commit `feat(F206-b2): risk summary + pending order expirer`，phase → needs_review

---

## 测试门禁

- §A 14 + §B 10 = 24 新用例，100% pass
- 全量回归：698（b1 末）+ 24 = ≥722 pass
- F206-a 35 + F206-b1 41 = 76 既有用例必须仍全绿
- mypy / ruff 无新增 warning

---

## 未决事项

- F206-a / b1 / b2 三者均处于 needs_review 路径，**不单独验收**
- F206-b2 完工后由 acceptance skill 起草合并验收脚本（含 curl 创建 OPEN/ACTIVE/EXPIRED 三态 + 验证 summary + 手动调用 expirer）
- 待提交：本 session 仅产生 contract 文档与 handoff 更新，无代码改动；Generator session 开始时一并 commit `chore: update SESSION-HANDOFF for F206-b2 contract_agreed` + 三个 contract 文件

---

## 下一 session 恢复指令

```
继续开发 F206-b2，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F206-b2-contract.md，
进入 Generator 模式，从开发步骤 2 开始（步骤 1 已完成：account_size 默认值 = 100000.0）。
```

**建议用 Sonnet 开启新 session**（小切片任务，无新模型/迁移/外部 IO，0.5-1 session 可完工）。
