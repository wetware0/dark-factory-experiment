"""SQL Server repository for the PAVE factory portal.

This is intentionally separate from the existing DynaChat Postgres repository.
The factory portal state is operational metadata and fits WTG's standard SQL
Server footprint without needing pgvector or Postgres full-text features.
"""

from __future__ import annotations

import asyncio
import struct
import json
import threading
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any, TypeVar

import pyodbc

from backend import config

Json = dict[str, Any] | list[Any]
T = TypeVar("T")

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

_schema_ready = False
_schema_lock = threading.Lock()


def _connection_string() -> str:
    if not config.FACTORY_SQLSERVER_CONNECTION_STRING:
        raise RuntimeError(
            "FACTORY_STORAGE_PROVIDER=sqlserver requires "
            "FACTORY_SQLSERVER_CONNECTION_STRING."
        )
    return config.FACTORY_SQLSERVER_CONNECTION_STRING


def _handle_datetimeoffset(value: bytes) -> datetime:
    year, month, day, hour, minute, second, fraction, tz_hour, tz_minute = struct.unpack(
        "<6hI2h",
        value,
    )
    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        second,
        fraction // 1000,
        timezone(timedelta(hours=tz_hour, minutes=tz_minute)),
    )


def _connect() -> pyodbc.Connection:
    conn = pyodbc.connect(_connection_string(), autocommit=False)
    conn.add_output_converter(-155, _handle_datetimeoffset)
    return conn


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


def _normalize_value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _row_to_dict(cursor: pyodbc.Cursor, row: pyodbc.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    columns = [column[0] for column in cursor.description]
    data = {key: _normalize_value(value) for key, value in zip(columns, row, strict=False)}
    return {key: _decode_value(key, value) for key, value in data.items()}


def _fetch_one(conn: pyodbc.Connection, sql: str, *params: Any) -> dict[str, Any] | None:
    cursor = conn.cursor()
    row = cursor.execute(sql, params).fetchone()
    return _row_to_dict(cursor, row)


def _fetch_all(conn: pyodbc.Connection, sql: str, *params: Any) -> list[dict[str, Any]]:
    cursor = conn.cursor()
    rows = cursor.execute(sql, params).fetchall()
    return [item for row in rows if (item := _row_to_dict(cursor, row)) is not None]


def _execute(conn: pyodbc.Connection, sql: str, *params: Any) -> None:
    conn.cursor().execute(sql, params)


def _new_id() -> str:
    return str(uuid.uuid4())


def _top(limit: int) -> int:
    return max(1, min(int(limit), 5000))


def _instance_stale_seconds() -> int:
    return max(1, int(config.FACTORY_INSTANCE_STALE_SECONDS))


def _ensure_schema(conn: pyodbc.Connection) -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        cursor = conn.cursor()
        for statement in SQLSERVER_SCHEMA:
            cursor.execute(statement)
        conn.commit()
        _schema_ready = True


async def _run(fn: Callable[[pyodbc.Connection], T]) -> T:
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


SQLSERVER_SCHEMA = [
    """
    IF OBJECT_ID('dbo.factory_instances', 'U') IS NULL
    CREATE TABLE dbo.factory_instances (
        id NVARCHAR(200) NOT NULL PRIMARY KEY,
        name NVARCHAR(400) NOT NULL,
        host_name NVARCHAR(400) NOT NULL CONSTRAINT DF_factory_instances_host DEFAULT '',
        staff_code NVARCHAR(50) NOT NULL CONSTRAINT DF_factory_instances_staff DEFAULT '',
        detected_staff_code NVARCHAR(50) NULL,
        board_name NVARCHAR(400) NOT NULL CONSTRAINT DF_factory_instances_board DEFAULT '',
        status NVARCHAR(80) NOT NULL CONSTRAINT DF_factory_instances_status DEFAULT 'starting',
        is_paused BIT NOT NULL CONSTRAINT DF_factory_instances_paused DEFAULT 0,
        paused_reason NVARCHAR(MAX) NULL,
        version NVARCHAR(200) NULL,
        process_id NVARCHAR(100) NULL,
        capabilities NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_instances_cap DEFAULT '{}',
        config NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_instances_config DEFAULT '{}',
        last_heartbeat_at DATETIMEOFFSET NULL,
        created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_instances_created DEFAULT SYSDATETIMEOFFSET(),
        updated_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_instances_updated DEFAULT SYSDATETIMEOFFSET()
    )
    """,
    """
    IF OBJECT_ID('dbo.factory_mcp_readiness', 'U') IS NULL
    CREATE TABLE dbo.factory_mcp_readiness (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        instance_id NVARCHAR(200) NULL REFERENCES dbo.factory_instances(id),
        mcp_name NVARCHAR(100) NOT NULL,
        status NVARCHAR(80) NOT NULL CONSTRAINT DF_factory_mcp_readiness_status DEFAULT 'checking',
        detail NVARCHAR(MAX) NULL,
        auth_subject NVARCHAR(400) NULL,
        reauth_url NVARCHAR(MAX) NULL,
        last_checked_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_mcp_readiness_checked DEFAULT SYSDATETIMEOFFSET(),
        expires_at DATETIMEOFFSET NULL,
        metadata NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_mcp_readiness_metadata DEFAULT '{}',
        updated_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_mcp_readiness_updated DEFAULT SYSDATETIMEOFFSET()
    )
    """,
    """
    IF OBJECT_ID('dbo.factory_mcp_reauth_sessions', 'U') IS NULL
    CREATE TABLE dbo.factory_mcp_reauth_sessions (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        instance_id NVARCHAR(200) NULL REFERENCES dbo.factory_instances(id),
        mcp_name NVARCHAR(100) NOT NULL,
        status NVARCHAR(80) NOT NULL CONSTRAINT DF_factory_mcp_reauth_status DEFAULT 'requested',
        reauth_url NVARCHAR(MAX) NULL,
        requested_by_user_id NVARCHAR(200) NULL,
        completed_at DATETIMEOFFSET NULL,
        metadata NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_mcp_reauth_metadata DEFAULT '{}',
        created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_mcp_reauth_created DEFAULT SYSDATETIMEOFFSET(),
        updated_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_mcp_reauth_updated DEFAULT SYSDATETIMEOFFSET()
    )
    """,
    """
    IF OBJECT_ID('dbo.factory_scout_cycles', 'U') IS NULL
    CREATE TABLE dbo.factory_scout_cycles (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        instance_id NVARCHAR(200) NULL REFERENCES dbo.factory_instances(id),
        board_name NVARCHAR(400) NOT NULL,
        staff_code NVARCHAR(50) NOT NULL,
        status NVARCHAR(80) NOT NULL CONSTRAINT DF_factory_scout_cycles_status DEFAULT 'running',
        started_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_scout_cycles_started DEFAULT SYSDATETIMEOFFSET(),
        finished_at DATETIMEOFFSET NULL,
        active_pave_task_id NVARCHAR(200) NULL,
        candidate_count INT NOT NULL CONSTRAINT DF_factory_scout_cycles_candidates DEFAULT 0,
        selected_pave_task_id NVARCHAR(200) NULL,
        decision NVARCHAR(200) NULL,
        local_model NVARCHAR(200) NULL,
        token_estimate INT NOT NULL CONSTRAINT DF_factory_scout_cycles_tokens DEFAULT 0,
        summary NVARCHAR(MAX) NULL,
        input_snapshot NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_scout_cycles_input DEFAULT '{}',
        output_snapshot NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_scout_cycles_output DEFAULT '{}'
    )
    """,
    """
    IF OBJECT_ID('dbo.factory_runs', 'U') IS NULL
    CREATE TABLE dbo.factory_runs (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        instance_id NVARCHAR(200) NULL REFERENCES dbo.factory_instances(id),
        pave_task_id NVARCHAR(200) NULL,
        pave_work_item_id NVARCHAR(200) NULL,
        pave_incident_id NVARCHAR(200) NULL,
        pave_task_title NVARCHAR(1000) NOT NULL CONSTRAINT DF_factory_runs_title DEFAULT '',
        pave_board_name NVARCHAR(400) NOT NULL CONSTRAINT DF_factory_runs_board DEFAULT '',
        staff_code NVARCHAR(50) NOT NULL CONSTRAINT DF_factory_runs_staff DEFAULT '',
        status NVARCHAR(80) NOT NULL CONSTRAINT DF_factory_runs_status DEFAULT 'queued',
        phase NVARCHAR(100) NOT NULL CONSTRAINT DF_factory_runs_phase DEFAULT 'scout',
        failure_reason NVARCHAR(MAX) NULL,
        workflow_id NVARCHAR(200) NULL,
        workflow_name NVARCHAR(400) NULL,
        claim_attempted_at DATETIMEOFFSET NULL,
        claimed_at DATETIMEOFFSET NULL,
        started_at DATETIMEOFFSET NULL,
        finished_at DATETIMEOFFSET NULL,
        suspended_at DATETIMEOFFSET NULL,
        assigned_to_staff_code NVARCHAR(50) NULL,
        quality_close_attempted BIT NOT NULL CONSTRAINT DF_factory_runs_quality_attempt DEFAULT 0,
        quality_close_status NVARCHAR(100) NULL,
        e_doc_report_id NVARCHAR(200) NULL,
        e_doc_status NVARCHAR(100) NULL,
        dashboard_log NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_runs_log DEFAULT '[]',
        metadata NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_runs_metadata DEFAULT '{}',
        created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_runs_created DEFAULT SYSDATETIMEOFFSET(),
        updated_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_runs_updated DEFAULT SYSDATETIMEOFFSET()
    )
    """,
    """
    IF OBJECT_ID('dbo.factory_run_events', 'U') IS NULL
    CREATE TABLE dbo.factory_run_events (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        run_id UNIQUEIDENTIFIER NULL REFERENCES dbo.factory_runs(id),
        instance_id NVARCHAR(200) NULL REFERENCES dbo.factory_instances(id),
        level NVARCHAR(80) NOT NULL CONSTRAINT DF_factory_run_events_level DEFAULT 'info',
        phase NVARCHAR(100) NOT NULL CONSTRAINT DF_factory_run_events_phase DEFAULT '',
        message NVARCHAR(MAX) NOT NULL,
        dashboard_visible BIT NOT NULL CONSTRAINT DF_factory_run_events_visible DEFAULT 1,
        payload NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_run_events_payload DEFAULT '{}',
        created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_run_events_created DEFAULT SYSDATETIMEOFFSET()
    )
    """,
    """
    IF OBJECT_ID('dbo.factory_run_repositories', 'U') IS NULL
    CREATE TABLE dbo.factory_run_repositories (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        run_id UNIQUEIDENTIFIER NOT NULL REFERENCES dbo.factory_runs(id),
        repo_name NVARCHAR(400) NOT NULL,
        repo_path NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_repos_path DEFAULT '',
        remote_url NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_repos_remote DEFAULT '',
        base_branch NVARCHAR(400) NOT NULL CONSTRAINT DF_factory_repos_base DEFAULT '',
        branch_name NVARCHAR(400) NOT NULL CONSTRAINT DF_factory_repos_branch DEFAULT '',
        status NVARCHAR(80) NOT NULL CONSTRAINT DF_factory_repos_status DEFAULT 'planned',
        pr_url NVARCHAR(MAX) NULL,
        pr_number NVARCHAR(100) NULL,
        commit_sha NVARCHAR(100) NULL,
        build_status NVARCHAR(100) NULL,
        test_status NVARCHAR(100) NULL,
        metadata NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_repos_metadata DEFAULT '{}',
        created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_repos_created DEFAULT SYSDATETIMEOFFSET(),
        updated_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_repos_updated DEFAULT SYSDATETIMEOFFSET()
    )
    """,
    """
    IF OBJECT_ID('dbo.factory_artifacts', 'U') IS NULL
    CREATE TABLE dbo.factory_artifacts (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        run_id UNIQUEIDENTIFIER NULL REFERENCES dbo.factory_runs(id),
        repository_id UNIQUEIDENTIFIER NULL REFERENCES dbo.factory_run_repositories(id),
        category NVARCHAR(100) NOT NULL,
        name NVARCHAR(400) NOT NULL,
        status NVARCHAR(80) NOT NULL CONSTRAINT DF_factory_artifacts_status DEFAULT 'created',
        storage_uri NVARCHAR(MAX) NULL,
        content_type NVARCHAR(200) NULL,
        summary NVARCHAR(MAX) NULL,
        payload NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_artifacts_payload DEFAULT '{}',
        created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_artifacts_created DEFAULT SYSDATETIMEOFFSET()
    )
    """,
    """
    IF OBJECT_ID('dbo.factory_critic_reports', 'U') IS NULL
    CREATE TABLE dbo.factory_critic_reports (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        run_id UNIQUEIDENTIFIER NOT NULL REFERENCES dbo.factory_runs(id),
        node_id NVARCHAR(100) NOT NULL CONSTRAINT DF_factory_critic_node DEFAULT 'critic',
        status NVARCHAR(80) NOT NULL CONSTRAINT DF_factory_critic_status DEFAULT 'pending',
        summary NVARCHAR(MAX) NULL,
        findings NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_critic_findings DEFAULT '[]',
        score DECIMAL(10, 4) NULL,
        payload NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_critic_payload DEFAULT '{}',
        created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_critic_created DEFAULT SYSDATETIMEOFFSET()
    )
    """,
    """
    IF OBJECT_ID('dbo.factory_learning_assessments', 'U') IS NULL
    CREATE TABLE dbo.factory_learning_assessments (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        run_id UNIQUEIDENTIFIER NULL REFERENCES dbo.factory_runs(id),
        pave_task_id NVARCHAR(200) NULL,
        status NVARCHAR(80) NOT NULL CONSTRAINT DF_factory_learning_status DEFAULT 'pending',
        generated_artifact_id UNIQUEIDENTIFIER NULL REFERENCES dbo.factory_artifacts(id),
        manual_changes_detected BIT NOT NULL CONSTRAINT DF_factory_learning_manual DEFAULT 0,
        diff_summary NVARCHAR(MAX) NULL,
        learnings NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_learning_learnings DEFAULT '[]',
        sbkb_document_id NVARCHAR(200) NULL,
        sbkb_status NVARCHAR(100) NULL,
        created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_learning_created DEFAULT SYSDATETIMEOFFSET(),
        updated_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_learning_updated DEFAULT SYSDATETIMEOFFSET()
    )
    """,
    """
    IF OBJECT_ID('dbo.factory_edoc_uploads', 'U') IS NULL
    CREATE TABLE dbo.factory_edoc_uploads (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        run_id UNIQUEIDENTIFIER NOT NULL REFERENCES dbo.factory_runs(id),
        pave_job_id NVARCHAR(200) NULL,
        status NVARCHAR(80) NOT NULL CONSTRAINT DF_factory_edoc_status DEFAULT 'pending',
        document_id NVARCHAR(200) NULL,
        file_name NVARCHAR(400) NOT NULL CONSTRAINT DF_factory_edoc_file DEFAULT '',
        artifact_id UNIQUEIDENTIFIER NULL REFERENCES dbo.factory_artifacts(id),
        full_log_included BIT NOT NULL CONSTRAINT DF_factory_edoc_log DEFAULT 0,
        critic_output_included BIT NOT NULL CONSTRAINT DF_factory_edoc_critic DEFAULT 0,
        error_message NVARCHAR(MAX) NULL,
        created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_edoc_created DEFAULT SYSDATETIMEOFFSET(),
        updated_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_edoc_updated DEFAULT SYSDATETIMEOFFSET()
    )
    """,
    """
    IF OBJECT_ID('dbo.factory_knowledge_queries', 'U') IS NULL
    CREATE TABLE dbo.factory_knowledge_queries (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        run_id UNIQUEIDENTIFIER NULL REFERENCES dbo.factory_runs(id),
        service_name NVARCHAR(100) NOT NULL,
        query NVARCHAR(MAX) NOT NULL,
        status NVARCHAR(80) NOT NULL CONSTRAINT DF_factory_knowledge_status DEFAULT 'planned',
        result_count INT NOT NULL CONSTRAINT DF_factory_knowledge_count DEFAULT 0,
        tokens_estimated INT NOT NULL CONSTRAINT DF_factory_knowledge_tokens DEFAULT 0,
        citations NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_knowledge_citations DEFAULT '[]',
        created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_knowledge_created DEFAULT SYSDATETIMEOFFSET()
    )
    """,
    """
    IF OBJECT_ID('dbo.factory_skill_invocations', 'U') IS NULL
    CREATE TABLE dbo.factory_skill_invocations (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        run_id UNIQUEIDENTIFIER NULL REFERENCES dbo.factory_runs(id),
        skill_name NVARCHAR(300) NOT NULL,
        skill_source NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_skill_source DEFAULT '',
        version NVARCHAR(100) NULL,
        phase NVARCHAR(100) NOT NULL CONSTRAINT DF_factory_skill_phase DEFAULT '',
        status NVARCHAR(80) NOT NULL CONSTRAINT DF_factory_skill_status DEFAULT 'planned',
        started_at DATETIMEOFFSET NULL,
        finished_at DATETIMEOFFSET NULL,
        metadata NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_skill_metadata DEFAULT '{}',
        created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_skill_created DEFAULT SYSDATETIMEOFFSET()
    )
    """,
    """
    IF OBJECT_ID('dbo.factory_tooling_inventory', 'U') IS NULL
    CREATE TABLE dbo.factory_tooling_inventory (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        instance_id NVARCHAR(200) NULL REFERENCES dbo.factory_instances(id),
        tool_type NVARCHAR(100) NOT NULL,
        name NVARCHAR(300) NOT NULL,
        installed_version NVARCHAR(200) NULL,
        latest_version NVARCHAR(200) NULL,
        status NVARCHAR(80) NOT NULL CONSTRAINT DF_factory_tooling_status DEFAULT 'unknown',
        source_url NVARCHAR(MAX) NULL,
        update_available BIT NOT NULL CONSTRAINT DF_factory_tooling_update DEFAULT 0,
        last_checked_at DATETIMEOFFSET NULL,
        metadata NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_tooling_metadata DEFAULT '{}',
        created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_tooling_created DEFAULT SYSDATETIMEOFFSET(),
        updated_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_tooling_updated DEFAULT SYSDATETIMEOFFSET()
    )
    """,
    """
    IF OBJECT_ID('dbo.factory_tooling_update_jobs', 'U') IS NULL
    CREATE TABLE dbo.factory_tooling_update_jobs (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        instance_id NVARCHAR(200) NULL REFERENCES dbo.factory_instances(id),
        tool_id UNIQUEIDENTIFIER NULL REFERENCES dbo.factory_tooling_inventory(id),
        status NVARCHAR(80) NOT NULL CONSTRAINT DF_factory_tooling_jobs_status DEFAULT 'queued',
        requested_by_user_id NVARCHAR(200) NULL,
        from_version NVARCHAR(200) NULL,
        to_version NVARCHAR(200) NULL,
        started_at DATETIMEOFFSET NULL,
        finished_at DATETIMEOFFSET NULL,
        log NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_tooling_jobs_log DEFAULT '[]',
        error_message NVARCHAR(MAX) NULL,
        created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_tooling_jobs_created DEFAULT SYSDATETIMEOFFSET()
    )
    """,
    """
    IF OBJECT_ID('dbo.factory_audit_log', 'U') IS NULL
    CREATE TABLE dbo.factory_audit_log (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        actor_type NVARCHAR(100) NOT NULL,
        actor_id NVARCHAR(300) NOT NULL CONSTRAINT DF_factory_audit_actor DEFAULT '',
        action NVARCHAR(200) NOT NULL,
        target_type NVARCHAR(100) NOT NULL,
        target_id NVARCHAR(300) NOT NULL CONSTRAINT DF_factory_audit_target DEFAULT '',
        run_id UNIQUEIDENTIFIER NULL REFERENCES dbo.factory_runs(id),
        payload NVARCHAR(MAX) NOT NULL CONSTRAINT DF_factory_audit_payload DEFAULT '{}',
        created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_factory_audit_created DEFAULT SYSDATETIMEOFFSET()
    )
    """,
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_factory_instances_status') CREATE INDEX IX_factory_instances_status ON dbo.factory_instances (status, is_paused)",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_factory_instances_heartbeat') CREATE INDEX IX_factory_instances_heartbeat ON dbo.factory_instances (last_heartbeat_at DESC)",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_factory_mcp_readiness_lookup') CREATE INDEX IX_factory_mcp_readiness_lookup ON dbo.factory_mcp_readiness (instance_id, mcp_name, updated_at DESC)",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_factory_mcp_readiness_status') CREATE INDEX IX_factory_mcp_readiness_status ON dbo.factory_mcp_readiness (status, updated_at DESC)",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_factory_runs_status') CREATE INDEX IX_factory_runs_status ON dbo.factory_runs (status, updated_at DESC)",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_factory_runs_pave_task') CREATE INDEX IX_factory_runs_pave_task ON dbo.factory_runs (pave_task_id)",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_factory_run_events_run') CREATE INDEX IX_factory_run_events_run ON dbo.factory_run_events (run_id, created_at)",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_factory_run_repositories_run') CREATE INDEX IX_factory_run_repositories_run ON dbo.factory_run_repositories (run_id)",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_factory_artifacts_run') CREATE INDEX IX_factory_artifacts_run ON dbo.factory_artifacts (run_id, category)",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_factory_tooling_inventory_lookup') CREATE UNIQUE INDEX IX_factory_tooling_inventory_lookup ON dbo.factory_tooling_inventory (instance_id, tool_type, name) WHERE instance_id IS NOT NULL",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_factory_tooling_inventory_lookup_global') CREATE UNIQUE INDEX IX_factory_tooling_inventory_lookup_global ON dbo.factory_tooling_inventory (tool_type, name) WHERE instance_id IS NULL",
]


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
    def _sync(conn: pyodbc.Connection) -> dict[str, Any]:
        existing = _fetch_one(conn, "SELECT id FROM dbo.factory_instances WHERE id = ?", instance_id)
        if existing:
            _execute(
                conn,
                """
                UPDATE dbo.factory_instances
                SET name = ?, host_name = ?, staff_code = ?, detected_staff_code = ?,
                    board_name = ?, status = ?, version = ?, process_id = ?,
                    capabilities = ?, config = ?, last_heartbeat_at = SYSDATETIMEOFFSET(),
                    updated_at = SYSDATETIMEOFFSET()
                WHERE id = ?
                """,
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
                instance_id,
            )
        else:
            _execute(
                conn,
                """
                INSERT INTO dbo.factory_instances (
                    id, name, host_name, staff_code, detected_staff_code, board_name, status,
                    version, process_id, capabilities, config, last_heartbeat_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, SYSDATETIMEOFFSET())
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
        result = _fetch_one(conn, "SELECT * FROM dbo.factory_instances WHERE id = ?", instance_id)
        assert result is not None
        return result

    return await _run(_sync)


async def heartbeat_instance(
    instance_id: str,
    *,
    status: str,
    detected_staff_code: str | None = None,
    process_id: str | None = None,
) -> dict[str, Any] | None:
    def _sync(conn: pyodbc.Connection) -> dict[str, Any] | None:
        _execute(
            conn,
            """
            UPDATE dbo.factory_instances
            SET status = ?,
                detected_staff_code = COALESCE(?, detected_staff_code),
                process_id = COALESCE(?, process_id),
                last_heartbeat_at = SYSDATETIMEOFFSET(),
                updated_at = SYSDATETIMEOFFSET()
            WHERE id = ?
            """,
            status,
            detected_staff_code,
            process_id,
            instance_id,
        )
        return _fetch_one(conn, "SELECT * FROM dbo.factory_instances WHERE id = ?", instance_id)

    return await _run(_sync)


async def pause_instance(instance_id: str, reason: str) -> dict[str, Any] | None:
    def _sync(conn: pyodbc.Connection) -> dict[str, Any] | None:
        _execute(
            conn,
            """
            UPDATE dbo.factory_instances
            SET is_paused = 1, paused_reason = ?, status = 'paused',
                updated_at = SYSDATETIMEOFFSET()
            WHERE id = ?
            """,
            reason,
            instance_id,
        )
        return _fetch_one(conn, "SELECT * FROM dbo.factory_instances WHERE id = ?", instance_id)

    return await _run(_sync)


async def resume_instance(instance_id: str) -> dict[str, Any] | None:
    def _sync(conn: pyodbc.Connection) -> dict[str, Any] | None:
        _execute(
            conn,
            """
            UPDATE dbo.factory_instances
            SET is_paused = 0, paused_reason = NULL, status = 'ready',
                updated_at = SYSDATETIMEOFFSET()
            WHERE id = ?
            """,
            instance_id,
        )
        return _fetch_one(conn, "SELECT * FROM dbo.factory_instances WHERE id = ?", instance_id)

    return await _run(_sync)


async def list_instances() -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _fetch_all(
            conn,
            """
            SELECT *
            FROM dbo.factory_instances
            WHERE last_heartbeat_at >= DATEADD(second, -?, SYSDATETIMEOFFSET())
               OR is_paused = 1
               OR status IN ('paused', 'stalled')
            ORDER BY updated_at DESC
            """,
            _instance_stale_seconds(),
        )
    )


async def get_instance(instance_id: str) -> dict[str, Any] | None:
    return await _run(
        lambda conn: _fetch_one(conn, "SELECT * FROM dbo.factory_instances WHERE id = ?", instance_id)
    )


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
    row_id = _new_id()

    def _sync(conn: pyodbc.Connection) -> dict[str, Any]:
        _execute(
            conn,
            """
            INSERT INTO dbo.factory_mcp_readiness (
                id, instance_id, mcp_name, status, detail, auth_subject,
                reauth_url, expires_at, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, TRY_CONVERT(datetimeoffset, ?), ?)
            """,
            row_id,
            instance_id,
            mcp_name,
            status,
            detail,
            auth_subject,
            reauth_url,
            expires_at,
            _to_json(metadata),
        )
        result = _fetch_one(conn, "SELECT * FROM dbo.factory_mcp_readiness WHERE id = ?", row_id)
        assert result is not None
        return result

    return await _run(_sync)


async def list_latest_mcp_readiness(instance_id: str | None = None) -> list[dict[str, Any]]:
    def _sync(conn: pyodbc.Connection) -> list[dict[str, Any]]:
        params: list[Any] = []
        where_parts: list[str] = []
        if instance_id is not None:
            where_parts.append("m.instance_id = ?")
            params.append(instance_id)
        else:
            where_parts.append(
                """
                (
                    m.instance_id IS NULL
                    OR i.id IS NULL
                    OR i.last_heartbeat_at >= DATEADD(second, -?, SYSDATETIMEOFFSET())
                    OR i.is_paused = 1
                    OR i.status IN ('paused', 'stalled')
                )
                """
            )
            params.append(_instance_stale_seconds())
        where = "WHERE " + " AND ".join(where_parts)
        return _fetch_all(
            conn,
            f"""
            WITH latest AS (
                SELECT m.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY ISNULL(m.instance_id, ''), m.mcp_name
                        ORDER BY m.updated_at DESC
                    ) AS rn
                FROM dbo.factory_mcp_readiness m
                LEFT JOIN dbo.factory_instances i ON i.id = m.instance_id
                {where}
            )
            SELECT *
            FROM latest
            WHERE rn = 1
            ORDER BY ISNULL(instance_id, ''), mcp_name
            """,
            *params,
        )

    return await _run(_sync)


async def list_stalled_mcps() -> list[dict[str, Any]]:
    def _sync(conn: pyodbc.Connection) -> list[dict[str, Any]]:
        return _fetch_all(
            conn,
            """
            WITH latest AS (
                SELECT m.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY ISNULL(m.instance_id, ''), m.mcp_name
                        ORDER BY m.updated_at DESC
                    ) AS rn
                FROM dbo.factory_mcp_readiness m
                LEFT JOIN dbo.factory_instances i ON i.id = m.instance_id
                WHERE m.instance_id IS NULL
                   OR i.id IS NULL
                   OR i.last_heartbeat_at >= DATEADD(second, -?, SYSDATETIMEOFFSET())
                   OR i.is_paused = 1
                   OR i.status IN ('paused', 'stalled')
            )
            SELECT *
            FROM latest
            WHERE rn = 1
              AND status IN ('stale', 'unauthenticated', 'unavailable', 'degraded')
            ORDER BY updated_at DESC
            """,
            _instance_stale_seconds(),
        )

    return await _run(_sync)


async def create_reauth_session(
    *,
    instance_id: str | None,
    mcp_name: str,
    reauth_url: str | None,
    requested_by_user_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row_id = _new_id()

    def _sync(conn: pyodbc.Connection) -> dict[str, Any]:
        _execute(
            conn,
            """
            INSERT INTO dbo.factory_mcp_reauth_sessions (
                id, instance_id, mcp_name, reauth_url, requested_by_user_id, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            row_id,
            instance_id,
            mcp_name,
            reauth_url,
            requested_by_user_id,
            _to_json(metadata),
        )
        result = _fetch_one(conn, "SELECT * FROM dbo.factory_mcp_reauth_sessions WHERE id = ?", row_id)
        assert result is not None
        return result

    return await _run(_sync)


async def update_reauth_session(
    session_id: str,
    *,
    status: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    completed_sql = (
        "SYSDATETIMEOFFSET()" if status in {"complete", "verified", "cancelled"} else "completed_at"
    )

    def _sync(conn: pyodbc.Connection) -> dict[str, Any] | None:
        _execute(
            conn,
            f"""
            UPDATE dbo.factory_mcp_reauth_sessions
            SET status = ?,
                metadata = COALESCE(?, metadata),
                completed_at = {completed_sql},
                updated_at = SYSDATETIMEOFFSET()
            WHERE id = ?
            """,
            status,
            _to_json(metadata) if metadata is not None else None,
            session_id,
        )
        return _fetch_one(conn, "SELECT * FROM dbo.factory_mcp_reauth_sessions WHERE id = ?", session_id)

    return await _run(_sync)


async def list_reauth_sessions() -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _fetch_all(
            conn,
            "SELECT TOP (100) * FROM dbo.factory_mcp_reauth_sessions ORDER BY created_at DESC",
        )
    )


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
    row_id = _new_id()

    def _sync(conn: pyodbc.Connection) -> dict[str, Any]:
        _execute(
            conn,
            """
            INSERT INTO dbo.factory_scout_cycles (
                id, instance_id, board_name, staff_code, status, active_pave_task_id,
                candidate_count, local_model, token_estimate, input_snapshot
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row_id,
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
        result = _fetch_one(conn, "SELECT * FROM dbo.factory_scout_cycles WHERE id = ?", row_id)
        assert result is not None
        return result

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
    def _sync(conn: pyodbc.Connection) -> dict[str, Any] | None:
        _execute(
            conn,
            """
            UPDATE dbo.factory_scout_cycles
            SET status = ?, selected_pave_task_id = ?, candidate_count = COALESCE(?, candidate_count),
                decision = ?, summary = ?,
                output_snapshot = ?, finished_at = SYSDATETIMEOFFSET()
            WHERE id = ?
            """,
            status,
            selected_pave_task_id,
            candidate_count,
            decision,
            summary,
            _to_json(output_snapshot),
            cycle_id,
        )
        return _fetch_one(conn, "SELECT * FROM dbo.factory_scout_cycles WHERE id = ?", cycle_id)

    return await _run(_sync)


async def list_scout_cycles(limit: int = 50) -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _fetch_all(
            conn,
            f"SELECT TOP ({_top(limit)}) * FROM dbo.factory_scout_cycles ORDER BY started_at DESC",
        )
    )


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
    row_id = _new_id()

    def _sync(conn: pyodbc.Connection) -> dict[str, Any]:
        _execute(
            conn,
            """
            INSERT INTO dbo.factory_runs (
                id, instance_id, pave_task_id, pave_work_item_id, pave_incident_id,
                pave_task_title, pave_board_name, staff_code, status, phase,
                workflow_id, workflow_name, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row_id,
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
        result = _fetch_one(conn, "SELECT * FROM dbo.factory_runs WHERE id = ?", row_id)
        assert result is not None
        return result

    return await _run(_sync)


async def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _fetch_all(
            conn, f"SELECT TOP ({_top(limit)}) * FROM dbo.factory_runs ORDER BY updated_at DESC"
        )
    )


async def get_run(run_id: str) -> dict[str, Any] | None:
    return await _run(lambda conn: _fetch_one(conn, "SELECT * FROM dbo.factory_runs WHERE id = ?", run_id))


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
    def _sync(conn: pyodbc.Connection) -> dict[str, Any] | None:
        existing = _fetch_one(conn, "SELECT metadata FROM dbo.factory_runs WHERE id = ?", run_id)
        if existing is None:
            return None
        merged_metadata = existing.get("metadata") or {}
        if metadata:
            merged_metadata = {**merged_metadata, **metadata}
        _execute(
            conn,
            """
            UPDATE dbo.factory_runs
            SET status = COALESCE(?, status),
                phase = COALESCE(?, phase),
                failure_reason = COALESCE(?, failure_reason),
                e_doc_status = COALESCE(?, e_doc_status),
                e_doc_report_id = COALESCE(?, e_doc_report_id),
                quality_close_attempted = COALESCE(?, quality_close_attempted),
                quality_close_status = COALESCE(?, quality_close_status),
                assigned_to_staff_code = COALESCE(?, assigned_to_staff_code),
                claim_attempted_at = CASE WHEN ? = 1 THEN SYSDATETIMEOFFSET() ELSE claim_attempted_at END,
                claimed_at = CASE WHEN ? = 1 THEN SYSDATETIMEOFFSET() ELSE claimed_at END,
                started_at = CASE WHEN ? = 1 THEN SYSDATETIMEOFFSET() ELSE started_at END,
                finished_at = CASE WHEN ? = 1 THEN SYSDATETIMEOFFSET() ELSE finished_at END,
                suspended_at = CASE WHEN ? = 1 THEN SYSDATETIMEOFFSET() ELSE suspended_at END,
                metadata = ?,
                updated_at = SYSDATETIMEOFFSET()
            WHERE id = ?
            """,
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
            _to_json(merged_metadata),
            run_id,
        )
        return _fetch_one(conn, "SELECT * FROM dbo.factory_runs WHERE id = ?", run_id)

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
    row_id = _new_id()

    def _sync(conn: pyodbc.Connection) -> dict[str, Any]:
        _execute(
            conn,
            """
            INSERT INTO dbo.factory_run_events (
                id, run_id, instance_id, level, phase, message, payload, dashboard_visible
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row_id,
            run_id,
            instance_id,
            level,
            phase,
            message,
            _to_json(payload),
            dashboard_visible,
        )
        result = _fetch_one(conn, "SELECT * FROM dbo.factory_run_events WHERE id = ?", row_id)
        assert result is not None
        if run_id:
            _refresh_run_dashboard_log_sync(conn, run_id)
        return result

    return await _run(_sync)


def _refresh_run_dashboard_log_sync(conn: pyodbc.Connection, run_id: str) -> None:
    events = _fetch_all(
        conn,
        """
        SELECT created_at, level, phase, message, payload
        FROM dbo.factory_run_events
        WHERE run_id = ? AND dashboard_visible = 1
        ORDER BY created_at ASC
        """,
        run_id,
    )
    _execute(
        conn,
        "UPDATE dbo.factory_runs SET dashboard_log = ?, updated_at = SYSDATETIMEOFFSET() WHERE id = ?",
        _to_json(events, []),
        run_id,
    )


async def refresh_run_dashboard_log(run_id: str) -> None:
    await _run(lambda conn: _refresh_run_dashboard_log_sync(conn, run_id))


async def list_run_events(run_id: str, limit: int = 500) -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _fetch_all(
            conn,
            f"""
            SELECT TOP ({_top(limit)}) *
            FROM dbo.factory_run_events
            WHERE run_id = ?
            ORDER BY created_at ASC
            """,
            run_id,
        )
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
    row_id = _new_id()

    def _sync(conn: pyodbc.Connection) -> dict[str, Any]:
        _execute(
            conn,
            """
            INSERT INTO dbo.factory_run_repositories (
                id, run_id, repo_name, repo_path, remote_url, base_branch,
                branch_name, status, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row_id,
            run_id,
            repo_name,
            repo_path,
            remote_url,
            base_branch,
            branch_name,
            status,
            _to_json(metadata),
        )
        result = _fetch_one(conn, "SELECT * FROM dbo.factory_run_repositories WHERE id = ?", row_id)
        assert result is not None
        return result

    return await _run(_sync)


async def list_run_repositories(run_id: str) -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _fetch_all(
            conn,
            "SELECT * FROM dbo.factory_run_repositories WHERE run_id = ? ORDER BY created_at ASC",
            run_id,
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
    row_id = _new_id()

    def _sync(conn: pyodbc.Connection) -> dict[str, Any]:
        _execute(
            conn,
            """
            INSERT INTO dbo.factory_artifacts (
                id, run_id, repository_id, category, name, status,
                storage_uri, content_type, summary, payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row_id,
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
        result = _fetch_one(conn, "SELECT * FROM dbo.factory_artifacts WHERE id = ?", row_id)
        assert result is not None
        return result

    return await _run(_sync)


async def list_artifacts(run_id: str) -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _fetch_all(
            conn,
            "SELECT * FROM dbo.factory_artifacts WHERE run_id = ? ORDER BY created_at ASC",
            run_id,
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
    row_id = _new_id()

    def _sync(conn: pyodbc.Connection) -> dict[str, Any]:
        _execute(
            conn,
            """
            INSERT INTO dbo.factory_critic_reports (
                id, run_id, node_id, status, summary, findings, score, payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row_id,
            run_id,
            node_id,
            status,
            summary,
            _to_json(findings, []),
            score,
            _to_json(payload),
        )
        result = _fetch_one(conn, "SELECT * FROM dbo.factory_critic_reports WHERE id = ?", row_id)
        assert result is not None
        return result

    return await _run(_sync)


async def list_critic_reports(run_id: str) -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _fetch_all(
            conn,
            "SELECT * FROM dbo.factory_critic_reports WHERE run_id = ? ORDER BY created_at DESC",
            run_id,
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
    row_id = _new_id()

    def _sync(conn: pyodbc.Connection) -> dict[str, Any]:
        _execute(
            conn,
            """
            INSERT INTO dbo.factory_learning_assessments (
                id, run_id, pave_task_id, status, generated_artifact_id,
                manual_changes_detected, diff_summary, learnings,
                sbkb_document_id, sbkb_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row_id,
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
        result = _fetch_one(conn, "SELECT * FROM dbo.factory_learning_assessments WHERE id = ?", row_id)
        assert result is not None
        return result

    return await _run(_sync)


async def list_learning_assessments(limit: int = 50) -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _fetch_all(
            conn,
            f"""
            SELECT TOP ({_top(limit)}) *
            FROM dbo.factory_learning_assessments
            ORDER BY updated_at DESC
            """,
        )
    )


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
    row_id = _new_id()

    def _sync(conn: pyodbc.Connection) -> dict[str, Any]:
        _execute(
            conn,
            """
            INSERT INTO dbo.factory_edoc_uploads (
                id, run_id, pave_job_id, status, file_name, artifact_id,
                full_log_included, critic_output_included, error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row_id,
            run_id,
            pave_job_id,
            status,
            file_name,
            artifact_id,
            full_log_included,
            critic_output_included,
            error_message,
        )
        result = _fetch_one(conn, "SELECT * FROM dbo.factory_edoc_uploads WHERE id = ?", row_id)
        assert result is not None
        return result

    return await _run(_sync)


async def list_edoc_uploads(run_id: str) -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _fetch_all(
            conn,
            "SELECT * FROM dbo.factory_edoc_uploads WHERE run_id = ? ORDER BY created_at DESC",
            run_id,
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
    row_id = _new_id()

    def _sync(conn: pyodbc.Connection) -> dict[str, Any]:
        _execute(
            conn,
            """
            INSERT INTO dbo.factory_knowledge_queries (
                id, run_id, service_name, query, status, result_count,
                tokens_estimated, citations
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row_id,
            run_id,
            service_name,
            query,
            status,
            result_count,
            tokens_estimated,
            _to_json(citations, []),
        )
        result = _fetch_one(conn, "SELECT * FROM dbo.factory_knowledge_queries WHERE id = ?", row_id)
        assert result is not None
        return result

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
    row_id = _new_id()

    def _sync(conn: pyodbc.Connection) -> dict[str, Any]:
        _execute(
            conn,
            """
            INSERT INTO dbo.factory_skill_invocations (
                id, run_id, skill_name, skill_source, version, phase, status, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row_id,
            run_id,
            skill_name,
            skill_source,
            version,
            phase,
            status,
            _to_json(metadata),
        )
        result = _fetch_one(conn, "SELECT * FROM dbo.factory_skill_invocations WHERE id = ?", row_id)
        assert result is not None
        return result

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
    def _sync(conn: pyodbc.Connection) -> dict[str, Any]:
        existing = _fetch_one(
            conn,
            """
            SELECT id
            FROM dbo.factory_tooling_inventory
            WHERE ((instance_id IS NULL AND ? IS NULL) OR instance_id = ?)
              AND tool_type = ?
              AND name = ?
            """,
            instance_id,
            instance_id,
            tool_type,
            name,
        )
        if existing:
            row_id = str(existing["id"])
            _execute(
                conn,
                """
                UPDATE dbo.factory_tooling_inventory
                SET installed_version = ?, latest_version = ?, status = ?,
                    source_url = ?, update_available = ?, metadata = ?,
                    last_checked_at = SYSDATETIMEOFFSET(),
                    updated_at = SYSDATETIMEOFFSET()
                WHERE id = ?
                """,
                installed_version,
                latest_version,
                status,
                source_url,
                update_available,
                _to_json(metadata),
                row_id,
            )
        else:
            row_id = _new_id()
            _execute(
                conn,
                """
                INSERT INTO dbo.factory_tooling_inventory (
                    id, instance_id, tool_type, name, installed_version, latest_version,
                    status, source_url, update_available, last_checked_at, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, SYSDATETIMEOFFSET(), ?)
                """,
                row_id,
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
        result = _fetch_one(conn, "SELECT * FROM dbo.factory_tooling_inventory WHERE id = ?", row_id)
        assert result is not None
        return result

    return await _run(_sync)


async def list_tooling_inventory() -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _fetch_all(
            conn,
            """
            SELECT t.*
            FROM dbo.factory_tooling_inventory t
            LEFT JOIN dbo.factory_instances i ON i.id = t.instance_id
            WHERE t.instance_id IS NULL
               OR (
                    i.id IS NOT NULL
                    AND (
                        i.last_heartbeat_at >= DATEADD(second, -?, SYSDATETIMEOFFSET())
                        OR i.is_paused = 1
                        OR i.status IN ('paused', 'stalled')
                    )
               )
            ORDER BY t.update_available DESC, t.updated_at DESC, t.tool_type, t.name
            """,
            _instance_stale_seconds(),
        )
    )


async def create_tooling_update_job(
    *,
    instance_id: str | None,
    tool_id: str | None,
    requested_by_user_id: str | None,
    from_version: str | None,
    to_version: str | None,
) -> dict[str, Any]:
    row_id = _new_id()

    def _sync(conn: pyodbc.Connection) -> dict[str, Any]:
        _execute(
            conn,
            """
            INSERT INTO dbo.factory_tooling_update_jobs (
                id, instance_id, tool_id, requested_by_user_id, from_version, to_version
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            row_id,
            instance_id,
            tool_id,
            requested_by_user_id,
            from_version,
            to_version,
        )
        result = _fetch_one(conn, "SELECT * FROM dbo.factory_tooling_update_jobs WHERE id = ?", row_id)
        assert result is not None
        return result

    return await _run(_sync)


async def list_tooling_update_jobs(limit: int = 50) -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _fetch_all(
            conn,
            f"""
            SELECT TOP ({_top(limit)}) *
            FROM dbo.factory_tooling_update_jobs
            ORDER BY created_at DESC
            """,
        )
    )


async def update_tooling_update_job(
    job_id: str,
    *,
    status: str | None = None,
    log_entry: dict[str, Any] | None = None,
    error_message: str | None = None,
    set_started: bool = False,
    set_finished: bool = False,
) -> dict[str, Any] | None:
    def _sync(conn: pyodbc.Connection) -> dict[str, Any] | None:
        existing = _fetch_one(
            conn,
            "SELECT log FROM dbo.factory_tooling_update_jobs WHERE id = ?",
            job_id,
        )
        if existing is None:
            return None
        log = existing.get("log") or []
        if log_entry is not None:
            log.append(log_entry)
        _execute(
            conn,
            """
            UPDATE dbo.factory_tooling_update_jobs
            SET status = COALESCE(?, status),
                started_at = CASE WHEN ? = 1 THEN SYSDATETIMEOFFSET() ELSE started_at END,
                finished_at = CASE WHEN ? = 1 THEN SYSDATETIMEOFFSET() ELSE finished_at END,
                log = ?,
                error_message = COALESCE(?, error_message)
            WHERE id = ?
            """,
            status,
            1 if set_started else 0,
            1 if set_finished else 0,
            _to_json(log),
            error_message,
            job_id,
        )
        return _fetch_one(conn, "SELECT * FROM dbo.factory_tooling_update_jobs WHERE id = ?", job_id)

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
    row_id = _new_id()

    def _sync(conn: pyodbc.Connection) -> dict[str, Any]:
        _execute(
            conn,
            """
            INSERT INTO dbo.factory_audit_log (
                id, actor_type, actor_id, action, target_type, target_id, run_id, payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row_id,
            actor_type,
            actor_id,
            action,
            target_type,
            target_id,
            run_id,
            _to_json(payload),
        )
        result = _fetch_one(conn, "SELECT * FROM dbo.factory_audit_log WHERE id = ?", row_id)
        assert result is not None
        return result

    return await _run(_sync)


async def dashboard_summary() -> dict[str, Any]:
    def _sync(conn: pyodbc.Connection) -> dict[str, Any]:
        row = _fetch_one(
            conn,
            """
            SELECT
                (SELECT COUNT(*) FROM dbo.factory_instances WHERE last_heartbeat_at >= DATEADD(second, -?, SYSDATETIMEOFFSET()) OR is_paused = 1 OR status IN ('paused', 'stalled')) AS instances_total,
                (SELECT COUNT(*) FROM dbo.factory_instances WHERE status = 'ready' AND last_heartbeat_at >= DATEADD(second, -?, SYSDATETIMEOFFSET())) AS instances_ready,
                (SELECT COUNT(*) FROM dbo.factory_instances WHERE is_paused = 1 OR status = 'paused') AS instances_paused,
                (SELECT COUNT(*) FROM dbo.factory_runs WHERE status IN ('queued', 'claimed', 'running')) AS runs_active,
                (SELECT COUNT(*) FROM dbo.factory_runs WHERE status = 'stalled') AS runs_stalled,
                (SELECT COUNT(*) FROM dbo.factory_runs WHERE status = 'failed') AS runs_failed,
                (
                    SELECT COUNT(*)
                    FROM dbo.factory_tooling_inventory t
                    LEFT JOIN dbo.factory_instances i ON i.id = t.instance_id
                    WHERE t.update_available = 1
                      AND (
                        t.instance_id IS NULL
                        OR (
                            i.id IS NOT NULL
                            AND (
                                i.last_heartbeat_at >= DATEADD(second, -?, SYSDATETIMEOFFSET())
                                OR i.is_paused = 1
                                OR i.status IN ('paused', 'stalled')
                            )
                        )
                      )
                ) AS tooling_updates_available,
                (SELECT COUNT(*) FROM dbo.factory_learning_assessments WHERE status IN ('pending', 'queued')) AS learning_pending
            """,
            _instance_stale_seconds(),
            _instance_stale_seconds(),
            _instance_stale_seconds(),
        )
        assert row is not None
        stalled = _fetch_all(
            conn,
            """
            WITH latest AS (
                SELECT m.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY ISNULL(m.instance_id, ''), m.mcp_name
                        ORDER BY m.updated_at DESC
                    ) AS rn
                FROM dbo.factory_mcp_readiness m
                LEFT JOIN dbo.factory_instances i ON i.id = m.instance_id
                WHERE m.instance_id IS NULL
                   OR i.id IS NULL
                   OR i.last_heartbeat_at >= DATEADD(second, -?, SYSDATETIMEOFFSET())
                   OR i.is_paused = 1
                   OR i.status IN ('paused', 'stalled')
            )
            SELECT *
            FROM latest
            WHERE rn = 1
              AND status IN ('stale', 'unauthenticated', 'unavailable', 'degraded')
            """,
            _instance_stale_seconds(),
        )
        row["stalled_mcp_count"] = len(stalled)
        return row

    return await _run(_sync)


async def dashboard_failures(limit: int = 20) -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _fetch_all(
            conn,
            f"""
            SELECT TOP ({_top(limit)}) *
            FROM dbo.factory_runs
            WHERE status IN ('stalled', 'failed', 'suspended')
            ORDER BY updated_at DESC
            """,
        )
    )


async def dashboard_throughput(days: int = 14) -> list[dict[str, Any]]:
    return await _run(
        lambda conn: _fetch_all(
            conn,
            """
            SELECT
                CAST(created_at AS date) AS day,
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN status IN ('failed', 'stalled', 'suspended') THEN 1 ELSE 0 END) AS interrupted
            FROM dbo.factory_runs
            WHERE created_at >= DATEADD(day, -?, SYSDATETIMEOFFSET())
            GROUP BY CAST(created_at AS date)
            ORDER BY day ASC
            """,
            int(days),
        )
    )
