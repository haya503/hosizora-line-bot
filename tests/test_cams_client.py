import requests
from unittest.mock import MagicMock, patch
from cams_client import fetch_aod, fetch_pm25


def _make_mock(times, values, variable="aerosol_optical_depth"):
    m = MagicMock()
    m.json.return_value = {
        "hourly": {"time": times, variable: values}
    }
    m.raise_for_status.return_value = None
    return m


def test_fetch_aod_returns_evening_average():
    times = [f"2026-05-09T{h:02d}:00" for h in range(24)]
    values = [0.0] * 21 + [0.3, 0.5, 0.4] + [0.0]
    with patch("cams_client.requests.get", return_value=_make_mock(times, values)):
        result = fetch_aod(32.8022, 130.7081)
    assert result == round((0.3 + 0.5 + 0.4) / 3, 3)


def test_fetch_aod_skips_none_values():
    times = [f"2026-05-09T{h:02d}:00" for h in range(24)]
    values = [0.0] * 21 + [0.3, None, 0.5] + [0.0]
    with patch("cams_client.requests.get", return_value=_make_mock(times, values)):
        result = fetch_aod(32.8022, 130.7081)
    assert result == round((0.3 + 0.5) / 2, 3)


def test_fetch_aod_returns_none_when_all_none():
    times = [f"2026-05-09T{h:02d}:00" for h in range(24)]
    values = [0.0] * 21 + [None, None, None] + [0.0]
    with patch("cams_client.requests.get", return_value=_make_mock(times, values)):
        result = fetch_aod(32.8022, 130.7081)
    assert result is None


def test_fetch_aod_returns_none_on_exception():
    with patch("cams_client.requests.get", side_effect=requests.exceptions.RequestException("timeout")):
        result = fetch_aod(32.8022, 130.7081)
    assert result is None


def test_fetch_pm25_returns_evening_average():
    times = [f"2026-05-09T{h:02d}:00" for h in range(24)]
    values = [5.0] * 21 + [12.3, 15.1, 18.2] + [5.0]
    with patch("cams_client.requests.get", return_value=_make_mock(times, values, "pm2_5")) as mock_get:
        result = fetch_pm25(32.8022, 130.7081)
    assert result == round((12.3 + 15.1 + 18.2) / 3, 1)
    mock_get.assert_called_once_with(
        "https://air-quality-api.open-meteo.com/v1/air-quality",
        params={
            "latitude": 32.8022,
            "longitude": 130.7081,
            "hourly": "pm2_5",
            "timezone": "Asia/Tokyo",
            "forecast_days": 1,
        },
        timeout=10,
    )


def test_fetch_pm25_returns_none_when_variable_missing():
    times = [f"2026-05-09T{h:02d}:00" for h in range(24)]
    values = [0.3] * 24
    with patch("cams_client.requests.get", return_value=_make_mock(times, values)):
        result = fetch_pm25(32.8022, 130.7081)
    assert result is None


def test_fetch_pm25_returns_none_on_exception():
    with patch("cams_client.requests.get", side_effect=requests.exceptions.RequestException("timeout")):
        result = fetch_pm25(32.8022, 130.7081)
    assert result is None
