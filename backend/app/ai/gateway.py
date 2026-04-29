"""AiGateway: orchestrates the full AI request lifecycle (F208-c)."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.ai import guardrail
from app.ai.budget import assert_within_budget
from app.ai.errors import AiProviderError, AiSchemaError
from app.ai.memo_repo import AiMemoRepository, compute_input_hash
from app.ai.routing import ResolvedRoute, resolve
from app.ai.schemas import get_schemas
from app.config import settings


@dataclass(frozen=True)
class GatewayMeta:
    model_used: str
    tier: str
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal
    latency_ms: int
    cache_hit: bool


@dataclass(frozen=True)
class GatewayResult:
    memo_id: int | None
    task_type: str
    schema_version: str
    output: dict[str, Any]
    meta: GatewayMeta


def _call_litellm(
    route: ResolvedRoute,
    input_dict: dict[str, Any],
    output_schema: type,
    system_prompt: str = "",
) -> tuple[dict[str, Any], int, int, Decimal]:
    """Lazy-import litellm and call completion.

    Returns (raw_output_dict, tokens_in, tokens_out, cost_usd).
    Wraps any provider error into AiProviderError.

    Custom cost (D075): if route.custom_input_cost / custom_output_cost are set,
    pass input_cost_per_token / output_cost_per_token directly to litellm.completion()
    so that completion_cost(completion_response=response) uses those values instead
    of built-in pricing. Unit conversion: per-1M-token → per-token (÷ 1_000_000).
    """
    import litellm  # noqa: PLC0415 — intentional lazy import (Contract §3 #13)

    kwargs: dict[str, Any] = {}
    if route.custom_input_cost is not None:
        kwargs["input_cost_per_token"] = route.custom_input_cost / 1_000_000.0
    if route.custom_output_cost is not None:
        kwargs["output_cost_per_token"] = route.custom_output_cost / 1_000_000.0

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": json.dumps(input_dict)})

    try:
        response = litellm.completion(
            model=route.model,
            messages=messages,
            response_format=output_schema,
            api_key=route.api_key or None,
            api_base=route.base_url,  # None → litellm uses provider default
            **kwargs,
        )
    except Exception as e:
        raise AiProviderError(str(e)) from e

    content = response.choices[0].message.content
    if isinstance(content, dict):
        raw: dict[str, Any] = content
    else:
        try:
            raw = json.loads(content)
        except (json.JSONDecodeError, TypeError) as e:
            raise AiProviderError(f"LiteLLM returned non-JSON content: {e}") from e

    tokens_in: int = int(getattr(response.usage, "prompt_tokens", 0) or 0)
    tokens_out: int = int(getattr(response.usage, "completion_tokens", 0) or 0)
    try:
        cost_usd = Decimal(str(litellm.completion_cost(response, model=route.model) or 0))
    except Exception:
        cost_usd = Decimal("0")

    return raw, tokens_in, tokens_out, cost_usd


class AiGateway:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = AiMemoRepository(db)

    def run(
        self,
        *,
        task_type: str,
        input_dict: dict[str, Any],
        no_cache: bool = False,
    ) -> GatewayResult:
        schema_version = settings.ai_schema_version
        ttl_hours = settings.ai_memo_cache_ttl_hours
        t0 = time.monotonic()

        # Step 1: schema lookup — KeyError if unregistered
        pair = get_schemas(task_type)

        # Step 2: validate input (Pydantic ValidationError propagates to caller)
        validated = pair.input_schema(**input_dict)
        validated_dict = validated.model_dump()

        # Step 3: compute canonical hash
        input_hash = compute_input_hash(validated_dict)

        # Step 4: cache lookup (skipped when no_cache=True)
        if not no_cache:
            cached = self._repo.find_cached(
                task_type=task_type,
                input_hash=input_hash,
                schema_version=schema_version,
                ttl_hours=ttl_hours,
            )
            if cached is not None:
                latency_ms = int((time.monotonic() - t0) * 1000)
                return GatewayResult(
                    memo_id=cached.id,
                    task_type=task_type,
                    schema_version=schema_version,
                    output=json.loads(cached.output_json),
                    meta=GatewayMeta(
                        model_used="cache",
                        tier=cached.tier,
                        tokens_in=0,
                        tokens_out=0,
                        cost_usd=Decimal("0"),
                        latency_ms=latency_ms,
                        cache_hit=True,
                    ),
                )

        # Step 5: budget check — raises AiBudgetExceeded if over cap
        assert_within_budget(self._db)

        # Step 6: resolve route (tier + model + override fields, D064 + D075)
        route = resolve(task_type)

        # Step 7: call LiteLLM via lazy-import wrapper
        raw_output, tokens_in, tokens_out, cost_usd = _call_litellm(
            route=route,
            input_dict=validated_dict,
            output_schema=pair.output_schema,
            system_prompt=pair.system_prompt,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        # Step 8: secondary output schema validation (防 LiteLLM response_format 失效)
        try:
            validated_output = pair.output_schema(**raw_output)
        except Exception as e:
            raise AiSchemaError(str(e)) from e
        output_dict = validated_output.model_dump()

        # Step 9: guardrail — raises AiGuardrailViolation if rejected
        guardrail.run(task_type, validated_dict, output_dict)

        # Step 10: write memo (only after guardrail passes — D068 safety principle)
        memo_id = self._repo.write(
            task_type=task_type,
            input_dict=validated_dict,
            output_dict=output_dict,
            schema_version=schema_version,
            model_used=route.model,
            tier=route.tier,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            input_hash=input_hash,
        )

        # Step 11: return result
        return GatewayResult(
            memo_id=memo_id,
            task_type=task_type,
            schema_version=schema_version,
            output=output_dict,
            meta=GatewayMeta(
                model_used=route.model,
                tier=route.tier,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                cache_hit=False,
            ),
        )
