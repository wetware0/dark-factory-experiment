"""Repository for the PAVE-driven Dark Factory portal.

The factory state is intentionally explicit: workers, dashboard routes, and
future Archon integrations all write through these functions so the portal can
show one authoritative operational log.
"""

from __future__ import annotations

import json
from typing import Any

from backend.db.postgres import get_pg_pool

Json = dict[str, Any] | list[Any]

JSON_KEYS = {
    "capabilities",
    "config",
    "metadata",
    "input_snapshot",
    "output_snapshot",
    "dashboard_log",
    "payload",
    "findings",
    "learnings",
    "citations",
    "log",
}


def _to_json(value: Any, default: Json | None = None) -> str:
    if value is None:
        value = {} if default is None else default
    return json.dumps(value)


def _decode_value(key: str, value: Any) -> Any:
    if key not in JSON_KEYS or not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _row_to_dict(row: Any | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    return {key: _decode_value(key, value) for key, value in data.items()}


def _rows_to_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    return [row for r in rows if (row := _row_to_dict(r)) is not None]


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
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO factory_instances (
                id, name, host_name, staff_code, detected_staff_code, board_name, status,
                version, process_id, capabilities, config, last_heartbeat_at, updated_at
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7,
                $8, $9, $10::jsonb, $11::jsonb, now(), now()
            )
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                host_name = EXCLUDED.host_name,
                staff_code = EXCLUDED.staff_code,
                detected_staff_code = EXCLUDED.detected_staff_code,
                board_name = EXCLUDED.board_name,
                status = EXCLUDED.status,
                version = EXCLUDED.version,
                process_id = EXCLUDED.process_id,
                capabilities = EXCLUDED.capabilities,
                config = EXCLUDED.config,
                last_heartbeat_at = now(),
                updated_at = now()
            RETURNING *
            """,
            instance_id,
            name,
            host_name,
            staff_code,
            detected_staff_code,
            board_name,
            status,
            version,
            process_id,
            _to_json(capabilities),
            _to_json(config),
        )
    result = _row_to_dict(row)
    assert result is not None
    return result


async def heartbeat_instance(
    instance_id: str,
    *,
    status: str,
    detected_staff_code: str | None = None,
    process_id: str | None = None,
) -> dict[str, Any] | None:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE factory_instances
            SET status = $2,
                detected_staff_code = COALESCE($3, detected_staff_code),
                process_id = COALESCE($4, process_id),
                last_heartbeat_at = now(),
                updated_at = now()
            WHERE id = $1
            RETURNING *
            """,
            instance_id,
            status,
            detected_staff_code,
            process_id,
        )
    return _row_to_dict(row)


async def pause_instance(instance_id: str, reason: str) -> dict[str, Any] | None:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE factory_instances
            SET is_paused = TRUE,
                paused_reason = $2,
                status = 'paused',
                updated_at = now()
            WHERE id = $1
            RETURNING *
            """,
            instance_id,
            reason,
        )
    return _row_to_dict(row)


async def resume_instance(instance_id: str) -> dict[str, Any] | None:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE factory_instances
            SET is_paused = FALSE,
                paused_reason = NULL,
                status = 'ready',
                updated_at = now()
            WHERE id = $1
            RETURNING *
            """,
            instance_id,
        )
    return _row_to_dict(row)


async def list_instances() -> list[dict[str, Any]]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM factory_instances ORDER BY updated_at DESC")
    return _rows_to_dicts(rows)


async def get_instance(instance_id: str) -> dict[str, Any] | None:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM factory_instances WHERE id = $1", instance_id)
    return _row_to_dict(row)


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
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO factory_mcp_readiness (
                instance_id, mcp_name, status, detail, auth_subject,
                reauth_url, expires_at, metadata, last_checked_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7::timestamptz, $8::jsonb, now(), now())
            RETURNING *
            """,
            instance_id,
            mcp_name,
            status,
            detail,
            auth_subject,
            reauth_url,
            expires_at,
            _to_json(metadata),
        )
    result = _row_to_dict(row)
    assert result is not None
    return result


async def list_latest_mcp_readiness(instance_id: str | None = None) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if instance_id is not None:
        params.append(instance_id)
        where = "WHERE instance_id = $1"
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT DISTINCT ON (COALESCE(instance_id, ''), mcp_name) *
            FROM factory_mcp_readiness
            {where}
            ORDER BY COALESCE(instance_id, ''), mcp_name, updated_at DESC
            """,
            *params,
        )
    return _rows_to_dicts(rows)


async def list_stalled_mcps() -> list[dict[str, Any]]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH latest AS (
                SELECT DISTINCT ON (COALESCE(instance_id, ''), mcp_name) *
                FROM factory_mcp_readiness
                ORDER BY COALESCE(instance_id, ''), mcp_name, updated_at DESC
            )
            SELECT *
            FROM latest
            WHERE status IN ('stale', 'unauthenticated', 'unavailable', 'degraded')
            ORDER BY updated_at DESC
            """
        )
    return _rows_to_dicts(rows)


async def create_reauth_session(
    *,
    instance_id: str | None,
    mcp_name: str,
    reauth_url: str | None,
    requested_by_user_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO factory_mcp_reauth_sessions (
                instance_id, mcp_name, reauth_url, requested_by_user_id, metadata
            )
            VALUES ($1, $2, $3, $4, $5::jsonb)
            RETURNING *
            """,
            instance_id,
            mcp_name,
            reauth_url,
            requested_by_user_id,
            _to_json(metadata),
        )
    result = _row_to_dict(row)
    assert result is not None
    return result


async def update_reauth_session(
    session_id: str,
    *,
    status: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    completed_expr = "now()" if status in {"complete", "verified", "cancelled"} else "completed_at"
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE factory_mcp_reauth_sessions
            SET status = $2,
                metadata = COALESCE($3::jsonb, metadata),
                completed_at = {completed_expr},
                updated_at = now()
            WHERE id = $1::uuid
            RETURNING *
            """,
            session_id,
            status,
            _to_json(metadata) if metadata is not None else None,
        )
    return _row_to_dict(row)


async def list_reauth_sessions() -> list[dict[str, Any]]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM factory_mcp_reauth_sessions ORDER BY created_at DESC LIMIT 100"
        )
    return _rows_to_dicts(rows)


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
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO factory_scout_cycles (
                instance_id, board_name, staff_code, status, active_pave_task_id,
                candidate_count, local_model, token_estimate, input_snapshot
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
            RETURNING *
            """,
            instance_id,
            board_name,
            staff_code,
            status,
            active_pave_task_id,
            candidate_count,
            local_model,
            token_estimate,
            _to_json(input_snapshot),
        )
    result = _row_to_dict(row)
    assert result is not None
    return result


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
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE factory_scout_cycles
            SET status = $2,
                selected_pave_task_id = $3,
                candidate_count = COALESCE($4, candidate_count),
                decision = $5,
                summary = $6,
                output_snapshot = $7::jsonb,
                finished_at = now()
            WHERE id = $1::uuid
            RETURNING *
            """,
            cycle_id,
            status,
            selected_pave_task_id,
            candidate_count,
            decision,
            summary,
            _to_json(output_snapshot),
        )
    return _row_to_dict(row)


async def list_scout_cycles(limit: int = 50) -> list[dict[str, Any]]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM factory_scout_cycles ORDER BY started_at DESC LIMIT $1",
            limit,
        )
    return _rows_to_dicts(rows)


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
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO factory_runs (
                instance_id, pave_task_id, pave_work_item_id, pave_incident_id,
                pave_task_title, pave_board_name, staff_code, status, phase,
                workflow_id, workflow_name, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb)
            RETURNING *
            """,
            instance_id,
            pave_task_id,
            pave_work_item_id,
            pave_incident_id,
            pave_task_title,
            pave_board_name,
            staff_code,
            status,
            phase,
            workflow_id,
            workflow_name,
            _to_json(metadata),
        )
    result = _row_to_dict(row)
    assert result is not None
    return result


async def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT *
            FROM factory_runs
            ORDER BY updated_at DESC
            LIMIT $1
            """,
            limit,
        )
    return _rows_to_dicts(rows)


async def get_run(run_id: str) -> dict[str, Any] | None:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM factory_runs WHERE id = $1::uuid", run_id)
    return _row_to_dict(row)


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
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE factory_runs
            SET status = COALESCE($2, status),
                phase = COALESCE($3, phase),
                failure_reason = COALESCE($4, failure_reason),
                e_doc_status = COALESCE($5, e_doc_status),
                e_doc_report_id = COALESCE($6, e_doc_report_id),
                quality_close_attempted = COALESCE($7, quality_close_attempted),
                quality_close_status = COALESCE($8, quality_close_status),
                assigned_to_staff_code = COALESCE($9, assigned_to_staff_code),
                claim_attempted_at = CASE WHEN $10 THEN now() ELSE claim_attempted_at END,
                claimed_at = CASE WHEN $11 THEN now() ELSE claimed_at END,
                started_at = CASE WHEN $12 THEN now() ELSE started_at END,
                finished_at = CASE WHEN $13 THEN now() ELSE finished_at END,
                suspended_at = CASE WHEN $14 THEN now() ELSE suspended_at END,
                metadata = CASE WHEN $15::jsonb IS NULL THEN metadata ELSE metadata || $15::jsonb END,
                updated_at = now()
            WHERE id = $1::uuid
            RETURNING *
            """,
            run_id,
            status,
            phase,
            failure_reason,
            e_doc_status,
            e_doc_report_id,
            quality_close_attempted,
            quality_close_status,
            assigned_to_staff_code,
            set_claim_attempted,
            set_claimed,
            set_started,
            set_finished,
            set_suspended,
            _to_json(metadata) if metadata is not None else None,
        )
    return _row_to_dict(row)


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
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO factory_run_events (
                run_id, instance_id, level, phase, message, payload, dashboard_visible
            )
            VALUES ($1::uuid, $2, $3, $4, $5, $6::jsonb, $7)
            RETURNING *
            """,
            run_id,
            instance_id,
            level,
            phase,
            message,
            _to_json(payload),
            dashboard_visible,
        )
    result = _row_to_dict(row)
    assert result is not None
    if run_id:
        await refresh_run_dashboard_log(run_id)
    return result


async def refresh_run_dashboard_log(run_id: str) -> None:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE factory_runs
            SET dashboard_log = COALESCE((
                    SELECT jsonb_agg(
                        jsonb_build_object(
                            'created_at', created_at,
                            'level', level,
                            'phase', phase,
                            'message', message,
                            'payload', payload
                        )
                        ORDER BY created_at
                    )
                    FROM factory_run_events
                    WHERE run_id = $1::uuid AND dashboard_visible = TRUE
                ), '[]'::jsonb),
                updated_at = now()
            WHERE id = $1::uuid
            """,
            run_id,
        )


async def list_run_events(run_id: str, limit: int = 500) -> list[dict[str, Any]]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT *
            FROM factory_run_events
            WHERE run_id = $1::uuid
            ORDER BY created_at ASC
            LIMIT $2
            """,
            run_id,
            limit,
        )
    return _rows_to_dicts(rows)


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
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO factory_run_repositories (
                run_id, repo_name, repo_path, remote_url, base_branch,
                branch_name, status, metadata
            )
            VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8::jsonb)
            RETURNING *
            """,
            run_id,
            repo_name,
            repo_path,
            remote_url,
            base_branch,
            branch_name,
            status,
            _to_json(metadata),
        )
    result = _row_to_dict(row)
    assert result is not None
    return result


async def list_run_repositories(run_id: str) -> list[dict[str, Any]]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT *
            FROM factory_run_repositories
            WHERE run_id = $1::uuid
            ORDER BY created_at ASC
            """,
            run_id,
        )
    return _rows_to_dicts(rows)


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
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO factory_artifacts (
                run_id, repository_id, category, name, status,
                storage_uri, content_type, summary, payload
            )
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9::jsonb)
            RETURNING *
            """,
            run_id,
            repository_id,
            category,
            name,
            status,
            storage_uri,
            content_type,
            summary,
            _to_json(payload),
        )
    result = _row_to_dict(row)
    assert result is not None
    return result


async def list_artifacts(run_id: str) -> list[dict[str, Any]]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT *
            FROM factory_artifacts
            WHERE run_id = $1::uuid
            ORDER BY created_at ASC
            """,
            run_id,
        )
    return _rows_to_dicts(rows)


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
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO factory_critic_reports (
                run_id, node_id, status, summary, findings, score, payload
            )
            VALUES ($1::uuid, $2, $3, $4, $5::jsonb, $6, $7::jsonb)
            RETURNING *
            """,
            run_id,
            node_id,
            status,
            summary,
            _to_json(findings, []),
            score,
            _to_json(payload),
        )
    result = _row_to_dict(row)
    assert result is not None
    return result


async def list_critic_reports(run_id: str) -> list[dict[str, Any]]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT *
            FROM factory_critic_reports
            WHERE run_id = $1::uuid
            ORDER BY created_at DESC
            """,
            run_id,
        )
    return _rows_to_dicts(rows)


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
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO factory_learning_assessments (
                run_id, pave_task_id, status, generated_artifact_id,
                manual_changes_detected, diff_summary, learnings,
                sbkb_document_id, sbkb_status
            )
            VALUES ($1::uuid, $2, $3, $4::uuid, $5, $6, $7::jsonb, $8, $9)
            RETURNING *
            """,
            run_id,
            pave_task_id,
            status,
            generated_artifact_id,
            manual_changes_detected,
            diff_summary,
            _to_json(learnings, []),
            sbkb_document_id,
            sbkb_status,
        )
    result = _row_to_dict(row)
    assert result is not None
    return result


async def list_learning_assessments(limit: int = 50) -> list[dict[str, Any]]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM factory_learning_assessments ORDER BY updated_at DESC LIMIT $1",
            limit,
        )
    return _rows_to_dicts(rows)


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
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO factory_edoc_uploads (
                run_id, pave_job_id, status, file_name, artifact_id,
                full_log_included, critic_output_included, error_message
            )
            VALUES ($1::uuid, $2, $3, $4, $5::uuid, $6, $7, $8)
            RETURNING *
            """,
            run_id,
            pave_job_id,
            status,
            file_name,
            artifact_id,
            full_log_included,
            critic_output_included,
            error_message,
        )
    result = _row_to_dict(row)
    assert result is not None
    return result


async def list_edoc_uploads(run_id: str) -> list[dict[str, Any]]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT *
            FROM factory_edoc_uploads
            WHERE run_id = $1::uuid
            ORDER BY created_at DESC
            """,
            run_id,
        )
    return _rows_to_dicts(rows)


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
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO factory_knowledge_queries (
                run_id, service_name, query, status, result_count,
                tokens_estimated, citations
            )
            VALUES ($1::uuid, $2, $3, $4, $5, $6, $7::jsonb)
            RETURNING *
            """,
            run_id,
            service_name,
            query,
            status,
            result_count,
            tokens_estimated,
            _to_json(citations, []),
        )
    result = _row_to_dict(row)
    assert result is not None
    return result


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
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO factory_skill_invocations (
                run_id, skill_name, skill_source, version, phase, status, metadata
            )
            VALUES ($1::uuid, $2, $3, $4, $5, $6, $7::jsonb)
            RETURNING *
            """,
            run_id,
            skill_name,
            skill_source,
            version,
            phase,
            status,
            _to_json(metadata),
        )
    result = _row_to_dict(row)
    assert result is not None
    return result


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
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            """
            SELECT id
            FROM factory_tooling_inventory
            WHERE COALESCE(instance_id, '') = COALESCE($1, '')
              AND tool_type = $2
              AND name = $3
            """,
            instance_id,
            tool_type,
            name,
        )
        if existing:
            row = await conn.fetchrow(
                """
                UPDATE factory_tooling_inventory
                SET installed_version = $2,
                    latest_version = $3,
                    status = $4,
                    source_url = $5,
                    update_available = $6,
                    metadata = $7::jsonb,
                    last_checked_at = now(),
                    updated_at = now()
                WHERE id = $1
                RETURNING *
                """,
                existing["id"],
                installed_version,
                latest_version,
                status,
                source_url,
                update_available,
                _to_json(metadata),
            )
        else:
            row = await conn.fetchrow(
                """
                INSERT INTO factory_tooling_inventory (
                    instance_id, tool_type, name, installed_version, latest_version,
                    status, source_url, update_available, last_checked_at, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now(), $9::jsonb)
                RETURNING *
                """,
                instance_id,
                tool_type,
                name,
                installed_version,
                latest_version,
                status,
                source_url,
                update_available,
                _to_json(metadata),
            )
    result = _row_to_dict(row)
    assert result is not None
    return result


async def list_tooling_inventory() -> list[dict[str, Any]]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT *
            FROM factory_tooling_inventory
            ORDER BY update_available DESC, updated_at DESC, tool_type, name
            """
        )
    return _rows_to_dicts(rows)


async def create_tooling_update_job(
    *,
    instance_id: str | None,
    tool_id: str | None,
    requested_by_user_id: str | None,
    from_version: str | None,
    to_version: str | None,
) -> dict[str, Any]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO factory_tooling_update_jobs (
                instance_id, tool_id, requested_by_user_id, from_version, to_version
            )
            VALUES ($1, $2::uuid, $3, $4, $5)
            RETURNING *
            """,
            instance_id,
            tool_id,
            requested_by_user_id,
            from_version,
            to_version,
        )
    result = _row_to_dict(row)
    assert result is not None
    return result


async def list_tooling_update_jobs(limit: int = 50) -> list[dict[str, Any]]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM factory_tooling_update_jobs ORDER BY created_at DESC LIMIT $1",
            limit,
        )
    return _rows_to_dicts(rows)


async def update_tooling_update_job(
    job_id: str,
    *,
    status: str | None = None,
    log_entry: dict[str, Any] | None = None,
    error_message: str | None = None,
    set_started: bool = False,
    set_finished: bool = False,
) -> dict[str, Any] | None:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE factory_tooling_update_jobs
            SET status = COALESCE($2, status),
                started_at = CASE WHEN $3 THEN now() ELSE started_at END,
                finished_at = CASE WHEN $4 THEN now() ELSE finished_at END,
                log = CASE
                    WHEN $5::jsonb IS NULL THEN log
                    ELSE log || jsonb_build_array($5::jsonb)
                END,
                error_message = COALESCE($6, error_message)
            WHERE id = $1::uuid
            RETURNING *
            """,
            job_id,
            status,
            set_started,
            set_finished,
            _to_json(log_entry) if log_entry is not None else None,
            error_message,
        )
    return _row_to_dict(row)


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
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO factory_audit_log (
                actor_type, actor_id, action, target_type, target_id, run_id, payload
            )
            VALUES ($1, $2, $3, $4, $5, $6::uuid, $7::jsonb)
            RETURNING *
            """,
            actor_type,
            actor_id,
            action,
            target_type,
            target_id,
            run_id,
            _to_json(payload),
        )
    result = _row_to_dict(row)
    assert result is not None
    return result


async def dashboard_summary() -> dict[str, Any]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                (SELECT count(*) FROM factory_instances) AS instances_total,
                (SELECT count(*) FROM factory_instances WHERE status = 'ready') AS instances_ready,
                (SELECT count(*) FROM factory_instances WHERE is_paused OR status = 'paused')
                    AS instances_paused,
                (SELECT count(*) FROM factory_runs WHERE status IN ('queued', 'claimed', 'running'))
                    AS runs_active,
                (SELECT count(*) FROM factory_runs WHERE status = 'stalled') AS runs_stalled,
                (SELECT count(*) FROM factory_runs WHERE status = 'failed') AS runs_failed,
                (SELECT count(*) FROM factory_tooling_inventory WHERE update_available)
                    AS tooling_updates_available,
                (SELECT count(*) FROM factory_learning_assessments WHERE status IN ('pending', 'queued'))
                    AS learning_pending
            """
        )
    data = _row_to_dict(row)
    assert data is not None
    stalled = await list_stalled_mcps()
    data["stalled_mcp_count"] = len(stalled)
    return data


async def dashboard_failures(limit: int = 20) -> list[dict[str, Any]]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT *
            FROM factory_runs
            WHERE status IN ('stalled', 'failed', 'suspended')
            ORDER BY updated_at DESC
            LIMIT $1
            """,
            limit,
        )
    return _rows_to_dicts(rows)


async def dashboard_throughput(days: int = 14) -> list[dict[str, Any]]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                date_trunc('day', created_at) AS day,
                count(*) AS total,
                count(*) FILTER (WHERE status = 'completed') AS completed,
                count(*) FILTER (WHERE status IN ('failed', 'stalled', 'suspended')) AS interrupted
            FROM factory_runs
            WHERE created_at >= now() - ($1::text || ' days')::interval
            GROUP BY date_trunc('day', created_at)
            ORDER BY day ASC
            """,
            str(days),
        )
    return _rows_to_dicts(rows)
