from backend.factory.edi_cli import (
    find_playing_tasks,
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
