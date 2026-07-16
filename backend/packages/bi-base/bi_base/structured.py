"""JSON-schema structured-output helpers.

The LLM agents are all constrained to return JSON matching a declared schema
(intent classification, SQL plan, insight object). These helpers give every
agent one consistent way to (a) parse a model's raw text into JSON even when it
wraps the object in prose or ```json fences, and (b) shallow-validate the parsed
object against a required-key spec before the orchestrator trusts it. Keeping
this dependency-free (no jsonschema at runtime) keeps the foundation light; the
required-keys check catches the failure mode we actually see — a missing field —
without a full validator.
"""
from __future__ import annotations

import json
import re
from typing import Any

from bi_base.errors import BiError

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


class StructuredOutputError(BiError):
    """The model output could not be coerced into the expected JSON shape."""

    code = "STRUCTURED_OUTPUT_INVALID"
    status_code = 502


def extract_json(text: str) -> dict[str, Any]:
    """Best-effort extraction of a single JSON object from model text.

    Handles three real-world shapes: a bare JSON object, a ```json fenced block,
    and an object embedded in explanatory prose. Raises StructuredOutputError if
    nothing parseable is found.
    """
    if not text or not text.strip():
        raise StructuredOutputError("empty model output")

    candidates: list[str] = []
    fenced = _FENCE_RE.search(text)
    if fenced:
        candidates.append(fenced.group(1))
    candidates.append(text)
    embedded = _OBJ_RE.search(text)
    if embedded:
        candidates.append(embedded.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    raise StructuredOutputError("no JSON object found in model output")


def require_keys(obj: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    """Assert every key in ``keys`` is present; raise otherwise. Returns ``obj``."""
    missing = [k for k in keys if k not in obj]
    if missing:
        raise StructuredOutputError(f"missing required keys: {', '.join(missing)}")
    return obj
