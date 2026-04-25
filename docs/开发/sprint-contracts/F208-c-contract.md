# Sprint Contract：F208-c — AI Gateway 主流程 + LiteLLM 集成 + `/api/ai/{task_type}` endpoint

> 状态：已确认 | 起草：2026-04-25 | 用户确认：2026-04-25
> 父 Feature：F208 LLM Gateway（v2.0 Cockpit P2 AI 层基座）
> 兄弟：F208-a（基座，done）/ F208-b（核心模块 errors/memo_repo/budget/routing，done）/ **F208-c（编排 + 对外，本 sprint）**
> 引用文档：
>   - DATA-MODEL.md §AiMemo（写入字段权威，13 列；不增不删）
>   - API-CONTRACT.md §POST /api/ai/{task_type}（请求 / 响应 / 错误码完整契约，含 cache hit meta 字段）
>   - DECISIONS.md D064（LiteLLM + 单一动态 endpoint + tier 三档）
>   - DECISIONS.md D068（trade_plan guardrail 框架；本 sprint 落地框架，trade_plan 具体 hook 留 F210）
>   - DECISIONS.md D069（ai_memos 双用途；TTL + schema_version 命中规则）
>   - F208-b-contract.md §7（"明确排除"即本 sprint 范围）

---

## 0. 背景与定位

F208 拆分链：F208-a（基座）→ F208-b（4 个支撑模块）→ **F208-c（编排 + 对外）**。

F208-b 完成后 `backend/app/ai/` 已有 4 个纯 Python 模块（errors / memo_repo / budget / routing），但**没有任何调用方**。本 sprint 的职责：

1. 把这 4 个模块编排为 `AiGateway.run(task_type, input_dict, no_cache=False)` 主流程
2. 引入 LiteLLM 真实调用（运行时 lazy import，测试全 mock 不打 token）
3. 落地 guardrail 框架（registry pattern，默认 no-op；F210 trade_plan 在此 hook）
4. 落地 schemas registry（task_type → input/output Pydantic schema），内置 `echo` 任务用于自测
5. 暴露 `POST /api/ai/{task_type}` 统一 endpoint，符合 API-CONTRACT envelope
6. 完整 mock-LiteLLM 集成测试覆盖 7 条 gateway 路径 + endpoint 错误码映射

完成后：F209 / F210 / F211 只需在 `backend/app/ai/schemas/` 新增 task 专属 schema 文件并在 `REGISTRY` 注册，无需再动 gateway / endpoint 代码。

---

## 1. 实现范围

### 1.1 包含

#### 1.1.1 `gateway.py` — `AiGateway.run()` 主流程

```python
class AiGateway:
    def __init__(self, db: Session) -> None: ...

    def run(
        self,
        *,
        task_type: str,
        input_dict: dict[str, Any],
        no_cache: bool = False,
    ) -> GatewayResult: ...
```

主流程编排（按顺序，任一步失败立即抛对应异常）：

| # | 步骤 | 失败行为 |
|---|------|---------|
| 1 | 查 schemas registry，取 `(input_schema, output_schema)` | 不存在 → 抛 `KeyError`，由 endpoint 转 `VALIDATION_ERROR 422` |
| 2 | `input_schema(**input_dict)` 校验 | Pydantic ValidationError → 由 endpoint 转 `VALIDATION_ERROR 422` |
| 3 | `compute_input_hash(input_dict)` | — |
| 4 | 若 `no_cache=False`：`AiMemoRepository.find_cached(...)` | 命中 → 直接组装 cache-hit `GatewayResult` 返回（不进 budget / routing / LLM） |
| 5 | `assert_within_budget(db)` | 超额 → `AiBudgetExceeded` |
| 6 | `routing.resolve(task_type)` → `(tier, model_id)` | — |
| 7 | LiteLLM 调用（lazy import `litellm`），用 `response_format=output_schema` | 任何异常（含超时 / 网络 / provider 5xx）→ `AiProviderError` |
| 8 | `output_schema(**llm_output)` 二次校验（防 LiteLLM response_format 失效） | ValidationError → `AiSchemaError` |
| 9 | `guardrail.run(task_type, input_dict, output_dict)` | 抛 `AiGuardrailViolation` |
| 10 | `AiMemoRepository.write(...)` | — |
| 11 | 返回 `GatewayResult`（含 memo_id、output、meta） | — |

`GatewayResult` 是简单 dataclass / TypedDict（gateway 内部数据结构，不直接当 HTTP 响应）：

```python
@dataclass(frozen=True)
class GatewayResult:
    memo_id: int | None        # cache hit 时取自 cached memo.id；miss 取自 write 返回
    task_type: str
    schema_version: str
    output: dict[str, Any]
    meta: GatewayMeta

@dataclass(frozen=True)
class GatewayMeta:
    model_used: str            # cache hit 固定 "cache"
    tier: str                  # cache hit 取自 cached memo.tier
    tokens_in: int             # cache hit = 0
    tokens_out: int            # cache hit = 0
    cost_usd: Decimal          # cache hit = Decimal("0")
    latency_ms: int            # cache hit < 50（实测耗时，不强造）
    cache_hit: bool
```

LiteLLM 调用细节：
- **lazy import**：`import litellm` 写在 `_call_litellm()` 函数内部，避免模块 import 时强依赖
- 调用接口：`litellm.completion(model=model_id, messages=[{"role":"user","content":json.dumps(input_dict)}], response_format=output_schema)`
- 解析返回：取 `response.choices[0].message.content`（JSON 字符串），`json.loads` 后过 Pydantic 二次校验
- token / cost：`response.usage.prompt_tokens` / `response.usage.completion_tokens` / `litellm.completion_cost(response)`
- 任何 LiteLLM 抛错 → 包成 `AiProviderError(str(e))`

**写 memo 时机**：仅在 step 9（guardrail）通过后写。Guardrail 抛错的输出不入表（D068 安全原则，不能让被拒输出污染 audit）。Provider / Schema / Budget 异常也不写（这些都没产生有效 LLM 输出）。

#### 1.1.2 `guardrail.py` — post-validate 框架

```python
GuardrailHook = Callable[[dict[str, Any], dict[str, Any]], None]
# (input_dict, output_dict) -> None；违规 raise AiGuardrailViolation

_HOOKS: dict[str, GuardrailHook] = {}

def register(task_type: str, hook: GuardrailHook) -> None: ...
def run(task_type: str, input_dict: dict, output_dict: dict) -> None: ...
    # 未注册 hook → 直接 return（默认 no-op）
    # 已注册 → 执行；hook 内部抛 AiGuardrailViolation 即透传
```

设计：
- 模块级 dict 注册表，进程启动时不预注册任何 hook（默认 no-op）
- F210 在自身 sprint 引入时调用 `guardrail.register("trade_plan", _validate_trade_plan)` 即可挂上（不动 gateway）
- 测试通过 monkeypatch 临时注册 hook 验证拦截路径

#### 1.1.3 `ai/schemas/__init__.py` — 任务 schema 注册表

```python
from typing import NamedTuple
from pydantic import BaseModel

class SchemaPair(NamedTuple):
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]

# Internal echo task — F208-c smoke test only, NOT in API-CONTRACT 7 enums
class _EchoInput(BaseModel):
    text: str
    model_config = {"extra": "forbid"}

class _EchoOutput(BaseModel):
    echoed: str
    model_config = {"extra": "forbid"}

REGISTRY: dict[str, SchemaPair] = {
    "echo": SchemaPair(_EchoInput, _EchoOutput),
    # F209/F210/F211 在各自 sprint 注册 7 个生产 task：
    # "market_narrator": ..., "setup_explainer": ..., "candidate_ranker": ...,
    # "trade_plan": ..., "contradiction_detector": ..., "news_summarizer": ...,
    # "journal_assistant": ...
}

def get_schemas(task_type: str) -> SchemaPair: ...  # KeyError if missing
def has_schema(task_type: str) -> bool: ...
```

**echo 任务约束**：
- 仅作为 F208-c 自测桩，不在 API-CONTRACT §POST /api/ai/{task_type} 的 7 个 Literal 枚举内
- 因此 `POST /api/ai/echo` HTTP 路径**应该 422**（被 endpoint 层 Literal 拦截）
- echo 测试通过**直接调用 `AiGateway.run("echo", ...)`** 进行（绕过 endpoint），自测 7 条路径
- echo 也需要在 routing._TASK_TIER 中加一条：`"echo": "default"` —— 修改 F208-b 的 routing.py（本 sprint 显式列出此处微调，不算新文件）

> ⚠️ 用户决策点：是否允许本 sprint 在 routing.py 加一行 `"echo": "default"`？  
> 替代方案：gateway 收到 echo 时绕过 routing.resolve()，硬编码 tier="default" + model="echo-mock"。  
> **推荐方案 A（routing 加一行 + 注释 "test-only, not in API-CONTRACT"）**，理由：保持 gateway 只走单一路径（避免 if-test-then-else 污染主流程），routing 是模块级常量便于未来移除。

#### 1.1.4 `routers/ai.py` — `POST /api/ai/{task_type}` endpoint

```python
from typing import Any, Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai import gateway as ai_gateway
from app.ai.errors import (
    AiBudgetExceeded, AiGuardrailViolation, AiProviderError, AiSchemaError,
)
from app.database import get_db
from app.services.watchlist_service import APIError

router = APIRouter(tags=["ai"])

# 7 production task_types 严格按 API-CONTRACT §POST /api/ai/{task_type}
TaskTypeEnum = Literal[
    "market_narrator", "setup_explainer",
    "candidate_ranker", "trade_plan",
    "contradiction_detector", "news_summarizer", "journal_assistant",
]

class AiRequestEnvelope(BaseModel):
    input: dict[str, Any]
    no_cache: bool = Field(default=False, alias="noCache")
    model_config = {"populate_by_name": True}

class AiMeta(BaseModel):
    model_used: str = Field(alias="modelUsed")
    tier: str
    tokens_in: int = Field(alias="tokensIn")
    tokens_out: int = Field(alias="tokensOut")
    cost_usd: float = Field(alias="costUsd")
    latency_ms: int = Field(alias="latencyMs")
    cache_hit: bool = Field(alias="cacheHit")
    model_config = {"populate_by_name": True}

class AiResponseData(BaseModel):
    memo_id: int = Field(alias="memoId")
    task_type: str = Field(alias="taskType")
    schema_version: str = Field(alias="schemaVersion")
    output: dict[str, Any]
    meta: AiMeta
    model_config = {"populate_by_name": True}

class AiResponse(BaseModel):
    data: AiResponseData
    message: str = "success"


@router.post("/{task_type}", response_model=AiResponse, response_model_by_alias=True)
def post_ai(
    task_type: TaskTypeEnum,
    body: AiRequestEnvelope,
    db: Session = Depends(get_db),
) -> AiResponse:
    try:
        result = ai_gateway.AiGateway(db).run(
            task_type=task_type,
            input_dict=body.input,
            no_cache=body.no_cache,
        )
    except KeyError:
        raise APIError("VALIDATION_ERROR", f"unregistered task_type: {task_type}", 422) from None
    except ValidationError as e:  # pydantic.ValidationError on input_schema
        raise APIError("VALIDATION_ERROR", str(e), 422) from e
    except AiBudgetExceeded as e:
        raise APIError("AI_BUDGET_EXCEEDED", str(e), 429) from e
    except AiGuardrailViolation as e:
        raise APIError("AI_GUARDRAIL_VIOLATION", str(e), 409) from e
    except AiSchemaError as e:
        raise APIError("AI_SCHEMA_ERROR", str(e), 502) from e
    except AiProviderError as e:
        raise APIError("AI_PROVIDER_ERROR", str(e), 502) from e
    return AiResponse(data=AiResponseData(...))  # 由 result 字段填充
```

错误码映射对照（与 API-CONTRACT §POST /api/ai/{task_type} 错误响应表 100% 一致）：

| 内部异常 | 错误码 | HTTP |
|---------|--------|------|
| `task_type` Literal 校验失败 | `VALIDATION_ERROR` | 422（FastAPI 422 的 `RequestValidationError` 已挂在 `main.py`，复用） |
| schemas REGISTRY KeyError | `VALIDATION_ERROR` | 422 |
| Pydantic input_schema ValidationError | `VALIDATION_ERROR` | 422 |
| `AiProviderError` | `AI_PROVIDER_ERROR` | 502 |
| `AiSchemaError` | `AI_SCHEMA_ERROR` | 502 |
| `AiBudgetExceeded` | `AI_BUDGET_EXCEEDED` | 429 |
| `AiGuardrailViolation` | `AI_GUARDRAIL_VIOLATION` | 409 |

> ⚠️ 复用既有 `APIError` 异常类型 + `main.py` 现成的 `handle_api_error` JSONResponse handler，不新增 handler。

#### 1.1.5 `main.py` — 注册 router

```python
# 既有 import 行追加：
from app.routers import ai as ai_router  # noqa: F401  避免名字冲突
# 注册行追加（在 cockpit_router 之后）：
app.include_router(ai_router.router, prefix="/api/ai")
```

#### 1.1.6 `tests/test_ai_gateway_e2e_f208c.py` — 测试

测试结构：
- **§A Gateway 7 路径（mock LiteLLM）** — 直接调 `AiGateway(db).run("echo", ...)`，monkeypatch `app.ai.gateway._call_litellm` 注入桩响应
- **§B Endpoint envelope + 错误码（FastAPI TestClient）** — 用真实 task `market_narrator`（在测试 setup 中临时往 REGISTRY 注册一个简易 schema），mock LiteLLM 验证 envelope alias / 错误码映射
- **§C Live smoke（1 个 `@pytest.mark.live` 测试）** — 真实打 OpenAI，`OPENAI_API_KEY` 未设时 `pytest.skip`；默认全量回归 `-m 'not live'` 不触发

```python
@pytest.mark.live
def test_echo_live_smoke(db_session):
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    result = AiGateway(db_session).run(
        task_type="echo",
        input_dict={"text": "ping"},
        no_cache=True,
    )
    assert isinstance(result.output.get("echoed"), str)
    assert result.meta.cache_hit is False
    assert result.meta.tokens_in > 0
    assert result.meta.cost_usd > Decimal("0")
    # ai_memos 真实写入一行
```

> ⚠️ §B 临时注册的 schema 在 test fixture 的 `yield` 后必须从 REGISTRY 移除（避免污染其他测试的全局状态）。用 `pytest fixture` + `try/finally` 包裹。
> ⚠️ §C 通过 `settings.openai_api_key`（F208-a env 字段）读取，绝不出现在测试常量 / 代码 / git 历史中。

### 1.2 明确排除（本次不做）

- **F209/F210/F211 的真实 task schema** —— 各自 sprint 在 `backend/app/ai/schemas/` 各自落地
- **D068 trade_plan 的 deterministic guardrail hook 实现** —— 框架本 sprint 落地，hook 实现在 F210
- **Streaming / function calling / fallbacks** —— D064 提及 LiteLLM 支持但 v2.0 未声明使用，本 sprint 仅用 `litellm.completion(response_format=...)`
- **AI_MEMO 180 天 retention 清理 cron** —— 数据建模文档 §AiMemo 提及但归 deployment 阶段（与 earnings retention 并行）
- **前端调用链** —— Cockpit widget 在 F209/F210/F211 各自接入

---

## 2. 预计修改文件（共 6 个 ≤ 上限 6）

| # | 文件路径 | 改动 | 说明 |
|---|----------|------|------|
| 1 | `backend/app/ai/gateway.py` | 新建 | `AiGateway` 类 + `GatewayResult/GatewayMeta` dataclass + `_call_litellm` lazy import 包装 |
| 2 | `backend/app/ai/guardrail.py` | 新建 | `register()` / `run()` + 模块级 `_HOOKS` dict |
| 3 | `backend/app/ai/schemas/__init__.py` | 新建 | `SchemaPair` NamedTuple + `REGISTRY` dict + `get_schemas()` / `has_schema()` + 内置 echo 任务 |
| 4 | `backend/app/routers/ai.py` | 新建 | endpoint + Request/Response Pydantic envelope + 错误码映射 |
| 5 | `backend/app/main.py` | 修改 | 2 行：import + include_router |
| 6 | `backend/tests/test_ai_gateway_e2e_f208c.py` | 新建 | §A gateway 7 路径 + §B endpoint envelope/错误码 |

**附加微调（不计入 6 文件主清单，因仅 1 行）**：
- `backend/app/ai/routing.py` — 在 `_TASK_TIER` 加一行 `"echo": "default"`，并在注释标注 "test-only, not in API-CONTRACT §POST /api/ai/{task_type} 的 7 enums"

> 🛑 用户在确认 Contract 时需明确接受：(a) 接受将 endpoint envelope 内联进 routers/ai.py 的轻微 pattern 偏离（cockpit 既有 router 通常将 schema 放 `app/schemas/cockpit/*`）；(b) 接受 routing.py 加 echo 一行作为附加微调。

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 / 用例 |
|---|---------|---------|-------------|
| 1 | `AiGateway.run("echo", {"text":"hi"})` 在 REGISTRY 命中 + LiteLLM mock 返回 `{"echoed":"hi"}` 时，返回 `cache_hit=False`、`memo_id` 为新 row、ai_memos 新增一行 | 集成 | pytest + monkeypatch + sqlite session |
| 2 | 重复调用相同 input → 第二次 `cache_hit=True`、`tokens_in=0`、`tokens_out=0`、`cost_usd=0`、`model_used="cache"`、不打 LiteLLM、ai_memos 不新增行 | 集成 | pytest（断言 monkeypatch mock 调用次数 == 1） |
| 3 | 第二次调用传 `no_cache=True` → 强制刷新，`cache_hit=False`、ai_memos 多 1 行（同 input_hash 的两条记录共存） | 集成 | pytest |
| 4 | 月度 cost SUM 已达 cap → `AiGateway.run()` 抛 `AiBudgetExceeded`，未触发 LiteLLM、未写 memo | 集成 | pytest（提前 insert 一条 cost_usd=20 的 memo + cap=20） |
| 5 | LiteLLM mock 抛任意 `Exception` → gateway 抛 `AiProviderError`，未写 memo | 集成 | pytest |
| 6 | LiteLLM mock 返回不符合 output_schema 的 JSON（缺 echoed 字段）→ gateway 抛 `AiSchemaError`，未写 memo | 集成 | pytest |
| 7 | 临时注册 echo 的 guardrail hook 抛 `AiGuardrailViolation` → gateway 透传该异常，未写 memo | 集成 | pytest（fixture register + cleanup） |
| 8 | `POST /api/ai/echo` HTTP 422（不在 7 enums 内） | 集成 | FastAPI TestClient |
| 9 | `POST /api/ai/market_narrator` 成功路径返回严格符合 API-CONTRACT envelope（camelCase alias、data.memoId/output/meta/meta.cacheHit/...） | 集成 | TestClient + 临时 REGISTRY 注册 + monkeypatch LiteLLM |
| 10 | endpoint 错误码映射 6 条全覆盖：input ValidationError → 422 / AiProviderError → 502 AI_PROVIDER_ERROR / AiSchemaError → 502 AI_SCHEMA_ERROR / AiBudgetExceeded → 429 AI_BUDGET_EXCEEDED / AiGuardrailViolation → 409 AI_GUARDRAIL_VIOLATION / unknown task_type Literal → 422 VALIDATION_ERROR | 集成 | TestClient × 6 case |
| 11 | `GET /docs` 可见 `POST /api/ai/{task_type}` 且 task_type 字段类型显示为 7-value enum | 集成 | TestClient（解析 /openapi.json） |
| 12 | guardrail.run 默认未注册 hook 时为 no-op；register() 后调用生效 | 单元 | pytest（直接调用 guardrail 模块） |
| 13 | gateway 模块顶层 import 时**不**触发 `import litellm`（懒加载，便于离线 CI） | 单元 | pytest（断言 `sys.modules` 在 import gateway 后不含 "litellm"） |
| 14 | 字段命名 100% 对照 DATA-MODEL §AiMemo 13 列写入（task_type / input_hash / input_json / output_json / schema_version / model_used / tier / tokens_in / tokens_out / cost_usd / latency_ms） | 单元 | grep + assert 写入字段 |
| 15 | 设置 `OPENAI_API_KEY` 后 `pytest -m live` 通过 echo live smoke：真实返回非空 echoed、tokens_in/out > 0、cost_usd > 0、ai_memos 真实写入 1 行 | live | pytest -m live |

---

## 4. 开发顺序（Generator 模式必须按此推进）

1. **schemas/__init__.py** — 先把 `SchemaPair` + `REGISTRY` + 内置 echo + `get_schemas` 写好（gateway 依赖此）
2. **guardrail.py** — 模块级 dict 注册表 + register/run（gateway 依赖此）
3. **routing.py 微调** — 加 `"echo": "default"` 一行（含注释）
4. **gateway.py** — `_call_litellm` lazy import + `AiGateway.run()` 主流程
5. **routers/ai.py** — endpoint + envelope + 错误码映射
6. **main.py** — 注册 router 2 行
7. **测试文件 §A**（gateway 7 路径）→ 跑通后 commit
8. **测试文件 §B**（endpoint envelope/错误码 6 case + /docs 可见性）→ 跑通后 commit
9. 单模块回归 + 全量回归（≥ 520 基线）

每完成一步且通过该步最小验证（单元/类型 import OK），立即按 §2 文件清单 wip commit（禁用 `git add -A`）。

---

## 5. Evaluator 自检清单

开发完成后，Evaluator 模式逐条打勾，全过才能进 needs_review：

- [ ] §3 表格 14 条标准全覆盖
- [ ] gateway.py 顶层未 `import litellm`（仅 `_call_litellm` 内部 lazy import）
- [ ] gateway 写 memo 仅在 guardrail 通过后；provider/schema/budget/guardrail 错误均**不写表**
- [ ] cache hit 路径 `tokens_in=0` / `tokens_out=0` / `cost_usd=Decimal("0")` / `model_used="cache"` / 不调用 LiteLLM mock
- [ ] cache hit 时 `memo_id` 取自 cached memo.id（不是 None，不是 0）
- [ ] no_cache=True 时跳过 find_cached，直接进 budget/routing/LiteLLM/write
- [ ] 错误码映射与 API-CONTRACT 表 100% 一致（VALIDATION_ERROR / AI_PROVIDER_ERROR / AI_SCHEMA_ERROR / AI_BUDGET_EXCEEDED / AI_GUARDRAIL_VIOLATION）
- [ ] endpoint 响应 camelCase alias 全部生效（memoId / taskType / schemaVersion / modelUsed / tokensIn / tokensOut / costUsd / latencyMs / cacheHit）
- [ ] schemas/__init__.py 仅注册 echo 一个；7 production task 留待 F209/F210/F211（注释明示）
- [ ] guardrail 默认 no-op；test fixture 注册 hook 后 yield 末尾必须 cleanup（避免全局污染其他测试）
- [ ] routing.py 加 echo 一行附 "test-only" 注释，未变更其他 7 task → tier 映射
- [ ] 字段命名 100% 对照 DATA-MODEL §AiMemo（grep 确认 input_json / output_json / model_used / cost_usd 等下划线一致）
- [ ] 无新增 pytest DeprecationWarning
- [ ] 无 console / print 调试残留
- [ ] DECISIONS.md 无需新决策（D064/D068/D069 已覆盖；如有偏离需追加）
- [ ] git status 干净（无未追踪 / 未提交文件）
- [ ] 回归测试：当前 sprint test 全 pass + 全量 `uv run pytest -m 'not live'` ≥ 520 基线（F208-b 验收时基线），新增预期 ~12-16 测试（§A 7 + §B 6 + §C 1 skip + 单元 2-3）
- [ ] live smoke 测试标记 `@pytest.mark.live`，未设 `OPENAI_API_KEY` 时 `pytest.skip`
- [ ] 默认全量回归 `pytest -m 'not live'` **不**触发 live smoke（保护 CI / 离线环境）
- [ ] OPENAI_API_KEY 走 `settings.openai_api_key`，不写入任何代码 / 测试常量 / git 历史 / log
- [ ] live smoke 跑过 1 次后用户在 ai_memos 表确认一条真实 row（model_used = 实际 OpenAI model id，cost_usd > 0）

### 5.1 D070 合规检查
- [ ] gateway / routers / schemas 代码内无魔法数字阈值（cache TTL / budget cap / schema_version 全走 settings；echo schema 字段无阈值）
- [ ] 本 sprint 不新增 cockpit_params.py 字段（gateway 层不属于 cockpit_params 范围）

### 5.2 代码质量
- [ ] 单个函数 ≤ 50 行（`AiGateway.run` 若超过 → 拆 `_check_cache` / `_call_and_validate` 私有方法）
- [ ] 无重复代码块（错误码映射如有 6 个相似 `except`，可保留显式列举不抽象，提交时说明）
- [ ] 错误处理完整：所有 `except` 都有具体类型，无裸 `except:`，无吞错

---

## 6. 风险与缓解

| 风险 | 缓解 |
|------|------|
| LiteLLM `response_format=Pydantic` 实际返回的 message.content 可能是已 parse 的对象（不是 JSON 字符串），版本差异 | gateway 内部判断：若 content 是 dict 直接用，是 str 才 `json.loads`；二次过 Pydantic 校验兜底 |
| schemas REGISTRY 全局状态被测试污染 | §B endpoint 测试用 fixture try/finally 强制 cleanup；提供 `_reset_for_tests()` 私有 helper（仅测试用） |
| budget 检查与 LiteLLM 调用之间的 race（多次并发） | 单用户单进程项目（D066），不做并发保护；F208-b 已有此假设 |
| LiteLLM cost_usd 返回 None / NaN 边界 | gateway 强制 `Decimal(str(litellm.completion_cost(response) or 0))`，写入前最小约束 |
| FastAPI Literal 校验返回的 422 错误码默认是 RequestValidationError（main.py 已 handler 成 VALIDATION_ERROR），与 endpoint 内 `APIError("VALIDATION_ERROR",...)` 路径并存但格式一致 | 测试 §B 同时验证两种 422 路径返回的 envelope 一致 |

---

## 7. 用户确认结果（2026-04-25）

1. ✅ 接受 6 文件清单（gateway / guardrail / schemas/__init__ / routers/ai / main.py / test）
2. ✅ 接受 endpoint envelope 内联 routers/ai.py（不新建 `app/schemas/ai.py`）
3. ✅ 接受 routing.py 加 `"echo": "default"` 一行（带 "test-only" 注释）作为附加微调
4. ✅ 接受 §B 用 `market_narrator` 临时注册 schema 做 endpoint 测试（fixture cleanup 保证不污染）
5. ✅ 接受加入 §C live smoke 1 测试（`@pytest.mark.live`，echo task，OPENAI_API_KEY 未设时 skip）
6. ✅ 用户提供 OpenAI key，走 backend/.env 的 `OPENAI_API_KEY` 字段（已在 .gitignore）

---

✅ Contract 已确认。Generator 模式从 §4 开发顺序 step 1（schemas/__init__.py）开始。
