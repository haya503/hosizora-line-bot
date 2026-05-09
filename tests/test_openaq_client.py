import requests
from unittest.mock import MagicMock, patch
from openaq_client import fetch_pm25


def _make_mock(results):
    m = MagicMock()
    m.json.return_value = {"results": results}
    m.raise_for_status.return_value = None
    return m


def test_fetch_pm25_returns_float():
    results = [
        {"sensors": [{"parameter": {"name": "pm25"}, "latest": {"value": 12.3}}]}
    ]
    with patch("openaq_client.requests.get", return_value=_make_mock(results)):
        result = fetch_pm25(32.8022, 130.7081)
    assert result == 12.3


def test_fetch_pm25_skips_non_pm25_sensors():
    results = [
        {"sensors": [
            {"parameter": {"name": "no2"}, "latest": {"value": 50.0}},
            {"parameter": {"name": "pm25"}, "latest": {"value": 8.0}},
        ]}
    ]
    with patch("openaq_client.requests.get", return_value=_make_mock(results)):
        result = fetch_pm25(32.8022, 130.7081)
    assert result == 8.0


def test_fetch_pm25_returns_none_when_no_pm25():
    results = [
        {"sensors": [{"parameter": {"name": "no2"}, "latest": {"value": 50.0}}]}
    ]
    with patch("openaq_client.requests.get", return_value=_make_mock(results)):
        result = fetch_pm25(32.8022, 130.7081)
    assert result is None


def test_fetch_pm25_returns_none_on_empty_results():
    with patch("openaq_client.requests.get", return_value=_make_mock([])):
        result = fetch_pm25(32.8022, 130.7081)
    assert result is None


def test_fetch_pm25_returns_none_on_exception():
    with patch("openaq_client.requests.get", side_effect=requests.exceptions.RequestException("network error")):
        result = fetch_pm25(32.8022, 130.7081)
    assert result is None


def test_fetch_pm25_returns_none_on_http_error():
    with patch("openaq_client.requests.get") as mock_get:
        mock_get.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError("429")
        result = fetch_pm25(32.8022, 130.7081)
    assert result is None
