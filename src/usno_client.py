from datetime import datetime, timedelta, timezone
from typing import Optional

from skyfield.api import Loader, wgs84
from skyfield import almanac

JST = timezone(timedelta(hours=9))


def fetch_astronomical_twilight(lat: float, lon: float, date_str: str) -> Optional[str]:
    """天文薄明終了時刻（JST HH:MM）を返す。取得失敗時は None。"""
    try:
        load = Loader("/tmp/skyfield-data")
        ts = load.timescale()
        eph = load("de421.bsp")

        d = datetime.fromisoformat(date_str)
        location = wgs84.latlon(lat, lon)
        f = almanac.dark_twilight_day(eph, location)

        t0 = ts.utc(d.year, d.month, d.day, 9)      # JST 18:00 (= UTC 09:00)
        t1 = ts.utc(d.year, d.month, d.day + 1, 9)  # JST 翌18:00

        times, events = almanac.find_discrete(t0, t1, f)

        # event == 0 のとき Dark (天文薄明終了 = 完全な夜になった瞬間)
        # 夕方の最初の 0 を探す
        for t, e in zip(times, events):
            if e == 0:
                dt_jst = t.utc_datetime().replace(tzinfo=timezone.utc).astimezone(JST)
                return dt_jst.strftime("%H:%M")
        return None
    except Exception:
        return None
