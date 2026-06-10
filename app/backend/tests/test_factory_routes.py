import pytest

from backend.routes import factory


@pytest.mark.asyncio
async def test_evidence_report_uses_dashboard_events_and_critic(monkeypatch):
    async def fake_get_run(run_id: str):
        return {
            "id": run_id,
            "pave_task_id": "TASK-1",
            "pave_work_item_id": "WI01020304",
            "pave_incident_id": None,
            "pave_board_name": "Peter's Board",
            "staff_code": "PWS",
            "status": "stalled",
            "phase": "mcp_readiness",
            "e_doc_status": "stalled_mcp",
        }

    async def fake_events(run_id: str, limit: int = 2000):
        return [
            {
                "created_at": "2026-06-10T01:00:00Z",
                "level": "warning",
                "phase": "mcp_readiness",
                "message": "Scout paused before PAVE polling.",
                "payload": {"mcp": "ediprod"},
            }
        ]

    async def fake_repositories(run_id: str):
        return [
            {
                "repo_name": "CargoWise.Customs",
                "branch_name": "codex/pave-task",
                "pr_url": "https://example.test/pr/1",
                "build_status": "not_started",
                "test_status": "not_started",
                "status": "planned",
            }
        ]

    async def fake_artifacts(run_id: str):
        return [
            {
                "category": "Audit",
                "name": "MCP readiness stall",
                "status": "created",
                "storage_uri": None,
                "summary": "ediprod unavailable",
            }
        ]

    async def fake_critics(run_id: str):
        return [
            {
                "node_id": "critic",
                "status": "blocked",
                "score": 0,
                "summary": "Cannot assess generated code because PAVE claim did not happen.",
                "findings": [
                    {
                        "severity": "high",
                        "finding": "Required MCP unavailable",
                        "evidence": "ediprod adapter missing",
                    }
                ],
            }
        ]

    async def fake_edocs(run_id: str):
        return [
            {
                "file_name": "factory-evidence.md",
                "status": "stalled_mcp",
                "document_id": None,
                "full_log_included": True,
                "critic_output_included": True,
                "error_message": "ediprod unavailable",
            }
        ]

    monkeypatch.setattr(factory.repo, "get_run", fake_get_run)
    monkeypatch.setattr(factory.repo, "list_run_events", fake_events)
    monkeypatch.setattr(factory.repo, "list_run_repositories", fake_repositories)
    monkeypatch.setattr(factory.repo, "list_artifacts", fake_artifacts)
    monkeypatch.setattr(factory.repo, "list_critic_reports", fake_critics)
    monkeypatch.setattr(factory.repo, "list_edoc_uploads", fake_edocs)

    report = await factory._build_evidence_report("run-1")

    assert "TASK-1" in report
    assert "Scout paused before PAVE polling." in report
    assert "Cannot assess generated code" in report
    assert "factory-evidence.md" in report
