# Sprint Contract：F216-a — Weekly Aggregation Service (B1)

> 日期：2026-05-14 | 状态：✅ 已确认（用户 2026-05-14 全部按推荐方案确认 NP1/NP2/NP3/NP4）
> Feature：F216 Cockpit Phase B — Weekly Stage Layer
> Sub-sprint：F216-a (Phase B 5 子里第 1 个，foundation 层)
> 依赖：F215 done（Phase A 已交付）
> 引用文档：
>   ARCHITECTURE.md（cockpit/ 模块层）
>   DATA-MODEL.md §Entity: DailyBar（聚合数据源；本 sub-sprint 不改 schema）
>   完整改善计划：/Users/wonderer/.claude/plans/featrue-dev-replicated-goblet.md §Phase B / B1

---

## 0. 背景与定位

Phase B 落地 Stan Weinstein 周线分层（Stage 1-4），用于过滤日线 setup 候选。第一步 **F216-a 不暴露 API、不动 DB schema、不动前端** — 只产出一个**纯服务层**：从已有 `daily_bars` 聚合出周线 + Weekly MA 10/30/40，为后续 F216-b（Stage 分类器）/ F216-c（router + widget）/ F216-d（setup gate）打底。

**为什么先做 service 再做 stage 分类**：B1 是数学聚合，B2 是规则判定。混在同一 sub-sprint 中文件数会超 6（B2 还要加新表 + alembic）。先把"聚合纯函数 + 数据加载"独立验证，B2 可直接复用其输出。

**关键约束**（用户已确认 2026-05-14）：
- `weeks` 默认 50（与现有 `DAILY_BAR_WINDOW=250 ≈ 50 周` 匹配），**不接受 5 年默认值**
- 零 FMP 调用 — 仅从 `daily_bars` 表读取，miss 时返回空（caller 决定如何处理）
- 5 年历史回测（NVDA 2022 Stage 3）不在本 sub-sprint 验收范围 — 留待未来扩窗 feature

---

## 1. 实现范围

**包含**：

1. **新文件**：`backend/app/services/cockpit/weekly_chart_service.py`
   - 纯函数 `aggregate_daily_to_weekly(daily_bars: list[BarDict]) -> list[WeeklyBarDict]`：
     - 输入：升序 daily bars（dict 含 date/open/high/low/close/volume）
     - 分组键：`bar.date.isocalendar()[:2]` （ISO year, ISO week）
     - 输出每周：open=本周首日 open，high=max(week.high)，low=min(week.low)，close=本周末日 close，volume=sum(week.volume)，date=**本周最后一日的实际交易日**（不强制周五；周五休市时退回到周四）
     - 输出按 date 升序
     - 空输入返回 []
     - 单日不足一周（孤立工作日）也算一周，weekly bar 等于该日 OHLC
   - Service 类 `WeeklyChartService(db: Session)`：
     - `__init__`：注入 Session，内部建 `StockRepository`
     - `get_weekly_chart(ticker: str, weeks: int = 50) -> dict`：
       - 解析 ticker（strip().upper()），查 Stock
       - Stock 不存在 → 抛 `APIError("NOT_FOUND", ...)`（沿用 `app.services.watchlist_service.APIError`）
       - 从 `daily_bars` 取该 stock 全部行（升序），通过 `aggregate_daily_to_weekly` 聚合
       - 截取最新 N 周（list[-weeks:]）
       - 调用现有 `chart_service._compute_ma_series(weekly_bars, period)` 算 Weekly MA 10 / 30 / 40
       - 返回 `{"ticker": ticker, "weekly_bars": [...], "weekly_mas": {"10": [...], "30": [...], "40": [...]}}`
     - 零 FMP：daily_bars 行数 < 4 时（连一周都凑不出）返回空 weekly_bars + 空 mas，**不报错**

2. **新文件**：`backend/tests/test_weekly_chart_service.py` — 单元测试套件（标准 1-9，见 §3）

3. **修改文件**：`backend/app/services/cockpit/cockpit_params.py`
   - 新增 `WEEKLY` 类常量分组：
     - `DEFAULT_WEEKS: int = 50`（默认输出周数）
     - `WEEKLY_MAS: list[int] = [10, 30, 40]`（Weekly MA 周期）
     - `MIN_DAILY_BARS_FOR_WEEKLY: int = 4`（不足 4 日的 stock 不聚合）

**明确排除（本 sub-sprint 不做）**：

- 任何 API endpoint（router 不动） — 由 F216-c 承担
- 任何 DB schema 变更 / Alembic migration — 由 F216-b、F216-d 承担
- Weekly Stage 1-4 分类逻辑 — 由 F216-b 承担
- 任何前端代码 — 由 F216-c 承担
- 任何 setup_service 接入 — 由 F216-d 承担
- 任何 scheduler 改动 — 由 F216-e 承担
- daily_bars 窗口扩容（DAILY_BAR_WINDOW 250 不动） — 用户已确认本期不做
- FMP fallback 加载 — 设计排除
- ISO 周强制周五对齐（plan 提到的"week_end_date=周五"被改为"本周最后实际交易日"，更贴近真实数据）

---

## 2. 预计修改文件（共 3 个）

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `backend/app/services/cockpit/weekly_chart_service.py` | 新建 | `aggregate_daily_to_weekly` + `WeeklyChartService.get_weekly_chart` |
| `backend/app/services/cockpit/cockpit_params.py` | 修改 | 追加 `WEEKLY` 配置组（不影响现有 CHART/REGIME/SETUP） |
| `backend/tests/test_weekly_chart_service.py` | 新建 | 单元测试 9 条 + 集成测试 1 条（覆盖 §3 全部完成标准） |

✅ 远低于 6 文件上限。

---

## 3. 可测试的完成标准

| # | 标准 | 测试层级 | 工具 |
|---|------|---------|------|
| 1 | `aggregate_daily_to_weekly([])` 返回 [] | 单元 | pytest |
| 2 | `aggregate_daily_to_weekly` 对 1 周 5 个交易日（周一–周五）输入返回 1 个 weekly bar，open=周一 open，high=max(5 高)，low=min(5 低)，close=周五 close，volume=sum(5 volume)，date=周五 | 单元 | pytest fixture |
| 3 | 跨周分组：2 周 10 个交易日输入返回 2 个 weekly bars，分别归属各自 ISO 周（用 `2026-05-04` 周一 ~ `2026-05-15` 周五构造） | 单元 | pytest |
| 4 | 周五休市的"短周"：周一–周四 4 交易日，weekly bar.date = 周四（不强制周五） | 单元 | pytest |
| 5 | 孤立单日：单一交易日输入返回 1 个 weekly bar 等于该日 OHLC，volume=该日 volume | 单元 | pytest |
| 6 | `WeeklyChartService.get_weekly_chart("UNKNOWN")` 抛 `APIError("NOT_FOUND", ...)` | 单元 | pytest mock db |
| 7 | `WeeklyChartService.get_weekly_chart("AAPL", weeks=50)` 在 mock daily_bars (250 行) 返回 `weekly_bars` 长度 ≈ 50，`weekly_mas["10"]/["30"]/["40"]` 长度按 `_compute_ma_series` 语义（period < len(weekly_bars) 才返回非空） | 单元 | pytest |
| 8 | daily_bars 行数 < 4 时（如 3 行）`get_weekly_chart` 返回 `{"ticker": T, "weekly_bars": [], "weekly_mas": {"10": [], "30": [], "40": []}}`，**不抛错** | 单元 | pytest |
| 9 | `WEEKLY.DEFAULT_WEEKS == 50` 且 `WEEKLY.WEEKLY_MAS == [10, 30, 40]`（防止误改） | 单元 | pytest |
| 10 | 全量后端 pytest 套件无新增失败（test_decision_f203b.py 预存 ImportError 例外） | 回归 | pytest |

---

## 4. Evaluator 自检清单

### 功能测试
- [ ] 标准 1-9 全部通过
- [ ] 标准 10 回归通过

### 代码质量
- [ ] `aggregate_daily_to_weekly` 是纯函数（不依赖 Session 或外部状态）
- [ ] `WeeklyChartService.get_weekly_chart` 仅依赖 Session + StockRepository，**不调 FMP**（grep 验证 `fmp_client` 在 weekly_chart_service.py 内 0 命中）
- [ ] 复用 `chart_service._compute_ma_series` 计算 Weekly MA，**不重新实现 SMA**
- [ ] 沿用 `app.services.watchlist_service.APIError` 错误类型（不自定义新异常）
- [ ] 函数 < 50 行
- [ ] 无硬编码魔法值（50 / 10 / 30 / 40 / 4 都引用 `WEEKLY.*` 常量）
- [ ] 无新增 console.error / print（除 logging）

### 文档同步
- [ ] DATA-MODEL.md：零改动（DailyBar 表不变，WeeklyStageSnapshot 由 F216-b 落地）
- [ ] API-CONTRACT.md：零改动（endpoint 由 F216-c 落地）
- [ ] DECISIONS.md：**追加 1 条决策** — 编号在 D089 之后顺延（具体号由 Generator 阶段查 DECISIONS.md 最大号 + 1）：
  - 标题："F216-a Weekly 聚合采用 ISO 周分组，week date 跟随实际最后交易日"
  - 内容：拒绝"强制 week_end_date=周五"方案的理由（短周/周五休市处理；与 lightweight-charts 周线显示约定一致）

### 集成边界
- [ ] `WeeklyChartService` 不修改任何现有文件的现有行（cockpit_params.py 仅追加新类组，不改现有 CHART/REGIME/SETUP/POOL）
- [ ] grep 验证 `weekly_chart_service` 在 backend/app 其他文件 0 引用（确认本 sub-sprint 隔离）

---

## 5. 实现要点（给 Generator 参考）

### 5.1 类型定义
weekly_chart_service.py 内部定义 TypedDict：
```python
class WeeklyBarDict(TypedDict):
    date: date          # 本周最后实际交易日
    open: float
    high: float
    low: float
    close: float
    volume: int
```
不导出到 schema 层（本 sub-sprint 无 API 暴露）。

### 5.2 聚合算法
```python
def aggregate_daily_to_weekly(daily_bars: list[BarDict]) -> list[WeeklyBarDict]:
    if not daily_bars:
        return []
    sorted_bars = sorted(daily_bars, key=lambda b: b["date"])
    groups: dict[tuple[int, int], list[BarDict]] = {}
    for bar in sorted_bars:
        key = bar["date"].isocalendar()[:2]  # (iso_year, iso_week)
        groups.setdefault(key, []).append(bar)
    weekly: list[WeeklyBarDict] = []
    for key in sorted(groups):
        week_bars = groups[key]
        weekly.append({
            "date": week_bars[-1]["date"],
            "open": week_bars[0]["open"],
            "high": max(b["high"] for b in week_bars),
            "low":  min(b["low"]  for b in week_bars),
            "close": week_bars[-1]["close"],
            "volume": sum(b["volume"] for b in week_bars),
        })
    return weekly
```

### 5.3 数据加载
- 复用 `StockRepository.get_by_ticker(ticker)` 拿 Stock
- 查询：`select(DailyBar).where(DailyBar.stock_id == stock.id).order_by(DailyBar.date.asc())` — **不限 limit**（最多 250 行已被 prune）
- 转换为 BarDict 列表（仿 `chart_service._bars_from_db` 的 dict 构造）

### 5.4 MA 复用
```python
from app.services.cockpit.chart_service import _compute_ma_series

weekly_mas: dict[str, list[dict[str, Any]]] = {}
for period in WEEKLY.WEEKLY_MAS:
    weekly_mas[str(period)] = _compute_ma_series(weekly_bars_dict_list, period)
```
`_compute_ma_series` 期望 `bars` list 含 `close` 与 `date` 字段，weekly_bars 已满足。

---

## 6. 开发顺序（Generator 阶段，不得跳步）

1. 重读 `backend/app/services/cockpit/chart_service.py` 的 `_compute_ma_series`（lines 24-40）和 `_bars_from_db`（lines 215-235）确认接口
2. 重读 `backend/app/services/cockpit/cockpit_params.py` 当前最末位置，确认在哪里追加 `WEEKLY` 类
3. 在 cockpit_params.py 追加 `WEEKLY` 配置组
4. 新建 `weekly_chart_service.py`：先写 `aggregate_daily_to_weekly` 纯函数 + WeeklyBarDict TypedDict
5. 跑标准 1-5 测试（pure function）确认聚合正确
6. 在 `weekly_chart_service.py` 加 `WeeklyChartService` 类 + `get_weekly_chart`
7. 跑标准 6-9 测试确认 service 集成正确
8. 跑全量后端 pytest，确认标准 10 无回归
9. 追加 DECISIONS.md 决策记录
10. Generator 收尾 WIP commit（不要 `-A`，显式列 3 个文件）
11. Evaluator 自检 → 全清后切 needs_review，调用 consistency-check (mode=interactive)

---

## 7. 风险与对策

| 风险 | 对策 |
|------|------|
| daily_bars 在某些 stock 上是稀疏的（如最近新加 watchlist 的 ticker 只有 30 行） | `get_weekly_chart` 不抛错，weekly_bars 可能很短，weekly_mas[30] / weekly_mas[40] 会是 []（_compute_ma_series 在 period >= len 时返回 []）。caller（F216-b stage 分类器）需要容错。本 sub-sprint 标准 8 已覆盖 |
| ISO 周分组对跨年周（如 2026-W01 跨 2025-12-29 ~ 2026-01-04）的处理 | `isocalendar()[:2]` 返回 (iso_year, iso_week)，跨年周自然落到 iso_year=2026，分组正确，无须特殊处理。fixture 测试中覆盖一例跨年场景（可选 bonus 测试） |
| 与 F216-b 接口约定 | F216-b 的 stage 分类器将以 `get_weekly_chart(ticker, weeks=N)` 的返回作为输入。本 sub-sprint 输出 schema 锁定为 `{ticker, weekly_bars, weekly_mas}`，F216-b 合约必须按此 schema 写 |
| EMA 周线版本 | 计划文件未要求 weekly EMA，仅 weekly **SMA**。本 sub-sprint 不计算 weekly EMA。如未来 stage 分类需要 weekly EMA，另起 sub-sprint |

---

## 8. 不在本 sub-sprint 范围

- 任何 ticker 数据不足的 UI 提示（前端职责，F216-c）
- 历史回测（NVDA 2022 Stage 3）— 数据窗口限制，留待扩窗 feature
- 跨 stock 批量聚合（B5 cron 由 F216-e 调度，本 sub-sprint 仅暴露单 stock service 方法）
- DailyBar 表索引优化 — 现有 `(stock_id, date)` 联合索引已足

---

## 9. 协商点（需用户确认）

✅ **NP1 — daily_bars 窗口冲突**：已确认（用户 2026-05-14 选 B：F216-a 限 50 周，不扩窗）

### NP2 — week date 命名约定（推荐方案 A，✅ 已确认）

| 选项 | weekly bar.date 值 | 说明 |
|------|-------------------|------|
| **A（推荐）** | 本周最后实际交易日 | 周五交易则=周五；周五休市则=周四等。**lightweight-charts 周线显示约定** |
| B | 强制周五（计划原文） | 周五休市时仍用周五日期，bar 数据是周一–周四的聚合。可能与日历视图错位 |

→ Sprint Contract 写法已选 A。

### NP3 — 错误类型选择（推荐方案 A，✅ 已确认）

| 选项 | UNKNOWN ticker 时 | 说明 |
|------|------------------|------|
| **A（推荐）** | 抛 `APIError("NOT_FOUND", ...)` | 与 `chart_service` 一致，便于 F216-c router 直接 502/404 透传 |
| B | 返回空 dict | 更"宽容"但 F216-c 需自行判定空结果意义 |

→ Sprint Contract 写法已选 A。

### NP4 — daily_bars < 4 行的行为（推荐方案 A，✅ 已确认）

| 选项 | 行为 | 说明 |
|------|------|------|
| **A（推荐）** | 返回 `{ticker, weekly_bars: [], weekly_mas: {"10":[], "30":[], "40":[]}}` 不抛错 | F216-b stage 分类器看到空列表自动判 stage=UNKNOWN，符合"零数据零结论"语义 |
| B | 抛 `APIError("INSUFFICIENT_DATA", ...)` | 强制 caller 处理，但实际是常态（新加 watchlist 的 ticker），抛错太严 |

→ Sprint Contract 写法已选 A。

---

✅ **2026-05-14：用户回复"全部按推荐"，NP1/NP2/NP3/NP4 全部确认。合约定稿，进入 Generator 阶段（建议下个 session）。**
