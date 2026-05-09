# tests/test_message_parser.py
from datetime import date
import pytest
from message_parser import parse_mention_text, ParsedRequest, ParseError

TODAY = date(2026, 5, 10)


def test_parse_today_night():
    r = parse_mention_text("@Bot 今日 夜 東京", today=TODAY)
    assert r == ParsedRequest(target_date=TODAY, time_type="night", hour=None, location="東京")


def test_parse_tomorrow_hour():
    r = parse_mention_text("@Bot 明日 21時 阿蘇山", today=TODAY)
    assert r == ParsedRequest(target_date=date(2026, 5, 11), time_type="hour", hour=21, location="阿蘇山")


def test_parse_compound_tonight():
    r = parse_mention_text("@Bot 今夜 東京", today=TODAY)
    assert r.target_date == TODAY
    assert r.time_type == "night"
    assert r.location == "東京"


def test_parse_compound_today_night():
    r = parse_mention_text("@Bot 今日の夜 東京", today=TODAY)
    assert r.target_date == TODAY
    assert r.time_type == "night"


def test_parse_compound_tomorrow_night():
    r = parse_mention_text("@Bot 明日の夜 大阪", today=TODAY)
    assert r.target_date == date(2026, 5, 11)
    assert r.time_type == "night"
    assert r.location == "大阪"


def test_parse_compound_day_after_tomorrow_night():
    r = parse_mention_text("@Bot 明後日の夜 東京", today=TODAY)
    assert r.target_date == date(2026, 5, 12)
    assert r.time_type == "night"


def test_parse_month_day():
    r = parse_mention_text("@Bot 5月15日 夜 新宿区", today=TODAY)
    assert r.target_date == date(2026, 5, 15)
    assert r.time_type == "night"


def test_parse_slash_date():
    r = parse_mention_text("@Bot 5/20 夜 東京", today=TODAY)
    assert r.target_date == date(2026, 5, 20)


def test_parse_afternoon_hour():
    r = parse_mention_text("@Bot 明日 午後9時 東京", today=TODAY)
    assert r.hour == 21
    assert r.time_type == "hour"


def test_parse_morning_hour():
    r = parse_mention_text("@Bot 明日 午前2時 東京", today=TODAY)
    assert r.hour == 2
    assert r.time_type == "hour"


def test_parse_night_prefix_hour():
    r = parse_mention_text("@Bot 明日 夜9時 東京", today=TODAY)
    assert r.hour == 21


def test_parse_night_no_prefix_hour():
    r = parse_mention_text("@Bot 明日 夜の9時 東京", today=TODAY)
    assert r.hour == 21


def test_parse_direct_hour():
    r = parse_mention_text("@Bot 明日 22時 東京", today=TODAY)
    assert r.hour == 22


def test_parse_missing_date_raises():
    with pytest.raises(ParseError):
        parse_mention_text("@Bot 夜 東京", today=TODAY)


def test_parse_missing_time_raises():
    with pytest.raises(ParseError):
        parse_mention_text("@Bot 今日 東京", today=TODAY)


def test_parse_missing_location_raises():
    with pytest.raises(ParseError):
        parse_mention_text("@Bot 今日 夜", today=TODAY)


def test_parse_past_month_day_wraps_to_next_year():
    r = parse_mention_text("@Bot 1月1日 夜 東京", today=TODAY)
    assert r.target_date == date(2027, 1, 1)


def test_parse_error_message_contains_example():
    with pytest.raises(ParseError) as exc:
        parse_mention_text("@Bot 夜 東京", today=TODAY)
    assert "@Bot" in str(exc.value)
