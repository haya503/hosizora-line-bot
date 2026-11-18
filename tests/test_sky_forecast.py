from datetime import date, datetime, timedelta, timezone
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


def _met_norway_response(cloud=20.0, fog=None, humidity=70.0, wind=2.5):
    """MET Norway の locationforecast 形式。時刻は UTC で、TODAY の JST 0 時から 48 時間分。"""
    start = datetime(TODAY.year, TODAY.month, TODAY.day, tzinfo=timezone.utc) - timedelta(hours=9)
    timeseries = []
    for h in range(48):
        details = {
            "cloud_area_fraction": cloud,
            "relative_humidity": humidity,
            "wind_speed": wind,
        }
        if fog is not None:
            details["fog_area_fraction"] = fog
        t = (start + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")
        timeseries.append({"time": t, "data": {"instant": {"details": details}}})
    m = MagicMock()
    m.json.return_value = {"properties": {"timeseries": timeseries}}
    m.raise_for_status.return_value = None
    return m


def _rate_limited_response():
    resp = MagicMock()
    resp.status_code = 429
    fail = MagicMock()
    fail.raise_for_status.side_effect = requests.HTTPError("429 Too Many Requests", response=resp)
    return fail


@patch("sky_forecast.time.sleep")
def test_fetch_raises_after_all_attempts_fail(mock_sleep):
    with patch("sky_forecast.requests.get", return_value=_failing_response()) as mock_get:
        with pytest.raises(requests.RequestException) as exc_info:
            fetch_sky_conditions(35.0, 135.0, TODAY)
    # Open-Meteo 3 回 + MET Norway 1 回
    assert mock_get.call_count == 4
    assert "Open-Meteo" in str(exc_info.value)
    assert "MET Norway" in str(exc_info.value)


@patch("sky_forecast.time.sleep")
def test_fetch_respects_attempts_and_timeout(mock_sleep):
    with patch("sky_forecast.requests.get", return_value=_failing_response()) as mock_get:
        with pytest.raises(requests.RequestException):
            fetch_sky_conditions(35.0, 135.0, TODAY, attempts=2, timeout=10)
    # Open-Meteo 2 回 + MET Norway 1 回
    assert mock_get.call_count == 3
    assert all(c.kwargs["timeout"] == 10 for c in mock_get.call_args_list)


@patch("sky_forecast.time.sleep")
def test_fetch_rate_limited_falls_back_to_met_norway_without_retry(mock_sleep):
    with patch(
        "sky_forecast.requests.get",
        side_effect=[_rate_limited_response(), _met_norway_response()],
    ) as mock_get:
        result = fetch_sky_conditions(35.0, 135.0, TODAY)
    assert mock_get.call_count == 2
    mock_sleep.assert_not_called()
    assert "api.met.no" in mock_get.call_args_list[1].args[0]
    assert result.humidity == 70
    assert result.wind_speed == 2.5
    assert [r.hour for r in result.hourly] == [21, 22, 23, 24]
    assert all(r.cloud_cover == 20 for r in result.hourly)
    assert all(r.visibility == 20000 for r in result.hourly)


@patch("sky_forecast.time.sleep")
def test_fetch_met_norway_sends_user_agent(mock_sleep):
    with patch(
        "sky_forecast.requests.get",
        side_effect=[_rate_limited_response(), _met_norway_response()],
    ) as mock_get:
        fetch_sky_conditions(32.80221, 130.70816, TODAY)
    met_call = mock_get.call_args_list[1]
    assert "python-requests" not in met_call.kwargs["headers"]["User-Agent"]
    assert met_call.kwargs["params"] == {"lat": 32.8022, "lon": 130.7082}


@patch("sky_forecast.time.sleep")
def test_fetch_met_norway_converts_utc_to_jst(mock_sleep):
    resp = _met_norway_response()
    timeseries = resp.json.return_value["properties"]["timeseries"]
    # JST 当日 21 時 = UTC 当日 12 時 → index 21、JST 翌日 0 時 = index 24
    timeseries[21]["data"]["instant"]["details"]["cloud_area_fraction"] = 55.4
    timeseries[24]["data"]["instant"]["details"]["cloud_area_fraction"] = 90.0
    with patch("sky_forecast.requests.get", side_effect=[_rate_limited_response(), resp]):
        result = fetch_sky_conditions(35.0, 135.0, TODAY)
    assert result.hourly[0].hour == 21 and result.hourly[0].cloud_cover == 55
    assert result.hourly[3].hour == 24 and result.hourly[3].cloud_cover == 90


@pytest.mark.parametrize("fog, visibility", [(None, 20000), (0.0, 20000), (20.0, 5000), (80.0, 1000)])
@patch("sky_forecast.time.sleep")
def test_fetch_met_norway_visibility_from_fog(mock_sleep, fog, visibility):
    with patch(
        "sky_forecast.requests.get",
        side_effect=[_rate_limited_response(), _met_norway_response(fog=fog)],
    ):
        result = fetch_sky_conditions(35.0, 135.0, TODAY)
    assert all(r.visibility == visibility for r in result.hourly)


@patch("sky_forecast.time.sleep")
def test_fetch_bad_open_meteo_data_falls_back_to_met_norway(mock_sleep):
    broken = MagicMock()
    broken.raise_for_status.return_value = None
    broken.json.return_value = {"error": True, "reason": "unexpected"}
    with patch("sky_forecast.requests.get", side_effect=[broken, _met_norway_response()]):
        result = fetch_sky_conditions(35.0, 135.0, TODAY)
    assert result.humidity == 70


def test_fetch_open_meteo_requests_wind_in_m_per_s():
    with patch("sky_forecast.requests.get", return_value=_make_mock_response()) as mock_get:
        fetch_sky_conditions(35.0, 135.0, TODAY)
    assert mock_get.call_args.kwargs["params"]["wind_speed_unit"] == "ms"


def test_fetch_uses_long_read_timeout_by_default():
    with patch("sky_forecast.requests.get", return_value=_make_mock_response()) as mock_get:
        fetch_sky_conditions(35.0, 135.0, TODAY)
    connect, read = mock_get.call_args.kwargs["timeout"]
    assert read >= 30
