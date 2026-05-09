import pytest
from unittest.mock import patch
import config
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
    monkeypatch.setenv("JMA_AREA_CODE", "130000")
    with pytest.raises(ValueError, match="at least one"):
        load()


def test_load_returns_notify_targets(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("LINE_NOTIFY_TARGETS", "userId:Uabc123")
    monkeypatch.setenv("JMA_AREA_CODE", "130000")
    cfg = load()
    assert cfg.LINE_NOTIFY_TARGETS == ["Uabc123"]
    assert cfg.LINE_CHANNEL_ACCESS_TOKEN == "tok"
    assert cfg.LOCATION_NAME == "熊本市中央区横手3丁目"
    assert cfg.LOCATION_LAT == 32.8022
    assert cfg.LOCATION_LON == 130.7081


def test_load_includes_nasa_apod_api_key(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("LINE_NOTIFY_TARGETS", "uid:abc")
    monkeypatch.setenv("LOCATION_LAT", "35.0")
    monkeypatch.setenv("LOCATION_LON", "135.0")
    monkeypatch.setenv("NASA_APOD_API_KEY", "mykey")
    monkeypatch.setenv("JMA_AREA_CODE", "130000")
    cfg = config.load()
    assert cfg.NASA_APOD_API_KEY == "mykey"


def test_load_includes_jma_area_code(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("LINE_NOTIFY_TARGETS", "uid:abc")
    monkeypatch.setenv("LOCATION_LAT", "35.0")
    monkeypatch.setenv("LOCATION_LON", "135.0")
    monkeypatch.setenv("NASA_APOD_API_KEY", "mykey")
    monkeypatch.setenv("JMA_AREA_CODE", "130000")
    cfg = config.load()
    assert cfg.JMA_AREA_CODE == "130000"


def test_load_apod_key_defaults_to_demo(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("LINE_NOTIFY_TARGETS", "uid:abc")
    monkeypatch.setenv("LOCATION_LAT", "35.0")
    monkeypatch.setenv("LOCATION_LON", "135.0")
    monkeypatch.delenv("NASA_APOD_API_KEY", raising=False)
    monkeypatch.setenv("JMA_AREA_CODE", "130000")
    with patch("config.load_dotenv"):
        cfg = config.load()
    assert cfg.NASA_APOD_API_KEY == "DEMO_KEY"
