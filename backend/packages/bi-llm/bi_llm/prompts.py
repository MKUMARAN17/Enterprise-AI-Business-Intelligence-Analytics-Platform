"""Prompt management from YAML.

Every agent's prompt (system instructions + versioned template) lives in a YAML
file, not in code — so prompts can be tuned, A/B'd and reviewed without a code
deploy (the "Prompt Management: YAML" requirement). :class:`PromptBuilder` loads
that catalog once and renders a per-task system+user pair, injecting the ``TASK:``
marker the router/completers key on and interpolating ``{placeholders}`` from the
call site.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from bi_base.errors import ConfigError


@dataclass(frozen=True, slots=True)
class RenderedPrompt:
    task: str
    system: str
    user: str
    version: str


class PromptBuilder:
    def __init__(self, catalog: dict):
        self._catalog = catalog or {}

    @classmethod
    def from_yaml(cls, path: str | Path) -> PromptBuilder:
        p = Path(path)
        if not p.exists():
            raise ConfigError(f"prompt catalog not found: {p}")
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        return cls(data.get("tasks", data))

    def render(self, task: str, **variables) -> RenderedPrompt:
        spec = self._catalog.get(task)
        if not spec:
            raise ConfigError(f"no prompt configured for task {task!r}")
        version = str(spec.get("version", "1"))
        system_tmpl = spec.get("system", "")
        user_tmpl = spec.get("user", "{question}")
        # The TASK marker lets provider-agnostic completers/routers dispatch.
        system = f"TASK: {task}\n" + _safe_format(system_tmpl, variables)
        user = _safe_format(user_tmpl, variables)
        return RenderedPrompt(task=task, system=system, user=user, version=version)


def _safe_format(template: str, variables: dict) -> str:
    """Format with tolerance for missing keys (leaves an unknown {x} untouched)."""

    class _Default(dict):
        def __missing__(self, key):  # noqa: D401
            return "{" + key + "}"

    try:
        return template.format_map(_Default(variables))
    except (ValueError, IndexError):
        return template
