from unittest.mock import patch, MagicMock
import apod_client

_IMAGE_URL = "https://assets.science.nasa.gov/dynamicimage/assets/science/cds/apod/apod/2026/october/Nebula.jpg"


def _entry(**overrides) -> dict:
    entry = {
        "date": "2026-10-15",
        "media_type": "image",
        "url": "https://science.nasa.gov/image-article/apod-2026-october-15/",
        "hdurl": f"{_IMAGE_URL}?w=1280&#038;h=1280&#038;fit=clip",
        "title": "Stellar Nursery in Orion&#8217;s Belt",
        "explanation": "<p>A <a href=\"https://example.com\">beautiful nebula</a> in deep space.</p>",
    }
    entry.update(overrides)
    return entry


def _fetch_with(entries):
    mock_resp = MagicMock()
    mock_resp.json.return_value = entries
    with patch("apod_client.requests.get", return_value=mock_resp) as mock_get:
        return apod_client.fetch_apod(), mock_get


def test_fetch_apod_returns_tuple_for_image():
    """正常系（画像）: hdurl の画像 URL と、HTML を除いた title / explanation が返る"""
    result, mock_get = _fetch_with([_entry()])
    assert result == (
        f"{_IMAGE_URL}?w=1280&h=1280&fit=clip",
        "Stellar Nursery in Orion’s Belt",
        "A beautiful nebula in deep space.",
    )
    mock_get.assert_called_once_with(
        "https://science.nasa.gov/wp-json/wp/v2/apod-basic",
        params={"per_page": 1},
        headers={"User-Agent": "hosizora-line-bot (+https://github.com/haya503/hosizora-line-bot)"},
        timeout=10
    )


def test_fetch_apod_adds_resize_query_when_missing():
    """hdurl にクエリが無いときは LINE のサイズ上限に収まるようリサイズ指定を付ける"""
    result, _ = _fetch_with([_entry(hdurl=_IMAGE_URL)])
    assert result[0] == f"{_IMAGE_URL}?w=1280&h=1280&fit=clip"


def test_fetch_apod_returns_none_for_video():
    """動画の日: media_type="video" のレスポンスで None が返る"""
    result, _ = _fetch_with([_entry(media_type="video")])
    assert result is None


def test_fetch_apod_returns_none_for_nasa_logo_placeholder():
    """NASA ロゴのプレースホルダー画像が返ったときは None を返す"""
    logo = "https://science.nasa.gov/wp-content/themes/nasa-child/assets/images/nasa-logo@2x.png"
    result, _ = _fetch_with([_entry(hdurl=logo, title="NASA Science")])
    assert result is None


def test_fetch_apod_returns_none_for_nasa_science_title():
    """タイトルが "NASA Science" のプレースホルダーは画像 URL に関係なく None を返す"""
    result, _ = _fetch_with([_entry(title="NASA Science")])
    assert result is None


def test_fetch_apod_returns_none_without_hdurl():
    """hdurl が無いエントリは None を返す"""
    result, _ = _fetch_with([_entry(hdurl=None)])
    assert result is None


def test_fetch_apod_returns_none_for_empty_list():
    """エントリが空のレスポンスは None を返す"""
    result, _ = _fetch_with([])
    assert result is None


def test_fetch_apod_returns_none_on_error():
    """ネットワークエラー: requests.get が例外を発生させたとき None が返る"""
    with patch("apod_client.requests.get") as mock_get:
        mock_get.side_effect = Exception("network error")
        result = apod_client.fetch_apod()
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
