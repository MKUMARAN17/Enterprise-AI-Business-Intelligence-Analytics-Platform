"""One Settings object for the whole app (pydantic-settings).

All configuration comes from the environment (prefix ``BI_``) or a ``.env`` file,
never hard-coded. Boot reads this once at the composition root; anything required
and missing surfaces as a ``ConfigError`` (fail-closed) rather than a half-wired
service. Relative config paths resolve against the backend package root so the
app boots regardless of the process CWD.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BI_", env_file=".env", extra="ignore")

    # ── HTTP / app ────────────────────────────────────────────────────────
    root_path: str = ""
    cors_allowed_origins: list[str] = []
    log_level: str = "INFO"
    json_logs: bool = True

    # ── Auth (JWT) ─────────────────────────────────────────────────────────
    jwt_secret: str = ""                       # HS256 dev secret
    jwt_public_key_path: str = ""              # RS256 PEM (prod)
    jwt_audience: str = "enterprise-bi"
    jwt_issuers: list[str] = ["enterprise-bi-dev"]
    # DEV ONLY: expose POST /api/v1/dev/login to mint a token for a chosen role
    # (HS256, needs jwt_secret). Never enable in production — it is an auth bypass.
    allow_dev_login: bool = False

    # ── Database ─────────────────────────────────────────────────────────
    # Analytical reads (sync). e.g. mysql+pymysql://user:pw@host:3306/ENTERPRISE_BI
    database_url: str = ""
    max_rows: int = 10000

    # ── LLM (bi-llm JsonTaskRouter) ────────────────────────────────────────
    openai_api_key: str = ""
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    # When no key is configured the router uses the deterministic OfflineCompleter.
    llm_routing_path: str = "config/llm_routing.yaml"
    prompts_path: str = "prompts/agent_prompts.yaml"

    # ── Guardrails / RAG / exports ─────────────────────────────────────────
    guardrail_max_length: int = 2000
    export_dir: str = "exports"

    # ── Memory (Redis, for follow-up conversation) ────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    memory_ttl_seconds: int = 3600
