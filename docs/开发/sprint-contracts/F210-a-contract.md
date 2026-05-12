# Sprint Contract：F210-a — AI Candidate Ranker + Trade Plan 后端 schemas + Guardrail（D068）

> 状态：草案，待用户确认 | 起草：2026-04-25
> 父 Feature：F210 AI Candidate Ranker + Trade Plan Generator（v2.0 Cockpit P2 critical-tier 双 task）
> 拆分：**F210-a（本 sprint，后端基座）** / F210-b（前端 SetupMonitor "AI 排序" 集成）/ F210-c（前端 DecisionPanel "Generate AI Plan" 集成）
> 依赖：F208-c ✅（AiGateway 主流程 + REGISTRY 注册位 + guardrail.run）+ F202 ✅（SetupSnapshot 数据源）+ F203 ✅（decision_service `_compute_hash` + deterministicHash）+ F209-a ✅（schema 文件模板，含 SCHEMA_VERSION / SYSTEM_PROMPT / BANNED_PHRASES / guardrail 函数模式）
> 引用文档：
>   - API-CONTRACT.md §POST /api/ai/{task_type}（line 1655-1734：统一 envelope / 错误码 / 7 task 枚举 / Guardrail 段 line 1707-1709）
>   - API-CONTRACT.md §GET /api/cockpit/decision/{ticker}（line 1155-1216：deterministicHash 锚点定义 + entry/stop/size 三字段权威值）
>   - DATA-MODEL.md §SetupSnapshot（line 420-466：candidate_ranker 输入字段权威）+ §UserSettings（line 499-521：仓位公式）+ §AiMemo（line 593-619）
>   - DECISIONS.md D064（tier 路由）/ D066（仓位公式）/ D068（trade_plan 确定性护栏）/ D069（memo 缓存）/ D074（schema 字段命名 camelCase）
>   - design-spec.md §Widget 5 SetupMonitor line 945-973（AI 排序后续承载）+ §Widget 6 DecisionPanel line 977-1024（Trade Plan 后续承载）
>   - data-mapping.md §Cockpit-6.c（line 616-628：AI Trade Plan 字段映射；output.entry/stop/size 必须等于 decision.* 的 guardrail 锚点）
>   - features.json#F210（acceptance_criteria 6 条）
>   - backend/app/ai/schemas/__init__.py（line 31-36：F210 REGISTRY 注册占位）
>   - backend/app/ai/schemas/setup_explainer.py（F209-a schema 模板，复用 SCHEMA_VERSION / Field 约束 / guardrail 函数风格）
>   - backend/app/services/cockpit/decision_service.py line 41-51（`_compute_hash` 实现 + 字段顺序，guardrail 校验需复用相同语义）

---

## 0. 背景与定位

F208-c 已落地 AI Gateway 主流程：`schemas/__init__.py` 的 `REGISTRY` 是显式占位（line 31-36 注释 `"trade_plan": SchemaPair(...)`），`guardrail.run` 已通过 registry 模式接入 `gateway.py` step 9（写 memo 之前必跑），`routing.py` 的 `_TASK_TIER` 已经把 `candidate_ranker` 和 `trade_plan` 都映射到 `critical` tier — 后端基础设施齐全，**本 sprint 只补 schema + guardrail，不动 gateway / routing / endpoint 层**。

F210 整体覆盖 2 个 task + 2 个独立前端落点：
- `candidate_ranker`：SetupMonitor 顶部 "AI 排序" 按钮 → top 3 排序面板（DecisionPanel 不涉）
- `trade_plan`：DecisionPanel "Generate AI Plan" 按钮 → memo/management 卡片（SetupMonitor 不涉）

按 D010（脚手架豁免）+ F208/F209 既定先例，F210 拆 a/b/c 三段：

| 子 sprint | 范围 | 估计文件 |
|----------|------|----------|
| **F210-a（本契约）** | 后端：两个 task 的 Pydantic input/output schema + trade_plan guardrail（D068 entry/stop/size 锚点校验）+ REGISTRY 注册 + 单元测试 | 4 |
| F210-b | 前端：SetupMonitor `AiCandidateRankerSection` 组件 + widget 集成 + 测试（top 3 渲染、20 截断、错误态） | 3-4 |
| F210-c | 前端：DecisionPanel `AiTradePlanSection` 组件 + widget 集成 + guardrail violation banner + 测试 | 3-4 |

本 sprint 不写任何前端代码、不改 gateway / endpoint / routing，让 F210-b/c 直接基于稳定的 schema 契约启动。

**关键约束**：
1. `trade_plan` guardrail 是 **F210 的硬核技术风险点**（D068）。LLM 输出的 `entry/stop/size` 三字段必须和输入完全一致（小数位对齐到 2 位），否则抛 `AiGuardrailViolation`，**不写 ai_memos**（gateway step 9 在 step 10 之前；先抛错就不入表）。
2. `candidate_ranker` **没有 guardrail**（无 deterministic 锚点可对齐；ranker 输出本身就是 LLM 主观排序）。仅做 schema 形状校验（top 3 长度、rank 1-3 唯一、action 枚举）。
3. 字段命名走 **D074 camelCase**（与 F209-a 保持一致），即输入/输出字段在 Pydantic 内用 camelCase 直名，**不**走 alias。
4. 截断规则（features.json AC4）在 schema 层用 `Field(max_length=20)` 强校验：超 20 → Pydantic ValidationError → gateway 上抛 → endpoint 转 422。**不在 schema 内做 silent 截断**（截断+meta 标记的语义放到 endpoint 层，但本 sprint 暂不做，F210-b 起草时再决定是 422 还是 silent truncate）。
   > **Q1（开放）**：features.json AC4 写"超过截断并在响应 meta 标记"。schema 强校验=422 与"截断+meta"语义冲突。**默认采 422**（Pydantic 严格），把"前端入参时主动 slice 到 20"的责任放到 F210-b。如用户希望服务端 silent truncate，需要在 endpoint 层加预处理（不在 F210-a 范围）。

---

## 1. 实现范围

### 1.1 包含

#### 1.1.1 `backend/app/ai/schemas/candidate_ranker.py`（新建，~110 行）

**职责**：定义 `candidate_ranker` task 的 input/output schema + SYSTEM_PROMPT + BANNED_PHRASES。**无 guardrail**（不注册 hook）。

```python
"""Candidate Ranker task schema (F210-a, critical tier).

Input: array of up to 20 setup candidates + market regime context
Output: top 3 ranked candidates with reason + action
"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

SCHEMA_VERSION = "v1"

SYSTEM_PROMPT = """You are a portfolio prioritization assistant for a slow-trading system.
Given up to 20 watchlist setup candidates and current market regime, rank the TOP 3 by
trade-now priority. Use trend/RS/quality/distance/earnings_risk/ready_signal jointly;
favor ready_signal=true and earnings_risk=SAFE; avoid Risk-Off regime over-extension.

Rules:
- Output exactly 3 items, ranks 1/2/3 unique
- reason: ≤ 200 chars, one sentence per candidate
- action: enter | watch | wait (matches SetupSnapshot.suggested_action subset)
Prohibited phrases (never use): buy now, sell now, 保证收益, 承诺收益, 忽略止损, ignore stop
Output must be valid JSON matching the schema exactly. No extra keys.
"""

BANNED_PHRASES: tuple[str, ...] = (
    "buy now", "sell now", "保证收益", "承诺收益", "忽略止损", "ignore stop",
)


class CandidateInput(BaseModel):
    """单个 candidate（来自 SetupSnapshot 投影 + DecisionData 派生）"""
    ticker: str = Field(min_length=1, max_length=10, pattern=r"^[A-Z][A-Z0-9.\-]*$")
    setupType: Literal["BREAKOUT", "PULLBACK", "RECLAIM", "EARNINGS_DRIFT", "EXTENDED", "BROKEN", "NONE"]
    setupQuality: Literal["A", "B", "C"] | None = None
    trendScore: int = Field(ge=0, le=5)               # SetupSnapshot.trend_score 0-5
    rsPercentile: float = Field(ge=0, le=100)
    distanceToEntryPct: float                          # 可负
    rewardRisk: float = Field(ge=0)
    earningsRisk: Literal["SAFE", "CAUTION", "DANGER"]
    readySignal: bool
    model_config = {"extra": "forbid"}


class CandidateRankerInput(BaseModel):
    regime: Literal["CONSTRUCTIVE", "NEUTRAL", "CAUTION", "RISK_OFF"]
    regimeScore: int = Field(ge=0, le=100)
    candidates: list[CandidateInput] = Field(min_length=1, max_length=20)
    model_config = {"extra": "forbid"}


class RankedCandidate(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    rank: Literal[1, 2, 3]
    reason: str = Field(min_length=1, max_length=200)
    action: Literal["enter", "watch", "wait"]
    model_config = {"extra": "forbid"}


class CandidateRankerOutput(BaseModel):
    topCandidates: list[RankedCandidate] = Field(min_length=3, max_length=3)
    model_config = {"extra": "forbid"}
```

> 不导出 guardrail 函数（无 deterministic 锚点）。BANNED_PHRASES 检测放到 trade_plan 同款 helper 还是显式不做？**默认显式不做**（ranker 输出 reason 短句，BANNED_PHRASES 命中风险极低；F211 复盘阶段统一抽 helper 时再回扫）。

#### 1.1.2 `backend/app/ai/schemas/trade_plan.py`（新建，~140 行，含 guardrail）

**职责**：定义 `trade_plan` schema + **D068 guardrail** + SYSTEM_PROMPT + BANNED_PHRASES。

```python
"""Trade Plan task schema (F210-a, critical tier).

Input: full Decision quote (ticker + entry/stop/target + size + risk + earnings + hash)
Output: memo + management list + echoed entry/stop/size (must match input — D068 guardrail)
"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

from app.ai.errors import AiGuardrailViolation
from app.services.cockpit.cockpit_params import DECISION

SCHEMA_VERSION = "v1"
HASH_PRICE_DECIMALS = 2  # 与 decision_service._compute_hash 对齐（DECISION.HASH_PRICE_DECIMALS）

SYSTEM_PROMPT = """You are an equity trade planning assistant for a slow-trading system.
You receive a fully deterministic trade quote (entry / stop / size already computed).
You MUST NOT alter entry / stop / size — echo them verbatim. Add narrative memo and
management rules only.

Rules:
- memo: 2-4 sentences, ≤ 600 chars; cite setup type and earnings risk if non-SAFE
- management: 1-5 short imperative rules (e.g. "Move stop to BE near 2R", "Trail with 21EMA")
- entry / stop / size: copy input values exactly, do not round, do not adjust
Prohibited phrases (never use): buy now, sell now, 保证收益, 承诺收益, 忽略止损, ignore stop
Output must be valid JSON matching the schema exactly. No extra keys.
"""

BANNED_PHRASES: tuple[str, ...] = (
    "buy now", "sell now", "保证收益", "承诺收益", "忽略止损", "ignore stop",
)


class TradePlanInput(BaseModel):
    ticker: str = Field(min_length=1, max_length=10, pattern=r"^[A-Z][A-Z0-9.\-]*$")
    setupType: Literal["BREAKOUT", "PULLBACK", "RECLAIM", "EARNINGS_DRIFT", "EXTENDED", "BROKEN", "NONE"]
    setupQuality: Literal["A", "B", "C"] | None = None
    entry: float = Field(gt=0)
    stop: float = Field(gt=0)
    target2r: float = Field(gt=0)
    target3r: float = Field(gt=0)
    size: int = Field(ge=1)                          # decision.suggestedShares
    rewardRisk: float = Field(ge=0)
    accountRiskPct: float = Field(ge=0, le=100)
    earningsRisk: Literal["SAFE", "CAUTION", "DANGER"]
    deterministicHash: str = Field(min_length=8)     # decision.deterministicHash 截断后（8 字符以上）
    model_config = {"extra": "forbid"}


class TradePlanOutput(BaseModel):
    memo: str = Field(min_length=1, max_length=600)
    management: list[str] = Field(min_length=1, max_length=5)
    entry: float = Field(gt=0)                       # echoed
    stop: float = Field(gt=0)                        # echoed
    size: int = Field(ge=1)                          # echoed
    model_config = {"extra": "forbid"}


def guardrail(input_dict: dict, output_dict: dict) -> None:
    """D068: entry / stop / size 必须严格等于 input（小数位对齐到 2 位）；BANNED_PHRASES 文本扫描。"""
    # ---- 数字锚点（D068 核心）----
    in_entry = round(float(input_dict["entry"]), HASH_PRICE_DECIMALS)
    in_stop = round(float(input_dict["stop"]), HASH_PRICE_DECIMALS)
    in_size = int(input_dict["size"])

    out_entry = round(float(output_dict.get("entry", 0)), HASH_PRICE_DECIMALS)
    out_stop = round(float(output_dict.get("stop", 0)), HASH_PRICE_DECIMALS)
    out_size = int(output_dict.get("size", 0))

    if out_entry != in_entry:
        raise AiGuardrailViolation(
            f"trade_plan entry mismatch: input={in_entry} output={out_entry}"
        )
    if out_stop != in_stop:
        raise AiGuardrailViolation(
            f"trade_plan stop mismatch: input={in_stop} output={out_stop}"
        )
    if out_size != in_size:
        raise AiGuardrailViolation(
            f"trade_plan size mismatch: input={in_size} output={out_size}"
        )

    # ---- BANNED_PHRASES 扫描（沿用 setup_explainer 风格）----
    parts: list[str] = [output_dict.get("memo", "") or ""]
    items = output_dict.get("management") or []
    if isinstance(items, list):
        parts.extend(str(x) for x in items)
    combined = " ".join(parts).lower()
    for phrase in BANNED_PHRASES:
        if phrase.lower() in combined:
            raise AiGuardrailViolation(f"banned phrase: {phrase}")
```

**关键设计点**：
1. **不重算 hash**：guardrail 只对比 `entry/stop/size` 三个数字，**不**对 input.deterministicHash 做 SHA-256 复算。理由：`decision_service._compute_hash` 还需要 `effective_risk_pct` 和 `snapshot_date`，gateway input 不带这两个字段，复算会引入跨服务耦合。**deterministicHash 字段在 schema 中是"前端传给后端的标识，gateway 不复算"** — 真正的护栏靠"输入 = 输出"的数字一致性。如需 hash 级一致性校验，应在 endpoint 层（不在 F210-a 内）。
2. **decimals 对齐 2 位**：与 `decision_service._compute_hash` 的 `HASH_PRICE_DECIMALS` 语义同步。risk_pct 有 4 位精度（HASH_RISK_DECIMALS），但 trade_plan 输入不含 risk_pct，无关。
3. **size 用 int 比较**：避免浮点比较误差。
4. **gateway step 9 失败 → step 10 不执行**：guardrail 抛错时 ai_memos **不写**（与 D068 "不落表不返回计划" 一致；当前 gateway 主流程已是这个语义）。

#### 1.1.3 `backend/app/ai/schemas/__init__.py`（修改，~+5 行）

```python
# 在 import 段补
from app.ai.schemas import candidate_ranker as _cr
from app.ai.schemas import trade_plan as _tp

# REGISTRY 字典内补两行（替换 line 32-33 占位）
"candidate_ranker":      SchemaPair(_cr.CandidateRankerInput, _cr.CandidateRankerOutput),
"trade_plan":            SchemaPair(_tp.TradePlanInput, _tp.TradePlanOutput),

# 模块级 guardrail 注册段补一行（紧跟 line 41 setup_explainer 注册之后）
_gr.register("trade_plan", _tp.guardrail)
# candidate_ranker 不注册 — 无 deterministic 锚点
```

#### 1.1.4 `backend/tests/test_ai_schemas_f210a.py`（新建，~280 行 / ~22 用例）

参照 `tests/test_ai_schemas_f209.py` 的组织方式（class-per-task + 输入正/负 + 输出正/负 + guardrail 行为）。

| 类 | # | 用例 | 类型 |
|----|---|------|------|
| `TestCandidateRankerInput` | I1 | 1 candidate（边界，min_length=1）通过 | 单元 |
|  | I2 | 20 candidates（边界，max_length=20）通过 | 单元 |
|  | I3 | 21 candidates → ValidationError（max_length） | 单元 |
|  | I4 | 0 candidates → ValidationError | 单元 |
|  | I5 | regime 非枚举 → ValidationError | 单元 |
|  | I6 | trendScore=6 → ValidationError（ge/le 0-5） | 单元 |
|  | I7 | rsPercentile=101 → ValidationError | 单元 |
|  | I8 | candidates[0].setupType 非枚举 → ValidationError | 单元 |
|  | I9 | extra 字段 → ValidationError（extra=forbid） | 单元 |
| `TestCandidateRankerOutput` | O1 | 3 ranked + rank 1/2/3 完整 → 通过 | 单元 |
|  | O2 | 2 ranked → ValidationError（min_length=3） | 单元 |
|  | O3 | 4 ranked → ValidationError（max_length=3） | 单元 |
|  | O4 | rank=4 → ValidationError | 单元 |
|  | O5 | action 非枚举 → ValidationError | 单元 |
|  | O6 | reason > 200 chars → ValidationError | 单元 |
| `TestTradePlanInput` | TI1 | 完整字段通过 | 单元 |
|  | TI2 | entry=0 → ValidationError（gt=0） | 单元 |
|  | TI3 | size=0 → ValidationError（ge=1） | 单元 |
|  | TI4 | deterministicHash 长度 < 8 → ValidationError | 单元 |
| `TestTradePlanGuardrail` | G1 | output entry/stop/size 全等于 input → pass（无异常） | 单元 |
|  | G2 | output.entry 偏 0.01 → AiGuardrailViolation（小数对齐严格） | 单元 |
|  | G3 | output.stop 偏 0.01 → AiGuardrailViolation | 单元 |
|  | G4 | output.size=input.size+1 → AiGuardrailViolation | 单元 |
|  | G5 | output.entry=850.001 vs input=850.00（rounding 后等） → pass | 单元 |
|  | G6 | memo 含 "buy now" → AiGuardrailViolation（banned phrase） | 单元 |
|  | G7 | management 含 "ignore stop" → AiGuardrailViolation | 单元 |
| `TestRegistry` | R1 | `get_schemas("candidate_ranker")` 返回 SchemaPair | 单元 |
|  | R2 | `get_schemas("trade_plan")` 返回 SchemaPair | 单元 |
|  | R3 | `guardrail._HOOKS["trade_plan"]` 已注册 | 单元 |
|  | R4 | `guardrail._HOOKS.get("candidate_ranker")` 为 None | 单元 |

> 测试文件复用 F209 测试的 fixture / helper 风格（直接构造 dict + Pydantic 校验）。

---

### 1.2 排除（明确不做）

- ❌ **不动 gateway.py / routing.py / endpoint ai.py**（routing 已正确映射到 critical tier；endpoint 已是动态 dispatch，新加 task 自动可用）
- ❌ **不写前端**（F210-b/c 处理）
- ❌ **不动 decision_service.py**（trade_plan guardrail 不复算 hash，仅对比 entry/stop/size 三字段）
- ❌ **不加 endpoint 层 silent truncate**（candidates > 20 走 422 严格校验；如需 silent truncate 留 F210-b/endpoint 改造）
- ❌ **不动 ai_memos schema / Alembic**（无新字段）
- ❌ **不加 candidate_ranker guardrail**（无 deterministic 锚点；BANNED_PHRASES 暂不查）
- ❌ **不动 cockpit_params.py**（HASH_PRICE_DECIMALS 已存在 DECISION.HASH_PRICE_DECIMALS，trade_plan.py 直接 import 复用）
- ❌ **不加 e2e LiteLLM 真实调用测试**（F208-c 已覆盖；本 sprint 是纯 schema 单测）

---

## 2. 预计修改文件清单（共 4 个，远低于 6 文件上限）

| 路径 | 操作 | 预计行数 |
|------|------|---------|
| `backend/app/ai/schemas/candidate_ranker.py` | 新建 | +110 |
| `backend/app/ai/schemas/trade_plan.py` | 新建 | +140 |
| `backend/app/ai/schemas/__init__.py` | 修改 | +5 / -2（替换占位注释） |
| `backend/tests/test_ai_schemas_f210a.py` | 新建 | +280 |

---

## 3. 完成标准（每条可测试）

| # | 完成标准 | 测试层级 | 工具 |
|---|---------|---------|------|
| C1 | `candidate_ranker` schema 输入 1-20 candidates 范围内通过；超 20 / 0 / 字段缺失 → ValidationError | 单元 | pytest |
| C2 | `candidate_ranker` schema 输出强制 3 项 + rank 1/2/3 + action 三枚举 | 单元 | pytest |
| C3 | `trade_plan` schema 输入 11 字段全部约束生效（entry/stop/target gt=0；size ge=1；deterministicHash min_length=8；earningsRisk/setupType 枚举） | 单元 | pytest |
| C4 | `trade_plan` guardrail：output entry/stop/size 与 input 完全相等（2 位小数后） → 无异常 | 单元 | pytest |
| C5 | `trade_plan` guardrail：任一字段偏移 → `AiGuardrailViolation` 抛出（带具体字段名信息） | 单元 | pytest |
| C6 | `trade_plan` guardrail：BANNED_PHRASES 命中（memo 或 management）→ `AiGuardrailViolation` | 单元 | pytest |
| C7 | REGISTRY：`get_schemas("candidate_ranker")` / `get_schemas("trade_plan")` 返回正确 SchemaPair | 单元 | pytest |
| C8 | `guardrail._HOOKS["trade_plan"]` 已注册；`candidate_ranker` 未注册 | 单元 | pytest |
| C9 | gateway e2e（复用 test_ai_gateway_e2e_f208c 的 monkeypatch 套路）：调 `task_type=trade_plan` 且 mock LLM 输出修改 size → 收到 `AiGuardrailViolation`，**memo 不入表**（DB count 不变） | 集成 | pytest + monkeypatch |
| C10 | gateway e2e：调 `task_type=candidate_ranker` mock LLM 输出 3 项合法 → memo 入表，无 guardrail 调用 | 集成 | pytest |
| C11 | 全量回归：`uv run pytest backend/tests/` 全绿（不引入回归） | 回归 | pytest |
| C12 | `uv run mypy backend/app/ai/schemas/` 无新错（与 F209-a 同基线） | 工程 | mypy |
| C13 | 进程启动 smoke：`uv run python -c "from app.ai.schemas import REGISTRY; assert 'candidate_ranker' in REGISTRY and 'trade_plan' in REGISTRY"` 退出码 0 | 工程 | python |
| C14 | features.json AC 对应：AC1（两 task schema 齐全 ✅ C1+C3）/ AC2（critical tier ✅ routing.py 现状校验，本 sprint 不动 routing 但要在测试 R5 显式 assert resolve_tier 返回 "critical"）/ AC3（trade_plan entry/stop/size = F203 deterministic ✅ C4-C5）/ AC4（≤20 截断+meta：本 sprint 仅做 422 强校验，meta 标记 deferred 到 F210-b endpoint 层；**待用户确认**）/ AC5-AC6（前端属于 F210-b/c） | 文档 | grep |

---

## 4. 开发顺序（Generator 模式严格执行）

```
1. 确认 DATA-MODEL.md 无需改动 → ✅（不动表）
2. 确认 API-CONTRACT.md 无需改动 → ✅（统一 envelope 已涵盖 7 task；schema 细节由 feature-dev 落地，line 1731-1732 明文允许）
3. 确认 routing.py 已映射 critical tier → ✅（line 11-12）
4. 数据库迁移 → ⏭ 跳过
5. Repository → ⏭ 跳过
6. Service → ⏭ 跳过
7. 单元测试 → 与 step 8 交叠（TDD：先写 G2-G4 三个核心 guardrail 用例，再实现 trade_plan.py）
8. Schema 落地 →
   8a. 新建 candidate_ranker.py（仅 schema，无 guardrail）
   8b. 新建 trade_plan.py（schema + guardrail 函数）
   8c. 修改 schemas/__init__.py（REGISTRY 两行 + 1 行 register）
   8d. 写完 8a-c 后跑 `uv run pytest backend/tests/test_ai_schemas_f210a.py -v`
9. 加 e2e 集成测试（C9/C10），可在已有 test_ai_gateway_e2e_f208c.py 内追加，**或**新文件 test_ai_gateway_e2e_f210a.py
   > 默认追加到已有文件，避免文件爆炸（不计入 4 文件上限，规则 8 测试扩展许可）
10. 全量 pytest + mypy 全绿
11. Evaluator 模式自检
```

每步通过后 wip commit（`git add` 显式列文件，禁用 `-A`）：
- step 8a → `wip(F210-a): candidate_ranker schema`
- step 8b → `wip(F210-a): trade_plan schema + guardrail`
- step 8c → `wip(F210-a): registry wiring`
- step 9 → `wip(F210-a): e2e guardrail test`

---

## 5. Evaluator 自检清单

- [ ] 单元测试：I1-I9 / O1-O6 / TI1-TI4 / G1-G7 / R1-R4 全部通过
- [ ] 集成 C9/C10 通过（guardrail 抛错时 ai_memos 计数不增）
- [ ] `uv run pytest backend/tests/ -v` 全绿（≥ 之前基线条数 + 22）
- [ ] `uv run mypy backend/app/ai/` 无新错
- [ ] 启动 smoke：`uv run uvicorn app.main:app --port 8001` 不报 import 错（schemas/__init__.py 模块加载即触发 register）
- [ ] `curl -X POST localhost:8001/api/ai/trade_plan -H "Content-Type: application/json" -d '{"input":{...},"noCache":true}'` 在无 OPENAI_API_KEY 时收到 `AI_PROVIDER_ERROR`（502），不是 schema/registry 报错
- [ ] BANNED_PHRASES 列表与 setup_explainer 完全一致（grep 比对）
- [ ] HASH_PRICE_DECIMALS 与 cockpit_params.DECISION.HASH_PRICE_DECIMALS 同值（避免漂移）—— **trade_plan.py 直接 import**，本约束自动成立
- [ ] D070 "无魔法数字" 检查：trade_plan.py 内 `HASH_PRICE_DECIMALS` 来自 import（已满足）；其他常量（max_length=20 / 600 / 200）属 schema 层文案约束，按 F209-a 先例不进 cockpit_params
- [ ] 颜色 / 前端 token 不涉及（纯后端 sprint）
- [ ] 无 console.error / 残余 print
- [ ] `git status` 无遗留未提交改动

---

## 6. 开放问题

| # | 问题 | 默认 | 备选 |
|---|------|------|------|
| Q1 | candidates > 20 的处理 | **422 严格校验**（schema `max_length=20`）；前端 F210-b 入参前 slice 到 20 | endpoint 层 silent truncate + meta.truncated=true 标记（需要改 ai.py 路由层，超 F210-a 范围） |
| Q2 | trade_plan guardrail 是否复算 SHA-256 hash？ | **否**，仅比 entry/stop/size 三字段（理由：避免 schema 层 import decision_service / 处理 risk_pct + snapshot_date） | 是，schema 内 import decision_service._compute_hash 复算 |
| Q3 | candidate_ranker 是否做 BANNED_PHRASES 扫描？ | **否**（reason 短句风险低；统一抽 helper 留 F211 复盘） | 是，注册 guardrail hook 仅做文本扫描 |
| Q4 | candidate_ranker 输出是否允许 < 3 项（候选不足时）？ | **否**，硬性 3 项（与 features.json AC5 "top 3" 一致；候选 < 3 时由前端 F210-b 不发请求处理） | 改 `max_length=3, min_length=1`，前端按实际渲染 |
| Q5 | trade_plan input 是否要带 target2r / target3r？ | **是**（提供给 LLM 作 management 参考，如 "Move stop to BE near 2R"），但不进 guardrail 校验 | 不带，让 LLM 不知 target |

> Q1/Q3/Q5 默认采用本表方案；Q2 决策上面 §1.1.2 已述；Q4 默认硬性 3 项。

---

## 7. 风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| LiteLLM `response_format=Pydantic` 对 nested model（CandidateInput list / RankedCandidate list）支持不一致 | 中 | LLM 实际输出可能字段缺失 → schema 二次校验失败 → AiSchemaError | 已有 gateway step 8 兜底；本 sprint 单测不依赖真 LLM |
| guardrail 浮点比较精度漂移 | 低 | 合法 trade_plan 误判 violation | `round(., 2)` + int 显式转换；G5 用例覆盖边界 |
| candidate_ranker 排序逻辑实际效果差（LLM 拍脑袋） | 中 | 用户感知质量差，但不属本 sprint 范围 | 本 sprint 只保 schema 形状；调优留观察期 + F211 反馈循环 |
| HASH_PRICE_DECIMALS 未来从 cockpit_params 修改 | 低 | guardrail 与 decision_service 漂移 | trade_plan.py import `from app.services.cockpit.cockpit_params import DECISION`，单一源 |
| schemas/__init__.py 修改触发 F209/F208 既有测试回归 | 低 | 全量 pytest 红 | C11 强制全量回归 |

---

## 8. F210-b / F210-c 骨架预览（仅供用户确认拆分合理性，非本 sprint 落地）

### F210-b — SetupMonitor "AI 排序" 集成

**触发**：F210-a Evaluator 通过后开新 sprint。

**核心**：
- 新建 `frontend/src/cockpit/components/AiCandidateRankerSection.tsx`（顶部按钮 + 加载/成功/错误三态 + top 3 列表 + 缓存命中徽章）
- 修改 `SetupMonitorWidget.tsx`：表格上方追加按钮区，点击调 `callAiTask<CandidateRankerInput, CandidateRankerOutput>('candidate_ranker', ...)`，输入从当前 items[] 取 `slice(0, 20)` 并按 §1.1.1 字段映射
- 测试扩展 `SetupMonitorWidget.test.tsx` §R 段（~10 用例：按钮渲染 / slice 截断 / top 3 展示 / 错误态 / cache）

预计 3-4 文件。

### F210-c — DecisionPanel "Generate AI Plan" 集成

**核心**：
- 新建 `frontend/src/cockpit/components/AiTradePlanSection.tsx`（按钮 + memo / management 卡片 + guardrail violation 红色 banner + cache meta）
- 修改 `DecisionPanelWidget.tsx`：在 Decision Card 下方追加该组件，输入从当前 decision 数据取 §1.1.2 11 字段映射
- 测试扩展 `DecisionPanelWidget.test.tsx`（~12 用例：含 409 AI_GUARDRAIL_VIOLATION 渲染 / memo 渲染 / 缓存命中）

预计 3-4 文件。

---

确认 Contract 后我会：
1. 更新 features.json：F210 新增 sub_phase_notes "拆 a/b/c"；F210-a 标记 `phase = contract_agreed`
2. 更新 claude-progress.txt（追加 Contract 协商记录）
3. 生成新 SESSION-HANDOFF.md（覆盖 F209-c 那份，下一步指向 F210-a Generator）
4. **停止**，建议你在新 session 开 Sonnet 进入 Generator 模式
