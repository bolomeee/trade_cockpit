# Sprint Contract：F207-a — ActionList 后端（rule engine + endpoint）

> 状态：草案，待用户确认 | 起草：2026-04-27
> 父 Feature：F207 Daily Action List Widget（v1.9 Cockpit P1）
> 拆分：**F207-a（本 sprint，后端 rule engine + endpoint）** / F207-b（前端 ActionListWidget）
> 依赖：
>   - F206-a ✅（PositionRepository / `position_action_rules.compute_next_action` / `LastCloseLoader` / EarningsEventRepository.get_next_earnings 直接复用）
>   - F206-b1 ✅（PendingOrderRepository.list_by_status）
>   - F202 ✅（MarketRegimeRepository.get_latest 提供 regime 字段）
>   - F201/F203 ✅（SetupSnapshotRepository.get_latest_for_tickers 提供 BROKEN 标记）
>   - 既有：UserSettingsRepository（不直接用，但 LastCloseLoader 已封装）
>
> 引用文档：
>   - API-CONTRACT.md §GET /api/cockpit/actions/today（line 1584-1660：响应 schema + actionType 枚举表）
>   - DATA-MODEL.md §Position / §PendingOrder / §SetupSnapshot / §EarningsEvent / §MarketRegimeSnapshot
>   - design-spec.md §Widget 9 ActionListWidget（line 1088-1118：分栏 UI 描述，本 sprint 只实现后端，不动 UI）
>   - DECISIONS.md D041（on-demand FMP fallback）/ D060-a（Triggered 不自动建 Position）/ D074（camelCase）
>   - features.json#F207（acceptance_criteria 6 条）
>   - 模板参考：
>     - `backend/app/services/cockpit/position_service.py`（D041 LastCloseLoader 接入 + 字段编排风格）
>     - `backend/app/services/cockpit/position_action_rules.py`（compute_next_action 已存在，reuse）
>     - `backend/app/routers/cockpit/positions.py`（router + APIError 风格，本 sprint 镜像）
>     - `backend/app/schemas/cockpit/position.py`（D074 camelCase + alias_generator）

---

## 0. 背景与定位

F207 把"今日动作清单"作为单独 widget 呈现。后端纯 deterministic 规则引擎，**不调用 AI**（AI 增强延到 F210/F211）。本 sprint 只做后端 rule engine + 1 个 endpoint，**不做前端**（→ F207-b）。

**核心难点**：F207 是 Cockpit 全栈的"集大成者"——同时读 5 个 repository（positions / pending_orders / setup_snapshots / earnings_events / market_regime_snapshots），还要算 last_close 和 distance。一旦 rule engine 写散，后续维护成本会炸。本 sprint 必须把规则引擎做成**纯函数化、按 actionType 一一对应的判定函数**，便于未来 F210 AI 层叠加和单测覆盖。

**关键约束**：

1. **rule engine 入口签名固定**：
   ```python
   def build_today_actions(db: Session) -> dict:
       """Returns {as_of_date, must_act, monitor, no_action} ready to serialize."""
   ```
   service 内部按"加载数据 → 逐条判定 → 分类 → 排序"四步走，不做 N+1 IO（一次性收集 ticker，统一调 LastCloseLoader / SetupSnapshotRepository.get_latest_for_tickers / EarningsEventRepository.get_next_earnings）。

2. **复用 `compute_next_action`，不引入 swing_low**（§7 Q1 已确认）：
   - 既有 rule 输出 `hold | raise_stop | reduce | exit`，本 sprint 在外面包一层 actionType 映射器，不动 `position_action_rules.py`
   - swing_low 精度延到未来 sprint（届时改 `position_action_rules.py` 即可，F207 不用动）

3. **rationale 模板纯字符串拼接**（不可空、不可"AI 生成"）：每条 actionType 一个 f-string 模板，引用具体数字（last_close / r_multiple / days_until_earnings / setup_snapshot.date / regime / distance_pct）。具体模板见 §1.1.2。

4. **as_of_date = `date.today()`**（UTC，与 PositionService 一致）；空数据下三数组全 `[]`，仍返回 200 + 当日日期（API-CONTRACT line 1652）。

5. **批量 IO 模式**：
   - 一次性收集 `position_tickers + pending_order_tickers` 去重 → 调 `LastCloseLoader.load(tickers)` 拿 `dict[str, float | None]`
   - 同样去重后调 `SetupSnapshotRepository.get_latest_for_tickers(tickers)` → `dict[str, SetupSnapshot]`
   - earnings 仅对 position_tickers 逐个调 `get_next_earnings(ticker, today)`（已有方法，无批量；ticker 数量 ≤ 持仓数 ≤ 几十，可接受）
   - regime 一次 `MarketRegimeRepository.get_latest()`（单行）

6. **响应 schema 严格按 API-CONTRACT line 1592-1631**：
   - 顶层 `{ "data": { "asOfDate": "...", "mustAct": [...], "monitor": [...], "noAction": [...] }, "message": "success" }`
   - 每条 item：`{ ticker, actionType, rationale, refs: {...} }`，`refs` 是 dict（字段集随 actionType 变化），D074 camelCase
   - **不嵌 `items` 包裹**（与 GET /pending-orders 一致；与 GET /positions 不同，但本 endpoint 没有 summary，无需占位）

7. **错误处理**：
   - 任一表查询失败 → 500，标准 APIError 体（与 positions / pending_orders 一致）
   - LastCloseLoader 内部已做 FMP fallback；某 ticker last_close 缺失 → 该 ticker 上的 distance / r_multiple 计算降级（具体见每条 rule 的 §1.1.2）
   - 没有 MarketRegimeSnapshot（系统未运行过 F202 nightly）→ 跳过 tighten_stop 判定（不抛错，仅日志 warn）

---

## 1. 实现范围

### 1.1 包含

#### 1.1.1 `backend/app/services/cockpit/action_service.py`（新建，~280 行）

**模块结构**：

```python
# ── 常量 ─────────────────────────────────────
APPROACH_TRIGGER_THRESHOLD_PCT = 3.0          # monitor.approaching_trigger
EARNINGS_REDUCE_DAYS = 2                       # must_act.reduce_before_earnings
REGIME_TIGHTEN_SET = frozenset({"DEFENSIVE", "RISK_OFF"})  # must_act.tighten_stop

# ── ActionType 枚举（Literal）─────────────────
ActionType = Literal[
    "raise_stop", "cancel_order", "reduce_before_earnings", "tighten_stop",
    "approaching_trigger", "stable_position",
]

# ── 入口 ─────────────────────────────────────
class ActionService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._positions_repo = PositionRepository(db)
        self._orders_repo = PendingOrderRepository(db)
        self._setup_repo = SetupSnapshotRepository(db)
        self._earnings_repo = EarningsEventRepository(db)
        self._regime_repo = MarketRegimeRepository(db)
        self._last_close_loader = LastCloseLoader(db)

    def build_today_actions(self) -> dict:
        """Top-level entry. Returns dict ready for ActionsTodayResponse(**data)."""
```

**算法（伪代码）**：

```
1. positions = positions_repo.list_by_status("open")
2. orders    = orders_repo.list_by_status("active")
3. tickers   = unique(positions[*].ticker + orders[*].ticker)
4. last_close_map = LastCloseLoader.load(tickers)        # {ticker: float | None}
5. setup_map      = SetupSnapshotRepository.get_latest_for_tickers(tickers)  # {ticker: SetupSnapshot}
6. earnings_map   = {p.ticker: get_next_earnings(p.ticker, today) for p in positions}
7. regime_row     = MarketRegimeRepository.get_latest()  # may be None
8. regime         = regime_row.regime if regime_row else None

9. must_act, monitor, no_action = [], [], []

10. for p in positions:
       action_type, rationale, refs = _classify_position(p, last_close_map, earnings_map, regime)
       (must_act or no_action).append(...)

11. for o in orders:
       action_type, rationale, refs = _classify_pending_order(o, last_close_map, setup_map)
       (must_act or monitor).append(...)

12. # 排序：must_act 按优先级（tighten_stop > reduce_before_earnings > raise_stop > cancel_order）
   #       monitor / no_action 按 ticker 字典序
13. return { "as_of_date": today, "must_act": ..., "monitor": ..., "no_action": ... }
```

**`_classify_position` 优先级**（首匹配胜出，§7 Q2 已确认）：

| 优先级 | 条件 | 输出 actionType / 栏 |
|---|---|---|
| 1 | last_close ≤ stop_price（rule 引擎 `exit`） | **must_act / `raise_stop`**（rationale 标注"stop already breached, immediate review"，重用 raise_stop 枚举避免扩展 spec — §7 Q3 决策）|
| 2 | regime ∈ {DEFENSIVE, RISK_OFF} | **must_act / `tighten_stop`** |
| 3 | days_until_earnings ≤ 2（rule 引擎 `reduce`） | **must_act / `reduce_before_earnings`** |
| 4 | rule 引擎返回 `raise_stop`（R ≥ 2.0 且 stop < entry） | **must_act / `raise_stop`** |
| 5 | 否则（rule 引擎 `hold`） | **no_action / `stable_position`** |

⚠️ 优先级 1 vs 2 的关系：若同时满足 stop breached AND regime DEFENSIVE，仍按优先级 1（stop breached）→ raise_stop（措辞"stop already breached"）。理由：stop breached 是 ticker 个体硬信号，比 regime 全局软信号更紧迫；用户"立即处置"语义更强。

**`_classify_pending_order` 优先级**（首匹配胜出）：

| 优先级 | 条件 | 输出 actionType / 栏 |
|---|---|---|
| 1 | setup_map[ticker].setup_type == "BROKEN" | **must_act / `cancel_order`** |
| 2 | distance_to_trigger_pct ≤ 3.0%（必须 last_close 非空，且 entry > last_close 表示尚未触发） | **monitor / `approaching_trigger`** |
| 3 | 否则 | （**不出现在任何栏**——pending order 既不"必做"也不"接近"就不展示，避免噪音） |

⚠️ §7 Q4 已确认：pending_order 无 stable 栏。原因：pending order 本身是"等待执行"，距离很远的 active order 在 PendingOrdersWidget 已可见，ActionList 只关心"可能要动手的"。

**rationale 模板**（每个 actionType 一个，确定性字符串）：

| actionType | 模板（f-string） | refs |
|---|---|---|
| `raise_stop`（rule） | `f"R-multiple {r:.2f}; stop {stop} below entry {entry} — consider tightening"` | `{positionId, currentStop, rMultiple}` |
| `raise_stop`（exit / breached） | `f"Last close {last_close} <= stop {stop} — stop already breached, immediate review"` | `{positionId, currentStop, lastClose}` |
| `reduce_before_earnings` | `f"Earnings in {days_until_earnings} day(s) ({earnings_date}); reduce per playbook"` | `{positionId, earningsDate, daysUntilEarnings}` |
| `tighten_stop` | `f"Regime turned {regime}; tighten stops across all open positions"` | `{positionId, regime}` |
| `cancel_order` | `f"Setup BROKEN as of {snapshot_date}; cancel pending order"` | `{orderId, setupSnapshotDate}` |
| `approaching_trigger` | `f"Pending order trigger at {entry}; current {last_close} ({distance:+.2f}%)"` | `{orderId, entry, lastClose, distancePct}` |
| `stable_position` | `"Trend intact, no rule change"` | `{positionId}` |

**排序规则**：
- `must_act`：按 actionType 优先级 `tighten_stop > reduce_before_earnings > raise_stop > cancel_order`，同 actionType 内按 ticker 字典序
- `monitor`：ticker 字典序
- `no_action`：ticker 字典序

> 排序的目的是渲染时 Must Act 顶部用户最先看到最紧迫的；不同 ticker 一致行为不依赖入库顺序。

#### 1.1.2 `backend/app/routers/cockpit/actions.py`（新建，~70 行）

```python
@router.get("/actions/today", response_model=ActionsTodayResponse)
def get_today_actions(db: Session = Depends(get_db)) -> ActionsTodayResponse:
    try:
        data = ActionService(db).build_today_actions()
        return ActionsTodayResponse(data=ActionsTodayPayload(**data), message="success")
    except SQLAlchemyError as exc:
        raise APIError("INTERNAL_ERROR", str(exc), 500) from exc
```

**Pydantic schemas（行内定义在 router 文件，~50 行）**：

```python
class ActionItem(_CamelModel):
    ticker: str
    action_type: str           # 不用 Literal，schema 由 service 保证
    rationale: str
    refs: dict                  # 弱类型，refs 字段集随 actionType 变化

class ActionsTodayPayload(_CamelModel):
    as_of_date: date            # serialized as ISO YYYY-MM-DD
    must_act: list[ActionItem]
    monitor: list[ActionItem]
    no_action: list[ActionItem]

class ActionsTodayResponse(BaseModel):
    data: ActionsTodayPayload
    message: str
```

`_CamelModel` 复用既有定义（`backend/app/schemas/cockpit/position.py` 内）；如果共享需要新增文件则**直接 import**，不重复定义。

#### 1.1.3 `backend/app/routers/cockpit/__init__.py`（修改，+2 行）

```python
from app.routers.cockpit.actions import router as actions_router
...
router.include_router(actions_router)
```

#### 1.1.4 `backend/tests/test_action_service.py`（新建，~360 行）

**单元测试矩阵（10 用例）**：

| # | 场景 | 期望 |
|---|---|---|
| U1 | 空 DB（无 positions / orders / regime / setups） | `as_of_date=today, must_act=[], monitor=[], no_action=[]` |
| U2 | 1 个 OPEN position，rule=hold，无 regime | no_action 1 条，actionType=`stable_position` |
| U3 | 1 个 position，last_close ≤ stop（breached） | must_act 1 条，actionType=`raise_stop`，rationale 含 "stop already breached" |
| U4 | regime=DEFENSIVE + 1 个 stable position | must_act 1 条 `tighten_stop`（优先级高于 stable） |
| U5 | regime=CONSTRUCTIVE + 1 个 R=2.5 position（rule=raise_stop） | must_act 1 条 `raise_stop`，rationale 含 R-multiple |
| U6 | position 财报 in 1d | must_act 1 条 `reduce_before_earnings`（优先级在 tighten_stop 之下，故无 regime 时触发） |
| U7 | position 财报 in 2d + regime=DEFENSIVE | must_act 1 条 `tighten_stop`（优先级高于 earnings） |
| U8 | 1 个 ACTIVE pending_order，distance=2%（last_close=entry×0.98） | monitor 1 条 `approaching_trigger`，rationale 含 "(-2.00%)" |
| U9 | pending_order 对应 setup BROKEN | must_act 1 条 `cancel_order`，rationale 含 setup snapshot date |
| U10 | pending_order distance=10% | 不出现在任何栏（既无 must 也无 monitor） |

**额外覆盖**：
- 排序：U11 — must_act 多条混合 actionType，断言顺序为 `tighten_stop > reduce_before_earnings > raise_stop > cancel_order`
- 字段缺失降级：U12 — last_close=None 的 pending_order，distance 无法算 → 不进入 monitor（不抛错）
- regime 缺失：U13 — `MarketRegimeRepository.get_latest()` 返回 None，逻辑跳过 tighten_stop 判定，不抛错

#### 1.1.5 `backend/tests/test_actions_router.py`（新建，~200 行）

**集成测试（6 用例）**：

| # | 场景 | 断言 |
|---|---|---|
| I1 | GET 空 DB → 200 + `data.must_act=[] / monitor=[] / no_action=[]` + `data.asOfDate` 是 ISO 日期 |
| I2 | GET 含 2 OPEN positions（一个 stable / 一个 R=3） → `must_act` 含 1 条 `raise_stop`，`no_action` 含 1 条 `stable_position` |
| I3 | GET 含 1 ACTIVE pending_order distance=1% → `monitor[0].actionType="approaching_trigger"`，`refs.distancePct` 为负数（-1.00 左右） |
| I4 | GET 含 1 pending_order + 对应 ticker BROKEN setup → `must_act[0].actionType="cancel_order"` |
| I5 | 响应 schema 严格符合 API-CONTRACT：camelCase 字段（`asOfDate / mustAct / monitor / noAction / actionType`），item 含 `ticker / actionType / rationale / refs` 四字段 |
| I6 | DB 抛错 → 500 + APIError 标准体（mock SQLAlchemyError） |

**fixture 复用**：
- 复用 F206-a/b1 已有的 `positions_repo` / `pending_orders_repo` / `setup_snapshot_repo` / `market_regime_repo` 测试装置（参考 `test_position_service.py` / `test_pending_order_service.py` 的 setup 模式）
- earnings_event 用 `EarningsEventRepository.upsert_batch` 直插

### 1.2 排除（本 sprint 不做）

| 排除项 | 何时做 | 原因 |
|---|---|---|
| 前端 ActionListWidget UI / 组件 / 测试 | F207-b | 拆分 |
| AI Daily Brief 折叠区 | v2.0 (F209/F211) | spec 已明确"v2.0 feature-dev 阶段细化" |
| swing_low 精度（替代 R≥2.0 触发） | 未来 sprint，改 `position_action_rules.py` | 当前 rule 已稳定，避免扩面 |
| `nextAction` 字段加入 GET /positions 响应 | 已在 F206-a 落地（`compute_next_action` 已编排进 PositionService）| 不再重复 |
| pending_order TRIGGERED 自动建 Position | D060-a 已决策不做 | — |
| 把 ActionItem 内 `refs` 字段做成 typed Pydantic union | 等前端 F207-b 反馈 schema 是否够用 | over-engineering 风险，弱类型 dict 在 MVP 内够用 |
| Widget 注册（`COCKPIT_WIDGET_REGISTRY`）| F207-b | 前端 sprint 范畴 |

---

## 2. 预计修改文件（共 5 个）

| # | 文件路径 | 改动 | 说明 |
|---|---|---|---|
| 1 | `backend/app/services/cockpit/action_service.py` | 新建 | 主体 rule engine + 数据加载 + rationale 拼接 |
| 2 | `backend/app/routers/cockpit/actions.py` | 新建 | `GET /api/cockpit/actions/today` + Pydantic schemas |
| 3 | `backend/app/routers/cockpit/__init__.py` | 修改 | 注册 actions_router |
| 4 | `backend/tests/test_action_service.py` | 新建 | 13 单元用例（rule 引擎覆盖） |
| 5 | `backend/tests/test_actions_router.py` | 新建 | 6 集成用例（endpoint 全链路） |

✅ 在 6 文件上限内。

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---|---|---|
| S1 | `ActionService.build_today_actions()` 在空 DB 返回 `must_act=[] / monitor=[] / no_action=[] / as_of_date=today` | 单元 | pytest |
| S2 | OPEN position last_close ≤ stop → must_act `raise_stop` rationale 含 "stop already breached" | 单元 | pytest |
| S3 | regime=DEFENSIVE 优先于 reduce_before_earnings 与 raise_stop（rule） | 单元 | pytest |
| S4 | regime=DEFENSIVE 优先于 stable_position（即使 position 处于 hold 也升级为 must_act tighten_stop） | 单元 | pytest |
| S5 | days_until_earnings ≤ 2 → must_act `reduce_before_earnings`（无 regime 升级时） | 单元 | pytest |
| S6 | rule 引擎返回 raise_stop（R ≥ 2.0 且 stop < entry）→ must_act `raise_stop` 模板 | 单元 | pytest |
| S7 | rule 引擎返回 hold → no_action `stable_position` | 单元 | pytest |
| S8 | pending_order 对应 ticker 当日最新 setup_type=BROKEN → must_act `cancel_order` | 单元 | pytest |
| S9 | pending_order distance ≤ 3% 且 last_close ≠ None → monitor `approaching_trigger`，rationale 含 distance% | 单元 | pytest |
| S10 | pending_order distance > 3% → 不出现在 must_act / monitor / no_action 任一栏 | 单元 | pytest |
| S11 | last_close=None 的 pending_order → 不抛错，不进入 monitor | 单元 | pytest |
| S12 | 无 MarketRegimeSnapshot → 不抛错，跳过 tighten_stop 判定 | 单元 | pytest |
| S13 | must_act 排序：tighten_stop > reduce_before_earnings > raise_stop > cancel_order，同 actionType 内 ticker 字典序 | 单元 | pytest |
| S14 | GET /api/cockpit/actions/today 200，响应顶层 `{ data: { asOfDate, mustAct, monitor, noAction }, message }` 全 camelCase | 集成 | pytest + httpx + 测试 DB |
| S15 | 集成 — 含 2 OPEN positions（stable + R=3）→ mustAct 1 条 raise_stop / noAction 1 条 stable_position | 集成 | pytest |
| S16 | 集成 — 含 ACTIVE pending order distance≈1% → monitor[0].actionType="approaching_trigger"，refs.distancePct 为负 | 集成 | pytest |
| S17 | 集成 — pending order + setup BROKEN → mustAct[0].actionType="cancel_order" | 集成 | pytest |
| S18 | 集成 — DB 抛错 → 500 + 标准 APIError 体 | 集成 | pytest |
| S19 | 静态 — `ruff check backend/` 0 warning（仅本 sprint 新文件） | 静态 | ruff |
| S20 | 全量回归 — 后端全套 pytest 通过（212 之外的所有 backend tests），无回归 | 回归 | pytest |

---

## 4. Evaluator 自检清单

开发完成后逐条 ✓：

- [ ] 单元测试 13/13 通过（`pytest backend/tests/test_action_service.py -v`）
- [ ] 集成测试 6/6 通过（`pytest backend/tests/test_actions_router.py -v`）
- [ ] 后端全量回归通过（`pytest backend/`）
- [ ] 响应字段完全符合 API-CONTRACT.md line 1592-1631（camelCase / 4 顶层 key / 4 item 字段）
- [ ] DATA-MODEL.md 字段命名一致（不擅自创造字段）
- [ ] rationale 模板内的数字均为实际数据（无占位符 / 无 AI 调用）
- [ ] APIError 错误体格式与 cockpit 其他 endpoint 一致
- [ ] `ruff check backend/` 0 warning（本 sprint 新文件）
- [ ] 无 `print()` / `console.error` 遗留
- [ ] action_service.py 无重复实现 LastCloseLoader / compute_next_action（必须 import 复用）
- [ ] 本 sprint 决策（§7）已写入 DECISIONS.md

---

## 5. 开发顺序

```
1. 写 backend/app/services/cockpit/action_service.py 框架（class + build_today_actions 空壳）
   → wip(F207-a): action service skeleton
2. 实现 _classify_position（5 优先级）+ rationale 模板
   → 单元 U1-U7 跑通
   → wip(F207-a): position classifier + rationale templates
3. 实现 _classify_pending_order（3 优先级，含"无栏"分支）+ rationale 模板
   → 单元 U8-U13 跑通
   → wip(F207-a): pending-order classifier + sort
4. 加排序逻辑 + as_of_date
   → wip(F207-a): action sort + as_of_date
5. 写 backend/app/routers/cockpit/actions.py + Pydantic schemas
   → wip(F207-a): actions router skeleton
6. 在 backend/app/routers/cockpit/__init__.py 注册路由
   → 集成 I1 跑通（GET 空 DB）
7. 写 test_actions_router.py 余下 5 集成用例
   → 集成 I2-I6 跑通
   → wip(F207-a): integration tests
8. 全量回归 pytest backend/
9. ruff check
10. 写 DECISIONS.md（本 sprint 决策追加）
11. Evaluator 自检 → phase=needs_review
12. 最终 commit feat(F207-a)
```

---

## 6. 风险与决策点

| 风险 | 影响 | 缓解 |
|---|---|---|
| `compute_next_action` 输出与 F207 actionType 不一一对应 | 映射层走样 | §1.1.1 表格写死映射，单测 U2-U7 全覆盖 |
| ticker 同时是 OPEN position 和 ACTIVE pending_order | 双行重复 | 不去重，position 和 pending_order 是两个生命周期实体，分别判定不冲突；同 ticker 在不同栏可同时出现（如持仓 stable + 加仓 order approaching） |
| LastCloseLoader 慢路径（FMP）放大延迟 | endpoint 响应过慢 | 复用现有批量优化（watchlist 内 SQL 一次，watchlist 外串行 FMP 已被 PositionService 接受），不新增逻辑 |
| `refs` 字段弱类型 → 前端契约不稳 | F207-b 易出错 | rationale 模板表（§1.1.2）已固定每个 actionType 的 refs 字段集；F207-b 直接照表实现 |
| 设计稿 spec 对 stable_position 在 monitor 的归属模糊 | 实现偏差 | §7 Q4 已决策：monitor 不出现 stable_position；只有 approaching_trigger 走 monitor |

---

## 7. 决策记录（用户确认后写入 DECISIONS.md）

| Q | 决策点 | 选项 | **用户已选** | 落点 |
|---|---|---|---|---|
| Q1 | raise_stop 触发条件 | (a) 复用 `compute_next_action`（R≥2.0）/ (b) 新引入 swing_low 检测 | **(a) 复用** | F207-a 不动 `position_action_rules.py`；swing_low 精度延到未来 sprint |
| Q2 | tighten_stop 触发条件 | (a) regime DEFENSIVE/RISK_OFF 时对所有 OPEN positions 全局发 / (b) 按持仓单独发 | **(a) 全局** | service 内一次 regime 查询，遍历每个 position 各发一条；rationale 引用 regime |
| Q3 | cancel_order 触发口径 | (a) ticker 当日最新 setup_snapshot.setup_type=BROKEN / (b) 其他规则 | **(a) BROKEN** | `SetupSnapshotRepository.get_latest_for_tickers()` 已返回最新一行，直接读 setup_type |
| Q4 | stable_position 在哪一栏 | (a) approaching_trigger→monitor，其他稳态持仓→noAction，monitor 不出现 stable_position / (b) 同时出现在两栏 | **(a) 简化** | 与 API-CONTRACT 表格仍兼容（noAction 那行说明仍然成立；monitor.stable_position 那行视为预留） |
| Q5 | reduce_before_earnings 触发 | days_until_earnings ≤ 2 个自然日（含 0） | **确认** | 与 `position_action_rules.compute_next_action` 当前阈值一致 |
| Q6 | Widget layout 槽位 | x:0 y:16 w:12 h:6（全宽，置于 positions+pending_orders 下方） | **确认** | F207-b sprint 实施；本 sprint 仅记录 |
| Q7（新）| position 同时 stop breached 与 regime DEFENSIVE | 优先 raise_stop（exit 语义） vs 优先 tighten_stop | **优先 raise_stop**（个体硬信号 > 全局软信号） | 单元 U3 / U4 区分 |
| Q8（新）| pending_order distance > 3% 且 setup 非 BROKEN | 是否放 noAction / monitor / 不展示 | **不展示**（避免噪音） | 单元 U10 验证 |

---

👤 用户确认本 Contract（含 §7 Q1-Q8 决策）后，进入 Generator 模式。
