"""Small scout worker for the PAVE-driven Dark Factory.

The scout is intentionally cheap: it checks MCP/tool readiness, verifies the
staff-code constraint, and only escalates to an agent when PAVE lifecycle calls
are available. In environments without a concrete ediProd adapter it reports a
stalled state instead of mutating PAVE.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from backend import config
from backend.factory.edi_cli import (
    EdiCli,
    EdiCliError,
    find_playing_tasks,
    select_startable_candidate,
)

DEFAULT_API_BASE = os.environ.get("FACTORY_API_BASE", "http://127.0.0.1:8000/api")
REQUIRED_MCPS = ("ediprod", "wtgkb", "sbkb")


@dataclass(frozen=True)
class McpProbeResult:
    name: str
    status: str
    detail: str
    metadata: dict[str, Any]


class FactoryApi:
    def __init__(self, base_url: str, token: str, instance_id: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.instance_id = instance_id

    async def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        headers = {
            "X-Factory-Worker-Token": self.token,
            "X-Factory-Instance-Id": self.instance_id,
        }
        async with httpx.AsyncClient(base_url=self.base_url, timeout=20) as client:
            response = await client.request(method, path, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

    async def post(self, path: str, payload: dict[str, Any]) -> Any:
        return await self._request("POST", path, payload)

    async def patch(self, path: str, payload: dict[str, Any]) -> Any:
        return await self._request("PATCH", path, payload)


def _run_command(args: list[str], timeout: int = 10, cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _codex_mcp_lines() -> tuple[int, str]:
    codex = shutil.which("codex")
    if not codex:
        return (127, "codex executable not found on PATH")
    try:
        result = _run_command([codex, "mcp", "list"], timeout=15)
    except subprocess.TimeoutExpired:
        return (124, "codex mcp list timed out")
    output = "\n".join(part for part in [result.stdout, result.stderr] if part).strip()
    return (result.returncode, output)


def _git_head(path: str) -> tuple[str | None, str]:
    git_dir = Path(path)
    if not git_dir.exists():
        return (None, "path does not exist")
    if not (git_dir / ".git").exists():
        return (None, "path is not a git repository")
    result = _run_command(["git", "rev-parse", "--short=12", "HEAD"], cwd=str(git_dir), timeout=10)
    if result.returncode != 0:
        return (None, result.stderr.strip() or result.stdout.strip() or "git rev-parse failed")
    return (result.stdout.strip(), "ok")


def _probe_mcp_configured(name: str, codex_output: str) -> tuple[bool, str]:
    for line in codex_output.splitlines():
        parts = line.split()
        if parts and parts[0].lower() == name.lower():
            return (True, line.strip())
    return (False, "")


def _detect_staff_code() -> tuple[str, str]:
    detected = os.environ.get("PAVE_DETECTED_STAFF_CODE", "").strip()
    if detected:
        return (detected, "detected from PAVE_DETECTED_STAFF_CODE")
    if shutil.which("edi"):
        try:
            profile = EdiCli().get_own_staff_profile()
            return (profile.code, f"detected from edi OAuth profile: {profile.display_name or profile.code}")
        except EdiCliError as exc:
            configured = os.environ.get("PAVE_STAFF_CODE", config.PAVE_STAFF_CODE).strip()
            return (configured, f"using configured fallback; edi staff detection failed: {exc}")
    configured = os.environ.get("PAVE_STAFF_CODE", config.PAVE_STAFF_CODE).strip()
    return (configured, "using configured fallback; ediProd OAuth staff-code lookup unavailable")


def probe_mcps() -> list[McpProbeResult]:
    returncode, codex_output = _codex_mcp_lines()
    edi_cli = shutil.which("edi")
    adapter = os.environ.get("FACTORY_PAVE_ADAPTER", "auto").strip().lower()
    adapter_url = os.environ.get("FACTORY_PAVE_ADAPTER_URL", "").strip()
    edi_profile: dict[str, Any] | None = None
    edi_auth_error = ""
    if edi_cli:
        try:
            profile = EdiCli(edi_cli).get_own_staff_profile()
            edi_profile = profile.raw
        except EdiCliError as exc:
            edi_auth_error = str(exc)
    results: list[McpProbeResult] = []

    for name in REQUIRED_MCPS:
        configured, line = _probe_mcp_configured(name, codex_output)
        metadata = {
            "codex_mcp_returncode": returncode,
            "codex_mcp_line": line,
            "adapter": adapter,
            "edi_cli": edi_cli,
            "edi_profile": edi_profile,
        }
        if returncode != 0:
            results.append(
                McpProbeResult(
                    name=name,
                    status="unavailable",
                    detail=codex_output,
                    metadata=metadata,
                )
            )
            continue
        if not configured:
            results.append(
                McpProbeResult(
                    name=name,
                    status="unavailable",
                    detail=f"{name} is not listed by codex mcp list",
                    metadata=metadata,
                )
            )
            continue
        if name == "ediprod" and adapter in {"auto", ""} and not edi_cli and not adapter_url:
            results.append(
                McpProbeResult(
                    name=name,
                    status="unavailable",
                    detail=(
                        "ediprod is configured in Codex, but this worker has no concrete "
                        "callable PAVE adapter and no edi CLI fallback."
                    ),
                    metadata=metadata,
                )
            )
            continue
        if name == "ediprod" and adapter in {"auto", "edi-cli"} and edi_cli and edi_auth_error:
            results.append(
                McpProbeResult(
                    name=name,
                    status="unauthenticated",
                    detail=f"edi CLI is present but staff profile lookup failed: {edi_auth_error}",
                    metadata={**metadata, "edi_auth_error": edi_auth_error},
                )
            )
            continue
        if name == "ediprod" and adapter == "ediprod-mcp" and not adapter_url:
            results.append(
                McpProbeResult(
                    name=name,
                    status="degraded",
                    detail="FACTORY_PAVE_ADAPTER=ediprod-mcp requires FACTORY_PAVE_ADAPTER_URL",
                    metadata=metadata,
                )
            )
            continue
        results.append(
            McpProbeResult(
                name=name,
                status="ready",
                detail=(
                    f"{name} is configured"
                    if name != "ediprod" or not edi_profile
                    else f"ediprod is configured; edi CLI authenticated as {edi_profile.get('code')}"
                ),
                metadata=metadata,
            )
        )
    return results


def collect_tooling_inventory(instance_id: str) -> list[dict[str, Any]]:
    codex_returncode, codex_output = _codex_mcp_lines()
    edi_version = None
    edi_status = "missing"
    edi_detail = "edi executable not found on PATH"
    if shutil.which("edi"):
        try:
            edi_version = EdiCli().version()
            edi_status = "present"
            edi_detail = "ok"
        except EdiCliError as exc:
            edi_status = "error"
            edi_detail = str(exc)
    sbkb_head, sbkb_detail = _git_head("C:/git/WTG.sbkb-mcp")
    prompts_head, prompts_detail = _git_head("C:/git/WTG.AI.Prompts")
    second_brain_exists = Path("C:/git/SecondBrain").exists()
    records = [
        {
            "instance_id": instance_id,
            "tool_type": "cli",
            "name": "edi",
            "installed_version": edi_version,
            "latest_version": None,
            "status": edi_status,
            "source_url": "https://github.com/WiseTechGlobal/mcp-ediprod",
            "update_available": False,
            "metadata": {"detail": edi_detail, "path": shutil.which("edi")},
        },
        {
            "instance_id": instance_id,
            "tool_type": "mcp",
            "name": "ediprod",
            "installed_version": None,
            "latest_version": None,
            "status": "configured" if "ediprod" in codex_output else "missing",
            "source_url": "https://ediprod.mcp.wtg.zone",
            "update_available": False,
            "metadata": {"codex_mcp_returncode": codex_returncode},
        },
        {
            "instance_id": instance_id,
            "tool_type": "mcp",
            "name": "wtgkb",
            "installed_version": None,
            "latest_version": None,
            "status": "configured" if "wtgkb" in codex_output else "missing",
            "source_url": "https://knowledge.mcp.wtg.zone",
            "update_available": False,
            "metadata": {"codex_mcp_returncode": codex_returncode},
        },
        {
            "instance_id": instance_id,
            "tool_type": "mcp",
            "name": "sbkb",
            "installed_version": sbkb_head,
            "latest_version": None,
            "status": "present" if sbkb_head else "missing",
            "source_url": "C:/git/WTG.sbkb-mcp",
            "update_available": False,
            "metadata": {"detail": sbkb_detail, "second_brain_exists": second_brain_exists},
        },
        {
            "instance_id": instance_id,
            "tool_type": "prompt_repo",
            "name": "WTG.AI.Prompts",
            "installed_version": prompts_head,
            "latest_version": None,
            "status": "present" if prompts_head else "missing",
            "source_url": "https://github.com/WiseTechGlobal/WTG.AI.Prompts",
            "update_available": False,
            "metadata": {"detail": prompts_detail},
        },
    ]
    return records


async def wait_for_backend(api: FactoryApi, timeout_seconds: int = 60) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            async with httpx.AsyncClient(base_url=api.base_url, timeout=5) as client:
                response = await client.get("/health")
                if response.status_code < 500:
                    return
        except httpx.HTTPError:
            await asyncio.sleep(2)
    raise RuntimeError(f"Factory backend did not become reachable at {api.base_url}")


async def register_instance(api: FactoryApi, *, board_name: str, staff_code: str) -> None:
    detected_staff_code, detection_detail = _detect_staff_code()
    await api.post(
        "/factory/worker/instances/register",
        {
            "instance_id": api.instance_id,
            "name": f"factory-scout-{socket.gethostname()}",
            "host_name": socket.gethostname(),
            "staff_code": staff_code,
            "detected_staff_code": detected_staff_code,
            "board_name": board_name,
            "status": "ready",
            "version": "pave-factory-2026-06-10",
            "process_id": str(os.getpid()),
            "capabilities": {
                "scout": True,
                "pave_claim": bool(shutil.which("edi"))
                or bool(os.environ.get("FACTORY_PAVE_ADAPTER_URL")),
                "multi_repo": True,
                "critic_node": True,
                "self_learning_task": True,
            },
            "config": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "staff_code_detection": detection_detail,
            },
        },
    )


async def report_readiness(api: FactoryApi) -> list[McpProbeResult]:
    results = probe_mcps()
    for result in results:
        await api.post(
            "/factory/worker/mcps/readiness",
            {
                "instance_id": api.instance_id,
                "mcp_name": result.name,
                "status": result.status,
                "detail": result.detail,
                "metadata": result.metadata,
            },
        )
    status = "ready" if all(item.status == "ready" for item in results) else "stalled"
    detected_staff_code, _ = _detect_staff_code()
    await api.post(
        f"/factory/worker/instances/{api.instance_id}/heartbeat",
        {
            "status": status,
            "detected_staff_code": detected_staff_code,
            "process_id": str(os.getpid()),
        },
    )
    return results


async def report_tooling(api: FactoryApi) -> None:
    for record in collect_tooling_inventory(api.instance_id):
        await api.post("/factory/worker/tooling/inventory", record)


async def scout_once(api: FactoryApi, *, board_name: str, staff_code: str) -> None:
    await register_instance(api, board_name=board_name, staff_code=staff_code)
    readiness = await report_readiness(api)
    await report_tooling(api)

    stalled = [item for item in readiness if item.status != "ready"]
    cycle = await api.post(
        "/factory/worker/scout-cycles",
        {
            "instance_id": api.instance_id,
            "board_name": board_name,
            "staff_code": staff_code,
            "status": "running",
            "candidate_count": 0,
            "local_model": config.FACTORY_LOCAL_SCOUT_MODEL,
            "token_estimate": 0,
            "input_snapshot": {
                "required_mcps": list(REQUIRED_MCPS),
                "readiness": [item.__dict__ for item in readiness],
            },
        },
    )

    if stalled:
        summary = "; ".join(f"{item.name}: {item.status} - {item.detail}" for item in stalled)
        await api.patch(
            f"/factory/worker/scout-cycles/{cycle['id']}",
            {
                "status": "stalled",
                "decision": "pause_before_pave_poll",
                "summary": summary,
                "output_snapshot": {
                    "reason": "required MCP unavailable",
                    "stalled_mcps": [item.__dict__ for item in stalled],
                },
            },
        )
        run = await api.post(
            "/factory/worker/runs",
            {
                "instance_id": api.instance_id,
                "pave_task_title": "PAVE scout paused before claiming work",
                "pave_board_name": board_name,
                "staff_code": staff_code,
                "status": "stalled",
                "phase": "mcp_readiness",
                "workflow_name": "pave-dark-factory-execute-task",
                "metadata": {
                    "no_pave_mutation": True,
                    "reason": "required MCP unavailable",
                },
            },
        )
        await api.post(
            f"/factory/worker/runs/{run['id']}/events",
            {
                "instance_id": api.instance_id,
                "level": "warning",
                "phase": "mcp_readiness",
                "message": "Scout paused before PAVE polling because required MCPs are not ready.",
                "payload": {"stalled_mcps": [item.__dict__ for item in stalled]},
            },
        )
        await api.post(
            f"/factory/worker/runs/{run['id']}/artifacts",
            {
                "category": "Audit",
                "name": "MCP readiness stall",
                "status": "created",
                "content_type": "application/json",
                "summary": summary,
                "payload": {"readiness": [item.__dict__ for item in readiness]},
            },
        )
        return

    if not shutil.which("edi"):
        await api.patch(
            f"/factory/worker/scout-cycles/{cycle['id']}",
            {
                "status": "stalled",
                "decision": "edi_cli_missing",
                "summary": "All MCPs are configured, but edi CLI is unavailable for PAVE polling.",
                "output_snapshot": {"readiness": [item.__dict__ for item in readiness]},
            },
        )
        return

    edi = EdiCli()
    tasks = edi.list_staff_tasks(
        staff_code,
        include_capability_pool=config.FACTORY_SCOUT_INCLUDE_CAPABILITY_POOL,
    )
    playing_tasks = find_playing_tasks(tasks)
    board_candidates = [
        task for task in tasks if task.board_name == board_name and task.ready_to_start
    ]

    if playing_tasks:
        await api.patch(
            f"/factory/worker/scout-cycles/{cycle['id']}",
            {
                "status": "blocked",
                "decision": "playing_task_present",
                "summary": f"{staff_code} already has {len(playing_tasks)} playing PAVE task(s).",
                "candidate_count": len(board_candidates),
                "output_snapshot": {
                    "playing_tasks": [task.raw for task in playing_tasks],
                    "board_candidates": [task.raw for task in board_candidates[:10]],
                },
            },
        )
        return

    candidate = select_startable_candidate(tasks, board_name=board_name)
    if candidate is None:
        await api.patch(
            f"/factory/worker/scout-cycles/{cycle['id']}",
            {
                "status": "ready",
                "decision": "no_startable_work",
                "summary": f"No ready-to-start tasks found on {board_name} for {staff_code}.",
                "candidate_count": 0,
                "output_snapshot": {
                    "task_count": len(tasks),
                    "board_candidate_count": len(board_candidates),
                },
            },
        )
        return

    resolved = edi.resolve_task(candidate)
    if resolved is None:
        await api.patch(
            f"/factory/worker/scout-cycles/{cycle['id']}",
            {
                "status": "stalled",
                "decision": "task_id_resolution_failed",
                "summary": (
                    f"Selected {candidate.job_number} / {candidate.task_type} but could not "
                    "resolve a unique PAVE task id."
                ),
                "candidate_count": len(board_candidates),
                "output_snapshot": {
                    "candidate": candidate.raw,
                    "resolution": "no_unique_match",
                },
            },
        )
        return

    await api.patch(
        f"/factory/worker/scout-cycles/{cycle['id']}",
        {
            "status": "ready",
            "selected_pave_task_id": resolved.task_id,
            "decision": "selected_startable_task",
            "summary": (
                f"Selected {candidate.job_number} / {candidate.task_type}: "
                f"{candidate.description}"
            ),
            "candidate_count": len(board_candidates),
            "output_snapshot": {
                "dry_run": config.FACTORY_SCOUT_DRY_RUN,
                "candidate": candidate.raw,
                "resolved_task": {
                    "task_id": resolved.task_id,
                    "workflow_id": resolved.workflow_id,
                    "task": resolved.raw,
                },
            },
        },
    )

    run_status = "queued" if config.FACTORY_SCOUT_DRY_RUN else "claimed"
    run_phase = "scout_handoff" if config.FACTORY_SCOUT_DRY_RUN else "claimed_started"
    lifecycle_output = ""
    if not config.FACTORY_SCOUT_DRY_RUN:
        fresh_tasks = edi.list_staff_tasks(
            staff_code,
            include_capability_pool=config.FACTORY_SCOUT_INCLUDE_CAPABILITY_POOL,
        )
        fresh_playing = find_playing_tasks(fresh_tasks)
        if fresh_playing:
            await api.patch(
                f"/factory/worker/scout-cycles/{cycle['id']}",
                {
                    "status": "blocked",
                    "decision": "playing_task_appeared_before_start",
                    "summary": "A playing task appeared before claim/start; PAVE mutation skipped.",
                    "output_snapshot": {"playing_tasks": [task.raw for task in fresh_playing]},
                },
            )
            return
        lifecycle_output = edi.start_task(resolved.task_id)

    run = await api.post(
        "/factory/worker/runs",
        {
            "instance_id": api.instance_id,
            "pave_task_id": resolved.task_id,
            "pave_work_item_id": candidate.job_number if candidate.job_number.startswith("WI") else None,
            "pave_incident_id": candidate.job_number if candidate.job_number.startswith("CS") else None,
            "pave_task_title": f"{candidate.job_number} / {candidate.task_type}: {candidate.description}",
            "pave_board_name": board_name,
            "staff_code": staff_code,
            "status": run_status,
            "phase": run_phase,
            "workflow_id": resolved.workflow_id,
            "workflow_name": "pave-dark-factory-execute-task",
            "metadata": {
                "dry_run": config.FACTORY_SCOUT_DRY_RUN,
                "candidate": candidate.raw,
                "resolved_task": resolved.raw,
                "lifecycle_output": lifecycle_output,
            },
        },
    )
    if not config.FACTORY_SCOUT_DRY_RUN:
        await api.patch(
            f"/factory/worker/runs/{run['id']}",
            {
                "set_claim_attempted": True,
                "set_claimed": True,
                "set_started": True,
                "metadata": {"lifecycle_output": lifecycle_output},
            },
        )
    await api.post(
        f"/factory/worker/runs/{run['id']}/events",
        {
            "instance_id": api.instance_id,
            "level": "info",
            "phase": run_phase,
            "message": (
                "Scout selected a startable PAVE task in dry-run mode."
                if config.FACTORY_SCOUT_DRY_RUN
                else "Scout claimed and started the selected PAVE task through edi CLI."
            ),
            "payload": {
                "dry_run": config.FACTORY_SCOUT_DRY_RUN,
                "candidate": candidate.raw,
                "resolved_task_id": resolved.task_id,
                "workflow_id": resolved.workflow_id,
            },
        },
    )
    await api.post(
        f"/factory/worker/runs/{run['id']}/artifacts",
        {
            "category": "Specs",
            "name": "PAVE scout handoff",
            "status": "created",
            "content_type": "application/json",
            "summary": f"{candidate.job_number} / {candidate.task_type}: {candidate.description}",
            "payload": {
                "candidate": candidate.raw,
                "resolved_task_id": resolved.task_id,
                "workflow_id": resolved.workflow_id,
                "dry_run": config.FACTORY_SCOUT_DRY_RUN,
            },
        },
    )


async def run_loop(api: FactoryApi, *, board_name: str, staff_code: str, once: bool) -> None:
    await wait_for_backend(api)
    while True:
        try:
            await scout_once(api, board_name=board_name, staff_code=staff_code)
        except Exception as exc:
            print(f"factory scout iteration failed: {exc}", file=sys.stderr)
        if once:
            return
        await asyncio.sleep(config.FACTORY_SCOUT_INTERVAL_SECONDS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the PAVE Dark Factory scout worker.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--instance-id", default=config.FACTORY_INSTANCE_ID or f"factory-{uuid.uuid4()}")
    parser.add_argument("--board-name", default=config.PAVE_BOARD_NAME)
    parser.add_argument("--staff-code", default=config.PAVE_STAFF_CODE)
    parser.add_argument("--once", action="store_true", help="Run one scout cycle and exit.")
    parser.add_argument(
        "--check-tooling",
        action="store_true",
        help="Only register tooling inventory and exit.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    token = config.FACTORY_WORKER_TOKEN
    if not token:
        raise RuntimeError("FACTORY_WORKER_TOKEN must be set for the worker")
    api = FactoryApi(args.api_base, token, args.instance_id)
    await wait_for_backend(api)
    await register_instance(api, board_name=args.board_name, staff_code=args.staff_code)
    if args.check_tooling:
        await report_readiness(api)
        await report_tooling(api)
        return
    await run_loop(api, board_name=args.board_name, staff_code=args.staff_code, once=args.once)


if __name__ == "__main__":
    asyncio.run(main())
