from datetime import date
from unittest.mock import MagicMock, patch
import pytest
import requests
from sky_forecast import fetch_sky_conditions, SkyConditions, HourlySkyReading

TODAY = date(2026, 5, 2)
TOMORROW = date(2026, 5, 3)

def _make_mock_response(cloud_values=None, vis_values=None):
    times = (
        [f"{TODAY}T{h:02d}:00" for h in range(24)]
        + [f"{TOMORROW}T{h:02d}:00" for h in range(24)]
    )
    cloud = cloud_values or [10] * 48
    vis = vis_values or [20000] * 48
    m = MagicMock()
    m.json.return_value = {
        "hourly": {
            "time": times,
            "cloud_cover": cloud,
            "visibility": vis,
            "relative_humidity_2m": [50] * 48,
            "wind_speed_10m": [3.0] * 48,
        }
    }
    m.raise_for_status.return_value = None
    return m


def test_fetch_returns_sky_conditions():
    with patch("sky_forecast.requests.get", return_value=_make_mock_response()):
        result = fetch_sky_conditions(35.0, 135.0, TODAY)
    assert isinstance(result, SkyConditions)
    assert result.humidity == 50
    assert result.wind_speed == 3.0


def test_fetch_returns_4_hourly_readings():
    with patch("sky_forecast.requests.get", return_value=_make_mock_response()):
        result = fetch_sky_conditions(35.0, 135.0, TODAY)
    assert len(result.hourly) == 4
    hours = [r.hour for r in result.hourly]
    assert hours == [21, 22, 23, 24]


def test_fetch_hourly_reading_has_correct_values():
    with patch("sky_forecast.requests.get", return_value=_make_mock_response()):
        result = fetch_sky_conditions(35.0, 135.0, TODAY)
    r21 = result.hourly[0]
    assert r21.hour == 21
    assert r21.cloud_cover == 10
    assert r21.visibility == 20000


def test_fetch_24h_reads_tomorrows_midnight():
    # 24時は翌日T00:00 = tomorrow T00:00
    cloud = [10] * 48
    cloud[24] = 90  # tomorrow T00:00 = index 24
    with patch("sky_forecast.requests.get", return_value=_make_mock_response(cloud_values=cloud)):
        result = fetch_sky_conditions(35.0, 135.0, TODAY)
    r24 = result.hourly[3]
    assert r24.hour == 24
    assert r24.cloud_cover == 90


def test_fetch_humidity_is_evening_average():
    # 昼間0%、夕方18-23時は60%にして夜間平均だけ取れることを確認
    humidity = [0] * 18 + [60] * 6 + [0] * 24
    m = MagicMock()
    times = [f"{TODAY}T{h:02d}:00" for h in range(24)] + [f"{TOMORROW}T{h:02d}:00" for h in range(24)]
    m.json.return_value = {
        "hourly": {
            "time": times,
            "cloud_cover": [10] * 48,
            "visibility": [20000] * 48,
            "relative_humidity_2m": humidity + [0] * 24,
            "wind_speed_10m": [3.0] * 48,
        }
    }
    m.raise_for_status.return_value = None
    with patch("sky_forecast.requests.get", return_value=m):
        result = fetch_sky_conditions(35.0, 135.0, TODAY)
    assert result.humidity == 60


def _failing_response():
    fail = MagicMock()
    fail.raise_for_status.side_effect = requests.RequestException("timeout")
    return fail


@patch("sky_forecast.time.sleep")
def test_fetch_retries_on_error(mock_sleep):
    ok = _make_mock_response()
    with patch("sky_forecast.requests.get", side_effect=[_failing_response(), ok]):
        result = fetch_sky_conditions(35.0, 135.0, TODAY)
    assert isinstance(result, SkyConditions)
    mock_sleep.assert_called_once_with(5)


@patch("sky_forecast.time.sleep")
def test_fetch_succeeds_on_third_attempt(mock_sleep):
    ok = _make_mock_response()
    with patch(
        "sky_forecast.requests.get",
        side_effect=[_failing_response(), _failing_response(), ok],
    ):
        result = fetch_sky_conditions(35.0, 135.0, TODAY)
    assert isinstance(result, SkyConditions)
    assert [c.args[0] for c in mock_sleep.call_args_list] == [5, 15]


@patch("sky_forecast.time.sleep")
def test_fetch_raises_after_all_attempts_fail(mock_sleep):
    with patch("sky_forecast.requests.get", return_value=_failing_response()) as mock_get:
        with pytest.raises(requests.RequestException):
            fetch_sky_conditions(35.0, 135.0, TODAY)
    assert mock_get.call_count == 3


@patch("sky_forecast.time.sleep")
def test_fetch_respects_attempts_and_timeout(mock_sleep):
    with patch("sky_forecast.requests.get", return_value=_failing_response()) as mock_get:
        with pytest.raises(requests.RequestException):
            fetch_sky_conditions(35.0, 135.0, TODAY, attempts=2, timeout=10)
    assert mock_get.call_count == 2
    assert all(c.kwargs["timeout"] == 10 for c in mock_get.call_args_list)


def test_fetch_uses_long_read_timeout_by_default():
    with patch("sky_forecast.requests.get", return_value=_make_mock_response()) as mock_get:
        fetch_sky_conditions(35.0, 135.0, TODAY)
    connect, read = mock_get.call_args.kwargs["timeout"]
    assert read >= 30
