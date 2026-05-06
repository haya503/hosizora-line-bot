from typing import Optional
import requests


def fetch_apod(api_key: str) -> Optional[tuple[str, str]]:
    """
    NASA APOD API から今日の天文写真の (url, title) を返す。
    media_type が "video" の日、または取得失敗時は None を返す。

    Args:
        api_key: NASA API キー

    Returns:
        (url, title) のタプル、または None
    """
    try:
        response = requests.get(
            "https://api.nasa.gov/planetary/apod",
            params={"api_key": api_key},
            timeout=10
        )
        data = response.json()

        # media_type が "video" の場合は None を返す
        if data.get("media_type") == "video":
            return None

        # 正常時は (url, title) を返す
        url = data.get("url")
        title = data.get("title")
        if url and title:
            return (url, title)
        return None

    except Exception:
        return None
