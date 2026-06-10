import pytest

from backend.db import factory_sqlite_repository as repo


@pytest.fixture(autouse=True)
def isolated_sqlite_store(monkeypatch, tmp_path):
    monkeypatch.setattr(repo.config, "FACTORY_SQLITE_PATH", str(tmp_path / "factory.sqlite3"))
    monkeypatch.setattr(repo, "_schema_ready", False)


@pytest.mark.asyncio
async def test_sqlite_factory_store_records_run_log_and_evidence_inputs():
    instance = await repo.upsert_instance(
        instance_id="sqlite-worker",
        name="SQLite worker",
        host_name="local",
        staff_code="C50",
        detected_staff_code="PWS",
        board_name="Peter's Board",
        status="ready",
        capabilities={"scout": True},
        config={"guardian_staff_code": "PWS"},
    )
    assert instance["staff_code"] == "C50"

    run = await repo.create_run(
        instance_id=instance["id"],
        pave_task_id="task-1",
        pave_work_item_id="WI01020304",
        pave_incident_id=None,
        pave_task_title="WI01020304 / CDF: Test",
        pave_board_name="Peter's Board",
        staff_code="C50",
        workflow_name="pave-dark-factory-execute-task",
        metadata={"dry_run": True},
    )
    await repo.append_run_event(
        run_id=run["id"],
        instance_id=instance["id"],
        level="info",
        phase="scout",
        message="SQLite smoke event",
        payload={"ok": True},
    )
    await repo.add_critic_report(
        run_id=run["id"],
        node_id="critic",
        status="passed",
        summary="SQLite critic output",
        findings=[],
    )
    await repo.create_edoc_upload(
        run_id=run["id"],
        pave_job_id="WI01020304",
        status="uploaded",
        file_name="evidence.md",
        full_log_included=True,
        critic_output_included=True,
    )

    saved = await repo.get_run(run["id"])
    assert saved is not None
    assert saved["dashboard_log"][0]["message"] == "SQLite smoke event"
    assert (await repo.list_critic_reports(run["id"]))[0]["summary"] == "SQLite critic output"
    assert (await repo.list_edoc_uploads(run["id"]))[0]["file_name"] == "evidence.md"


@pytest.mark.asyncio
async def test_sqlite_factory_store_dashboard_and_tooling_jobs():
    await repo.record_mcp_readiness(
        instance_id="sqlite-worker",
        mcp_name="ediprod",
        status="unauthenticated",
        detail="expired",
    )
    summary = await repo.dashboard_summary()
    assert summary["stalled_mcp_count"] == 1

    tool = await repo.upsert_tooling_inventory(
        instance_id=None,
        tool_type="prompt_repo",
        name="WTG.AI.Prompts",
        installed_version="aaa",
        latest_version="bbb",
        status="present",
        update_available=True,
    )
    job = await repo.create_tooling_update_job(
        instance_id=None,
        tool_id=tool["id"],
        requested_by_user_id="admin",
        from_version="aaa",
        to_version="bbb",
    )
    updated = await repo.update_tooling_update_job(
        job["id"],
        status="completed",
        log_entry={"message": "updated"},
        set_started=True,
        set_finished=True,
    )

    assert updated is not None
    assert updated["status"] == "completed"
    assert updated["log"][0]["message"] == "updated"
