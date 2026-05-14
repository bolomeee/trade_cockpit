# SESSION-HANDOFF — F216-d2 完成，等待 acceptance

> 生成时间：2026-05-14
> 当前分支：improve_against_plan
> 父 feature：F216 Cockpit Phase B — Weekly Stage Layer（in_progress）
> 本阶段：F216-d2 done → needs_review（等待 acceptance skill）
> 下一阶段：acceptance → F216-d3（前端 WS 列）

---

## 1. F216-d2 完成摘要

**Sprint**：F216-d2 — Weekly Stage 强制门禁接入 ready_signal（全 8 AND 门）

**实现 7 文件**（NP-A 单 sprint）：

| # | 文件 | 改动 |
|---|------|------|
| 1 | `backend/app/services/cockpit/setup_service.py` | `_compute_ready_signal` 加 `weekly_stage` 参数 + `stage_ok` gate；`__init__` 加 `weekly_stage_repo`；`compute_and_store_all` 开头批量 `get_latest_for_tickers` 取 `stage_map`，inject `weekly_stage_val` 到短数据分支 + 完整数据分支；`_row_to_dict` 加 `weeklyStage` |
| 2 | `backend/app/schemas/cockpit/setup.py` | `SetupItemResponse` 加 `weekly_stage: int \| None = None` |
| 3 | `backend/app/services/cockpit/cockpit_params.py` | §2 SETUP Ready signal 区加 `READY_REQUIRE_STAGE2: bool = True` |
| 4 | `backend/tests/test_setup_f216d2.py` | 新建，28 测试（T1-T8 纯函数 + T9-T13 集成 + T14-T15 row_to_dict + T16 schema）全绿 |
| 5 | `docs/系统设计/API-CONTRACT.md` | §setup-monitor 响应示例加 `weeklyStage` + 字段说明 + readySignal 描述 7→8 |
| 6 | `docs/系统设计/DATA-MODEL.md` | §SetupSnapshot ready_signal 描述 7→8；业务规则段加 Weekly Stage 门禁 bullet |
| 7 | `docs/系统设计/DECISIONS.md` | 追加 D093 |

**测试门禁结果**：
- `test_setup_f216d2.py`：28/28 passed
- `test_setup_f202a.py`：27/27 passed（s10/s11 通过 weekly_stage=2 fixture 修复）
- `test_setup_f202b.py`：全绿
- `test_setup_service_f215b.py`：全绿
- 全量回归：1047 passed（+28 new），7 pre-existing failures（与 my 改动无关）

**Git commits**：
- `0fbe6b7` wip(F216-d2): ready_signal 8th AND gate + stage flag + pure tests
- `ed16eb8` wip(F216-d2): compute_and_store_all join + row_to_dict + integration tests
- `ca665a6` feat(F216-d2): weekly_stage as 8th ready_signal gate（docs sync）

---

## 2. Consistency Check 结果

- C1 ✅ F216 status=in_progress，d2/d3/e 未完成，状态一致
- C4 🟢 F216-d3/F216-e 无 iteration_history（design_needed，预期）
- C5 🟢 F216-d3/F216-e 无合约（design_needed，预期）
- C7 ✅ F216-d2 phase 序列：contract_agreed → needs_review（合法）
- C8 ✅ active_sprint=F216-d2 有效

---

## 3. 当前状态

- `features.json` F216-d2 sub_sprint: `needs_review`
- `features.json` F216.active_sprint_phase: `needs_review`
- 等待 `acceptance` skill 验收

---

## 4. 下一步（新 session）

### 4a. acceptance

```
运行 acceptance skill，验收 F216-d2。
关键验收点：
1. GET /api/cockpit/setup-monitor 响应含 weeklyStage 字段
2. ready_signal=true 标的数量减少（stage != 2 的被过滤掉）
3. weekly_stage_snapshots 表有数据时 row.weekly_stage 正确显示
4. READY_REQUIRE_STAGE2=False 时行为恢复到 7 AND 门
```

### 4b. F216-d3（acceptance 通过后）

前端 WS 列：
- `setupMonitorApi.ts` `SetupItem` 类型加 `weeklyStage?: number | null`
- `SetupMonitorWidget.tsx` 加 "WS" 列渲染 Stage 1-4 标签

### 4c. 生产环境注意事项

- 首次部署前需手动跑 `WeeklyStageService.compute_and_store_all()` 否则所有 ticker 的 weekly_stage=None → ready=False
- 或临时 `READY_REQUIRE_STAGE2=False` 等 cron 跑完再开启

---

## 5. 排除风险备忘

| 风险 | 状态 |
|------|------|
| s10/s11 fixture 破坏 | ✅ 已修复（weekly_stage=2 加入 _ready_kwargs） |
| 短数据分支漏写 weekly_stage | ✅ T12 覆盖，代码 line 409 |
| WeeklyStageRepository get_latest_for_tickers 多 ticker | ✅ T13 覆盖 |
| ready=False 标的暴增 | flag 一键关闭（READY_REQUIRE_STAGE2=False） |
