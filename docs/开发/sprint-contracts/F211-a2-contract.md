# Sprint Contract：F211-a2 — Per-task Model Override 基建

> 状态：草案，待用户确认 | 起草：2026-04-28
> 父 Feature：F211 AI Contradiction Detector + News Summarizer + Journal Assistant
> 拆分位置：F211-a1 ✅ done / **F211-a2（本 sprint）** / F211-b / F211-c / F211-d
> 依赖：
>   - F208-c ✅（AiGateway 主流程：`gateway.py` 调 LiteLLM 已透传 `api_key`，但未透传 `api_base`，cost 仅依赖 LiteLLM 内置 pricing）
>   - F211-a1 ✅（3 个 F211 task schema + REGISTRY + guardrail，本 sprint 不动 schema 层）
> 引用文档：
>   - DECISIONS.md §D064（LiteLLM 三 tier 模型 .env 驱动；本 sprint 在 D064 基础上叠加 per-task override，不破坏 tier 兜底）
>   - DECISIONS.md §D070 line 1527（AI 模型配置走 .env，**不**进 `cockpit_params.py`；本 sprint 沿用此约定）
>   - DECISIONS.md §D069（ai_memos 双用途，cost 字段是审计核心；override 注入的自定义 cost 必须能正确写入 `cost_usd`）
>   - CLAUDE.md "开发时文档查询（强制）" — LiteLLM 通过 context7 `/websites/litellm` 查询最新 API 形态（`api_base` per-call 调用 + `register_model` 当前签名），不得凭训练数据
>   - F211-a1 contract §8 line 466-480（F211-a2 骨架预览，本契约即其落地版）
>   - backend/app/config.py line 35-43（v2.0 F208 AI Gateway 字段块，本 sprint 在该块尾部追加一行）
>   - backend/app/ai/routing.py（line 8-17 _TASK_TIER；line 41-44 resolve() 当前签名）
>   - backend/app/ai/gateway.py line 41-80（`_call_litellm` 当前调用形态：仅传 `api_key`，未传 `api_base`，cost 走 `litellm.completion_cost`）
>   - backend/app/main.py（lifespan hook，本 sprint **不**在此注入 register_model — 见 §1.2 设计决定）

---

## 0. 背景与定位

F211-a1 已经完成 3 个 task 的 schema + guardrail + REGISTRY 注册。但所有 7 个 task_type（market_narrator / setup_explainer / candidate_ranker / trade_plan / contradiction_detector / news_summarizer / journal_assistant）当前**只能**走 D064 的三档 tier 模型 `.env`：`AI_MODEL_DEFAULT` / `AI_MODEL_CRITICAL` / `AI_MODEL_COMPLEX`，且全部**共用**单一 `OPENAI_API_KEY` 端点。

实际使用场景中：
1. `news_summarizer` 单次输入 30×500=15K char，但用户可能想用更大上下文模型（如 Anthropic Sonnet）→ 需要换 model + base_url + key
2. `journal_assistant` monthly 模式可能想接本地 Ollama / Together / Groq → 不同 base_url + 自定义价格
3. `candidate_ranker` 高频调用，用户可能切到更便宜的 inference 服务（DeepSeek/Qwen）→ 需自定义 cost rate 才能让 D069 月度预算 cap 正确生效

**F211-a2 范围**：在不破坏 D064 三 tier 兜底的前提下，叠加一层**可选的 per-task override**，env 驱动、JSON 单字段、fallback 安全。本 sprint **不**改 endpoint、**不**改 schema、**不**改 guardrail、**不**动前端，只在 `config.py` / `routing.py` / `gateway.py` 三个文件 + 1 个新测试文件 + DECISIONS.md 落地。

**关键约束**：
1. **向后兼容**：未配置 `AI_TASK_OVERRIDES_JSON` 时所有现有行为完全不变（877 测试零回归）。
2. **fail-soft**：JSON 解析失败 → log warning + 整个 override 字段视为空（不抛、不 crash），系统继续按 tier 兜底运行。**不**做局部 entry 容错（一个坏 entry 直接拖垮整个 dict 是预期行为，避免静默错配）。
3. **D070 合规**：所有新字段进 `.env`，**不**进 `cockpit_params.py`。
4. **D069 cost 注入正确性**：override 提供 `inputCostPer1m` / `outputCostPer1m` 时，LiteLLM `completion_cost()` 返回值必须使用该自定义价（而非内置 pricing），否则月度预算 cap 会错算。
5. **不做的事**：不引入新外部依赖（litellm 已在 pyproject）；不改 ai_memos 表（model_used 字段足以审计）；不改 API-CONTRACT（endpoint 不变）；不写 admin endpoint 让前端切 model（用户改 `.env` 重启即可，符合"个人投资工具"定位）。

---

## 1. 实现范围

### 1.1 包含

#### A. Settings 字段（config.py 第 1 文件）

在 `Settings` 类的 v2.0 F208 AI Gateway 字段块尾部追加一行：

```python
# F211-a2 per-task model override (D075)
ai_task_overrides_json: str = ""  # JSON dict: task_type → {model, base_url, api_key, input_cost_per_1m, output_cost_per_1m}
```

`.env` 字段名自动映射为 `AI_TASK_OVERRIDES_JSON`（pydantic-settings 大写规则）。

**JSON 结构**（用户 `.env` 配置示例）：

```bash
AI_TASK_OVERRIDES_JSON='{"news_summarizer":{"model":"anthropic/claude-sonnet-4-6","base_url":"https://api.anthropic.com","api_key":"sk-ant-...","input_cost_per_1m":3.0,"output_cost_per_1m":15.0},"journal_assistant":{"model":"openai/local-llama","base_url":"http://localhost:11434/v1","api_key":"ollama","input_cost_per_1m":0.0,"output_cost_per_1m":0.0}}'
```

字段语义：
- `model`（必填）：LiteLLM model id（含 provider prefix，如 `anthropic/claude-sonnet-4-6` / `openai/...`）
- `base_url`（可选）：透传给 `litellm.completion(api_base=...)`；缺失/空字符串 → 使用 LiteLLM 默认端点
- `api_key`（可选）：透传给 `litellm.completion(api_key=...)`；缺失/空字符串 → fallback 到 `settings.openai_api_key`（保证向后兼容现有 OPENAI_API_KEY）
- `input_cost_per_1m`（可选）：每 1M input token 价（USD）；提供则通过 `litellm.register_model({...})` 注入
- `output_cost_per_1m`（可选）：每 1M output token 价（USD）；同上

**JSON 字段命名**：`snake_case`（与 .env 习惯一致），routing.py 内部 dataclass 字段同样 `snake_case`。**这与 D074 schema 字段 camelCase 的约束不冲突** — D074 仅约束 ai_memos 内部 JSON 字段，本 sprint 是 .env 配置。

#### B. routing.py 新签名（第 2 文件）

引入 `ResolvedRoute` dataclass + override 解析 + 修订 `resolve()` 签名。

```python
"""task_type → tier → model_id routing (D064) + per-task override (D075, F211-a2)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Literal

from app.config import settings

log = logging.getLogger(__name__)

_TASK_TIER: dict[str, Literal["default", "critical", "complex"]] = {
    # ... 与现状一致，不动
}


@dataclass(frozen=True)
class ResolvedRoute:
    tier: str
    model: str
    base_url: str | None       # None = LiteLLM 默认端点
    api_key: str               # 绝不为 None，回落到 settings.openai_api_key
    custom_input_cost: float | None   # per 1M tokens; None = 使用 LiteLLM 内置
    custom_output_cost: float | None  # per 1M tokens; None = 使用 LiteLLM 内置


def known_task_types() -> tuple[str, ...]:
    return tuple(_TASK_TIER.keys())


def resolve_tier(task_type: str) -> str:
    """保留旧签名（test_ai_core_modules_f208b / test_ai_schemas_f209a/f210a/f211a1 在用）。"""
    if task_type not in _TASK_TIER:
        raise ValueError(f"unknown task_type: {task_type!r} (known={list(_TASK_TIER)})")
    return _TASK_TIER[task_type]


def resolve_model(tier: str) -> str:
    """保留旧签名（test_ai_core_modules_f208b 在用）。"""
    if tier == "default":
        return settings.ai_model_default
    if tier == "critical":
        return settings.ai_model_critical
    if tier == "complex":
        return settings.ai_model_complex
    raise ValueError(f"unknown tier: {tier!r}")


def _parse_overrides() -> dict[str, dict]:
    """解析 settings.ai_task_overrides_json；失败 → log warning + 返回 {}。"""
    raw = settings.ai_task_overrides_json or ""
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning("ai_task_overrides_json parse failed, falling back to tier defaults: %s", e)
        return {}
    if not isinstance(parsed, dict):
        log.warning("ai_task_overrides_json not a JSON object, ignored")
        return {}
    return parsed


def resolve(task_type: str) -> ResolvedRoute:
    """task_type → ResolvedRoute（含 override 解析）.

    Override 命中规则：task_type 在 overrides 字典内 AND override["model"] 非空 →
    使用 override 全部字段；否则走 tier 默认 + 无 base_url + settings.openai_api_key + 无自定义 cost。
    """
    tier = resolve_tier(task_type)
    overrides = _parse_overrides()
    entry = overrides.get(task_type) or {}

    model_override = (entry.get("model") or "").strip()
    if model_override:
        model = model_override
        base_url = (entry.get("base_url") or "").strip() or None
        api_key = (entry.get("api_key") or "").strip() or settings.openai_api_key
        in_cost = entry.get("input_cost_per_1m")
        out_cost = entry.get("output_cost_per_1m")
        custom_input_cost = float(in_cost) if isinstance(in_cost, (int, float)) else None
        custom_output_cost = float(out_cost) if isinstance(out_cost, (int, float)) else None
    else:
        model = resolve_model(tier)
        base_url = None
        api_key = settings.openai_api_key
        custom_input_cost = None
        custom_output_cost = None

    return ResolvedRoute(
        tier=tier,
        model=model,
        base_url=base_url,
        api_key=api_key,
        custom_input_cost=custom_input_cost,
        custom_output_cost=custom_output_cost,
    )
```

**Breaking change**：`resolve()` 返回类型从 `tuple[str, str]` → `ResolvedRoute`。`gateway.py` 与 `test_ai_core_modules_f208b.py` 中 `resolve()` 解构调用必须改写。**仅此 1 处生产 caller**（grep 验证），改动范围明确可控。

#### C. gateway.py 透传 + cost 注入（第 3 文件）

修订 `_call_litellm` 签名 + 加入 register_model 一次性注入 hook。

```python
import logging
from threading import Lock
from app.ai.routing import ResolvedRoute, resolve

log = logging.getLogger(__name__)

_REGISTERED_COSTS: dict[str, tuple[float, float]] = {}  # model_id → (input_cost, output_cost)
_REGISTER_LOCK = Lock()


def _ensure_cost_registered(model: str, in_cost_per_1m: float | None, out_cost_per_1m: float | None) -> None:
    """Lazy register_model 注入：仅当 override 提供自定义 cost 时调用一次。

    LiteLLM 的 register_model 接受 input_cost_per_token / output_cost_per_token（注意单位是 per-token）。
    我们存的是 per-1M-token，需要 / 1_000_000。

    线程安全：使用 module-level dict + lock，确保同一 (model, cost-pair) 只 register 一次；
    如果 cost 变了（例如 .env 改后重启），新值会覆盖旧值。
    """
    if in_cost_per_1m is None and out_cost_per_1m is None:
        return
    with _REGISTER_LOCK:
        in_per_token = (in_cost_per_1m or 0.0) / 1_000_000.0
        out_per_token = (out_cost_per_1m or 0.0) / 1_000_000.0
        existing = _REGISTERED_COSTS.get(model)
        if existing == (in_per_token, out_per_token):
            return
        import litellm  # noqa: PLC0415
        try:
            litellm.register_model({
                model: {
                    "input_cost_per_token": in_per_token,
                    "output_cost_per_token": out_per_token,
                }
            })
            _REGISTERED_COSTS[model] = (in_per_token, out_per_token)
        except Exception as e:
            log.warning("litellm.register_model failed for %s: %s (continuing with built-in pricing)", model, e)


def _call_litellm(
    route: ResolvedRoute,
    input_dict: dict[str, Any],
    output_schema: type,
) -> tuple[dict[str, Any], int, int, Decimal]:
    import litellm  # noqa: PLC0415

    _ensure_cost_registered(route.model, route.custom_input_cost, route.custom_output_cost)

    try:
        response = litellm.completion(
            model=route.model,
            messages=[{"role": "user", "content": json.dumps(input_dict)}],
            response_format=output_schema,
            api_key=route.api_key or None,
            api_base=route.base_url,  # None → litellm uses default
        )
    except Exception as e:
        raise AiProviderError(str(e)) from e

    # ... 其余 content / tokens / cost 解析与现有完全一致
```

`AiGateway.run` 内的 `tier, model_id = resolve(task_type)` 改为 `route = resolve(task_type)`，下游 `tier=route.tier`、`model_id=route.model`、`_call_litellm(route, ...)`。

⚠️ **context7 强制查询点**（Generator 阶段执行）：
- `litellm.register_model` 当前签名（input_cost_per_token vs input_cost_per_1m）
- `litellm.completion` 的 `api_base` 参数命名（一些版本是 `base_url`）
- `litellm.completion_cost(response, model=...)` 是否会自动读取 register_model 注入的价

#### D. 测试（第 4 文件）

`backend/tests/test_ai_routing_overrides.py`（新建）：

| # | 测试 | 验证 |
|---|------|------|
| 1 | `test_resolve_no_override_falls_back_to_tier_defaults` | 空 JSON → ResolvedRoute.model = settings.ai_model_default/critical/complex 对应；base_url/cost None；api_key = settings.openai_api_key |
| 2 | `test_resolve_override_full_entry_returns_all_fields` | 完整 override → 5 字段全透传 |
| 3 | `test_resolve_override_partial_entry_only_model` | 仅有 model → base_url=None, api_key fallback 到 settings.openai_api_key, cost None |
| 4 | `test_resolve_override_empty_model_falls_back_to_tier` | model="" → 走 tier 兜底 |
| 5 | `test_resolve_override_invalid_json_logs_warning_and_falls_back` | JSON 损坏 → log warning + 全 task 走 tier |
| 6 | `test_resolve_override_non_dict_json_falls_back` | JSON 是 array/string → log warning + fallback |
| 7 | `test_resolve_override_for_unmapped_task_type` | override 提供未知 task_type → resolve_tier 仍抛 ValueError（不可静默接受陌生 task） |
| 8 | `test_resolve_override_cost_zero_treated_as_explicit` | input_cost=0.0 / output_cost=0.0 → custom_*_cost=0.0（用于本地模型显式标 0） |
| 9 | `test_resolve_override_cost_string_ignored` | 误填 "3.0" 字符串 → 视为 None（类型严格） |
| 10 | `test_ensure_cost_registered_calls_litellm_once_per_model` | 用 monkeypatch 替换 litellm.register_model；连续 3 次相同 (model, cost) 只 call 1 次；cost 变化触发再注册 |
| 11 | `test_ensure_cost_registered_skipped_when_both_costs_none` | cost 都 None → 不调 register_model |
| 12 | `test_ensure_cost_registered_swallows_register_failure` | mock register_model raise → 不抛，仅 warning |
| 13 | `test_resolve_unknown_task_type_raises` | resolve("garbage") → ValueError（保留 a1 既有约束）|

测试间共享 fixture：`monkeypatch.setattr(settings, "ai_task_overrides_json", json_str)` + `_REGISTERED_COSTS.clear()` autouse。

#### E. test_ai_gateway_e2e_f208c.py 追加（不计入 5 文件）

追加 1 个 e2e 测试 **C13c**：

```python
def test_gateway_passes_override_api_base_and_cost_uses_registered_price(...):
    """配置 news_summarizer override，调 gateway.run；
    断言 monkeypatched litellm.completion 收到 api_base=override.base_url；
    断言 ai_memos 行的 cost_usd 等于 register_model 注入价 × token 数。"""
```

#### F. test_ai_core_modules_f208b.py 适配（不计入 5 文件）

`test_resolve_returns_tier_and_model` 改为：

```python
def test_resolve_returns_route_dataclass(...):
    route = resolve("market_narrator")
    assert route.tier == "default"
    assert route.model == settings.ai_model_default
    assert route.base_url is None
    assert route.api_key == settings.openai_api_key
    assert route.custom_input_cost is None
```

`resolve_tier` / `resolve_model` 签名不变，相关测试零改动。

#### G. DECISIONS.md（第 5 文件）

追加 D075，D064 兄弟决策。模板：

```markdown
## D075：F211-a2 per-task model override（D064 增量）

**日期**：2026-04-28
**触发**：F211 三 task 实际调用中，`news_summarizer`（长上下文）/ `journal_assistant` monthly（推理密集）/ `candidate_ranker`（高频）希望脱离三 tier 单端点，按 task 切到不同 provider/cost。

**决策**：
1. 新 .env 字段 `AI_TASK_OVERRIDES_JSON`，单 JSON dict，key = task_type，value = `{model, base_url?, api_key?, input_cost_per_1m?, output_cost_per_1m?}`。
2. `routing.resolve()` 签名升级为返回 `ResolvedRoute` dataclass；override 命中（model 非空）→ 全字段透传；否则走 D064 三 tier 兜底。`resolve_tier` / `resolve_model` 旧 API 保留，零回归。
3. `gateway._call_litellm` 透传 `api_base` 给 LiteLLM；首次见到含自定义 cost 的 model id 时调 `litellm.register_model({model: {input_cost_per_token, output_cost_per_token}})` 注入价；同一 (model, cost) 仅注册一次（线程安全 module-level dict）。
4. JSON 解析失败、非 dict、register_model 失败：**log warning，整体 fallback 到 tier 默认**，不抛异常 — fail-soft 优先于 fail-fast，保证现有 .env 用户零感知。

**放弃**：
- 方案 B：每 task 独立 6 个 .env 变量（如 `AI_NEWS_MODEL` / `AI_NEWS_BASE_URL` …）。放弃原因：7 task × 5 字段 = 35 个变量，污染 .env，增 task 时还要改 Settings 类。
- 方案 C：admin endpoint + UI 切 model。放弃原因：个人投资工具定位，重启 backend 改 .env 已足够；增 endpoint 反而引入鉴权 / 审计成本。
- 方案 D：把 override 写进 `cockpit_params.py`。放弃原因：违反 D070 line 1527（AI 模型走 .env 不进 cockpit_params.py）。

**影响**：
- `backend/app/config.py` 增 `ai_task_overrides_json: str = ""`
- `backend/app/ai/routing.py` 新 `ResolvedRoute` dataclass + `_parse_overrides` + `resolve()` 新签名
- `backend/app/ai/gateway.py` `_call_litellm` 透传 `api_base`；新 `_ensure_cost_registered` lazy hook
- `.env.example` 追加 `AI_TASK_OVERRIDES_JSON=` 注释行（非测试关注点，列入开发顺序步骤 1）
- D064 段落不需要重写，本 D075 作为增量决策

**未来扩展点**：
- 若需要支持 LiteLLM Router 多模型 fallback，扩展 `ResolvedRoute` 加 `fallbacks: list[str]` 字段，gateway 改用 `litellm.Router.completion`。本 sprint 不做。
```

### 1.2 设计决定（写在这里以避免 Generator 阶段反复）

1. **register_model 注入位置**：选 gateway lazy hook（`_ensure_cost_registered`），**不**放 main.py lifespan。
   - 理由：lifespan 会在 settings 还没解析完前执行；并且 register_model 是模块全局副作用，靠近调用点便于 mock 测试；与 litellm 模块本身的 lazy-import 风格一致。
2. **api_key fallback 顺序**：`override.api_key` 非空 → 用之；否则用 `settings.openai_api_key`。
   - 理由：保证未配 override 的 task 行为零变化；保证只配 model + base_url 的 override（同一个 OpenAI 兼容端点换 model）能复用 OPENAI_API_KEY，免重复填。
3. **cost 单位**：.env 用户填 per-1M-token（直观），routing dataclass 也用 per-1M；register_model 调用前 `/1_000_000` 转换。
   - 理由：LiteLLM 文档 / OpenAI 价格表都用 per-1M 报价；per-token 是 LiteLLM 内部细节，不应让用户感知。
4. **fail-soft vs fail-fast**：JSON 损坏 → fallback；register_model 失败 → fallback；**不**抛 startup error。
   - 理由："投资工具不能因为 AI override 配错就启动失败"。但**单 entry 字段错误**（如缺 model）已在 resolve 内通过 `model_override` 检查处理为 fallback，符合"配错最差等于没配"。
5. **不做 Provider 鉴权预校验**：override 的 `api_key` 不提前 ping provider 验证。
   - 理由：startup 不依赖网络；首次调 LiteLLM 时如果 key 错会抛 AiProviderError，由 gateway 既有错误路径返回 502。

### 1.3 排除（明确不做，留给后续 sprint）

- ❌ 不引入 LiteLLM Router 多模型 fallback（需要时另起 sprint，本 sprint 单一 model_id 即可）
- ❌ 不做 admin UI / endpoint
- ❌ 不改 `ai_memos` 表（model_used 列已经能审计任何模型 id）
- ❌ 不改 endpoint POST /api/ai/{task_type} 的请求/响应 schema
- ❌ 不为 override 写 startup ping / 健康检查
- ❌ 不在前端展示当前 task 走的是 override 还是 tier（meta.modelUsed 已能区分；F211-c 摘要 bar 会展示）
- ❌ 不做单 entry 字段级容错（缺 model 字段就 fallback 是预期；不再做更细粒度部分容错）
- ❌ 不动 F211-a1 已落地的 schema / guardrail / REGISTRY

---

## 2. 预计修改文件清单（共 5 个，符合 6 文件上限）

```
backend/app/config.py                       (修改 +1 字段)
backend/app/ai/routing.py                   (修改 +ResolvedRoute / _parse_overrides / resolve 新签名；保留 resolve_tier / resolve_model)
backend/app/ai/gateway.py                   (修改 _call_litellm 签名 + _ensure_cost_registered hook + AiGateway.run 调用方式)
backend/tests/test_ai_routing_overrides.py  (新建 ~13 用例)
docs/系统设计/DECISIONS.md                  (追加 D075)
```

测试扩展（不计入 5 文件上限，与 F211-a1 同处理方式）：
- `backend/tests/test_ai_core_modules_f208b.py`：1 处适配（resolve 返回值改 dataclass）
- `backend/tests/test_ai_gateway_e2e_f208c.py`：追加 C13c（override e2e）

文档级附带（不计入）：
- `.env.example` 追加注释行 `# AI_TASK_OVERRIDES_JSON='{...}'`（开发顺序步骤 1 顺手做）

---

## 3. 完成标准（每条可测试）

| C# | 标准 | 测试层级 | 工具 |
|----|------|---------|------|
| C1 | `Settings.ai_task_overrides_json` 字段存在，默认 `""` | 单元 | `pytest tests/test_ai_routing_overrides.py::test_settings_has_overrides_field` |
| C2 | `ResolvedRoute` dataclass 含 6 字段（tier/model/base_url/api_key/custom_input_cost/custom_output_cost），frozen | 单元 | dataclass 字段 + frozen 校验 |
| C3 | 空 JSON → fallback 到 tier；ResolvedRoute 字段语义正确（base_url None / api_key=settings.openai_api_key） | 单元 | test 1 |
| C4 | 完整 override → 全字段透传（model/base_url/api_key/cost） | 单元 | test 2 |
| C5 | 部分 override（仅 model）→ base_url None / api_key fallback / cost None | 单元 | test 3 |
| C6 | model="" → fallback 到 tier | 单元 | test 4 |
| C7 | JSON 损坏 → log warning + fallback；register 计数器为 0 | 单元 | test 5（`caplog` 断言 WARNING level） |
| C8 | JSON 顶层非 dict（array/string）→ log warning + fallback | 单元 | test 6 |
| C9 | resolve("unknown_task") 仍抛 ValueError | 单元 | test 13 |
| C10 | cost=0.0 视为显式（custom_*_cost=0.0 而非 None） | 单元 | test 8 |
| C11 | cost=字符串 "3.0" → custom_*_cost=None（类型严格） | 单元 | test 9 |
| C12 | `_ensure_cost_registered` 同 (model, cost) 只调 litellm.register_model 1 次 | 单元 | test 10（monkeypatch litellm.register_model，断言 call_count） |
| C13 | cost 都 None → 不调 register_model | 单元 | test 11 |
| C14 | register_model 抛异常 → 不传播，仅 warning | 单元 | test 12 |
| C15 | gateway e2e（C13c）：override 配置下 litellm.completion 收到 `api_base=override.base_url`；ai_memos 写入的 `model_used` = override.model；写入的 `cost_usd` 等于 register_model 注入价 × token | 集成 | `test_ai_gateway_e2e_f208c.py::test_override_path_passes_api_base_and_cost` |
| C16 | 现有 877 测试零回归（含 test_ai_core_modules_f208b 适配后） | 回归 | `pytest backend/tests` 全绿 |
| C17 | mypy 全绿（backend/app/config.py + backend/app/ai/routing.py + backend/app/ai/gateway.py + 新测试文件） | 静态 | `mypy --no-incremental backend/app/config.py backend/app/ai/routing.py backend/app/ai/gateway.py` |
| C18 | smoke：`python -c "from app.ai.routing import resolve, ResolvedRoute; r=resolve('news_summarizer'); print(r)"` 输出 ResolvedRoute(...) 且不抛 | 烟囱 | 手动 |
| C19 | features.json#F211 sub_sprints["F211-a2"] 由 `design_needed` → `done`；iteration_history 追加 a2 一条；C1 invariant 检查（a1+a2 done，b/c/d 仍 design_needed → 父 feature **保持** in_progress 不升 done） | 元 | consistency-check skill (mode=interactive) |

### 全通过 → phase 升 needs_review，调用 consistency-check (mode=interactive) 验 C1/C4/C5

---

## 4. 开发顺序（Generator 模式严格执行）

1. **依赖 / 环境准备（不写代码）**
   - context7 查 `/websites/litellm`：
     - `litellm.completion(api_base=...)` 形参名（一些版本叫 `base_url`，需对齐当前 pyproject pin 的 `>=1.83,<2.0`）
     - `litellm.register_model({...})` 当前签名 + 是否仍走 `input_cost_per_token` / `output_cost_per_token`
     - `litellm.completion_cost(response, model=...)` 是否优先使用 register_model 注入的 pricing 而非内置
   - 把上述查询结论写入 commit message，如形参实为 `base_url` 而非 `api_base`，调整 §1 代码草案
2. **config.py 加字段** → `pytest backend/tests/test_ai_routing_overrides.py::test_settings_has_overrides_field` 单测先过（红→绿）→ wip commit
3. **routing.py 改签名 + override 解析** → 跑全部 13 个 routing override 测试 → wip commit
4. **`.env.example` 加注释行** → 顺手 wip commit
5. **gateway.py `_ensure_cost_registered` + `_call_litellm` 透传 + `AiGateway.run` 调用方式** → 跑 test_ai_gateway_e2e_f208c.py（含新 C13c）+ test_ai_routing_overrides.py（10/11/12 三 register 测试） → wip commit
6. **test_ai_core_modules_f208b.py 适配 resolve 返回值** → 全量回归 `pytest backend/tests` → wip commit
7. **DECISIONS.md 追加 D075** → wip commit
8. **mypy 全绿 + smoke** → 进 Evaluator 模式

⚠️ 6 文件原则铁律：本 sprint 5 文件 + 2 测试文件追加，符合上限。

⚠️ 步骤 1 context7 查询若发现 LiteLLM API 与本 contract 草案不符（如形参名不同、register_model 签名变了），**停下来**，更新 contract §1.1 设计后再继续，并把分歧写入 D075 决策记录。

---

## 5. Evaluator 自检清单

### 5.1 测试通过性
- [ ] 13 个 routing override 单元测试全绿
- [ ] C13c gateway e2e 测试（override 路径）通过
- [ ] test_ai_core_modules_f208b 适配后通过
- [ ] 全量回归：`pytest backend/tests` 应 ≥ 878 passed（877 baseline + 14 新增 - 0 删除）

### 5.2 代码质量
- [ ] routing.py + gateway.py + config.py mypy 全绿
- [ ] 无 `print` 调试残留（用 logger）
- [ ] `_REGISTERED_COSTS` / `_REGISTER_LOCK` 模块级 state 有清理 fixture（autouse `_REGISTERED_COSTS.clear()`），避免测试间污染
- [ ] `_ensure_cost_registered` 未引入新 import 在模块顶层（保持 litellm 的 lazy import 模式）
- [ ] log.warning 用 `%s` 占位符而非 f-string

### 5.3 合约/文档同步
- [ ] DECISIONS.md D075 已追加，引用 D064 / D069 / D070
- [ ] `.env.example` 已加 `AI_TASK_OVERRIDES_JSON=` 注释行
- [ ] features.json#F211 sub_sprints["F211-a2"] = "done"
- [ ] features.json#F211 iteration_history 追加 a2 一条

### 5.4 行为正确性
- [ ] 不配 override 时跑既有 test_ai_gateway_e2e_f208c 全部场景行为完全等价
- [ ] override 命中时 ai_memos.cost_usd ≠ 内置 pricing 计算值（证明 register_model 生效）
- [ ] override 损坏 JSON 时 backend 仍能 startup 并跑通 default tier 调用（fail-soft）

### 5.5 consistency-check
- [ ] mode=interactive 通过 C1（父 feature 仍 in_progress，因 b/c/d 未完）
- [ ] C4 iteration_history 含 a2 entry
- [ ] C5 sub_sprints["F211-a2"] 与本 contract 文件存在双向一致

---

## 6. 开放问题（暂未决，标默认采）

| Q# | 问题 | 默认采 | 决策时机 |
|----|------|--------|---------|
| Q1 | LiteLLM 现行版本 `completion()` 形参是 `api_base` 还是 `base_url`？ | 暂按 `api_base`（与 D064 验证版一致），Generator 步骤 1 context7 验证后调整 | 步骤 1 |
| Q2 | `register_model` 注入 cost 后，`completion_cost(response, model=...)` 是否真的会用注入价？若不会需手算 cost = (tokens_in × in_cost + tokens_out × out_cost) / 1M | Generator 步骤 1 context7 验证；若不行则 fallback 到手算（gateway.py 加 5 行计算逻辑） | 步骤 1 |
| Q3 | 是否需要支持 override 提供 `extra_headers` / `timeout` / `max_retries`？ | 不支持。本 sprint 仅 5 字段。需要时另起 a3 sprint | — |
| Q4 | _REGISTERED_COSTS 是否需要支持运行时清除（用于测试以外的场景，如热重载 .env）？ | 不支持。改 .env 后用户重启 backend 即可。autouse fixture 仅清测试用 | — |
| Q5 | override 的 task_type 是否要校验属于 `known_task_types()`？例如填了 "garbage_task" → 是否 startup warning？ | 不校验。`resolve("garbage_task")` 已有 ValueError 兜底（test 13）；不在 startup 增校验避免破坏 fail-soft | — |
| Q6 | `cost_usd` 写入精度：register_model 用 float per-token 后 LiteLLM 返回的可能是科学计数法 float，转 Decimal 需要 quantize 吗？ | 沿用现有逻辑 `Decimal(str(litellm.completion_cost(...)))`，不额外 quantize；ai_memos 列定义的 NUMERIC 精度兜底 | — |
| Q7 | 是否需要在 gateway 返回 meta 增 `route_source: "tier"\|"override"`？让前端 F211-c 摘要 bar 区分？ | 不增。`meta.modelUsed` 已能区分（override 走 anthropic/... 等非 tier 默认 model id），无需新字段污染 API-CONTRACT | — |

⚠️ Generator 阶段如果 Q1/Q2 context7 查询结果与默认采不符，必须停下来更新 D075 决策再继续。

---

## 7. 风险

| 风险 | 等级 | 影响 | 缓解 |
|------|------|------|------|
| LiteLLM `register_model` 在 1.83 版本签名/行为与训练数据不符 | 中 | cost 计算错 / 调用形态变 | Generator 步骤 1 context7 强制验证；不符则更新 D075 + 调整 §1 代码 |
| `resolve()` 签名 breaking 影响未发现的隐式 caller | 低 | 编译/测试失败 | grep 已确认仅 1 处生产 caller（gateway.py）+ 4 个测试文件；mypy 步骤会暴露遗漏 |
| `_REGISTERED_COSTS` 模块级状态在多 worker（uvicorn --workers N）下每 worker 独立 register | 低 | 重复 register（无害，幂等） | LiteLLM register_model 幂等，重复无副作用；不在本 sprint 处理跨进程同步 |
| 用户 .env 配错（model 写错 provider prefix），override 命中但 LiteLLM 调用失败 | 中 | 该 task 502 / AiProviderError | 现有 gateway 错误路径已正确返回；不增 startup 验证（fail-soft 原则） |
| api_base override 指向 OpenAI 不兼容端点，response_format=Pydantic 失效 | 中 | AiSchemaError | gateway step 8 secondary 校验已兜底；用户配置文档（D075 影响段）需提示"端点必须 OpenAI-compatible 且支持 response_format" |
| context7 查询失败 / 网络不通 | 低 | Generator 步骤 1 阻塞 | 兜底：基于训练数据按 §1 草案实现，但**必须**在 D075 标注"未通过 context7 验证"，并在 Generator 完成后用 smoke test 实际跑一次（无 override 场景，验证 LiteLLM 形参名没破回归） |

---

## 8. 用户确认点

确认 Contract 后我会：
1. 更新 features.json：F211-a2 sub_sprint 由 `design_needed` 升 `contract_agreed`；记录 `contract_agreed_at: 2026-04-28`；append 一条 iteration_history（subtask=F211-a2, phase=contract_agreed）
2. 更新 claude-progress.txt（追加 F211-a2 Contract 协商完成记录）
3. 生成新 SESSION-HANDOFF.md（覆盖上一份；保留 F206-c2 待办；新增 F211-a2 Generator 入口指令）
4. **强制停止本 session**，建议你在新 session 开 Sonnet 进入 Generator 模式，粘贴指令：
   ```
   继续开发 F211-a2，Sprint Contract 已确认。
   读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F211-a2-contract.md，
   进入 Generator 模式，从开发步骤 1（context7 查 LiteLLM）开始。
   ```

不在同一 session 中继续进入 Generator 模式（feature-dev 规则）。
