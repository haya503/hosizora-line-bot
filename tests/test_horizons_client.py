import requests
from unittest.mock import MagicMock, patch
from horizons_client import fetch_visible_comets, _parse_ephemeris, CometInfo

SAMPLE_HORIZONS_TEXT = """
*******************************************************************************
 Revised: ...
*******************************************************************************
$$SOE
2026-May-09 12:00 *  10 30 00.00  +20 00 00.0  5.5
2026-May-09 21:00 *  10 30 00.00  +20 00 00.0  5.5
2026-May-09 22:00 *  10 30 00.00  +20 00 00.0  5.5
2026-May-09 23:00 *  10 30 00.00  +20 00 00.0  5.5
$$EOE
*******************************************************************************
"""

SAMPLE_HORIZONS_TEXT_NO_COMET = """
$$SOE
$$EOE
"""

SAMPLE_HORIZONS_TEXT_FAINT = """
$$SOE
2026-May-09 21:00 *  10 30 00.00  +20 00 00.0  11.0
$$EOE
"""


def test_parse_ephemeris_returns_rows():
    rows = _parse_ephemeris(SAMPLE_HORIZONS_TEXT)
    assert len(rows) == 4


def test_parse_ephemeris_correct_magnitude():
    rows = _parse_ephemeris(SAMPLE_HORIZONS_TEXT)
    _, _, _, mag = rows[0]
    assert mag == 5.5


def test_parse_ephemeris_empty_on_no_data():
    rows = _parse_ephemeris(SAMPLE_HORIZONS_TEXT_NO_COMET)
    assert rows == []


def test_fetch_visible_comets_returns_list():
    mock = MagicMock()
    mock.text = SAMPLE_HORIZONS_TEXT
    mock.raise_for_status.return_value = None
    with patch("horizons_client.requests.get", return_value=mock):
        result = fetch_visible_comets(32.8022, 130.7081, "2026-05-09")
    assert isinstance(result, list)


def test_fetch_visible_comets_filters_faint():
    mock = MagicMock()
    mock.text = SAMPLE_HORIZONS_TEXT_FAINT
    mock.raise_for_status.return_value = None
    with patch("horizons_client.requests.get", return_value=mock):
        result = fetch_visible_comets(32.8022, 130.7081, "2026-05-09")
    assert result == []


def test_fetch_visible_comets_returns_empty_on_exception():
    with patch("horizons_client.requests.get", side_effect=requests.exceptions.RequestException("timeout")):
        result = fetch_visible_comets(32.8022, 130.7081, "2026-05-09")
    assert result == []


def test_fetch_visible_comets_returns_empty_when_no_ephemeris():
    mock = MagicMock()
    mock.text = "No ephemeris for target"
    mock.raise_for_status.return_value = None
    with patch("horizons_client.requests.get", return_value=mock):
        result = fetch_visible_comets(32.8022, 130.7081, "2026-05-09")
    assert result == []
