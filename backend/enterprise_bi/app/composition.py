"""Composition root — builds every real collaborator from Settings.

This is the ONE place that knows how to turn configuration into wired objects:
the LLM router (real providers when keyed, offline otherwise), the schema-RAG
index, the RBAC policy, the read-only query runner, the audit writer, and finally
the compiled :class:`OrchestrationService`. Boot fails fast (``ConfigError``) if a
hard dependency is missing — the process should never come up green without what
it needs to serve a turn.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from bi_auth import JwtValidator, RbacPolicy
from bi_base import ConfigError, get_logger
from bi_data import AuditLogWriter, QueryRunner
from bi_llm import JsonTaskRouter, OfflineCompleter, OpenAICompleter, PromptBuilder, TaskRoute
from bi_schema_rag import SchemaIndex, SchemaRetriever, default_catalog

from enterprise_bi.config.settings import Settings
from enterprise_bi.orchestration.deps import GraphDeps
from enterprise_bi.orchestration.service import OrchestrationService

log = get_logger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else _BACKEND_ROOT / p


def build_router(settings: Settings) -> JsonTaskRouter:
    """Build the JsonTaskRouter. Uses real providers when a key is set for that
    provider; otherwise registers a single OfflineCompleter under every provider
    id so the graph runs deterministically with no spend."""
    prompts = PromptBuilder.from_yaml(_resolve(settings.prompts_path))

    routing = yaml.safe_load(_resolve(settings.llm_routing_path).read_text(encoding="utf-8")) or {}
    routes: dict[str, TaskRoute] = {}
    for task, cfg in (routing.get("routes") or {}).items():
        routes[task] = TaskRoute(
            provider=cfg.get("provider", "offline"),
            model=cfg.get("model", "offline"),
            temperature=float(cfg.get("temperature", 0.0)),
            required_keys=tuple(cfg.get("required_keys", ())),
        )

    completers: dict = {}
    if settings.openai_api_key:
        completers["openai"] = OpenAICompleter(api_key=settings.openai_api_key, model="gpt-4o-mini")
    if settings.gemini_api_key:
        completers["gemini"] = OpenAICompleter(
            api_key=settings.gemini_api_key,
            model="gemini-1.5-pro",
            base_url=settings.gemini_base_url,
        )

    if not completers:
        log.warning("llm.offline_mode", reason="no API key configured; using OfflineCompleter")
        offline = OfflineCompleter()
        providers = {r.provider for r in routes.values()} | {"offline"}
        completers = {p: offline for p in providers}
    else:
        # Fill any provider referenced by a route but not keyed with offline.
        offline = OfflineCompleter()
        for r in routes.values():
            completers.setdefault(r.provider, offline)

    return JsonTaskRouter(completers=completers, routes=routes, prompts=prompts)


def build_retriever() -> SchemaRetriever:
    tables, glossary = default_catalog()
    index = SchemaIndex.build(tables, glossary)
    return SchemaRetriever(index)


def build_validator(settings: Settings) -> JwtValidator | None:
    if settings.jwt_public_key_path:
        pem = _resolve(settings.jwt_public_key_path).read_text(encoding="utf-8")
        return JwtValidator(
            public_key=pem,
            algorithms=["RS256"],
            audience=settings.jwt_audience,
            issuers=settings.jwt_issuers,
        )
    if settings.jwt_secret:
        return JwtValidator(
            secret=settings.jwt_secret,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuers=settings.jwt_issuers,
        )
    return None  # factory mounts a fail-closed AUTH_NOT_CONFIGURED gate


def build_orchestration_service(settings: Settings) -> OrchestrationService:
    if not settings.database_url:
        raise ConfigError("BI_DATABASE_URL is required to build the orchestration service")

    query_runner = QueryRunner.from_url(settings.database_url, default_max_rows=settings.max_rows)
    audit = AuditLogWriter(query_runner.engine)
    deps = GraphDeps(
        router=build_router(settings),
        retriever=build_retriever(),
        rbac=RbacPolicy(),
        query_runner=query_runner,
        max_rows=settings.max_rows,
    )
    log.info("composition.ready", offline_llm=not (settings.openai_api_key or settings.gemini_api_key))
    return OrchestrationService(
        deps=deps,
        rbac=deps.rbac,
        audit=audit,
        export_dir=settings.export_dir,
    )
