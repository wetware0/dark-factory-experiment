"""edi CLI adapter for low-token PAVE scout operations."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any


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


def find_playing_tasks(tasks: list[StaffTaskCandidate]) -> list[StaffTaskCandidate]:
    return [task for task in tasks if task.status == "WRK"]


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
