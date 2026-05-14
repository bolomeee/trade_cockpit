# SESSION-HANDOFF — F216-c2 needs_review → 下一步 acceptance c1+c2

> 生成时间：2026-05-14
> 当前分支：improve_against_plan
> 父 feature：F216 Cockpit Phase B — Weekly Stage Layer（in_progress）
> 本 sprint：F216-c2 **needs_review**（Final commit 待 push）
> 上一 sprint：F216-c1 needs_review（commit e87a08c）

---

## 1. F216-c2 完成摘要

**目标已达成**：WeeklyStageChartWidget 前端实现完整交付。

**6 文件变更（等于 sprint 上限）**：

| # | 文件 | 状态 |
|---|------|------|
| 1 | `frontend/src/cockpit/lib/api/cockpitWeeklyChartApi.ts` | ✅ 新建 |
| 2 | `frontend/src/cockpit/widgets/WeeklyStageChartWidget.tsx` | ✅ 新建 |
| 3 | `frontend/src/cockpit/widgets/__tests__/WeeklyStageChartWidget.test.tsx` | ✅ 新建 |
| 4 | `frontend/src/cockpit/lib/api/__tests__/cockpitApis.test.ts` | ✅ 修改（追加 S4） |
| 5 | `frontend/src/cockpit/CockpitRegistry.ts` | ✅ 修改 |
| 6 | `backend/layouts/cockpit.json` | ✅ 修改 |

**测试结果**：
- vitest F216-c2：22/22 通过（API client S4 × 4 + widget standards 6-12 × 9）
- vitest 全量：预存失败（TopNav/AiNewsSummaryBar/SetupMonitorExplainer）无新增
- pytest 全量：1001 passed（baseline 持平）
- 浏览器 smoke：JD Stage 0 灰底 header（`rgb(107, 114, 128)` = `#6b7280`）+ TradingView chart SVG 渲染；无 console.error

**WIP commits**：
1. e8bd0fc — `wip(F216-c2): cockpitWeeklyChartApi + types`
2. 3a2f14c — `wip(F216-c2): API client tests S4`
3. 05b51b7 — `wip(F216-c2): WeeklyStageChartWidget skeleton`
4. c21f09b — `wip(F216-c2): WeeklyStageChartWidget tests`

**Final commit**（待执行）：`feat(F216-c2): Weekly Stage Chart Widget`

---

## 2. NP1-NP10 拍板落地状态

| NP | 议题 | 落地状态 |
|----|------|---------|
| 1 | Stage 标签 UI | ✅ header 整条 background 跟随 stage 色 + 白字 |
| 2 | 色映射 token | ✅ readToken + STAGE_BG_TOKENS/FALLBACKS（0-4 全覆盖） |
| 3 | ticker 来源 | ✅ `useCockpitStore.selectedTicker` |
| 4 | 默认 weeks | ✅ DEFAULT_WEEKS = 50 |
| 5 | 文案 | ✅ 完全复用 CockpitChartWidget |
| 6 | registry / layout | ✅ id=cockpit.weekly-stage / chart / x=0,y=43,w=6,h=10 |
| 7 | 数据不足 | ✅ weeklyBars.length===0 → "数据不足"；stage=0 → 灰底 |
| 8 | helper 抽取 | ✅ 本 sprint 复制，spawn_task 已记录后续重构 |
| 9 | decision price lines | ✅ 不渲染（无 cockpitDecisionApi import） |
| 10 | stage 文本 | ✅ "Stage N · {Label}"（0-4 全覆盖） |

---

## 3. 下一步任务

### 优先：acceptance c1+c2 联合验收

F216-c1（GET /weekly endpoint）和 F216-c2（WeeklyStageChartWidget）均在 needs_review。

**建议下个 session 启动指令**：
```
触发 acceptance skill，对 F216-c1 和 F216-c2 做联合验收。
读取 SESSION-HANDOFF.md 了解当前状态，两个 sub-sprint 都是 needs_review。
验收重点：
1. 后端需重启 uvicorn（当前运行实例未加载 c1 weekly 路由，touch main.py 触发 reload 即可）
2. 浏览器 /cockpit → Setup Monitor 选 ticker → Weekly Stage widget 出现 + 正确颜色 + chart 渲染
3. screenshot 留证 stage=2/4 各 1 张
```

### 之后：F216-d Sprint Contract 协商

- setup_service gate（Stage 必须=2 才允许 ready_signal=true）
- setup_snapshots 加 weekly_stage 列
- 前端 SetupMonitorWidget 新增 WS 列

---

## 4. 重要技术细节（避免下次踩坑）

- **uvicorn 热重载问题**：dev server 在 F216-c1 合并前启动，`/weekly` 路由未加载。`touch backend/app/main.py` 可强制 reload。长期方案：重启 uvicorn 进程
- **localStorage 布局**：cockpit.json 的 default layout 更新后，浏览器需清 localStorage key `ma150.cockpit.layouts.v1` 才会看到新 widget（`localStorage.removeItem('ma150.cockpit.layouts.v1')`）
- **camelCase 字段**：`slope30W`（W 大写）、`weeklyMa10/30/40`、`scanDate`、`weeklyClose`、`weeklyBars`、`weeklyMas`。tsc 已锁定
- **WeeklyStageChartWidget 主函数 199 行**：接近 200 行上限。NP8 follow-up（抽 `_chartHelpers.ts`）已 spawn_task 记录，后续执行可降至 ~150 行

---

## 5. F216 sub_sprints 当前状态

| sub_sprint | phase | 备注 |
|------------|-------|------|
| F216-a | done | commit 6e86e75 — WeeklyChartService |
| F216-b | needs_review | commit ab6a16b — WeeklyStageService.classify + numpy + DB |
| F216-c1 | needs_review | commit e87a08c — GET /weekly endpoint |
| F216-c2 | needs_review | 本次完成 — WeeklyStageChartWidget |
| F216-d | design_needed | setup_service gate + setup_snapshots 加列 + 前端 WS 列 |
| F216-e | design_needed | scheduler cron 22:20 UTC |

C1 invariant：父 F216 status 必须保持 `in_progress`（d/e 仍 design_needed）。

---

## 6. NP8 follow-up（spawn_task 已记录）

`toTs` / `readToken` / `MA_TOKENS` / `MA_FALLBACKS` 同时存在于 `CockpitChartWidget.tsx` 和 `WeeklyStageChartWidget.tsx`。后续单独 sprint 抽取到 `frontend/src/cockpit/lib/_chartHelpers.ts`。
