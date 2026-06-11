import subprocess

from backend.factory.edi_cli import (
    EdiCli,
    find_playing_tasks,
    is_self_learning_task,
    normalise_board_channel_tasks,
    normalise_global_playing_tasks,
    normalise_staff_tasks,
    select_startable_candidate,
    task_matches_candidate,
)


def test_select_startable_candidate_filters_to_board_and_prioritises_zone():
    tasks = normalise_staff_tasks(
        [
            {
                "sequence": 4,
                "status": "ASN",
                "readyToStart": True,
                "jobNumber": "WI00000004",
                "jobTitle": "Later",
                "boardName": "Peter's Board",
                "boardZone": "Three",
                "type": "CDF",
                "description": "Later task",
            },
            {
                "sequence": 2,
                "status": "SUS",
                "readyToStart": True,
                "jobNumber": "WI00000002",
                "jobTitle": "Earlier",
                "boardName": "Peter's Board",
                "boardZone": "One",
                "type": "INV",
                "description": "Earlier task",
            },
            {
                "sequence": 1,
                "status": "ASN",
                "readyToStart": True,
                "jobNumber": "WI00000001",
                "jobTitle": "Wrong board",
                "boardName": "Other Board",
                "boardZone": "Zero",
                "type": "CDF",
                "description": "Wrong board task",
            },
        ]
    )

    candidate = select_startable_candidate(tasks, board_name="Peter's Board")

    assert candidate is not None
    assert candidate.job_number == "WI00000002"
    assert candidate.task_type == "INV"


def test_find_playing_tasks_detects_any_working_task_across_boards():
    tasks = normalise_staff_tasks(
        [
            {
                "status": "ASN",
                "readyToStart": True,
                "jobNumber": "WI00000001",
                "boardName": "Peter's Board",
                "type": "CDF",
                "description": "Ready task",
            },
            {
                "status": "WRK",
                "readyToStart": False,
                "jobNumber": "WI00000002",
                "boardName": "Other Board",
                "type": "INV",
                "description": "Already playing",
            },
        ]
    )

    playing = find_playing_tasks(tasks)

    assert len(playing) == 1
    assert playing[0].job_number == "WI00000002"


def test_self_learning_task_is_int_with_self_learning_description():
    learning_task = normalise_staff_tasks(
        [
            {
                "status": "ASN",
                "readyToStart": True,
                "jobNumber": "WI00000003",
                "boardName": "Peter's Board",
                "type": "INT",
                "description": "Self Learning - generated artifact assessment",
            }
        ]
    )[0]
    non_learning_int = normalise_staff_tasks(
        [
            {
                "status": "ASN",
                "readyToStart": True,
                "jobNumber": "WI00000004",
                "boardName": "Peter's Board",
                "type": "INT",
                "description": "Internal investigation",
            }
        ]
    )[0]
    wrong_type = normalise_staff_tasks(
        [
            {
                "status": "ASN",
                "readyToStart": True,
                "jobNumber": "WI00000005",
                "boardName": "Peter's Board",
                "type": "DES",
                "description": "Self Learning review",
            }
        ]
    )[0]

    assert is_self_learning_task(learning_task)
    assert not is_self_learning_task(non_learning_int)
    assert not is_self_learning_task(wrong_type)


def test_task_matches_candidate_uses_sequence_type_status_description_and_startable_state():
    candidate = normalise_staff_tasks(
        [
            {
                "sequence": 7,
                "status": "ASN",
                "readyToStart": True,
                "jobNumber": "WI00000007",
                "boardName": "Peter's Board",
                "type": "CDF",
                "description": "Implement change",
                "capability": "DEV",
            }
        ]
    )[0]

    assert task_matches_candidate(
        {
            "id": "task-id",
            "sequence": 7,
            "status": "ASN",
            "startable": True,
            "type": "CDF",
            "description": "Implement change",
            "capability": "DEV",
        },
        candidate,
    )
    assert not task_matches_candidate(
        {
            "id": "task-id",
            "sequence": 7,
            "status": "ASN",
            "startable": False,
            "type": "CDF",
            "description": "Implement change",
            "capability": "DEV",
        },
        candidate,
    )


def test_board_channel_tasks_normalise_direct_pave_ids():
    tasks = normalise_board_channel_tasks(
        "Peter's Board",
        "C50",
        [
            {
                "key": "workflow-1",
                "title": "WI01081111",
                "subtitle": "Review docs repo",
                "releaseDateTime": "2026-06-02T03:35:33.333",
                "startableSince": "2026-06-10T00:30:13.227",
                "zone": "One",
                "items": [
                    {
                        "key": "task-1",
                        "type": {"code": "DES", "description": "High Level Design"},
                        "title": "Review Skills in AI.Prompts Repo",
                        "startable": True,
                        "staffCode": "C50",
                        "taskStatus": "ASN",
                        "sequence": 13,
                        "hasNotes": False,
                    },
                    {
                        "key": "task-2",
                        "type": {"code": "DES"},
                        "title": "Guardian review",
                        "startable": True,
                        "staffCode": "PWS",
                        "taskStatus": "SUS",
                        "sequence": 13,
                    },
                ],
            }
        ],
    )

    assert len(tasks) == 1
    assert tasks[0].job_number == "WI01081111"
    assert tasks[0].task_type == "DES"
    assert tasks[0].description == "Review Skills in AI.Prompts Repo"
    assert tasks[0].board_name == "Peter's Board"
    assert tasks[0].raw["taskId"] == "task-1"
    assert tasks[0].raw["workflowId"] == "workflow-1"


def test_global_playing_tasks_normalise_for_staff_guard():
    tasks = normalise_global_playing_tasks(
        [
            {
                "P9_PK": "task-1",
                "P9_FH_ProcessHeader": "workflow-1",
                "P9_ParentTableCode": "WKI",
                "P9_ParentID": "parent-1",
                "P9_Sequence": 2,
                "P9_Type": "DES",
                "P9_Description": "Already playing",
                "P9_Status": "WRK",
            }
        ]
    )

    assert len(find_playing_tasks(tasks)) == 1
    assert tasks[0].raw["taskId"] == "task-1"
    assert tasks[0].raw["workflowId"] == "workflow-1"


def test_resolve_task_uses_direct_task_id_without_cli_lookup():
    candidate = normalise_board_channel_tasks(
        "Peter's Board",
        "C50",
        [
            {
                "key": "workflow-1",
                "title": "WI01081111",
                "items": [
                    {
                        "key": "task-1",
                        "type": {"code": "DES"},
                        "title": "Review Skills in AI.Prompts Repo",
                        "startable": True,
                        "staffCode": "C50",
                        "taskStatus": "ASN",
                    }
                ],
            }
        ],
    )[0]

    resolved = EdiCli("edi").resolve_task(candidate)

    assert resolved is not None
    assert resolved.task_id == "task-1"
    assert resolved.workflow_id == "workflow-1"


def test_append_task_notes_uses_cli_content_option(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="updated", stderr="")

    monkeypatch.setattr("backend.factory.edi_cli.subprocess.run", fake_run)

    cli = EdiCli("edi")
    output = cli.append_task_notes("task-123", "Needs guardian review")

    assert output == "updated"
    assert calls == [
        ["edi", "task", "notes", "append", "task-123", "--content", "Needs guardian review"]
    ]
