# SESSION-HANDOFF — F216 a/b/c1/c2 全部验收通过，下一步 F216-d 设计

> 生成时间：2026-05-14
> 当前分支：improve_against_plan
> 父 feature：F216 Cockpit Phase B — Weekly Stage Layer（in_progress）
> 本次完成：F216-b 验收 → done（累计 a/b/c1/c2 全部 done）

---

## 1. F216 sub_sprints 当前状态

| sub_sprint | phase | 内容 | commit |
|------------|-------|------|--------|
| F216-a | **done** | WeeklyChartService（weekly bars 聚合 + MA10/30/40） | 6e86e75 |
| F216-b | **done** | WeeklyStageService.classify（numpy OLS）+ weekly_stage_snapshots | ab6a16b |
| F216-c1 | **done** | GET /api/cockpit/chart/{ticker}/weekly endpoint | e87a08c |
| F216-c2 | **done** | WeeklyStageChartWidget 前端 | 0f7d7c9 |
| F216-d | design_needed | setup_service gate + setup_snapshots 加列 + 前端 WS 列 | — |
| F216-e | design_needed | scheduler cron 22:20 UTC | — |

C1 invariant：父 F216 保持 `in_progress`（d/e 仍 design_needed）。

---

## 2. F216-b 验收摘要（本次）

- 17/17 pytest 通过（合约要求 13 条）
- numpy OLS slope 三组 fixture：上行/下行/常数全验证
- live API：AMZN Stage 2 (slope +0.67%/w)、MSFT Stage 4 (slope -0.72%/w)
- 全量回归 1001 passed，无新增失败
- numpy 隔离在 weekly_stage_service.py（grep 确认）
- 验收记录：docs/验收/v2.0-F216-b-acceptance.md

---

## 3. 下一步：F216-d Sprint Contract 协商

**F216-d 功能**：setup_service gate — Stage 必须 ≥ 2 才允许 `ready_signal=true`。

**预估范围（≤ 6 文件）**：

| 文件 | 改动类型 |
|------|---------|
| `backend/app/services/cockpit/setup_service.py` | 修改：接入 WeeklyStageRepository，`compute_for_ticker` 加 weekly_stage 门禁 |
| `backend/alembic/versions/020_f216d_setup_snapshots_weekly_stage.py` | 新建：setup_snapshots 加 weekly_stage INT 列（DEFAULT 0） |
| `backend/tests/test_setup_service_weekly_gate.py` | 新建：gate 测试（stage<2 → ready_signal=false） |
| `frontend/src/cockpit/widgets/SetupMonitorWidget.tsx` | 修改：Setup Monitor 表格加 WS 列（显示周线 stage 数字） |
| `frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx` | 修改：追加 WS 列测试 |

**启动 F216-d 的指令**：
```
准备开发 F216-d。读取 SESSION-HANDOFF.md 了解当前状态。
F216-b/c1/c2 均已验收 done，F216-d = setup_service gate（Stage ≥ 2 门禁）。
触发 feature-dev skill 协商 F216-d Sprint Contract。
```

---

## 4. 重要技术细节

- **uvicorn 启动**：从 `backend/` 目录运行 `uv run uvicorn app.main:app --reload --port 8001`
- **WeeklyStageRepository 已可用**：`get_latest_for_tickers(tickers)` 返回 `{ticker: WeeklyStageSnapshot}`，供 F216-d 的 setup_service 批量读取
- **WEEKLY_STAGE params**：`MIN_WEEKS_FOR_CLASSIFICATION=30`，数据不足时 stage=0，setup gate 看 0 即 `ready_signal=false`
- **setup_snapshots 加列**：F216-d 需要新建 alembic 020，在 `setup_snapshots` 表追加 `weekly_stage INT NOT NULL DEFAULT 0`

---

## 5. 验收记录文件

| 文件 | 内容 |
|------|------|
| docs/验收/v2.0-F216-b-acceptance.md | F216-b 验收记录（本次） |
| docs/验收/v2.0-F216-c-acceptance.md | F216-c1+c2 联合验收记录 |
