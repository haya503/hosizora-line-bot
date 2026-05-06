from unittest.mock import patch, MagicMock
import apod_client


def test_fetch_apod_returns_tuple_for_image():
    """正常系（画像）: media_type="image" のレスポンスで (url, title, explanation) が返る"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "media_type": "image",
        "url": "https://example.com/photo.jpg",
        "title": "Stellar Nursery",
        "explanation": "A beautiful nebula in deep space."
    }
    with patch("apod_client.requests.get") as mock_get:
        mock_get.return_value = mock_resp
        result = apod_client.fetch_apod("test_api_key")
    assert result == ("https://example.com/photo.jpg", "Stellar Nursery", "A beautiful nebula in deep space.")
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


def test_translate_apod_explanation_returns_text():
    """正常系: DeepL API が日本語翻訳を返す"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"translations": [{"text": "美しい星雲の写真です。"}]}
    with patch("apod_client.requests.post", return_value=mock_resp):
        result = apod_client.translate_apod_explanation("A beautiful nebula.", "test_key")
    assert result == "美しい星雲の写真です。"


def test_translate_apod_explanation_posts_to_deepl():
    """DeepL Free API エンドポイントを叩いていることを確認"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"translations": [{"text": "訳文"}]}
    with patch("apod_client.requests.post", return_value=mock_resp) as mock_post:
        apod_client.translate_apod_explanation("Some text.", "mykey")
    mock_post.assert_called_once_with(
        "https://api-free.deepl.com/v2/translate",
        headers={"Authorization": "DeepL-Auth-Key mykey"},
        json={"text": ["Some text."], "target_lang": "JA"},
        timeout=15
    )


def test_translate_apod_explanation_returns_none_on_empty_key():
    """APIキー未設定時は None を返す"""
    result = apod_client.translate_apod_explanation("Some explanation", "")
    assert result is None


def test_translate_apod_explanation_returns_none_on_empty_explanation():
    """説明文が空のときは None を返す"""
    result = apod_client.translate_apod_explanation("", "api_key")
    assert result is None


def test_translate_apod_explanation_returns_none_on_api_error():
    """DeepL API 呼び出し失敗時は None を返す"""
    with patch("apod_client.requests.post") as mock_post:
        mock_post.side_effect = Exception("API error")
        result = apod_client.translate_apod_explanation("Some explanation", "test_key")
    assert result is None
