from datetime import date
from unittest.mock import patch, MagicMock
import jma_client

TODAY = date(2026, 10, 15)


def _mock_forecast(time_defines, weather_codes):
    """気象庁 府県天気予報 JSON の data[0]["timeSeries"][0]（日単位の天気）を模したレスポンス"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = [
        {
            "timeSeries": [
                {
                    "timeDefines": time_defines,
                    "areas": [
                        {"area": {"name": "熊本地方", "code": "430010"}, "weatherCodes": weather_codes},
                        {"area": {"name": "阿蘇地方", "code": "430020"}, "weatherCodes": ["300", "300", "300"]},
                    ],
                }
            ]
        }
    ]
    return mock_resp


def test_fetch_night_weather_penalties_uses_today_for_evening_and_tomorrow_for_midnight():
    """21〜23時は今日、24時は明日の天気を使い、明後日の天気は使わない"""
    resp = _mock_forecast(
        ["2026-10-15T17:00:00+09:00", "2026-10-16T00:00:00+09:00", "2026-10-17T00:00:00+09:00"],
        ["100", "201", "300"],  # 今日: 晴れ→0、明日: 曇り→-1、明後日: 雨→-2
    )
    with patch("jma_client.requests.get", return_value=resp) as mock_get:
        result = jma_client.fetch_night_weather_penalties("430000", today_jst=TODAY)

    assert result == {21: 0, 22: 0, 23: 0, 24: -1}
    mock_get.assert_called_once_with(
        "https://www.jma.go.jp/bosai/forecast/data/forecast/430000.json", timeout=10
    )


def test_fetch_night_weather_penalties_rain_and_snow():
    """雨（3xx）・雪（4xx）は -2"""
    resp = _mock_forecast(
        ["2026-10-15T11:00:00+09:00", "2026-10-16T00:00:00+09:00", "2026-10-17T00:00:00+09:00"],
        ["302", "400", "100"],
    )
    with patch("jma_client.requests.get", return_value=resp):
        result = jma_client.fetch_night_weather_penalties("430000", today_jst=TODAY)

    assert result == {21: -2, 22: -2, 23: -2, 24: -2}


def test_fetch_night_weather_penalties_skips_today_when_not_in_forecast():
    """予報に今日が含まれないときは 21〜23時の補正を付けない"""
    resp = _mock_forecast(
        ["2026-10-16T05:00:00+09:00", "2026-10-17T00:00:00+09:00", "2026-10-18T00:00:00+09:00"],
        ["100", "201", "300"],
    )
    with patch("jma_client.requests.get", return_value=resp):
        result = jma_client.fetch_night_weather_penalties("430000", today_jst=TODAY)

    assert result == {24: 0}


def test_fetch_night_weather_penalties_returns_none_on_network_error():
    """ネットワークエラー時: None が返る"""
    with patch("jma_client.requests.get") as mock_get:
        mock_get.side_effect = Exception("Network error")
        result = jma_client.fetch_night_weather_penalties("430000")

    assert result is None
