from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import requests

JST = timezone(timedelta(hours=9))


@dataclass
class HourlySkyReading:
    hour: int        # JST時 (21, 22, 23, 24)
    cloud_cover: int # %
    visibility: int  # m


@dataclass
class SkyConditions:
    humidity: int      # % 夜間(18-23時)平均
    wind_speed: float  # m/s 夜間平均
    hourly: list[HourlySkyReading]  # 21〜24時JST


def fetch_sky_conditions(
    lat: float, lon: float, today_jst: date | None = None
) -> SkyConditions:
    if today_jst is None:
        today_jst = datetime.now(JST).date()
    tomorrow_jst = today_jst + timedelta(days=1)

    target_times = {
        21: f"{today_jst}T21:00",
        22: f"{today_jst}T22:00",
        23: f"{today_jst}T23:00",
        24: f"{tomorrow_jst}T00:00",
    }

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "cloud_cover,visibility,relative_humidity_2m,wind_speed_10m",
        "timezone": "Asia/Tokyo",
        "forecast_days": 2,
    }
    last_exc: Exception | None = None
    for _ in range(2):
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()["hourly"]
            times = data["time"]

            evening_idx = [
                i for i, t in enumerate(times)
                if t.startswith(str(today_jst))
                and any(t.endswith(f"T{h:02d}:00") for h in range(18, 24))
            ]
            avg_humidity = round(
                sum(data["relative_humidity_2m"][i] for i in evening_idx) / len(evening_idx)
            )
            avg_wind = round(
                sum(data["wind_speed_10m"][i] for i in evening_idx) / len(evening_idx), 1
            )

            hourly = []
            for hour, target_time in target_times.items():
                if target_time in times:
                    i = times.index(target_time)
                    hourly.append(HourlySkyReading(
                        hour=hour,
                        cloud_cover=data["cloud_cover"][i],
                        visibility=data["visibility"][i],
                    ))

            return SkyConditions(humidity=avg_humidity, wind_speed=avg_wind, hourly=hourly)
        except requests.RequestException as e:
            last_exc = e
    raise last_exc  # type: ignore[misc]
