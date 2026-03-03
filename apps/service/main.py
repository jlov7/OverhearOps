from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import shutil
import threading
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, cast

import httpx
import orjson
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from opentelemetry import trace
from pydantic import BaseModel, ConfigDict, Field

from apps.service.adapters.teams_demo import (
    iter_messages as demo_iter_messages,
)
from apps.service.adapters.teams_demo import (
    list_threads as demo_list_threads,
)
from apps.service.adapters.teams_graph import TeamsGraphAdapter
from apps.service.queue_store import (
    claim_next_job,
    complete_job,
    enqueue_job,
    get_job,
    init_queue,
    replayable_failed_jobs,
    requeue_stale_jobs,
)
from apps.service.runtime_config import (
    get_feature_flag,
    get_min_approvals,
    get_policy_rules,
    get_strategy_preset,
    get_token_budgets,
    load_policy_rules,
    load_prompt_registry,
    load_runtime_settings,
    save_policy_rules,
    save_prompt_registry,
    save_runtime_settings,
    set_strategy_preset,
)
from apps.service.storage_codec import resolve_storage_codec
from apps.service.usage_meter import export_usage_records, get_tenant_usage, record_usage
from packages.agentkit.graph import build_graph
from packages.obs.action_graph import build_graphs
from packages.obs.otel import init_otel
from packages.obs.runtime import set_run_context


def _spans_path(run_id: str) -> Path:
    return RUNS / run_id / "spans.jsonl"


def _record_sort_key(item: dict[str, Any]) -> tuple[str, str]:
    attrs = item.get("attributes", {})
    stable_attrs = attrs if isinstance(attrs, dict) else {}
    return (
        str(item.get("name", "")),
        json.dumps(stable_attrs, sort_keys=True, default=str),
    )


def _compute_replay_hash(run_id: str) -> str:
    digest = hashlib.sha256()
    span_file = _spans_path(run_id)
    if not span_file.exists():
        digest.update(run_id.encode("utf-8"))
        return digest.hexdigest()
    records: list[dict[str, Any]] = []
    with span_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            data = json.loads(line)
            attributes = data.get("attributes")
            if not isinstance(attributes, dict):
                attributes = {}
            stable_attrs = {key: attributes[key] for key in sorted(attributes)}
            records.append(
                {
                    "name": str(data.get("name", "")),
                    "attributes": stable_attrs,
                }
            )
    records.sort(key=_record_sort_key)
    for record in records:
        digest.update(json.dumps(record, sort_keys=True, default=str).encode("utf-8"))
    return digest.hexdigest()


def _cors_origins() -> list[str]:
    configured = os.getenv("OVERHEAROPS_CORS_ORIGINS")
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return ["http://localhost:3000", "http://127.0.0.1:3000"]


def _safe_id(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")
    return cleaned or fallback


def _safe_thread_id(thread_id: str) -> str:
    return _safe_id(thread_id, "thread")


def _safe_tenant_id(tenant_id: str) -> str:
    return _safe_id(tenant_id, "default")


def _new_run_id(thread_id: str, tenant_id: str) -> str:
    timestamp_ms = int(time.time() * 1000)
    nonce = uuid.uuid4().hex[:8]
    safe_tenant = _safe_tenant_id(tenant_id)
    return f"{safe_tenant}-{ADAPTER_MODE}-{_safe_thread_id(thread_id)}-{timestamp_ms}-{nonce}"


def _max_thread_events() -> int:
    raw = os.getenv("OVERHEAROPS_MAX_THREAD_EVENTS", "500")
    try:
        return max(1, int(raw))
    except ValueError:
        return 500


def _max_run_status_entries() -> int:
    raw = os.getenv("OVERHEAROPS_MAX_RUN_STATUS", "1000")
    try:
        return max(10, int(raw))
    except ValueError:
        return 1000


def _max_idempotency_entries() -> int:
    raw = os.getenv("OVERHEAROPS_MAX_IDEMPOTENCY", "5000")
    try:
        return max(100, int(raw))
    except ValueError:
        return 5000


def _run_max_runtime_s() -> float:
    raw = os.getenv("OVERHEAROPS_RUN_MAX_RUNTIME_S", "600")
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 600.0


def _queue_enabled() -> bool:
    return os.getenv("OVERHEAROPS_QUEUE_ENABLED", "true").strip().lower() != "false"


def _queue_poll_interval_s() -> float:
    raw = os.getenv("OVERHEAROPS_QUEUE_POLL_INTERVAL_S", "0.2")
    try:
        return max(0.05, float(raw))
    except ValueError:
        return 0.2


def _queue_lease_ms() -> int:
    raw = os.getenv("OVERHEAROPS_QUEUE_LEASE_MS", "60000")
    try:
        return max(1000, int(raw))
    except ValueError:
        return 60000


def _security_mode() -> str:
    raw = os.getenv("OVERHEAROPS_SECURITY_MODE", "off").lower().strip()
    return raw if raw in {"off", "api_key"} else "off"


def _default_tenant() -> str:
    return _safe_tenant_id(os.getenv("OVERHEAROPS_DEFAULT_TENANT", "default"))


def _ingest_hmac_secret() -> str:
    return os.getenv("OVERHEAROPS_INGEST_HMAC_SECRET", "")


def _idempotency_ttl_s() -> int:
    raw = os.getenv("OVERHEAROPS_IDEMPOTENCY_TTL_S", "86400")
    try:
        return max(60, int(raw))
    except ValueError:
        return 86400


def _integration_mode() -> str:
    mode = os.getenv("OVERHEAROPS_INTEGRATION_MODE", "dry_run").strip().lower()
    return mode if mode in {"dry_run", "live"} else "dry_run"


def _require_approval_for_ship() -> bool:
    raw = os.getenv("OVERHEAROPS_REQUIRE_APPROVAL_FOR_SHIP", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"(?i)\bsk-[A-Za-z0-9]{10,}\b"), "[REDACTED_API_KEY]"),
    (
        re.compile(r"(?i)\b(api[_-]?key|token|secret)\s*[:=]\s*([A-Za-z0-9._-]{6,})"),
        r"\1=[REDACTED]",
    ),
)


ROLE_RANK: dict[str, int] = {
    "viewer": 10,
    "operator": 20,
    "approver": 30,
    "admin": 40,
}


TERMINAL_STATUSES: set[str] = {"succeeded", "failed", "cancelled"}


class AuthContext(BaseModel):
    subject: str
    role: str
    tenant_id: str


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        redacted = value
        for pattern, replacement in REDACTION_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_value(item) for key, item in value.items()}
    return value


def _auth_tokens() -> dict[str, AuthContext]:
    raw = os.getenv("OVERHEAROPS_AUTH_TOKENS_JSON", "")
    if not raw.strip():
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("OVERHEAROPS_AUTH_TOKENS_JSON must be a JSON object.")
    tokens: dict[str, AuthContext] = {}
    for token, payload in parsed.items():
        if not isinstance(token, str) or not isinstance(payload, dict):
            continue
        role = str(payload.get("role", "viewer")).strip().lower()
        if role not in ROLE_RANK:
            continue
        tenant_id = _safe_tenant_id(str(payload.get("tenant_id", _default_tenant())))
        subject = str(payload.get("subject", f"user:{token[:8]}"))
        tokens[token] = AuthContext(subject=subject, role=role, tenant_id=tenant_id)
    return tokens


def _resolve_auth_context(
    authorization: str | None,
    tenant_header: str | None,
) -> AuthContext:
    tenant = _safe_tenant_id(tenant_header or _default_tenant())
    if _security_mode() == "off":
        return AuthContext(subject="anonymous", role="admin", tenant_id=tenant)

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer authorization.")
    token = authorization.split(" ", 1)[1].strip()
    tokens = _auth_tokens()
    principal = tokens.get(token)
    if principal is None:
        raise HTTPException(status_code=401, detail="Invalid API token.")
    if principal.role != "admin" and tenant != principal.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant access denied.")
    if principal.role == "admin":
        return AuthContext(subject=principal.subject, role=principal.role, tenant_id=tenant)
    return principal


def _require_role(required_role: str):
    if required_role not in ROLE_RANK:
        raise RuntimeError(f"Unknown role requirement: {required_role}")

    def dependency(
        authorization: str | None = Header(default=None),
        tenant_header: str | None = Header(default=None, alias="X-OverhearOps-Tenant"),
    ) -> AuthContext:
        context = _resolve_auth_context(authorization=authorization, tenant_header=tenant_header)
        if ROLE_RANK[context.role] < ROLE_RANK[required_role]:
            raise HTTPException(status_code=403, detail="Insufficient role.")
        return context

    return dependency


def _validate_ingest_signature(raw_body: bytes, signature: str | None) -> None:
    secret = _ingest_hmac_secret()
    if not secret:
        return
    if not signature:
        raise HTTPException(status_code=401, detail="Missing ingest signature.")
    prefix = "sha256="
    if not signature.startswith(prefix):
        raise HTTPException(status_code=401, detail="Invalid ingest signature format.")
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    provided = signature[len(prefix):]
    if not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=401, detail="Invalid ingest signature.")


ViewerAuth = Annotated[AuthContext, Depends(_require_role("viewer"))]
OperatorAuth = Annotated[AuthContext, Depends(_require_role("operator"))]
ApproverAuth = Annotated[AuthContext, Depends(_require_role("approver"))]
AdminAuth = Annotated[AuthContext, Depends(_require_role("admin"))]


class RunRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=256)
    background: bool = True
    simulate_only: bool = False


class ThreadEventPayload(BaseModel):
    id: str = Field(min_length=1, max_length=256)
    createdDateTime: str = Field(min_length=1, max_length=64)
    model_config = ConfigDict(extra="allow")


class ApprovalRequest(BaseModel):
    note: str = Field(default="", max_length=2048)
    decision: str = Field(default="approve", pattern="^(approve|reject)$")


class DsrDeleteRequest(BaseModel):
    dry_run: bool = True


class SettingsUpdateRequest(BaseModel):
    payload: dict[str, Any]


class AnalyticsEventRequest(BaseModel):
    event: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


BASE = Path(__file__).resolve().parents[2]
RUNS = BASE / "runs"
RUNS.mkdir(exist_ok=True, parents=True)
DLQ = RUNS / "dlq"
DLQ.mkdir(exist_ok=True, parents=True)
ANALYTICS_DIR = RUNS / "analytics"
ANALYTICS_DIR.mkdir(exist_ok=True, parents=True)
QUEUE_DB = BASE / "overhearops_queue.db"
init_queue(QUEUE_DB)

ADAPTER_MODE = os.getenv("ADAPTER", "demo").lower()
_GRAPH_ADAPTER: TeamsGraphAdapter | None = None

PLAYGROUND_PLAN_CARD: dict[str, Any] = {
    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
    "type": "AdaptiveCard",
    "version": "1.5",
    "body": [
        {"type": "TextBlock", "text": "OverhearOps Plan B", "weight": "Bolder", "size": "Medium"},
        {"type": "TextBlock", "text": "Increase timeout to 120s on Windows", "wrap": True},
        {
            "type": "FactSet",
            "facts": [
                {"title": "Confidence", "value": "0.74"},
                {"title": "Estimated cost", "value": "~3.2k tokens"},
                {"title": "Blast radius", "value": "Low"},
            ],
        },
    ],
    "actions": [
        {"type": "Action.Submit", "title": "Ship (dry-run)", "data": {"action": "ship_plan_b"}},
        {"type": "Action.Submit", "title": "Show Diff", "data": {"action": "show_diff"}},
    ],
}


def _graph_adapter() -> TeamsGraphAdapter:
    global _GRAPH_ADAPTER
    if _GRAPH_ADAPTER is None:
        try:
            _GRAPH_ADAPTER = TeamsGraphAdapter()
        except RuntimeError as exc:  # pragma: no cover - exercised via HTTPException
            raise HTTPException(status_code=401, detail=str(exc)) from exc
    return _GRAPH_ADAPTER


def _resolve_graph_targets(thread_id: str) -> tuple[str, str]:
    if ":" in thread_id:
        team_id, channel_id = thread_id.split(":", 1)
        return team_id, channel_id
    return thread_id, thread_id


def _load_thread_messages(thread_id: str) -> list[dict[str, Any]]:
    if ADAPTER_MODE in {"demo", "playground"}:
        try:
            messages = list(demo_iter_messages(thread_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if not messages:
            raise HTTPException(
                status_code=404,
                detail=f"No messages recorded for thread {thread_id}.",
            )
        return messages
    if ADAPTER_MODE == "graph":
        adapter = _graph_adapter()
        team_id, channel_id = _resolve_graph_targets(thread_id)
        messages = list(adapter.list_messages(team_id, channel_id))
        if not messages:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Teams Graph adapter configured but returned no messages; provide valid IDs "
                    "and ensure Graph app permissions and consent are configured."
                ),
            )
        return messages
    raise HTTPException(status_code=400, detail=f"Unknown adapter mode: {ADAPTER_MODE}")


async def iter_messages(thread_id: str) -> AsyncGenerator[dict[str, Any], None]:
    if ADAPTER_MODE == "graph":
        adapter = _graph_adapter()
        for message in adapter.stream_thread(thread_id):
            yield message
        return
    messages = _load_thread_messages(thread_id)
    for message in messages:
        yield message


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    _ensure_dispatcher_started()
    try:
        yield
    finally:
        _stop_dispatcher()


app = FastAPI(title="OverhearOps", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

THREAD_EVENTS: dict[str, list[dict[str, Any]]] = {}
RUN_STATUS: dict[str, dict[str, Any]] = {}
RUN_STATUS_LOCK = threading.Lock()
RUN_EXECUTION_LOCK = threading.Lock()
RUN_THREADS: dict[str, threading.Thread] = {}
RUN_CANCEL_REQUESTS: set[str] = set()
RUN_CANCEL_LOCK = threading.Lock()
IDEMPOTENCY_INDEX: dict[str, dict[str, Any]] = {}
IDEMPOTENCY_LOCK = threading.Lock()
QUEUE_DISPATCHER_THREAD: threading.Thread | None = None
QUEUE_DISPATCHER_LOCK = threading.Lock()
QUEUE_DISPATCHER_STOP = threading.Event()
RUN_NOTIFICATION_SENT: set[str] = set()
RUN_NOTIFICATION_LOCK = threading.Lock()

TRACER = init_otel("overhearops")
GRAPH = build_graph(db_url=os.getenv("OVERHEAROPS_DB", "overhearops.db"))
STORAGE_CODEC = resolve_storage_codec()


def _event_store_key(tenant_id: str, thread_id: str) -> str:
    safe_tenant = _safe_tenant_id(tenant_id)
    return thread_id if safe_tenant == _default_tenant() else f"{safe_tenant}:{thread_id}"


def _run_audit_path(run_id: str) -> Path:
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir / "audit.log"


def _run_approval_path(run_id: str) -> Path:
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir / "approval.json"


def _load_run_approval(run_id: str) -> dict[str, Any] | None:
    path = _run_approval_path(run_id)
    if not path.exists():
        return None
    return STORAGE_CODEC.read_json(path)


def _run_approvals_path(run_id: str) -> Path:
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir / "approvals.json"


def _load_run_approvals(run_id: str) -> list[dict[str, Any]]:
    path = _run_approvals_path(run_id)
    if not path.exists():
        legacy = _load_run_approval(run_id)
        return [legacy] if legacy else []
    payload = STORAGE_CODEC.read_json(path)
    items = payload.get("items", [])
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _store_run_approvals(run_id: str, items: list[dict[str, Any]]) -> None:
    STORAGE_CODEC.write_json(
        _run_approvals_path(run_id),
        {
            "run_id": run_id,
            "items": items,
            "updated_at_ms": int(time.time() * 1000),
        },
    )


def _run_token_cost(graphs: dict[str, Any]) -> int:
    action_graph = graphs.get("action_graph", {})
    nodes = action_graph.get("nodes", []) if isinstance(action_graph, dict) else []
    if not isinstance(nodes, list):
        return 0
    total = 0
    for node in nodes:
        if not isinstance(node, dict):
            continue
        attrs = node.get("attrs", {})
        if not isinstance(attrs, dict):
            continue
        inbound = attrs.get("token.approx_in", 0)
        outbound = attrs.get("token.approx_out", 0)
        try:
            total += max(0, int(inbound)) + max(0, int(outbound))
        except (TypeError, ValueError):
            continue
    return total


def _tenant_budget_exhausted(tenant_id: str) -> tuple[bool, dict[str, Any]]:
    _, per_tenant_budget = get_token_budgets()
    usage = get_tenant_usage(_safe_tenant_id(tenant_id))
    used_tokens = int(usage.get("used_tokens", 0))
    exhausted = used_tokens >= per_tenant_budget
    return exhausted, {
        "used_tokens": used_tokens,
        "per_tenant_budget": per_tenant_budget,
        "remaining_tokens": max(0, per_tenant_budget - used_tokens),
    }


def _can_notify_run(run_id: str) -> bool:
    with RUN_NOTIFICATION_LOCK:
        if run_id in RUN_NOTIFICATION_SENT:
            return False
        RUN_NOTIFICATION_SENT.add(run_id)
        return True


def _notify_run_terminal(run_id: str, tenant_id: str, payload: dict[str, Any]) -> None:
    if not get_feature_flag("notifications_enabled", default=False):
        return
    if not _can_notify_run(run_id):
        return
    settings = load_runtime_settings()
    notifications = settings.get("notifications", {})
    if not isinstance(notifications, dict):
        return
    webhooks_raw = notifications.get("webhooks", [])
    teams_raw = notifications.get("teams_webhooks", [])
    targets: list[str] = []
    if isinstance(webhooks_raw, list):
        targets.extend(str(item).strip() for item in webhooks_raw if str(item).strip())
    if isinstance(teams_raw, list):
        targets.extend(str(item).strip() for item in teams_raw if str(item).strip())
    if not targets:
        return
    body = {
        "event": "run_terminal",
        "run_id": run_id,
        "tenant_id": _safe_tenant_id(tenant_id),
        "status": payload.get("status"),
        "thread_id": payload.get("thread_id"),
        "error": payload.get("error", ""),
    }
    for target in targets:
        try:
            with httpx.Client(timeout=3.0) as client:
                client.post(target, json=body)
        except httpx.HTTPError:
            continue


def _run_summary(run_id: str, tenant_id: str) -> dict[str, Any] | None:
    status = _get_run_status(run_id=run_id, tenant_id=tenant_id)
    if not status:
        return None
    artefact_path = RUNS / run_id / "artefacts.json"
    artefact: dict[str, Any] = {}
    if artefact_path.exists():
        artefact = STORAGE_CODEC.read_json(artefact_path)
    verdict = artefact.get("verdict", {}) if isinstance(artefact, dict) else {}
    gate = artefact.get("gate", {}) if isinstance(artefact, dict) else {}
    return {
        "run_id": run_id,
        "thread_id": status.get("thread_id", ""),
        "tenant_id": status.get("tenant_id", ""),
        "status": status.get("status", ""),
        "updated_at_ms": status.get("updated_at_ms", 0),
        "created_at_ms": status.get("created_at_ms", 0),
        "winner_plan_id": (
            verdict.get("winner_plan_id")
            if isinstance(verdict, dict)
            else ""
        ),
        "action": gate.get("action") if isinstance(gate, dict) else "",
        "certainty": gate.get("certainty") if isinstance(gate, dict) else None,
        "replay_hash": artefact.get("replay_hash", "") if isinstance(artefact, dict) else "",
    }


def _audit_event(
    action: str,
    tenant_id: str,
    actor: str,
    run_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    payload = {
        "ts_ms": int(time.time() * 1000),
        "action": action,
        "tenant_id": _safe_tenant_id(tenant_id),
        "actor": actor,
        "run_id": run_id,
        "detail": _redact_value(detail or {}),
    }
    line = json.dumps(payload, sort_keys=True, default=str) + "\n"
    with (RUNS / "audit.log").open("a", encoding="utf-8") as handle:
        handle.write(line)
    if run_id:
        with _run_audit_path(run_id).open("a", encoding="utf-8") as handle:
            handle.write(line)


def _request_cancel(run_id: str) -> None:
    with RUN_CANCEL_LOCK:
        RUN_CANCEL_REQUESTS.add(run_id)


def _clear_cancel(run_id: str) -> None:
    with RUN_CANCEL_LOCK:
        RUN_CANCEL_REQUESTS.discard(run_id)


def _cancel_requested(run_id: str) -> bool:
    with RUN_CANCEL_LOCK:
        return run_id in RUN_CANCEL_REQUESTS


def _prune_idempotency() -> None:
    now_s = int(time.time())
    ttl_s = _idempotency_ttl_s()
    with IDEMPOTENCY_LOCK:
        stale_keys = [
            key
            for key, payload in IDEMPOTENCY_INDEX.items()
            if int(payload.get("created_at_s", now_s)) < now_s - ttl_s
        ]
        for key in stale_keys:
            IDEMPOTENCY_INDEX.pop(key, None)

        max_entries = _max_idempotency_entries()
        if len(IDEMPOTENCY_INDEX) > max_entries:
            oldest = sorted(
                IDEMPOTENCY_INDEX.items(),
                key=lambda item: int(item[1].get("created_at_s", 0)),
            )
            for stale_key, _ in oldest[: len(IDEMPOTENCY_INDEX) - max_entries]:
                IDEMPOTENCY_INDEX.pop(stale_key, None)


def _idempotency_index_key(tenant_id: str, key: str) -> str:
    return f"{_safe_tenant_id(tenant_id)}:{key}"


def _record_idempotency(tenant_id: str, key: str, run_id: str) -> None:
    with IDEMPOTENCY_LOCK:
        IDEMPOTENCY_INDEX[_idempotency_index_key(tenant_id=tenant_id, key=key)] = {
            "run_id": run_id,
            "created_at_s": int(time.time()),
        }


def _find_idempotent_run(tenant_id: str, key: str) -> str | None:
    _prune_idempotency()
    with IDEMPOTENCY_LOCK:
        payload = IDEMPOTENCY_INDEX.get(_idempotency_index_key(tenant_id=tenant_id, key=key))
        if not payload:
            return None
        run_id = payload.get("run_id")
        return str(run_id) if run_id else None


def _run_belongs_to_tenant(record: dict[str, Any], tenant_id: str) -> bool:
    record_tenant = _safe_tenant_id(str(record.get("tenant_id", _default_tenant())))
    return record_tenant == _safe_tenant_id(tenant_id)


def _tenant_run_ids(tenant_id: str) -> list[str]:
    tenant = _safe_tenant_id(tenant_id)
    run_ids: list[str] = []
    for path in RUNS.iterdir():
        if not path.is_dir():
            continue
        status_path = path / "status.json"
        if not status_path.exists():
            continue
        try:
            status = STORAGE_CODEC.read_json(status_path)
        except (json.JSONDecodeError, OSError, RuntimeError, ValueError):
            continue
        status_tenant = _safe_tenant_id(str(status.get("tenant_id", _default_tenant())))
        if status_tenant == tenant:
            run_ids.append(path.name)
    return sorted(run_ids)


def _write_dlq(
    run_id: str,
    thread_id: str,
    tenant_id: str,
    actor: str,
    status: str,
    error: str,
) -> None:
    payload = {
        "run_id": run_id,
        "thread_id": thread_id,
        "tenant_id": _safe_tenant_id(tenant_id),
        "actor": actor,
        "status": status,
        "error": str(_redact_value(error)),
        "created_at_ms": int(time.time() * 1000),
    }
    (DLQ / f"{run_id}.json").write_text(
        json.dumps(payload, sort_keys=True, default=str, indent=2),
        encoding="utf-8",
    )


def _dispatch_queued_runs() -> None:
    worker_id = f"queue-{os.getpid()}-{uuid.uuid4().hex[:6]}"
    requeue_stale_jobs(QUEUE_DB)
    while not QUEUE_DISPATCHER_STOP.is_set():
        job = claim_next_job(
            QUEUE_DB,
            worker_id=worker_id,
            lease_ms=_queue_lease_ms(),
        )
        if not job:
            time.sleep(_queue_poll_interval_s())
            continue

        run_id = str(job["run_id"])
        thread_id = str(job["thread_id"])
        tenant_id = str(job["tenant_id"])
        actor = str(job["actor"])
        _run_worker(run_id=run_id, thread_id=thread_id, tenant_id=tenant_id, actor=actor)
        status = _get_run_status(run_id=run_id, tenant_id=tenant_id) or {}
        final = str(status.get("status", "failed"))
        error = str(status.get("error", ""))
        complete_job(QUEUE_DB, run_id=run_id, status=final, error=error)
        if final in {"failed", "timed_out"}:
            _write_dlq(
                run_id=run_id,
                thread_id=thread_id,
                tenant_id=tenant_id,
                actor=actor,
                status=final,
                error=error,
            )


def _ensure_dispatcher_started() -> None:
    global QUEUE_DISPATCHER_THREAD
    if not _queue_enabled():
        return
    with QUEUE_DISPATCHER_LOCK:
        if QUEUE_DISPATCHER_THREAD and QUEUE_DISPATCHER_THREAD.is_alive():
            return
        QUEUE_DISPATCHER_STOP.clear()
        thread = threading.Thread(target=_dispatch_queued_runs, daemon=True)
        thread.start()
        QUEUE_DISPATCHER_THREAD = thread


def _stop_dispatcher() -> None:
    QUEUE_DISPATCHER_STOP.set()
    with QUEUE_DISPATCHER_LOCK:
        thread = QUEUE_DISPATCHER_THREAD
        if thread and thread.is_alive():
            thread.join(timeout=0.5)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/livez")
def livez() -> dict[str, str]:
    return {"status": "live"}


@app.get("/readyz")
def readyz() -> dict[str, Any]:
    return {
        "status": "ready",
        "queue_enabled": _queue_enabled(),
        "queue_db_exists": QUEUE_DB.exists(),
    }


@app.get("/status/public")
def public_status() -> dict[str, Any]:
    queue_items = replayable_failed_jobs(QUEUE_DB) if QUEUE_DB.exists() else []
    return {
        "status": "ok",
        "api_version": "v1",
        "strategy_preset": get_strategy_preset(),
        "dlq_items": len(queue_items),
    }


@app.get("/playground/card/plan")
def playground_plan_card(
    context: ViewerAuth,
) -> dict[str, Any]:
    if ADAPTER_MODE != "playground":
        raise HTTPException(
            status_code=404,
            detail="Playground mode disabled; set ADAPTER=playground to expose the sample card.",
        )
    _audit_event(action="playground.card.read", tenant_id=context.tenant_id, actor=context.subject)
    return PLAYGROUND_PLAN_CARD


@app.get("/threads")
def list_threads(
    context: ViewerAuth,
) -> dict[str, int]:
    if ADAPTER_MODE in {"demo", "playground"}:
        _audit_event(action="threads.list", tenant_id=context.tenant_id, actor=context.subject)
        return demo_list_threads()
    return {}


@app.get("/threads/{thread_id}")
def get_thread(
    thread_id: str,
    context: ViewerAuth,
) -> list[dict[str, Any]]:
    _audit_event(
        action="thread.read",
        tenant_id=context.tenant_id,
        actor=context.subject,
        detail={"thread_id": thread_id},
    )
    return _load_thread_messages(thread_id)


@app.post("/threads/{thread_id}/events")
async def ingest_event(
    thread_id: str,
    payload: ThreadEventPayload,
    request: Request,
    context: OperatorAuth,
    signature: str | None = Header(default=None, alias="X-OverhearOps-Signature"),
) -> dict[str, Any]:
    raw_body = await request.body()
    _validate_ingest_signature(raw_body=raw_body, signature=signature)

    key = _event_store_key(tenant_id=context.tenant_id, thread_id=thread_id)
    events = THREAD_EVENTS.setdefault(key, [])
    events.append(cast(dict[str, Any], _redact_value(payload.model_dump(mode="json"))))
    cap = _max_thread_events()
    if len(events) > cap:
        del events[:-cap]
    _audit_event(
        action="thread.event.ingested",
        tenant_id=context.tenant_id,
        actor=context.subject,
        detail={"thread_id": thread_id, "stored": len(events)},
    )
    return {"status": "ok", "stored": len(events)}


@app.post("/analytics/events")
def ingest_analytics_event(
    payload: AnalyticsEventRequest,
    context: ViewerAuth,
) -> dict[str, Any]:
    if not get_feature_flag("analytics_ingest_enabled", default=True):
        raise HTTPException(status_code=503, detail="Analytics ingest disabled by feature flag.")
    line = {
        "event": payload.event,
        "session_id": payload.session_id,
        "tenant_id": _safe_tenant_id(context.tenant_id),
        "metadata": cast(dict[str, Any], _redact_value(payload.metadata)),
        "ts_ms": int(time.time() * 1000),
    }
    events_path = ANALYTICS_DIR / "events.jsonl"
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line, sort_keys=True, default=str) + "\n")
    return {"status": "ok"}


@app.get("/analytics/funnel")
def analytics_funnel(
    context: AdminAuth,
) -> dict[str, Any]:
    counts: dict[str, int] = {}
    events_path = ANALYTICS_DIR / "events.jsonl"
    if events_path.exists():
        with events_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                data = cast(dict[str, Any], json.loads(line))
                if _safe_tenant_id(str(data.get("tenant_id", ""))) != _safe_tenant_id(
                    context.tenant_id
                ):
                    continue
                event = str(data.get("event", "unknown"))
                counts[event] = counts.get(event, 0) + 1
    return {"tenant_id": _safe_tenant_id(context.tenant_id), "counts": counts}


@app.websocket("/stream/{thread_id}")
async def stream(ws: WebSocket, thread_id: str) -> None:
    try:
        context = _resolve_auth_context(
            authorization=ws.headers.get("authorization"),
            tenant_header=ws.headers.get("x-overhearops-tenant"),
        )
    except HTTPException as exc:
        await ws.close(code=4401, reason=str(exc.detail))
        return
    await ws.accept()
    try:
        _audit_event(
            action="thread.stream.open",
            tenant_id=context.tenant_id,
            actor=context.subject,
            detail={"thread_id": thread_id},
        )
        async for message in iter_messages(thread_id):
            await ws.send_json(message)
            await asyncio.sleep(0.35)
    except HTTPException as exc:
        await ws.send_json({"error": exc.detail})
        await ws.close()
    except WebSocketDisconnect:
        return


def _set_run_status(
    run_id: str,
    thread_id: str,
    tenant_id: str,
    status: str,
    error: str | None = None,
    actor: str = "system",
) -> None:
    now_ms = int(time.time() * 1000)
    with RUN_STATUS_LOCK:
        record = RUN_STATUS.setdefault(
            run_id,
            {
                "run_id": run_id,
                "thread_id": thread_id,
                "tenant_id": _safe_tenant_id(tenant_id),
                "status": status,
                "created_at_ms": now_ms,
            },
        )
        record["thread_id"] = thread_id
        record["tenant_id"] = _safe_tenant_id(tenant_id)
        record["status"] = status
        record["updated_at_ms"] = now_ms
        if status == "running":
            record.setdefault("started_at_ms", now_ms)
        if status in TERMINAL_STATUSES or status == "timed_out":
            record["ended_at_ms"] = now_ms
        if error:
            record["error"] = str(_redact_value(error))
        elif status not in {"failed", "timed_out"}:
            record.pop("error", None)

        run_dir = RUNS / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        status_path = run_dir / "status.json"
        STORAGE_CODEC.write_json(status_path, record)

        max_entries = _max_run_status_entries()
        if len(RUN_STATUS) > max_entries:
            oldest = sorted(
                RUN_STATUS.items(),
                key=lambda item: int(item[1].get("updated_at_ms", 0)),
            )
            for old_run_id, _ in oldest[: len(RUN_STATUS) - max_entries]:
                RUN_STATUS.pop(old_run_id, None)

    _audit_event(
        action=f"run.status.{status}",
        tenant_id=tenant_id,
        actor=actor,
        run_id=run_id,
        detail={"thread_id": thread_id, "error": error or ""},
    )
    if status in TERMINAL_STATUSES or status == "timed_out":
        payload = _get_run_status(run_id=run_id, tenant_id=tenant_id)
        if payload:
            _notify_run_terminal(run_id=run_id, tenant_id=tenant_id, payload=payload)


def _get_run_status(run_id: str, tenant_id: str) -> dict[str, Any] | None:
    with RUN_STATUS_LOCK:
        record = RUN_STATUS.get(run_id)
        if record and _run_belongs_to_tenant(record=record, tenant_id=tenant_id):
            return dict(record)

    status_path = RUNS / run_id / "status.json"
    if status_path.exists():
        payload = STORAGE_CODEC.read_json(status_path)
        if _run_belongs_to_tenant(record=payload, tenant_id=tenant_id):
            return payload

    if _security_mode() == "off":
        path = RUNS / run_id / "artefacts.json"
        if path.exists():
            data = STORAGE_CODEC.read_json(path)
            return {
                "run_id": run_id,
                "thread_id": str(data.get("thread_id", "")),
                "tenant_id": _safe_tenant_id(str(data.get("tenant_id", tenant_id))),
                "status": "succeeded",
            }
    return None


def _execute_run(thread_id: str, run_id: str, tenant_id: str) -> dict[str, Any]:
    if _cancel_requested(run_id):
        raise RuntimeError("Run cancelled.")
    messages = _load_thread_messages(thread_id)
    last = messages[-1] if messages else {}
    config = {"configurable": {"thread_id": run_id}}
    run_dir = RUNS / run_id
    run_dir.mkdir(exist_ok=True, parents=True)
    previous_run_id = os.getenv("OVERHEAROPS_RUN_ID")
    os.environ["OVERHEAROPS_RUN_ID"] = run_id
    set_run_context(
        run_id=run_id,
        mode=os.getenv("OVERHEAROPS_LLM_MODE"),
        provider=os.getenv("OVERHEAROPS_LLM_PROVIDER"),
    )
    try:
        with RUN_EXECUTION_LOCK:
            state: dict[str, Any] = GRAPH.invoke(
                {"msg": last or {}, "thread_id": thread_id}, config=config
            )
    finally:
        set_run_context(run_id=None, mode=None, provider=None)
        if previous_run_id is not None:
            os.environ["OVERHEAROPS_RUN_ID"] = previous_run_id
        else:
            os.environ.pop("OVERHEAROPS_RUN_ID", None)

    if _cancel_requested(run_id):
        raise RuntimeError("Run cancelled.")

    provider = trace.get_tracer_provider()
    flush = getattr(provider, "force_flush", None)
    if callable(flush):
        flush()
    graphs = build_graphs(run_id)
    replay_hash = _compute_replay_hash(run_id)
    token_cost = _run_token_cost(graphs)
    per_run_budget, _ = get_token_budgets()
    if token_cost > per_run_budget:
        raise RuntimeError(
            f"Run token budget exceeded ({token_cost} > {per_run_budget})."
        )
    usage = record_usage(
        tenant_id=_safe_tenant_id(tenant_id),
        run_id=run_id,
        token_cost=token_cost,
        cost_usd=token_cost * 0.000002,
    )

    verdict = state.get("verdict", {})
    artefacts = {
        "run_id": run_id,
        "thread_id": thread_id,
        "tenant_id": _safe_tenant_id(tenant_id),
        "mode": os.getenv("OVERHEAROPS_LLM_MODE", "offline"),
        "provider": os.getenv("OVERHEAROPS_LLM_PROVIDER", "offline"),
        "integration_mode": _integration_mode(),
        "strategy_preset": get_strategy_preset(),
        "verdict": verdict,
        "gate": {
            "action": verdict.get("action"),
            "certainty": verdict.get("certainty"),
        },
        "artefacts": state.get("artefacts", {}),
        "artefacts_by_plan": state.get("artefacts_by_plan", {}),
        "plans": state.get("plans", []),
        "replay_hash": replay_hash,
        "graphs": graphs,
        "budget": {
            "token_cost": token_cost,
            "per_run_budget": per_run_budget,
            "tenant_used_tokens": int(usage.get("used_tokens", 0)),
        },
    }
    artefacts = cast(dict[str, Any], _redact_value(artefacts))
    STORAGE_CODEC.write_json(run_dir / "artefacts.json", artefacts)
    with (run_dir / "graphs.json").open("wb") as fh:
        fh.write(orjson.dumps(graphs))
    (run_dir / "hash.txt").write_text(replay_hash, encoding="utf-8")

    return {"run_id": run_id, "verdict": artefacts["verdict"]}


def _run_worker(run_id: str, thread_id: str, tenant_id: str, actor: str = "system") -> None:
    if _cancel_requested(run_id):
        _set_run_status(
            run_id=run_id,
            thread_id=thread_id,
            tenant_id=tenant_id,
            status="cancelled",
            actor=actor,
        )
        return

    _set_run_status(
        run_id=run_id,
        thread_id=thread_id,
        tenant_id=tenant_id,
        status="running",
        actor=actor,
    )
    error_box: dict[str, Exception] = {}

    def invoke() -> None:
        try:
            _execute_run(thread_id=thread_id, run_id=run_id, tenant_id=tenant_id)
        except Exception as exc:  # noqa: BLE001
            error_box["exc"] = exc

    worker = threading.Thread(target=invoke, daemon=True)
    worker.start()
    worker.join(timeout=_run_max_runtime_s())

    if worker.is_alive():
        _request_cancel(run_id)
        _set_run_status(
            run_id=run_id,
            thread_id=thread_id,
            tenant_id=tenant_id,
            status="timed_out",
            error=f"Run exceeded max runtime of {_run_max_runtime_s():.0f}s.",
            actor=actor,
        )
        return

    if _cancel_requested(run_id):
        _set_run_status(
            run_id=run_id,
            thread_id=thread_id,
            tenant_id=tenant_id,
            status="cancelled",
            actor=actor,
        )
        _clear_cancel(run_id)
        return

    exc = error_box.get("exc")
    if exc is not None:
        status = "cancelled" if "cancel" in str(exc).lower() else "failed"
        _set_run_status(
            run_id=run_id,
            thread_id=thread_id,
            tenant_id=tenant_id,
            status=status,
            error=str(exc),
            actor=actor,
        )
        _clear_cancel(run_id)
        return
    _set_run_status(
        run_id=run_id,
        thread_id=thread_id,
        tenant_id=tenant_id,
        status="succeeded",
        actor=actor,
    )
    _clear_cancel(run_id)


@app.post("/run/{thread_id}")
async def run(
    thread_id: str,
    context: OperatorAuth,
) -> dict[str, Any]:
    run_id = _new_run_id(thread_id=thread_id, tenant_id=context.tenant_id)
    _set_run_status(
        run_id=run_id,
        thread_id=thread_id,
        tenant_id=context.tenant_id,
        status="queued",
        actor=context.subject,
    )
    try:
        _set_run_status(
            run_id=run_id,
            thread_id=thread_id,
            tenant_id=context.tenant_id,
            status="running",
            actor=context.subject,
        )
        payload = _execute_run(thread_id=thread_id, run_id=run_id, tenant_id=context.tenant_id)
    except HTTPException as exc:
        _set_run_status(
            run_id=run_id,
            thread_id=thread_id,
            tenant_id=context.tenant_id,
            status="failed",
            error=str(exc.detail),
            actor=context.subject,
        )
        raise
    except Exception as exc:  # noqa: BLE001 - map unknown failures to HTTP 500
        _set_run_status(
            run_id=run_id,
            thread_id=thread_id,
            tenant_id=context.tenant_id,
            status="failed",
            error=str(exc),
            actor=context.subject,
        )
        raise HTTPException(status_code=500, detail="Run execution failed.") from exc
    _set_run_status(
        run_id=run_id,
        thread_id=thread_id,
        tenant_id=context.tenant_id,
        status="succeeded",
        actor=context.subject,
    )
    return payload


@app.post("/runs")
def start_run(
    request: RunRequest,
    context: OperatorAuth,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Any:
    if not get_feature_flag("run_execution_enabled", default=True):
        raise HTTPException(status_code=503, detail="Run execution is disabled by feature flag.")
    exhausted, budget_payload = _tenant_budget_exhausted(context.tenant_id)
    if exhausted:
        raise HTTPException(
            status_code=429,
            detail=(
                "Tenant token budget exhausted. "
                f"Used={budget_payload['used_tokens']} Budget={budget_payload['per_tenant_budget']}"
            ),
        )

    if idempotency_key:
        existing_run_id = _find_idempotent_run(tenant_id=context.tenant_id, key=idempotency_key)
        if existing_run_id:
            existing = _get_run_status(run_id=existing_run_id, tenant_id=context.tenant_id)
            if existing:
                existing_status = str(existing.get("status", "queued"))
                code = 200 if existing_status in TERMINAL_STATUSES else 202
                return JSONResponse(status_code=code, content=existing)

    run_id = _new_run_id(thread_id=request.thread_id, tenant_id=context.tenant_id)
    if idempotency_key:
        _record_idempotency(tenant_id=context.tenant_id, key=idempotency_key, run_id=run_id)

    _set_run_status(
        run_id=run_id,
        thread_id=request.thread_id,
        tenant_id=context.tenant_id,
        status="queued",
        actor=context.subject,
    )
    if request.simulate_only:
        _run_worker(
            run_id=run_id,
            thread_id=request.thread_id,
            tenant_id=context.tenant_id,
            actor=context.subject,
        )
        simulation = simulate_run(
            run_id=run_id,
            context=AuthContext(
                subject=context.subject,
                role="viewer",
                tenant_id=context.tenant_id,
            ),
        )
        return JSONResponse(status_code=200, content={"status": "simulated", **simulation})
    if request.background:
        if _queue_enabled():
            enqueue_job(
                QUEUE_DB,
                run_id=run_id,
                thread_id=request.thread_id,
                tenant_id=context.tenant_id,
                actor=context.subject,
                payload={"background": True},
            )
            _ensure_dispatcher_started()
        else:
            worker = threading.Thread(
                target=_run_worker,
                args=(run_id, request.thread_id, context.tenant_id, context.subject),
                daemon=True,
            )
            RUN_THREADS[run_id] = worker
            worker.start()
        payload = _get_run_status(run_id=run_id, tenant_id=context.tenant_id) or {
            "run_id": run_id,
            "thread_id": request.thread_id,
            "tenant_id": context.tenant_id,
            "status": "queued",
        }
        return JSONResponse(status_code=202, content=payload)

    _run_worker(
        run_id=run_id,
        thread_id=request.thread_id,
        tenant_id=context.tenant_id,
        actor=context.subject,
    )
    payload = _get_run_status(run_id=run_id, tenant_id=context.tenant_id) or {
        "run_id": run_id,
        "thread_id": request.thread_id,
        "tenant_id": context.tenant_id,
        "status": "failed",
        "error": "Run status unavailable",
    }
    status_code = 200 if payload.get("status") == "succeeded" else 500
    return JSONResponse(status_code=status_code, content=payload)


@app.get("/runs/dlq")
def list_dlq(
    context: OperatorAuth,
) -> dict[str, Any]:
    records = [
        record
        for record in replayable_failed_jobs(QUEUE_DB)
        if _safe_tenant_id(str(record.get("tenant_id", ""))) == _safe_tenant_id(context.tenant_id)
    ]
    return {"items": records}


@app.get("/tenants/{tenant_id}/dsr/export")
def dsr_export(
    tenant_id: str,
    context: AdminAuth,
) -> dict[str, Any]:
    target_tenant = _safe_tenant_id(tenant_id)
    run_ids = _tenant_run_ids(target_tenant)
    export = {
        "tenant_id": target_tenant,
        "run_ids": run_ids,
        "count": len(run_ids),
        "exported_at_ms": int(time.time() * 1000),
    }
    export_dir = RUNS / "dsr"
    export_path = export_dir / f"{target_tenant}-{int(time.time())}.json"
    STORAGE_CODEC.write_json(export_path, export)
    _audit_event(
        action="tenant.dsr.export",
        tenant_id=target_tenant,
        actor=context.subject,
        detail={"count": len(run_ids), "path": str(export_path)},
    )
    return {
        "status": "ok",
        "tenant_id": target_tenant,
        "count": len(run_ids),
        "export_path": str(export_path),
    }


@app.post("/tenants/{tenant_id}/dsr/delete")
def dsr_delete(
    tenant_id: str,
    request: DsrDeleteRequest,
    context: AdminAuth,
) -> dict[str, Any]:
    target_tenant = _safe_tenant_id(tenant_id)
    run_ids = _tenant_run_ids(target_tenant)
    deleted = 0
    if not request.dry_run:
        for run_id in run_ids:
            run_path = RUNS / run_id
            if run_path.exists():
                shutil.rmtree(run_path, ignore_errors=True)
                deleted += 1
    _audit_event(
        action="tenant.dsr.delete",
        tenant_id=target_tenant,
        actor=context.subject,
        detail={"dry_run": request.dry_run, "matched": len(run_ids), "deleted": deleted},
    )
    return {
        "status": "ok",
        "tenant_id": target_tenant,
        "dry_run": request.dry_run,
        "matched_runs": len(run_ids),
        "deleted_runs": deleted,
    }


@app.get("/admin/settings")
def get_admin_settings(
    context: AdminAuth,
) -> dict[str, Any]:
    _audit_event(
        action="admin.settings.read",
        tenant_id=context.tenant_id,
        actor=context.subject,
    )
    return load_runtime_settings()


@app.put("/admin/settings")
def update_admin_settings(
    request: SettingsUpdateRequest,
    context: AdminAuth,
) -> dict[str, Any]:
    _audit_event(
        action="admin.settings.update",
        tenant_id=context.tenant_id,
        actor=context.subject,
    )
    return save_runtime_settings(request.payload)


@app.get("/admin/prompts")
def get_admin_prompts(
    context: AdminAuth,
) -> dict[str, Any]:
    _audit_event(
        action="admin.prompts.read",
        tenant_id=context.tenant_id,
        actor=context.subject,
    )
    return load_prompt_registry()


@app.put("/admin/prompts")
def update_admin_prompts(
    request: SettingsUpdateRequest,
    context: AdminAuth,
) -> dict[str, Any]:
    _audit_event(
        action="admin.prompts.update",
        tenant_id=context.tenant_id,
        actor=context.subject,
    )
    return save_prompt_registry(request.payload)


@app.get("/admin/policies")
def get_admin_policies(
    context: AdminAuth,
) -> dict[str, Any]:
    _audit_event(
        action="admin.policies.read",
        tenant_id=context.tenant_id,
        actor=context.subject,
    )
    return load_policy_rules()


@app.put("/admin/policies")
def update_admin_policies(
    request: SettingsUpdateRequest,
    context: AdminAuth,
) -> dict[str, Any]:
    _audit_event(
        action="admin.policies.update",
        tenant_id=context.tenant_id,
        actor=context.subject,
    )
    return save_policy_rules(request.payload)


@app.post("/admin/strategy/{preset}")
def update_strategy_preset(
    preset: str,
    context: AdminAuth,
) -> dict[str, Any]:
    applied = set_strategy_preset(preset)
    _audit_event(
        action="admin.strategy.update",
        tenant_id=context.tenant_id,
        actor=context.subject,
        detail={"preset": applied},
    )
    return {"status": "ok", "strategy_preset": applied}


@app.get("/runs/{run_id}/status")
def run_status(
    run_id: str,
    context: ViewerAuth,
) -> dict[str, Any]:
    payload = _get_run_status(run_id=run_id, tenant_id=context.tenant_id)
    if payload:
        return payload
    raise HTTPException(status_code=404, detail="Run status not found.")


@app.get("/runs/history")
def run_history(
    context: ViewerAuth,
    status: str | None = Query(default=None),
    thread_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    term = q.lower().strip() if q else ""
    items: list[dict[str, Any]] = []
    for run_id in _tenant_run_ids(context.tenant_id):
        summary = _run_summary(run_id=run_id, tenant_id=context.tenant_id)
        if summary is None:
            continue
        if status and str(summary.get("status", "")) != status:
            continue
        if thread_id and str(summary.get("thread_id", "")) != thread_id:
            continue
        haystack = " ".join(
            [
                str(summary.get("run_id", "")),
                str(summary.get("thread_id", "")),
                str(summary.get("winner_plan_id", "")),
                str(summary.get("action", "")),
            ]
        ).lower()
        if term and term not in haystack:
            continue
        items.append(summary)
    items.sort(key=lambda item: int(item.get("updated_at_ms", 0)), reverse=True)
    return {"items": items[:limit], "count": len(items)}


@app.get("/runs/export")
def export_run_history(
    context: ViewerAuth,
    format: str = Query(default="json", pattern="^(json|jsonl)$"),
    limit: int = Query(default=500, ge=1, le=5000),
) -> Any:
    payload = run_history(
        context=context,
        status=None,
        thread_id=None,
        q=None,
        limit=limit,
    )
    items = payload.get("items", [])
    if format == "jsonl":
        lines = [
            json.dumps(item, sort_keys=True, default=str)
            for item in items
            if isinstance(item, dict)
        ]
        return PlainTextResponse("\n".join(lines), media_type="application/x-ndjson")
    return payload


@app.get("/runs/compare")
def compare_runs(
    context: ViewerAuth,
    left: str = Query(..., min_length=1),
    right: str = Query(..., min_length=1),
) -> dict[str, Any]:
    left_payload = _run_summary(left, context.tenant_id)
    right_payload = _run_summary(right, context.tenant_id)
    if left_payload is None or right_payload is None:
        raise HTTPException(status_code=404, detail="One or both runs not found.")
    diff: dict[str, dict[str, Any]] = {}
    keys = sorted(set(left_payload.keys()) | set(right_payload.keys()))
    for key in keys:
        left_value = left_payload.get(key)
        right_value = right_payload.get(key)
        if left_value != right_value:
            diff[key] = {"left": left_value, "right": right_value}
    return {"left": left_payload, "right": right_payload, "diff": diff}


@app.get("/tenants/{tenant_id}/usage")
def tenant_usage(
    tenant_id: str,
    context: AdminAuth,
) -> dict[str, Any]:
    target_tenant = _safe_tenant_id(tenant_id)
    if context.role != "admin" and _safe_tenant_id(context.tenant_id) != target_tenant:
        raise HTTPException(status_code=403, detail="Tenant access denied.")
    return get_tenant_usage(target_tenant)


@app.get("/usage/export")
def usage_export(
    context: AdminAuth,
) -> dict[str, Any]:
    records = export_usage_records()
    return {"items": records, "count": len(records)}


@app.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    context: ViewerAuth,
) -> dict[str, Any]:
    status = _get_run_status(run_id=run_id, tenant_id=context.tenant_id)
    if not status:
        raise HTTPException(status_code=404, detail="Run not found.")
    path = RUNS / run_id / "artefacts.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Run not found.")
    payload = STORAGE_CODEC.read_json(path)
    if _security_mode() != "off":
        payload_tenant = _safe_tenant_id(str(payload.get("tenant_id", "")))
        if payload_tenant != _safe_tenant_id(context.tenant_id):
            raise HTTPException(status_code=404, detail="Run not found.")
    return payload


@app.get("/runs/{run_id}/graphs.json")
async def get_graphs(
    run_id: str,
    context: ViewerAuth,
) -> dict[str, Any]:
    status = _get_run_status(run_id=run_id, tenant_id=context.tenant_id)
    if not status:
        raise HTTPException(status_code=404, detail="Run not found.")
    return build_graphs(run_id)


@app.post("/runs/{run_id}/simulate")
def simulate_run(
    run_id: str,
    context: ViewerAuth,
) -> dict[str, Any]:
    status = _get_run_status(run_id=run_id, tenant_id=context.tenant_id)
    if not status:
        raise HTTPException(status_code=404, detail="Run not found.")
    artefact_path = RUNS / run_id / "artefacts.json"
    if not artefact_path.exists():
        raise HTTPException(status_code=404, detail="Run artefacts not found.")
    payload = STORAGE_CODEC.read_json(artefact_path)
    verdict = payload.get("verdict", {})
    policy = get_policy_rules()
    shipping = policy.get("shipping", {}) if isinstance(policy, dict) else {}
    simulation = policy.get("simulation", {}) if isinstance(policy, dict) else {}

    action = str(verdict.get("action", "")) if isinstance(verdict, dict) else ""
    certainty = float(verdict.get("certainty", 0.0)) if isinstance(verdict, dict) else 0.0
    allowed_actions = (
        shipping.get("allowed_actions", ["approve", "ship"])
        if isinstance(shipping, dict)
        else ["approve", "ship"]
    )
    min_certainty = (
        float(shipping.get("min_certainty", 0.66))
        if isinstance(shipping, dict)
        else 0.66
    )
    safety = payload.get("artefacts", {}).get("safety", {})
    safety_allowed = bool(safety.get("allowed", True)) if isinstance(safety, dict) else True
    require_safety_allowed = (
        bool(simulation.get("require_safety_allowed", True))
        if isinstance(simulation, dict)
        else True
    )
    checks = {
        "action_allowed": action in allowed_actions,
        "certainty_allowed": certainty >= min_certainty,
        "safety_allowed": safety_allowed or not require_safety_allowed,
    }
    can_ship = all(checks.values())
    return {
        "run_id": run_id,
        "tenant_id": _safe_tenant_id(context.tenant_id),
        "checks": checks,
        "policy": policy,
        "can_ship": can_ship,
    }


@app.post("/runs/{run_id}/cancel")
def cancel_run(
    run_id: str,
    context: OperatorAuth,
) -> dict[str, Any]:
    payload = _get_run_status(run_id=run_id, tenant_id=context.tenant_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Run not found.")
    current = str(payload.get("status", ""))
    if current in TERMINAL_STATUSES:
        return payload
    _request_cancel(run_id)
    _set_run_status(
        run_id=run_id,
        thread_id=str(payload.get("thread_id", "")),
        tenant_id=context.tenant_id,
        status="cancel_requested",
        actor=context.subject,
    )
    if _queue_enabled():
        complete_job(QUEUE_DB, run_id=run_id, status="cancelled", error="cancel requested")
        _set_run_status(
            run_id=run_id,
            thread_id=str(payload.get("thread_id", "")),
            tenant_id=context.tenant_id,
            status="cancelled",
            actor=context.subject,
        )
    return cast(
        dict[str, Any],
        _get_run_status(run_id=run_id, tenant_id=context.tenant_id) or payload,
    )


@app.post("/runs/{run_id}/approve")
def approve_run(
    run_id: str,
    request: ApprovalRequest,
    context: ApproverAuth,
) -> dict[str, Any]:
    status = _get_run_status(run_id=run_id, tenant_id=context.tenant_id)
    if not status:
        raise HTTPException(status_code=404, detail="Run not found.")
    approval_entry = {
        "id": f"approval-{uuid.uuid4().hex[:8]}",
        "run_id": run_id,
        "tenant_id": _safe_tenant_id(context.tenant_id),
        "decision": request.decision,
        "approved": request.decision == "approve",
        "actor": context.subject,
        "created_at_ms": int(time.time() * 1000),
        "note": str(_redact_value(request.note.strip())),
    }
    approvals = _load_run_approvals(run_id)
    approvals.append(approval_entry)
    _store_run_approvals(run_id, approvals)
    STORAGE_CODEC.write_json(_run_approval_path(run_id), approval_entry)
    _audit_event(
        action="run.approved",
        tenant_id=context.tenant_id,
        actor=context.subject,
        run_id=run_id,
        detail={"note": approval_entry["note"], "decision": approval_entry["decision"]},
    )
    return {
        "run_id": run_id,
        "tenant_id": _safe_tenant_id(context.tenant_id),
        "min_approvals": get_min_approvals(),
        "items": approvals,
    }


@app.get("/runs/{run_id}/approvals")
def get_run_approvals(
    run_id: str,
    context: ViewerAuth,
) -> dict[str, Any]:
    status = _get_run_status(run_id=run_id, tenant_id=context.tenant_id)
    if not status:
        raise HTTPException(status_code=404, detail="Run not found.")
    approvals = _load_run_approvals(run_id)
    return {
        "run_id": run_id,
        "tenant_id": _safe_tenant_id(context.tenant_id),
        "min_approvals": get_min_approvals(),
        "items": approvals,
    }


@app.post("/runs/{run_id}/ship")
def ship_run(
    run_id: str,
    context: OperatorAuth,
) -> dict[str, Any]:
    if not get_feature_flag("ship_side_effects_enabled", default=True):
        raise HTTPException(
            status_code=503,
            detail="Shipping side effects disabled by feature flag.",
        )
    status = _get_run_status(run_id=run_id, tenant_id=context.tenant_id)
    if not status:
        raise HTTPException(status_code=404, detail="Run not found.")

    artefact_path = RUNS / run_id / "artefacts.json"
    if not artefact_path.exists():
        raise HTTPException(status_code=409, detail="Run artefacts are not available yet.")
    payload = STORAGE_CODEC.read_json(artefact_path)
    payload_tenant = _safe_tenant_id(str(payload.get("tenant_id", "")))
    if payload_tenant != _safe_tenant_id(context.tenant_id):
        raise HTTPException(status_code=404, detail="Run not found.")
    verdict = payload.get("verdict", {})
    verdict_payload = verdict if isinstance(verdict, dict) else {}
    action = str(verdict_payload.get("action", "")).lower()
    policy = get_policy_rules()
    shipping_rules = policy.get("shipping", {}) if isinstance(policy, dict) else {}
    allowed_actions_raw = (
        shipping_rules.get("allowed_actions", ["approve", "ship"])
        if isinstance(shipping_rules, dict)
        else ["approve", "ship"]
    )
    allowed_actions = [str(value).lower() for value in allowed_actions_raw]
    min_certainty = (
        float(shipping_rules.get("min_certainty", 0.66))
        if isinstance(shipping_rules, dict)
        else 0.66
    )
    certainty = float(verdict_payload.get("certainty", 0.0))
    if action not in allowed_actions:
        raise HTTPException(status_code=409, detail="Run verdict is not eligible for shipping.")
    if certainty < min_certainty:
        raise HTTPException(
            status_code=409,
            detail=(
                "Run certainty below shipping policy threshold "
                f"({certainty:.2f} < {min_certainty:.2f})."
            ),
        )
    if _integration_mode() != "live":
        raise HTTPException(
            status_code=409,
            detail=(
                "Integration mode is dry_run. Set OVERHEAROPS_INTEGRATION_MODE=live "
                "to apply side effects."
            ),
        )
    approval = _load_run_approval(run_id=run_id)
    approvals = _load_run_approvals(run_id)
    if _require_approval_for_ship():
        if approval is None and not approvals:
            raise HTTPException(status_code=409, detail="Run requires approver sign-off.")
        approval_source = approval if approval is not None else approvals[0]
        approval_tenant = _safe_tenant_id(str(approval_source.get("tenant_id", "")))
        if approval_tenant != _safe_tenant_id(context.tenant_id):
            raise HTTPException(status_code=404, detail="Run not found.")
        min_approvals = get_min_approvals()
        unique_approvers = {
            str(item.get("actor", item.get("approved_by", "")))
            for item in approvals
            if str(item.get("decision", "approve")).lower() == "approve"
        }
        if len([actor for actor in unique_approvers if actor]) < min_approvals:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Run requires additional approvers before shipping "
                    f"({len(unique_approvers)}/{min_approvals})."
                ),
            )

    ship_record = {
        "run_id": run_id,
        "tenant_id": _safe_tenant_id(context.tenant_id),
        "applied": True,
        "applied_by": context.subject,
        "applied_at_ms": int(time.time() * 1000),
        "integration_mode": _integration_mode(),
        "approval": approval or {},
        "approvals": approvals,
    }
    STORAGE_CODEC.write_json(RUNS / run_id / "shipped.json", ship_record)
    _audit_event(
        action="run.ship.applied",
        tenant_id=context.tenant_id,
        actor=context.subject,
        run_id=run_id,
        detail={"integration_mode": _integration_mode()},
    )
    return ship_record


@app.post("/runs/{run_id}/replay")
def replay_run(
    run_id: str,
    context: OperatorAuth,
) -> dict[str, Any]:
    original = get_job(QUEUE_DB, run_id=run_id)
    if original is None:
        dlq_path = DLQ / f"{run_id}.json"
        if dlq_path.exists():
            original = cast(dict[str, Any], json.loads(dlq_path.read_text(encoding="utf-8")))
    if original is None:
        raise HTTPException(status_code=404, detail="Replay source not found.")

    source_tenant = _safe_tenant_id(str(original.get("tenant_id", "")))
    if source_tenant != _safe_tenant_id(context.tenant_id):
        raise HTTPException(status_code=404, detail="Replay source not found.")

    thread_id = str(original.get("thread_id", ""))
    if not thread_id:
        raise HTTPException(status_code=400, detail="Replay source missing thread_id.")
    new_run_id = _new_run_id(thread_id=thread_id, tenant_id=context.tenant_id)
    _set_run_status(
        run_id=new_run_id,
        thread_id=thread_id,
        tenant_id=context.tenant_id,
        status="queued",
        actor=context.subject,
    )
    enqueue_job(
        QUEUE_DB,
        run_id=new_run_id,
        thread_id=thread_id,
        tenant_id=context.tenant_id,
        actor=context.subject,
        payload={"replay_of": run_id},
    )
    _ensure_dispatcher_started()
    return cast(
        dict[str, Any],
        _get_run_status(run_id=new_run_id, tenant_id=context.tenant_id)
        or {"run_id": new_run_id, "status": "queued"},
    )


@app.get("/api/version")
def api_version() -> dict[str, str]:
    return {"version": "v1"}


@app.get("/api/v1/health")
def api_v1_health() -> dict[str, str]:
    return health()


@app.get("/api/v1/threads")
def api_v1_threads(
    context: ViewerAuth,
) -> dict[str, int]:
    return list_threads(context=context)


@app.post("/api/v1/runs")
def api_v1_start_run(
    request: RunRequest,
    context: OperatorAuth,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Any:
    return start_run(request=request, context=context, idempotency_key=idempotency_key)


@app.get("/api/v1/runs/{run_id}/status")
def api_v1_run_status(
    run_id: str,
    context: ViewerAuth,
) -> dict[str, Any]:
    return run_status(run_id=run_id, context=context)


@app.get("/api/v1/runs/history")
def api_v1_run_history(
    context: ViewerAuth,
    status: str | None = Query(default=None),
    thread_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    return run_history(
        context=context,
        status=status,
        thread_id=thread_id,
        q=q,
        limit=limit,
    )


@app.get("/api/v1/runs/{run_id}")
async def api_v1_get_run(
    run_id: str,
    context: ViewerAuth,
) -> dict[str, Any]:
    return await get_run(run_id=run_id, context=context)
