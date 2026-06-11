import subprocess

from backend.factory import worker


def test_stable_instance_id_is_reused_for_same_staff_board(monkeypatch):
    monkeypatch.setattr(worker.socket, "gethostname", lambda: "Ryzen2")

    first = worker._stable_instance_id(board_name="Peter's Board", staff_code="C50")
    second = worker._stable_instance_id(board_name="Peter's Board", staff_code="C50")

    assert first == second
    assert first == "factory-ryzen2-c50-peter-s-board"


def test_staff_mutation_check_blocks_guardian_oauth_for_c50(monkeypatch):
    monkeypatch.setattr(worker, "_detect_staff_code", lambda: ("PWS", "test profile"))
    monkeypatch.setattr(worker.config, "FACTORY_ALLOW_OAUTH_STAFF_MISMATCH", False)

    result = worker._staff_mutation_check("C50")

    assert not result.allowed
    assert result.detected_staff_code == "PWS"
    assert "live PAVE mutation is blocked" in result.detail
    assert result.metadata["configured_staff_code"] == "C50"


def test_staff_mutation_check_allows_matching_c50_oauth(monkeypatch):
    monkeypatch.setattr(worker, "_detect_staff_code", lambda: ("C50", "test profile"))
    monkeypatch.setattr(worker.config, "FACTORY_ALLOW_OAUTH_STAFF_MISMATCH", False)

    result = worker._staff_mutation_check("C50")

    assert result.allowed
    assert result.detected_staff_code == "C50"


def test_project_skill_catalog_reports_locked_skills():
    version, detail, metadata = worker._project_skill_catalog()

    assert version
    assert "locked project skills" in detail
    assert "pave" in metadata["skills"]


def test_dispatch_archon_workflow_uses_selected_workflow(monkeypatch, tmp_path):
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="run-id", stderr="")

    monkeypatch.setattr(worker.config, "FACTORY_ARCHON_EXECUTE", True)
    monkeypatch.setattr(worker.shutil, "which", lambda name: name if name == "archon" else None)
    monkeypatch.setattr(worker, "_run_command", fake_run)
    monkeypatch.setattr(
        worker,
        "_write_json_artifact",
        lambda run_id, name, payload: tmp_path / name,
    )

    result = worker._dispatch_archon_workflow(
        "run-1",
        {"run_id": "run-1"},
        workflow_name="pave-dark-factory-self-learning",
    )

    assert result.status == "running"
    assert calls[0][2] == "run"
    assert calls[0][3] == "pave-dark-factory-self-learning"
