# SESSION-HANDOFF — F216-c1 Sprint Contract 已确认（contract_agreed）

> 生成时间：2026-05-14
> 当前 sprint：F216-c1 — Weekly Chart Router + Stage Payload（后端）
> 当前分支：improve_against_plan
> 父 feature：F216 Cockpit Phase B — Weekly Stage Layer（in_progress）

---

## 本 session 完成内容

### F216-c 拆分 + F216-c1 Sprint Contract 协商

1. **6 文件原则触发拆分**：F216-c 预估 8 文件超上限，按父 feature `sub_sprint_notes` 预告方案拆为：
   - F216-c1 (后端) — 5 文件
   - F216-c2 (前端) — 4 文件
2. **features.json sub_sprints 同步**（C5 双向一致已闭合）：删 `F216-c` 键，加 `F216-c1` + `F216-c2` 两键
3. **4 协商点全部按推荐方案拍板**（用户 2026-05-14 确认）：
   - NP1 weeks 参数 `default=50` `range=[10,50]`
   - NP2 拆分按 c1=后端 / c2=前端
   - NP3 router pure compute 不写 DB（调 `classify` 纯函数）
   - NP4 顶层 `stage: WeeklyStagePayload`（7 字段对齐 DATA-MODEL.md）
4. **Contract 文档生成**：`docs/开发/sprint-contracts/F216-c1-contract.md`
5. **状态流转**：F216-c1 design_needed → **contract_agreed**

---

## F216-c1 Sprint Contract 摘要

### 实现范围（5 文件）

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `backend/app/routers/cockpit/chart.py` | 修改 | 加 `GET /{ticker}/weekly` route + 2 个 Depends helper |
| `backend/app/schemas/cockpit/chart.py` | 修改 | 加 `WeeklyStagePayload` / `WeeklyChartData` / `WeeklyChartResponse` 3 个 schema |
| `backend/app/services/cockpit/cockpit_params.py` | 修改 | 加 §7 `CockpitChartWeeklyParams` + `CHART_WEEKLY` 单例 |
| `backend/tests/test_cockpit_chart_weekly_router.py` | 新建 | 集成测试覆盖 §3 标准 1-9 |
| `docs/系统设计/API-CONTRACT.md` | 修改 | 加子节 "GET /api/cockpit/chart/{ticker}/weekly" |

### 11 完成标准（合约 §3 详）

- 标准 1：响应符合 `WeeklyChartResponse` schema（含 `data.ticker / weeklyBars / weeklyMas / stage`）
- 标准 2-3：weeklyBars 长度 / weeklyMas 三 keys / 序列长度正确
- 标准 4：Stage 2 fixture → stage=2 + slope30w>0.5 + ma_*非null + scan_date=末周
- 标准 5：daily_bars<4 → 全空 + stage=0 + scanDate=null
- 标准 6：daily_bars<30 周 → weeklyBars 非空 + stage=0 + scanDate 非 null
- 标准 7：unknown ticker → 404 NOT_FOUND
- 标准 8：weeks 越界 → 422 VALIDATION_ERROR；边界 10 / 50 → 200
- 标准 9：GET 前后 `weekly_stage_snapshots` 表行数不变（pure compute）
- 标准 10：API-CONTRACT.md 子节完整
- 标准 11：全量后端 pytest 回归无新增失败（基线 994 passed）

### 21 步开发顺序（合约 §6 详）

```
阶段一：schema + 配置（步骤 1-5）
  └─ WIP commit 1: schema + cockpit_params CHART_WEEKLY
阶段二：router 实现（步骤 6-8）
  └─ WIP commit 2: router GET /weekly endpoint
阶段三：测试（步骤 9-12）
  └─ WIP commit 3: integration tests for GET /weekly
阶段四：文档 + 收尾（步骤 13-21）
  ├─ 调 consistency-check (mode=interactive) C1/C4/C5
  └─ Final commit: feat(F216-c1): GET /api/cockpit/chart/{ticker}/weekly with stage payload
```

---

## 当前功能状态

```
F216 Phase B Weekly Stage Layer：🔄 in_progress
  ├─ F216-a Weekly Aggregation Service:  ✅ done (commit 6e86e75)
  ├─ F216-b Stage Classifier + DB:       🔍 needs_review (commit ab6a16b)
  ├─ F216-c1 Router + Stage Payload:     🤝 contract_agreed  ← 当前
  ├─ F216-c2 Widget + Registry:          ⬜ design_needed
  ├─ F216-d setup_service gate:          ⬜ design_needed
  └─ F216-e Scheduler cron:              ⬜ design_needed
```

---

## 已确认依赖（开发前再核对一次）

- F216-a `WeeklyChartService.get_weekly_chart(ticker, weeks)` — 已 done，纯本地 daily_bars 聚合，零 FMP，unknown ticker → APIError(NOT_FOUND)
- F216-b `WeeklyStageService.classify(weekly_bars, ma10, ma30, ma40) -> WeeklyStageResult` — 纯函数，已通过 17 个单测验证；不需要构造 db Session
- F216-b `WEEKLY_STAGE` 常量组（含 `MIN_WEEKS_FOR_CLASSIFICATION=30` 等）— 已 in place
- F216-a `WEEKLY.DEFAULT_WEEKS=50` — 作为 `CHART_WEEKLY.MAX_WEEKS` 来源
- `app.services.watchlist_service.APIError` — 沿用，不引新异常类

---

## 已知约束 / 注意点

- ⚠️ **Router 严格 pure compute**：禁止 `WeeklyStageRepository.upsert` / `WeeklyStageService.compute_for_ticker` 调用；只调 `classify`。Evaluator 自检会 grep 校验
- ⚠️ **scan_date 当 weekly_bars 为空时返回 null**；非空但 stage=0 时仍返回最后周 date（标准 5 vs 标准 6 的关键区分）
- ⚠️ **C1 invariant**：F216-c1 完成升 done 后，父 F216 保持 in_progress（c2/d/e 仍 design_needed）。consistency-check skill 自动校验，不得人工误升
- 复用现有 `ChartBarItem` / `ChartSeriesPoint` schema — 字段兼容 weekly bar，不要新建另一组
- API-CONTRACT.md 子节插入到 §"Cockpit Chart (/api/cockpit/chart/{ticker})" 节内，**不要**放到 Decision 节下

---

## 启动下个 Session 指令

> **F216-c1 Generator 模式**（建议 Sonnet）：
>
> 继续开发 F216-c1，Sprint Contract 已确认。
> 读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F216-c1-contract.md，
> 进入 Generator 模式，从 §6 开发顺序步骤 1 开始。
> 严格按 21 步执行，3 个 WIP commit 节点不要省。
