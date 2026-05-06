from typing import Optional
import requests


def fetch_apod(api_key: str) -> Optional[tuple[str, str, str]]:
    """
    NASA APOD API から今日の天文写真の (url, title, explanation) を返す。
    media_type が "video" の日、または取得失敗時は None を返す。
    """
    try:
        response = requests.get(
            "https://api.nasa.gov/planetary/apod",
            params={"api_key": api_key},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if data.get("media_type") == "video":
            return None

        url = data.get("url")
        title = data.get("title")
        explanation = data.get("explanation", "")
        if url and title:
            return (url, title, explanation)
        return None

    except Exception:
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
