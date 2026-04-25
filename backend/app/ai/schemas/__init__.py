"""Task schema registry (F208-c / F209-a): SchemaPair + REGISTRY + task schemas."""
from typing import NamedTuple

from pydantic import BaseModel

from app.ai.schemas import market_narrator as _mn
from app.ai.schemas import setup_explainer as _se
from app.ai import guardrail as _gr


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
    "market_narrator": SchemaPair(_mn.MarketNarratorInput, _mn.MarketNarratorOutput),
    "setup_explainer": SchemaPair(_se.SetupExplainerInput, _se.SetupExplainerOutput),
    # F210/F211 register remaining 5 production task schemas here:
    # "candidate_ranker":      SchemaPair(...),
    # "trade_plan":            SchemaPair(...),
    # "contradiction_detector":SchemaPair(...),
    # "news_summarizer":       SchemaPair(...),
    # "journal_assistant":     SchemaPair(...),
}

# Guardrail hooks — registered as module load side effect (D068)
_gr.register("market_narrator", _mn.guardrail)
_gr.register("setup_explainer", _se.guardrail)


def get_schemas(task_type: str) -> SchemaPair:
    """Return SchemaPair for task_type; raises KeyError if not registered."""
    return REGISTRY[task_type]


def has_schema(task_type: str) -> bool:
    return task_type in REGISTRY
