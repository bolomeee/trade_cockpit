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
