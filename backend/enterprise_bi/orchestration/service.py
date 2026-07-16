"""OrchestrationService — the entrypoint the HTTP route calls.

Wraps one graph invocation with the cross-cutting concerns that don't belong in a
node: request-context binding, wall-clock timing (EXECUTION_MS), optional report
export (Excel/PDF/CSV when the user asked), and the AUDIT_LOG write that must
happen for every turn regardless of outcome. The graph is compiled once in
``__post_init__`` (unless one is injected for tests) — mirroring the reference
platform's build-once composition.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from bi_auth import Identity, RbacPolicy
from bi_base import bind_request, get_logger, stopwatch
from bi_data import AuditEntry, AuditLogWriter

from enterprise_bi.orchestration.builder import build_graph
from enterprise_bi.orchestration.deps import GraphDeps
from enterprise_bi.orchestration.state import BIState

log = get_logger(__name__)


@dataclass
class OrchestrationService:
    deps: GraphDeps
    rbac: RbacPolicy
    audit: AuditLogWriter | None = None
    export_dir: str = "exports"
    graph: object | None = None
    _compiled: object = field(init=False, default=None)

    def __post_init__(self) -> None:
        self._compiled = self.graph or build_graph(self.deps)

    def handle_turn(
        self,
        *,
        question: str,
        identity: Identity,
        request_id: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict:
        bind_request(request_id, user_id=identity.user_id)
        allowed = sorted(self.rbac.allowed_tables(identity.role))
        initial: BIState = {
            "request_id": request_id,
            "question": question,
            "user_id": identity.user_id,
            "username": identity.username,
            "role": identity.role.value,
            "allowed_tables": allowed,
            "history": history or [],
            "status": "OK",
        }

        with stopwatch() as elapsed:
            final: BIState = self._compiled.invoke(initial)  # type: ignore[union-attr]
        final["execution_ms"] = elapsed.ms

        export = self._maybe_export(final, request_id)
        response = self._assemble(final, export)
        self._write_audit(final, identity, export)
        return response

    # ── report export ────────────────────────────────────────────────────
    def _maybe_export(self, state: BIState, request_id: str) -> dict | None:
        fmt = state.get("export_format")
        if not fmt or state.get("status") != "OK" or not state.get("rows"):
            return None
        try:
            from bi_reports import Dataset as ReportDataset
            from bi_reports import export

            ds = ReportDataset(
                columns=tuple(state.get("columns", [])),
                rows=tuple(tuple(r) for r in state.get("rows", [])),
            )
            Path(self.export_dir).mkdir(parents=True, exist_ok=True)
            path = str(Path(self.export_dir) / f"report_{request_id}.{_ext(fmt)}")
            result = export(ds, fmt, path, title="Enterprise BI Report")
            return {"format": result.format, "path": result.path, "bytes": result.byte_size}
        except Exception as exc:  # noqa: BLE001 - export must not fail the turn
            log.warning("export.failed", error=str(exc)[:200])
            return {"format": fmt, "error": "export unavailable (missing engine)"}

    # ── response assembly ────────────────────────────────────────────────
    def _assemble(self, state: BIState, export: dict | None) -> dict:
        if state.get("error"):
            return {
                "request_id": state.get("request_id"),
                "status": state.get("status", "ERROR"),
                "error": state["error"],
                "generated_sql": state.get("sql"),
            }
        return {
            "request_id": state.get("request_id"),
            "status": "OK",
            "intent": state.get("intent"),
            "generated_sql": state.get("validated_sql") or state.get("sql"),
            "columns": state.get("columns", []),
            "rows": state.get("rows", []),
            "row_count": state.get("row_count", 0),
            "analytics": state.get("analytics", {}),
            "visualization": state.get("visualization", {}),
            "insight": state.get("insight", {}),
            "export": export,
            "execution_ms": state.get("execution_ms"),
        }

    # ── audit ───────────────────────────────────────────────────────────
    def _write_audit(self, state: BIState, identity: Identity, export: dict | None) -> None:
        if self.audit is None:
            return
        err = state.get("error") or {}
        self.audit.write(
            AuditEntry(
                request_id=state.get("request_id", ""),
                prompt=state.get("question", ""),
                user_id=identity.user_id,
                username=identity.username,
                role_name=identity.role.value,
                generated_sql=state.get("validated_sql") or state.get("sql"),
                intent=(state.get("intent") or {}).get("intent"),
                execution_ms=int(state.get("execution_ms") or 0),
                row_count=state.get("row_count"),
                chart_kind=state.get("chart_kind"),
                report_format=(export or {}).get("format"),
                status=state.get("status", "OK"),
                error_message=err.get("message"),
            )
        )


def _ext(fmt: str) -> str:
    return {"excel": "xlsx", "csv": "csv", "pdf": "pdf"}.get(fmt, "csv")
