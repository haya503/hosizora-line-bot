from dataclasses import dataclass
import requests


@dataclass
class SkyConditions:
    cloud_cover: int   # %
    visibility: int    # m
    humidity: int      # %
    wind_speed: float  # m/s


def fetch_sky_conditions(lat: float, lon: float) -> SkyConditions:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "cloud_cover,visibility,relative_humidity_2m,wind_speed_10m",
        "timezone": "Asia/Tokyo",
        "forecast_days": 1,
    }
    last_exc: Exception | None = None
    for _ in range(2):
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()["hourly"]
            times = data["time"]
            evening_suffixes = {f"T{h:02d}:00" for h in range(18, 24)}
            idx = [i for i, t in enumerate(times) if any(t.endswith(s) for s in evening_suffixes)]

            def avg(vals: list) -> float:
                return sum(vals[i] for i in idx) / len(idx)

            return SkyConditions(
                cloud_cover=round(avg(data["cloud_cover"])),
                visibility=round(avg(data["visibility"])),
                humidity=round(avg(data["relative_humidity_2m"])),
                wind_speed=round(avg(data["wind_speed_10m"]), 1),
            )
        except requests.RequestException as e:
            last_exc = e
    raise last_exc  # type: ignore[misc]
