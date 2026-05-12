from unittest.mock import MagicMock

from backend.schemas.ut_gate_run import UtGateRunCreate
from backend.services.ut_gate_run_service import _payload_matches_existing_row


def _make_row(**kwargs):
    row = MagicMock()
    defaults = {
        "job_name": "job",
        "build_number": 1,
        "build_url": None,
        "jenkins_base_url": None,
        "mr_url": None,
        "is_intercepted": False,
        "ut_exit_code": None,
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


def test_payload_matches_equal_minimal():
    body = UtGateRunCreate(
        idempotency_key="k1",
        job_name="job",
        build_number=1,
        is_intercepted=False,
    )
    assert _payload_matches_existing_row(body, _make_row()) is True


def test_payload_matches_with_urls_and_exit_code():
    body = UtGateRunCreate(
        idempotency_key="k1",
        job_name="job",
        build_number=2,
        is_intercepted=True,
        build_url="https://j.example/job/2/",
        jenkins_base_url="https://j.example",
        mr_url="https://c.example/mr/1",
        ut_exit_code=0,
    )
    row = _make_row(
        build_number=2,
        is_intercepted=True,
        build_url="https://j.example/job/2/",
        jenkins_base_url="https://j.example",
        mr_url="https://c.example/mr/1",
        ut_exit_code=0,
    )
    assert _payload_matches_existing_row(body, row) is True


def test_payload_mismatch_job_name():
    body = UtGateRunCreate(
        idempotency_key="k1",
        job_name="other",
        build_number=1,
        is_intercepted=False,
    )
    assert _payload_matches_existing_row(body, _make_row()) is False


def test_payload_mismatch_ut_exit_code_none_vs_int():
    body = UtGateRunCreate(
        idempotency_key="k1",
        job_name="job",
        build_number=1,
        is_intercepted=False,
        ut_exit_code=1,
    )
    assert _payload_matches_existing_row(body, _make_row(ut_exit_code=None)) is False


def test_unknown_json_keys_ignored_by_schema():
    data = {
        "idempotency_key": "k1",
        "job_name": "job",
        "build_number": 1,
        "is_intercepted": False,
        "error_message": "should be ignored",
    }
    m = UtGateRunCreate.model_validate(data)
    assert "error_message" not in m.model_dump()
