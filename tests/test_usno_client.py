from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import usno_client


def test_fetch_astronomical_twilight_returns_time():
    mock_t = MagicMock()
    mock_t.utc_datetime.return_value = datetime(2026, 5, 6, 11, 34, tzinfo=timezone.utc)  # 20:34 JST

    with patch("usno_client.Loader") as mock_loader_cls, \
         patch("usno_client.almanac.find_discrete", return_value=([mock_t], [0])):
        mock_loader_cls.return_value = MagicMock()
        result = usno_client.fetch_astronomical_twilight(35.6762, 139.6503, "2026-05-06")

    assert result == "20:34"


def test_fetch_astronomical_twilight_returns_none_when_no_dark_event():
    with patch("usno_client.Loader") as mock_loader_cls, \
         patch("usno_client.almanac.find_discrete", return_value=([], [])):
        mock_loader_cls.return_value = MagicMock()
        result = usno_client.fetch_astronomical_twilight(35.6762, 139.6503, "2026-05-06")

    assert result is None


def test_fetch_astronomical_twilight_returns_none_on_error():
    with patch("usno_client.Loader") as mock_loader_cls:
        mock_loader_cls.side_effect = Exception("skyfield error")
        result = usno_client.fetch_astronomical_twilight(35.6762, 139.6503, "2026-05-06")

    assert result is None
