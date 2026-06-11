"""Small scout worker for the PAVE-driven Dark Factory.

The scout is intentionally cheap: it checks MCP/tool readiness, verifies the
staff-code constraint, and only escalates to an agent when PAVE lifecycle calls
are available. In environments without a concrete ediProd adapter it reports a
stalled state instead of mutating PAVE.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from backend import config
from backend.factory.edi_cli import (
    EdiCli,
    EdiCliError,
    find_playing_tasks,
    is_self_learning_task,
    select_startable_candidate,
)

DEFAULT_API_BASE = os.environ.get("FACTORY_API_BASE", "http://127.0.0.1:8000/api")
REQUIRED_MCPS = ("ediprod", "wtgkb", "sbkb")
REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class McpProbeResult:
    name: str
    status: str
    detail: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class StaffMutationCheck:
    allowed: bool
    detected_staff_code: str
    detail: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ArchonDispatchResult:
    status: str
    detail: str
    command: list[str]
    handoff_path: str | None
    stdout: str
    stderr: str


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

    async def get(self, path: str) -> Any:
        return await self._request("GET", path)

    async def get_text(self, path: str) -> str:
        headers = {
            "X-Factory-Worker-Token": self.token,
            "X-Factory-Instance-Id": self.instance_id,
        }
        async with httpx.AsyncClient(base_url=self.base_url, timeout=20) as client:
            response = await client.get(path, headers=headers)
            response.raise_for_status()
            return response.text


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


def _git_remote_head(path: str) -> tuple[str | None, str]:
    git_dir = Path(path)
    if not git_dir.exists():
        return (None, "path does not exist")
    if not (git_dir / ".git").exists():
        return (None, "path is not a git repository")
    remote = _run_command(["git", "remote", "get-url", "origin"], cwd=str(git_dir), timeout=10)
    if remote.returncode != 0:
        return (None, remote.stderr.strip() or remote.stdout.strip() or "git remote lookup failed")
    result = _run_command(["git", "ls-remote", "origin", "HEAD"], cwd=str(git_dir), timeout=30)
    if result.returncode != 0:
        return (None, result.stderr.strip() or result.stdout.strip() or "git ls-remote failed")
    first = result.stdout.strip().splitlines()[0].split()[0] if result.stdout.strip() else ""
    if not first:
        return (None, "remote HEAD not found")
    return (first[:12], f"origin {remote.stdout.strip()}")


def _project_skill_catalog() -> tuple[str | None, str, dict[str, Any]]:
    lock_path = REPO_ROOT / "skills-lock.json"
    if not lock_path.exists():
        return (
            None,
            "skills-lock.json not found",
            {"lock_path": str(lock_path), "skills": []},
        )
    try:
        raw = lock_path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return (
            None,
            f"failed to read skills-lock.json: {exc}",
            {"lock_path": str(lock_path), "skills": []},
        )
    skills = sorted((data.get("skills") or {}).keys())
    version = hashlib.sha256(raw).hexdigest()[:12]
    return (
        version,
        f"{len(skills)} locked project skills",
        {
            "lock_path": str(lock_path),
            "skills": skills,
            "lock_version": data.get("version"),
        },
    )


def _stable_instance_id(*, board_name: str, staff_code: str) -> str:
    raw = f"{socket.gethostname()}-{staff_code}-{board_name}".lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return f"factory-{slug or 'worker'}"


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


def _staff_mutation_check(staff_code: str) -> StaffMutationCheck:
    detected_staff_code, detection_detail = _detect_staff_code()
    detected = detected_staff_code.upper()
    configured = staff_code.strip().upper()
    allowed = detected == configured or config.FACTORY_ALLOW_OAUTH_STAFF_MISMATCH
    detail = (
        f"OAuth staff code {detected} matches execution staff code {configured}."
        if detected == configured
        else (
            f"OAuth staff code {detected} differs from execution staff code {configured}; "
            "live PAVE mutation is blocked unless FACTORY_ALLOW_OAUTH_STAFF_MISMATCH=true."
        )
    )
    if config.FACTORY_ALLOW_OAUTH_STAFF_MISMATCH and detected != configured:
        detail = (
            f"OAuth staff code {detected} differs from execution staff code {configured}; "
            "override FACTORY_ALLOW_OAUTH_STAFF_MISMATCH=true permits live PAVE mutation."
        )
    return StaffMutationCheck(
        allowed=allowed,
        detected_staff_code=detected_staff_code,
        detail=detail,
        metadata={
            "detection_detail": detection_detail,
            "configured_staff_code": staff_code,
            "detected_staff_code": detected_staff_code,
            "allow_oauth_staff_mismatch": config.FACTORY_ALLOW_OAUTH_STAFF_MISMATCH,
        },
    )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def probe_mcps(execution_staff_code: str | None = None) -> list[McpProbeResult]:
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
        if name == "ediprod" and execution_staff_code and edi_cli and edi_profile:
            detected_staff_code = str(edi_profile.get("code") or "").strip().upper()
            expected_staff_code = execution_staff_code.strip().upper()
            if (
                detected_staff_code
                and detected_staff_code != expected_staff_code
                and not config.FACTORY_ALLOW_OAUTH_STAFF_MISMATCH
                and not config.FACTORY_SCOUT_DRY_RUN
            ):
                results.append(
                    McpProbeResult(
                        name=name,
                        status="degraded",
                        detail=(
                            f"ediprod is authenticated as {detected_staff_code}, but the "
                            f"execution staff code is {expected_staff_code}; live mutation is blocked."
                        ),
                        metadata={
                            **metadata,
                            "execution_staff_code": execution_staff_code,
                            "allow_oauth_staff_mismatch": config.FACTORY_ALLOW_OAUTH_STAFF_MISMATCH,
                        },
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
                    else (
                        f"ediprod is configured; edi CLI authenticated as {edi_profile.get('code')}"
                        + (
                            f" while polling execution staff {execution_staff_code}"
                            if execution_staff_code
                            and str(edi_profile.get("code") or "").strip().upper()
                            != execution_staff_code.strip().upper()
                            else ""
                        )
                    )
                ),
                metadata={
                    **metadata,
                    "execution_staff_code": execution_staff_code,
                    "allow_oauth_staff_mismatch": config.FACTORY_ALLOW_OAUTH_STAFF_MISMATCH,
                    "dry_run": config.FACTORY_SCOUT_DRY_RUN,
                },
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
    sbkb_latest, sbkb_latest_detail = _git_remote_head("C:/git/WTG.sbkb-mcp")
    prompts_head, prompts_detail = _git_head("C:/git/WTG.AI.Prompts")
    prompts_latest, prompts_latest_detail = _git_remote_head("C:/git/WTG.AI.Prompts")
    skill_catalog_version, skill_catalog_detail, skill_catalog_metadata = _project_skill_catalog()
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
            "latest_version": sbkb_latest,
            "status": "present" if sbkb_head else "missing",
            "source_url": "C:/git/WTG.sbkb-mcp",
            "update_available": bool(sbkb_head and sbkb_latest and sbkb_head != sbkb_latest),
            "metadata": {
                "detail": sbkb_detail,
                "latest_detail": sbkb_latest_detail,
                "second_brain_exists": second_brain_exists,
            },
        },
        {
            "instance_id": instance_id,
            "tool_type": "skill_catalog",
            "name": "Project skills",
            "installed_version": skill_catalog_version,
            "latest_version": None,
            "status": "present" if skill_catalog_version else "missing",
            "source_url": "skills-lock.json",
            "update_available": False,
            "metadata": {
                "detail": skill_catalog_detail,
                **skill_catalog_metadata,
            },
        },
        {
            "instance_id": instance_id,
            "tool_type": "prompt_repo",
            "name": "WTG.AI.Prompts",
            "installed_version": prompts_head,
            "latest_version": prompts_latest,
            "status": "present" if prompts_head else "missing",
            "source_url": "https://github.com/WiseTechGlobal/WTG.AI.Prompts",
            "update_available": bool(
                prompts_head and prompts_latest and prompts_head != prompts_latest
            ),
            "metadata": {"detail": prompts_detail, "latest_detail": prompts_latest_detail},
        },
    ]
    return records


async def wait_for_backend(api: FactoryApi, timeout_seconds: int = 60) -> None:
    deadline = time.monotonic() + timeout_seconds
    headers = {
        "X-Factory-Worker-Token": api.token,
        "X-Factory-Instance-Id": api.instance_id,
    }
    while time.monotonic() < deadline:
        try:
            async with httpx.AsyncClient(base_url=api.base_url, timeout=5) as client:
                response = await client.get("/factory/worker/health", headers=headers)
                if response.status_code == 200:
                    return
                if response.status_code in {401, 403, 503}:
                    raise RuntimeError(
                        "Factory backend is reachable but worker authentication is not ready: "
                        f"HTTP {response.status_code} {response.text}"
                    )
        except httpx.HTTPError:
            await asyncio.sleep(2)
    raise RuntimeError(f"Factory backend did not become reachable at {api.base_url}")


async def register_instance(
    api: FactoryApi, *, board_name: str, staff_code: str, guardian_staff_code: str
) -> None:
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
                "execution_staff_code": staff_code,
                "guardian_staff_code": guardian_staff_code,
                "dry_run": config.FACTORY_SCOUT_DRY_RUN,
                "archon_execute": config.FACTORY_ARCHON_EXECUTE,
            },
        },
    )


async def report_readiness(api: FactoryApi, *, staff_code: str) -> list[McpProbeResult]:
    results = probe_mcps(staff_code)
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


def _tooling_update_path(tool: dict[str, Any]) -> Path | None:
    name = str(tool.get("name") or "")
    if name == "sbkb":
        return Path("C:/git/WTG.sbkb-mcp")
    if name == "WTG.AI.Prompts":
        return Path("C:/git/WTG.AI.Prompts")
    return None


async def process_tooling_update_jobs(api: FactoryApi) -> None:
    payload = await api.get("/factory/worker/tooling/update-jobs")
    for job in payload.get("jobs", []):
        job_id = str(job.get("id"))
        tool = job.get("tool") or {}
        tool_name = str(tool.get("name") or job.get("tool_id") or "unknown")
        await api.patch(
            f"/factory/worker/tooling/update-jobs/{job_id}",
            {
                "status": "running",
                "set_started": True,
                "log_entry": {
                    "time": _now_iso(),
                    "message": f"Starting tooling update for {tool_name}",
                },
            },
        )
        path = _tooling_update_path(tool)
        if path is None:
            await api.patch(
                f"/factory/worker/tooling/update-jobs/{job_id}",
                {
                    "status": "failed",
                    "set_finished": True,
                    "error_message": f"No automated update handler for {tool_name}",
                    "log_entry": {
                        "time": _now_iso(),
                        "message": f"No automated update handler for {tool_name}",
                    },
                },
            )
            continue
        if not path.exists():
            await api.patch(
                f"/factory/worker/tooling/update-jobs/{job_id}",
                {
                    "status": "failed",
                    "set_finished": True,
                    "error_message": f"Tooling path does not exist: {path}",
                    "log_entry": {
                        "time": _now_iso(),
                        "message": f"Tooling path does not exist: {path}",
                    },
                },
            )
            continue
        result = _run_command(["git", "pull", "--ff-only"], cwd=str(path), timeout=120)
        status = "completed" if result.returncode == 0 else "failed"
        await api.patch(
            f"/factory/worker/tooling/update-jobs/{job_id}",
            {
                "status": status,
                "set_finished": True,
                "error_message": None if result.returncode == 0 else result.stderr.strip(),
                "log_entry": {
                    "time": _now_iso(),
                    "command": "git pull --ff-only",
                    "cwd": str(path),
                    "returncode": result.returncode,
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip(),
                },
            },
        )
    if payload.get("jobs"):
        await report_tooling(api)


def _run_artifacts_dir(run_id: str) -> Path:
    path = REPO_ROOT / ".factory" / "runs" / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json_artifact(run_id: str, name: str, payload: dict[str, Any]) -> Path:
    path = _run_artifacts_dir(run_id) / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _dispatch_archon_workflow(
    run_id: str, handoff: dict[str, Any], *, workflow_name: str
) -> ArchonDispatchResult:
    handoff_path = _write_json_artifact(run_id, "pave-task-handoff.json", handoff)
    if not config.FACTORY_ARCHON_EXECUTE:
        return ArchonDispatchResult(
            status="skipped",
            detail="FACTORY_ARCHON_EXECUTE=false; Archon dispatch skipped.",
            command=[],
            handoff_path=str(handoff_path),
            stdout="",
            stderr="",
        )

    archon = shutil.which("archon")
    if not archon:
        return ArchonDispatchResult(
            status="failed",
            detail="archon executable not found on PATH",
            command=[],
            handoff_path=str(handoff_path),
            stdout="",
            stderr="",
        )

    message = (
        f"Execute PAVE dark factory run {run_id}. "
        f"Read the handoff JSON at {handoff_path} and follow the C50/PWS guardian policy."
    )
    command = [
        archon,
        "workflow",
        "run",
        workflow_name,
        "--cwd",
        str(REPO_ROOT),
        "--detach",
        message,
    ]
    try:
        result = _run_command(command, timeout=60, cwd=str(REPO_ROOT))
    except subprocess.TimeoutExpired:
        return ArchonDispatchResult(
            status="failed",
            detail="archon workflow dispatch timed out",
            command=command,
            handoff_path=str(handoff_path),
            stdout="",
            stderr="",
        )
    status = "running" if result.returncode == 0 else "failed"
    detail = (
        "Archon workflow dispatched in detached mode."
        if result.returncode == 0
        else "Archon workflow dispatch failed."
    )
    return ArchonDispatchResult(
        status=status,
        detail=detail,
        command=command,
        handoff_path=str(handoff_path),
        stdout=result.stdout.strip(),
        stderr=result.stderr.strip(),
    )


async def escalate_task_to_guardian(
    api: FactoryApi,
    *,
    task_id: str,
    guardian_staff_code: str,
    reason: str,
    run_id: str | None = None,
    job_number: str | None = None,
    phase: str = "guardian_escalation",
) -> dict[str, Any]:
    edi = EdiCli()
    note = "\n".join(
        [
            "Dark Factory guardian escalation",
            f"Time: {_now_iso()}",
            f"Task: {task_id}",
            f"Guardian: {guardian_staff_code}",
            f"Reason: {reason}",
        ]
    )
    operations: dict[str, Any] = {}
    for name, operation in (
        ("notes_append", lambda: edi.append_task_notes(task_id, note)),
        ("suspend", lambda: edi.suspend_task(task_id)),
        ("assign", lambda: edi.assign_task(task_id, guardian_staff_code)),
    ):
        try:
            operations[name] = {"status": "ok", "output": operation()}
        except EdiCliError as exc:
            operations[name] = {"status": "failed", "error": str(exc)}

    assigned = operations.get("assign", {}).get("status") == "ok"
    suspended = operations.get("suspend", {}).get("status") == "ok"
    escalation_status = "suspended" if assigned and suspended else "stalled" if assigned else "failed"
    if run_id is None:
        run = await api.post(
            "/factory/worker/runs",
            {
                "instance_id": api.instance_id,
                "pave_task_id": task_id,
                "pave_work_item_id": job_number if (job_number or "").startswith("WI") else None,
                "pave_incident_id": job_number if (job_number or "").startswith("CS") else None,
                "pave_task_title": f"Guardian escalation for {task_id}",
                "pave_board_name": config.PAVE_BOARD_NAME,
                "staff_code": config.PAVE_STAFF_CODE,
                "status": escalation_status,
                "phase": phase,
                "workflow_name": config.FACTORY_ARCHON_WORKFLOW_NAME,
                "metadata": {"guardian_escalation": operations, "reason": reason},
            },
        )
        run_id = run["id"]
    else:
        await api.patch(
            f"/factory/worker/runs/{run_id}",
            {
                "status": escalation_status,
                "phase": phase,
                "failure_reason": reason,
                "assigned_to_staff_code": guardian_staff_code if assigned else None,
                "set_suspended": suspended,
                "metadata": {"guardian_escalation": operations, "reason": reason},
            },
        )
    await api.patch(
        f"/factory/worker/runs/{run_id}",
        {
            "assigned_to_staff_code": guardian_staff_code if assigned else None,
            "set_suspended": suspended,
            "metadata": {"guardian_escalation": operations, "reason": reason},
        },
    )

    await api.post(
        f"/factory/worker/runs/{run_id}/events",
        {
            "instance_id": api.instance_id,
            "level": "warning" if assigned else "error",
            "phase": phase,
            "message": (
                f"Task suspended and assigned to guardian {guardian_staff_code}."
                if assigned and suspended
                else f"Task assigned to guardian {guardian_staff_code}, but suspend did not complete."
                if assigned
                else f"Guardian escalation to {guardian_staff_code} failed."
            ),
            "payload": {"task_id": task_id, "reason": reason, "operations": operations},
        },
    )
    await api.post(
        f"/factory/worker/runs/{run_id}/artifacts",
        {
            "category": "Audit",
            "name": "Guardian escalation",
            "status": "created" if assigned and suspended else escalation_status,
            "content_type": "application/json",
            "summary": reason,
            "payload": {"task_id": task_id, "guardian_staff_code": guardian_staff_code, **operations},
        },
    )
    return {
        "run_id": run_id,
        "task_id": task_id,
        "assigned": assigned,
        "suspended": suspended,
        "operations": operations,
    }


async def upload_evidence_report(
    api: FactoryApi, *, run_id: str, job_number: str, doc_type: str = "INT"
) -> dict[str, Any]:
    report = await api.get_text(f"/factory/worker/runs/{run_id}/evidence-report")
    evidence_path = _run_artifacts_dir(run_id) / f"dark-factory-evidence-{run_id}.md"
    evidence_path.write_text(report, encoding="utf-8")
    edi = EdiCli()
    try:
        output = edi.upload_file(
            job_number,
            str(evidence_path),
            doc_type=doc_type,
            description=f"Dark Factory evidence report {run_id}",
        )
        status = "uploaded"
        error = None
    except EdiCliError as exc:
        output = ""
        status = "failed"
        error = str(exc)
    await api.post(
        f"/factory/worker/runs/{run_id}/edoc-uploads",
        {
            "pave_job_id": job_number,
            "status": status,
            "file_name": evidence_path.name,
            "full_log_included": True,
            "critic_output_included": True,
            "error_message": error,
        },
    )
    await api.patch(
        f"/factory/worker/runs/{run_id}",
        {
            "e_doc_status": status,
            "e_doc_report_id": output if status == "uploaded" else None,
            "metadata": {
                "evidence_report_path": str(evidence_path),
                "evidence_upload_output": output,
                "evidence_upload_error": error,
            },
        },
    )
    await api.post(
        f"/factory/worker/runs/{run_id}/events",
        {
            "instance_id": api.instance_id,
            "level": "info" if status == "uploaded" else "error",
            "phase": "evidence_upload",
            "message": (
                f"Evidence report uploaded to {job_number} eDoc."
                if status == "uploaded"
                else f"Evidence report upload to {job_number} eDoc failed."
            ),
            "payload": {
                "job_number": job_number,
                "file_path": str(evidence_path),
                "status": status,
                "output": output,
                "error": error,
            },
        },
    )
    return {
        "run_id": run_id,
        "job_number": job_number,
        "status": status,
        "file_path": str(evidence_path),
        "output": output,
        "error": error,
    }


async def scout_once(
    api: FactoryApi, *, board_name: str, staff_code: str, guardian_staff_code: str
) -> None:
    await register_instance(
        api, board_name=board_name, staff_code=staff_code, guardian_staff_code=guardian_staff_code
    )
    readiness = await report_readiness(api, staff_code=staff_code)
    await report_tooling(api)
    await process_tooling_update_jobs(api)

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
                "execution_staff_code": staff_code,
                "guardian_staff_code": guardian_staff_code,
                "dry_run": config.FACTORY_SCOUT_DRY_RUN,
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
                "workflow_name": config.FACTORY_ARCHON_WORKFLOW_NAME,
                "metadata": {
                    "no_pave_mutation": True,
                    "reason": "required MCP unavailable",
                    "guardian_staff_code": guardian_staff_code,
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
    discovery_sources = ["edi_staff_tasks"]
    fallback_error = ""
    tasks = edi.list_staff_tasks(
        staff_code,
        include_capability_pool=config.FACTORY_SCOUT_INCLUDE_CAPABILITY_POOL,
    )
    if config.FACTORY_PAVE_BOARD_CHANNEL_FALLBACK:
        try:
            global_playing_tasks = edi.list_global_playing_tasks(staff_code)
            board_channel_tasks = edi.list_board_channel_tasks(
                board_name=board_name,
                staff_code=staff_code,
            )
            seen_task_ids = {
                str(task.raw.get("taskId") or task.raw.get("id") or "").lower()
                for task in tasks
            }
            for task in [*global_playing_tasks, *board_channel_tasks]:
                task_id = str(task.raw.get("taskId") or task.raw.get("id") or "").lower()
                if task_id and task_id in seen_task_ids:
                    continue
                if task_id:
                    seen_task_ids.add(task_id)
                tasks.append(task)
            discovery_sources.append("glow_board_channel")
        except EdiCliError as exc:
            fallback_error = str(exc)

    playing_tasks = find_playing_tasks(tasks)
    board_candidates = [
        task for task in tasks if task.board_name == board_name and task.ready_to_start
    ]

    if fallback_error and not tasks:
        await api.patch(
            f"/factory/worker/scout-cycles/{cycle['id']}",
            {
                "status": "stalled",
                "decision": "board_channel_poll_failed",
                "summary": f"Could not query PAVE board channel fallback: {fallback_error}",
                "candidate_count": 0,
                "output_snapshot": {
                    "discovery_sources": discovery_sources,
                    "fallback_error": fallback_error,
                },
            },
        )
        return

    if playing_tasks:
        await api.patch(
            f"/factory/worker/scout-cycles/{cycle['id']}",
            {
                "status": "blocked",
                "decision": "playing_task_present",
                "summary": f"{staff_code} already has {len(playing_tasks)} playing PAVE task(s).",
                "candidate_count": len(board_candidates),
                "output_snapshot": {
                    "discovery_sources": discovery_sources,
                    "fallback_error": fallback_error,
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
                    "discovery_sources": discovery_sources,
                    "fallback_error": fallback_error,
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
                    "discovery_sources": discovery_sources,
                    "fallback_error": fallback_error,
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
                "discovery_sources": discovery_sources,
                "fallback_error": fallback_error,
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

    active_run = await api.get(
        f"/factory/worker/runs/active?pave_task_id={quote(resolved.task_id)}"
        f"&include_dry_run={str(config.FACTORY_SCOUT_DRY_RUN).lower()}"
    )
    existing_run = active_run.get("run") if isinstance(active_run, dict) else None
    if existing_run:
        existing_metadata = existing_run.get("metadata") or {}
        if (
            config.FACTORY_SCOUT_DRY_RUN
            and existing_run.get("status") == "queued"
            and existing_metadata.get("dry_run") is True
        ):
            await api.patch(
                f"/factory/worker/runs/{existing_run['id']}",
                {
                    "status": "dry_run",
                    "phase": "scout_dry_run",
                    "metadata": {
                        "status_correction": (
                            "Dry-run scout selections are not execution queue items."
                        )
                    },
                },
            )
        await api.patch(
            f"/factory/worker/scout-cycles/{cycle['id']}",
            {
                "status": "ready",
                "selected_pave_task_id": resolved.task_id,
                "decision": "selected_task_already_queued",
                "summary": (
                    f"Selected {candidate.job_number} / {candidate.task_type}, "
                    f"but active run {existing_run['id']} already exists."
                ),
                "candidate_count": len(board_candidates),
                "output_snapshot": {
                    "discovery_sources": discovery_sources,
                    "fallback_error": fallback_error,
                    "dry_run": config.FACTORY_SCOUT_DRY_RUN,
                    "candidate": candidate.raw,
                    "existing_run": existing_run,
                },
            },
        )
        return

    task_kind = "self_learning" if is_self_learning_task(candidate) else "delivery"
    selected_workflow_name = (
        config.FACTORY_SELF_LEARNING_WORKFLOW_NAME
        if task_kind == "self_learning"
        else config.FACTORY_ARCHON_WORKFLOW_NAME
    )
    initial_phase = (
        "self_learning_dry_run"
        if config.FACTORY_SCOUT_DRY_RUN and task_kind == "self_learning"
        else "scout_dry_run"
        if config.FACTORY_SCOUT_DRY_RUN
        else "self_learning_handoff"
        if task_kind == "self_learning"
        else "scout_handoff"
    )

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
            "status": "dry_run" if config.FACTORY_SCOUT_DRY_RUN else "queued",
            "phase": initial_phase,
            "workflow_id": resolved.workflow_id,
            "workflow_name": selected_workflow_name,
            "metadata": {
                "dry_run": config.FACTORY_SCOUT_DRY_RUN,
                "task_kind": task_kind,
                "self_learning_task": task_kind == "self_learning",
                "self_learning_rule": "type INT and description contains 'Self Learning'",
                "discovery_sources": discovery_sources,
                "fallback_error": fallback_error,
                "candidate": candidate.raw,
                "resolved_task": resolved.raw,
                "guardian_staff_code": guardian_staff_code,
            },
        },
    )
    handoff = {
        "run_id": run["id"],
        "instance_id": api.instance_id,
        "board_name": board_name,
        "execution_staff_code": staff_code,
        "guardian_staff_code": guardian_staff_code,
        "workflow_name": selected_workflow_name,
        "dry_run": config.FACTORY_SCOUT_DRY_RUN,
        "task_kind": task_kind,
        "self_learning_task": task_kind == "self_learning",
        "self_learning_rule": "type INT and description contains 'Self Learning'",
        "candidate": candidate.raw,
        "discovery_sources": discovery_sources,
        "fallback_error": fallback_error,
        "resolved_task": {
            "task_id": resolved.task_id,
            "workflow_id": resolved.workflow_id,
            "task": resolved.raw,
        },
        "policy": {
            "pave_is_source_of_truth": True,
            "play_guard_rechecked_before_start": True,
            "escalate_to_guardian_on_clarity_or_failure": True,
            "quality_iteration_mcp_unavailable_action": "suspend_and_assign_guardian",
        },
    }
    handoff_path = _write_json_artifact(run["id"], "pave-task-handoff.json", handoff)
    await api.post(
        f"/factory/worker/runs/{run['id']}/events",
        {
            "instance_id": api.instance_id,
            "level": "info",
            "phase": initial_phase,
            "message": (
                "Scout selected a dedicated PAVE self-learning task in dry-run mode."
                if config.FACTORY_SCOUT_DRY_RUN and task_kind == "self_learning"
                else "Scout selected a startable PAVE task in dry-run mode."
                if config.FACTORY_SCOUT_DRY_RUN
                else "Scout selected a dedicated PAVE self-learning task and prepared live handoff."
                if task_kind == "self_learning"
                else "Scout selected a startable PAVE task and prepared live handoff."
            ),
            "payload": {
                "dry_run": config.FACTORY_SCOUT_DRY_RUN,
                "task_kind": task_kind,
                "candidate": candidate.raw,
                "resolved_task_id": resolved.task_id,
                "workflow_id": resolved.workflow_id,
                "workflow_name": selected_workflow_name,
                "handoff_path": str(handoff_path),
            },
        },
    )
    await api.post(
        f"/factory/worker/runs/{run['id']}/artifacts",
        {
            "category": "Self Learning" if task_kind == "self_learning" else "Specs",
            "name": (
                "PAVE self-learning handoff"
                if task_kind == "self_learning"
                else "PAVE scout handoff"
            ),
            "status": "created",
            "content_type": "application/json",
            "summary": f"{candidate.job_number} / {candidate.task_type}: {candidate.description}",
            "payload": {
                "candidate": candidate.raw,
                "resolved_task_id": resolved.task_id,
                "workflow_id": resolved.workflow_id,
                "workflow_name": selected_workflow_name,
                "task_kind": task_kind,
                "guardian_staff_code": guardian_staff_code,
                "handoff_path": str(handoff_path),
                "dry_run": config.FACTORY_SCOUT_DRY_RUN,
            },
        },
    )

    if config.FACTORY_SCOUT_DRY_RUN:
        return

    if not config.FACTORY_ARCHON_EXECUTE:
        summary = "FACTORY_ARCHON_EXECUTE=false; live PAVE mutation skipped."
        await api.patch(
            f"/factory/worker/scout-cycles/{cycle['id']}",
            {
                "status": "stalled",
                "decision": "archon_dispatch_disabled",
                "summary": summary,
                "output_snapshot": {"candidate": candidate.raw, "handoff_path": str(handoff_path)},
            },
        )
        await api.patch(
            f"/factory/worker/runs/{run['id']}",
            {
                "status": "stalled",
                "phase": "archon_dispatch_disabled",
                "failure_reason": summary,
                "metadata": {"no_pave_mutation": True, "handoff_path": str(handoff_path)},
            },
        )
        await api.post(
            f"/factory/worker/runs/{run['id']}/events",
            {
                "instance_id": api.instance_id,
                "level": "warning",
                "phase": "archon_dispatch_disabled",
                "message": summary,
                "payload": {"no_pave_mutation": True},
            },
        )
        return

    if not shutil.which("archon"):
        summary = "archon executable not found; live PAVE mutation skipped."
        await api.patch(
            f"/factory/worker/scout-cycles/{cycle['id']}",
            {
                "status": "stalled",
                "decision": "archon_missing",
                "summary": summary,
                "output_snapshot": {"candidate": candidate.raw},
            },
        )
        await api.patch(
            f"/factory/worker/runs/{run['id']}",
            {
                "status": "stalled",
                "phase": "archon_missing",
                "failure_reason": summary,
                "metadata": {"no_pave_mutation": True},
            },
        )
        return

    mutation_check = _staff_mutation_check(staff_code)
    if not mutation_check.allowed:
        await api.patch(
            f"/factory/worker/scout-cycles/{cycle['id']}",
            {
                "status": "stalled",
                "decision": "oauth_staff_mismatch",
                "summary": mutation_check.detail,
                "output_snapshot": mutation_check.metadata,
            },
        )
        await api.patch(
            f"/factory/worker/runs/{run['id']}",
            {
                "status": "stalled",
                "phase": "oauth_staff_mismatch",
                "failure_reason": mutation_check.detail,
                "metadata": {"no_pave_mutation": True, **mutation_check.metadata},
            },
        )
        await api.post(
            f"/factory/worker/runs/{run['id']}/events",
            {
                "instance_id": api.instance_id,
                "level": "warning",
                "phase": "oauth_staff_mismatch",
                "message": mutation_check.detail,
                "payload": mutation_check.metadata,
            },
        )
        return

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
        await api.patch(
            f"/factory/worker/runs/{run['id']}",
            {
                "status": "stalled",
                "phase": "playing_task_guard",
                "failure_reason": "A playing task appeared before claim/start; PAVE mutation skipped.",
                "metadata": {"no_pave_mutation": True},
            },
        )
        return

    lifecycle_output = ""
    await api.patch(
        f"/factory/worker/runs/{run['id']}",
        {
            "status": "running",
            "phase": "claim_start",
            "set_claim_attempted": True,
            "metadata": {"mutation_check": mutation_check.metadata},
        },
    )
    try:
        lifecycle_output = edi.start_task(resolved.task_id)
    except EdiCliError as exc:
        reason = f"edi task start failed: {exc}"
        await api.post(
            f"/factory/worker/runs/{run['id']}/events",
            {
                "instance_id": api.instance_id,
                "level": "error",
                "phase": "claim_start",
                "message": reason,
                "payload": {"task_id": resolved.task_id},
            },
        )
        await escalate_task_to_guardian(
            api,
            task_id=resolved.task_id,
            guardian_staff_code=guardian_staff_code,
            reason=reason,
            run_id=run["id"],
            job_number=candidate.job_number,
            phase="claim_start_failed",
        )
        return

    await api.patch(
        f"/factory/worker/runs/{run['id']}",
        {
            "status": "claimed",
            "phase": "claimed_started",
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
            "phase": "claimed_started",
            "message": "Scout claimed and started the selected PAVE task through edi CLI.",
            "payload": {"lifecycle_output": lifecycle_output, "task_id": resolved.task_id},
        },
    )

    dispatch = _dispatch_archon_workflow(
        run["id"], handoff, workflow_name=selected_workflow_name
    )
    await api.post(
        f"/factory/worker/runs/{run['id']}/artifacts",
        {
            "category": "Self Learning" if task_kind == "self_learning" else "Coding",
            "name": (
                "Archon self-learning workflow dispatch"
                if task_kind == "self_learning"
                else "Archon workflow dispatch"
            ),
            "status": dispatch.status,
            "content_type": "application/json",
            "summary": dispatch.detail,
            "payload": {
                "command": dispatch.command,
                "handoff_path": dispatch.handoff_path,
                "stdout": dispatch.stdout,
                "stderr": dispatch.stderr,
            },
        },
    )
    if dispatch.status != "running":
        await escalate_task_to_guardian(
            api,
            task_id=resolved.task_id,
            guardian_staff_code=guardian_staff_code,
            reason=dispatch.detail,
            run_id=run["id"],
            job_number=candidate.job_number,
            phase="archon_dispatch_failed",
        )
        return
    await api.patch(
        f"/factory/worker/runs/{run['id']}",
        {
            "status": "running",
            "phase": "archon_dispatched",
            "metadata": {
                "archon_dispatch": {
                    "command": dispatch.command,
                    "handoff_path": dispatch.handoff_path,
                    "stdout": dispatch.stdout,
                    "stderr": dispatch.stderr,
                }
            },
        },
    )
    await api.post(
        f"/factory/worker/runs/{run['id']}/events",
        {
            "instance_id": api.instance_id,
            "level": "info",
            "phase": "archon_dispatched",
            "message": "Archon workflow dispatched for the claimed PAVE task.",
            "payload": {"handoff_path": dispatch.handoff_path, "stdout": dispatch.stdout},
        },
    )


async def run_loop(
    api: FactoryApi, *, board_name: str, staff_code: str, guardian_staff_code: str, once: bool
) -> None:
    await wait_for_backend(api)
    while True:
        try:
            await scout_once(
                api,
                board_name=board_name,
                staff_code=staff_code,
                guardian_staff_code=guardian_staff_code,
            )
        except Exception as exc:
            print(f"factory scout iteration failed: {exc}", file=sys.stderr)
        if once:
            return
        await asyncio.sleep(config.FACTORY_SCOUT_INTERVAL_SECONDS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the PAVE Dark Factory scout worker.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--instance-id", default="")
    parser.add_argument("--board-name", default=config.PAVE_BOARD_NAME)
    parser.add_argument("--staff-code", default=config.PAVE_STAFF_CODE)
    parser.add_argument("--guardian-staff-code", default=config.PAVE_GUARDIAN_STAFF_CODE)
    parser.add_argument("--once", action="store_true", help="Run one scout cycle and exit.")
    parser.add_argument(
        "--check-tooling",
        action="store_true",
        help="Only register tooling inventory and exit.",
    )
    parser.add_argument("--escalate-task-id", help="Suspend/assign one task to the guardian and exit.")
    parser.add_argument(
        "--escalation-reason",
        default="Dark Factory manual escalation",
        help="Reason written to the task notes and dashboard when escalating.",
    )
    parser.add_argument("--escalation-job-number", help="Optional WI/CS/PRJ number for the escalation.")
    parser.add_argument("--upload-evidence-run-id", help="Upload a run evidence report to eDoc and exit.")
    parser.add_argument("--upload-evidence-job-number", help="WI/CS/PRJ number for eDoc upload.")
    args = parser.parse_args()
    if not args.instance_id:
        args.instance_id = config.FACTORY_INSTANCE_ID or _stable_instance_id(
            board_name=args.board_name,
            staff_code=args.staff_code,
        )
    return args


async def main() -> None:
    args = parse_args()
    token = config.FACTORY_WORKER_TOKEN
    if not token:
        raise RuntimeError("FACTORY_WORKER_TOKEN must be set for the worker")
    api = FactoryApi(args.api_base, token, args.instance_id)
    await wait_for_backend(api)
    await register_instance(
        api,
        board_name=args.board_name,
        staff_code=args.staff_code,
        guardian_staff_code=args.guardian_staff_code,
    )
    if args.check_tooling:
        await report_readiness(api, staff_code=args.staff_code)
        await report_tooling(api)
        await process_tooling_update_jobs(api)
        return
    if args.escalate_task_id:
        await escalate_task_to_guardian(
            api,
            task_id=args.escalate_task_id,
            guardian_staff_code=args.guardian_staff_code,
            reason=args.escalation_reason,
            job_number=args.escalation_job_number,
        )
        return
    if args.upload_evidence_run_id:
        if not args.upload_evidence_job_number:
            raise RuntimeError("--upload-evidence-job-number is required with --upload-evidence-run-id")
        await upload_evidence_report(
            api,
            run_id=args.upload_evidence_run_id,
            job_number=args.upload_evidence_job_number,
        )
        return
    await run_loop(
        api,
        board_name=args.board_name,
        staff_code=args.staff_code,
        guardian_staff_code=args.guardian_staff_code,
        once=args.once,
    )


if __name__ == "__main__":
    asyncio.run(main())
