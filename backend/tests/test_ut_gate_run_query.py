import pytest
from pydantic import ValidationError

from backend.schemas.ut_gate_run import UtGateRunQuery


def test_mr_url_mutual_exclusive():
    with pytest.raises(ValidationError) as ei:
        UtGateRunQuery(mr_url="https://a/mr/1", mr_url_contains="mr")
    assert "互斥" in str(ei.value)


def test_start_end_date_mix_with_iso_fails():
    with pytest.raises(ValidationError) as ei:
        UtGateRunQuery(start_time="2026-01-01", end_time="2026-01-02T00:00:00")
    assert "同为" in str(ei.value)


def test_start_after_end_fails():
    with pytest.raises(ValidationError) as ei:
        UtGateRunQuery(start_time="2026-01-03", end_time="2026-01-01")
    assert "不能晚于" in str(ei.value)


def test_sort_field_invalid():
    with pytest.raises(ValidationError) as ei:
        UtGateRunQuery(sort_field="job_name")
    assert "sort_field" in str(ei.value).lower() or "仅支持" in str(ei.value)


def test_iso8601_with_z_normalized():
    q = UtGateRunQuery(start_time="2026-05-07T12:00:00Z", end_time="2026-05-07T15:00:00Z")
    assert q.parsed_reported_at_start is not None
    assert q.parsed_reported_at_end is not None
    assert q.parsed_reported_at_start <= q.parsed_reported_at_end


def test_page_size_max():
    with pytest.raises(ValidationError):
        UtGateRunQuery(page_size=101)
