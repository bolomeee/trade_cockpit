# Sprint Contract：F203-a — CockpitChart 数据层 + 接入层

> 状态：草案 | 起草：2026-04-25
> 父 Feature：F203 Decision Panel
> 兄弟：F203-b（user_settings + Decision 服务/接入）；F203-c（CockpitChartWidget 前端）；F203-d（Decision Card + Settings 表单 前端）
> 引用文档：
>   - DATA-MODEL.md §Stock / §DailyBar / §EarningsEvent（无 schema 变更）
>   - API-CONTRACT.md §GET /api/cockpit/chart/{ticker}（接口权威）
>   - DECISIONS.md D063（CockpitChartWidget / 端点独立；MA utility 函数级复用允许）
>   - DECISIONS.md D070（Cockpit 参数管理 → 本 Sprint 追加 §3 CockpitChartParams）

---

## 0. 背景与定位

F203 总文件 ≈ 14 个，按 6 文件原则拆为 4 段：

- **F203-a（本 Sprint，6 生产文件）**：CockpitChart 数据 + HTTP 接入 — chart service（OHLCV + 多 MA + ATR + AVWAP）+ Pydantic schema + FastAPI Router + cockpit_params §3
- **F203-b**：user_settings + Decision 数据/接入 — UserSettings model + repo + Alembic migration + 2 services + 2 routers + schemas
- **F203-c**：CockpitChartWidget 前端 — widget + api client + Registry 注册
- **F203-d**：Decision Card + Settings 表单 前端 — DecisionCardWidget + UserSettingsForm + 2 api client + Registry 注册

F203-a 完成后，前端通过 `GET /api/cockpit/chart/NVDA?mas=10,21,50,150,200&days=250` 即可拿到完整 chart payload；F203-b/c/d 之前不出现 entry/stop/size/decision card UI。

---

## 1. 实现范围

### 1.1 cockpit_params.py — 追加 §3 CockpitChartParams

修改 `backend/app/services/cockpit/cockpit_params.py`：

```python
class CockpitChartParams(BaseModel):
    """§3 CHART — bars window / MA periods allowlist / ATR period / AVWAP fallback."""

    model_config = ConfigDict(frozen=True)

    # ── Bars 窗口 ───────────────────────────────────────────────────────
    DEFAULT_DAYS: int = Field(default=250, description="Default bars days when client omits ?days", ge=100, le=400)
    MIN_DAYS: int = Field(default=100, description="Lower bound for ?days", ge=20, le=400)
    MAX_DAYS: int = Field(default=400, description="Upper bound for ?days", ge=100, le=1000)

    # ── MA 周期允许范围 ─────────────────────────────────────────────────
    DEFAULT_MAS: list[int] = Field(default=[10, 21, 50, 150, 200], description="Default MA periods returned when ?mas omitted")
    MA_MIN: int = Field(default=5, description="Min single MA period", ge=2, le=100)
    MA_MAX: int = Field(default=250, description="Max single MA period", ge=50, le=500)
    MA_MAX_COUNT: int = Field(default=8, description="Max number of MA series allowed in one request", ge=1, le=20)

    # ── ATR ─────────────────────────────────────────────────────────────
    ATR_PERIOD: int = Field(default=14, description="ATR rolling period", ge=5, le=50)

    # ── AVWAP fallback ──────────────────────────────────────────────────
    AVWAP_FALLBACK_DAYS: int = Field(
        default=0,
        description="If no anchor and no earnings_event, fall back to N days back from latest bar (0 = no fallback, return empty avwap series)",
        ge=0, le=180,
    )


CHART = CockpitChartParams()
```

### 1.2 chart_service.py（计算引擎 + 编排）

新文件 `backend/app/services/cockpit/chart_service.py`：

```python
class CockpitChartService:
    def __init__(self, db: Session): ...

    def get_chart(
        self,
        ticker: str,
        mas: list[int] | None = None,
        days: int | None = None,
        anchor: date | None = None,
    ) -> dict:
        """
        组装 API-CONTRACT §GET /api/cockpit/chart/{ticker} 响应数据 dict。
        1. ticker 大写规范化；mas/days 应用默认值
        2. 优先走本地 stocks + daily_bars；
           ticker 不在 stocks 或 bars 不足 → fallback FMP on-demand（复用 D041 逻辑，不写 daily_bars）
        3. _compute_ma_series：对每个 ma 周期计算 SMA 序列（窗口前部为 None，序列化时跳过）
        4. _compute_atr_series：14 日 Wilder ATR 序列
        5. anchor 解析：传入 → 直接用；为空 → 查 EarningsEventRepository 取 ticker 的最近一次 earnings_date（<= today）；
           都没有 + AVWAP_FALLBACK_DAYS=0 → anchor=None, series=[]
        6. _compute_avwap_series：从 anchor 起累计 typical_price * volume / volume
        返回 dict（snake_case；router 层转 camelCase）。
        """
```

**纯函数（模块级，可独立测试）**：

```python
def _compute_ma_series(bars: list[dict], period: int) -> list[dict]:
    """
    bars: [{"date": date, "close": float, ...}, ...]（已按 date ASC 排序）
    返回 [{"date": d, "value": v}]，前 period-1 个 bar 不输出（不返回 None 占位）。
    period 不合法（>= len(bars)）时返回空列表。
    """

def _compute_atr_series(bars: list[dict], period: int) -> list[dict]:
    """
    Wilder ATR：
      TR_i = max(high - low, |high - prev_close|, |low - prev_close|)
      ATR_1 = avg(TR[:period])
      ATR_i = (ATR_{i-1} * (period-1) + TR_i) / period   # i > period
    返回 [{"date": d, "value": v}]，前 period 个 bar 不输出。
    """

def _compute_avwap_series(bars: list[dict], anchor: date) -> list[dict]:
    """
    从 anchor（含当日）起累计：
      typical = (high + low + close) / 3
      cum_pv  += typical * volume
      cum_v   += volume
      avwap   = cum_pv / cum_v   # cum_v == 0 时跳过该点
    anchor 早于 bars[0].date → 等价于 bars[0]
    anchor 晚于 bars[-1].date → 返回空列表
    返回 [{"date": d, "value": v}]，仅 anchor 之后（含）的 bar。
    """

def _resolve_anchor(
    explicit_anchor: date | None,
    earnings_repo: EarningsEventRepository,
    ticker: str,
    today: date,
) -> date | None:
    """
    explicit_anchor 优先；否则查 earnings_events 取 ticker 最近一次 earnings_date <= today；
    无 → 返回 None。
    """
```

**`mas` / `days` 解析与校验（router 层）**：
- `mas` 字符串按逗号切分 → int 列表；任一非法（< MA_MIN / > MA_MAX）或数量 > MA_MAX_COUNT → 422
- `days` 不在 [MIN_DAYS, MAX_DAYS] → 422

### 1.3 schemas/cockpit/chart.py — Pydantic 响应

新文件 `backend/app/schemas/cockpit/chart.py`：

```python
class ChartBarItem(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int

class ChartSeriesPoint(BaseModel):
    date: date
    value: float

class ChartAvwap(BaseModel):
    anchor: date | None
    series: list[ChartSeriesPoint]

class CockpitChartData(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    ticker: str
    bars: list[ChartBarItem]
    mas: dict[str, list[ChartSeriesPoint]]   # key 为 period 字符串："10" / "21" / ...
    atr: list[ChartSeriesPoint]
    avwap: ChartAvwap

class CockpitChartResponse(BaseModel):
    data: CockpitChartData
    message: str = "success"
```

### 1.4 routers/cockpit/chart.py

新文件 `backend/app/routers/cockpit/chart.py`：

```python
router = APIRouter(prefix="/cockpit/chart", tags=["cockpit-chart"])

@router.get("/{ticker}", response_model=CockpitChartResponse)
def get_cockpit_chart(
    ticker: str,
    mas: str = Query(default=",".join(str(p) for p in CHART.DEFAULT_MAS)),
    days: int = Query(default=CHART.DEFAULT_DAYS),
    anchor: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> CockpitChartResponse:
    # 解析 mas、days、anchor → 422 on validation error（含 anchor 非 ISO 日期）
    # 调用 service.get_chart(...) → 包装 success 响应
    # ticker 经 FMP fallback 仍无数据 → 404 NOT_FOUND
    # FMP 外部异常 → 502 EXTERNAL_API_ERROR
```

错误码沿用现有 `app.core.exceptions` 模式（参考 setup router）。

### 1.5 routers/cockpit/__init__.py

修改 `backend/app/routers/cockpit/__init__.py`：

```python
from app.routers.cockpit.chart import router as chart_router
...
cockpit_router.include_router(chart_router)
```

### 1.6 测试 `tests/test_chart_f203a.py`

参见 §3 完成标准 S1–S14。

---

## 2. 预计修改文件（共 6 个）

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `backend/app/services/cockpit/cockpit_params.py` | 修改 | 追加 §3 CockpitChartParams + `CHART` 实例 |
| 2 | `backend/app/services/cockpit/chart_service.py` | 新建 | CockpitChartService + 4 纯函数 |
| 3 | `backend/app/schemas/cockpit/chart.py` | 新建 | Pydantic 响应 schema |
| 4 | `backend/app/routers/cockpit/chart.py` | 新建 | FastAPI router `GET /cockpit/chart/{ticker}` |
| 5 | `backend/app/routers/cockpit/__init__.py` | 修改 | include_router(chart_router) |
| 6 | `backend/tests/test_chart_f203a.py` | 新建 | S1–S14 测试用例 |

> ⚠️ 6 文件，正好上限。

---

## 3. 完成标准（可测试）

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| S1 | `_compute_ma_series` period=10 / closes 长度=15 → 返回 6 个点；前 9 个 bar 不输出 | 单元 | pytest |
| S2 | `_compute_ma_series` period >= len(bars) → 返回空列表 | 单元 | pytest |
| S3 | `_compute_atr_series` 已知 OHLC 序列 → 与手算（Wilder）三位小数一致 | 单元 | pytest |
| S4 | `_compute_avwap_series` anchor=bars[0].date → series 长度等于 bars 长度，第一点 value = typical_price[0] | 单元 | pytest |
| S5 | `_compute_avwap_series` anchor 晚于 bars[-1].date → 返回空 | 单元 | pytest |
| S6 | `_compute_avwap_series` anchor 早于 bars[0].date → 等价于 anchor=bars[0].date | 单元 | pytest |
| S7 | `_resolve_anchor`：explicit_anchor 提供 → 返回 explicit；否则查 earnings_events；无 earnings → None | 单元 | pytest（参数化 3 case） |
| S8 | `CockpitChartService.get_chart` 注入 stocks + 250 条 daily_bars + earnings_events → response 含 mas[10/21/50/150/200] + atr + avwap.anchor=earnings_date | 集成 | pytest + in-memory SQLite |
| S9 | service 在 `mas=[5, 250]` 时返回两条序列；`mas=[5]` 单条；`mas=[]` 返回空 dict | 单元 | pytest |
| S10 | router `GET /cockpit/chart/NVDA` 默认参数 → 200，data.bars 非空，data.mas keys = ["10","21","50","150","200"] | 集成 | FastAPI TestClient |
| S11 | router `?mas=10,500` → 422 VALIDATION_ERROR（500 > MA_MAX） | 集成 | TestClient |
| S12 | router `?days=50` → 422（< MIN_DAYS） | 集成 | TestClient |
| S13 | router `?anchor=not-a-date` → 422 | 集成 | TestClient |
| S14 | router ticker 不在 stocks 且 FMP fallback 仍无数据（mock FMP miss）→ 404 NOT_FOUND | 集成 | TestClient + monkeypatch |
| S15 | `pytest backend/tests/` 全量回归通过，无新增 failure（`test_news_api` pre-existing 标注） | 回归 | pytest |

---

## 4. Evaluator 自检清单

### 文件存在性
- [ ] 6 个文件全部存在，路径与表 2 一致
- [ ] 没有触碰 F203-b/c/d 范围内的文件（user_settings / decision_service / DecisionCardWidget / CockpitChartWidget 均不在本 Sprint）

### D063 / D070 合规性
- [ ] `chart_service.py` 不 import 任何 `app/routers` 或 `app/services/stock_detail_service.py` 的代码（仅函数级 utility 复用允许，且仅限 `signal_engine.compute_ma150_series` 之类纯函数；本 Sprint 重写 `_compute_ma_series` 即可，不强制复用）
- [ ] `chart_service.py` 内无任何魔法数字 / 字符串阈值（grep 确认）
- [ ] 所有阈值通过 `from app.services.cockpit.cockpit_params import CHART, SHARED` 引入
- [ ] `cockpit_params.py` 新增字段均带 `Field(description=...)`
- [ ] `CHART = CockpitChartParams()` 模块级实例存在
- [ ] import cockpit_params 无异常

### Schema 合规性
- [ ] response data 字段 camelCase（`avwap.anchor`、`avwap.series`、各 `ChartSeriesPoint.value`）
- [ ] `mas` key 为 period 字符串（与 API-CONTRACT.md 一致）
- [ ] `volume` 字段类型 int（不写 float）

### 算法正确性
- [ ] ATR 使用 Wilder（首条 ATR = SMA(TR, period)，后续 ATR_i = (ATR_{i-1}*(period-1)+TR_i)/period），不使用简单 SMA(TR)
- [ ] AVWAP typical_price = (high+low+close)/3，按累计 PV / 累计 V 计算
- [ ] AVWAP anchor 之前的 bar 不计入累计
- [ ] MA 序列前 period-1 个 bar 不输出（与 design-spec 对齐）

### 测试
- [ ] S1–S15 全部通过
- [ ] S15 全量回归通过

### 代码质量
- [ ] 单个函数不超过 50 行
- [ ] 纯函数（`_compute_*` / `_resolve_anchor`）无 `self`
- [ ] 无 `print` 遗留
- [ ] 无未使用 import
- [ ] router 层不直接计算（计算全部委托 service）

---

## 5. 非目标（明确不做，留给 F203-b/c/d）

- `user_settings` 表 / model / repository / migration（F203-b）
- `decision_service.py`（entry/stop/size 计算）（F203-b）
- `GET /cockpit/decision/{ticker}`、`GET/PUT /cockpit/user-settings`（F203-b）
- `deterministicHash`（F203-b）
- `CockpitChartWidget.tsx` 前端（F203-c）
- `cockpitChartApi.ts`、CockpitRegistry 注册（F203-c）
- `DecisionCardWidget`、`UserSettingsForm` 前端（F203-d）

---

## 6. 开发顺序

1. `services/cockpit/cockpit_params.py` 追加 §3（import 验证通过）
2. `services/cockpit/chart_service.py` 纯函数（`_compute_ma_series` / `_compute_atr_series` / `_compute_avwap_series` / `_resolve_anchor`）
3. `CockpitChartService.get_chart` 编排 + FMP fallback 复用 D041
4. `schemas/cockpit/chart.py` Pydantic
5. `routers/cockpit/chart.py` + `routers/cockpit/__init__.py` 注册
6. 单元 / 集成测试 `test_chart_f203a.py`（S1–S14）
7. 全量 `pytest backend/tests/` 回归（S15）
8. Evaluator 自检清单逐条
9. `features.json` 更新 + `claude-progress.txt` 追加
10. `git commit -m "feat(F203-a): CockpitChart 数据层 + 接入层（chart_service + router + cockpit_params §3）"`

---

## 7. 风险与取舍

- **FMP fallback 路径**：D041 已在 `stock_detail_service.py` 实现 on-demand 拉取；本 Sprint 不复用其完整 service（D063 目录解耦），改为在 `chart_service.py` 内复用 FMP HTTP client 工具函数（若已有）或直接调用 `fetch_daily_bars_fmp`。具体复用边界在 Generator 阶段确认。
- **AVWAP 历史计算成本**：250 条 bars 内 O(n) 累计，无性能问题。
- **MA 周期上限**：MA_MAX=250 与 MAX_DAYS=400 配合保证 `period >= len(bars)` 时返回空（不抛错）。
- **anchor 早于 bars[0]**：取 bars[0].date 作为有效 anchor，避免空响应（保持产品体验）。

---

👤 请确认：

1. **F203 四段拆分**（F203-a chart 数据/接入；F203-b user_settings + decision 数据/接入；F203-c chart widget；F203-d decision card + settings form）→ OK？
2. **CockpitChartParams §3 默认值**（DEFAULT_MAS=[10,21,50,150,200] / DEFAULT_DAYS=250 / ATR_PERIOD=14 / MA_MAX_COUNT=8）→ OK？
3. **MA 序列输出格式**（前 period-1 个 bar 不输出，不返回 None 占位；与 API-CONTRACT.md 示例一致）→ OK？
4. **ATR 算法**（Wilder 而非简单 SMA(TR)）→ OK？
5. **AVWAP anchor 解析顺序**（explicit_anchor → earnings_events 最近 ≤ today → None；不启用 AVWAP_FALLBACK_DAYS）→ OK？
6. **FMP fallback 行为**（ticker 不在 stocks 表时按 D041 on-demand 拉取，不写 daily_bars；FMP miss → 404）→ OK？

全部 OK 后切换 Sonnet 新 session 进入 Generator 模式。
