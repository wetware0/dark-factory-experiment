"""Add PAVE factory portal state.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-10

"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS factory_instances (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            host_name TEXT NOT NULL DEFAULT '',
            staff_code TEXT NOT NULL DEFAULT '',
            detected_staff_code TEXT,
            board_name TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'starting',
            is_paused BOOLEAN NOT NULL DEFAULT FALSE,
            paused_reason TEXT,
            version TEXT,
            process_id TEXT,
            capabilities JSONB NOT NULL DEFAULT '{}'::jsonb,
            config JSONB NOT NULL DEFAULT '{}'::jsonb,
            last_heartbeat_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_instances_status_idx "
        "ON factory_instances (status, is_paused)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_instances_heartbeat_idx "
        "ON factory_instances (last_heartbeat_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS factory_mcp_readiness (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            instance_id TEXT REFERENCES factory_instances(id) ON DELETE CASCADE,
            mcp_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'checking',
            detail TEXT,
            auth_subject TEXT,
            reauth_url TEXT,
            last_checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_mcp_readiness_lookup_idx "
        "ON factory_mcp_readiness (instance_id, mcp_name, updated_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_mcp_readiness_status_idx "
        "ON factory_mcp_readiness (status, updated_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS factory_mcp_reauth_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            instance_id TEXT REFERENCES factory_instances(id) ON DELETE SET NULL,
            mcp_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'requested',
            reauth_url TEXT,
            requested_by_user_id TEXT,
            completed_at TIMESTAMPTZ,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_mcp_reauth_sessions_status_idx "
        "ON factory_mcp_reauth_sessions (status, created_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS factory_scout_cycles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            instance_id TEXT REFERENCES factory_instances(id) ON DELETE SET NULL,
            board_name TEXT NOT NULL,
            staff_code TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'running',
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at TIMESTAMPTZ,
            active_pave_task_id TEXT,
            candidate_count INTEGER NOT NULL DEFAULT 0,
            selected_pave_task_id TEXT,
            decision TEXT,
            local_model TEXT,
            token_estimate INTEGER NOT NULL DEFAULT 0,
            summary TEXT,
            input_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
            output_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_scout_cycles_started_idx "
        "ON factory_scout_cycles (started_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS factory_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            instance_id TEXT REFERENCES factory_instances(id) ON DELETE SET NULL,
            pave_task_id TEXT,
            pave_work_item_id TEXT,
            pave_incident_id TEXT,
            pave_task_title TEXT NOT NULL DEFAULT '',
            pave_board_name TEXT NOT NULL DEFAULT '',
            staff_code TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'queued',
            phase TEXT NOT NULL DEFAULT 'scout',
            failure_reason TEXT,
            workflow_id TEXT,
            workflow_name TEXT,
            claim_attempted_at TIMESTAMPTZ,
            claimed_at TIMESTAMPTZ,
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            suspended_at TIMESTAMPTZ,
            assigned_to_staff_code TEXT,
            quality_close_attempted BOOLEAN NOT NULL DEFAULT FALSE,
            quality_close_status TEXT,
            e_doc_report_id TEXT,
            e_doc_status TEXT,
            dashboard_log JSONB NOT NULL DEFAULT '[]'::jsonb,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_runs_status_idx "
        "ON factory_runs (status, updated_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_runs_pave_task_idx "
        "ON factory_runs (pave_task_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS factory_run_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id UUID REFERENCES factory_runs(id) ON DELETE CASCADE,
            instance_id TEXT REFERENCES factory_instances(id) ON DELETE SET NULL,
            level TEXT NOT NULL DEFAULT 'info',
            phase TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL,
            dashboard_visible BOOLEAN NOT NULL DEFAULT TRUE,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_run_events_run_idx "
        "ON factory_run_events (run_id, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_run_events_visible_idx "
        "ON factory_run_events (dashboard_visible, created_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS factory_run_repositories (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id UUID NOT NULL REFERENCES factory_runs(id) ON DELETE CASCADE,
            repo_name TEXT NOT NULL,
            repo_path TEXT NOT NULL DEFAULT '',
            remote_url TEXT NOT NULL DEFAULT '',
            base_branch TEXT NOT NULL DEFAULT '',
            branch_name TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'planned',
            pr_url TEXT,
            pr_number TEXT,
            commit_sha TEXT,
            build_status TEXT,
            test_status TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_run_repositories_run_idx "
        "ON factory_run_repositories (run_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS factory_artifacts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id UUID REFERENCES factory_runs(id) ON DELETE CASCADE,
            repository_id UUID REFERENCES factory_run_repositories(id) ON DELETE SET NULL,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'created',
            storage_uri TEXT,
            content_type TEXT,
            summary TEXT,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_artifacts_run_idx "
        "ON factory_artifacts (run_id, category)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS factory_critic_reports (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id UUID NOT NULL REFERENCES factory_runs(id) ON DELETE CASCADE,
            node_id TEXT NOT NULL DEFAULT 'critic',
            status TEXT NOT NULL DEFAULT 'pending',
            summary TEXT,
            findings JSONB NOT NULL DEFAULT '[]'::jsonb,
            score NUMERIC,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_critic_reports_run_idx "
        "ON factory_critic_reports (run_id, created_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS factory_learning_assessments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id UUID REFERENCES factory_runs(id) ON DELETE SET NULL,
            pave_task_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            generated_artifact_id UUID REFERENCES factory_artifacts(id) ON DELETE SET NULL,
            manual_changes_detected BOOLEAN NOT NULL DEFAULT FALSE,
            diff_summary TEXT,
            learnings JSONB NOT NULL DEFAULT '[]'::jsonb,
            sbkb_document_id TEXT,
            sbkb_status TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_learning_assessments_status_idx "
        "ON factory_learning_assessments (status, updated_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS factory_edoc_uploads (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id UUID NOT NULL REFERENCES factory_runs(id) ON DELETE CASCADE,
            pave_job_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            document_id TEXT,
            file_name TEXT NOT NULL DEFAULT '',
            artifact_id UUID REFERENCES factory_artifacts(id) ON DELETE SET NULL,
            full_log_included BOOLEAN NOT NULL DEFAULT FALSE,
            critic_output_included BOOLEAN NOT NULL DEFAULT FALSE,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_edoc_uploads_run_idx "
        "ON factory_edoc_uploads (run_id, created_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS factory_knowledge_queries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id UUID REFERENCES factory_runs(id) ON DELETE CASCADE,
            service_name TEXT NOT NULL,
            query TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'planned',
            result_count INTEGER NOT NULL DEFAULT 0,
            tokens_estimated INTEGER NOT NULL DEFAULT 0,
            citations JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_knowledge_queries_run_idx "
        "ON factory_knowledge_queries (run_id, created_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS factory_skill_invocations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id UUID REFERENCES factory_runs(id) ON DELETE CASCADE,
            skill_name TEXT NOT NULL,
            skill_source TEXT NOT NULL DEFAULT '',
            version TEXT,
            phase TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'planned',
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_skill_invocations_run_idx "
        "ON factory_skill_invocations (run_id, created_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS factory_tooling_inventory (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            instance_id TEXT REFERENCES factory_instances(id) ON DELETE SET NULL,
            tool_type TEXT NOT NULL,
            name TEXT NOT NULL,
            installed_version TEXT,
            latest_version TEXT,
            status TEXT NOT NULL DEFAULT 'unknown',
            source_url TEXT,
            update_available BOOLEAN NOT NULL DEFAULT FALSE,
            last_checked_at TIMESTAMPTZ,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_tooling_inventory_status_idx "
        "ON factory_tooling_inventory (status, update_available, updated_at DESC)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS factory_tooling_inventory_unique_idx "
        "ON factory_tooling_inventory (COALESCE(instance_id, ''), tool_type, name)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS factory_tooling_update_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            instance_id TEXT REFERENCES factory_instances(id) ON DELETE SET NULL,
            tool_id UUID REFERENCES factory_tooling_inventory(id) ON DELETE SET NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            requested_by_user_id TEXT,
            from_version TEXT,
            to_version TEXT,
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            log JSONB NOT NULL DEFAULT '[]'::jsonb,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_tooling_update_jobs_status_idx "
        "ON factory_tooling_update_jobs (status, created_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS factory_audit_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            actor_type TEXT NOT NULL,
            actor_id TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL DEFAULT '',
            run_id UUID REFERENCES factory_runs(id) ON DELETE SET NULL,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_audit_log_created_idx "
        "ON factory_audit_log (created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS factory_audit_log_run_idx "
        "ON factory_audit_log (run_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS factory_audit_log")
    op.execute("DROP TABLE IF EXISTS factory_tooling_update_jobs")
    op.execute("DROP TABLE IF EXISTS factory_tooling_inventory")
    op.execute("DROP TABLE IF EXISTS factory_skill_invocations")
    op.execute("DROP TABLE IF EXISTS factory_knowledge_queries")
    op.execute("DROP TABLE IF EXISTS factory_edoc_uploads")
    op.execute("DROP TABLE IF EXISTS factory_learning_assessments")
    op.execute("DROP TABLE IF EXISTS factory_critic_reports")
    op.execute("DROP TABLE IF EXISTS factory_artifacts")
    op.execute("DROP TABLE IF EXISTS factory_run_repositories")
    op.execute("DROP TABLE IF EXISTS factory_run_events")
    op.execute("DROP TABLE IF EXISTS factory_runs")
    op.execute("DROP TABLE IF EXISTS factory_scout_cycles")
    op.execute("DROP TABLE IF EXISTS factory_mcp_reauth_sessions")
    op.execute("DROP TABLE IF EXISTS factory_mcp_readiness")
    op.execute("DROP TABLE IF EXISTS factory_instances")
