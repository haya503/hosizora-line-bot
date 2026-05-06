from typing import Optional
import requests

_URL = "https://aa.usno.navy.mil/api/rstt/oneday"


def fetch_astronomical_twilight(lat: float, lon: float, date: str) -> Optional[str]:
    """天文薄明終了時刻（JST）を返す。取得失敗時は None。"""
    try:
        resp = requests.get(
            _URL,
            params={"date": date, "coords": f"{lat},{lon}", "tz": 9},
            timeout=10,
        )
        resp.raise_for_status()
        phenomena = resp.json()["properties"]["data"]["phenomena"]
        for p in phenomena:
            if p["phen"] == "EA":
                return p["time"]
        return None
    except Exception:
        return None
