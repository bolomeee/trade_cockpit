---
status: confirmed
drafted_at: 2026-05-18
confirmed_at: 2026-05-18
sprint: F218-d2
parent_feature: F218
---

# F218-d2 Sprint Contract — T1 Earnings Acceleration detector 实装

> 生成：2026-05-18 | 状态：草案 → 待用户确认
> Feature：[F218](docs/需求/features.json) Cockpit Phase D — Repricing Trigger 完整框架（5 类）
> Sub-sprint：F218-d2（Phase D 10 sub-sprint 第 2 个，detector 实装第 1 个 / T1）
> 前置：F218-d1 done（service skeleton + RepricingTriggerRepository + repricing_triggers 表 + 5 `_detect_*` 占位 + soft expire 主循环）
> 下游：F218-d4 (T3) / F218-d5 (T4) / F218-d3a (T2 FMP 接入) / F218-d6a (T5 FMP 接入)

> 引用文档：
> - [DATA-MODEL.md](docs/系统设计/DATA-MODEL.md) §RepricingTrigger — EARNINGS_ACCEL evidence_json schema + confidence 业务规则（yoy ≥ 30% → 0.8 / 其余 0.5）
> - [ARCHITECTURE.md](docs/系统设计/ARCHITECTURE.md) §Cockpit Repricing Trigger Service — T1 = `_detect_earnings_acceleration(ticker)`，复用 EarningsEventRepository（不新接 FMP）
> - [F218-d1-contract.md](docs/开发/sprint-contracts/F218-d1-contract.md) — 上游合约：DetectorResult 签名 / TRIGGER_TYPES 常量 / 主入口调度链
> - [F204-a-contract.md](docs/开发/sprint-contracts/F204-a-contract.md) — earnings_events 表 / EarningsEvent model / EarningsEventRepository 既有接口

---

## 0. 背景与定位

F218-d1 留下的 5 个占位 detector 之一：`_detect_earnings_acceleration` 当前返回 None。本 sub-sprint 把它换成真实业务逻辑，是首个走通"detector hit → upsert repricing_triggers"的完整数据回路。

**为什么 T1 是首个 detector**：
- 不需要新接 FMP（T2/T5 才需要，留给 d3a/d6a）
- 不需要新表（T2/T5 需要 stock_key_metrics_quarterly / stock_fundamentals_quarterly）
- 数据源完全复用 F204-a 已有的 `earnings_events` 表 + `EarningsEventRepository`
- 业务逻辑相对纯粹（YoY 比较 + 单调判断），适合验证 d1 skeleton 调度链端到端
- ARCHITECTURE.md §Cockpit Repricing Trigger Service 把 T1 列为串行调度第 1 个

**T1 业务定义**（DATA-MODEL §RepricingTrigger §evidence_json schema）：
- 输入：单 ticker 的近 6 个 earnings_events（含 actual EPS + actual revenue）
- 触发条件：最近 3 个季度 EPS YoY 增长率严格单调递增（Q-3 YoY < Q-2 YoY < Q-1 YoY）
- confidence：默认 0.5；若最近一季 EPS YoY ≥ 30% 升至 0.8（DATA-MODEL.md 业务规则原文）
- evidence_json：`{"eps_yoy_growth": [...], "revenue_yoy_growth": [...], "quarters": ["2025Q3", "2025Q4", "2026Q1"]}`

---

## 1. 实现范围

**包含**：

### 1.1 EarningsEventRepository 新方法

**修改** `backend/app/repositories/earnings_event_repository.py`，在既有 3 方法（upsert_batch / get_next_earnings / delete_before）之后追加 1 个 read 方法：

```python
def get_recent_completed_for_ticker(
    self, ticker: str, limit: int = 8,
) -> list[EarningsEvent]:
    """Return the most recent `limit` earnings_events for `ticker` where eps_actual IS NOT NULL,
    ordered by earnings_date DESC. Used by T1 EARNINGS_ACCEL detector for YoY computation.

    eps_actual NULL 行（未发布 / FMP 尚未回填）被过滤；revenue_actual 不参与过滤
    （允许部分 ticker 仅有 EPS 触发 T1，revenue 缺失时 revenue_yoy_growth 列以 None 填充）。
    """
    return (
        self._db.query(EarningsEvent)
        .filter(
            EarningsEvent.ticker == ticker,
            EarningsEvent.eps_actual.isnot(None),
        )
        .order_by(EarningsEvent.earnings_date.desc())
        .limit(limit)
        .all()
    )
```

### 1.2 RepricingTriggerService — `_detect_earnings_acceleration` 实装

**修改** `backend/app/services/cockpit/repricing_trigger_service.py`：

- 顶部 import 追加：`from app.repositories.earnings_event_repository import EarningsEventRepository`
- `__init__` 追加：`self._earnings = EarningsEventRepository(db)`
- 新增模块级常量：
  ```python
  # T1 EARNINGS_ACCEL detector 参数
  T1_LOOKBACK_QUARTERS = 6            # 需 Q-3..Q-1 + 上年同期 = 6 季
  T1_REQUIRED_QUARTERS = 3            # 检查 YoY 加速的最近季度数
  T1_HIGH_CONFIDENCE_YOY = 0.30       # 最近一季 EPS YoY ≥ 30% → confidence=0.8
  T1_HIGH_CONFIDENCE_SCORE = 0.8
  T1_DEFAULT_CONFIDENCE = 0.5
  ```
- 替换占位方法体：

```python
def _detect_earnings_acceleration(
    self, ticker: str, scan_date: date,
) -> DetectorResult | None:
    """T1: 最近 3 季度 EPS YoY 增长率严格单调递增 → 触发。

    需要 6 季 actual EPS（最近 3 季 + 上年同期 3 季）；任一季缺失 → return None。
    上年同期 EPS ≤ 0 → 该季 YoY 视为不可计算 → return None（避免负基准除法噪声）。
    revenue_yoy_growth 同步计算用于 evidence；revenue_actual 缺失时该位为 None
    （不影响 EPS 触发判定）。
    """
    rows = self._earnings.get_recent_completed_for_ticker(
        ticker, limit=T1_LOOKBACK_QUARTERS,
    )
    if len(rows) < T1_LOOKBACK_QUARTERS:
        return None

    # rows 按 earnings_date DESC：rows[0] = 最新，rows[5] = 最早
    # 计算最近 3 季 YoY：(Q-1, Q-2, Q-3) 与 (Q-1y, Q-2y, Q-3y) 配对
    recent = rows[:T1_REQUIRED_QUARTERS]            # 索引 0,1,2 = Q-1, Q-2, Q-3
    prior  = rows[T1_REQUIRED_QUARTERS:]            # 索引 3,4,5 = Q-1y, Q-2y, Q-3y

    eps_yoy: list[float] = []
    revenue_yoy: list[float | None] = []
    for cur, prv in zip(recent, prior):
        if prv.eps_actual is None or prv.eps_actual <= 0:
            return None  # 负基准 / 缺数据
        eps_yoy.append(cur.eps_actual / prv.eps_actual - 1.0)

        if (cur.revenue_actual is None or prv.revenue_actual is None
                or prv.revenue_actual <= 0):
            revenue_yoy.append(None)
        else:
            revenue_yoy.append(cur.revenue_actual / prv.revenue_actual - 1.0)

    # eps_yoy 当前为 [Q-1, Q-2, Q-3]（最新在前）；反转为时间顺序 [Q-3, Q-2, Q-1]
    eps_yoy.reverse()
    revenue_yoy.reverse()

    # 严格单调递增：eps_yoy[0] < eps_yoy[1] < eps_yoy[2]
    if not (eps_yoy[0] < eps_yoy[1] < eps_yoy[2]):
        return None

    # confidence: 最近一季 EPS YoY ≥ 30% → 0.8；否则 0.5
    confidence = (
        T1_HIGH_CONFIDENCE_SCORE
        if eps_yoy[-1] >= T1_HIGH_CONFIDENCE_YOY
        else T1_DEFAULT_CONFIDENCE
    )

    # quarter label 按 earnings_date 派生日历季度 "YYYYQN"；时间顺序 [Q-3, Q-2, Q-1]
    quarters = [_quarter_label(r.earnings_date) for r in reversed(recent)]

    return DetectorResult(
        confidence=confidence,
        evidence={
            "eps_yoy_growth": [round(v, 4) for v in eps_yoy],
            "revenue_yoy_growth": [
                round(v, 4) if v is not None else None for v in revenue_yoy
            ],
            "quarters": quarters,
        },
    )
```

- 新增模块级 helper（与 service class 同文件，文件底部）：

```python
def _quarter_label(d: date) -> str:
    """Map a date to calendar-quarter label, e.g. 2026-02-15 → "2026Q1"."""
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"
```

### 1.3 Tests

**新文件** `backend/tests/test_repricing_trigger_earnings_accel.py`：

按 §3 测试用例表展开 10 个测试，集中覆盖 T1 detector 业务逻辑 + repo 新方法 + 端到端集成（通过主入口 `compute_and_store_all_triggers` 验证写入 repricing_triggers）。按 3 个 class 分组：
- `TestEarningsEventRepoRecentCompleted` —— repo 新方法 2 测试
- `TestDetectEarningsAcceleration` —— detector 单元 7 测试
- `TestEarningsAccelEndToEnd` —— 主入口端到端 1 测试（hit + upsert + soft expire 协同）

---

## 2. 预计修改文件

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/repositories/earnings_event_repository.py` | 修改 | +1 方法 `get_recent_completed_for_ticker(ticker, limit=8)` |
| 2 | `backend/app/services/cockpit/repricing_trigger_service.py` | 修改 | `_detect_earnings_acceleration` 占位 → 实装；+EarningsEventRepository import / self._earnings / 5 T1 常量 / `_quarter_label` 模块函数 |
| 3 | `backend/tests/test_repricing_trigger_earnings_accel.py` | 新增 | 10 测试 / 3 class |

**合计 3 文件**，远低于 6 文件上限。✅

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `get_recent_completed_for_ticker(ticker, limit=8)` 仅返回 eps_actual IS NOT NULL 行，按 earnings_date DESC，limit 截断 | 单元 | pytest（SQLite in-memory fixture）|
| 2 | `get_recent_completed_for_ticker` 在 ticker 无任何 actual 行时返回空 list（不抛错） | 单元 | pytest |
| 3 | `_detect_earnings_acceleration` 6 季完整 + EPS YoY 严格单调递增 + 最近一季 yoy < 30% → 返回 DetectorResult(confidence=0.5, evidence={eps_yoy_growth:[3 floats], revenue_yoy_growth:[3 floats], quarters:[3 strs]}) | 单元 | pytest |
| 4 | `_detect_earnings_acceleration` 最近一季 EPS YoY ≥ 30% → confidence=0.8 | 单元 | pytest |
| 5 | `_detect_earnings_acceleration` 6 季完整但 YoY 序列非严格单调（持平 / 下行 / 中段回落）→ 返回 None | 单元 | pytest（参数化覆盖 3 case：[0.2, 0.2, 0.3] 持平 / [0.3, 0.25, 0.2] 下行 / [0.2, 0.3, 0.25] 中段回落） |
| 6 | `_detect_earnings_acceleration` ticker 历史不足 6 季（如 5 季 / 0 季）→ 返回 None | 单元 | pytest |
| 7 | `_detect_earnings_acceleration` 上年同期 EPS ≤ 0（含 0 与负值）→ 返回 None（不做负基准除法） | 单元 | pytest |
| 8 | `_detect_earnings_acceleration` EPS 全合规 + 任一季 revenue_actual=None 或上年同期 revenue ≤ 0 → 仍触发，evidence_json.revenue_yoy_growth 对应位置为 null（EPS 单独判定，revenue 缺失不阻断） | 单元 | pytest |
| 9 | `_quarter_label(date(2026,2,15))` == "2026Q1"；`_quarter_label(date(2025,12,31))` == "2025Q4"；`_quarter_label(date(2025,4,1))` == "2025Q2" | 单元 | pytest（参数化）|
| 10 | 主入口端到端：`compute_and_store_all_triggers` 注入 1 active ticker + 6 季 actual data 命中 T1 → repricing_triggers 表新增 1 行（trigger_type=EARNINGS_ACCEL, active=true, evidence_json JSON 反序列化字段齐全）；同 ticker 第二天数据未命中（YoY 跌破）→ 该行 active=false（soft expire 自动触发，d1 主循环验证） | 集成 | pytest |

预期测试数：**10 个**（单文件 `test_repricing_trigger_earnings_accel.py`，按 3 class 分组）。

---

## 4. Evaluator 自检清单

开发完成后 Evaluator 模式逐条检查：

- [ ] 10 个新测试全部通过（`cd backend && uv run pytest tests/test_repricing_trigger_earnings_accel.py -v`）
- [ ] d1 既有 14 测试仍全绿（`uv run pytest tests/test_repricing_trigger_skeleton.py -v`），尤其端到端 service 测试不因 T1 实装回归
- [ ] 全量后端回归通过（`uv run pytest`），无新增失败
- [ ] `EARNINGS_ACCEL` evidence_json schema 与 [DATA-MODEL.md §RepricingTrigger evidence_json schema](docs/系统设计/DATA-MODEL.md) 一致（3 字段：eps_yoy_growth / revenue_yoy_growth / quarters；列长度均为 3）
- [ ] confidence 策略与 DATA-MODEL.md 业务规则一致（yoy ≥ 30% → 0.8 / 其余 0.5）
- [ ] T1 常量集中在 `repricing_trigger_service.py` 顶部命名常量段（不散落 magic number）
- [ ] `_detect_earnings_acceleration` 签名仍为 `(self, ticker: str, scan_date: date) -> DetectorResult | None`（与 d1 skeleton 一致，d3b/d4/d5/d6b 不需要因此改 signature）
- [ ] EarningsEventRepository 改动仅"加方法"，既有 3 方法（upsert_batch / get_next_earnings / delete_before）签名不变，F204 既有 test_earnings_f204a/b 不回归
- [ ] import 边界仍符合 ARCHITECTURE.md §Cockpit Repricing Trigger Service（本 sprint 新增 import 仅 `EarningsEventRepository`，未引入 journal/watchlist/signal_engine）
- [ ] `_quarter_label` 作为模块级 helper，不挂 service class（保持纯函数便于单测，且 d3b/d6b 复用时不耦合 service 实例）

### 代码质量检查
- [ ] 无死代码 / 注释掉的代码块
- [ ] 无硬编码魔法值（6/3/0.30/0.8/0.5 全部抽 T1_* 常量）
- [ ] `_detect_earnings_acceleration` 函数长度 ≤ 50 行（预计 ~35 行符合）
- [ ] eps_actual / revenue_actual 负基准与 None 防御性早返回，不在分支内累积 nan / inf

### 回归测试
- [ ] 后端全量 `uv run pytest` 通过
- [ ] 既有 cockpit 服务（regime/setup/weekly_stage/pool_cache/repricing_trigger skeleton）未受 import 改动影响

---

## 5. 关键设计决策（执行前确认）

| # | 议题 | 推荐方案 | 备选方案 |
|---|------|---------|---------|
| **NP-d2-1** | 加速判定 = 严格单调递增（`yoy[0] < yoy[1] < yoy[2]`） | **严格单调（推荐）** | (a) 允许持平（`yoy[0] <= yoy[1] <= yoy[2]` 且至少 1 步 `<`） / (b) 每步最小增量 ≥ 5pp |
| **NP-d2-2** | 触发依据 = EPS 单独判定（revenue 缺失不阻断，仅作为 evidence 副产物） | **EPS 单独（推荐）** | (a) EPS AND revenue 都必须加速 / (b) EPS OR revenue 任一加速 |
| **NP-d2-3** | 数据完整性 = 6 季 actual EPS 全齐才判定；任一缺失返回 None | **6 季全齐（推荐）** | (a) 允许最早 1 季缺失，3 季 YoY 中最早一季用线性插值 / (b) 不足 6 季时用历史均值做基准 |
| **NP-d2-4** | confidence 阈值 = 仅看最近一季（yoy[-1] ≥ 0.30 → 0.8） | **最近一季（推荐，与 DATA-MODEL.md 原文一致）** | (a) 3 季全部 ≥ 30% 才升 / (b) 3 季均值 ≥ 30% 才升 |
| **NP-d2-5** | quarter label 来源 = `earnings_date` 日历季度（2026-02-15 → 2026Q1） | **日历季度（推荐）** | (a) 给 earnings_events 加 `fiscal_quarter` 列（需 alembic 023，扩文件数） / (b) 用 ISO 日期字符串 `"2026-02-15"` 直接代替季度标签 |
| **NP-d2-6** | repo 新方法名 = `get_recent_completed_for_ticker(ticker, limit=8)` | **`get_recent_completed_for_ticker`（推荐）** | (a) `get_recent_for_ticker`（与 SESSION-HANDOFF 用语一致但语义弱）/ (b) 把查询逻辑写在 service 内不出 repo |
| **NP-d2-7** | 负基准（上年同期 EPS ≤ 0）处理 = 整体返 None（不计算该 ticker） | **整体返 None（推荐）** | (a) 该季 YoY 列入 evidence 为 null + 其余 2 季单调判定 / (b) 用绝对值倒推符号 |

### 推荐理由速览

- **NP-d2-1 严格单调**：SRS § 十一 把 EARNINGS_ACCEL 定义为"加速"而非"持续高位"，持平/回落均不是加速。备选 (b) 每步 ≥ 5pp 引入新魔法值且 SRS 未要求，先不加；后续 D4b 校准时可再加严。
- **NP-d2-2 EPS 单独**：SRS 与 DATA-MODEL.md 业务规则原文均以 EPS YoY 为判定主轴；revenue 在 evidence 内是辅助信号。要求 AND 会显著降低命中率（许多 EPS 加速来自 margin 而非 revenue），违反 SRS 命中频率预期。
- **NP-d2-3 6 季全齐**：T1 是高 conviction 信号，宁可漏不可错；插值 / 均值会引入估算噪声破坏"加速"语义的可解释性（用户在 widget 看到 evidence 时期望真实数字）。
- **NP-d2-4 最近一季阈值**：DATA-MODEL.md §RepricingTrigger 业务规则原文 "EARNINGS_ACCEL 若 yoy ≥ 30% confidence=0.8" 未指明哪一季，但语义自然落到"最新一季"（首先决定信号强度的是当前状态）。3 季全要求会过严。
- **NP-d2-5 日历季度**：earnings_events 本身无 fiscal_quarter 列；加列要 alembic 023 + model 改 + 数据回填，超出 d2 范围。日历季度对 widget 展示足够清晰；如未来 widget 需要 fiscal 严格对齐，可在 d7b 时通过另一接口拉 FMP fiscal period。
- **NP-d2-6 `get_recent_completed_for_ticker`**：语义明确（"completed" = eps_actual 已填），与既有 `get_next_earnings` 对称（"next" = 未来 vs "recent_completed" = 过去已实算）。把查询放 repo 而非 service 是分层一致性（cockpit/setup_service / weekly_stage_service 同样模式）。
- **NP-d2-7 整体返 None**：负基准 YoY 在数学上不可解释（如 -0.1 → 0.2 = "增长 -300%" 是噪声），且 ticker 上年同期亏损本就提示业务不稳定；标记 N/A 反而让 evidence_json 列长度参差不齐，破坏 widget 渲染契约。

---

## 6. 不在范围（本 sprint 排除）

- ❌ T2/T3/T4/T5 detector 真实实装（留给 d3b/d4/d5/d6b）
- ❌ FMP key-metrics / ratios / balance-sheet / cash-flow（d3a/d6a）
- ❌ 新表（stock_key_metrics_quarterly / stock_fundamentals_quarterly）（d3a/d6a）
- ❌ pool_cache_service.py 改动（d3a/d6a）
- ❌ refresh_job.py cron 注册（d7a）
- ❌ router + 2 endpoint（d7a）
- ❌ 前端任何文件 / design-spec / tokens / data-mapping / component-plan（d7b）
- ❌ DECISIONS.md 追加（本 sprint 无新决策；NP-d2-1~7 是实施级别决策由本 contract 承载，不需要 D099+）
- ❌ earnings_events 表结构变更（不加 fiscal_quarter 列；NP-d2-5 决策不引入 alembic 023）
- ❌ T1 历史回测脚本（验证 NVDA / TSLA 案例命中数 ≥ 2 类）—— 这是 acceptance 阶段任务，留给 d7b 之后整体回测时统一做

---

## 7. 用户待确认

1. **NP-d2-1 ~ NP-d2-7** 七项决策：全部按推荐？还是有需要调整的？
2. **Contract 整体是否同意进入 Generator 模式开发**？

确认后我会：
1. 更新 features.json：F218-d2 phase 改 `contract_agreed`；`_pipeline_status.active_sprint` 已为 `F218-d2` 保持不变
2. 追加 F218 iteration_history 一条 contract_agreed 记录（subtask=F218-d2，date=2026-05-18）
3. 更新 claude-progress.txt
4. 生成 SESSION-HANDOFF.md（含 d2 3 步开发顺序：repo +方法 → service detector 实装 → tests，及恢复指令）
5. **强制停止本 session**（feature-dev skill 铁律），输出新 session 恢复指令
