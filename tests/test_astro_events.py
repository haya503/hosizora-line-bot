from datetime import date, datetime, timezone
from astro_events import get_moon_age, get_upcoming_meteor_showers


def test_get_moon_age_at_reference_new_moon():
    known_new_moon = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    age = get_moon_age(known_new_moon)
    assert abs(age) < 0.01


def test_get_moon_age_is_in_valid_range():
    now = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    age = get_moon_age(now)
    assert 0 <= age < 29.531


def test_get_upcoming_meteor_showers_on_peak_day():
    result = get_upcoming_meteor_showers(date(2026, 8, 12))
    assert ("ペルセウス座流星群", 0) in result


def test_get_upcoming_meteor_showers_days_before_peak():
    result = get_upcoming_meteor_showers(date(2026, 8, 9))
    assert ("ペルセウス座流星群", 3) in result


def test_get_upcoming_meteor_showers_excludes_after_peak():
    result = get_upcoming_meteor_showers(date(2026, 8, 14))
    names = {name for name, _ in result}
    assert "ペルセウス座流星群" not in names


def test_get_upcoming_meteor_showers_excludes_outside_window():
    result = get_upcoming_meteor_showers(date(2026, 8, 1))
    names = {name for name, _ in result}
    assert "ペルセウス座流星群" not in names
