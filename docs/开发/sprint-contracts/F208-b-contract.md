# Sprint Contract：F208-b — AI Gateway 核心模块（errors / memo_repo / budget / routing）

> 状态：已确认 | 起草：2026-04-25 | 用户确认：2026-04-25
> 父 Feature：F208 LLM Gateway（v2.0 Cockpit P2 AI 层基座）
> 兄弟：F208-a（基座，已 done）/ F208-c（gateway 主流程 + endpoint，待 b 完成后启动）
> 引用文档：
>   - DATA-MODEL.md §AiMemo（memo_repo 操作目标，13 列字段权威）
>   - DECISIONS.md D064（LiteLLM + tier 三档；本 sprint 落地 routing 表与 tier→model 解析）
>   - DECISIONS.md D069（ai_memos 双用途；本 sprint 落地 memo dedup 命中规则与 budget 月度 SUM）
>   - F208-a-contract.md（Settings 7 字段、AiMemo ORM、Alembic 012 已就位）

---

## 0. 背景与定位

F208 拆分链：F208-a（基座）→ **F208-b（核心支撑层）** → F208-c（主流程 + endpoint）。

F208-a 完成后已具备：
- `litellm 1.83.13` 在 lockfile
- Settings 7 个 AI 字段（`ai_model_default` / `ai_model_critical` / `ai_model_complex` / `openai_api_key` / `ai_monthly_budget_usd` / `ai_memo_cache_ttl_hours` / `ai_schema_version`）
- `ai_memos` 表 + 复合索引
- `AiMemo` ORM

本 Sprint 在此基座上落地 4 个**纯 Python 支撑模块** + 配套测试，**不打 LLM、不暴露 endpoint、不依赖 LiteLLM 运行时**（仅 routing 模块读取 Settings 中的 model 字符串，不实例化 LiteLLM client）。模块解耦后，F208-c 只需把它们编排成 `AiGateway.run()`。

---

## 1. 实现范围

### 1.1 包初始化（`backend/app/ai/__init__.py`）

新建空 `__init__.py`（仅一行 docstring，不重导出符号；F208-c 再视情况增加 `from .gateway import AiGateway`）。

### 1.2 errors.py — 4 个异常类

```python
"""AI gateway exception hierarchy (D064)."""


class AiError(Exception):
    """Base for all AI gateway errors. Never raised directly."""


class AiProviderError(AiError):
    """LiteLLM 调用失败（网络 / provider 5xx / 超时）。"""


class AiSchemaError(AiError):
    """LLM 返回结果未通过 Pydantic output schema 校验。"""


class AiBudgetExceeded(AiError):
    """当月累计 cost_usd ≥ AI_MONTHLY_BUDGET_USD（D069）。"""


class AiGuardrailViolation(AiError):
    """post-validate hook 拒绝输出（D068 trade_plan 等）。"""
```

设计细节：
- 提供 `AiError` 共同基类，便于 F208-c 在 endpoint 层做一次 `except AiError` 兜底映射错误码
- 4 个具体异常**不带必传字段**（msg 走 `Exception.__init__`），保持调用点 `raise AiBudgetExceeded(f"month_to_date={x:.4f} >= cap={y}")` 的自由度
- 不在本文件定义错误码常量；错误码 → HTTP 状态映射归属 F208-c 的 endpoint 层（API-CONTRACT.md 已定）

### 1.3 memo_repo.py — 持久化 + dedup 查询（Repository class 风格）

```python
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.ai_memo import AiMemo


def compute_input_hash(input_dict: dict[str, Any]) -> str:
    """SHA-256 of canonical JSON (sort_keys + compact separators) → 64 hex chars.

    Module-level helper (not on the Repository) so callers can compute the hash
    without instantiating a DB-bound object — the gateway uses it once for both
    find_cached and write.
    """
    canonical = json.dumps(input_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class AiMemoRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_cached(
        self,
        *,
        task_type: str,
        input_hash: str,
        schema_version: str,
        ttl_hours: int,
        now: datetime | None = None,
    ) -> AiMemo | None:
        """Return latest matching memo within TTL window, else None.

        Hit conditions (all required):
          - task_type 相同
          - input_hash 相同
          - schema_version 相同（D069: schema 升级旧 memo 自动 invalidate）
          - created_at > now - ttl_hours
        """
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=ttl_hours)
        return (
            self.db.query(AiMemo)
            .filter(
                AiMemo.task_type == task_type,
                AiMemo.input_hash == input_hash,
                AiMemo.schema_version == schema_version,
                AiMemo.created_at > cutoff,
            )
            .order_by(AiMemo.created_at.desc())
            .first()
        )

    def write(
        self,
        *,
        task_type: str,
        input_dict: dict[str, Any],
        output_dict: dict[str, Any],
        schema_version: str,
        model_used: str,
        tier: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: Decimal,
        latency_ms: int,
        input_hash: str | None = None,
    ) -> int:
        """Insert one ai_memos row. Returns AiMemo.id.

        Caller may pass precomputed input_hash to avoid double-hashing
        (gateway computes hash once, uses it for find_cached then write).
        """
        if input_hash is None:
            input_hash = compute_input_hash(input_dict)
        memo = AiMemo(
            task_type=task_type,
            input_hash=input_hash,
            input_json=_canonical_json(input_dict),
            output_json=_canonical_json(output_dict),
            schema_version=schema_version,
            model_used=model_used,
            tier=tier,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            # created_at 由 ORM default 生成 UTC now
        )
        self.db.add(memo)
        self.db.commit()
        self.db.refresh(memo)
        return memo.id
```

设计细节：
- **Repository class 风格**，与 `JournalRepository` / `UserSettingsRepository` / `DailyBarRepository` 等保持一致；`self.db` 命名（不是 `_db`）对齐 `JournalRepository`
- `compute_input_hash` 是模块级函数（不挂在 Repository 上）— 理由：哈希计算无需 DB session，gateway 在 dedup 流程开头计算一次后既要传给 `find_cached` 又要传给 `write`，模块级 helper 更自然
- `_canonical_json` 是模块级私有 helper，避免 `write` 内重复字符串拼接
- 关键字参数（`*,`）强制 caller 显式命名，13 个字段不会传错位
- `write` 不接 `error_code` 字段：DATA-MODEL §AiMemo 当前 schema **不含** `error_code` 列（D069 文字描述提及但 v2.0 schema 表未加）；如需失败也落库审计，需先走 system-design 加列 → 不在本 sprint 范围
- `input_json` / `output_json` 也用 canonical JSON 写入，便于审计 diff 一致

### 1.4 budget.py — 月度 SUM 熔断

```python
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.ai_memo import AiMemo

from .errors import AiBudgetExceeded


def month_to_date_cost(db: Session, *, now: datetime | None = None) -> Decimal:
    """Return SUM(cost_usd) of ai_memos created since first day of current UTC month."""
    now = now or datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = (
        db.query(func.coalesce(func.sum(AiMemo.cost_usd), 0))
        .filter(AiMemo.created_at >= month_start)
        .scalar()
    )
    return Decimal(total)


def assert_within_budget(
    db: Session,
    *,
    cap_usd: float | None = None,
    now: datetime | None = None,
) -> Decimal:
    """Raise AiBudgetExceeded when month-to-date cost ≥ cap. Returns current MTD on success.

    cap_usd defaults to settings.ai_monthly_budget_usd; passing explicit value
    is for testability (override without env juggling).
    """
    cap = Decimal(str(cap_usd if cap_usd is not None else settings.ai_monthly_budget_usd))
    mtd = month_to_date_cost(db, now=now)
    if mtd >= cap:
        raise AiBudgetExceeded(f"month_to_date={mtd} >= cap={cap}")
    return mtd
```

设计细节：
- 边界语义：**`mtd ≥ cap`** 即抛错（acceptance criteria 第 4 条"恰好等于上限抛错"）。理由：cap 是绝对上限，等于即触顶；下一次调用必然超
- `month_start` 用 UTC，与 `created_at` 默认时区一致（F208-a 已统一 UTC，D070 不涉及）
- `cap_usd` 参数化便于 unit test 不依赖 env；生产路径默认读 settings
- 返回 `mtd` 给 caller（F208-c 可在 response meta 暴露当前预算消耗，可选）

### 1.5 routing.py — task_type → tier → model_id

```python
from typing import Literal

from app.config import settings

# task_type → tier 映射（DATA-MODEL §AiMemo task_type 枚举 + D064 tier 分配）
# 7 种 task_type；F209/F210/F211 各自对应若干
_TASK_TIER: dict[str, Literal["default", "critical", "complex"]] = {
    "market_narrator": "default",        # F209
    "setup_explainer": "default",        # F209
    "candidate_ranker": "critical",      # F210
    "trade_plan": "critical",            # F210
    "contradiction_detector": "default", # F211
    "news_summarizer": "default",        # F211
    "journal_assistant": "complex",      # F211
}


def known_task_types() -> tuple[str, ...]:
    return tuple(_TASK_TIER.keys())


def resolve_tier(task_type: str) -> str:
    if task_type not in _TASK_TIER:
        raise ValueError(f"unknown task_type: {task_type!r} (known={list(_TASK_TIER)})")
    return _TASK_TIER[task_type]


def resolve_model(tier: str) -> str:
    """Map tier → Settings model field."""
    if tier == "default":
        return settings.ai_model_default
    if tier == "critical":
        return settings.ai_model_critical
    if tier == "complex":
        return settings.ai_model_complex
    raise ValueError(f"unknown tier: {tier!r}")


def resolve(task_type: str) -> tuple[str, str]:
    """Convenience: task_type → (tier, model_id)."""
    tier = resolve_tier(task_type)
    return tier, resolve_model(tier)
```

设计细节：
- `_TASK_TIER` 是模块级常量字典，不走 Pydantic（不属于 D070 的 Cockpit 算法参数；D070 明确"AI 模型名 → .env"，本模块只是 task→tier 路由静态表，无可调阈值，常量字典最简单）
- 三个分层函数（`resolve_tier` / `resolve_model` / `resolve`）便于测试隔离（routing 表错误 vs Settings 错误）
- 未知 task_type / tier 抛 `ValueError`（不抛 `AiProviderError` — 这是**调用方代码 bug**，不是 provider 问题；F208-c endpoint 层把 ValueError 映射为 `VALIDATION_ERROR 422`）
- 不在本模块实例化 LiteLLM Router（那是 F208-c 的事）；只回模型字符串

### 1.6 测试（`backend/tests/test_ai_core_modules_f208b.py`）

复用 conftest.py 现有 `db_session` fixture（基于 in-memory SQLite + `Base.metadata.create_all`，已包含 `ai_memos`）。

| # | 测试名 | 内容 |
|---|--------|------|
| 1 | `test_input_hash_is_order_invariant` | `compute_input_hash({"a":1,"b":2})` == `compute_input_hash({"b":2,"a":1})`，且都为 64 字符 hex |
| 2 | `test_input_hash_distinguishes_values` | `{"a":1}` vs `{"a":2}` 哈希不等；`{"a":1}` vs `{"a":"1"}` 哈希不等（类型敏感） |
| 3 | `test_input_hash_stable_with_unicode` | 含中文 key/value 的 dict 哈希稳定（`ensure_ascii=False`） |
| 4 | `test_routing_seven_task_types_mapped` | `known_task_types()` 包含 7 个；逐个 `resolve(t)` → tier 与 features.json 描述一致 |
| 5 | `test_routing_unknown_task_type_raises` | `resolve("foo")` 抛 `ValueError`，message 含 `"foo"` |
| 6 | `test_routing_uses_settings_models` | `monkeypatch.setattr(settings, "ai_model_critical", "claude-sonnet-4-6")` 后 `resolve("trade_plan")[1] == "claude-sonnet-4-6"` |
| 7 | `test_memo_write_returns_id_and_persists` | `AiMemoRepository(db).write(...)` 返回正整数 id；`db.query(AiMemo).get(id)` 字段值一致 |
| 8 | `test_memo_find_cached_hit_within_ttl` | 写一条 memo（`now-1h`）→ `repo.find_cached(ttl_hours=24, ...)` 命中 |
| 9 | `test_memo_find_cached_miss_after_ttl` | 写一条 memo（`now-25h`，通过显式构造 AiMemo + 改写 created_at）→ `repo.find_cached(ttl_hours=24)` 返回 None |
| 10 | `test_memo_find_cached_miss_on_schema_version_mismatch` | 写 schema_version="v1" → `repo.find_cached(schema_version="v2")` 返回 None |
| 11 | `test_memo_find_cached_returns_latest_when_multiple` | 同 (task_type, input_hash, schema_version) 写 2 条，间隔时间 → `repo.find_cached` 返回较新一条 |
| 12 | `test_memo_write_uses_canonical_input_json` | 不传 `input_hash`，传 `{"b":2,"a":1}`；落库后 `input_json == '{"a":1,"b":2}'` 且 `input_hash` 与 `compute_input_hash({"a":1,"b":2})` 一致 |
| 13 | `test_budget_zero_when_no_memos` | 空表 → `month_to_date_cost(db) == Decimal("0")`；`assert_within_budget(db, cap_usd=10)` 不抛错且返回 Decimal("0") |
| 14 | `test_budget_sums_current_month_only` | 写 1 条上月 cost=5、1 条本月 cost=3 → MTD == Decimal("3") |
| 15 | `test_budget_exceeds_at_exact_cap` | MTD 等于 cap（写一条 cost=10，cap=10）→ `assert_within_budget` 抛 `AiBudgetExceeded`，message 含两个数字 |
| 16 | `test_budget_uses_settings_default_cap` | `monkeypatch.setattr(settings, "ai_monthly_budget_usd", 1.0)` + 写一条 cost=2 → 不传 cap 也抛错 |

测试 9 / 14 需要写入"非默认时间"的 AiMemo —— 直接 `AiMemo(created_at=<指定时间>)` 构造（model 的 default 是 lambda，构造时显式传值会跳过 default）。测试 6 / 16 用 `monkeypatch.setattr(settings, ...)` 而非 `setenv` —— Settings 单例已实例化，env 改动不会自动重载。

---

## 2. 预计修改文件清单（精确 6 个）

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/ai/__init__.py` | 新增 | 包初始化（仅 docstring） |
| 2 | `backend/app/ai/errors.py` | 新增 | `AiError` 基类 + 4 个具体异常 |
| 3 | `backend/app/ai/memo_repo.py` | 新增 | `AiMemoRepository` class（`find_cached` / `write`）+ 模块级 `compute_input_hash` |
| 4 | `backend/app/ai/budget.py` | 新增 | `month_to_date_cost` / `assert_within_budget` |
| 5 | `backend/app/ai/routing.py` | 新增 | `_TASK_TIER` 表 + `resolve_tier` / `resolve_model` / `resolve` / `known_task_types` |
| 6 | `backend/tests/test_ai_core_modules_f208b.py` | 新增 | 16 个测试用例 |

不超 6 文件上限。**纯新增**，不修改任何现有文件。

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `errors.py` 4 个异常类全部存在且继承自 `AiError`，`AiError` 继承自 `Exception` | 单元 | pytest（`isinstance` 断言） |
| 2 | `compute_input_hash` 对相同 dict 的不同 key 顺序产出相同 64-hex 串 | 单元 | pytest（测试 1） |
| 3 | `compute_input_hash` 对值类型敏感（int 1 ≠ str "1"） | 单元 | pytest（测试 2） |
| 4 | `routing.resolve(t)` 对 7 种 task_type 返回 (tier, model_id)，tier 分配与 features.json `_iteration_log[v2.0].description` 一致 | 单元 | pytest（测试 4） |
| 5 | `routing.resolve("foo")` 抛 `ValueError` | 单元 | pytest（测试 5） |
| 6 | Settings 字段被 monkeypatch 后，`routing.resolve(critical_task)[1]` 立即反映新值 | 单元 | pytest（测试 6） |
| 7 | `AiMemoRepository.write` 返回 `int` id，写入后 13 列字段值与传参严格一致（cost_usd 精度不丢） | 集成 | pytest + db_session |
| 8 | `AiMemoRepository.find_cached` 在 TTL 内命中、超 TTL miss、schema_version 不一致 miss、多条命中返最新 | 集成 | pytest + db_session（测试 8/9/10/11） |
| 9 | 不传 `input_hash` 时，`write` 自动用 `compute_input_hash` 计算并写入 canonical `input_json` | 集成 | pytest（测试 12） |
| 10 | `budget.month_to_date_cost` 仅累加当月（≥ 月初 UTC 00:00）；空表返 Decimal("0") | 集成 | pytest（测试 13/14） |
| 11 | `budget.assert_within_budget` 在 MTD == cap 时抛 `AiBudgetExceeded`；message 含 mtd 与 cap 数值 | 集成 | pytest（测试 15） |
| 12 | 不传 cap_usd 时，`assert_within_budget` 默认读 `settings.ai_monthly_budget_usd` | 集成 | pytest（测试 16） |
| 13 | `from app.ai import errors, memo_repo, budget, routing` 全部 import 成功，无循环依赖 | 集成 | pytest（任一测试触发即覆盖） |
| 14 | 全量回归 `uv run pytest -m 'not live'` 通过率不低于 main 分支水平（503 passed 基线） | 回归 | pytest |

---

## 4. Generator 开发顺序

```
1. backend/app/ai/__init__.py + backend/app/ai/errors.py
   (errors.py 无依赖，先落基础异常)
   wip commit: "wip(F208-b): ai package + errors module"

2. backend/app/ai/routing.py
   (routing 只依赖 settings，无 DB)
   wip commit: "wip(F208-b): routing task_type → tier → model"

3. backend/app/ai/memo_repo.py
   (依赖 AiMemo ORM；AiMemoRepository class + 模块级 compute_input_hash)
   wip commit: "wip(F208-b): AiMemoRepository write + find_cached"

4. backend/app/ai/budget.py
   (依赖 AiMemo + errors.AiBudgetExceeded)
   wip commit: "wip(F208-b): budget month_to_date + assert_within_budget"

5. backend/tests/test_ai_core_modules_f208b.py
   (16 测试，按 4 个模块分 4 个 test class 或顺序排布)
   pytest 全跑通
   wip commit: "wip(F208-b): core modules unit + integration tests"

6. 全量回归 uv run pytest -m 'not live'
   (无新失败则进入 Evaluator)
```

每步严格按文件名 `git add <path>`，**禁用 `git add -A`**。

---

## 5. Evaluator 自检清单

- [ ] §3 表格 14 条全部 ✅
- [ ] 4 个新模块均无对 `litellm` 包的运行时 import（本 sprint 不打 LLM；litellm 只是 lockfile 中存在）
- [ ] 字段命名 100% 对照 DATA-MODEL §AiMemo（含 `model_used` / `tokens_in` / `tokens_out` / `cost_usd` / `latency_ms`）
- [ ] 无硬编码 model 字符串（routing 全走 settings）
- [ ] 无硬编码 cap（budget 默认走 settings.ai_monthly_budget_usd）
- [ ] 无对 `error_code` 列的引用（v2.0 schema 表无此列；如需求出现先走 system-design）
- [ ] 无新增 pytest warning（DeprecationWarning 等）
- [ ] DECISIONS.md 不需要新决策（D064 / D069 已定方案，本 sprint 仅执行）
- [ ] `git status` 干净，所有改动按文件名显式 commit
- [ ] 全量回归通过率不低于 main（503 passed 基线，本 sprint 预期 +16 = 519 passed）
- [ ] D070 合规：本 sprint 未引入 Cockpit 算法阈值，无需写入 cockpit_params.py（routing 表是 dispatch 字典，非可调阈值）

### 代码质量自检
- [ ] Lint：`uv run ruff check backend/app/ai/ backend/tests/test_ai_core_modules_f208b.py`（项目已用 ruff）无新增 warning
- [ ] 无死代码、无未使用 import
- [ ] 无重复代码（canonical JSON 序列化在 memo_repo 内复用 helper）

---

## 6. 风险点

- **R1（cost_usd 精度）**：SQLAlchemy `Numeric(10,6)` 在 SQLite 上读出为 Decimal；`func.sum` 在 SQLite 可能返回 float。`Decimal(total)` 强转 + 测试 14 显式断言 `Decimal` 类型。
- **R2（月初边界）**：`month_to_date_cost` 用 `created_at >= month_start`（含等号）。本月 1 号 00:00:00 写入的 memo 必须计入本月。测试 14 的"上月"行用 `month_start - timedelta(seconds=1)` 构造确保不踩边界。
- **R3（routing tier 顺序）**：features.json `_iteration_log[v2.0]` 描述是权威来源（"contradiction_detector/news_summarizer→default、journal_assistant→complex"），与 DATA-MODEL §AiMemo task_type 表的 tier 列一致。测试 4 直接断言这 7 个映射对，避免 DATA-MODEL 与代码 drift。
- **R4（Settings 单例 vs monkeypatch）**：`config.py` 末尾 `settings = Settings()` 是 module-level 单例。测试用 `monkeypatch.setattr(settings, "ai_model_critical", ...)` 直接改实例属性（不走 env 重载）。生产代码每次 `settings.ai_model_default` 读属性即取最新，方案安全。
- **R5（无循环依赖）**：依赖图为 `errors ← budget`；`budget → errors + AiMemo + settings`；`memo_repo → AiMemo`（不依赖 errors）；`routing → settings`。无环，import 顺序无关。

---

## 7. 排除项（明确不做，留给 F208-c）

- LiteLLM Router 实例化、真实 LLM 调用、`response_format=Pydantic` 调用
- `gateway.py` 主流程编排
- `guardrail.py` post-validate 框架
- `schemas/` Pydantic 注册表
- `POST /api/ai/{task_type}` endpoint
- `main.py` 注册 ai router
- API-CONTRACT 错误码 → HTTP 状态映射

以上全部留给 F208-c。

---

👤 用户确认（2026-04-25）：5 项设计点全部接受。features.json F208-b phase → `contract_agreed`，强制结束当前 session，建议新开 Sonnet session 执行 Generator。
