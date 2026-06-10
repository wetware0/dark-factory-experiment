"""PAVE factory portal routes.

Admin routes power the dashboard. Worker routes are token-protected and let
scout/agent instances report MCP readiness, PAVE run progress, critic output,
artifacts, and eDoc evidence upload status.
"""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from backend import config
from backend.auth.dependencies import get_current_admin
from backend.db import factory_store as repo

router = APIRouter(prefix="/factory", tags=["factory"])


class InstanceRegistration(BaseModel):
    instance_id: str
    name: str
    host_name: str = ""
    staff_code: str = Field(default_factory=lambda: config.PAVE_STAFF_CODE)
    board_name: str = Field(default_factory=lambda: config.PAVE_BOARD_NAME)
    status: str = "ready"
    detected_staff_code: str | None = None
    version: str | None = None
    process_id: str | None = None
    capabilities: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)


class InstanceHeartbeat(BaseModel):
    status: str = "ready"
    detected_staff_code: str | None = None
    process_id: str | None = None


class PauseRequest(BaseModel):
    reason: str = "Paused from dashboard"


class McpReadinessIn(BaseModel):
    instance_id: str | None = None
    mcp_name: str
    status: str
    detail: str | None = None
    auth_subject: str | None = None
    reauth_url: str | None = None
    expires_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReauthRequest(BaseModel):
    instance_id: str | None = None
    mcp_name: str
    reauth_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReauthUpdateRequest(BaseModel):
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScoutCycleCreate(BaseModel):
    instance_id: str | None = None
    board_name: str = Field(default_factory=lambda: config.PAVE_BOARD_NAME)
    staff_code: str = Field(default_factory=lambda: config.PAVE_STAFF_CODE)
    status: str = "running"
    active_pave_task_id: str | None = None
    candidate_count: int = 0
    local_model: str | None = Field(default_factory=lambda: config.FACTORY_LOCAL_SCOUT_MODEL)
    token_estimate: int = 0
    input_snapshot: dict[str, Any] = Field(default_factory=dict)


class ScoutCycleFinish(BaseModel):
    status: str
    selected_pave_task_id: str | None = None
    candidate_count: int | None = None
    decision: str | None = None
    summary: str | None = None
    output_snapshot: dict[str, Any] = Field(default_factory=dict)


class RunCreate(BaseModel):
    instance_id: str | None = None
    pave_task_id: str | None = None
    pave_work_item_id: str | None = None
    pave_incident_id: str | None = None
    pave_task_title: str = ""
    pave_board_name: str = Field(default_factory=lambda: config.PAVE_BOARD_NAME)
    staff_code: str = Field(default_factory=lambda: config.PAVE_STAFF_CODE)
    status: str = "queued"
    phase: str = "scout"
    workflow_id: str | None = None
    workflow_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunPatch(BaseModel):
    status: str | None = None
    phase: str | None = None
    failure_reason: str | None = None
    e_doc_status: str | None = None
    e_doc_report_id: str | None = None
    quality_close_attempted: bool | None = None
    quality_close_status: str | None = None
    assigned_to_staff_code: str | None = None
    set_claim_attempted: bool = False
    set_claimed: bool = False
    set_started: bool = False
    set_finished: bool = False
    set_suspended: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunEventIn(BaseModel):
    instance_id: str | None = None
    level: str = "info"
    phase: str = ""
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    dashboard_visible: bool = True


class RunRepositoryIn(BaseModel):
    repo_name: str
    repo_path: str = ""
    remote_url: str = ""
    base_branch: str = ""
    branch_name: str = ""
    status: str = "planned"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactIn(BaseModel):
    repository_id: str | None = None
    category: str
    name: str
    status: str = "created"
    storage_uri: str | None = None
    content_type: str | None = None
    summary: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class CriticReportIn(BaseModel):
    node_id: str = "critic"
    status: str
    summary: str | None = None
    findings: list[dict[str, Any]] = Field(default_factory=list)
    score: float | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class EdocUploadIn(BaseModel):
    pave_job_id: str | None = None
    status: str
    file_name: str
    artifact_id: str | None = None
    full_log_included: bool = False
    critic_output_included: bool = False
    error_message: str | None = None


class LearningAssessmentIn(BaseModel):
    run_id: str | None = None
    pave_task_id: str | None = None
    status: str
    generated_artifact_id: str | None = None
    manual_changes_detected: bool = False
    diff_summary: str | None = None
    learnings: list[dict[str, Any]] = Field(default_factory=list)
    sbkb_document_id: str | None = None
    sbkb_status: str | None = None


class ToolingInventoryIn(BaseModel):
    instance_id: str | None = None
    tool_type: str
    name: str
    installed_version: str | None = None
    latest_version: str | None = None
    status: str = "unknown"
    source_url: str | None = None
    update_available: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolingUpdateRequest(BaseModel):
    instance_id: str | None = None
    to_version: str | None = None


async def require_worker(request: Request) -> dict[str, str]:
    expected = config.FACTORY_WORKER_TOKEN
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FACTORY_WORKER_TOKEN is not configured",
        )
    token = request.headers.get("x-factory-worker-token", "")
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid worker token")
    return {
        "actor_type": "worker",
        "actor_id": request.headers.get("x-factory-instance-id", "factory-worker"),
    }


def _actor_from_user(user: dict[str, Any]) -> tuple[str, str]:
    return ("admin", str(user.get("id") or user.get("email") or "admin"))


async def _build_evidence_report(run_id: str) -> str:
    run = await repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    events = await repo.list_run_events(run_id, limit=2000)
    repositories = await repo.list_run_repositories(run_id)
    artifacts = await repo.list_artifacts(run_id)
    critic_reports = await repo.list_critic_reports(run_id)
    edoc_uploads = await repo.list_edoc_uploads(run_id)

    lines = [
        "# Dark Factory Evidence Report",
        "",
        f"Run ID: {run['id']}",
        f"PAVE Task: {run.get('pave_task_id') or 'unknown'}",
        f"Work Item: {run.get('pave_work_item_id') or 'unknown'}",
        f"Incident: {run.get('pave_incident_id') or 'unknown'}",
        f"Board: {run.get('pave_board_name') or 'unknown'}",
        f"Staff Code: {run.get('staff_code') or 'unknown'}",
        f"Status: {run.get('status')} / {run.get('phase')}",
        f"eDoc Status: {run.get('e_doc_status') or 'not uploaded'}",
        "",
        "## Repositories",
        "",
    ]
    if repositories:
        lines.append("| Repository | Branch | PR | Build | Test | Status |")
        lines.append("|---|---|---|---|---|---|")
        for item in repositories:
            lines.append(
                "| {repo} | {branch} | {pr} | {build} | {test} | {status} |".format(
                    repo=item.get("repo_name") or "",
                    branch=item.get("branch_name") or "",
                    pr=item.get("pr_url") or "",
                    build=item.get("build_status") or "",
                    test=item.get("test_status") or "",
                    status=item.get("status") or "",
                )
            )
    else:
        lines.append("No repositories recorded.")

    lines.extend(["", "## Artifacts", ""])
    if artifacts:
        lines.append("| Category | Name | Status | URI | Summary |")
        lines.append("|---|---|---|---|---|")
        for item in artifacts:
            lines.append(
                "| {category} | {name} | {status} | {uri} | {summary} |".format(
                    category=item.get("category") or "",
                    name=item.get("name") or "",
                    status=item.get("status") or "",
                    uri=item.get("storage_uri") or "",
                    summary=(item.get("summary") or "").replace("\n", " "),
                )
            )
    else:
        lines.append("No artifacts recorded.")

    lines.extend(["", "## Critic Output", ""])
    if critic_reports:
        for critic in critic_reports:
            lines.append(f"### {critic.get('node_id') or 'critic'}")
            lines.append("")
            lines.append(f"Status: {critic.get('status')}")
            if critic.get("score") is not None:
                lines.append(f"Score: {critic.get('score')}")
            if critic.get("summary"):
                lines.append("")
                lines.append(str(critic["summary"]))
            findings = critic.get("findings") or []
            if findings:
                lines.append("")
                lines.append("| Severity | Finding | Evidence |")
                lines.append("|---|---|---|")
                for finding in findings:
                    lines.append(
                        "| {severity} | {finding} | {evidence} |".format(
                            severity=finding.get("severity", ""),
                            finding=str(finding.get("finding") or finding.get("message") or ""),
                            evidence=str(finding.get("evidence") or ""),
                        )
                    )
            lines.append("")
    else:
        lines.append("No critic output recorded.")

    lines.extend(["", "## eDoc Upload Attempts", ""])
    if edoc_uploads:
        lines.append("| File | Status | Document ID | Full Log | Critic Output | Error |")
        lines.append("|---|---|---|---|---|---|")
        for item in edoc_uploads:
            lines.append(
                "| {file} | {status} | {document} | {log} | {critic} | {error} |".format(
                    file=item.get("file_name") or "",
                    status=item.get("status") or "",
                    document=item.get("document_id") or "",
                    log="yes" if item.get("full_log_included") else "no",
                    critic="yes" if item.get("critic_output_included") else "no",
                    error=item.get("error_message") or "",
                )
            )
    else:
        lines.append("No eDoc upload attempts recorded.")

    lines.extend(["", "## Dashboard Log", ""])
    if events:
        for event in events:
            lines.append(
                "- {time} [{level}] {phase}: {message}".format(
                    time=event.get("created_at"),
                    level=event.get("level") or "info",
                    phase=event.get("phase") or "",
                    message=event.get("message") or "",
                )
            )
            payload = event.get("payload") or {}
            if payload:
                lines.append(f"  Payload: `{payload}`")
    else:
        lines.append("No dashboard events recorded.")

    return "\n".join(lines).rstrip() + "\n"


@router.get("/dashboard/summary")
async def dashboard_summary(_: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
    return await repo.dashboard_summary()


@router.get("/dashboard/stalled")
async def dashboard_stalled(_: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
    return {"mcps": await repo.list_stalled_mcps(), "runs": await repo.dashboard_failures()}


@router.get("/dashboard/queue")
async def dashboard_queue(_: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
    runs = await repo.list_runs(limit=100)
    return {
        "runs": [r for r in runs if r.get("status") in {"queued", "claimed", "running", "stalled"}]
    }


@router.get("/dashboard/failures")
async def dashboard_failures(_: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
    return {"runs": await repo.dashboard_failures()}


@router.get("/dashboard/throughput")
async def dashboard_throughput(_: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
    return {"days": await repo.dashboard_throughput()}


@router.get("/instances")
async def list_instances(_: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
    return {"instances": await repo.list_instances()}


@router.post("/instances/{instance_id}/pause")
async def pause_instance(
    instance_id: str,
    body: PauseRequest,
    user: dict[str, Any] = Depends(get_current_admin),
) -> dict[str, Any]:
    instance = await repo.pause_instance(instance_id, body.reason)
    if instance is None:
        raise HTTPException(status_code=404, detail="Instance not found")
    actor_type, actor_id = _actor_from_user(user)
    await repo.add_audit_entry(
        actor_type=actor_type,
        actor_id=actor_id,
        action="pause_instance",
        target_type="factory_instance",
        target_id=instance_id,
        payload={"reason": body.reason},
    )
    return instance


@router.post("/instances/{instance_id}/resume")
async def resume_instance(
    instance_id: str,
    user: dict[str, Any] = Depends(get_current_admin),
) -> dict[str, Any]:
    instance = await repo.resume_instance(instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Instance not found")
    actor_type, actor_id = _actor_from_user(user)
    await repo.add_audit_entry(
        actor_type=actor_type,
        actor_id=actor_id,
        action="resume_instance",
        target_type="factory_instance",
        target_id=instance_id,
    )
    return instance


@router.get("/mcps/readiness")
async def mcp_readiness(_: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
    return {"mcps": await repo.list_latest_mcp_readiness()}


@router.post("/mcps/reauth")
async def request_reauth(
    body: ReauthRequest,
    user: dict[str, Any] = Depends(get_current_admin),
) -> dict[str, Any]:
    actor_type, actor_id = _actor_from_user(user)
    session = await repo.create_reauth_session(
        instance_id=body.instance_id,
        mcp_name=body.mcp_name,
        reauth_url=body.reauth_url,
        requested_by_user_id=actor_id,
        metadata=body.metadata,
    )
    await repo.add_audit_entry(
        actor_type=actor_type,
        actor_id=actor_id,
        action="request_mcp_reauth",
        target_type="mcp",
        target_id=body.mcp_name,
        payload={"instance_id": body.instance_id, "session_id": str(session["id"])},
    )
    return session


@router.get("/mcps/reauth")
async def list_reauth(_: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
    return {"sessions": await repo.list_reauth_sessions()}


@router.patch("/mcps/reauth/{session_id}")
async def update_reauth(
    session_id: str,
    body: ReauthUpdateRequest,
    user: dict[str, Any] = Depends(get_current_admin),
) -> dict[str, Any]:
    session = await repo.update_reauth_session(session_id, status=body.status, metadata=body.metadata)
    if session is None:
        raise HTTPException(status_code=404, detail="Reauth session not found")
    actor_type, actor_id = _actor_from_user(user)
    await repo.add_audit_entry(
        actor_type=actor_type,
        actor_id=actor_id,
        action="update_mcp_reauth",
        target_type="mcp_reauth_session",
        target_id=session_id,
        payload={"status": body.status},
    )
    return session


@router.get("/runs")
async def list_runs(_: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
    return {"runs": await repo.list_runs(limit=100)}


@router.get("/runs/{run_id}")
async def get_run(run_id: str, _: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
    run = await repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "run": run,
        "events": await repo.list_run_events(run_id),
        "repositories": await repo.list_run_repositories(run_id),
        "artifacts": await repo.list_artifacts(run_id),
        "critic_reports": await repo.list_critic_reports(run_id),
        "edoc_uploads": await repo.list_edoc_uploads(run_id),
    }


@router.get("/runs/{run_id}/events")
async def get_run_events(
    run_id: str, _: dict[str, Any] = Depends(get_current_admin)
) -> dict[str, Any]:
    return {"events": await repo.list_run_events(run_id)}


@router.get("/runs/{run_id}/evidence-report", response_class=PlainTextResponse)
async def evidence_report(
    run_id: str, _: dict[str, Any] = Depends(get_current_admin)
) -> PlainTextResponse:
    return PlainTextResponse(await _build_evidence_report(run_id), media_type="text/markdown")


@router.get("/tooling")
async def list_tooling(_: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
    return {
        "tools": await repo.list_tooling_inventory(),
        "update_jobs": await repo.list_tooling_update_jobs(),
    }


@router.post("/tooling/check-latest")
async def check_latest_tooling(
    user: dict[str, Any] = Depends(get_current_admin),
) -> dict[str, Any]:
    known_tools = [
        {
            "tool_type": "mcp",
            "name": "ediprod",
            "source_url": "https://ediprod.mcp.wtg.zone",
            "status": "check_queued",
        },
        {
            "tool_type": "mcp",
            "name": "wtgkb",
            "source_url": "https://knowledge.mcp.wtg.zone",
            "status": "check_queued",
        },
        {
            "tool_type": "mcp",
            "name": "sbkb",
            "source_url": "C:/git/WTG.sbkb-mcp",
            "status": "check_queued",
        },
        {
            "tool_type": "prompt_repo",
            "name": "WTG.AI.Prompts",
            "source_url": "https://github.com/WiseTechGlobal/WTG.AI.Prompts",
            "status": "check_queued",
        },
    ]
    records = []
    for tool in known_tools:
        records.append(
            await repo.upsert_tooling_inventory(
                instance_id=None,
                tool_type=tool["tool_type"],
                name=tool["name"],
                installed_version=None,
                latest_version=None,
                status=tool["status"],
                source_url=tool["source_url"],
                update_available=False,
                metadata={
                    "requested_from": "dashboard",
                    "note": "A worker performs concrete latest-version checks.",
                },
            )
        )
    actor_type, actor_id = _actor_from_user(user)
    await repo.add_audit_entry(
        actor_type=actor_type,
        actor_id=actor_id,
        action="check_latest_tooling",
        target_type="tooling_inventory",
        target_id="all",
    )
    return {"tools": records}


@router.post("/tooling/{tool_id}/update")
async def update_tooling(
    tool_id: str,
    body: ToolingUpdateRequest,
    user: dict[str, Any] = Depends(get_current_admin),
) -> dict[str, Any]:
    tools = await repo.list_tooling_inventory()
    tool = next((item for item in tools if str(item["id"]) == tool_id), None)
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    actor_type, actor_id = _actor_from_user(user)
    job = await repo.create_tooling_update_job(
        instance_id=body.instance_id,
        tool_id=tool_id,
        requested_by_user_id=actor_id,
        from_version=tool.get("installed_version"),
        to_version=body.to_version or tool.get("latest_version"),
    )
    await repo.add_audit_entry(
        actor_type=actor_type,
        actor_id=actor_id,
        action="queue_tooling_update",
        target_type="tooling_inventory",
        target_id=tool_id,
        payload={"job_id": str(job["id"])},
    )
    return job


@router.get("/learning-assessments")
async def learning_assessments(_: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
    return {"assessments": await repo.list_learning_assessments()}


@router.post("/worker/instances/register")
async def worker_register_instance(
    body: InstanceRegistration,
    worker: dict[str, str] = Depends(require_worker),
) -> dict[str, Any]:
    instance = await repo.upsert_instance(
        instance_id=body.instance_id,
        name=body.name,
        host_name=body.host_name,
        staff_code=body.staff_code,
        detected_staff_code=body.detected_staff_code,
        board_name=body.board_name,
        status=body.status,
        version=body.version,
        process_id=body.process_id,
        capabilities=body.capabilities,
        config=body.config,
    )
    await repo.add_audit_entry(
        actor_type=worker["actor_type"],
        actor_id=worker["actor_id"],
        action="register_instance",
        target_type="factory_instance",
        target_id=body.instance_id,
        payload={"status": body.status},
    )
    return instance


@router.post("/worker/instances/{instance_id}/heartbeat")
async def worker_heartbeat(
    instance_id: str,
    body: InstanceHeartbeat,
    _: dict[str, str] = Depends(require_worker),
) -> dict[str, Any]:
    instance = await repo.heartbeat_instance(
        instance_id,
        status=body.status,
        detected_staff_code=body.detected_staff_code,
        process_id=body.process_id,
    )
    if instance is None:
        raise HTTPException(status_code=404, detail="Instance not found")
    return instance


@router.post("/worker/mcps/readiness")
async def worker_record_mcp(
    body: McpReadinessIn,
    _: dict[str, str] = Depends(require_worker),
) -> dict[str, Any]:
    return await repo.record_mcp_readiness(**body.model_dump())


@router.post("/worker/scout-cycles")
async def worker_create_scout_cycle(
    body: ScoutCycleCreate,
    _: dict[str, str] = Depends(require_worker),
) -> dict[str, Any]:
    return await repo.create_scout_cycle(**body.model_dump())


@router.patch("/worker/scout-cycles/{cycle_id}")
async def worker_finish_scout_cycle(
    cycle_id: str,
    body: ScoutCycleFinish,
    _: dict[str, str] = Depends(require_worker),
) -> dict[str, Any]:
    cycle = await repo.finish_scout_cycle(cycle_id, **body.model_dump())
    if cycle is None:
        raise HTTPException(status_code=404, detail="Scout cycle not found")
    return cycle


@router.post("/worker/runs")
async def worker_create_run(
    body: RunCreate,
    _: dict[str, str] = Depends(require_worker),
) -> dict[str, Any]:
    return await repo.create_run(**body.model_dump())


@router.patch("/worker/runs/{run_id}")
async def worker_update_run(
    run_id: str,
    body: RunPatch,
    _: dict[str, str] = Depends(require_worker),
) -> dict[str, Any]:
    data = body.model_dump()
    if data.get("metadata") == {}:
        data["metadata"] = None
    run = await repo.update_run(run_id, **data)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/worker/runs/{run_id}/events")
async def worker_append_event(
    run_id: str,
    body: RunEventIn,
    worker: dict[str, str] = Depends(require_worker),
) -> dict[str, Any]:
    return await repo.append_run_event(
        run_id=run_id,
        instance_id=body.instance_id or worker["actor_id"],
        level=body.level,
        phase=body.phase,
        message=body.message,
        payload=body.payload,
        dashboard_visible=body.dashboard_visible,
    )


@router.post("/worker/runs/{run_id}/repositories")
async def worker_add_repository(
    run_id: str,
    body: RunRepositoryIn,
    _: dict[str, str] = Depends(require_worker),
) -> dict[str, Any]:
    return await repo.add_run_repository(run_id=run_id, **body.model_dump())


@router.post("/worker/runs/{run_id}/artifacts")
async def worker_add_artifact(
    run_id: str,
    body: ArtifactIn,
    _: dict[str, str] = Depends(require_worker),
) -> dict[str, Any]:
    return await repo.add_artifact(run_id=run_id, **body.model_dump())


@router.post("/worker/runs/{run_id}/critic")
async def worker_add_critic(
    run_id: str,
    body: CriticReportIn,
    _: dict[str, str] = Depends(require_worker),
) -> dict[str, Any]:
    return await repo.add_critic_report(run_id=run_id, **body.model_dump())


@router.post("/worker/runs/{run_id}/edoc-uploads")
async def worker_add_edoc_upload(
    run_id: str,
    body: EdocUploadIn,
    _: dict[str, str] = Depends(require_worker),
) -> dict[str, Any]:
    return await repo.create_edoc_upload(run_id=run_id, **body.model_dump())


@router.post("/worker/learning-assessments")
async def worker_create_learning_assessment(
    body: LearningAssessmentIn,
    _: dict[str, str] = Depends(require_worker),
) -> dict[str, Any]:
    return await repo.create_learning_assessment(**body.model_dump())


@router.post("/worker/tooling/inventory")
async def worker_record_tooling(
    body: ToolingInventoryIn,
    _: dict[str, str] = Depends(require_worker),
) -> dict[str, Any]:
    return await repo.upsert_tooling_inventory(**body.model_dump())
