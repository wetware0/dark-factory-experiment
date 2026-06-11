"""edi CLI adapter for low-token PAVE scout operations."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from backend import config


class EdiCliError(RuntimeError):
    """Raised when the edi CLI is missing, unauthenticated, or returns invalid data."""


@dataclass(frozen=True)
class StaffProfile:
    code: str
    display_name: str | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class StaffTaskCandidate:
    sequence: int | None
    status: str
    ready_to_start: bool
    job_number: str
    job_title: str
    board_name: str
    board_zone: str
    task_type: str
    description: str
    capability: str
    has_notes: bool
    released_at: str
    startable_at: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class ResolvedTask:
    task_id: str
    workflow_id: str
    raw: dict[str, Any]


ZONE_RANK = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}

GLOW_AUTH_COOKIE_PATTERN = re.compile(r"Glow-Auth=[^;]+")


def _as_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _json_array(output: str, *, command: list[str]) -> list[dict[str, Any]]:
    output = output.strip()
    if not output:
        return []
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as exc:
        raise EdiCliError(f"edi returned non-JSON output for {' '.join(command)}") from exc
    if isinstance(parsed, dict):
        return [parsed]
    if not isinstance(parsed, list):
        raise EdiCliError(f"edi returned unexpected JSON for {' '.join(command)}")
    return [item for item in parsed if isinstance(item, dict)]


def normalise_staff_task(raw: dict[str, Any]) -> StaffTaskCandidate:
    return StaffTaskCandidate(
        sequence=_as_int(raw.get("sequence")),
        status=_as_text(raw.get("status")).upper(),
        ready_to_start=_as_bool(raw.get("readyToStart")),
        job_number=_as_text(raw.get("jobNumber")),
        job_title=_as_text(raw.get("jobTitle")),
        board_name=_as_text(raw.get("boardName")),
        board_zone=_as_text(raw.get("boardZone")),
        task_type=_as_text(raw.get("type")).upper(),
        description=_as_text(raw.get("description")),
        capability=_as_text(raw.get("capability")).upper(),
        has_notes=_as_bool(raw.get("hasNotes")),
        released_at=_as_text(raw.get("releasedAt")),
        startable_at=_as_text(raw.get("startableAt")),
        raw=raw,
    )


def normalise_staff_tasks(raw_tasks: list[dict[str, Any]]) -> list[StaffTaskCandidate]:
    return [normalise_staff_task(item) for item in raw_tasks]


def normalise_board_channel_tasks(
    board_name: str,
    staff_code: str,
    channel_tickets: list[dict[str, Any]],
) -> list[StaffTaskCandidate]:
    code = staff_code.upper()
    rows: list[dict[str, Any]] = []
    for ticket in channel_tickets:
        for item in ticket.get("items") or []:
            if _as_text(item.get("staffCode")).upper() != code:
                continue
            task_type = item.get("type") or {}
            capability = item.get("capability") or {}
            rows.append(
                {
                    "sequence": item.get("sequence"),
                    "status": item.get("taskStatus"),
                    "readyToStart": item.get("startable"),
                    "releasedAt": ticket.get("releaseDateTime"),
                    "startableAt": ticket.get("startableSince"),
                    "jobNumber": ticket.get("title"),
                    "jobTitle": ticket.get("subtitle"),
                    "boardName": board_name,
                    "boardZone": ticket.get("zone"),
                    "type": task_type.get("code"),
                    "description": item.get("title"),
                    "capability": capability.get("code"),
                    "hasNotes": item.get("hasNotes"),
                    "criticality": ticket.get("criticality"),
                    "taskId": item.get("key"),
                    "workflowId": ticket.get("key"),
                    "source": "glow_board_channel",
                    "ticket": ticket,
                    "item": item,
                }
            )
    return normalise_staff_tasks(rows)


def normalise_global_playing_tasks(rows: list[dict[str, Any]]) -> list[StaffTaskCandidate]:
    tasks: list[dict[str, Any]] = []
    for row in rows:
        parent_type = _as_text(row.get("P9_ParentTableCode"))
        parent_id = _as_text(row.get("P9_ParentID"))
        tasks.append(
            {
                "sequence": row.get("P9_Sequence"),
                "status": row.get("P9_Status"),
                "readyToStart": False,
                "releasedAt": "",
                "startableAt": "",
                "jobNumber": f"{parent_type}:{parent_id}" if parent_type or parent_id else "",
                "jobTitle": "",
                "boardName": "",
                "boardZone": "",
                "type": row.get("P9_Type"),
                "description": row.get("P9_Description"),
                "capability": row.get("P9_G4_RequiredCapability"),
                "hasNotes": bool(row.get("P9_Notes")),
                "taskId": row.get("P9_PK"),
                "workflowId": row.get("P9_FH_ProcessHeader"),
                "source": "glow_global_working_guard",
                "row": row,
            }
        )
    return normalise_staff_tasks(tasks)


def find_playing_tasks(tasks: list[StaffTaskCandidate]) -> list[StaffTaskCandidate]:
    return [task for task in tasks if task.status == "WRK"]


def is_self_learning_task(task: StaffTaskCandidate) -> bool:
    return task.task_type == "INT" and "self learning" in task.description.lower()


def select_startable_candidate(
    tasks: list[StaffTaskCandidate],
    *,
    board_name: str,
) -> StaffTaskCandidate | None:
    candidates = [
        task
        for task in tasks
        if task.board_name == board_name and task.ready_to_start and task.status != "WRK"
    ]
    if not candidates:
        return None

    def sort_key(task: StaffTaskCandidate) -> tuple[int, str, str, str, int]:
        zone = ZONE_RANK.get(task.board_zone.lower(), 99)
        startable_at = task.startable_at or "9999-12-31T23:59:59"
        released_at = task.released_at or "9999-12-31T23:59:59"
        return (zone, startable_at, released_at, task.job_number, task.sequence or 999999)

    return sorted(candidates, key=sort_key)[0]


def task_matches_candidate(task: dict[str, Any], candidate: StaffTaskCandidate) -> bool:
    if _as_text(task.get("type")).upper() != candidate.task_type:
        return False
    if _as_text(task.get("description")) != candidate.description:
        return False
    if _as_text(task.get("status")).upper() != candidate.status:
        return False
    if candidate.sequence is not None and _as_int(task.get("sequence")) != candidate.sequence:
        return False
    if candidate.capability and _as_text(task.get("capability")).upper() != candidate.capability:
        return False
    return _as_bool(task.get("startable")) == candidate.ready_to_start


def _odata_string(value: str) -> str:
    return value.replace("'", "''")


class GlowBoardClient:
    """Read-only Glow calls for PAVE board channels not exposed by the edi CLI."""

    def __init__(self, *, base_url: str | None = None, token_path: str | None = None) -> None:
        self.base_url = (base_url or config.FACTORY_GLOW_BASE_URL).rstrip("/")
        configured_token_path = token_path or config.FACTORY_GLOW_TOKEN_PATH
        self.token_path = (
            Path(configured_token_path).expanduser()
            if configured_token_path
            else Path.home() / ".glow" / "token.json"
        )

    def _read_token(self) -> str:
        try:
            data = json.loads(self.token_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise EdiCliError(f"Glow token file not found at {self.token_path}; run edi login.") from exc
        except json.JSONDecodeError as exc:
            raise EdiCliError(f"Glow token file is invalid JSON at {self.token_path}.") from exc
        token = _as_text(data.get("authenticationToken"))
        if not token:
            raise EdiCliError(f"Glow token file has no authenticationToken at {self.token_path}.")
        return token

    def _begin_session(self, client: httpx.Client) -> str:
        response = client.post(
            "/auth/v2/session/begin",
            json={
                "authenticationToken": self._read_token(),
                "sessionType": "general",
                "tokenType": 1,
            },
        )
        if response.status_code == 401:
            raise EdiCliError("Glow token was rejected; run edi login.")
        if response.status_code >= 400:
            raise EdiCliError(
                f"Glow session begin failed: HTTP {response.status_code} {response.text}"
            )
        match = GLOW_AUTH_COOKIE_PATTERN.search(response.headers.get("set-cookie", ""))
        if not match:
            raise EdiCliError("Glow session begin returned no Glow-Auth cookie.")
        return match.group(0)

    def _headers(self, cookie: str) -> dict[str, str]:
        return {"Cookie": cookie, "Accept": "application/json"}

    def _odata(
        self,
        client: httpx.Client,
        cookie: str,
        entity: str,
        *,
        filter_: str,
        select: list[str] | None = None,
        top: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {"$filter": filter_}
        if select:
            params["$select"] = ",".join(select)
        if top is not None:
            params["$top"] = str(top)
        response = client.get(
            f"/odata/BufferManagement/{entity}",
            params=params,
            headers=self._headers(cookie),
        )
        if response.status_code == 401:
            raise EdiCliError("Glow session expired during board query; run edi login.")
        if response.status_code >= 400:
            raise EdiCliError(
                f"Glow OData query failed for {entity}: HTTP {response.status_code} {response.text}"
            )
        data = response.json()
        rows = data.get("value")
        return rows if isinstance(rows, list) else []

    def _request_json(
        self,
        client: httpx.Client,
        cookie: str,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        response = client.request(
            method,
            path,
            json=payload,
            headers={**self._headers(cookie), "Content-Type": "application/json"},
        )
        if response.status_code == 401:
            raise EdiCliError("Glow session expired during board query; run edi login.")
        if response.status_code >= 400:
            raise EdiCliError(
                f"Glow request failed for {method} {path}: HTTP {response.status_code} {response.text}"
            )
        return response.json()

    def list_board_channel_tasks(
        self,
        *,
        board_name: str,
        staff_code: str,
    ) -> list[StaffTaskCandidate]:
        with httpx.Client(base_url=self.base_url, timeout=30) as client:
            cookie = self._begin_session(client)
            boards = self._odata(
                client,
                cookie,
                "BMBoardConfigurations",
                filter_=f"BMB_Name eq '{_odata_string(board_name)}'",
            )
            if not boards:
                return []
            board_id = _as_text(boards[0].get("BMB_PK"))
            if not board_id:
                return []
            section = self._request_json(
                client,
                cookie,
                "GET",
                f"/pave/boards/{board_id}/main-section",
            )
            section_id = _as_text(section.get("sectionId"))
            if not section_id:
                return []
            channels = self._request_json(
                client,
                cookie,
                "POST",
                f"/pave/channels/{section_id}",
                payload={"staffCodes": [staff_code]},
            )
            if not isinstance(channels, list):
                return []
            channel = next(
                (
                    item
                    for item in channels
                    if _as_text(item.get("code")).upper() == staff_code.upper()
                ),
                None,
            )
            tickets = channel.get("tickets") if isinstance(channel, dict) else None
            return normalise_board_channel_tasks(
                board_name,
                staff_code,
                tickets if isinstance(tickets, list) else [],
            )

    def list_global_playing_tasks(self, *, staff_code: str) -> list[StaffTaskCandidate]:
        with httpx.Client(base_url=self.base_url, timeout=30) as client:
            cookie = self._begin_session(client)
            rows = self._odata(
                client,
                cookie,
                "BMWorkflowTasks",
                filter_=(
                    f"P9_GS_NKAssignedStaffMember eq '{_odata_string(staff_code)}' "
                    "and P9_Status eq 'WRK' and P9_IsPublished eq true and P9_IsValid eq true"
                ),
                select=[
                    "P9_PK",
                    "P9_FH_ProcessHeader",
                    "P9_FH_JobWorkflow",
                    "P9_ParentTableCode",
                    "P9_ParentID",
                    "P9_Sequence",
                    "P9_Type",
                    "P9_Description",
                    "P9_G4_RequiredCapability",
                    "P9_Status",
                    "P9_Notes",
                ],
                top=1000,
            )
            return normalise_global_playing_tasks(rows)


class EdiCli:
    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or shutil.which("edi")
        if not self.executable:
            raise EdiCliError("edi executable not found on PATH")

    def _run(self, args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        command = [self.executable, *args]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise EdiCliError(f"edi command timed out: {' '.join(command)}") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise EdiCliError(detail or f"edi command failed: {' '.join(command)}")
        return result

    def _run_json_array(self, args: list[str], *, timeout: int = 30) -> list[dict[str, Any]]:
        result = self._run(args, timeout=timeout)
        return _json_array(result.stdout, command=[self.executable or "edi", *args])

    def version(self) -> str | None:
        result = self._run(["--version"], timeout=10)
        return result.stdout.strip() or None

    def get_own_staff_profile(self) -> StaffProfile:
        rows = self._run_json_array(
            ["--format", "json", "--fields", "code,displayName,name,email", "staff", "get"],
            timeout=30,
        )
        if not rows:
            raise EdiCliError("edi staff get returned no profile")
        row = rows[0]
        code = _as_text(row.get("code")).upper()
        if not code:
            raise EdiCliError("edi staff get did not return a staff code")
        return StaffProfile(code=code, display_name=_as_text(row.get("displayName")) or None, raw=row)

    def list_staff_tasks(
        self,
        staff_code: str,
        *,
        include_capability_pool: bool = True,
    ) -> list[StaffTaskCandidate]:
        fields = (
            "sequence,status,readyToStart,releasedAt,startableAt,jobNumber,jobTitle,"
            "boardName,boardZone,type,description,capability,hasNotes"
        )
        args = [
            "--format",
            "json",
            "--fields",
            fields,
            "staff",
            "tasks",
            staff_code,
        ]
        if include_capability_pool:
            args.append("--include-capability-pool")
        return normalise_staff_tasks(self._run_json_array(args, timeout=60))

    def list_board_channel_tasks(self, *, board_name: str, staff_code: str) -> list[StaffTaskCandidate]:
        return GlowBoardClient().list_board_channel_tasks(
            board_name=board_name,
            staff_code=staff_code,
        )

    def list_global_playing_tasks(self, staff_code: str) -> list[StaffTaskCandidate]:
        return GlowBoardClient().list_global_playing_tasks(staff_code=staff_code)

    def list_workflow_ids(self, job_number: str) -> list[str]:
        rows = self._run_json_array(
            ["--format", "json", "--fields", "workflowId", "workflow", "list", job_number],
            timeout=45,
        )
        return [_as_text(row.get("workflowId")) for row in rows if _as_text(row.get("workflowId"))]

    def list_active_tasks(self, workflow_id: str) -> list[dict[str, Any]]:
        fields = "id,sequence,type,description,staff,capability,status,startable,hasNotes"
        return self._run_json_array(
            [
                "--format",
                "json",
                "--fields",
                fields,
                "task",
                "list",
                workflow_id,
                "--status",
                "OPN",
                "ASN",
                "WRK",
                "SUS",
            ],
            timeout=45,
        )

    def resolve_task(self, candidate: StaffTaskCandidate) -> ResolvedTask | None:
        direct_task_id = _as_text(candidate.raw.get("taskId"))
        if direct_task_id:
            return ResolvedTask(
                task_id=direct_task_id,
                workflow_id=_as_text(candidate.raw.get("workflowId")),
                raw=candidate.raw,
            )
        matches: list[ResolvedTask] = []
        for workflow_id in self.list_workflow_ids(candidate.job_number):
            for task in self.list_active_tasks(workflow_id):
                if task_matches_candidate(task, candidate):
                    task_id = _as_text(task.get("id"))
                    if task_id:
                        matches.append(ResolvedTask(task_id=task_id, workflow_id=workflow_id, raw=task))
        if len(matches) == 1:
            return matches[0]
        return None

    def start_task(self, task_id: str) -> str:
        result = self._run(["task", "start", task_id], timeout=60)
        return (result.stdout or result.stderr).strip()

    def suspend_task(self, task_id: str) -> str:
        result = self._run(["task", "suspend", task_id], timeout=60)
        return (result.stdout or result.stderr).strip()

    def complete_task(self, task_id: str, *, duration_minutes: int | None = None) -> str:
        args = ["task", "complete", task_id]
        if duration_minutes is not None:
            args.extend(["--duration", str(duration_minutes)])
        result = self._run(args, timeout=60)
        return (result.stdout or result.stderr).strip()

    def assign_task(self, task_id: str, staff_or_capability_code: str) -> str:
        result = self._run(["task", "assign", task_id, staff_or_capability_code], timeout=60)
        return (result.stdout or result.stderr).strip()

    def append_task_notes(self, task_id: str, content: str) -> str:
        result = self._run(["task", "notes", "append", task_id, "--content", content], timeout=60)
        return (result.stdout or result.stderr).strip()

    def upload_file(
        self,
        job_number: str,
        file_path: str,
        *,
        doc_type: str = "INT",
        description: str | None = None,
    ) -> str:
        args = ["file", "upload", job_number, file_path, "--type", doc_type]
        if description:
            args.extend(["--description", description])
        result = self._run(args, timeout=120)
        return (result.stdout or result.stderr).strip()
