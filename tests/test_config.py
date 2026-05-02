import pytest
from config import _parse_targets, load


def test_parse_targets_single_user():
    assert _parse_targets("userId:Uabc123") == ["Uabc123"]


def test_parse_targets_multiple():
    assert _parse_targets("userId:Uabc123,groupId:Cdef456") == ["Uabc123", "Cdef456"]


def test_parse_targets_strips_whitespace():
    assert _parse_targets("userId:Uabc123, groupId:Cdef456") == ["Uabc123", "Cdef456"]


def test_parse_targets_invalid_entry_raises():
    with pytest.raises(ValueError, match="Invalid"):
        _parse_targets("Uabc123")  # missing type: prefix


def test_load_raises_on_empty_targets(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("LINE_NOTIFY_TARGETS", "")
    monkeypatch.setenv("LOCATION_LAT", "35.0")
    monkeypatch.setenv("LOCATION_LON", "135.0")
    with pytest.raises(ValueError, match="at least one"):
        load()


def test_load_returns_notify_targets(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("LINE_NOTIFY_TARGETS", "userId:Uabc123")
    monkeypatch.setenv("LOCATION_LAT", "35.0")
    monkeypatch.setenv("LOCATION_LON", "135.0")
    cfg = load()
    assert cfg.LINE_NOTIFY_TARGETS == ["Uabc123"]
    assert cfg.LINE_CHANNEL_ACCESS_TOKEN == "tok"
    assert cfg.LOCATION_LAT == 35.0
    assert cfg.LOCATION_LON == 135.0
