from unittest.mock import patch, MagicMock
import usno_client


SAMPLE_RESPONSE = {
    "properties": {
        "data": {
            "phenomena": [
                {"phen": "BC", "time": "04:46"},
                {"phen": "R",  "time": "05:12"},
                {"phen": "S",  "time": "18:17"},
                {"phen": "EN", "time": "19:12"},
                {"phen": "EA", "time": "19:42"},
            ]
        }
    }
}


def test_fetch_astronomical_twilight_returns_time():
    with patch("usno_client.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_RESPONSE
        mock_get.return_value = mock_resp
        result = usno_client.fetch_astronomical_twilight(35.6762, 139.6503, "2026-05-06")
    assert result == "19:42"


def test_fetch_astronomical_twilight_returns_none_when_ea_missing():
    response_no_ea = {
        "properties": {"data": {"phenomena": [{"phen": "R", "time": "05:12"}]}}
    }
    with patch("usno_client.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = response_no_ea
        mock_get.return_value = mock_resp
        result = usno_client.fetch_astronomical_twilight(35.6762, 139.6503, "2026-05-06")
    assert result is None


def test_fetch_astronomical_twilight_returns_none_on_http_error():
    with patch("usno_client.requests.get") as mock_get:
        mock_get.side_effect = Exception("network error")
        result = usno_client.fetch_astronomical_twilight(35.6762, 139.6503, "2026-05-06")
    assert result is None
