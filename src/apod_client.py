import html
import logging
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# 2026-09 に APOD が science.nasa.gov (WordPress) へ移行し、旧 api.nasa.gov/planetary/apod は
# 全日付で NASA ロゴ画像を返すようになったため、移行先のエンドポイント（APIキー不要）を使う。
_APOD_URL = "https://science.nasa.gov/wp-json/wp/v2/apod-basic"
_USER_AGENT = "hosizora-line-bot (+https://github.com/haya503/hosizora-line-bot)"
# LINE の画像メッセージ上限（プレビュー 1MB）に収まるよう NASA の画像リサイズを指定する
_RESIZE_QUERY = "w=1280&h=1280&fit=clip"
_TAG_RE = re.compile(r"<[^>]+>")


def _html_to_text(value: Optional[str]) -> str:
    """WordPress が返す HTML 文字列からタグと文字参照を取り除く。"""
    return html.unescape(_TAG_RE.sub("", value or "")).strip()


def _is_placeholder(image_url: str, title: str) -> bool:
    """APOD 本来の画像の代わりに返される NASA ロゴのプレースホルダーかどうか。"""
    return "nasa-logo" in image_url or title == "NASA Science"


def fetch_apod() -> Optional[tuple[str, str, str]]:
    """
    NASA APOD から最新の天文写真の (image_url, title, explanation) を返す。
    画像以外の日（動画など）、プレースホルダー画像、取得失敗時は None を返す。
    """
    try:
        response = requests.get(
            _APOD_URL,
            params={"per_page": 1},
            headers={"User-Agent": _USER_AGENT},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list) or not data:
            logger.warning("APOD: unexpected response: %.200r", data)
            return None
        entry = data[0]

        if entry.get("media_type") != "image":
            return None

        # url は記事ページの URL になったため、画像は hdurl から取る
        image_url = html.unescape(entry.get("hdurl") or "")
        title = _html_to_text(entry.get("title"))
        explanation = _html_to_text(entry.get("explanation"))
        if not image_url.startswith("https://") or not title:
            logger.warning("APOD: missing image or title: %r / %r", image_url, title)
            return None
        if _is_placeholder(image_url, title):
            logger.warning("APOD: placeholder image returned: %s", image_url)
            return None

        if "?" not in image_url:
            image_url = f"{image_url}?{_RESIZE_QUERY}"
        return (image_url, title, explanation)

    except Exception as e:
        logger.warning("APOD fetch failed: %s", e)
        return None


def translate_apod_explanation(explanation: str, api_key: str) -> Optional[str]:
    """DeepL Free API で APOD の説明文を日本語に翻訳する。失敗時は None。"""
    if not api_key or not explanation:
        return None
    try:
        response = requests.post(
            "https://api-free.deepl.com/v2/translate",
            headers={"Authorization": f"DeepL-Auth-Key {api_key}"},
            json={"text": [explanation], "target_lang": "JA"},
            timeout=15
        )
        response.raise_for_status()
        return response.json()["translations"][0]["text"]
    except Exception:
        return None
