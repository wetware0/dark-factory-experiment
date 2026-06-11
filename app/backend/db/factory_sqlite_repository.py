"""SQLite repository for local PAVE factory smoke tests.

This provider is for local integration and worker smoke tests only. SQL Server
remains the WTG operational target. The implementation stores typed JSON
entities in SQLite and exposes the same async repository contract as the
SQL Server/Postgres factory providers.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar

from backend import config

T = TypeVar("T")

_schema_ready = False
_schema_lock = threading.Lock()

STALL_MCP_STATUSES = {"stale", "unauthenticated", "unavailable", "degraded"}
ACTIVE_RUN_STATUSES = {"queued", "claimed", "running"}
INTERRUPTED_RUN_STATUSES = {"failed", "stalled", "suspended"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _limit(limit: int) -> int:
    return max(1, min(int(limit), 5000))


def _instance_stale_seconds() -> int:
    return max(1, int(config.FACTORY_INSTANCE_STALE_SECONDS))


def _is_live_instance(row: dict[str, Any]) -> bool:
    if row.get("is_paused") or row.get("status") in {"paused", "stalled"}:
        return True
    heartbeat_raw = str(row.get("last_heartbeat_at") or row.get("updated_at") or "")
    try:
        heartbeat = datetime.fromisoformat(heartbeat_raw)
    except ValueError:
        return False
    if heartbeat.tzinfo is None:
        heartbeat = heartbeat.replace(tzinfo=UTC)
    return datetime.now(UTC) - heartbeat <= timedelta(seconds=_instance_stale_seconds())


def _sqlite_path() -> Path:
    raw = config.FACTORY_SQLITE_PATH or ".factory/factory.sqlite3"
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_sqlite_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS factory_entities (
                kind TEXT NOT NULL,
                id TEXT NOT NULL,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (kind, id)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS factory_entities_kind_updated
            ON factory_entities (kind, updated_at DESC)
            """
        )
        conn.commit()
        _schema_ready = True


async def _run(fn: Callable[[sqlite3.Connection], T]) -> T:
    def _sync() -> T:
        conn = _connect()
        try:
            _ensure_schema(conn)
            result = fn(conn)
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    return await asyncio.to_thread(_sync)


def _save(conn: sqlite3.Connection, kind: str, data: dict[str, Any]) -> dict[str, Any]:
    if not data.get("id"):
        data["id"] = _new_id()
    data.setdefault("created_at", _now())
    data["updated_at"] = data.get("updated_at") or _now()
    conn.execute(
        """
        INSERT OR REPLACE INTO factory_entities (kind, id, data, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (kind, str(data["id"]), json.dumps(data), data["updated_at"]),
    )
    return data


def _get(conn: sqlite3.Connection, kind: str, entity_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT data FROM factory_entities WHERE kind = ? AND id = ?",
        (kind, entity_id),
    ).fetchone()
    return json.loads(row["data"]) if row else None


def _all(conn: sqlite3.Connection, kind: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT data FROM factory_entities WHERE kind = ?",
        (kind,),
    ).fetchall()
    return [json.loads(row["data"]) for row in rows]


def _sort_desc(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: str(item.get(key) or ""), reverse=True)


def _sort_asc(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: str(item.get(key) or ""))


def _refresh_run_dashboard_log_sync(conn: sqlite3.Connection, run_id: str) -> None:
    events = [
        {
            "created_at": event.get("created_at"),
            "level": event.get("level") or "info",
            "phase": event.get("phase") or "",
            "message": event.get("message") or "",
            "payload": event.get("payload") or {},
        }
        for event in _sort_asc(
            [
                item
                for item in _all(conn, "run_events")
                if item.get("run_id") == run_id and item.get("dashboard_visible", True)
            ],
            "created_at",
        )
    ]
    run = _get(conn, "runs", run_id)
    if run is None:
        return
    run["dashboard_log"] = events
    run["updated_at"] = _now()
    _save(conn, "runs", run)


async def upsert_instance(
    *,
    instance_id: str,
    name: str,
    host_name: str,
    staff_code: str,
    board_name: str,
    status: str,
    detected_staff_code: str | None = None,
    version: str | None = None,
    process_id: str | None = None,
    capabilities: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any]:
        existing = _get(conn, "instances", instance_id) or {}
        now = _now()
        data = {
            **existing,
            "id": instance_id,
            "name": name,
            "host_name": host_name,
            "staff_code": staff_code,
            "detected_staff_code": detected_staff_code,
            "board_name": board_name,
            "status": status,
            "is_paused": bool(existing.get("is_paused", False)),
            "paused_reason": existing.get("paused_reason"),
            "version": version,
            "process_id": process_id,
            "capabilities": capabilities or {},
            "config": config or {},
            "last_heartbeat_at": now,
            "created_at": existing.get("created_at", now),
            "updated_at": now,
        }
        return _save(conn, "instances", data)

    return await _run(_sync)


async def heartbeat_instance(
    instance_id: str,
    *,
    status: str,
    detected_staff_code: str | None = None,
    process_id: str | None = None,
) -> dict[str, Any] | None:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any] | None:
        data = _get(conn, "instances", instance_id)
        if data is None:
            return None
        data["status"] = status
        if detected_staff_code is not None:
            data["detected_staff_code"] = detected_staff_code
        if process_id is not None:
            data["process_id"] = process_id
        data["last_heartbeat_at"] = _now()
        data["updated_at"] = _now()
        return _save(conn, "instances", data)

    return await _run(_sync)


async def pause_instance(instance_id: str, reason: str) -> dict[str, Any] | None:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any] | None:
        data = _get(conn, "instances", instance_id)
        if data is None:
            return None
        data.update(
            {
                "is_paused": True,
                "paused_reason": reason,
                "status": "paused",
                "updated_at": _now(),
            }
        )
        return _save(conn, "instances", data)

    return await _run(_sync)


async def resume_instance(instance_id: str) -> dict[str, Any] | None:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any] | None:
        data = _get(conn, "instances", instance_id)
        if data is None:
            return None
        data.update(
            {
                "is_paused": False,
                "paused_reason": None,
                "status": "ready",
                "updated_at": _now(),
            }
        )
        return _save(conn, "instances", data)

    return await _run(_sync)


async def list_instances() -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _sort_desc(
            [item for item in _all(conn, "instances") if _is_live_instance(item)],
            "updated_at",
        )
    )


async def get_instance(instance_id: str) -> dict[str, Any] | None:
    return await _run(lambda conn: _get(conn, "instances", instance_id))


async def record_mcp_readiness(
    *,
    instance_id: str | None,
    mcp_name: str,
    status: str,
    detail: str | None = None,
    auth_subject: str | None = None,
    reauth_url: str | None = None,
    expires_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any]:
        now = _now()
        return _save(
            conn,
            "mcp_readiness",
            {
                "id": _new_id(),
                "instance_id": instance_id,
                "mcp_name": mcp_name,
                "status": status,
                "detail": detail,
                "auth_subject": auth_subject,
                "reauth_url": reauth_url,
                "last_checked_at": now,
                "expires_at": expires_at,
                "metadata": metadata or {},
                "created_at": now,
                "updated_at": now,
            },
        )

    return await _run(_sync)


def _latest_mcp_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("instance_id") or ""), str(row.get("mcp_name") or ""))
        if key not in latest or str(row.get("updated_at") or "") > str(latest[key].get("updated_at") or ""):
            latest[key] = row
    return sorted(latest.values(), key=lambda item: (str(item.get("instance_id") or ""), str(item.get("mcp_name") or "")))


def _live_instance_ids(conn: sqlite3.Connection) -> set[str]:
    instances = {str(item.get("id")): item for item in _all(conn, "instances")}
    return {
        instance_id for instance_id, instance in instances.items() if _is_live_instance(instance)
    }


def _live_mcp_rows(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    instances = {str(item.get("id")): item for item in _all(conn, "instances")}
    live_instance_ids = {
        instance_id for instance_id, instance in instances.items() if _is_live_instance(instance)
    }
    return [
        row
        for row in rows
        if not row.get("instance_id")
        or str(row.get("instance_id")) not in instances
        or str(row.get("instance_id")) in live_instance_ids
    ]


async def list_latest_mcp_readiness(instance_id: str | None = None) -> list[dict[str, Any]]:
    def _sync(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = _all(conn, "mcp_readiness")
        if instance_id is not None:
            rows = [row for row in rows if row.get("instance_id") == instance_id]
        else:
            rows = _live_mcp_rows(conn, rows)
        return _latest_mcp_rows(rows)

    return await _run(_sync)


async def list_stalled_mcps() -> list[dict[str, Any]]:
    return [
        row
        for row in await list_latest_mcp_readiness()
        if row.get("status") in STALL_MCP_STATUSES
    ]


async def create_reauth_session(
    *,
    instance_id: str | None,
    mcp_name: str,
    reauth_url: str | None,
    requested_by_user_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any]:
        now = _now()
        return _save(
            conn,
            "mcp_reauth_sessions",
            {
                "id": _new_id(),
                "instance_id": instance_id,
                "mcp_name": mcp_name,
                "status": "requested",
                "reauth_url": reauth_url,
                "requested_by_user_id": requested_by_user_id,
                "completed_at": None,
                "metadata": metadata or {},
                "created_at": now,
                "updated_at": now,
            },
        )

    return await _run(_sync)


async def update_reauth_session(
    session_id: str,
    *,
    status: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any] | None:
        data = _get(conn, "mcp_reauth_sessions", session_id)
        if data is None:
            return None
        data["status"] = status
        if metadata is not None:
            data["metadata"] = metadata
        if status in {"complete", "verified", "cancelled"}:
            data["completed_at"] = _now()
        data["updated_at"] = _now()
        return _save(conn, "mcp_reauth_sessions", data)

    return await _run(_sync)


async def list_reauth_sessions() -> list[dict[str, Any]]:
    return await _run(lambda conn: _sort_desc(_all(conn, "mcp_reauth_sessions"), "created_at")[:100])


async def create_scout_cycle(
    *,
    instance_id: str | None,
    board_name: str,
    staff_code: str,
    status: str = "running",
    active_pave_task_id: str | None = None,
    candidate_count: int = 0,
    local_model: str | None = None,
    token_estimate: int = 0,
    input_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any]:
        now = _now()
        return _save(
            conn,
            "scout_cycles",
            {
                "id": _new_id(),
                "instance_id": instance_id,
                "board_name": board_name,
                "staff_code": staff_code,
                "status": status,
                "started_at": now,
                "finished_at": None,
                "active_pave_task_id": active_pave_task_id,
                "candidate_count": candidate_count,
                "selected_pave_task_id": None,
                "decision": None,
                "local_model": local_model,
                "token_estimate": token_estimate,
                "summary": None,
                "input_snapshot": input_snapshot or {},
                "output_snapshot": {},
                "created_at": now,
                "updated_at": now,
            },
        )

    return await _run(_sync)


async def finish_scout_cycle(
    cycle_id: str,
    *,
    status: str,
    selected_pave_task_id: str | None = None,
    candidate_count: int | None = None,
    decision: str | None = None,
    summary: str | None = None,
    output_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any] | None:
        data = _get(conn, "scout_cycles", cycle_id)
        if data is None:
            return None
        data["status"] = status
        data["selected_pave_task_id"] = selected_pave_task_id
        if candidate_count is not None:
            data["candidate_count"] = candidate_count
        data["decision"] = decision
        data["summary"] = summary
        data["output_snapshot"] = output_snapshot or {}
        data["finished_at"] = _now()
        data["updated_at"] = _now()
        return _save(conn, "scout_cycles", data)

    return await _run(_sync)


async def list_scout_cycles(limit: int = 50) -> list[dict[str, Any]]:
    return await _run(lambda conn: _sort_desc(_all(conn, "scout_cycles"), "started_at")[:_limit(limit)])


async def create_run(
    *,
    instance_id: str | None,
    pave_task_id: str | None,
    pave_work_item_id: str | None,
    pave_incident_id: str | None,
    pave_task_title: str,
    pave_board_name: str,
    staff_code: str,
    status: str = "queued",
    phase: str = "scout",
    workflow_id: str | None = None,
    workflow_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any]:
        now = _now()
        return _save(
            conn,
            "runs",
            {
                "id": _new_id(),
                "instance_id": instance_id,
                "pave_task_id": pave_task_id,
                "pave_work_item_id": pave_work_item_id,
                "pave_incident_id": pave_incident_id,
                "pave_task_title": pave_task_title,
                "pave_board_name": pave_board_name,
                "staff_code": staff_code,
                "status": status,
                "phase": phase,
                "failure_reason": None,
                "workflow_id": workflow_id,
                "workflow_name": workflow_name,
                "claim_attempted_at": None,
                "claimed_at": None,
                "started_at": None,
                "finished_at": None,
                "suspended_at": None,
                "assigned_to_staff_code": None,
                "quality_close_attempted": False,
                "quality_close_status": None,
                "e_doc_report_id": None,
                "e_doc_status": None,
                "dashboard_log": [],
                "metadata": metadata or {},
                "created_at": now,
                "updated_at": now,
            },
        )

    return await _run(_sync)


async def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    return await _run(lambda conn: _sort_desc(_all(conn, "runs"), "updated_at")[:_limit(limit)])


async def get_run(run_id: str) -> dict[str, Any] | None:
    return await _run(lambda conn: _get(conn, "runs", run_id))


async def update_run(
    run_id: str,
    *,
    status: str | None = None,
    phase: str | None = None,
    failure_reason: str | None = None,
    e_doc_status: str | None = None,
    e_doc_report_id: str | None = None,
    quality_close_attempted: bool | None = None,
    quality_close_status: str | None = None,
    assigned_to_staff_code: str | None = None,
    set_claim_attempted: bool = False,
    set_claimed: bool = False,
    set_started: bool = False,
    set_finished: bool = False,
    set_suspended: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any] | None:
        data = _get(conn, "runs", run_id)
        if data is None:
            return None
        for key, value in {
            "status": status,
            "phase": phase,
            "failure_reason": failure_reason,
            "e_doc_status": e_doc_status,
            "e_doc_report_id": e_doc_report_id,
            "quality_close_attempted": quality_close_attempted,
            "quality_close_status": quality_close_status,
            "assigned_to_staff_code": assigned_to_staff_code,
        }.items():
            if value is not None:
                data[key] = value
        now = _now()
        if set_claim_attempted:
            data["claim_attempted_at"] = now
        if set_claimed:
            data["claimed_at"] = now
        if set_started:
            data["started_at"] = now
        if set_finished:
            data["finished_at"] = now
        if set_suspended:
            data["suspended_at"] = now
        if metadata:
            data["metadata"] = {**(data.get("metadata") or {}), **metadata}
        data["updated_at"] = now
        return _save(conn, "runs", data)

    return await _run(_sync)


async def append_run_event(
    *,
    run_id: str | None,
    instance_id: str | None,
    level: str,
    phase: str,
    message: str,
    payload: dict[str, Any] | None = None,
    dashboard_visible: bool = True,
) -> dict[str, Any]:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any]:
        now = _now()
        event = _save(
            conn,
            "run_events",
            {
                "id": _new_id(),
                "run_id": run_id,
                "instance_id": instance_id,
                "level": level,
                "phase": phase,
                "message": message,
                "dashboard_visible": dashboard_visible,
                "payload": payload or {},
                "created_at": now,
                "updated_at": now,
            },
        )
        if run_id:
            _refresh_run_dashboard_log_sync(conn, run_id)
        return event

    return await _run(_sync)


async def refresh_run_dashboard_log(run_id: str) -> None:
    await _run(lambda conn: _refresh_run_dashboard_log_sync(conn, run_id))


async def list_run_events(run_id: str, limit: int = 500) -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _sort_asc(
            [item for item in _all(conn, "run_events") if item.get("run_id") == run_id],
            "created_at",
        )[:_limit(limit)]
    )


async def add_run_repository(
    *,
    run_id: str,
    repo_name: str,
    repo_path: str = "",
    remote_url: str = "",
    base_branch: str = "",
    branch_name: str = "",
    status: str = "planned",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any]:
        now = _now()
        return _save(
            conn,
            "run_repositories",
            {
                "id": _new_id(),
                "run_id": run_id,
                "repo_name": repo_name,
                "repo_path": repo_path,
                "remote_url": remote_url,
                "base_branch": base_branch,
                "branch_name": branch_name,
                "status": status,
                "pr_url": None,
                "pr_number": None,
                "commit_sha": None,
                "build_status": None,
                "test_status": None,
                "metadata": metadata or {},
                "created_at": now,
                "updated_at": now,
            },
        )

    return await _run(_sync)


async def list_run_repositories(run_id: str) -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _sort_asc(
            [item for item in _all(conn, "run_repositories") if item.get("run_id") == run_id],
            "created_at",
        )
    )


async def add_artifact(
    *,
    run_id: str | None,
    repository_id: str | None = None,
    category: str,
    name: str,
    status: str = "created",
    storage_uri: str | None = None,
    content_type: str | None = None,
    summary: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any]:
        now = _now()
        return _save(
            conn,
            "artifacts",
            {
                "id": _new_id(),
                "run_id": run_id,
                "repository_id": repository_id,
                "category": category,
                "name": name,
                "status": status,
                "storage_uri": storage_uri,
                "content_type": content_type,
                "summary": summary,
                "payload": payload or {},
                "created_at": now,
                "updated_at": now,
            },
        )

    return await _run(_sync)


async def list_artifacts(run_id: str) -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _sort_asc(
            [item for item in _all(conn, "artifacts") if item.get("run_id") == run_id],
            "created_at",
        )
    )


async def add_critic_report(
    *,
    run_id: str,
    node_id: str,
    status: str,
    summary: str | None = None,
    findings: list[dict[str, Any]] | None = None,
    score: float | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any]:
        now = _now()
        return _save(
            conn,
            "critic_reports",
            {
                "id": _new_id(),
                "run_id": run_id,
                "node_id": node_id,
                "status": status,
                "summary": summary,
                "findings": findings or [],
                "score": score,
                "payload": payload or {},
                "created_at": now,
                "updated_at": now,
            },
        )

    return await _run(_sync)


async def list_critic_reports(run_id: str) -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _sort_desc(
            [item for item in _all(conn, "critic_reports") if item.get("run_id") == run_id],
            "created_at",
        )
    )


async def create_learning_assessment(
    *,
    run_id: str | None,
    pave_task_id: str | None,
    status: str,
    generated_artifact_id: str | None = None,
    manual_changes_detected: bool = False,
    diff_summary: str | None = None,
    learnings: list[dict[str, Any]] | None = None,
    sbkb_document_id: str | None = None,
    sbkb_status: str | None = None,
) -> dict[str, Any]:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any]:
        now = _now()
        return _save(
            conn,
            "learning_assessments",
            {
                "id": _new_id(),
                "run_id": run_id,
                "pave_task_id": pave_task_id,
                "status": status,
                "generated_artifact_id": generated_artifact_id,
                "manual_changes_detected": manual_changes_detected,
                "diff_summary": diff_summary,
                "learnings": learnings or [],
                "sbkb_document_id": sbkb_document_id,
                "sbkb_status": sbkb_status,
                "created_at": now,
                "updated_at": now,
            },
        )

    return await _run(_sync)


async def list_learning_assessments(limit: int = 50) -> list[dict[str, Any]]:
    return await _run(lambda conn: _sort_desc(_all(conn, "learning_assessments"), "updated_at")[:_limit(limit)])


async def create_edoc_upload(
    *,
    run_id: str,
    pave_job_id: str | None,
    status: str,
    file_name: str,
    artifact_id: str | None = None,
    full_log_included: bool = False,
    critic_output_included: bool = False,
    error_message: str | None = None,
) -> dict[str, Any]:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any]:
        now = _now()
        return _save(
            conn,
            "edoc_uploads",
            {
                "id": _new_id(),
                "run_id": run_id,
                "pave_job_id": pave_job_id,
                "status": status,
                "document_id": None,
                "file_name": file_name,
                "artifact_id": artifact_id,
                "full_log_included": full_log_included,
                "critic_output_included": critic_output_included,
                "error_message": error_message,
                "created_at": now,
                "updated_at": now,
            },
        )

    return await _run(_sync)


async def list_edoc_uploads(run_id: str) -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _sort_desc(
            [item for item in _all(conn, "edoc_uploads") if item.get("run_id") == run_id],
            "created_at",
        )
    )


async def record_knowledge_query(
    *,
    run_id: str | None,
    service_name: str,
    query: str,
    status: str,
    result_count: int = 0,
    tokens_estimated: int = 0,
    citations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any]:
        now = _now()
        return _save(
            conn,
            "knowledge_queries",
            {
                "id": _new_id(),
                "run_id": run_id,
                "service_name": service_name,
                "query": query,
                "status": status,
                "result_count": result_count,
                "tokens_estimated": tokens_estimated,
                "citations": citations or [],
                "created_at": now,
                "updated_at": now,
            },
        )

    return await _run(_sync)


async def record_skill_invocation(
    *,
    run_id: str | None,
    skill_name: str,
    skill_source: str,
    version: str | None,
    phase: str,
    status: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any]:
        now = _now()
        return _save(
            conn,
            "skill_invocations",
            {
                "id": _new_id(),
                "run_id": run_id,
                "skill_name": skill_name,
                "skill_source": skill_source,
                "version": version,
                "phase": phase,
                "status": status,
                "started_at": None,
                "finished_at": None,
                "metadata": metadata or {},
                "created_at": now,
                "updated_at": now,
            },
        )

    return await _run(_sync)


async def upsert_tooling_inventory(
    *,
    instance_id: str | None,
    tool_type: str,
    name: str,
    installed_version: str | None,
    latest_version: str | None,
    status: str,
    source_url: str | None = None,
    update_available: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any]:
        existing = next(
            (
                item
                for item in _all(conn, "tooling_inventory")
                if item.get("instance_id") == instance_id
                and item.get("tool_type") == tool_type
                and item.get("name") == name
            ),
            None,
        )
        now = _now()
        data = {
            **(existing or {}),
            "id": (existing or {}).get("id", _new_id()),
            "instance_id": instance_id,
            "tool_type": tool_type,
            "name": name,
            "installed_version": installed_version,
            "latest_version": latest_version,
            "status": status,
            "source_url": source_url,
            "update_available": update_available,
            "last_checked_at": now,
            "metadata": metadata or {},
            "created_at": (existing or {}).get("created_at", now),
            "updated_at": now,
        }
        return _save(conn, "tooling_inventory", data)

    return await _run(_sync)


async def list_tooling_inventory() -> list[dict[str, Any]]:
    def _sync(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        live_instance_ids = _live_instance_ids(conn)
        rows = [
            item
            for item in _all(conn, "tooling_inventory")
            if not item.get("instance_id") or str(item.get("instance_id")) in live_instance_ids
        ]
        return sorted(
            rows,
            key=lambda item: (
                not bool(item.get("update_available")),
                str(item.get("updated_at") or ""),
                str(item.get("tool_type") or ""),
                str(item.get("name") or ""),
            ),
            reverse=False,
        )

    return await _run(_sync)


async def create_tooling_update_job(
    *,
    instance_id: str | None,
    tool_id: str | None,
    requested_by_user_id: str | None,
    from_version: str | None,
    to_version: str | None,
) -> dict[str, Any]:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any]:
        now = _now()
        return _save(
            conn,
            "tooling_update_jobs",
            {
                "id": _new_id(),
                "instance_id": instance_id,
                "tool_id": tool_id,
                "status": "queued",
                "requested_by_user_id": requested_by_user_id,
                "from_version": from_version,
                "to_version": to_version,
                "started_at": None,
                "finished_at": None,
                "log": [],
                "error_message": None,
                "created_at": now,
                "updated_at": now,
            },
        )

    return await _run(_sync)


async def list_tooling_update_jobs(limit: int = 50) -> list[dict[str, Any]]:
    return await _run(lambda conn: _sort_desc(_all(conn, "tooling_update_jobs"), "created_at")[:_limit(limit)])


async def update_tooling_update_job(
    job_id: str,
    *,
    status: str | None = None,
    log_entry: dict[str, Any] | None = None,
    error_message: str | None = None,
    set_started: bool = False,
    set_finished: bool = False,
) -> dict[str, Any] | None:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any] | None:
        data = _get(conn, "tooling_update_jobs", job_id)
        if data is None:
            return None
        if status is not None:
            data["status"] = status
        if set_started:
            data["started_at"] = _now()
        if set_finished:
            data["finished_at"] = _now()
        if log_entry is not None:
            data.setdefault("log", []).append(log_entry)
        if error_message is not None:
            data["error_message"] = error_message
        data["updated_at"] = _now()
        return _save(conn, "tooling_update_jobs", data)

    return await _run(_sync)


async def add_audit_entry(
    *,
    actor_type: str,
    actor_id: str,
    action: str,
    target_type: str,
    target_id: str,
    run_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any]:
        now = _now()
        return _save(
            conn,
            "audit_log",
            {
                "id": _new_id(),
                "actor_type": actor_type,
                "actor_id": actor_id,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "run_id": run_id,
                "payload": payload or {},
                "created_at": now,
                "updated_at": now,
            },
        )

    return await _run(_sync)


async def dashboard_summary() -> dict[str, Any]:
    def _sync(conn: sqlite3.Connection) -> dict[str, Any]:
        instances = _all(conn, "instances")
        live_instances = [item for item in instances if _is_live_instance(item)]
        runs = _all(conn, "runs")
        live_instance_ids = {str(item.get("id")) for item in live_instances}
        tooling = [
            item
            for item in _all(conn, "tooling_inventory")
            if not item.get("instance_id") or str(item.get("instance_id")) in live_instance_ids
        ]
        learning = _all(conn, "learning_assessments")
        stalled = [
            row
            for row in _latest_mcp_rows(_live_mcp_rows(conn, _all(conn, "mcp_readiness")))
            if row.get("status") in STALL_MCP_STATUSES
        ]
        return {
            "instances_total": len(live_instances),
            "instances_ready": sum(1 for item in live_instances if item.get("status") == "ready"),
            "instances_paused": sum(
                1 for item in live_instances if item.get("is_paused") or item.get("status") == "paused"
            ),
            "runs_active": sum(1 for item in runs if item.get("status") in ACTIVE_RUN_STATUSES),
            "runs_stalled": sum(1 for item in runs if item.get("status") == "stalled"),
            "runs_failed": sum(1 for item in runs if item.get("status") == "failed"),
            "tooling_updates_available": sum(1 for item in tooling if item.get("update_available")),
            "learning_pending": sum(
                1 for item in learning if item.get("status") in {"pending", "queued"}
            ),
            "stalled_mcp_count": len(stalled),
        }

    return await _run(_sync)


async def dashboard_failures(limit: int = 20) -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _sort_desc(
            [item for item in _all(conn, "runs") if item.get("status") in INTERRUPTED_RUN_STATUSES],
            "updated_at",
        )[:_limit(limit)]
    )


async def dashboard_throughput(days: int = 14) -> list[dict[str, Any]]:
    def _sync(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        cutoff = datetime.now(UTC) - timedelta(days=int(days))
        grouped: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"day": "", "total": 0, "completed": 0, "interrupted": 0}
        )
        for run in _all(conn, "runs"):
            created_raw = str(run.get("created_at") or "")
            try:
                created = datetime.fromisoformat(created_raw)
            except ValueError:
                continue
            if created < cutoff:
                continue
            day = created.date().isoformat()
            grouped[day]["day"] = day
            grouped[day]["total"] += 1
            if run.get("status") == "completed":
                grouped[day]["completed"] += 1
            if run.get("status") in INTERRUPTED_RUN_STATUSES:
                grouped[day]["interrupted"] += 1
        return [grouped[key] for key in sorted(grouped)]

    return await _run(_sync)
