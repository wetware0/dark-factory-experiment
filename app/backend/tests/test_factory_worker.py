from backend.factory import worker


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
