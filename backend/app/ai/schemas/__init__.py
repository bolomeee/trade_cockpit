"""Task schema registry (F208-c): SchemaPair + REGISTRY + echo internal task."""
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
    # F209/F210/F211 register 7 production task schemas here:
    # "market_narrator":       SchemaPair(...),
    # "setup_explainer":       SchemaPair(...),
    # "candidate_ranker":      SchemaPair(...),
    # "trade_plan":            SchemaPair(...),
    # "contradiction_detector":SchemaPair(...),
    # "news_summarizer":       SchemaPair(...),
    # "journal_assistant":     SchemaPair(...),
}


def get_schemas(task_type: str) -> SchemaPair:
    """Return SchemaPair for task_type; raises KeyError if not registered."""
    return REGISTRY[task_type]


def has_schema(task_type: str) -> bool:
    return task_type in REGISTRY
