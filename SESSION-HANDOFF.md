# SESSION-HANDOFF — F216-c 验收通过，下一步 F216-b 验收或 F216-d 设计

> 生成时间：2026-05-14
> 当前分支：improve_against_plan
> 父 feature：F216 Cockpit Phase B — Weekly Stage Layer（in_progress）
> 本次完成：F216-c1 + F216-c2 **联合验收 → done**

---

## 1. 本次验收摘要

**F216-c1**（GET /api/cockpit/chart/{ticker}/weekly）验收通过：
- 7/7 pytest 集成测试通过
- Pure compute 策略：无 DB 副作用（test_7 确认）
- API 响应 schema 正确（camelCase alias + WeeklyStagePayload）

**F216-c2**（WeeklyStageChartWidget）验收通过：
- 22/22 vitest 通过（S4 × 4 API client + standards 6-12 × 9 widget）
- 浏览器截图留证：
  - Stage 2：AMZN · Stage 2 · Advancing，绿色 header `rgb(16, 185, 129)`
  - Stage 4：MSFT · Stage 4 · Declining，红色 header `rgb(239, 68, 68)`
- 无 console.error，全量回归无新增失败

---

## 2. F216 sub_sprints 当前状态

| sub_sprint | phase | 备注 |
|------------|-------|------|
| F216-a | done | commit 6e86e75 — WeeklyChartService |
| F216-b | needs_review | commit ab6a16b — WeeklyStageService.classify + numpy + DB |
| F216-c1 | **done** | commit e87a08c — GET /weekly endpoint |
| F216-c2 | **done** | commit 0f7d7c9 — WeeklyStageChartWidget |
| F216-d | design_needed | setup_service gate + setup_snapshots 加列 + 前端 WS 列 |
| F216-e | design_needed | scheduler cron 22:20 UTC |

C1 invariant：父 F216 status 保持 `in_progress`（b needs_review，d/e design_needed）。

---

## 3. 下一步选项

### 选项 A：验收 F216-b（推荐先做）
F216-b（WeeklyStageService）目前是 needs_review，应在 F216-d 协商前确认其分类逻辑正确。

**启动指令**：
```
触发 acceptance skill，对 F216-b 做验收。
F216-b commit ab6a16b — WeeklyStageService.classify + numpy + weekly_stage_snapshots 表。
```

### 选项 B：协商 F216-d Sprint Contract
setup_service gate 设计：Stage 必须 ≥ 2 才允许 `ready_signal=true`。

**F216-d 范围预估**：
- `backend/app/services/cockpit/setup_service.py`（修改）：weekly_stage 门禁
- `backend/alembic/versions/XXX_setup_snapshots_weekly_stage.py`（新建）：加列
- `backend/tests/test_setup_service_weekly_gate.py`（新建）：新门禁测试
- `frontend/src/cockpit/widgets/SetupMonitorWidget.tsx`（修改）：新增 WS 列
- ≤ 4-5 文件，符合 6 文件原则

---

## 4. 重要技术细节

- **uvicorn 启动方式**：从 `backend/` 目录运行 `uv run uvicorn app.main:app --reload --port 8001`（从项目根目录运行会找不到 uvicorn）
- **localStorage 布局**：清 `ma150.cockpit.layouts.v1` 后刷新可见新 widget；验收时曾临时修改 layout 让 Weekly Stage 移到顶部截图
- **camelCase 字段**：`slope30W`（W 大写）、`weeklyMa10/30/40`、`scanDate`、`weeklyClose`、`weeklyBars`、`weeklyMas`
- **NP8 follow-up**：spawn_task 已记录 `_chartHelpers.ts` 抽取（toTs/readToken/MA_TOKENS 在两个 widget 重复）

---

## 5. 文件变更记录（本 session）

| 文件 | 操作 |
|------|------|
| `docs/验收/v2.0-F216-c-acceptance.md` | 新建（本次验收记录） |
| `docs/需求/features.json` | F216-c1/c2 → done，pipeline active_sprint → F216-d |
| `claude-progress.txt` | 追加验收完成记录 |
| `SESSION-HANDOFF.md` | 本文件更新 |
