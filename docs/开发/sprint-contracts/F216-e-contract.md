# Sprint Contract：F216-e Cockpit Phase B — Weekly Stage Scheduler Cron

> 日期：2026-05-15 | 状态：草案（等待用户确认 NP1–NP7）
> 引用文档：
>   - features.json §F216 acceptance_criteria L10（22:20 UTC, mon-fri, 调用 WeeklyStageService.compute_and_store_all, order: regime → weekly_stage → setup）
>   - /Users/wonderer/.claude/plans/featrue-dev-replicated-goblet.md §Phase B5
>   - 现有同模式参照：refresh_job._setup_tick / _regime_tick（F202-b / F201-b）
>   - DECISIONS.md 待追加 D094

---

## 1. 本次实现范围

**包含（B5 scheduler cron）**：
- `backend/app/config.py` 追加 `weekly_stage_cron_hour=22` / `weekly_stage_cron_minute=20`（mon-fri 默认）
- `backend/app/services/refresh_job.py`：
  - 新增常量 `WEEKLY_STAGE_JOB_ID = "cockpit_weekly_stage_refresh"`
  - 新增 `_weekly_stage_tick(session_factory, fmp_factory)` 函数（mirror `_setup_tick` 模式：try/except 包裹、调用 `WeeklyStageService(db).compute_and_store_all()`、异常仅 logger.error 不上抛）
  - 在 `start_scheduler` 内追加一个 `add_job(_weekly_stage_tick, …)`，CronTrigger 用 `settings.weekly_stage_cron_hour/minute`、`day_of_week="mon-fri"`、`timezone="UTC"`、`id=WEEKLY_STAGE_JOB_ID`、`replace_existing=True`
  - 位置：在 `_regime_tick` 注册块（22:15）之后、`_setup_tick` 注册块（22:30）之前，保持代码顺序与时间顺序一致
- `backend/tests/test_weekly_stage_cron_f216e.py` 新建，3 条测试（S1 注册校验 22:20 mon-fri / S2a tick happy path / S2b tick 吞异常），mirror `test_setup_f202b.py§TestSetupScheduler/TestSetupTick`
- `docs/系统设计/DECISIONS.md` 追加 **D094**（cron 时段 22:20 选址、order 通过 wall-clock 时间间隔而非同步链）
- `docs/系统设计/ARCHITECTURE.md` 在 §部署 env 示例段 Cockpit Epic 块追加 `WEEKLY_STAGE_CRON_HOUR=22 / WEEKLY_STAGE_CRON_MINUTE=20` 两行注释

**明确排除（本次不做）**：
- 不引入 prefect / dagster 等编排器（保持 APScheduler 直接 add_job 模式，与 regime/setup 一致）
- 不实现"前一个任务完成后再触发下一个"的同步依赖链（NP5 决定改走时间间隔 ordering）
- 不增加 weekly_stage 的 `_force_run` API endpoint（F202-b 也没有，需要时单独迭代）
- 不改 `WeeklyStageService.compute_and_store_all` 签名或行为
- 不改 alembic / 数据模型 / API / 前端任何代码
- 不修复 ARCHITECTURE.md 中既有的 REGIME/SETUP cron env 默认值与 config.py 不一致的 drift（pre-existing，超出本 sprint scope）

---

## 2. 预计修改文件清单（5 个，未触发拆分）

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/config.py` | 修改 | 加 `weekly_stage_cron_hour: int = 22` / `weekly_stage_cron_minute: int = 20` 两行（紧跟 `setup_cron_*` 之后） |
| 2 | `backend/app/services/refresh_job.py` | 修改 | 加 `WEEKLY_STAGE_JOB_ID` 常量 + `_weekly_stage_tick` 函数 + `start_scheduler` 内 add_job 块 |
| 3 | `backend/tests/test_weekly_stage_cron_f216e.py` | 新建 | 3 条测试：S1 注册校验 / S2a tick happy path / S2b tick 吞异常 |
| 4 | `docs/系统设计/DECISIONS.md` | 修改 | 追加 D094 决策（时段选址 + ordering 策略） |
| 5 | `docs/系统设计/ARCHITECTURE.md` | 修改 | env 示例段加 WEEKLY_STAGE_CRON_HOUR / MINUTE 两行 |

👤 用户确认文件清单合理后，方可进入开发。

---

## 3. 协商点（NP）— 推荐方案 + 备选

### NP1：cron 时段 — 22:20 UTC（推荐：是）

**推荐**：`weekly_stage_cron_hour=22` / `weekly_stage_cron_minute=20`

**理由**：
- features.json acceptance_criteria L10 明文 "22:20 UTC"
- 落在 regime (22:15) 与 setup (22:30) 之间，10 分钟间隔足够 weekly_stage compute_and_store_all 完成（active_stocks ~25 标的，纯本地 DB 查询 + numpy OLS，<10s 经验值）
- setup 在 22:30 起跑时已能读到当天最新 weekly_stage_snapshots（NP-E 已规定 `get_latest_for_tickers` 不限 scan_date，即使 weekly_stage 周一才更新，setup 周二—周五也能读上周值，但 cron 每个工作日都跑给冷启动 + 节假日跳过场景兜底）

**备选**：
- B：22:25（regime + 10min，setup - 5min）— 缓冲更宽但与 acceptance criteria 文字不一致
- C：21:35（紧跟 main refresh 21:30）— daily_bars 21:30 刚开始 refresh，weekly_chart 依赖 daily_bars，过早会读到旧数据

### NP2：env 配置键命名（推荐：mirror 既有）

**推荐**：`weekly_stage_cron_hour` / `weekly_stage_cron_minute`（snake_case，与 setup_cron_hour / regime_cron_hour 同 pattern）

**备选**：
- B：合并为 `weekly_stage_cron = "20 22 * * 1-5"` 单字符串 — 偏离既有 pattern，无收益
- C：用 plan 默认值硬编码不放 settings — 配置不可调，反对

### NP3：Job ID 常量命名（推荐：cockpit 前缀）

**推荐**：`WEEKLY_STAGE_JOB_ID = "cockpit_weekly_stage_refresh"`（mirror `cockpit_setup_refresh` / `cockpit_regime_refresh` / `cockpit_earnings_refresh` 三例 pattern）

**备选**：
- B：`f216_weekly_stage_cron` — feature ID 进 job_id，与既有 6 个 job_id 全不一致
- C：`weekly_stage_refresh`（不带 cockpit 前缀）— 与 `ma150_daily_refresh` 同风格但不与 cockpit 系列对齐

### NP4：tick 函数 fmp_factory 形参（推荐：保留 placeholder）

**推荐**：`_weekly_stage_tick(session_factory, fmp_factory)` — 保留 fmp_factory 形参但不使用（mirror `_pending_orders_expirer_tick` 反例：那个连 fmp_factory 都没收）

**理由**：实际 weekly_stage 是零 FMP 调用（D090 已确认本地 daily_bars 聚合），但 `start_scheduler` 内所有 add_job 的 args 现在都传 `[session_factory, fmp_factory]`。统一签名降低注册块的特例理解成本。

**备选**：
- B：只收 session_factory（mirror `_pending_orders_expirer_tick` / `_journal_monthly_tick` 两例）— 节省 1 行但要让 add_job 的 args 单独传 `[session_factory]`，混入两种调用约定
- C：收两个但 logger.warning 一次 fmp_factory 未用 — 噪音无意义

### NP5：order 保证策略（推荐：wall-clock 时间间隔）

**推荐**：通过 cron 时间错峰（22:15 / 22:20 / 22:30）达成 regime → weekly_stage → setup 的 order，**不引入任何同步依赖或事件链**。

**理由**：
- 与现有 refresh → regime → setup 链条策略一致（21:30 → 22:15 → 22:30）
- APScheduler 不原生支持 job dependency；引入第三方编排器（prefect / dagster）违反 §1 排除范围
- weekly_stage compute 实测 <10s（active_stocks ~25），10 min 间隔有 60x 安全余量
- 若 weekly_stage 因 daily_bars 异常拖到 22:25 仍未结束，setup 22:30 起跑时会读 *昨天* 的 weekly_stage（NP-E 不限 scan_date），数据上不一致但不崩溃，符合 D093 "NULL/旧 stage → ready=False" 的保守语义

**备选**：
- B：在 `_weekly_stage_tick` 结尾直接同步调用 `SetupService.compute_and_store_all()` — 把两个 cron 揉成一个，强耦合，违反单一职责，setup_cron 配置失效
- C：用 BlockingScheduler 强制串行 — 重写整个 scheduler 模式，远超 sprint scope

### NP6：测试范围（推荐：3 条 S1/S2a/S2b）

**推荐**：新建独立测试文件 `test_weekly_stage_cron_f216e.py`，3 条：
- S1 `test_weekly_stage_job_registered_with_correct_schedule`：start_scheduler 后 `WEEKLY_STAGE_JOB_ID in job_ids`，trigger fields hour=22 / minute=20 / day_of_week=mon-fri
- S2a `test_tick_calls_compute_and_store_all`：patch `WeeklyStageService`，调用 `_weekly_stage_tick`，断言 service 被实例化（with db）且 `compute_and_store_all()` 调用 1 次
- S2b `test_tick_swallows_exception`：patch `WeeklyStageService` side_effect=RuntimeError，调用 `_weekly_stage_tick` 不抛

**理由**：mirror `test_setup_f202b.py§TestSetupScheduler/TestSetupTick`，与 _regime_tick / _setup_tick 测试覆盖等同；不需要新加 E2E（cron 时间走真实时钟无法测）。

**备选**：
- B：把 3 条测试塞进 `test_weekly_stage_service.py` — 测试关注点混乱（一个是 service 单测，一个是 scheduler 集成）
- C：再加一条"端到端：fake clock 跳到 22:20 验证 service 被调用" — APScheduler 没有时间冷冻 API，需要 freezegun + 启动真实 scheduler，复杂度收益比差

### NP7：DECISIONS.md D094 内容（推荐：双段落，时段 + ordering）

**推荐**：D094 含两段——
1. **时段选址 22:20**：理由（regime 22:15 / setup 22:30 间隙、零 FMP 调用 <10s 实测、acceptance criteria 文字约束）
2. **ordering 策略选择**：选 wall-clock 间隔而非同步链，理由（与 refresh→regime→setup 既有 pattern 一致、APScheduler 无原生 job dependency、stale stage 路径 NULL→ready=False 兜底安全）

**备选**：
- B：只写一段 ordering 不解释时段 — 时段选址来年看不懂为啥不是 22:25
- C：split D094 / D095 两个决策 — 一个 sprint 一个决策记录更紧凑

---

## 4. 可测试的完成标准（11 条）

| # | 标准描述 | 测试层级 | 工具 / 文件 |
|---|---------|---------|------|
| 1 | `settings.weekly_stage_cron_hour == 22` / `weekly_stage_cron_minute == 20` 默认值 | 单元 | pytest 既有 settings 默认值不需要新测 |
| 2 | `WEEKLY_STAGE_JOB_ID == "cockpit_weekly_stage_refresh"` 常量存在 | 单元 | import 即过 |
| 3 | `_weekly_stage_tick(session_factory, fmp_factory)` 函数签名匹配（接收两形参） | 单元 | inspect / 直接调用 |
| 4 | `start_scheduler(autostart=False)` 后 `WEEKLY_STAGE_JOB_ID` 在 `sched.get_jobs()` 中 | 集成（scheduler 实例） | pytest `test_weekly_stage_cron_f216e.py§S1` |
| 5 | 该 job trigger fields：`hour="22"` `minute="20"` `day_of_week="mon-fri"` | 集成 | pytest `S1` |
| 6 | `_weekly_stage_tick` happy path：实例化 `WeeklyStageService(db)`、调用 `compute_and_store_all()` 1 次 | 单元（mock） | pytest `S2a` |
| 7 | `_weekly_stage_tick` 异常路径：`WeeklyStageService` 抛 RuntimeError 时 tick 函数返回 None 不上抛 | 单元（mock） | pytest `S2b` |
| 8 | DECISIONS.md 含 `## D094` 标题且两段（时段 + ordering）齐全 | 文档 | grep 验证 |
| 9 | ARCHITECTURE.md env 示例段含 `WEEKLY_STAGE_CRON_HOUR` 与 `WEEKLY_STAGE_CRON_MINUTE` | 文档 | grep 验证 |
| 10 | 全量后端 pytest 回归无新增失败（基线对照 v1.8.1-planning F216-d3 done 时） | 回归 | `cd backend && uv run pytest` |
| 11 | 注册块在 refresh_job.py 中位于 `REGIME_JOB_ID` add_job 之后、`SETUP_JOB_ID` add_job 之前（代码顺序 = 时间顺序，便于读代码理解 pipeline） | 代码结构 | 人工 + Evaluator 自检 |

---

## 5. 开发顺序（11 步，严格按序）

1. `backend/app/config.py`：在 `setup_cron_minute: int = 30` 之后插入 4 行（注释 + 两 settings）
2. `backend/app/services/refresh_job.py`：在 `SETUP_JOB_ID` 常量声明后追加 `WEEKLY_STAGE_JOB_ID = "cockpit_weekly_stage_refresh"`
3. `backend/app/services/refresh_job.py`：在文件顶部 `from app.services.cockpit.setup_service import SetupService` 之后追加 `from app.services.cockpit.weekly_stage_service import WeeklyStageService`
4. `backend/app/services/refresh_job.py`：在 `_setup_tick` 函数定义之前插入 `_weekly_stage_tick` 函数（mirror `_setup_tick` 模式：try / `_session_scope` / `WeeklyStageService(db).compute_and_store_all()` / except BLE001 logger.error）
5. `backend/app/services/refresh_job.py`：在 `start_scheduler` 内 `_regime_tick` add_job 之后、`_setup_tick` add_job 之前插入新 add_job 块（CronTrigger(day_of_week="mon-fri", hour=settings.weekly_stage_cron_hour, minute=settings.weekly_stage_cron_minute, timezone="UTC")）
6. **WIP commit 1**：`wip(F216-e): cron config + tick + scheduler registration`（文件 1+2）
7. `backend/tests/test_weekly_stage_cron_f216e.py`：新建，含 `_reset_scheduler` autouse fixture（mirror test_setup_f202b.py）+ `TestWeeklyStageScheduler::test_s1_*` + `TestWeeklyStageTick::test_s2a_*` / `test_s2b_*`
8. 运行 `cd backend && uv run pytest tests/test_weekly_stage_cron_f216e.py -v`，3 条全绿
9. **WIP commit 2**：`wip(F216-e): cron registration + tick tests`（文件 3）
10. `docs/系统设计/DECISIONS.md` 追加 D094 + `docs/系统设计/ARCHITECTURE.md` 加 env 两行
11. 全量回归 `cd backend && uv run pytest`，确认无新增失败 → Evaluator 模式自检 → Final commit `feat(F216-e): weekly_stage 22:20 UTC scheduler cron`

---

## 6. WIP / Final commit 节点

- **WIP-1** (step 6)：`wip(F216-e): cron config + tick + scheduler registration` — backend/app/config.py + backend/app/services/refresh_job.py
- **WIP-2** (step 9)：`wip(F216-e): cron registration + tick tests` — backend/tests/test_weekly_stage_cron_f216e.py
- **Final** (step 11)：`feat(F216-e): weekly_stage 22:20 UTC scheduler cron` — docs/系统设计/DECISIONS.md + docs/系统设计/ARCHITECTURE.md（默认保留细粒度 wip，不 squash）

---

## 7. Evaluator 自检清单

- [ ] 标准 1–7 单元/集成测试全部通过（pytest 输出贴报告）
- [ ] 全量后端 pytest 回归无新增失败（标准 10）
- [ ] 标准 8–9 文档关键词 grep 命中
- [ ] 标准 11 注册块位置肉眼核对：`_regime_tick add_job` → `_weekly_stage_tick add_job` → `_setup_tick add_job`
- [ ] 字段命名对照 F216-d2 D093 + features.json acceptance_criteria L10 一字不差
- [ ] `_weekly_stage_tick` 接受 (session_factory, fmp_factory) 双参，但函数体不引用 fmp_factory（NP4 一致性）
- [ ] DECISIONS.md D094 含双段（时段选址 + ordering 策略）
- [ ] ARCHITECTURE.md env 块新增两行紧跟 SETUP_CRON_* 之后，保持顺序与代码一致
- [ ] 无 console.error / linter warning 新增
- [ ] DATA-MODEL.md / API-CONTRACT.md **未被触动**（B5 不涉及 schema / API）

---

## 8. 风险与备忘

- **风险 R1**：APScheduler 多 job 同时刻共享 ThreadPoolExecutor，22:15 / 22:20 / 22:30 三 cron 在 max_workers 默认（10）下没问题，但若未来加 cron 密度上升要监控线程池饱和。**本 sprint 不处理**。
- **风险 R2**：DST 切换日（3 月第 2 周日 / 11 月第 1 周日）UTC 不变，cron 行为稳定，无需特殊处理。
- **备忘 M1**：F216 父 feature 升 done 由 consistency-check C1 invariant 触发（F216-a/b/c1/c2/d1/d2/d3 已 done，F216-e done 后所有 sibling 齐全）。**Evaluator 升 needs_review 后调用 consistency-check (mode=interactive) 验证**。
- **备忘 M2**：F216 父 feature 自身没有独立 acceptance 环节需求（B5 是后端 cron，无 UI；与 F216-a 同理可直升 done）。Evaluator 通过 + consistency-check 全清后由用户拍板是否走 acceptance skill。

---

👤 请确认 NP1–NP7 选项（默认全部按推荐），文件清单 5 项无误后，本 Contract 进入已确认状态。
