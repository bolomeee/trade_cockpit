# Sprint Contract：F216-c1 — Weekly Chart Router + Stage Payload（B3 后端）

> 日期：2026-05-14 | 状态：📝 草案待确认
> Feature：F216 Cockpit Phase B — Weekly Stage Layer
> Sub-sprint：F216-c1（Phase B 第 3 子里的后端半段；F216-c 因 6 文件原则拆为 c1=后端 / c2=前端）
> 依赖：F216-a done（commit 6e86e75 — WeeklyChartService）、F216-b needs_review（commit ab6a16b — WeeklyStageService.classify 纯函数 + WEEKLY_STAGE params）
> 引用文档：
>   - ARCHITECTURE.md（cockpit/ 模块层）
>   - API-CONTRACT.md §"Cockpit Chart (/api/cockpit/chart/{ticker})"（新增子节）
>   - DATA-MODEL.md §"WeeklyStageSnapshot"（字段权威）
>   - DECISIONS.md §D091（Stage 量化判定）/ §D092（numpy 边界）
>   - 完整改善计划：/Users/wonderer/.claude/plans/featrue-dev-replicated-goblet.md §Phase B / B3

---

## 0. 背景与定位

F216-c 整体目标：暴露周线 chart endpoint + 前端 widget。父 feature `sub_sprint_notes` 已预告 "c 合约阶段二次拆 c1=后端 c2=前端"。

**c1（本 sprint）只交付后端**：
- `GET /api/cockpit/chart/{ticker}/weekly?weeks=50` 端点
- 响应 schema：weekly_bars + weekly_mas + **顶层 stage payload**
- API-CONTRACT.md 子节
- 集成测试覆盖路径 + schema + Stage 计算正确性 + 错误码

**c2（下一个 sprint）交付前端**：API client / `WeeklyStageChartWidget` / `CockpitRegistry` 注册 / `cockpit.json` 布局。

**为什么先后端再前端**：后端 endpoint 可独立用 TestClient 验证，前端 c2 才有真 API 可联调；这是其他 Cockpit widget（F203 chart / F213 setup）的既定 pattern。

**关键约束（用户已确认 2026-05-14）**：
- NP1 `weeks` 参数：`default=50`、`min=10`、`max=50`，与 F216-a `WEEKLY.DEFAULT_WEEKS` 一致（daily_bars 窗口 250 限制）
- NP3 Stage 计算策略：**pure compute** —— router 调 `WeeklyChartService.get_weekly_chart` + `WeeklyStageService.classify`（F216-b 纯函数），**不写 DB**。持久化交由 F216-e cron。
- NP4 响应 schema：顶层 `stage: WeeklyStagePayload` 对象，字段对齐 DATA-MODEL.md `WeeklyStageSnapshot`（去 `id` / `computed_at`，前端用不到）。

---

## 1. 实现范围

**包含**：

### 1.1 router 修改：`backend/app/routers/cockpit/chart.py`

新增 endpoint，**复用现有 `_get_service` Depends 模式但额外加 WeeklyStageService dependency**：

```python
def _get_weekly_stage_service(db: Session = Depends(get_db)) -> WeeklyStageService:
    return WeeklyStageService(db)


def _get_weekly_chart_service(db: Session = Depends(get_db)) -> WeeklyChartService:
    return WeeklyChartService(db)


@router.get("/{ticker}/weekly", response_model=WeeklyChartResponse)
def get_cockpit_weekly_chart(
    ticker: str,
    weeks: int = Query(default=WEEKLY.DEFAULT_WEEKS),
    chart_svc: WeeklyChartService = Depends(_get_weekly_chart_service),
    stage_svc: WeeklyStageService = Depends(_get_weekly_stage_service),
) -> WeeklyChartResponse:
    # validate weeks ∈ [MIN_WEEKS, DEFAULT_WEEKS]
    if not (CHART_WEEKLY.MIN_WEEKS <= weeks <= CHART_WEEKLY.MAX_WEEKS):
        raise APIError("VALIDATION_ERROR", f"weeks must be ...", 422)
    # fetch weekly bars + MAs
    chart = chart_svc.get_weekly_chart(ticker=ticker, weeks=weeks)
    # classify stage purely (no DB write)
    result = stage_svc.classify(
        chart["weekly_bars"],
        chart["weekly_mas"].get("10", []),
        chart["weekly_mas"].get("30", []),
        chart["weekly_mas"].get("40", []),
    )
    # derive scan_date from last weekly bar (NP4 — see DATA-MODEL.md)
    scan_date = chart["weekly_bars"][-1]["date"] if chart["weekly_bars"] else None
    stage_payload = WeeklyStagePayload(
        stage=result.stage,
        weekly_close=result.weekly_close,
        weekly_ma_10=result.weekly_ma_10,
        weekly_ma_30=result.weekly_ma_30,
        weekly_ma_40=result.weekly_ma_40,
        slope_30w=result.slope_30w,
        scan_date=scan_date,
    )
    bars = [ChartBarItem.model_validate(b) for b in chart["weekly_bars"]]
    mas_out = {k: [ChartSeriesPoint.model_validate(p) for p in v] for k, v in chart["weekly_mas"].items()}
    data = WeeklyChartData(ticker=ticker.upper(), weekly_bars=bars, weekly_mas=mas_out, stage=stage_payload)
    return WeeklyChartResponse(data=data)
```

**关键点**：
- 复用 `ChartBarItem` / `ChartSeriesPoint`（schema 字段 date/open/high/low/close/volume 完全兼容 weekly bar）
- `WeeklyChartService.get_weekly_chart` 已有 NOT_FOUND 抛出（unknown ticker） → 沿用，不重复抛
- 数据不足时（< MIN_WEEKS_FOR_CLASSIFICATION）`classify` 返回 `stage=0`，`scan_date` 仍能从最后一根 weekly bar 取到；若 weekly_bars 完全为空（< 4 个 daily bars），`scan_date=None`

### 1.2 schema 修改：`backend/app/schemas/cockpit/chart.py`

追加（不动现有 `ChartBarItem` / `ChartSeriesPoint` / `CamelModel`）：

```python
class WeeklyStagePayload(CamelModel):
    stage: int                       # 0=UNKNOWN, 1-4
    weekly_close: float | None
    weekly_ma_10: float | None
    weekly_ma_30: float | None
    weekly_ma_40: float | None
    slope_30w: float | None          # %/周
    scan_date: date | None


class WeeklyChartData(CamelModel):
    ticker: str
    weekly_bars: list[ChartBarItem]
    weekly_mas: dict[str, list[ChartSeriesPoint]]
    stage: WeeklyStagePayload


class WeeklyChartResponse(BaseModel):
    data: WeeklyChartData
    message: str = "success"
```

camelCase 自动转换（`weeklyBars` / `weeklyMas` / `weeklyClose` 等）由 `CamelModel.alias_generator=to_camel` 处理。

### 1.3 配置追加：`backend/app/services/cockpit/cockpit_params.py`

在 §5 `WEEKLY` 之后追加 §7 `CockpitChartWeeklyParams`（router 层参数，与 service 层 `WEEKLY` 分开）：

```python
@dataclass(frozen=True)
class CockpitChartWeeklyParams:
    MIN_WEEKS: int = 10                              # ≥ classify 要求的最少不太多
    MAX_WEEKS: int = WEEKLY.DEFAULT_WEEKS            # 复用 50，避免分散


CHART_WEEKLY = CockpitChartWeeklyParams()
```

**理由**：现有 `WEEKLY` 是 service 默认；router 校验区间需要 MIN/MAX 上下界。沿用 cockpit_params.py "router 层 vs service 层" 分组 pattern（参考 CHART 与 CHART_DEFAULTS）。这是范围内的 **第 5 个文件**。

> 二次确认：因引入 `CHART_WEEKLY`，本 sprint 文件数 = 5（chart.py router / chart.py schema / cockpit_params.py / test / API-CONTRACT.md），仍 ≤ 6。

### 1.4 测试新建：`backend/tests/test_cockpit_chart_weekly_router.py`

集成测试（FastAPI TestClient，复用 `tests/conftest.py` 中 `db` / `client` fixture），覆盖 §3 标准 1-9。

### 1.5 文档修改：`docs/系统设计/API-CONTRACT.md`

在 §"Cockpit Chart (/api/cockpit/chart/{ticker})" 节下新增子节 "GET /api/cockpit/chart/{ticker}/weekly"，格式参照同节既有 GET 子节。

**明确排除（本 sub-sprint 不做）**：

- 任何前端代码 / `CockpitRegistry` 修改 / `cockpit.json` 修改 → 全部归 F216-c2
- 任何 DB schema 变更 / Alembic / Repository 改动 → F216-c1 不写 DB
- `WeeklyStageService.compute_for_ticker` 调用 → router 用纯函数 `classify`，不触发持久化
- F216-d setup_service gate 接入 → F216-d 负责
- F216-e cron 调度 → F216-e 负责
- 修改现有 `GET /api/cockpit/chart/{ticker}` endpoint（保持完全独立）

---

## 2. 预计修改文件（共 5 个）

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `backend/app/routers/cockpit/chart.py` | 修改 | 追加 `_get_weekly_chart_service` / `_get_weekly_stage_service` Depends + `get_cockpit_weekly_chart` route |
| `backend/app/schemas/cockpit/chart.py` | 修改 | 追加 `WeeklyStagePayload` / `WeeklyChartData` / `WeeklyChartResponse` 三个 schema |
| `backend/app/services/cockpit/cockpit_params.py` | 修改 | 追加 §7 `CockpitChartWeeklyParams` + `CHART_WEEKLY` 单例 |
| `backend/tests/test_cockpit_chart_weekly_router.py` | 新建 | 集成测试，覆盖 §3 标准 1-9 |
| `docs/系统设计/API-CONTRACT.md` | 修改 | 新增子节 "GET /api/cockpit/chart/{ticker}/weekly" |

✅ 5 文件，≤ 6 上限。

---

## 3. 完成标准（可测试）

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `GET /api/cockpit/chart/AAPL/weekly` 返回 200，响应符合 `WeeklyChartResponse` schema（含 `data.ticker / weeklyBars / weeklyMas / stage`） | 集成 | pytest + TestClient + Pydantic 验证 |
| 2 | `weeklyBars` 长度等于 `min(weeks, len(aggregated))`；每条 bar 含 date/open/high/low/close/volume；按 date 升序 | 集成 | pytest |
| 3 | `weeklyMas` 含 keys `"10"`, `"30"`, `"40"`；每条 series 长度 = `len(weeklyBars) - period + 1`（不足 period 时为空数组） | 集成 | pytest |
| 4 | 当 daily_bars 充足（≥ 30 周）且呈上行趋势时，`data.stage.stage == 2` 且 `data.stage.slope30w > 0.5`；ma_10 / ma_30 / ma_40 非 null；scan_date == weeklyBars[-1].date | 集成 | pytest（构造 fixture daily_bars） |
| 5 | 当 daily_bars < 4 行时，`weeklyBars=[]`、`weeklyMas={"10":[], "30":[], "40":[]}`、`stage.stage == 0`、`stage.scanDate == null`、所有数值字段为 null | 集成 | pytest |
| 6 | 当 daily_bars < 30 周（足够聚合但不足分类）时，`weeklyBars` 非空，`stage.stage == 0`，`stage.scanDate` 不为 null（等于最后周 date） | 集成 | pytest |
| 7 | unknown ticker `GET /api/cockpit/chart/UNKNOWN/weekly` → 404，错误码 `NOT_FOUND` | 集成 | pytest |
| 8 | `weeks=5`（< MIN_WEEKS=10）→ 422 `VALIDATION_ERROR`；`weeks=100`（> MAX_WEEKS=50）→ 422 `VALIDATION_ERROR`；`weeks=50`（边界）→ 200；`weeks=10`（边界）→ 200 | 集成 | pytest |
| 9 | 路由调用**不**在 `weekly_stage_snapshots` 表写入新行（pure compute，无副作用） | 集成 | pytest（GET 前后查表行数不变） |
| 10 | API-CONTRACT.md 子节包含路径 / 查询参数表 / 成功响应示例 / 错误响应表 | 人工 | grep + 人眼 |
| 11 | 全量后端 pytest 回归无新增失败 | 集成 | pytest backend/tests/ |

---

## 4. Evaluator 自检清单

- [ ] 标准 1-9 全部通过（pytest）
- [ ] 标准 10 通过（API-CONTRACT.md 子节人眼检查）
- [ ] 标准 11 通过（全量回归对照基线 994 passed，无新增失败）
- [ ] Router 中**无任何**对 `WeeklyStageRepository.upsert` 的调用（grep 验证）
- [ ] Router 中**无**对 `WeeklyStageService.compute_for_ticker` 的调用（仅调 `classify`）
- [ ] schema 命名严格 camelCase 出参（pydantic alias_generator=to_camel 已配置）
- [ ] `CHART_WEEKLY.MIN_WEEKS / MAX_WEEKS` 仅在 router validator 中使用，无散落
- [ ] 无硬编码魔法值（weeks 范围引用 `CHART_WEEKLY.*`，stage 整数引用 F216-b `WeeklyStageService.STAGE_*` 或直接走 `result.stage`）
- [ ] 沿用 `APIError("NOT_FOUND" / "VALIDATION_ERROR", ...)`，不自定义新异常类
- [ ] router 函数主体 ≤ 50 行（超过应抽 helper）
- [ ] 无 print / console.log / 临时调试代码
- [ ] DECISIONS.md 无需新增（pure compute 策略已在 D091 / D092 范围内；本 sprint 无新决策）
- [ ] DATA-MODEL.md 无改动（不新建表 / 不动 WeeklyStageSnapshot schema）

---

## 5. 协商点（NP）拍板记录

| # | 议题 | 选项 | 用户拍板 | 落地 |
|---|------|------|---------|------|
| NP1 | weeks 默认 / 上限 | A: default=50, range [10, 50] / B: default=50, range [10, 260] 截短 / C: default=260, range [10, 260] | **A** | `CHART_WEEKLY.MIN_WEEKS=10` / `MAX_WEEKS=50` |
| NP2 | F216-c 是否拆分 | A: 不拆 / B: c1=后端 c2=前端 / C: 三段 | **B** | sub_sprints F216-c → F216-c1+c2（已同步） |
| NP3 | Stage 计算策略 | A: pure compute 不写 DB / B: GET 时 upsert / C: 读最新快照 fallback | **A** | router 调 classify 纯函数 |
| NP4 | Stage 字段在响应中的形式 | A: 顶层 stage payload / B: 扁平化两字段 / C: 全藏在 weeklyBars 末项 | **A** | 顶层 `stage: WeeklyStagePayload`，字段对齐 DATA-MODEL.md WeeklyStageSnapshot |

---

## 6. 开发顺序（21 步，不得跳步）

> 每完成一步且通过最小验证 → 立即 WIP commit（git add 显式列文件，禁 `-A`）。预计 3 个 WIP commit 节点 + 1 个 Final commit。

### 阶段一：schema + 配置（基础数据结构）

1. 读 DATA-MODEL.md WeeklyStageSnapshot 字段，确认字段名 / 类型 / 可空性一致
2. 编辑 `backend/app/schemas/cockpit/chart.py`，追加 `WeeklyStagePayload` / `WeeklyChartData` / `WeeklyChartResponse`
3. 编辑 `backend/app/services/cockpit/cockpit_params.py`，追加 §7 `CockpitChartWeeklyParams` + `CHART_WEEKLY` 单例
4. `python -c "from app.schemas.cockpit.chart import WeeklyChartResponse; from app.services.cockpit.cockpit_params import CHART_WEEKLY; print(CHART_WEEKLY)"` 冒烟
5. **WIP commit**：`wip(F216-c1): schema + cockpit_params CHART_WEEKLY`
   - 文件：`backend/app/schemas/cockpit/chart.py` `backend/app/services/cockpit/cockpit_params.py`

### 阶段二：router 实现

6. 编辑 `backend/app/routers/cockpit/chart.py`：
   - 顶部 import：`WeeklyChartService` / `WeeklyStageService` / 新 schema / `CHART_WEEKLY`
   - 追加 `_get_weekly_chart_service` / `_get_weekly_stage_service` Depends
   - 追加 `get_cockpit_weekly_chart` route（按 §1.1）
7. uvicorn 本地启动冒烟：`curl http://localhost:8000/api/cockpit/chart/AAPL/weekly` 验证 200 / 404
8. **WIP commit**：`wip(F216-c1): router GET /weekly endpoint`
   - 文件：`backend/app/routers/cockpit/chart.py`

### 阶段三：测试

9. 新建 `backend/tests/test_cockpit_chart_weekly_router.py`，按 §3 标准 1-9 写 11-15 条测试
10. 准备 fixture：构造 ≥ 35 周升序 daily_bars 用于 Stage 2 测试（模仿 F216-b `test_weekly_stage_service.py` 的 fixture 构造）
11. 跑测试：`uv run pytest backend/tests/test_cockpit_chart_weekly_router.py -v`，全绿
12. **WIP commit**：`wip(F216-c1): integration tests for GET /weekly`
   - 文件：`backend/tests/test_cockpit_chart_weekly_router.py`

### 阶段四：文档 + 收尾

13. 编辑 `docs/系统设计/API-CONTRACT.md`，在 §"Cockpit Chart (/api/cockpit/chart/{ticker})" 节追加子节（路径 / 参数表 / 成功响应示例 / 错误响应表）
14. grep `pure compute` `stage_payload` 在 router / schema 中无遗漏命名一致
15. 全量回归：`uv run pytest backend/tests/ -q`，对照基线 994 passed
16. Evaluator 自检清单逐条打勾
17. 更新 `features.json` F216-c1 phase → testing → needs_review，追加 iteration_history
18. 调用 consistency-check skill (mode=interactive)：验证 C1 父 feature 完整性（c1 升 done 后 c2/d/e 仍 design_needed → 父 in_progress 不动）/ C4 c1 history 已补 / C5 sub_sprints F216-c1 ↔ contract 文件已存在
19. 更新 `claude-progress.txt`（追加完成记录）
20. 生成或更新 `SESSION-HANDOFF.md`（F216-c1 完成 → 下一步 F216-c2）
21. **Final commit**：`feat(F216-c1): GET /api/cockpit/chart/{ticker}/weekly with stage payload`
   - 文件：上述 5 文件 + features.json + claude-progress.txt + SESSION-HANDOFF.md

---

## 7. 风险与对策

| 风险 | 概率 | 对策 |
|------|------|------|
| `_compute_ma_series` 对短序列返回值不一致 | 低 | F216-a 已覆盖；测试构造充足周数避免边界歧义 |
| `weekly_bars[-1]["date"]` 在空列表时崩 | 低 | router 中已用三元 `if chart["weekly_bars"] else None` 保护；标准 5 覆盖 |
| 测试 fixture 周数不足触发 stage=0 误判为 Stage 2 测试失败 | 中 | 构造 ≥ 35 行 daily_bars 且严格升序；明确指定起始价位与日斜率 |
| API-CONTRACT.md 子节插入位置错误（落到 Decision 节下） | 低 | 用 `## Cockpit Decision` 作为 anchor 反向定位插入点 |
| router 中重复实例化 service 影响测试 mock | 低 | 沿用既有 `_get_service` Depends pattern，TestClient override 已被 conftest 处理 |

---

## 8. 暂停与恢复指令

如本 sprint 中途中断：
1. WIP commit 当前进度（按 §6 节点）
2. 更新 features.json：`active_sprint_phase` 改为 `in_progress`，iteration_history 追加中断点
3. 生成 SESSION-HANDOFF.md
4. 下个 session 恢复指令：
   > 继续开发 F216-c1，Sprint Contract 已确认。读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F216-c1-contract.md，进入 Generator 模式，从开发顺序步骤 [N] 开始。

---

## 9. 完成后联动

- F216-c1 done → 触发 F216-c2 Sprint Contract 协商（前端 widget + API client + Registry + layout.json，预计 4 文件）
- F216-c1 endpoint 上线后 F216-c2 可用真后端联调，不依赖 mock
- 父 F216 status 保持 `in_progress`（C1 invariant：c2/d/e 仍 design_needed）
