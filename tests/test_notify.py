from types import SimpleNamespace
from unittest.mock import patch
from sky_forecast import SkyConditions
from astro_events import PlanetInfo
from notify import calculate_score, format_stars, format_message, main

SAMPLE_CONDITIONS = SkyConditions(cloud_cover=10, visibility=20000, humidity=50, wind_speed=3.0)
SAMPLE_PLANETS = [PlanetInfo("木星", "22:30", 58.0)]
FAKE_CFG = SimpleNamespace(
    LINE_CHANNEL_ACCESS_TOKEN="tok",
    LINE_USER_ID="uid",
    LOCATION_LAT=35.0,
    LOCATION_LON=135.0,
)


# --- calculate_score ---

def test_calculate_score_clear_no_moon():
    assert calculate_score(10, 5.0, 20000) == 5

def test_calculate_score_partly_cloudy():
    assert calculate_score(60, 5.0, 20000) == 4

def test_calculate_score_very_cloudy():
    assert calculate_score(85, 5.0, 20000) == 3

def test_calculate_score_full_moon():
    assert calculate_score(10, 15.0, 20000) == 4

def test_calculate_score_low_visibility():
    assert calculate_score(10, 5.0, 5000) == 4

def test_calculate_score_worst_case():
    assert calculate_score(90, 15.0, 5000) == 1

def test_calculate_score_minimum_is_1():
    assert calculate_score(100, 15.0, 0) >= 1

def test_calculate_score_partly_cloudy_low_visibility():
    # 雲量と視程は独立した減点（スペック準拠）
    assert calculate_score(60, 5.0, 5000) == 3


# --- format_stars ---

def test_format_stars_full():
    assert format_stars(5) == "★★★★★"

def test_format_stars_partial():
    assert format_stars(3) == "★★★☆☆"

def test_format_stars_one():
    assert format_stars(1) == "★☆☆☆☆"


# --- format_message ---

def test_format_message_contains_key_info():
    msg = format_message(SAMPLE_CONDITIONS, 5.0, "21:00", SAMPLE_PLANETS, [])
    assert "今夜の星空予報" in msg
    assert "雲量: 10%" in msg
    assert "月の出: 21:00" in msg
    assert "木星が南中 22:30" in msg
    assert "★" in msg

def test_format_message_no_events_shows_placeholder():
    msg = format_message(SAMPLE_CONDITIONS, 5.0, None, [], [])
    assert "特になし" in msg

def test_format_message_meteor_shower_peak():
    msg = format_message(SAMPLE_CONDITIONS, 5.0, None, [], [("ペルセウス座流星群", 0)])
    assert "本日がピーク" in msg

def test_format_message_meteor_shower_upcoming():
    msg = format_message(SAMPLE_CONDITIONS, 5.0, None, [], [("ペルセウス座流星群", 3)])
    assert "あと3日" in msg


# --- main() ---

@patch("notify.send_message")
@patch("notify.get_astro_data")
@patch("notify.fetch_sky_conditions")
@patch("notify.config")
def test_main_happy_path(mock_config, mock_fetch, mock_astro, mock_send):
    mock_config.load.return_value = FAKE_CFG
    mock_fetch.return_value = SAMPLE_CONDITIONS
    mock_astro.return_value = (5.0, "21:00", SAMPLE_PLANETS, [])

    main()

    mock_send.assert_called_once()
    text = mock_send.call_args[0][2]
    assert "今夜の星空予報" in text


@patch("notify.send_message")
@patch("notify.fetch_sky_conditions")
@patch("notify.config")
def test_main_weather_error_sends_error_notification(mock_config, mock_fetch, mock_send):
    mock_config.load.return_value = FAKE_CFG
    mock_fetch.side_effect = Exception("connection timeout")

    main()

    mock_send.assert_called_once()
    text = mock_send.call_args[0][2]
    assert "気象データ取得失敗" in text
