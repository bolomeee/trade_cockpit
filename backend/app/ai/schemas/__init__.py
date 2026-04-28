"""Task schema registry (F208-c / F209-a): SchemaPair + REGISTRY + task schemas."""
from typing import NamedTuple

from pydantic import BaseModel

from app.ai.schemas import candidate_ranker as _cr
from app.ai.schemas import contradiction_detector as _cd
from app.ai.schemas import journal_assistant as _ja
from app.ai.schemas import market_narrator as _mn
from app.ai.schemas import news_summarizer as _ns
from app.ai.schemas import setup_explainer as _se
from app.ai.schemas import trade_plan as _tp
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
    "setup_explainer":   SchemaPair(_se.SetupExplainerInput, _se.SetupExplainerOutput),
    "candidate_ranker":  SchemaPair(_cr.CandidateRankerInput, _cr.CandidateRankerOutput),
    "trade_plan":          SchemaPair(_tp.TradePlanInput, _tp.TradePlanOutput),
    "contradiction_detector": SchemaPair(_cd.ContradictionDetectorInput, _cd.ContradictionDetectorOutput),
    "news_summarizer":        SchemaPair(_ns.NewsSummarizerInput, _ns.NewsSummarizerOutput),
    "journal_assistant":      SchemaPair(_ja.JournalAssistantInput, _ja.JournalAssistantOutput),
}

# Guardrail hooks — registered as module load side effect (D068)
_gr.register("market_narrator", _mn.guardrail)
_gr.register("setup_explainer", _se.guardrail)
_gr.register("trade_plan", _tp.guardrail)
_gr.register("contradiction_detector", _cd.guardrail)
_gr.register("news_summarizer", _ns.guardrail)
_gr.register("journal_assistant", _ja.guardrail)
# candidate_ranker: no deterministic anchor — no guardrail


def get_schemas(task_type: str) -> SchemaPair:
    """Return SchemaPair for task_type; raises KeyError if not registered."""
    return REGISTRY[task_type]


def has_schema(task_type: str) -> bool:
    return task_type in REGISTRY
