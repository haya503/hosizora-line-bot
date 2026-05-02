import pytest
from unittest.mock import MagicMock, patch
import requests
from sky_forecast import fetch_sky_conditions, SkyConditions

MOCK_RESPONSE = {
    "hourly": {
        "time": [f"2026-05-01T{h:02d}:00" for h in range(24)],
        "cloud_cover": [10] * 24,
        "visibility": [20000] * 24,
        "relative_humidity_2m": [50] * 24,
        "wind_speed_10m": [3.0] * 24,
    }
}


def make_mock_resp(data=None):
    m = MagicMock()
    m.json.return_value = data or MOCK_RESPONSE
    m.raise_for_status.return_value = None
    return m


def test_fetch_returns_sky_conditions():
    with patch("sky_forecast.requests.get", return_value=make_mock_resp()):
        result = fetch_sky_conditions(35.0, 135.0)
    assert isinstance(result, SkyConditions)
    assert result.cloud_cover == 10
    assert result.visibility == 20000
    assert result.humidity == 50
    assert result.wind_speed == 3.0


def test_fetch_averages_evening_hours_only():
    # 昼間 0、夜間18-23は60にして夜間平均だけ取れることを確認
    data = {
        "hourly": {
            "time": MOCK_RESPONSE["hourly"]["time"],
            "cloud_cover": [0] * 18 + [60] * 6,
            "visibility": [20000] * 24,
            "relative_humidity_2m": [50] * 24,
            "wind_speed_10m": [3.0] * 24,
        }
    }
    with patch("sky_forecast.requests.get", return_value=make_mock_resp(data)):
        result = fetch_sky_conditions(35.0, 135.0)
    assert result.cloud_cover == 60


def test_fetch_retries_once_on_failure():
    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise requests.RequestException("timeout")
        return make_mock_resp()

    with patch("sky_forecast.requests.get", side_effect=side_effect):
        result = fetch_sky_conditions(35.0, 135.0)

    assert call_count == 2
    assert result.cloud_cover == 10


def test_fetch_raises_after_two_failures():
    with patch("sky_forecast.requests.get", side_effect=requests.RequestException("error")):
        with pytest.raises(requests.RequestException):
            fetch_sky_conditions(35.0, 135.0)
