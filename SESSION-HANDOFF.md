# SESSION-HANDOFF — F216-c1 完成（needs_review）

> 生成时间：2026-05-14
> 当前分支：improve_against_plan
> 父 feature：F216 Cockpit Phase B — Weekly Stage Layer（in_progress）

---

## 本 session 完成内容

### F216-c1 — GET /api/cockpit/chart/{ticker}/weekly（后端）

**Generator 阶段（21 步全部完成）**：

1. DATA-MODEL.md WeeklyStageSnapshot 字段已确认（去掉 id/computed_at，7 字段对齐）
2. API-CONTRACT.md 已包含 GET /api/cockpit/chart/{ticker}/weekly 子节
3. 无 schema 变更（不新建表，不动 WeeklyStageSnapshot）
4. 新建 3 个 schema：`WeeklyStagePayload` / `WeeklyChartData` / `WeeklyChartResponse`
5. 追加 `CockpitChartWeeklyParams §7` + `CHART_WEEKLY` 单例（MIN=10 / MAX=50）
6. WIP commit 1：`ca8486b wip(F216-c1): schema + cockpit_params CHART_WEEKLY`
7. Router 追加 `GET /{ticker}/weekly`（pure compute：调 classify，不写 DB）
8. WIP commit 2：`df443b8 wip(F216-c1): router GET /weekly endpoint`
9. 集成测试 7/7 全通过（标准 1-9）
10. WIP commit 3：`2b8d803 wip(F216-c1): integration tests for GET /weekly`
11. API-CONTRACT.md 子节追加（包含 slope30W 大写 W 的正确 camelCase）
12. 全量回归：1001 passed，12 failed 全部预先存在（非本 sprint 引入）
13. Evaluator 自检全清
14. consistency-check C1/C4/C5 全清（exit=0）
15. F216-c1 sub_sprints → needs_review

**关键发现**：
- `slope_30w` 经 pydantic `to_camel` 转换为 `slope30W`（大写 W），因 `capitalize()` 将 `w` 大写。测试和 API-CONTRACT.md 均已使用正确大写。

---

## 已修改文件（5 文件 Contract + features.json + claude-progress.txt + SESSION-HANDOFF.md）

| 文件 | 改动 |
|------|------|
| `backend/app/schemas/cockpit/chart.py` | 追加 WeeklyStagePayload / WeeklyChartData / WeeklyChartResponse |
| `backend/app/services/cockpit/cockpit_params.py` | 追加 §7 CockpitChartWeeklyParams + CHART_WEEKLY |
| `backend/app/routers/cockpit/chart.py` | 追加 _get_weekly_*_service Depends + GET /{ticker}/weekly route |
| `backend/tests/test_cockpit_chart_weekly_router.py` | 新建，7 条集成测试 |
| `docs/系统设计/API-CONTRACT.md` | 新增 GET /weekly 子节（路径/参数/响应/错误） |

---

## 当前功能状态

```
F216 Phase B Weekly Stage Layer：🔄 in_progress
  ├─ F216-a Weekly Aggregation Service:  ✅ done (commit 6e86e75)
  ├─ F216-b Stage Classifier + DB:       🔍 needs_review (commit ab6a16b)
  ├─ F216-c1 Router + Stage Payload:     🔍 needs_review  ← 本次完成
  ├─ F216-c2 Widget + Registry:          ⬜ design_needed
  ├─ F216-d setup_service gate:          ⬜ design_needed
  └─ F216-e Scheduler cron:              ⬜ design_needed
```

---

## 未决事项

1. **预先存在的测试失败（12 个，非本 sprint 引入）**：
   - `test_regime_f201a.py::test_s14_cockpit_params_import_no_exception`（INDEX_ETFS 4≠3 — VXX 后加）
   - Alembic schema 相关测试（环境问题）
   - 其余 AI/FMP 客户端测试
   - 这些不阻塞 F216-c1 的 needs_review 流转

2. **`test_decision_f203b.py`（untracked）**：引用不存在的 `DecisionService`，收集阶段就报错。与 F216-c1 无关。

---

## 下一步选项

### 选项 A：继续 F216-c2（前端 widget）
> 直接进入 F216-c2 Sprint Contract 协商

```
准备开发 F216-c2，需要协商 Sprint Contract。
读取 SESSION-HANDOFF.md，F216-c1 已完成（needs_review），
现在进行 F216-c2 前端 widget Sprint Contract 协商。
```

预计 4 文件：
- `src/workbench/widgets/WeeklyStageChartWidget.tsx`（新建）
- `src/api/cockpit/weeklyChart.ts`（新建 API client）
- `src/workbench/WidgetRegistry.ts`（修改，注册 widget）
- `src/workbench/layouts/cockpit.json`（修改，加 widget slot）

### 选项 B：先完成 F216-b acceptance
> F216-b 已在 needs_review，可先验收再继续 c2

```
验收 F216-b（Weekly Stage Classifier + DB），needs_review 状态。
```

### 选项 C：Final commit 收尾 + 开新 session
> 当前 WIP commits 可 final commit，然后开新 session 继续 c2

---

## 启动下个 Session 指令（F216-c2）

> **F216-c2 Sprint Contract 协商**（建议 Sonnet）：
>
> 读取 SESSION-HANDOFF.md，F216-c1 已完成（needs_review）。
> 现在准备开发 F216-c2：前端 WeeklyStageChart Widget。
> 进行 F216-c2 Sprint Contract 协商，从预计修改文件清单开始。
