---
status: confirmed
drafted_at: 2026-05-20
confirmed_at: 2026-05-20
sprint: F218-d6b
parent_feature: F218
---

# F218-d6b Sprint Contract — T5 BALANCE_INFLECTION detector 实装

> 生成：2026-05-20 | 状态：已确认 → 进入 Generator
> Feature：[F218](docs/需求/features.json) Cockpit Phase D — Repricing Trigger 完整框架（5 类）
> Sub-sprint：F218-d6b（Phase D 10 sub-sprint 第 8 个；T5 Balance Inflection **detector 实装**，数据层由 d6a 完成）
> 前置：F218-d1 done（service skeleton + 5 占位）/ F218-d3b done（T2 detector 样板）/ F218-d6a done（`stock_fundamentals_quarterly` 表 + `FundamentalsRepository` + pool_cache 集成）
> 下游：F218-d7a（cron 注册 + router + 2 endpoint）/ F218-d7b（前端 widget + DecisionPanel chip）

> 引用文档：
> - [DATA-MODEL.md](docs/系统设计/DATA-MODEL.md) §RepricingTrigger 1080–1129（evidence_json schema / confidence 规则）+ §StockFundamentalsQuarterly 1186–1235（detector 读取契约）
> - [DECISIONS.md](docs/系统设计/DECISIONS.md) D096（5 类 detector 框架 + confidence 简化策略）/ D097（FMP 3 endpoint 接入修正 2026-05-18）
> - [ARCHITECTURE.md](docs/系统设计/ARCHITECTURE.md) §Cockpit Repricing Trigger Service
> - [F218-d3b-contract.md](docs/开发/sprint-contracts/F218-d3b-contract.md) — T2 detector 实装样板（双臂 / fail-soft / trigger_metric 优先 / trend 时间锚点）
> - [F218-d6a-contract.md](docs/开发/sprint-contracts/F218-d6a-contract.md) — 数据层契约（fiscal_quarter 格式 / period_end_date DESC / `FundamentalsRepository.get_recent_for_ticker`）

---

## 0. 背景与定位

F218-d1 留下的 5 个占位中第 5 个 `_detect_balance_inflection` 在 d6a 完成数据层后可以实装：从 `stock_fundamentals_quarterly` 取最近 ≥ 3 季 → 判定 net_debt QoQ 下降双臂 或 FCF 负→正切换臂 → 命中则写 `repricing_triggers` 行。

**与 d6a 的边界**：d6a 把"周一 06:30 UTC pool rebuild 时把 8 季 balance-sheet + cash-flow 数据填到 `stock_fundamentals_quarterly` 表"这一管道修好；d6b 把"每日 22:40 UTC RepricingTriggerService 串行调度时第 5 个 detector"实装。d6a 是 producer，d6b 是 consumer。

**T5 触发语义**（DATA-MODEL.md §1208-1214 + §1100 + D096）：
- 读最近 ≥ 3 季 fundamentals 行（按 period_end_date DESC），不足 3 行 → return None
- **Net Debt 臂**：(Q-1.net_debt − Q0.net_debt) / Q-1.net_debt ≥ 5% AND (Q-2.net_debt − Q-1.net_debt) / Q-2.net_debt ≥ 5% → 命中
  - 分母 ≤ 0（已净现金）→ 跳过该臂（不可定义"下降比例"且业务无意义）
  - 任一 Qn.net_debt 为 None → 跳过该臂
- **FCF 臂**：Q-2.fcf ≤ 0 AND Q-1.fcf > 0 AND Q0.fcf > 0 → 命中（"负→连续 2 季正"严格切换语义）
  - 任一 Qn.fcf 为 None → 跳过该臂
- 任一臂命中即触发；两臂都命中以 `net_debt` 为 trigger_metric（DATA-MODEL §1100 example 默认偏好，负债下降是主路径，FCF 转正是补充信号）
- **confidence**：恒 `0.5`（DATA-MODEL §1107: T5 无高置信路径，与 T3/T4 一致）
- **evidence_json**：trigger_metric / 双臂 trend / quarters — 完整 schema 见 §1.2

---

## 1. 实现范围

**包含**：

### 1.1 `repricing_trigger_service.py` 实装 `_detect_balance_inflection`

**修改** `backend/app/services/cockpit/repricing_trigger_service.py`：

1. **顶部 import 段追加**：
   ```python
   from app.repositories.fundamentals_repository import FundamentalsRepository
   ```

2. **`__init__` 追加 repository 注入**（紧跟既有 `self._key_metrics`）：
   ```python
   self._fundamentals = FundamentalsRepository(db)
   ```

3. **新增 T5 常量段**（位置：T4 常量段之后空一行，与 T1–T4 常量段并列对齐）：
   ```python
   # T5 BALANCE_INFLECTION detector 参数
   T5_LOOKBACK_QUARTERS = 3            # 需 Q0/Q-1/Q-2 = 至少 3 季
   T5_NET_DEBT_QOQ_THRESHOLD = 0.05    # 净负债环比下降率阈值（5%）
   T5_DEFAULT_CONFIDENCE = 0.5         # DATA-MODEL §1107: T5 无高置信路径
   ```

4. **替换占位** `_detect_balance_inflection`（删除 `return None`，按以下伪码实装；详细决策见 §3）：

   ```python
   def _detect_balance_inflection(
       self, ticker: str, scan_date: date,
   ) -> DetectorResult | None:
       """T5: 净负债连续 2 季 QoQ 下降 ≥ 5%，或 FCF 由负切为连续 2 季正 → 触发.

       读最近 ≥ 3 季 stock_fundamentals_quarterly（DESC by period_end_date）：
         - net_debt 臂：(Q-1−Q0)/Q-1 ≥ 5% AND (Q-2−Q-1)/Q-2 ≥ 5%；分母 ≤ 0 → 跳过该臂
         - fcf 臂：    Q-2 ≤ 0 AND Q-1 > 0 AND Q0 > 0（严格切换点）
       任一臂数据缺失（rows 不足 / 字段 None / 分母无效）→ 跳过该臂；两臂全空 → return None.
       两臂都命中 → trigger_metric=net_debt（DATA-MODEL §1100 默认偏好）.
       """
       rows = self._fundamentals.get_recent_for_ticker(
           ticker, limit=T5_LOOKBACK_QUARTERS,
       )
       if len(rows) < T5_LOOKBACK_QUARTERS:
           return None

       # rows[0]=Q0 (最新), rows[1]=Q-1, rows[2]=Q-2
       q0, q1, q2 = rows[0], rows[1], rows[2]

       net_debt_hit, _ = _eval_net_debt_arm(
           q0.net_debt, q1.net_debt, q2.net_debt,
           threshold=T5_NET_DEBT_QOQ_THRESHOLD,
       )
       fcf_hit = _eval_fcf_arm(q0.fcf, q1.fcf, q2.fcf)

       if not (net_debt_hit or fcf_hit):
           return None

       # net_debt 优先（DATA-MODEL §1100 默认偏好），fcf 备选
       trigger_metric = "net_debt" if net_debt_hit else "fcf"

       # trend 3 个值：[Q-2, Q-1, Q0] 时间顺序，与 DATA-MODEL §1100 example 对齐
       net_debt_trend = [q2.net_debt, q1.net_debt, q0.net_debt]
       fcf_trend = [q2.fcf, q1.fcf, q0.fcf]
       quarters = [_quarter_label(r.period_end_date) for r in (q2, q1, q0)]

       return DetectorResult(
           confidence=T5_DEFAULT_CONFIDENCE,
           evidence={
               "net_debt_trend": net_debt_trend,
               "fcf_trend": fcf_trend,
               "quarters": quarters,
               "trigger_metric": trigger_metric,
           },
       )
   ```

5. **新增 2 个模块级辅助函数**（紧跟既有 `_eval_margin_arm` / `_round_or_none` 之后）：

   ```python
   def _eval_net_debt_arm(
       q0: int | None, q1: int | None, q2: int | None,
       *, threshold: float,
   ) -> tuple[bool, float]:
       """评估 net_debt 臂：(Q-1−Q0)/Q-1 AND (Q-2−Q-1)/Q-2 都 ≥ threshold → 命中.

       Returns (hit, recent_qoq_pct)：
         - 任一字段 None → (False, 0.0)
         - 分母 (Q-1 或 Q-2) ≤ 0（已净现金）→ (False, 0.0)
         - 双 QoQ 下降比例都 ≥ threshold → (True, recent_qoq_pct)
       recent_qoq_pct = round((q1 - q0) / q1, 4)，hit=False 时仍计算用于调试日志.
       """
       if q0 is None or q1 is None or q2 is None:
           return False, 0.0
       if q1 <= 0 or q2 <= 0:
           return False, 0.0
       qoq_recent = (q1 - q0) / q1
       qoq_prior = (q2 - q1) / q2
       hit = (qoq_recent >= threshold) and (qoq_prior >= threshold)
       return hit, round(qoq_recent, 4)


   def _eval_fcf_arm(
       q0: int | None, q1: int | None, q2: int | None,
   ) -> bool:
       """评估 fcf 臂：Q-2 ≤ 0 AND Q-1 > 0 AND Q0 > 0（严格"负→连续 2 季正"切换）.

       任一字段 None → False.
       """
       if q0 is None or q1 is None or q2 is None:
           return False
       return q2 <= 0 and q1 > 0 and q0 > 0
   ```

### 1.2 evidence_json schema（最终落地版）

```json
{
  "net_debt_trend": [120000000, 105000000, 95000000],   // [Q-2, Q-1, Q0] 美元整数；任一 None 时位置占 null
  "fcf_trend":      [-15000000, 8000000, 22000000],      // [Q-2, Q-1, Q0] 美元整数；任一 None 时位置占 null
  "quarters":       ["2025Q3", "2025Q4", "2026Q1"],     // YYYYQN 日历季度（与 T1/T2 同格式，从 period_end_date 派生）
  "trigger_metric": "net_debt"                           // 或 "fcf"
}
```

与 DATA-MODEL.md §1100 示例 `{"net_debt_trend": [120000000, 105000000, 95000000], "fcf_trend": [-15000000, 8000000, 22000000], "quarters": [...], "trigger_metric": "net_debt"}` 完全对齐。

### 1.3 Tests

**新建** `backend/tests/test_repricing_trigger_balance_inflection.py`：

按 4 个 class 分组 10 个测试（对齐 d3b 模式）：

| Class | # | 测试简述 |
|-------|---|---------|
| `TestEvalNetDebtArm`（辅助函数 ×3） | B1 | happy: 双 QoQ 都 ≥ 5% 下降 → hit=True |
| | B2 | 单 QoQ 不够 5% → hit=False |
| | B3 | 任一字段 None / 分母 ≤ 0（参数化 5 case：q0/q1/q2=None；q1=0；q2=−5）→ hit=False, recent_qoq_pct=0.0 |
| `TestEvalFcfArm`（辅助函数 ×2） | B4 | happy: Q-2 ≤ 0 / Q-1 > 0 / Q0 > 0 → True |
| | B5 | 不满足切换（参数化 4 case：Q-2>0 / Q-1≤0 / Q0≤0 / 任一 None）→ False |
| `TestDetectBalanceInflection`（detector ×4） | B6 | net_debt 单臂命中（fcf 全 None 或不符合切换）→ trigger_metric=`net_debt` |
| | B7 | fcf 单臂命中（net_debt 全平 / fcf 满足切换）→ trigger_metric=`fcf` |
| | B8 | 两臂同命中 → trigger_metric=`net_debt`（DATA-MODEL §1100 偏好）|
| | B9 | 行数不足 3 / 双臂均不命中（参数化 3 case）→ return None |
| `TestBalanceInflectionEndToEnd`（service ×1） | B10 | `compute_and_store_all_triggers` 端到端：(1) seed 1 个 active Stock + 3 行 fundamentals 满足 net_debt 命中；(2) 调用 → repricing_triggers 表插 1 行 trigger_type=BALANCE_INFLECTION + active=True + evidence_json 完整；(3) 改 Q0.net_debt 平掉 → 再调用 → 同行 active=False（soft expire）|

**Helper**：
- `_fundamentals(db, *, ticker, fiscal_quarter, period_end_date, total_debt=None, cash=None, net_debt=None, fcf=None)` 直接 INSERT `StockFundamentalsQuarterly` 行
- `_insert_3_seasons_for_t5(db, ticker, net_debt_series=None, fcf_series=None)` 批量插入 3 行（DESC 时间顺序：Q-2 → Q-1 → Q0）
- 复用 d2/d3b 的 `_stock` helper（创建 Stock 行）

**dB session fixture**：复用既有 conftest.py 的 `db_session`（sqlite in-memory）。

---

## 2. 预计修改文件

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/services/cockpit/repricing_trigger_service.py` | 修改 | +1 import (FundamentalsRepository) / `__init__` +1 行 / +T5 常量段 3 行 / 替换 `_detect_balance_inflection` 实装（~35 行）/ +2 模块级 helpers (`_eval_net_debt_arm`、`_eval_fcf_arm`，共 ~25 行）|
| 2 | `backend/tests/test_repricing_trigger_balance_inflection.py` | 新建 | 10 测试 / 4 class |

**实际 2 文件**，远低于 6 文件上限。

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `_eval_net_debt_arm(q0=95M, q1=105M, q2=120M, threshold=0.05)` → `(True, ~0.0952)`；双 QoQ 下降比例 (105-95)/105 ≈ 9.5%, (120-105)/120 ≈ 12.5% 都 ≥ 5% | 单元 | pytest |
| 2 | `_eval_net_debt_arm(q0=102M, q1=105M, q2=120M, threshold=0.05)` → `(False, ~0.0286)`；recent QoQ ≈ 2.86% < 5% | 单元 | pytest |
| 3 | `_eval_net_debt_arm` 参数化 5 case（q0=None / q1=None / q2=None / q1=0 / q2=−5）→ 全部返 `(False, 0.0)`；不抛 ZeroDivisionError / TypeError | 单元（parametrize） | pytest |
| 4 | `_eval_fcf_arm(q0=22M, q1=8M, q2=-15M)` → True（严格切换：Q-2 负，Q-1 / Q0 正）| 单元 | pytest |
| 5 | `_eval_fcf_arm` 参数化 4 case：(Q-2=5M, Q-1=8M, Q0=22M)→False（Q-2 已正，无切换）/ (Q-2=-15M, Q-1=-3M, Q0=22M)→False（Q-1 未转正）/ (Q-2=-15M, Q-1=8M, Q0=0)→False（Q0=0 非严格正）/ (任一 None)→False | 单元（parametrize） | pytest |
| 6 | T5 detector net_debt 单臂命中：fundamentals 3 行 net_debt=[120M, 105M, 95M]（Q-2→Q0，时间升序），fcf 全 None → 命中；trigger_metric=`net_debt`；evidence net_debt_trend=[120M,105M,95M], fcf_trend=[null,null,null]；confidence=0.5 | 单元 | pytest |
| 7 | T5 detector fcf 单臂命中：fundamentals 3 行 net_debt 全 100M（QoQ 0%），fcf=[-15M, 8M, 22M] → 命中；trigger_metric=`fcf`；evidence net_debt_trend=[100M,100M,100M], fcf_trend=[-15M,8M,22M]；confidence=0.5 | 单元 | pytest |
| 8 | T5 detector 两臂同命中：net_debt=[120M,105M,95M] 且 fcf=[-15M,8M,22M] → 命中；trigger_metric=`net_debt`（DATA-MODEL §1100 偏好）| 单元 | pytest |
| 9 | T5 detector return None 三场景（参数化）：(a) `get_recent_for_ticker` 返 < 3 行；(b) net_debt 双 QoQ 都 < 5% + fcf 不符切换；(c) net_debt 字段全 None + fcf 字段全 None → return None | 单元（parametrize） | pytest |
| 10 | `RepricingTriggerService.compute_and_store_all_triggers` 端到端：(1) seed 1 个 active Stock + 3 行 fundamentals 满足 net_debt 命中；(2) 调用 → repricing_triggers 表插 1 行 trigger_type=`BALANCE_INFLECTION` + active=True + confidence=0.5 + evidence_json 含 trigger_metric/quarters/双 trend；(3) 改 Q0.net_debt 升回 105M（QoQ 0%）→ 再调用 → 同行 active=False（soft expire）| 集成 | pytest |
| 11 | evidence_json 结构验证：assert keys = `{"net_debt_trend", "fcf_trend", "quarters", "trigger_metric"}`；trend 长度 = 3；quarters 长度 = 3；trigger_metric ∈ {"net_debt", "fcf"}；fcf_trend 在 fcf 全 None 时为 `[null, null, null]` | 单元（嵌在 B6） | pytest |

预期测试数：**10 个**（B11 嵌在 B6 内一并断言；参数化会展开更多 case）。单文件 `test_repricing_trigger_balance_inflection.py`。

---

## 4. Evaluator 自检清单

- [ ] 10 个新测试全部通过（`cd backend && uv run pytest tests/test_repricing_trigger_balance_inflection.py -v`）
- [ ] d1/d2/d3a/d3b/d4/d5/d6a 既有测试仍全绿（`uv run pytest tests/test_repricing_trigger_skeleton.py tests/test_repricing_trigger_earnings_accel.py tests/test_repricing_trigger_margin_expansion.py tests/test_repricing_trigger_new_product.py tests/test_repricing_trigger_sector_cycle.py tests/test_f218_d3a_key_metrics.py tests/test_f218_d6a_fundamentals.py -v`）
- [ ] 全量后端回归通过（`uv run pytest`）— 允许 d6a 记录的 9 个 pre-existing failures，不得新增
- [ ] `_detect_balance_inflection` 签名不变 `(self, ticker: str, scan_date: date) -> DetectorResult | None`；返回类型与 T1-T4 一致
- [ ] evidence_json 4 个键齐全且类型正确（list / list / list / str），与 DATA-MODEL.md §1100 example schema 1:1 对齐
- [ ] trigger_metric 决策正确：两臂同命中 → `net_debt`（DATA-MODEL §1100 偏好）；仅 fcf 命中 → `fcf`
- [ ] T5 detector 失败 fail-out（return None）而非 raise；任一原始字段 None 不导致 TypeError / ZeroDivisionError
- [ ] net_debt 臂在分母 ≤ 0（公司已净现金）时永远不命中；不抛除零异常
- [ ] fcf 臂在 Q0=0 或 Q-1=0 时不命中（严格大于）
- [ ] `FundamentalsRepository` 注入 `__init__` 不破坏既有 service 测试（d1 skeleton 5 占位测试 + d2/d3b/d4/d5 各 detector 测试中 service 实例化路径）
- [ ] T5 常量段独立于 T1-T4 常量段，命名前缀 `T5_*` 清晰
- [ ] `_eval_net_debt_arm` 与 `_eval_fcf_arm` 为模块级（不挂 class），与既有 `_eval_margin_arm` / `_round_or_none` 同居所
- [ ] `_quarter_label` 直接复用既有函数（d2 已定义），不重复实现

### 代码质量检查
- [ ] `_detect_balance_inflection` 函数长度 ≤ 50 行（拆分 helpers 后 main 函数预估 ~30 行）
- [ ] 无硬编码魔法值（0.05 抽 T5_NET_DEBT_QOQ_THRESHOLD；0.5 抽 T5_DEFAULT_CONFIDENCE；rows 索引 0/1/2 在注释中说明含义）
- [ ] `_eval_net_debt_arm` / `_eval_fcf_arm` 纯函数无副作用
- [ ] 无注释掉的代码 / 死 import / 未使用变量

### 回归测试
- [ ] 后端全量 `uv run pytest` 通过（允许 9 pre-existing failures，不得新增）
- [ ] cockpit/setup/regime/pool_cache/repricing_trigger（d1+d2+d3a+d3b+d4+d5+d6a）未受 import / 字段命名改动影响
- [ ] 调用 `compute_and_store_all_triggers` 时 T5 detector 串行位置（第 5 个）与 d1 skeleton 一致；其他 4 个 detector（T1-T4）继续按既有逻辑运行

---

## 5. 关键设计决策（已与用户确认）

| # | 议题 | 已定方案 |
|---|------|---------|
| **NP-d6b-1** | "净负债连续 2 季环比下降 ≥ 5%" 解读 | **双 QoQ 都 ≥ 5% 下降**：(Q-1−Q0)/Q-1 AND (Q-2−Q-1)/Q-2 同时过 5%；与 T1/T2"连续 N 季"严格解读一致。单 QoQ 易被一次性还债噪声触发。 |
| **NP-d6b-2** | net_debt 下降率的分母与零/负值处理 | **分母 ≤ 0（已净现金）→ 跳过 net_debt 臂**。已净现金的公司谈"负债下降"无业务意义；`abs()` 处理会让净现金加深的公司误触发；同时杜绝 ZeroDivisionError。 |
| **NP-d6b-3** | "FCF 从负值切为连续 2 季正" 解读 | **严格切换点语义**：Q-2 ≤ 0 AND Q-1 > 0 AND Q0 > 0；字面"切换"必须有负→正的跳变，Q-2 已正则无切换语义。Q0/Q-1 严格大于 0（=0 不算正）。 |
| **NP-d6b-4** | 数据缺失策略 | **fail-soft 跳过该臂**：任一字段 None → return (False, ...)；两臂全空 → return None。与 d3b NP-2 一致；FMP 偶发字段缺失不应抛错。 |
| **NP-d6b-5** | 两臂同命中时的 trigger_metric | **`net_debt` 优先**（DATA-MODEL §1100 example 即用 `net_debt`；负债下降是主路径，FCF 转正是补充信号）。与 UI chip 单标签渲染需求一致。 |
| **NP-d6b-6** | evidence trend 时间锚点 | **[Q-2, Q-1, Q0] 连续 3 季**（与 DATA-MODEL §1100 example 单调序列 [120M, 105M, 95M] / [-15M, 8M, 22M] 一致）。判定逻辑与展示解耦。 |
| **NP-d6b-7** | confidence 取值 | **恒 0.5**（DATA-MODEL §1107: T5 无高置信路径，与 T3/T4 一致）。无需分支判断。 |
| **NP-d6b-8** | helpers 放哪 / 数量 | **2 个模块级 helpers**（`_eval_net_debt_arm`、`_eval_fcf_arm`）放 service.py 与既有 `_quarter_label` / `_eval_margin_arm` 同居所。YAGNI 不预先抽 helpers.py；与 d3b NP-7 一致。 |

---

## 6. 不在范围（本 sprint 排除）

- ❌ FMP balance-sheet / cash-flow endpoint 接入（d6a 已完成）
- ❌ `FundamentalsRepository` 扩展（d6a `get_recent_for_ticker` 已够用，本 sprint 不动 repo）
- ❌ T2 detector 已有 fcf_margin 数据后的回归验证（d3b 已覆盖，本 sprint 不重测）
- ❌ refresh_job.py cron 注册（d7a — 22:40 UTC RepricingTriggerService 调度；d1 skeleton 已能跑 main entry，cron 接线由 d7a 完成）
- ❌ router + 2 endpoint `/api/cockpit/repricing-triggers*`（d7a）
- ❌ 前端 widget RepricingTriggerWidget + DecisionPanelWidget chip 区（d7b）
- ❌ DECISIONS.md 追加（D096/D097 已覆盖本 sprint 所需全部决策；NP-d6b-1~8 是实施级决策，由本 contract 承载，不升 DXXX）
- ❌ ARCHITECTURE.md / DATA-MODEL.md / API-CONTRACT.md 任何修改（4 文档 status 已 confirmed，本 sprint 严格落地无新增 drift）
- ❌ T5 历史回测验证（NVDA/META 等 balance inflection 案例，acceptance / d7b 收官时统一做）
- ❌ T5 触发后对 cockpit 其他模块（setup / decision / position）的串联消费（d7b 前端展示阶段或独立 feature）
- ❌ `compute_and_store_all_triggers` 性能优化（5 detector × ~50 ticker 串行调度，预估 d7a 上线时再评估）

---

## 7. 开发顺序（Generator 模式执行）

1. **顶部 import + `__init__` 注入 + T5 常量段**（最小变更 3 处，编译跑通即可）
2. **2 个模块级 helpers**（`_eval_net_debt_arm`、`_eval_fcf_arm`）
3. **替换 `_detect_balance_inflection` 占位**（按 §1.1 step 4 伪码实装）
4. **测试新建**（10 个，按 §1.3 4 class 分组）
5. **本地 pytest 全绿 → 全量回归 → Evaluator 自检 → consistency-check (C1/C4/C5) → phase=needs_review**

每步通过最小验证后 WIP commit（`wip(F218-d6b): [step 名]`），按文件名显式 add，禁用 `git add -A`。

---

## 8. 用户已确认（2026-05-20）

- ✅ NP-d6b-1 ~ NP-d6b-8 全部按推荐
- ✅ evidence_json schema（§1.2）与 DATA-MODEL §1100 example 1:1 对齐
- ✅ 10 测试规划合适
- ✅ 进入 Generator 模式开发
