# SESSION-HANDOFF — F216-d1 ✅ done，下一步 F216-d2 Contract 协商

> 生成时间：2026-05-14
> 当前分支：improve_against_plan
> 父 feature：F216 Cockpit Phase B — Weekly Stage Layer（in_progress）
> 当前阶段：F216-d1 ✅ done；下一个 active_sprint = F216-d2（design_needed）

---

## 1. F216-d1 完成摘要

**已提交 commits**：
- `37c4c20` — `wip(F216-d1): alembic 020 + setup_snapshot weekly_stage column`
- `9fe4ce4` — `feat(F216-d1): setup_snapshots add weekly_stage column for stage gate`

**已落地**：
- `setup_snapshots.weekly_stage` (INTEGER NULL) 列
- `SetupSnapshot.weekly_stage: Mapped[int | None]`
- `DATA-MODEL.md` §SetupSnapshot 字段表 weekly_stage 行（业务规则段未提前写门禁）

**验收记录**：`docs/验收/v2.0-F216-d1-acceptance.md`

---

## 2. 下一步：F216-d2 Contract 协商

### 范围（来自父 feature sub_sprint_notes + SESSION-HANDOFF）

| 文件 | 改动类型 |
|------|---------|
| `backend/app/services/cockpit/setup_service.py` | 修改：`compute_and_store_all` 取 weekly_stage_snapshots 注入 weekly_stage；`_compute_ready_signal` 加 stage==2 强制门禁；`_row_to_dict` 输出 weeklyStage |
| `backend/app/schemas/cockpit/setup.py` | 修改：`SetupItemResponse` 加 `weeklyStage: int | None` |
| `backend/app/services/cockpit/cockpit_params.py` | 修改：加 `READY_REQUIRE_STAGE2 = True`（或类似 flag） |
| `backend/tests/test_setup_f202a.py` | 修改：API 响应字段断言加 weeklyStage；ready_signal=True 的测试用例新增 weekly_stage==2 的 mock |
| `docs/系统设计/API-CONTRACT.md` | 修改：§setup-monitor 响应 items[] 加 weeklyStage 字段 |
| `docs/系统设计/DATA-MODEL.md` | 修改：业务规则段 ready_signal 描述追加 weekly_stage==2 门禁（D093） |
| `docs/系统设计/DECISIONS.md` | 修改：追加 D093（weekly_stage 作为 ready_signal 强制门禁的决策与权衡） |

**预计 6-7 文件**，接近 6 文件上限，若测试文件算单独则恰好 6。

### 关键设计决策待协商

- **D093 门禁设计**：weekly_stage==2 是 hard gate（False when NULL/0/1/3/4）还是 soft gate（NULL 时不扣分、cron 未跑时不降级）？
- **`_row_to_dict` weeklyStage 输出**：`int | None` 直传前端（NULL 显示为 null），前端 d3 再处理列显示
- **现有 test_setup_f202a.py 修改幅度**：`ready_signal=True` 的 mock 需加 weekly_stage=2，对应修改 3-5 个测试用例
- **cockpit_params.py flag 或直接 hardcode**？（Sprint Contract 层面决定）

---

## 3. 父 feature F216 子 sprint 状态

| Sub-sprint | 名称 | 状态 |
|------------|------|------|
| F216-a | Weekly Aggregation Service | ✅ done |
| F216-b | Stage Classifier + DB | ✅ done |
| F216-c1 | Router + Stage Payload | ✅ done |
| F216-c2 | Widget + Registry | ✅ done |
| F216-d1 | setup_snapshots schema col | ✅ done（本次）|
| **F216-d2** | **service gate + API** | **⬜ design_needed（下一个）** |
| F216-d3 | 前端 WS 列 | ⬜ design_needed |
| F216-e | Scheduler cron | ⬜ design_needed |

---

## 4. 关键引用

| 文档 | 路径 | 用途 |
|------|------|------|
| Feature 注册 | `docs/需求/features.json` F216 | 状态追踪 |
| 上一个 Sprint Contract | `docs/开发/sprint-contracts/F216-d1-contract.md` | d1 参考 |
| DATA-MODEL §SetupSnapshot | `docs/系统设计/DATA-MODEL.md` L426-479 | d2 要修改业务规则段 |
| API-CONTRACT §setup-monitor | `docs/系统设计/API-CONTRACT.md` | d2 要追加 weeklyStage |
| SetupService | `backend/app/services/cockpit/setup_service.py` | d2 主要修改对象 |
| SetupItemResponse | `backend/app/schemas/cockpit/setup.py` | d2 schema 改动 |
| cockpit_params | `backend/app/services/cockpit/cockpit_params.py` | d2 flag 改动 |
| 完整改善计划 §B4 | `/Users/wonderer/.claude/plans/featrue-dev-replicated-goblet.md` | 设计意图 |

---

## 5. 恢复指令

> F216-d1 已完成验收（done）。读取 SESSION-HANDOFF.md，开始 F216-d2 Sprint Contract 协商（setup_service ready_signal 门禁 + weekly_stage==2 + API 暴露 weeklyStage）。
