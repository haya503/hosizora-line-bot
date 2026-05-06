from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from sky_forecast import SkyConditions, HourlySkyReading
from astro_events import PlanetInfo
from astro_client import HourlyAstroData
from notify import calculate_hourly_score, format_stars, format_message, main

_SAMPLE_HOURLY = [
    HourlySkyReading(21, 10, 20000),
    HourlySkyReading(22, 10, 20000),
    HourlySkyReading(23, 10, 20000),
    HourlySkyReading(24, 10, 20000),
]
SAMPLE_CONDITIONS = SkyConditions(humidity=50, wind_speed=3.0, hourly=_SAMPLE_HOURLY)
SAMPLE_ASTRO = {h: HourlyAstroData(1, 1) for h in [21, 22, 23, 24]}
SAMPLE_PLANETS = [PlanetInfo("木星", "22:30", 58.0)]
FAKE_CFG = SimpleNamespace(
    LINE_CHANNEL_ACCESS_TOKEN="tok",
    LINE_NOTIFY_TARGETS=["uid"],
    LOCATION_LAT=35.0,
    LOCATION_LON=135.0,
    HOSHIMIRU_API_TOKEN="test_token",
    JMA_AREA_CODE="130000",
    NASA_APOD_API_KEY="DEMO_KEY",
    DEEPL_API_KEY="",
)


# --- calculate_hourly_score ---

def test_calculate_hourly_score_perfect():
    assert calculate_hourly_score(10, 20000, 1, 1) == 5

def test_calculate_hourly_score_partly_cloudy():
    assert calculate_hourly_score(60, 20000, 1, 1) == 4

def test_calculate_hourly_score_very_cloudy():
    assert calculate_hourly_score(85, 20000, 1, 1) == 3

def test_calculate_hourly_score_low_visibility():
    assert calculate_hourly_score(10, 5000, 1, 1) == 4

def test_calculate_hourly_score_bad_seeing():
    assert calculate_hourly_score(10, 20000, 5, 1) == 4

def test_calculate_hourly_score_bad_transparency():
    assert calculate_hourly_score(10, 20000, 1, 6) == 4

def test_calculate_hourly_score_all_bad():
    assert calculate_hourly_score(85, 5000, 5, 6) == 1

def test_calculate_hourly_score_minimum_is_1():
    assert calculate_hourly_score(100, 0, 8, 8) >= 1

def test_calculate_hourly_score_cloud_penalty_is_exclusive():
    # 雲量>80%は-2だけ（-2と-1が重複しない）
    assert calculate_hourly_score(85, 20000, 1, 1) == 3  # 5-2=3, not 5-3=2

def test_calculate_hourly_score_weather_penalty_default():
    # weather_penalty=0（デフォルト）で既存の動作が変わらない
    assert calculate_hourly_score(10, 20000, 1, 1) == 5
    assert calculate_hourly_score(60, 20000, 1, 1) == 4

def test_calculate_hourly_score_weather_penalty_minus_1():
    # weather_penalty=-1 でスコアが1減る
    assert calculate_hourly_score(10, 20000, 1, 1, weather_penalty=-1) == 4

def test_calculate_hourly_score_weather_penalty_minus_2():
    # weather_penalty=-2 でスコアが2減る
    assert calculate_hourly_score(10, 20000, 1, 1, weather_penalty=-2) == 3

def test_calculate_hourly_score_weather_penalty_minimum_score():
    # ペナルティを加えてもスコアが1未満にならない
    assert calculate_hourly_score(85, 5000, 5, 6, weather_penalty=-5) == 1


# --- format_stars ---

def test_format_stars_full():
    assert format_stars(5) == "★★★★★"

def test_format_stars_partial():
    assert format_stars(3) == "★★★☆☆"

def test_format_stars_one():
    assert format_stars(1) == "★☆☆☆☆"


# --- format_message ---

def test_format_message_contains_header():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, "21:00", SAMPLE_PLANETS, [], [])
    assert "今夜の星空予報" in msg

def test_format_message_shows_hourly_display():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [])
    assert "21時" in msg
    assert "22時" in msg
    assert "23時" in msg
    assert "24時" in msg

def test_format_message_shows_stars_per_hour():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [])
    assert "★★★★★" in msg  # 全条件良好なら5つ星

def test_format_message_shows_constellations():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], ["さそり座", "こと座"])
    assert "今夜見える星座" in msg
    assert "さそり座" in msg

def test_format_message_no_constellations_skips_section():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [])
    assert "今夜見える星座" not in msg

def test_format_message_shows_planet_info():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, "21:00", SAMPLE_PLANETS, [], [])
    assert "木星が南中 22:30" in msg

def test_format_message_no_events_shows_placeholder():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [])
    assert "特になし" in msg

def test_format_message_meteor_shower_peak():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [("ペルセウス座流星群", 0)], [])
    assert "本日がピーク" in msg

def test_format_message_meteor_shower_upcoming():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [("ペルセウス座流星群", 3)], [])
    assert "あと3日" in msg

def test_format_message_shows_overall_score():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [])
    assert "総合評価" in msg

def test_format_message_empty_astro_data_uses_defaults():
    # astro_data が空（7timer失敗時）でもクラッシュしない
    msg = format_message(SAMPLE_CONDITIONS, {}, 5.0, None, [], [], [])
    assert "今夜の星空予報" in msg

def test_format_message_twilight_time_none_no_section():
    # twilight_time=None の場合、「天文薄明」行がメッセージに含まれない
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [], twilight_time=None)
    assert "天文薄明" not in msg

def test_format_message_twilight_time_shown():
    # twilight_time="20:15" の場合、メッセージに含まれる
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [], twilight_time="20:15")
    assert "天文薄明: 20:15" in msg

def test_format_message_weather_penalties_lower_score():
    # weather_penalties={21: -1} の場合、21時のスコアが補正なしより下がる
    msg_no_penalty = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [])
    msg_with_penalty = format_message(
        SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [],
        weather_penalties={21: -1}
    )
    # 補正なし: 21時は★★★★★、補正あり: 21時は★★★★☆ になるはず
    assert "★★★★★" in msg_no_penalty
    # 補正ありでは少なくとも総合スコアが下がるか、21時の行が変化している
    lines_no = {l for l in msg_no_penalty.splitlines() if "21時" in l}
    lines_with = {l for l in msg_with_penalty.splitlines() if "21時" in l}
    assert lines_no != lines_with


# --- main() ---

@patch("notify.send_image_message")
@patch("notify.translate_apod_explanation")
@patch("notify.fetch_apod")
@patch("notify.fetch_night_weather_penalties")
@patch("notify.fetch_astronomical_twilight")
@patch("notify.send_messages")
@patch("notify.fetch_constellations")
@patch("notify.fetch_7timer_astro")
@patch("notify.get_astro_data")
@patch("notify.fetch_sky_conditions")
@patch("notify.config")
def test_main_happy_path(mock_config, mock_fetch, mock_astro, mock_7timer, mock_const, mock_send,
                         mock_twilight, mock_penalties, mock_apod, mock_summarize, mock_send_image):
    mock_config.load.return_value = FAKE_CFG
    mock_fetch.return_value = SAMPLE_CONDITIONS
    mock_astro.return_value = (5.0, "21:00", SAMPLE_PLANETS, [])
    mock_7timer.return_value = SAMPLE_ASTRO
    mock_const.return_value = []
    mock_twilight.return_value = None
    mock_penalties.return_value = None
    mock_apod.return_value = None

    main()

    mock_send.assert_called_once()
    text = mock_send.call_args[0][2]
    assert "今夜の星空予報" in text


@patch("notify.send_messages")
@patch("notify.fetch_sky_conditions")
@patch("notify.config")
def test_main_weather_error_sends_error_notification(mock_config, mock_fetch, mock_send):
    mock_config.load.return_value = FAKE_CFG
    mock_fetch.side_effect = Exception("connection timeout")

    main()

    mock_send.assert_called_once()
    text = mock_send.call_args[0][2]
    assert "気象データ取得失敗" in text


@patch("notify.send_image_message")
@patch("notify.translate_apod_explanation")
@patch("notify.fetch_apod")
@patch("notify.fetch_night_weather_penalties")
@patch("notify.fetch_astronomical_twilight")
@patch("notify.send_messages")
@patch("notify.fetch_constellations")
@patch("notify.fetch_7timer_astro")
@patch("notify.get_astro_data")
@patch("notify.fetch_sky_conditions")
@patch("notify.config")
def test_main_7timer_failure_still_sends(mock_config, mock_fetch, mock_astro, mock_7timer, mock_const, mock_send,
                                         mock_twilight, mock_penalties, mock_apod, mock_summarize, mock_send_image):
    mock_config.load.return_value = FAKE_CFG
    mock_fetch.return_value = SAMPLE_CONDITIONS
    mock_astro.return_value = (5.0, None, [], [])
    mock_7timer.side_effect = Exception("7timer down")
    mock_const.return_value = []
    mock_twilight.return_value = None
    mock_penalties.return_value = None
    mock_apod.return_value = None

    main()

    mock_send.assert_called_once()
    assert "今夜の星空予報" in mock_send.call_args[0][2]


@patch("notify.send_image_message")
@patch("notify.translate_apod_explanation")
@patch("notify.fetch_apod")
@patch("notify.fetch_night_weather_penalties")
@patch("notify.fetch_astronomical_twilight")
@patch("notify.send_messages")
@patch("notify.fetch_constellations")
@patch("notify.fetch_7timer_astro")
@patch("notify.get_astro_data")
@patch("notify.fetch_sky_conditions")
@patch("notify.config")
def test_main_constellation_failure_still_sends(mock_config, mock_fetch, mock_astro, mock_7timer, mock_const, mock_send,
                                                 mock_twilight, mock_penalties, mock_apod, mock_summarize, mock_send_image):
    mock_config.load.return_value = FAKE_CFG
    mock_fetch.return_value = SAMPLE_CONDITIONS
    mock_astro.return_value = (5.0, None, [], [])
    mock_7timer.return_value = SAMPLE_ASTRO
    mock_const.side_effect = Exception("constellation API down")
    mock_twilight.return_value = None
    mock_penalties.return_value = None
    mock_apod.return_value = None

    main()

    mock_send.assert_called_once()
    assert "今夜の星空予報" in mock_send.call_args[0][2]
