import pytest


def test_config_load_returns_all_fields(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "mytoken")
    monkeypatch.setenv("LINE_USER_ID", "myuserid")
    monkeypatch.setenv("LOCATION_LAT", "34.6937")
    monkeypatch.setenv("LOCATION_LON", "135.5023")

    import config
    cfg = config.load()

    assert cfg.LINE_CHANNEL_ACCESS_TOKEN == "mytoken"
    assert cfg.LINE_USER_ID == "myuserid"
    assert cfg.LOCATION_LAT == pytest.approx(34.6937)
    assert cfg.LOCATION_LON == pytest.approx(135.5023)


def test_config_load_raises_on_missing_env(monkeypatch):
    for key in ["LINE_CHANNEL_ACCESS_TOKEN", "LINE_USER_ID", "LOCATION_LAT", "LOCATION_LON"]:
        monkeypatch.delenv(key, raising=False)

    import config
    with pytest.raises(KeyError):
        config.load()
