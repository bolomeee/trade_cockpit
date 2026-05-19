---
status: confirmed
drafted_at: 2026-05-19
confirmed_at: 2026-05-19
sprint: F218-d3b
parent_feature: F218
---

# F218-d3b Sprint Contract — T2 MARGIN_EXPANSION detector 实装

> 生成：2026-05-19 | 状态：草案 → 待用户确认
> Feature：[F218](docs/需求/features.json) Cockpit Phase D — Repricing Trigger 完整框架（5 类）
> Sub-sprint：F218-d3b（Phase D 10 sub-sprint 第 6 个；T2 Margin Expansion **detector 实装**，数据层由 d3a 完成）
> 前置：F218-d1 done（service skeleton + 5 占位）/ F218-d2 done（T1 实装样板）/ F218-d3a done（`stock_key_metrics_quarterly` 表 + KeyMetricsRepository + pool_cache 集成）
> 下游：F218-d6a（cash-flow + balance-sheet 接入，补齐 fcf_margin / roic 列 → T2 FCF 臂自动激活；本 sprint 已留好接线）

> 引用文档：
> - [DATA-MODEL.md](docs/系统设计/DATA-MODEL.md) §RepricingTrigger 1080–1129（evidence_json schema / confidence 规则）+ §StockKeyMetricsQuarterly 1132–1183（detector 读取契约 §1159）
> - [DECISIONS.md](docs/系统设计/DECISIONS.md) D096（5 类 detector 框架 + confidence 简化策略）/ D097 修正（fcf_margin / roic 在 d3b 期间为 NULL）
> - [ARCHITECTURE.md](docs/系统设计/ARCHITECTURE.md) §Cockpit Repricing Trigger Service
> - [F218-d2-contract.md](docs/开发/sprint-contracts/F218-d2-contract.md) — T1 detector 实装样板（YoY 比较 / quarter label / fail-out 模式）
> - [F218-d3a-contract.md](docs/开发/sprint-contracts/F218-d3a-contract.md) — 数据层契约（fiscal_quarter 格式 "Q1 2026" / period_end_date DESC 排序）

---

## 0. 背景与定位

F218-d1 留下的 5 个占位中第 2 个 `_detect_margin_expansion` 在 d3a 完成数据层后可以实装：从 `stock_key_metrics_quarterly` 取最近 ≥ 6 季 → 判定 gross_margin / fcf_margin 双臂 YoY 扩张 → 命中则写 `repricing_triggers` 行。

**与 d3a 的边界**：d3a 把"周一 06:30 UTC pool rebuild 时把 8 季 income-statement 数据填到 key_metrics 表"这一管道修好；d3b 把"每日 22:40 UTC RepricingTriggerService 串行调度时第 2 个 detector"实装。d3a 是 producer，d3b 是 consumer。

**与 d6a 的边界（重要）**：d3a 落地后 `stock_key_metrics_quarterly.fcf_margin` 与 `.roic` **全表 NULL**（d6a 接入 cash-flow 后才补齐）。d3b 实装必须**优雅降级**：FCF 臂遇 NULL → 跳过该臂（不算命中、不抛错）；gross 臂照常评估。d6a 上线后 FCF 数据出现 → detector 代码**零修改**自动激活 FCF 臂。这是 d3a 决策 NP-d3a-6（NULL 列）的兑现路径。

**T2 触发语义**（DATA-MODEL.md §1159 + §1098 + 决策依据 D096）：
- 读最近 ≥ 6 季 key_metrics 行（按 period_end_date DESC），不足 6 行 → return None
- **Gross 臂**：(Q0.gross_margin − Q-4.gross_margin) ≥ **200bp** AND (Q-1.gross_margin − Q-5.gross_margin) ≥ **200bp** → 命中（"连续 2 季同比扩张" 严格解读 = 两个 YoY 都过阈值）
- **FCF 臂**：(Q0.fcf_margin − Q-4.fcf_margin) ≥ **300bp** AND (Q-1.fcf_margin − Q-5.fcf_margin) ≥ **300bp** → 命中
- Q0 / Q-1 / Q-4 / Q-5 任一对应字段 NULL（或负基准）→ **跳过该臂**，但不否决另一臂
- 任一臂命中即触发；两臂都命中以 gross 臂为 trigger_metric（gross 更稳定，FCF 易受 capex 季节性扰动 — D096 默认偏好）
- **confidence**：触发臂 Q0 vs Q-4 YoY 扩张 ≥ **400bp** → 0.8；否则 0.5（DATA-MODEL.md §1107）
- **evidence_json**：trigger_metric / expansion_bp / 双臂 trend（None 占位）/ quarters — 完整 schema 见 §1.2

---

## 1. 实现范围

**包含**：

### 1.1 `repricing_trigger_service.py` 实装 `_detect_margin_expansion`

**修改** `backend/app/services/cockpit/repricing_trigger_service.py`：

1. **顶部 import 段追加**：
   ```python
   from app.repositories.key_metrics_repository import KeyMetricsRepository
   ```

2. **`__init__` 追加 repository 注入**（紧跟既有 `self._earnings`）：
   ```python
   self._key_metrics = KeyMetricsRepository(db)
   ```

3. **新增 T2 常量段**（位置：`T1_DEFAULT_CONFIDENCE = 0.5` 之后空一行；与 T1 常量段并列对齐）：
   ```python
   # T2 MARGIN_EXPANSION detector 参数
   T2_LOOKBACK_QUARTERS = 6            # 需 Q0..Q-1 + 上年同期 Q-4..Q-5 = 至少 6 季
   T2_GROSS_THRESHOLD_BP = 200         # gross_margin YoY 扩张阈值（基点）
   T2_FCF_THRESHOLD_BP = 300           # fcf_margin YoY 扩张阈值（基点）
   T2_HIGH_CONFIDENCE_BP = 400         # Q0 YoY 扩张 ≥ 400bp → confidence=0.8（DATA-MODEL §1107）
   T2_HIGH_CONFIDENCE_SCORE = 0.8
   T2_DEFAULT_CONFIDENCE = 0.5
   ```

4. **替换占位** `_detect_margin_expansion`（删除 `return None`，按以下伪码实装；详细决策见 §3）：

   ```python
   def _detect_margin_expansion(
       self, ticker: str, scan_date: date,
   ) -> DetectorResult | None:
       """T2: 最近 2 季 gross_margin 或 fcf_margin YoY 扩张 ≥ 阈值 → 触发.

       读最近 ≥ 6 季 stock_key_metrics_quarterly（DESC by period_end_date）：
         - gross 臂：Q0 vs Q-4 AND Q-1 vs Q-5 都 ≥ 200bp 扩张
         - fcf 臂：  Q0 vs Q-4 AND Q-1 vs Q-5 都 ≥ 300bp 扩张
       任一臂数据缺失（rows 不足 / 字段 None）→ 跳过该臂；两臂全空 → return None.
       两臂都命中 → trigger_metric=gross_margin（DATA-MODEL §1098 默认偏好）.
       """
       rows = self._key_metrics.get_recent_for_ticker(
           ticker, limit=T2_LOOKBACK_QUARTERS,
       )
       if len(rows) < T2_LOOKBACK_QUARTERS:
           return None

       # rows[0] = Q0 (最新), rows[1] = Q-1, rows[4] = Q-4, rows[5] = Q-5
       q0, q1, q4, q5 = rows[0], rows[1], rows[4], rows[5]

       gross_hit, gross_q0_bp = _eval_margin_arm(
           q0.gross_margin, q1.gross_margin, q4.gross_margin, q5.gross_margin,
           threshold_bp=T2_GROSS_THRESHOLD_BP,
       )
       fcf_hit, fcf_q0_bp = _eval_margin_arm(
           q0.fcf_margin, q1.fcf_margin, q4.fcf_margin, q5.fcf_margin,
           threshold_bp=T2_FCF_THRESHOLD_BP,
       )

       if not (gross_hit or fcf_hit):
           return None

       # gross 优先（D096 默认偏好），fcf 备选
       if gross_hit:
           trigger_metric = "gross_margin"
           expansion_bp = gross_q0_bp  # 已是整数基点
       else:
           trigger_metric = "fcf_margin"
           expansion_bp = fcf_q0_bp

       confidence = (
           T2_HIGH_CONFIDENCE_SCORE
           if expansion_bp >= T2_HIGH_CONFIDENCE_BP
           else T2_DEFAULT_CONFIDENCE
       )

       # trend 3 个值（按时间顺序：Q-2, Q-1, Q0，与 DATA-MODEL §1098 例对齐）
       q2 = rows[2]
       gross_trend = [
           _round_or_none(q2.gross_margin), _round_or_none(q1.gross_margin), _round_or_none(q0.gross_margin),
       ]
       fcf_trend = [
           _round_or_none(q2.fcf_margin), _round_or_none(q1.fcf_margin), _round_or_none(q0.fcf_margin),
       ]
       quarters = [_quarter_label(r.period_end_date) for r in (q2, q1, q0)]

       return DetectorResult(
           confidence=confidence,
           evidence={
               "gross_margin_trend": gross_trend,
               "fcf_margin_trend": fcf_trend,
               "quarters": quarters,
               "trigger_metric": trigger_metric,
               "expansion_bp": expansion_bp,
           },
       )
   ```

5. **新增 2 个模块级辅助函数**（紧跟既有 `_quarter_label` 之后）：

   ```python
   def _eval_margin_arm(
       q0: float | None, q1: float | None,
       q4: float | None, q5: float | None,
       *, threshold_bp: int,
   ) -> tuple[bool, int]:
       """评估单臂（gross 或 fcf）：Q0 vs Q-4 AND Q-1 vs Q-5 双 YoY 都 ≥ threshold_bp → 命中.

       Returns (hit, q0_yoy_bp)：
         - 任一字段 None → (False, 0)
         - 双 YoY 都 ≥ threshold → (True, q0_yoy_bp)
         - 任一 YoY < threshold → (False, q0_yoy_bp)
       q0_yoy_bp 为 round((q0 - q4) * 10000)，命中场景外仍计算用于调试日志（caller 忽略）.
       """
       if q0 is None or q1 is None or q4 is None or q5 is None:
           return False, 0
       q0_bp = round((q0 - q4) * 10000)
       q1_bp = round((q1 - q5) * 10000)
       hit = (q0_bp >= threshold_bp) and (q1_bp >= threshold_bp)
       return hit, q0_bp


   def _round_or_none(v: float | None, ndigits: int = 4) -> float | None:
       """Round to ndigits, preserving None."""
       return None if v is None else round(v, ndigits)
   ```

### 1.2 evidence_json schema（最终落地版）

```json
{
  "gross_margin_trend": [0.42, 0.44, 0.46],   // [Q-2, Q-1, Q0] 绝对 margin 值；任一 None 时位置占 null
  "fcf_margin_trend":   [null, null, null],    // d3b 期间永远全 None（d6a 后自然出值）
  "quarters":           ["2025Q3", "2025Q4", "2026Q1"],  // 与 T1 同格式（YYYYQN，从 period_end_date 派生）
  "trigger_metric":     "gross_margin",        // 或 "fcf_margin"
  "expansion_bp":       400                     // 触发臂 Q0 vs Q-4 YoY 扩张（基点，整数）
}
```

与 DATA-MODEL.md §1098 示例 `{"gross_margin_trend": [0.42, 0.44, 0.46], "fcf_margin_trend": [0.18, 0.22, 0.25], "quarters": [...], "trigger_metric": "gross_margin", "expansion_bp": 400}` 完全对齐。

### 1.3 Tests

**新建** `backend/tests/test_repricing_trigger_margin_expansion.py`：

按 3 个 class 分组 10 个测试（对齐 d2 模式）：

| Class | # | 测试简述 |
|-------|---|---------|
| `TestEvalMarginArm`（辅助函数 ×3） | M1 | happy: 双 YoY 都过阈值 → hit=True |
| | M2 | 单 YoY 不过阈值 → hit=False |
| | M3 | 任一字段 None → hit=False, q0_bp=0 |
| `TestDetectMarginExpansion`（detector ×6） | M4 | gross 单臂命中（confidence=0.5，< 400bp）|
| | M5 | gross 高置信命中（≥ 400bp → confidence=0.8）|
| | M6 | fcf 单臂命中（gross 不动 / fcf 双季 YoY ≥ 300bp，trigger_metric=fcf_margin）|
| | M7 | 两臂同命中 → trigger_metric=gross_margin（D096 偏好）|
| | M8 | 仅 1 季 YoY 过阈值（Q-1 vs Q-5 未达）→ 不触发 |
| | M9 | 行数不足 6 / 任一字段 None / 双臂均空 → return None（3 子场景参数化）|
| `TestMarginExpansionEndToEnd`（service ×1） | M10 | `compute_and_store_all_triggers` mock 命中后 upsert，下次扫描 NULL → soft expire |

**Helper**：
- `_km(db, *, ticker, fiscal_quarter, period_end_date, gross_margin=None, fcf_margin=None, ...)` 直接 INSERT `StockKeyMetricsQuarterly` 行
- `_insert_6_seasons_for_t2(db, ticker, gross_series, fcf_series=None)` 批量插入 6 行（DESC 时间顺序）
- 复用 d2 的 `_stock` helper（创建 Stock 行）

**dB session fixture**：复用既有 conftest.py 的 `db_session`（sqlite in-memory）。

---

## 2. 预计修改文件

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/services/cockpit/repricing_trigger_service.py` | 修改 | +1 import (KeyMetricsRepository) / __init__ +1 行 / +T2 常量段 6 行 / 替换 `_detect_margin_expansion` 实装 / +2 模块级 helpers (`_eval_margin_arm`、`_round_or_none`) |
| 2 | `backend/tests/test_repricing_trigger_margin_expansion.py` | 新建 | 10 测试 / 3 class |

**实际 2 文件**，远低于 6 文件上限。

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `_eval_margin_arm(q0=0.46, q1=0.44, q4=0.42, q5=0.40, threshold_bp=200)` → `(True, 400)`；q0_bp = round((0.46-0.42)*10000) = 400 | 单元 | pytest |
| 2 | `_eval_margin_arm(q0=0.43, q1=0.44, q4=0.42, q5=0.40, threshold_bp=200)` → `(False, 100)`；Q0 YoY=100bp 未过 200bp 阈值 | 单元 | pytest |
| 3 | `_eval_margin_arm` 任一字段 None（参数化 4 case：q0/q1/q4/q5 各置 None）→ 全部返 `(False, 0)`；不抛 TypeError | 单元（parametrize） | pytest |
| 4 | T2 detector happy 低置信：构造 6 行 gross_margin [Q0..Q-5] = [0.46, 0.44, 0.43, 0.42, 0.42, 0.40]，fcf 全 None → 命中 gross 臂；Q0 YoY = 400bp, Q-1 YoY = 400bp 都 ≥ 200bp；但 Q0 YoY = 400bp 边界 = 阈值 → confidence=0.8 *(注：边界 ≥ 用 ≥，400 即 0.8)* | 单元 | pytest |
| 5 | T2 detector 严格"低置信"语义：gross [0.42, 0.41, 0.41, 0.40, 0.40, 0.38]（Q0 YoY=200bp, Q-1 YoY=300bp）→ 命中；Q0 YoY=200bp < 400bp → confidence=0.5 | 单元 | pytest |
| 6 | T2 detector FCF 臂命中：gross 全字段相同（0.40）/fcf [0.30, 0.28, 0.26, 0.25, 0.24, 0.23]（Q0 YoY=600bp, Q-1 YoY=500bp）→ 命中；trigger_metric=`fcf_margin`，expansion_bp=600 | 单元 | pytest |
| 7 | T2 detector 两臂同命中：gross / fcf 都 ≥ 阈值 → trigger_metric=`gross_margin`（D096 偏好），expansion_bp 取 gross Q0 YoY | 单元 | pytest |
| 8 | T2 detector 单季 YoY 过阈值：gross [0.46, 0.41, ..., 0.42, 0.40, ...]（Q0 YoY=400bp ≥ 200bp, 但 Q-1 YoY=100bp < 200bp）→ 不触发（return None）| 单元 | pytest |
| 9 | T2 detector return None 三场景（参数化）：(a) get_recent_for_ticker 返 < 6 行；(b) 双臂 Q0..Q-5 任一字段 None（如 gross 全 None + fcf 全 None）→ return None；(c) 双臂都 NOT hit（如 gross [0.40, 0.40, ...] 全平 + fcf 全 None）| 单元（parametrize） | pytest |
| 10 | `RepricingTriggerService.compute_and_store_all_triggers` 端到端：(1) seed 1 个 active Stock + 6 行 key_metrics 满足 gross 命中；(2) 调用 → repricing_triggers 表插 1 行 trigger_type=MARGIN_EXPANSION + active=True + evidence_json 含 trigger_metric/expansion_bp/quarters；(3) 改 Q0 gross_margin 平掉 → 再调用 → 同行 active=False（soft expire） | 集成 | pytest |
| 11 | evidence_json 结构验证：assert keys = `{"gross_margin_trend", "fcf_margin_trend", "quarters", "trigger_metric", "expansion_bp"}`；trend 长度 = 3；quarters 长度 = 3；trigger_metric ∈ {"gross_margin", "fcf_margin"}；fcf_margin_trend 在 fcf 数据全 None 时为 `[null, null, null]` | 单元（嵌在 M4） | pytest |

预期测试数：**10 个**（M11 嵌在 M4 内一并断言）。单文件 `test_repricing_trigger_margin_expansion.py`。

---

## 4. Evaluator 自检清单

- [ ] 10 个新测试全部通过（`cd backend && uv run pytest tests/test_repricing_trigger_margin_expansion.py -v`）
- [ ] d1/d2/d3a 既有测试仍全绿（`uv run pytest tests/test_repricing_trigger_skeleton.py tests/test_repricing_trigger_earnings_accel.py tests/test_f218_d3a_key_metrics.py -v`）
- [ ] 全量后端回归通过（`uv run pytest`）— 允许 d2 记录的 9 个 pre-existing failures，不得新增
- [ ] `_detect_margin_expansion` 签名不变 `(self, ticker: str, scan_date: date) -> DetectorResult | None`；返回类型与 T1 一致
- [ ] evidence_json 5 个键齐全且类型正确（list / list / list / str / int），与 DATA-MODEL.md §1098 example schema 1:1 对齐
- [ ] trigger_metric 决策正确：两臂同命中 → `gross_margin`（D096 偏好）；仅 fcf 命中 → `fcf_margin`
- [ ] expansion_bp 为整数基点（round），不是浮点小数
- [ ] T2 detector 失败 fail-out（return None）而非 raise；任一原始字段 None 不导致 TypeError
- [ ] FCF 臂在 fcf_margin 全 NULL 数据下永远不命中（d3a 落地后 d6a 之前的当前状态）；fcf_margin_trend 输出 `[null, null, null]`
- [ ] `KeyMetricsRepository` 注入 `__init__` 不破坏既有 service 测试（d1 skeleton 5 占位测试 + d2 T1 测试中 service 实例化路径）
- [ ] T2 常量段独立于 T1 常量段，命名前缀 `T2_*` 清晰
- [ ] `_eval_margin_arm` 与 `_round_or_none` 为模块级（不挂 class），便于 d4/d5/d6b 复用相似 helper 模式
- [ ] `_quarter_label` 直接复用既有函数（d2 已定义），不重复实现

### 代码质量检查
- [ ] `_detect_margin_expansion` 函数长度 ≤ 50 行（拆分 helpers 后 main 函数预估 ~30 行）
- [ ] 无硬编码魔法值（200/300/400/0.5/0.8 全部抽 T2_* 常量；fiscal_quarter 行索引 0/1/4/5 在注释中说明含义）
- [ ] `_eval_margin_arm` 纯函数无副作用
- [ ] 无注释掉的代码 / 死 import / 未使用变量

### 回归测试
- [ ] 后端全量 `uv run pytest` 通过（允许 9 pre-existing failures，不得新增）
- [ ] cockpit/setup/regime/pool_cache/repricing_trigger（d1+d2+d3a）未受 import / 字段命名改动影响
- [ ] 调用 `compute_and_store_all_triggers` 时 T2 detector 串行位置（第 2 个）与 d1 skeleton 一致；其他 4 个 detector 仍为占位（return None）

---

## 5. 关键设计决策（执行前确认）

| # | 议题 | 推荐方案 | 备选方案 |
|---|------|---------|---------|
| **NP-d3b-1** | "最近 2 季同比扩张" 解读 | **A：双 YoY 都 ≥ 阈值（推荐）**：Q0 vs Q-4 AND Q-1 vs Q-5 同时过 200bp；与 T1"连续 2 季"严格解读一致。配合 fail-out（任一 YoY < 阈值 → 整臂 not hit）。 | (a) **B：单 YoY ≥ 阈值** — 只判 Q0 vs Q-4，更宽松但偏离 "连续 2 季" 字面 / (b) **C：累计/QoQ 扩张** — Q0 vs Q-2 ≥ 阈值，更激进但放弃 "同比" 语义。 |
| **NP-d3b-2** | FCF 臂在 d3b 期间数据全 NULL 的策略 | **fail-soft 跳过 FCF 臂（推荐）**：`_eval_margin_arm` 任一 None → return (False, 0)；fcf_margin_trend 输出 `[null, null, null]`；d6a 落地后零修改自动激活。无需 feature flag、无需 d6a 反向修改 detector。 | (a) d3b 期间完全删 FCF 臂，d6a 再加回 — 引入冗余 detector 改动，违反单一职责 / (b) FCF 臂 d3b 期间抛 NotImplementedError — 阻断 service 主循环 try/except 流程，污染日志。 |
| **NP-d3b-3** | 两臂同命中时的 trigger_metric | **`gross_margin` 优先（推荐）**：DATA-MODEL §1098 example 用 `gross_margin`；D096 指 gross 更稳定 / FCF 受 capex 季节性扰动；保持 evidence 一致性便于 UI（widget chip 单色单标签）。 | (a) `fcf_margin` 优先 — 现金流更"硬"，但 capex 噪声大 / (b) 双标签 `"gross_margin+fcf_margin"` — 突破 DATA-MODEL 枚举值约束，影响下游消费。 |
| **NP-d3b-4** | confidence 阈值取哪个臂的 Q0 YoY | **触发臂 Q0 YoY（推荐）**：gross 触发 → 取 gross Q0 YoY 与 400bp 比；fcf 触发 → 取 fcf Q0 YoY 与 400bp 比（注意：fcf 阈值 400bp ≠ trigger 阈值 300bp；命中后仍按 400bp 判高置信，DATA-MODEL §1107 唯一阈值）。两臂同命中按 gross 臂值。 | (a) 始终取 gross Q0 YoY — fcf 触发场景 gross 未必扩张，无意义 / (b) 取双臂最大 — DATA-MODEL §1107 未提此规则，引入歧义。 |
| **NP-d3b-5** | evidence_json `quarters` 字段格式 | **`YYYYQN` 日历季度（推荐）**：与 T1 `_quarter_label(earnings_date)` 同函数同格式（"2026Q1"），UI 跨 trigger 类型一致；用 `period_end_date` 派生（非 fiscal_quarter 字段，因 fiscal_quarter 是 FMP 财年口径 "Q1 2026" 与日历季度可能错位）。 | (a) 直接用 fiscal_quarter "Q1 2026" — FMP 财年与日历错位时 UI 困惑 / (b) ISO 日期 "2026-03-31" — 与 T1 不一致，UI 双套渲染逻辑。 |
| **NP-d3b-6** | trend 字段 3 个值的时间锚点 | **[Q-2, Q-1, Q0] 连续 3 季（推荐）**：与 DATA-MODEL §1098 example 单调上升 [0.42, 0.44, 0.46] 直观对齐；用户看 widget 图就能直接读趋势，无需脑补 YoY 配对；YoY 阈值判定在 detector 内部独立完成，evidence 只服务 UI 展示。 | (a) [Q-4, Q-1, Q0] 跨年 3 点 — 跳 Q-3/Q-2，UI 折线断裂 / (b) [Q-5, Q-4, Q0] — 同样跳点。 |
| **NP-d3b-7** | `_eval_margin_arm` / `_round_or_none` 放哪 | **`repricing_trigger_service.py` 模块级（推荐）**：与既有 `_quarter_label` 同居所；T2 专属逻辑，d4/d5/d6b 若复用可后续抽 `repricing_trigger_helpers.py`（YAGNI，本 sprint 不预先抽）。 | (a) 抽 `repricing_trigger_helpers.py` 新文件 — +1 文件无即时收益 / (b) 放 `pool_helpers.py` — pool_helpers 是 pool_cache 域，跨域污染。 |
| **NP-d3b-8** | T2 触发后 d3a `delete_for_tickers_not_in` 是否要清理对应 trigger 行 | **不在 d3b 范围（推荐）**：d3a NP-d3a-5 已决议"实装方法但不挂"；trigger 行 ttl 由 D096 §保留策略 `REPRICING_TRIGGER_RETENTION_DAYS=365` 管理，与 key_metrics 表清理解耦。本 sprint 不引入新清理调用。 | (a) 在 RepricingTriggerService 入口扫一遍已退 pool ticker 的 trigger 行 → soft expire — 越出 sub-sprint 边界，应在 acceptance 或独立 cleanup task 处理。 |

### 推荐理由速览

- **NP-d3b-1 双 YoY 严格判定**：和 T1 一致的"连续 N 季"严格解读，避免单季异常波动误触发；同时与 SRS § 十一 D3 描述"连续 2 季同比扩张"字面对齐。
- **NP-d3b-2 fail-soft**：核心好处是 d6a 上线无需改 detector 代码 — 加 cash-flow / balance-sheet 数据 → 表里 fcf_margin 出值 → detector 自然命中。这是 d3a NP-d3a-6（fcf_margin / roic 列 d3a 期间 NULL）整套设计的最终兑现。
- **NP-d3b-3 gross 优先**：与 DATA-MODEL example 一致；UI chip 颜色与 trigger_metric 1:1 映射，单标签更易渲染；FCF 触发场景仍可在 widget 详情里展开看 fcf_margin_trend。
- **NP-d3b-4 触发臂 Q0 YoY**：DATA-MODEL §1107 confidence 规则用语模糊（"expansion ≥ 400bp"），最合理读法是"触发臂的扩张幅度"。所有 testcase 围绕此规则展开。
- **NP-d3b-5 YYYYQN**：与 T1 evidence_json `quarters` 字段格式严格一致，避免 widget 渲染分支判 trigger_type。
- **NP-d3b-6 连续 3 季 trend**：DATA-MODEL example 默认排列就是连续 3 季；YoY 比较的两端点（Q-4 / Q-5）放 evidence 反而干扰 UI 阅读。expansion_bp 单独字段已完整表达 YoY 信息。
- **NP-d3b-7 同模块**：模块级 helpers 数量目前不构成"helpers 文件"提取阈值；d4/d5/d6b 真用到时再抽。
- **NP-d3b-8 不动 cleanup**：避免越出 d3b 范围；365 天 retention 已经够长，TTL 清理是独立 cleanup task 责任。

---

## 6. 不在范围（本 sprint 排除）

- ❌ 接 FMP cash-flow-statement / balance-sheet-statement endpoint（d6a）
- ❌ 补齐 `stock_key_metrics_quarterly.fcf_margin` 与 `.roic` 实际数据（d6a）
- ❌ T3 NEW_PRODUCT detector 实装（d4）
- ❌ T4 SECTOR_CYCLE detector 实装（d5）
- ❌ T5 BALANCE_INFLECTION detector 实装（d6b）
- ❌ refresh_job.py cron 注册（d7a — 22:40 UTC RepricingTriggerService 调度；d1 skeleton 已能跑 main entry，cron 接线由 d7a 完成）
- ❌ router + 2 endpoint `/api/cockpit/repricing-triggers*`（d7a）
- ❌ 前端 widget RepricingTriggerWidget + DecisionPanelWidget chip 区（d7b）
- ❌ DECISIONS.md 追加（D096/D097 已覆盖本 sprint 所需全部决策；NP-d3b-1~8 是实施级决策，由本 contract 承载，不升 DXXX）
- ❌ ARCHITECTURE.md / DATA-MODEL.md / API-CONTRACT.md 任何修改（4 文档 status 在 2026-05-18 D097 修正同步 confirmed，本 sprint 严格落地无新增 drift）
- ❌ T2 历史回测验证 SRS 案例（NVDA/TSLA/META，acceptance / d7b 收官时统一做）
- ❌ T2 触发后对 cockpit 其他模块（setup / decision / position）的串联消费（d7b 前端展示阶段或独立 feature）
- ❌ `compute_and_store_all_triggers` 性能优化（当前串行调度 5 detector × ~50 ticker，预估 d7a 上线时再评估）

---

## 7. 用户待确认

1. **NP-d3b-1 ~ NP-d3b-8** 八项决策：全部按推荐？还是有需要调整的？特别注意：
   - **NP-d3b-1**（"连续 2 季同比"解读 → 双 YoY 都过阈值）— 决定误报率
   - **NP-d3b-2**（FCF 臂 fail-soft）— 决定与 d6a 的耦合方式
2. **evidence_json schema**（§1.2 最终落地版）是否同意？尤其 `fcf_margin_trend: [null, null, null]` 在 d3b 期间的占位形态。
3. **Contract 整体是否同意进入 Generator 模式开发**？

确认后我会：
1. 更新 features.json：`F218-d3b` sub_sprints state `design_needed` → `contract_agreed`；`_pipeline_status.active_sprint` 切到 `F218-d3b`；`_pipeline_status.active_sprint_phase` → `contract_agreed`
2. 追加 F218 iteration_history 一条 `contract_agreed` 记录（subtask=F218-d3b，date=2026-05-19）
3. 更新 claude-progress.txt
4. 生成 SESSION-HANDOFF.md（含 d3b 4 步开发顺序：T2 常量段 → `_eval_margin_arm` + `_round_or_none` helpers → `_detect_margin_expansion` 实装 + KeyMetricsRepository 注入 → 测试 10 个）
5. **强制停止本 session**（feature-dev skill 铁律），输出新 session 恢复指令
