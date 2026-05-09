import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def fetch_pm25(lat: float, lon: float) -> Optional[float]:
    url = "https://api.openaq.io/v3/locations"
    params = {
        "coordinates": f"{lat},{lon}",
        "radius": 50000,
        "parameters_name": "pm25",
        "limit": 5,
        "order_by": "distance",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        for loc in resp.json().get("results", []):
            for sensor in loc.get("sensors", []):
                if sensor.get("parameter", {}).get("name") == "pm25":
                    val = (sensor.get("latest") or {}).get("value")
                    if val is not None:
                        return float(val)
        return None
    except requests.exceptions.RequestException as e:
        logger.warning("OpenAQ fetch failed: %s", e)
        return None
