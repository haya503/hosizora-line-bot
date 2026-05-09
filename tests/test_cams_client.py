from unittest.mock import MagicMock, patch
from cams_client import fetch_aod


def _make_mock(times, values):
    m = MagicMock()
    m.json.return_value = {
        "hourly": {"time": times, "aerosol_optical_depth": values}
    }
    m.raise_for_status.return_value = None
    return m


def test_fetch_aod_returns_evening_average():
    times = [f"2026-05-09T{h:02d}:00" for h in range(24)]
    values = [0.0] * 21 + [0.3, 0.5, 0.4] + [0.0]
    with patch("cams_client.requests.get", return_value=_make_mock(times, values)):
        result = fetch_aod(32.8022, 130.7081)
    assert result == round((0.3 + 0.5 + 0.4) / 3, 3)


def test_fetch_aod_skips_none_values():
    times = [f"2026-05-09T{h:02d}:00" for h in range(24)]
    values = [0.0] * 21 + [0.3, None, 0.5] + [0.0]
    with patch("cams_client.requests.get", return_value=_make_mock(times, values)):
        result = fetch_aod(32.8022, 130.7081)
    assert result == round((0.3 + 0.5) / 2, 3)


def test_fetch_aod_returns_none_when_all_none():
    times = [f"2026-05-09T{h:02d}:00" for h in range(24)]
    values = [0.0] * 21 + [None, None, None] + [0.0]
    with patch("cams_client.requests.get", return_value=_make_mock(times, values)):
        result = fetch_aod(32.8022, 130.7081)
    assert result is None


def test_fetch_aod_returns_none_on_exception():
    with patch("cams_client.requests.get", side_effect=Exception("timeout")):
        result = fetch_aod(32.8022, 130.7081)
    assert result is None
