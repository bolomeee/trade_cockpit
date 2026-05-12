"""Post-validate guardrail framework (D068): registry pattern, default no-op."""
from __future__ import annotations

from typing import Any, Callable

GuardrailHook = Callable[[dict[str, Any], dict[str, Any]], None]
# (input_dict, output_dict) -> None; raise AiGuardrailViolation on violation

_HOOKS: dict[str, GuardrailHook] = {}


def register(task_type: str, hook: GuardrailHook) -> None:
    """Register a guardrail hook for task_type; replaces existing hook."""
    _HOOKS[task_type] = hook


def run(task_type: str, input_dict: dict[str, Any], output_dict: dict[str, Any]) -> None:
    """Invoke the registered hook for task_type, or no-op if not registered."""
    hook = _HOOKS.get(task_type)
    if hook is not None:
        hook(input_dict, output_dict)
