"""POST /api/ai/{task_type} unified endpoint (F208-c, D064)."""
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.ai import gateway as ai_gateway_module
from app.ai.errors import (
    AiBudgetExceeded,
    AiGuardrailViolation,
    AiProviderError,
    AiSchemaError,
)
from app.database import get_db
from app.services.watchlist_service import APIError

router = APIRouter(tags=["ai"])

# 7 production task_types — strictly per API-CONTRACT §POST /api/ai/{task_type}
# "echo" is NOT listed here (F208-c internal test task only)
TaskTypeEnum = Literal[
    "market_narrator",
    "setup_explainer",
    "candidate_ranker",
    "trade_plan",
    "contradiction_detector",
    "news_summarizer",
    "journal_assistant",
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
        result = ai_gateway_module.AiGateway(db).run(
            task_type=task_type,
            input_dict=body.input,
            no_cache=body.no_cache,
        )
    except KeyError:
        raise APIError("VALIDATION_ERROR", f"unregistered task_type: {task_type}", 422) from None
    except ValidationError as e:
        raise APIError("VALIDATION_ERROR", str(e), 422) from e
    except AiBudgetExceeded as e:
        raise APIError("AI_BUDGET_EXCEEDED", str(e), 429) from e
    except AiGuardrailViolation as e:
        raise APIError("AI_GUARDRAIL_VIOLATION", str(e), 409) from e
    except AiSchemaError as e:
        raise APIError("AI_SCHEMA_ERROR", str(e), 502) from e
    except AiProviderError as e:
        raise APIError("AI_PROVIDER_ERROR", str(e), 502) from e

    return AiResponse(
        data=AiResponseData(
            memo_id=result.memo_id,
            task_type=result.task_type,
            schema_version=result.schema_version,
            output=result.output,
            meta=AiMeta(
                model_used=result.meta.model_used,
                tier=result.meta.tier,
                tokens_in=result.meta.tokens_in,
                tokens_out=result.meta.tokens_out,
                cost_usd=float(result.meta.cost_usd),
                latency_ms=result.meta.latency_ms,
                cache_hit=result.meta.cache_hit,
            ),
        )
    )
