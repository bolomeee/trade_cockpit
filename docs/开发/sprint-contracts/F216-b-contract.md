# Sprint Contract：F216-b — Weekly Stage Classifier + 持久化 (B2)

> 日期：2026-05-14 | 状态：✅ 已确认（用户 2026-05-14 全部按推荐确认 NP1/NP3/NP4/NP5/NP6/NP7；NP2 二次拍板选 B-2 引入 numpy）
> Feature：F216 Cockpit Phase B — Weekly Stage Layer
> Sub-sprint：F216-b（Phase B 5 子里第 2 个，DB 层 + 分类器）
> 依赖：F216-a done（commit 6e86e75，`WeeklyChartService.get_weekly_chart` 提供聚合输入）
> 引用文档：
>   ARCHITECTURE.md（cockpit/ 模块层 + 新表归入"Cockpit Epic 新增"区）
>   DATA-MODEL.md §MarketRegimeSnapshot / §SetupSnapshot（同类 snapshot 表的字段命名 / repo 模式）
>   完整改善计划：/Users/wonderer/.claude/plans/featrue-dev-replicated-goblet.md §Phase B / B2
>   SRS 扫描报告：docs/对比/cockpit-vs-srs-framework.md

---

## 0. 背景与定位

Phase B 第 2 步 — 把 F216-a 输出的 weekly bars + weekly MAs 喂进 Stan Weinstein **Stage 1–4 分类器**，并落地 `weekly_stage_snapshots` 新表。

**为什么 B2 不动 API/前端**：
- API endpoint 留给 F216-c（Router + Widget），由它负责把 weekly bars + stage 一同返回
- 前端展示留给 F216-c（WeeklyStageChartWidget）/ F216-d（SetupMonitor 新增 WS 列）
- 本 sub-sprint 只交付 **classifier 服务 + 持久化层**，确保 F216-c/d 有 stage 数据可读

**关键约束**：
- 单只 ticker 数据不足（< 30 周可计算 30wMA） → `stage = UNKNOWN`，仍写入快照
- `compute_and_store_all` 仅遍历 **active stocks**（与 setup_service 对齐）
- **新增依赖 `numpy`**（用户 2026-05-14 确认）：用于 OLS 线性回归算 slope_30w。同时为未来 Phase C (ATR/z-score 已手写，待统一) / Phase D (repricing 数值计算) 提供基础设施。按 feature-dev 规则 9 走新依赖流程

---

## 1. 实现范围

**包含**：

### 1.1 ORM Model + 注册
**新文件** `backend/app/models/weekly_stage_snapshot.py`：

```python
class WeeklyStageSnapshot(Base):
    __tablename__ = "weekly_stage_snapshots"
    __table_args__ = (
        UniqueConstraint("ticker", "scan_date", name="uq_weekly_stage_ticker_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    scan_date = Column(Date, nullable=False, index=True)  # 见 NP4
    stage = Column(Integer, nullable=False)                # 0=UNKNOWN, 1-4 见 NP3
    weekly_close = Column(Float, nullable=True)            # UNKNOWN 时可 null
    weekly_ma_10 = Column(Float, nullable=True)
    weekly_ma_30 = Column(Float, nullable=True)
    weekly_ma_40 = Column(Float, nullable=True)
    slope_30w = Column(Float, nullable=True)               # 30wMA 斜率（%/单位见 NP2）
    computed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
```

**修改** `backend/app/models/__init__.py`：1 行 import + `__all__` 追加 `"WeeklyStageSnapshot"`。

### 1.2 Alembic Migration
**新文件** `backend/alembic/versions/019_f216b_weekly_stage_snapshots.py`：
- `revision = "019_f216b_weekly_stage_snapshots"`，`down_revision = "018_f215b_setup_volume_accumulation"`
- `upgrade()`：创建表，含 `uq_weekly_stage_ticker_date` 唯一约束 + `ticker`/`scan_date` 两个独立索引
- `downgrade()`：`op.drop_table("weekly_stage_snapshots")`

### 1.3 Repository
**新文件** `backend/app/repositories/weekly_stage_repository.py`：
```python
class WeeklyStageRepository:
    def __init__(self, db: Session) -> None: ...
    def upsert(self, data: dict) -> WeeklyStageSnapshot: ...   # ON CONFLICT(ticker, scan_date)
    def get_latest_by_ticker(self, ticker: str) -> WeeklyStageSnapshot | None: ...
    def get_latest_for_tickers(self, tickers: list[str]) -> dict[str, WeeklyStageSnapshot]: ...
        # F216-d 接入 setup_service 时需要 N 个 ticker 一次性查最新 stage
    def delete_old(self, cutoff: date) -> int: ...
```

### 1.4 Service：分类器 + compute_and_store
**新文件** `backend/app/services/cockpit/weekly_stage_service.py`：

```python
class WeeklyStageService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._chart = WeeklyChartService(db)
        self._repo = WeeklyStageRepository(db)
        self._stocks = StockRepository(db)

    # ── Public ───────────────────────────────────────────────────────────────
    def classify(self, weekly_bars: list[dict], weekly_ma_10: list, weekly_ma_30: list,
                 weekly_ma_40: list) -> WeeklyStageResult:
        """纯函数：从已聚合的 weekly bars + MAs 输出 stage + 中间量。"""

    def compute_for_ticker(self, ticker: str, scan_date: date | None = None) -> WeeklyStageSnapshot:
        """单只 ticker：调 weekly_chart_service 拉聚合数据 → classify → upsert。"""

    def compute_and_store_all(self, scan_date: date | None = None) -> dict[str, int]:
        """遍历 active stocks → compute_for_ticker；返回 {stage: count} 用于日志/监控。"""

    # ── 内部 ───────────────────────────────────────────────────────────────
    def _compute_slope_30w(self, weekly_ma_30: list[dict]) -> float | None: ...
```

**分类规则**（具体阈值见 NP1，本处给伪码）：

```
若 len(weekly_bars) < WEEKLY_STAGE.MIN_WEEKS_FOR_CLASSIFICATION (30):
    return UNKNOWN

ma30_current = weekly_ma_30[-1]
ma10_current = weekly_ma_10[-1] if available else None
close = weekly_bars[-1].close
slope = _compute_slope_30w(weekly_ma_30)   # %，正负

if abs(slope) <= STAGE1_FLAT_TOL_PCT and abs(close - ma30) / ma30 <= STAGE1_PRICE_BAND_PCT:
    return STAGE_1
if close > ma30 and slope > STAGE2_SLOPE_MIN_PCT and (ma10 is None or ma10 > ma30):
    return STAGE_2
if close < ma30 and slope < -STAGE4_SLOPE_MIN_PCT:
    return STAGE_4
if abs(slope) <= STAGE3_FLAT_TOL_PCT and _ma30_crossings_recent(weekly_bars, ma30_series) >= STAGE3_MIN_CROSSINGS:
    return STAGE_3
return UNKNOWN  # 兜底，不强行归类
```

**返回 schema**：
```python
@dataclass
class WeeklyStageResult:
    stage: int                  # 0/1/2/3/4
    weekly_close: float | None
    weekly_ma_10: float | None
    weekly_ma_30: float | None
    weekly_ma_40: float | None
    slope_30w: float | None     # 百分比，例如 1.5 表示 +1.5%
```

### 1.5 cockpit_params 追加 `WEEKLY_STAGE`
**修改** `backend/app/services/cockpit/cockpit_params.py`：
```python
class CockpitWeeklyStageParams(BaseModel):
    """§6 WEEKLY_STAGE — Stan Weinstein Stage 1-4 classification parameters (F216-b / D091)."""
    model_config = ConfigDict(frozen=True)

    # 数据门槛
    MIN_WEEKS_FOR_CLASSIFICATION: int = Field(default=30, ge=10, le=100,
        description="Min weekly bars required to compute 30wMA and classify stage; below → UNKNOWN")
    SLOPE_LOOKBACK_WEEKS: int = Field(default=5, ge=2, le=26,
        description="Window size (weeks) for OLS regression of 30wMA; uses last N+1 points (current week + N prior)")

    # Stage 1（base / 走平）
    STAGE1_FLAT_TOL_PCT: float = Field(default=2.0, ge=0.1, le=10.0,
        description="|slope_30w| <= this AND price within band → Stage 1")
    STAGE1_PRICE_BAND_PCT: float = Field(default=3.0, ge=0.5, le=10.0,
        description="|close - ma30|/ma30 <= this → 价格在 30wMA 附近震荡")

    # Stage 2（advancing）
    STAGE2_SLOPE_MIN_PCT: float = Field(default=0.5, ge=0.0, le=10.0,
        description="slope_30w > this AND close > 30wMA AND 10wMA>30wMA → Stage 2")

    # Stage 3（distribution / topping）
    STAGE3_FLAT_TOL_PCT: float = Field(default=2.0, ge=0.1, le=10.0,
        description="|slope_30w| <= this AND 反复穿越 30wMA → Stage 3")
    STAGE3_CROSSING_LOOKBACK_WEEKS: int = Field(default=10, ge=4, le=26,
        description="Look-back weeks to count close-vs-30wMA crossings")
    STAGE3_MIN_CROSSINGS: int = Field(default=3, ge=2, le=10,
        description="Min crossings in lookback to qualify as Stage 3")

    # Stage 4（declining）
    STAGE4_SLOPE_MIN_PCT: float = Field(default=0.5, ge=0.0, le=10.0,
        description="slope_30w < -this AND close < 30wMA → Stage 4")

    # 数据保留
    WEEKLY_STAGE_RETENTION_DAYS: int = Field(default=60, ge=7, le=365,
        description="Days to retain weekly_stage snapshots (与 SetupSnapshot 对齐)")

WEEKLY_STAGE = CockpitWeeklyStageParams()
```

**Stage 枚举常量**（建议作为模块级常量定义在 weekly_stage_service.py 内，不放 params）：
```python
STAGE_UNKNOWN = 0
STAGE_1 = 1
STAGE_2 = 2
STAGE_3 = 3
STAGE_4 = 4
```

### 1.6 单元测试
**新文件** `backend/tests/test_weekly_stage_service.py`：覆盖 §3 标准 1–13。

### 1.7 文档同步
- `docs/系统设计/DATA-MODEL.md` 追加 `WeeklyStageSnapshot` 实体章节（在 SetupSnapshot 之后）+ ORM 类（在底部 Cockpit Epic ORM 区）
- `docs/系统设计/DECISIONS.md` 追加 **D091** — "F216-b Weekly Stage 量化判定细则"

**明确排除（本 sub-sprint 不做）**：
- API endpoint（`GET /cockpit/chart/{ticker}/weekly` 由 F216-c 承担）
- 前端 widget（F216-c WeeklyStageChartWidget + F216-d SetupMonitor 加 WS 列）
- `setup_service` 接入 weekly_stage gate（F216-d 承担 — 含 setup_snapshots 新增 weekly_stage 列、ready_signal 强制门）
- `refresh_job` cron（F216-e 承担 22:20 UTC daily cron）
- 历史回测验证（NVDA 2022 Stage 3 / 2023 Stage 2）— 数据窗口由 F216-a 限定 50 周，回测在 plan 中预留为未来扩窗 feature

---

## 2. 预计修改文件（共 7 个代码 + 2 个依赖配置，方案 A 不拆分）

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `backend/app/models/weekly_stage_snapshot.py` | 新建 | ORM model |
| `backend/app/models/__init__.py` | 修改 | 注册（1 行 import + `__all__`） |
| `backend/alembic/versions/019_f216b_weekly_stage_snapshots.py` | 新建 | 建表 + 唯一约束 |
| `backend/app/repositories/weekly_stage_repository.py` | 新建 | upsert / get_latest / get_latest_for_tickers / delete_old |
| `backend/app/services/cockpit/weekly_stage_service.py` | 新建 | classify (纯函数) + compute_for_ticker + compute_and_store_all |
| `backend/app/services/cockpit/cockpit_params.py` | 修改 | 末尾追加 `CockpitWeeklyStageParams` 类 + `WEEKLY_STAGE` 实例（不动现有 5 组） |
| `backend/tests/test_weekly_stage_service.py` | 新建 | 单测 13 条（§3） |

依赖配置（feature-dev 规则 9 新依赖流程）：
| `backend/pyproject.toml` | 修改 | `dependencies` 追加 `"numpy>=2.0,<3"`（具体下限由 Generator step 1 context7 查询确认） |
| `backend/uv.lock` | 自动生成 | `uv lock` 重新求解；提交时一起 commit |

附加文档（不计入代码 6 文件原则）：
- `docs/系统设计/DATA-MODEL.md` — 新增 WeeklyStageSnapshot 章节 + ORM 类
- `docs/系统设计/DECISIONS.md` — 追加 **D091**（Stage 量化判定细则）+ **D092**（引入 numpy 的决策）

⚠️ 用户已确认走方案 A（不拆分）。代码文件 7 个不变，依赖配置 2 个不计入 6 文件原则（属于 infra，类似 alembic migration）。

---

## 3. 可测试的完成标准

| # | 标准 | 测试层级 | 工具 |
|---|------|---------|------|
| 1 | `WeeklyStageService.classify` 在 weekly_bars=[] 或 weekly_bars < 30 周时返回 `WeeklyStageResult(stage=UNKNOWN, ..., slope_30w=None)` | 单元 | pytest |
| 2 | Stage 2 fixture：构造 weekly bars 使 30wMA 单调上升（slope > 0.5%）、close > 30wMA、10wMA > 30wMA → `classify` 返回 `stage=2` | 单元 | pytest |
| 3 | Stage 4 fixture：构造 weekly bars 使 30wMA 单调下降（slope < -0.5%）、close < 30wMA → `classify` 返回 `stage=4` | 单元 | pytest |
| 4 | Stage 1 fixture：30wMA 走平（|slope| ≤ 2%）+ close 在 30wMA ±3% 内震荡 → `classify` 返回 `stage=1` | 单元 | pytest |
| 5 | Stage 3 fixture：30wMA 走平 + 过去 10 周 close 跨越 30wMA ≥ 3 次 → `classify` 返回 `stage=3` | 单元 | pytest |
| 6 | "兜底"场景：close > 30wMA 但 slope ≈ 0 且不满足 Stage 1 价格带、不满足 Stage 3 穿越条件 → 返回 `stage=UNKNOWN`（不强行归类） | 单元 | pytest |
| 7 | `_compute_slope_30w(ma_series)` 在 len(ma_series) < SLOPE_LOOKBACK_WEEKS+1 时返回 `None`；否则对最后 N+1 个点做 OLS 线性回归，返回 `(beta / mean_y) * 100`（单位：%/周）。单调上升 fixture（每周 +1.0）应返回正值；单调下降 fixture（每周 -1.0）应返回负值；常数序列应返回 0.0 | 单元 | pytest |
| 8 | `WeeklyStageRepository.upsert` 同 (ticker, scan_date) 二次写入更新原行，不新增（uq 约束生效） | 单元 + DB fixture | pytest + sqlite in-memory |
| 9 | `WeeklyStageRepository.get_latest_for_tickers(["AAPL","NVDA"])` 返回 dict，缺失 ticker 不出现在结果中（不抛错） | 单元 | pytest |
| 10 | `compute_for_ticker("UNKNOWN_TICKER")` 抛 `APIError("NOT_FOUND", ...)`（沿用 watchlist_service.APIError） | 单元 | pytest mock |
| 11 | `compute_for_ticker("AAPL")` 数据不足（mock daily_bars 仅 50 行 ≈ 10 周）→ 写入 stage=UNKNOWN 行，`weekly_close/mas/slope` 全为 null | 单元 | pytest |
| 12 | `compute_and_store_all()` 遍历 active stocks（mock 3 只）→ 各写 1 行；返回 `{0: n0, 1: n1, 2: n2, 3: n3, 4: n4}` 计数 dict | 单元 | pytest |
| 13 | alembic upgrade head 创建表 + 唯一约束；downgrade 回滚干净 | 集成 | pytest + alembic command |
| 14 | 全量后端 pytest 套件无新增失败（test_decision_f203b.py 预存 ImportError 例外） | 回归 | pytest |

---

## 4. Evaluator 自检清单

### 功能测试
- [ ] 标准 1–13 全部通过
- [ ] 标准 14 回归通过（test_decision_f203b.py 预存例外保持）

### 代码质量
- [ ] `classify` 是纯函数（不持有 db Session，仅消费 weekly_bars + MAs）
- [ ] `WeeklyStageService.compute_for_ticker` 复用 `self._chart.get_weekly_chart(ticker)` —— 不重新写聚合
- [ ] 无硬编码魔法值（30 / 0.5 / 2.0 / 3.0 / 10 / 3 全部引用 `WEEKLY_STAGE.*`）
- [ ] 沿用 `app.services.watchlist_service.APIError`，不自定义新异常
- [ ] 函数 < 50 行；`classify` 主逻辑 ≤ 50 行（分类规则可读、不嵌套地狱）
- [ ] 无新增 `print` / `console.error`；写入 SystemLog 用 WARN 级
- [ ] 无 SQLAlchemy 1.x 风格（不用 `query()`，统一 `select()`）

### 新依赖
- [ ] `pyproject.toml` `dependencies` 含 `numpy>=2.0,<3`（或 context7 查询确认的版本约束）
- [ ] `uv.lock` 已通过 `uv lock` 重生成并 commit
- [ ] `numpy` 在本 sub-sprint 范围内**仅** `weekly_stage_service.py` 使用；其他文件 0 引用（grep `import numpy` / `from numpy` 在 backend/app 应只有 1 个命中）
- [ ] DECISIONS.md D092 明确："numpy 引入范围 = cockpit 数值计算（slope/std/regression 等）；不允许蔓延到 router / repo / models 层"

### 文档同步
- [ ] DATA-MODEL.md 新增 WeeklyStageSnapshot 章节（结构同 SetupSnapshot），含字段表 + 业务规则 + ORM 类
- [ ] DECISIONS.md 追加 D091（含 NP1–NP7 最终选定值的理由）
- [ ] API-CONTRACT.md：**零改动**（endpoint 由 F216-c 落地）

### 集成边界
- [ ] `cockpit_params.py` 仅末尾追加新类组，不动现有 SHARED / REGIME / SETUP / CHART / DECISION / WEEKLY
- [ ] `models/__init__.py` 仅追加注册行，不改原有行顺序
- [ ] alembic 019 的 `down_revision` 必须等于 `"018_f215b_setup_volume_accumulation"`（不要改动 018 链）
- [ ] grep 验证 `WeeklyStageService` / `weekly_stage_service` 在 backend/app 其他文件 0 引用（确认本 sub-sprint 隔离，F216-d/e 后续接入）

### Sprint Contract 流转
- [ ] phase 切换：design_needed → contract_agreed（本 contract 确认时）→ in_progress（Generator 启动）→ testing（写完）→ needs_review（Evaluator 全清）
- [ ] Evaluator 通过后调 consistency-check skill (mode=interactive) 验 C1/C4/C5
- [ ] sub_sprints["F216-b"] 同步更新到 "done"

---

## 5. 实现要点（给 Generator 参考）

### 5.1 slope_30w 计算（numpy OLS，单位 %/周）

```python
import numpy as np

def _compute_slope_30w(self, weekly_ma_30: list[dict]) -> float | None:
    """对最后 N+1 个 ma 值做 numpy 一阶最小二乘拟合，归一化为 %/周。

    ma series schema：[{"date": ..., "value": float}, ...]（沿用 _compute_ma_series 输出）
    返回：beta / mean_y * 100，含义"每周 30wMA 变化的百分比"
    """
    n = WEEKLY_STAGE.SLOPE_LOOKBACK_WEEKS
    points = weekly_ma_30[-(n + 1):]
    if len(points) < n + 1:
        return None
    values = [p["value"] for p in points if p.get("value") is not None]
    if len(values) < n + 1:
        return None

    y = np.asarray(values, dtype=float)
    x = np.arange(y.size, dtype=float)
    beta, _intercept = np.polyfit(x, y, deg=1)          # 一阶最小二乘
    y_mean = float(y.mean())
    if y_mean == 0:
        return None
    return float(beta / y_mean) * 100                    # 归一化为 %/周
```

**单位说明**（写进 D091）：`slope_30w` 字段单位是 **% per week**，例如 `1.5` 表示 30wMA 每周以 1.5% 速度上升。
所有 Stage 判定阈值（`STAGE2_SLOPE_MIN_PCT` 等）都按 %/周 比较，不是累计百分比。

**numpy 导入位置**：模块顶部 `import numpy as np`，不延迟到函数内（启动期 import 一次，~50ms 一次性成本即可）。

### 5.2 Stage 3 反复穿越计数
```python
def _ma30_crossings_recent(self, weekly_bars: list[dict], ma30_series: list[dict]) -> int:
    """统计过去 STAGE3_CROSSING_LOOKBACK_WEEKS 周内 close 跨越 30wMA 的次数（上穿 + 下穿）"""
    window = WEEKLY_STAGE.STAGE3_CROSSING_LOOKBACK_WEEKS
    # ma_series 长度可能 < weekly_bars（前 29 周无 30wMA），按 date 对齐
    aligned = _align_by_date(weekly_bars, ma30_series)[-window:]
    crossings = 0
    for i in range(1, len(aligned)):
        prev_diff = aligned[i-1]["close"] - aligned[i-1]["ma30"]
        curr_diff = aligned[i]["close"] - aligned[i]["ma30"]
        if prev_diff * curr_diff < 0:  # 符号翻转 = 穿越
            crossings += 1
    return crossings
```

### 5.3 compute_for_ticker 流程
```python
def compute_for_ticker(self, ticker: str, scan_date: date | None = None) -> WeeklyStageSnapshot:
    ticker = ticker.strip().upper()
    if self._stocks.get_by_ticker(ticker) is None:
        raise APIError("NOT_FOUND", f"ticker {ticker} not found", 404)

    chart = self._chart.get_weekly_chart(ticker)  # 注：APIError 由 self._chart 抛
    result = self.classify(
        chart["weekly_bars"],
        chart["weekly_mas"]["10"],
        chart["weekly_mas"]["30"],
        chart["weekly_mas"]["40"],
    )

    actual_scan_date = scan_date or self._derive_scan_date(chart["weekly_bars"])  # 见 NP4
    return self._repo.upsert({
        "ticker": ticker,
        "scan_date": actual_scan_date,
        "stage": result.stage,
        "weekly_close": result.weekly_close,
        "weekly_ma_10": result.weekly_ma_10,
        "weekly_ma_30": result.weekly_ma_30,
        "weekly_ma_40": result.weekly_ma_40,
        "slope_30w": result.slope_30w,
        "computed_at": datetime.now(timezone.utc),
    })
```

### 5.4 active stocks 迭代（compute_and_store_all）
参考 `setup_service.py:476` 写法：`select(Stock).where(Stock.active == True)`（或既有 active 标识字段，Generator 阶段对齐 setup_service 用法）。

---

## 6. 开发顺序（Generator 阶段，不得跳步）

1. **新依赖前置（feature-dev 规则 9）**：通过 context7 查 numpy 最新稳定版及 `polyfit` API 现状（推荐 `mcp__context7__resolve-library-id` → `query-docs`），记录到 DECISIONS.md D092 草稿
2. 修改 `backend/pyproject.toml` 追加 `"numpy>=2.0,<3"`（具体下限以 context7 查询结果为准），跑 `uv lock` 重生成 `uv.lock`
3. **WIP commit** `chore(F216-b): add numpy dependency for OLS slope`（pyproject.toml + uv.lock 两个文件）
4. 重读 `backend/app/services/cockpit/weekly_chart_service.py` 确认 weekly_bars / weekly_mas schema
5. 重读 `backend/app/services/cockpit/market_regime_service.py` + `market_regime_repository.py` 学 upsert/repo 模式
6. 在 `backend/app/services/cockpit/cockpit_params.py` 末尾追加 `CockpitWeeklyStageParams` + `WEEKLY_STAGE` 实例
7. 新建 `backend/app/models/weekly_stage_snapshot.py` ORM 类
8. 修改 `backend/app/models/__init__.py` 注册（import + `__all__`）
9. 新建 `backend/alembic/versions/019_f216b_weekly_stage_snapshots.py`
10. **WIP commit** `wip(F216-b): alembic 019 + ORM model + params`（4 文件）
11. 新建 `backend/app/repositories/weekly_stage_repository.py`
12. 新建 `backend/app/services/cockpit/weekly_stage_service.py`：先 `import numpy as np` + dataclass + `classify` 纯函数 + `_compute_slope_30w`（numpy OLS） + `_ma30_crossings_recent`
13. 新建 `backend/tests/test_weekly_stage_service.py`：跑标准 1–7（纯 classify 单测，含 numpy slope 三组 fixture）
14. **WIP commit** `wip(F216-b): repo + classify pure function + 7 unit tests`
15. 补 service 的 `compute_for_ticker` + `compute_and_store_all`
16. 补测试标准 8–13（含 alembic migration up/down 集成测试）
17. 跑全量 pytest 验证标准 14 回归
18. 更新 DATA-MODEL.md（新增 WeeklyStageSnapshot 章节 + ORM 类）
19. 更新 DECISIONS.md（追加 **D091** Stage 量化判定 + **D092** 引入 numpy）
20. Evaluator 自检 → 全清 → consistency-check skill (mode=interactive) → 切 needs_review
21. **Final commit** `feat(F216-b): Weekly Stage Classifier + persistence`（显式列文件，不用 `-A`）

---

## 7. 风险与对策

| 风险 | 对策 |
|------|------|
| Stage 1 / Stage 3 "走平"的容差阈值都设 2%，可能落入互判区 | 算法**优先级**：Stage 2/4 先判（明显趋势），再判 Stage 1（窄价格带）；最后判 Stage 3（多次穿越）。同时满足 Stage 1+3 时 Stage 1 优先（因 Stage 3 需要"反复穿越"额外条件，Stage 1 是 base） |
| `_compute_ma_series` 输出长度 < weekly_bars 长度（前 N-1 周无 MA） | 标准 5 测试用例显式覆盖此对齐；`_ma30_crossings_recent` 按 date 对齐 + take last N |
| weekly_bars 不够 30 周但够 10 周 | 仍写 UNKNOWN 快照，weekly_ma_10 字段可有值（仅 30wMA 缺）。这是 F216-d 的 setup gate 看到的"无法判定"信号 |
| 跨年周（ISO 边界）影响 slope 计算 | slope 用 ma 序列下标算（lookback=5 个 list 位置），与 ISO 周边界无关 |
| compute_and_store_all 在 watchlist 100 只时跑多久 | 每只跑一次 `get_weekly_chart`（一次 sqlite query + 内存聚合），总耗时预估 < 5s。本 sub-sprint 不做 batch 优化；若 F216-e cron 跑超 30s 再考虑预聚合缓存 |
| F216-d 接入时发现 stage Int 字段不够表达细节（如 Stage 2 早期 / 后期） | 不在本 sub-sprint 处理；未来需要时增列（slope_strength），不破坏现有 stage 字段 |
| Stage 3 阈值实际跑出来全是 UNKNOWN | DECISIONS.md D091 记录"参数为初始值，F216 整 phase 验收后回顾调参"。本 sub-sprint 不引入历史回测装置 |

---

## 8. 不在本 sub-sprint 范围

- 历史回测验证（NVDA 2022/2023 案例）— plan 中已标"留待扩窗 feature"
- Stage 中文/英文标签翻译（"Base / Advancing / Distribution / Declining"）— F216-c widget 负责
- WeeklyStageSnapshot 与 SetupSnapshot JOIN 查询优化 — F216-d 自行决定 join 方式
- API endpoint / Pydantic schema 暴露 — F216-c
- 调度器 cron 注册 — F216-e

---

## 9. 协商点（NP1–NP7，需用户拍板）

### NP1 — Stage 分类阈值默认值（✅ 用户 2026-05-14 全部按推荐）

| 参数 | 推荐值 | 含义 |
|------|--------|------|
| `MIN_WEEKS_FOR_CLASSIFICATION` | **30** | < 30 周无法算 30wMA，直接 UNKNOWN |
| `SLOPE_LOOKBACK_WEEKS` | **5** | 30wMA 5 周前对比，~1 个月趋势 |
| `STAGE1_FLAT_TOL_PCT` | **2.0** | \|slope\| ≤ 2% 视为走平（与 SRS "±2%" 原文一致） |
| `STAGE1_PRICE_BAND_PCT` | **3.0** | close 距 30wMA ≤ 3% 视为"附近震荡" |
| `STAGE2_SLOPE_MIN_PCT` | **0.5** | slope > 0.5% 才算上行（避免 0 附近抖动归入 Stage 2） |
| `STAGE3_FLAT_TOL_PCT` | **2.0** | 与 Stage 1 同（拓扑上 1/3 都需 30wMA 走平，靠穿越次数区分） |
| `STAGE3_CROSSING_LOOKBACK_WEEKS` | **10** | 过去 10 周（2.5 月） |
| `STAGE3_MIN_CROSSINGS` | **3** | ≥ 3 次穿越 = "反复" |
| `STAGE4_SLOPE_MIN_PCT` | **0.5** | slope < -0.5% 才算下行 |

→ 推荐：**全部采纳上表默认值**，理由：(a) 数值来自 SRS 第四节 + Stan Weinstein 原书的经验值；(b) 全部参数化进 `WEEKLY_STAGE`，未来调参不需要改代码；(c) D091 会记录"参数为初始值，phase B 整体验收后回顾"。

→ 备选 B：用户给出自己的偏好值（例如 STAGE2_SLOPE_MIN_PCT 改成 1.0 更严格）。

### NP2 — slope_30w 计算方法（✅ 用户 2026-05-14 选 B + numpy）

| 选项 | 公式 | 实现 | 说明 |
|------|------|------|------|
| A | `(ma[-1] / ma[-(N+1)] - 1) * 100` | 1 行端点法 | 只用 2 个点，与 30wMA 平滑度匹配但抗噪空间小 |
| B-1 | OLS 线性回归 | 8 行纯 Python | 无新依赖，但 6 行 → 8 行换可读性 |
| **B-2（已选）** | OLS 线性回归 `np.polyfit(x, y, 1)[0] / mean(y) * 100`，单位 %/周 | `numpy>=2.0` | 1 行表达；为 Phase C/D 数值计算预埋基础设施 |

→ 用户选 B-2 的理由：未来若把 `SLOPE_LOOKBACK_WEEKS` 缩短，OLS 抗噪优势显著；numpy 同时为 Phase C (ATR / z-score 当前手写) / Phase D (repricing) 提供数值库。代价：依赖 +~25MB，启动 +~50ms（一次性），DECISIONS.md 追加 **D092**（引入 numpy 的范围与版本约束）。

**Generator 阶段 step 1 强制动作**：通过 context7 (`/numpy/numpy` 或 `resolve-library-id`) 查询 numpy 最新稳定版，确认 `polyfit` API 在 2.x 与 1.x 行为一致（应一致，但走规则 9 留痕），然后在 pyproject 写入约束。

### NP3 — stage 字段类型 + UNKNOWN 表示（✅ 用户 2026-05-14 选 A）

| 选项 | 类型 | UNKNOWN | 说明 |
|------|------|---------|------|
| **A（推荐）** | `Integer NOT NULL` | `0` | 与 plan 原文 "stage 1-4" 一致；0 作为哨兵值；前端 `if stage === 0` 显示"未知" |
| B | `String(8) NOT NULL` | `"UNKNOWN"` | 更可读但占空间；前端要做字符串映射 |
| C | `Integer nullable` | `NULL` | DB 行少一列值；但 setup_service 写 `weekly_stage == 2` 时 NULL 处理稍麻烦 |

→ 推荐 A。理由：Int 聚合方便（`COUNT(*) WHERE stage = 2`）；0 作为哨兵不会被 setup_service 误判为 Stage 2；F216-d 设计 `setup_snapshots.weekly_stage INT NOT NULL DEFAULT 0` 也是 Int。

### NP4 — scan_date 语义（uniq key 的一半）（✅ 用户 2026-05-14 选 A）

| 选项 | 取值 | 说明 |
|------|------|------|
| **A（推荐）** | 本周最后实际交易日（= weekly_bars[-1].date） | 每周一个快照（即使 cron 一天跑多次，同周 upsert 不增行）。Stage 演变曲线天然按周对齐 |
| B | cron 当日（date.today()） | 每个交易日一行，量级 ×5；同周 Stage 内可见日内细节但意义不大 |
| C | scan_date 入参 = None 时用 today，传值则用入参 | 接口灵活但破坏唯一性语义 |

→ 推荐 A。理由：周线 Stage 本身就是周级语义；保留窗口（60d）≈ 12 行/ticker，DB 体积可控；与 SetupSnapshot 每日一行不同，因为 weekly 数据天然每周才更新一次。

### NP5 — `compute_and_store_all` 输入 ticker 范围（✅ 用户 2026-05-14 选 A）

| 选项 | 范围 | 说明 |
|------|------|------|
| **A（推荐）** | `active_stocks`（与 setup_service 一致） | Stage 仅服务于 setup gating，非 watchlist ticker 无意义 |
| B | 所有 stocks 表行 | 浪费算力；非 watchlist 不会被 setup_service 读 |
| C | 入参 `tickers: list[str] \| None`，None 时走 A | 灵活但 cron 注册时还是用 A |

→ 推荐 A。

### NP6 — 保留窗口（`WEEKLY_STAGE_RETENTION_DAYS`）（✅ 用户 2026-05-14 选 A）

| 选项 | 天数 | 说明 |
|------|------|------|
| **A（推荐）** | **60** | 与 `SETUP_RETENTION_DAYS=60` 对齐；约 12 周 Stage 演变 |
| B | 180 | 半年历史，便于看 Stage 转换历程 |
| C | 永久（不删） | 数据量小（100 ticker × 50 周/年 = 5k 行/年），可行；但破坏既有"snapshot 表都有 retention"惯例 |

→ 推荐 A。理由：60 天足以看到 Stage 1→2 / 2→3 一次转换；与 setup 对齐便于联合查询；后期若不够再调 D091 即可。

### NP7 — 数据不足时的快照行为（✅ 用户 2026-05-14 选 A）

| 选项 | 行为 | 说明 |
|------|------|------|
| **A（推荐）** | 写入 `stage=0(UNKNOWN)`，其他字段 nullable 全填 null | F216-d setup gate 看到 stage=0 即 `ready_signal=false`，F216-c widget 显示"数据不足"。审计闭环 |
| B | 不写入（跳过该 ticker） | DB 干净但 F216-d 要单独判"snapshot 不存在 = UNKNOWN"，逻辑多一层 |
| C | 抛 `APIError("INSUFFICIENT_DATA")` | 太严，新加 watchlist 的 ticker 自然不足，常态不该报错 |

→ 推荐 A。

---

## 10. 用户确认区

✅ **2026-05-14 用户全部确认**：
- NP1 Stage 阈值：全部用推荐默认（9 个参数见 §1.5）
- NP2 slope 计算：选 **B-2**（引入 numpy + `np.polyfit`，单位 %/周）
- NP3 stage 字段：Integer NOT NULL，UNKNOWN=0
- NP4 scan_date：本周最后实际交易日（与 weekly bar.date 一致，每周一行）
- NP5 compute_and_store_all 范围：active_stocks
- NP6 保留窗口：60 天
- NP7 数据不足行为：写入 stage=0 + 其他字段 null，不抛错

Contract 定稿。下一步：本 session 仅更新 features.json + SESSION-HANDOFF.md，**不写代码**。Generator 阶段建议新 session 启动（粘 §6 step 1 指令）。
