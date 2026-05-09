import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def fetch_aod(lat: float, lon: float) -> Optional[float]:
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "aerosol_optical_depth",
        "timezone": "Asia/Tokyo",
        "forecast_days": 1,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()["hourly"]
        times = data["time"]
        values = data["aerosol_optical_depth"]
        evening_idx = [
            i for i, t in enumerate(times)
            if any(t.endswith(f"T{h:02d}:00") for h in range(21, 24))
        ]
        if not evening_idx:
            return None
        vals = [values[i] for i in evening_idx if values[i] is not None]
        if not vals:
            return None
        return round(sum(vals) / len(vals), 3)
    except (requests.exceptions.RequestException, ValueError, KeyError, TypeError) as e:
        logger.warning("CAMS AOD fetch failed: %s", e)
        return None
