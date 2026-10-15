import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def _fetch_evening_mean(lat: float, lon: float, variable: str, ndigits: int) -> Optional[float]:
    """Open-Meteo Air Quality API (CAMS) から当日 21〜23 時の平均値を返す。失敗時は None。"""
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": variable,
        "timezone": "Asia/Tokyo",
        "forecast_days": 1,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()["hourly"]
        times = data["time"]
        values = data[variable]
        evening_idx = [
            i for i, t in enumerate(times)
            if any(t.endswith(f"T{h:02d}:00") for h in range(21, 24))
        ]
        if not evening_idx:
            return None
        vals = [values[i] for i in evening_idx if values[i] is not None]
        if not vals:
            return None
        return round(sum(vals) / len(vals), ndigits)
    except (requests.exceptions.RequestException, ValueError, KeyError, TypeError) as e:
        logger.warning("CAMS %s fetch failed: %s", variable, e)
        return None


def fetch_aod(lat: float, lon: float) -> Optional[float]:
    return _fetch_evening_mean(lat, lon, "aerosol_optical_depth", 3)


def fetch_pm25(lat: float, lon: float) -> Optional[float]:
    """当夜 21〜23 時の PM2.5 予報値の平均 (μg/m³)。"""
    return _fetch_evening_mean(lat, lon, "pm2_5", 1)
