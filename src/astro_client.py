from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import requests

JST = timezone(timedelta(hours=9))


@dataclass
class HourlyAstroData:
    seeing: int        # 1-8 (1=最良)
    transparency: int  # 1-8 (1=最良)


def fetch_7timer_astro(lat: float, lon: float) -> dict[int, HourlyAstroData]:
    """JST 21〜24時のシーイング・透明度を返す。keyはJST時(21,22,23,24)。"""
    url = "http://www.7timer.info/bin/astro.php"
    params = {"lon": lon, "lat": lat, "ac": 0, "lang": "en", "output": "json", "tzshift": 0}

    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    init_utc = datetime.strptime(data["init"], "%Y%m%d%H").replace(tzinfo=timezone.utc)
    today_jst = (init_utc + timedelta(hours=9)).date()
    dataseries = data["dataseries"]

    result: dict[int, HourlyAstroData] = {}
    for jst_hour in [21, 22, 23, 24]:
        if jst_hour == 24:
            jst_dt = (
                datetime(today_jst.year, today_jst.month, today_jst.day, 0, tzinfo=JST)
                + timedelta(days=1)
            )
        else:
            jst_dt = datetime(today_jst.year, today_jst.month, today_jst.day, jst_hour, tzinfo=JST)
        target_offset = (jst_dt.astimezone(timezone.utc) - init_utc).total_seconds() / 3600
        nearest = min(dataseries, key=lambda d, t=target_offset: abs(d["timepoint"] - t))
        result[jst_hour] = HourlyAstroData(
            seeing=nearest["seeing"],
            transparency=nearest["transparency"],
        )
    return result


def fetch_constellations(lat: float, lon: float, date_jst: str, token: str) -> list[str]:
    """22時JST時点で見える星座名を最大5件返す。"""
    url = "https://app.livlog.xyz/hoshimiru/constellation"
    params = {"lat": lat, "lng": lon, "date": date_jst, "hour": 22, "min": 0}
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    items = data.get("results", [])
    names = [item["jpName"] for item in items if "jpName" in item]
    return names[:5]
