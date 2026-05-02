from unittest.mock import MagicMock, patch
import pytest
from astro_client import (
    fetch_7timer_astro,
    fetch_constellations,
    HourlyAstroData,
)

# init=2026050209 → UTC 09:00 = JST 18:00 (通知時刻)
# timepoint 3 = UTC 12:00 = JST 21:00
# timepoint 6 = UTC 15:00 = JST 24:00
MOCK_7TIMER = {
    "init": "2026050209",
    "dataseries": [
        {"timepoint": 3, "seeing": 2, "transparency": 3,
         "cloudcover": 1, "lifted_index": 10, "rh2m": 5,
         "wind10m": {"direction": "N", "speed": 1}, "temp2m": 15, "prec_type": "none"},
        {"timepoint": 6, "seeing": 4, "transparency": 5,
         "cloudcover": 3, "lifted_index": 6, "rh2m": 8,
         "wind10m": {"direction": "S", "speed": 2}, "temp2m": 14, "prec_type": "none"},
        {"timepoint": 9, "seeing": 5, "transparency": 6,
         "cloudcover": 5, "lifted_index": 2, "rh2m": 10,
         "wind10m": {"direction": "W", "speed": 3}, "temp2m": 13, "prec_type": "none"},
    ],
}

MOCK_CONSTELLATION = {
    "results": [
        {"name": "さそり座"},
        {"name": "こと座"},
        {"name": "はくちょう座"},
        {"name": "わし座"},
        {"name": "いて座"},
        {"name": "へびつかい座"},  # 6件 → 5件に切り捨て
    ]
}


def _make_7timer_mock():
    m = MagicMock()
    m.json.return_value = MOCK_7TIMER
    m.raise_for_status.return_value = None
    return m


def _make_const_mock(data=None):
    m = MagicMock()
    m.json.return_value = data or MOCK_CONSTELLATION
    m.raise_for_status.return_value = None
    return m


# --- fetch_7timer_astro ---

def test_fetch_7timer_returns_all_4_hours():
    with patch("astro_client.requests.get", return_value=_make_7timer_mock()):
        result = fetch_7timer_astro(35.0, 135.0)
    assert set(result.keys()) == {21, 22, 23, 24}


def test_fetch_7timer_returns_hourly_astro_data():
    with patch("astro_client.requests.get", return_value=_make_7timer_mock()):
        result = fetch_7timer_astro(35.0, 135.0)
    assert isinstance(result[21], HourlyAstroData)


def test_fetch_7timer_jst21_and_22_map_to_tp3():
    # JST 21/22 → UTC 12/13 → nearest to timepoint 3
    with patch("astro_client.requests.get", return_value=_make_7timer_mock()):
        result = fetch_7timer_astro(35.0, 135.0)
    assert result[21].seeing == 2   # from tp3
    assert result[22].seeing == 2   # same tp3 (nearest)


def test_fetch_7timer_jst23_and_24_map_to_tp6():
    # JST 23/24 → UTC 14/15 → nearest to timepoint 6
    with patch("astro_client.requests.get", return_value=_make_7timer_mock()):
        result = fetch_7timer_astro(35.0, 135.0)
    assert result[23].seeing == 4   # from tp6
    assert result[24].seeing == 4   # same tp6 (nearest)


# --- fetch_constellations ---

def test_fetch_constellations_returns_names():
    with patch("astro_client.requests.get", return_value=_make_const_mock()):
        result = fetch_constellations(35.0, 135.0, "2026-05-02", "test_token")
    assert "さそり座" in result


def test_fetch_constellations_limits_to_5():
    with patch("astro_client.requests.get", return_value=_make_const_mock()):
        result = fetch_constellations(35.0, 135.0, "2026-05-02", "test_token")
    assert len(result) == 5


def test_fetch_constellations_empty_result():
    with patch("astro_client.requests.get", return_value=_make_const_mock({"results": []})):
        result = fetch_constellations(35.0, 135.0, "2026-05-02", "test_token")
    assert result == []
