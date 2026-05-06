from unittest.mock import patch, MagicMock
import apod_client


def test_fetch_apod_returns_tuple_for_image():
    """正常系（画像）: media_type="image" のレスポンスで (url, title) が返る"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "media_type": "image",
        "url": "https://example.com/photo.jpg",
        "title": "Stellar Nursery"
    }
    with patch("apod_client.requests.get") as mock_get:
        mock_get.return_value = mock_resp
        result = apod_client.fetch_apod("test_api_key")
    assert result == ("https://example.com/photo.jpg", "Stellar Nursery")
    mock_get.assert_called_once_with(
        "https://api.nasa.gov/planetary/apod",
        params={"api_key": "test_api_key"},
        timeout=10
    )


def test_fetch_apod_returns_none_for_video():
    """動画の日: media_type="video" のレスポンスで None が返る"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "media_type": "video",
        "url": "https://youtube.com/...",
        "title": "Some Video"
    }
    with patch("apod_client.requests.get") as mock_get:
        mock_get.return_value = mock_resp
        result = apod_client.fetch_apod("test_api_key")
    assert result is None


def test_fetch_apod_returns_none_on_error():
    """ネットワークエラー: requests.get が例外を発生させたとき None が返る"""
    with patch("apod_client.requests.get") as mock_get:
        mock_get.side_effect = Exception("network error")
        result = apod_client.fetch_apod("test_api_key")
    assert result is None
