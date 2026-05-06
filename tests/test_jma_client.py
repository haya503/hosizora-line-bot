from unittest.mock import patch, MagicMock
import jma_client


def test_fetch_night_weather_penalties_returns_dict_with_correct_penalties():
    """正常系: 晴れ→0、曇り→-1、雨→-2が返る"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = [
        {
            "timeSeries": [
                {
                    "timeDefines": [
                        "2026-05-06T09:00:00+09:00",  # 昼間 → 除外
                        "2026-05-06T18:00:00+09:00",  # 18時 → 含む（100: 晴れ→0）
                        "2026-05-07T00:00:00+09:00",  # 0時 → 含む（201: 曇り→-1）
                        "2026-05-07T02:00:00+09:00",  # 2時 → 含む（300: 雨→-2）
                    ],
                    "areas": [
                        {
                            "weatherCodes": ["100", "100", "201", "300"]
                        }
                    ]
                }
            ]
        }
    ]

    with patch("jma_client.requests.get") as mock_get:
        mock_get.return_value = mock_resp
        result = jma_client.fetch_night_weather_penalties("130010")

    # 100: 晴れ→0, 201: 曇り→-1, 300: 雨→-2
    assert result is not None
    assert result[18] == 0
    assert result[0] == -1
    assert result[2] == -2
    assert len(result) == 3


def test_fetch_night_weather_penalties_filters_daytime():
    """夜間フィルタ: 昼間（9時）のコードは辞書に含まれない"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = [
        {
            "timeSeries": [
                {
                    "timeDefines": [
                        "2026-05-06T09:00:00+09:00",  # 昼間 → 除外
                        "2026-05-06T18:00:00+09:00",  # 18時 → 含む
                    ],
                    "areas": [
                        {
                            "weatherCodes": ["100", "201"]
                        }
                    ]
                }
            ]
        }
    ]

    with patch("jma_client.requests.get") as mock_get:
        mock_get.return_value = mock_resp
        result = jma_client.fetch_night_weather_penalties("130010")

    assert result is not None
    assert 18 in result
    assert len(result) == 1


def test_fetch_night_weather_penalties_returns_none_on_network_error():
    """ネットワークエラー時: None が返る"""
    with patch("jma_client.requests.get") as mock_get:
        mock_get.side_effect = Exception("Network error")
        result = jma_client.fetch_night_weather_penalties("130010")

    assert result is None
