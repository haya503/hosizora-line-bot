import logging
import requests
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
logger = logging.getLogger(__name__)

KNOWN_COMETS = [
    "C/2025 E3",
    "C/2023 A3",
    "12P/Pons-Brooks",
    "C/2024 G3",
    "C/2021 S3",
]

_skyfield_loaded = False
_ts = None
_eph = None


def _load_skyfield():
    global _skyfield_loaded, _ts, _eph
    if _skyfield_loaded:
        return _ts is not None and _eph is not None
    _skyfield_loaded = True
    try:
        from skyfield.api import Loader
        for path in ["/app/skyfield-data", "/tmp/skyfield-data"]:
            try:
                loader = Loader(path)
                _ts = loader.timescale(builtin=True)
                _eph = loader("de421.bsp")
                return True
            except Exception:
                continue
        return False
    except ImportError:
        return False


@dataclass
class CometInfo:
    name: str
    best_time: str   # JST "HH:MM"
    altitude: float  # 度
    magnitude: float


def fetch_visible_comets(lat: float, lon: float, date_jst: str) -> list[CometInfo]:
    result = []
    for comet_id in KNOWN_COMETS:
        try:
            info = _query_comet(comet_id, lat, lon, date_jst)
            if info is not None:
                result.append(info)
        except Exception:
            continue
    return result


def _query_comet(comet_id: str, lat: float, lon: float, date_jst: str) -> "CometInfo | None":
    date_obj = date.fromisoformat(date_jst)
    tomorrow = date_obj + timedelta(days=1)
    url = "https://ssd.jpl.nasa.gov/api/horizons.api"
    params = {
        "format": "text",
        "COMMAND": f"DES={comet_id};",
        "OBJ_DATA": "NO",
        "MAKE_EPHEM": "YES",
        "EPHEM_TYPE": "OBSERVER",
        "CENTER": "coord@399",
        "SITE_COORD": f"{lon},{lat},0",
        "START_TIME": f"{date_obj} 12:00",
        "STOP_TIME": f"{tomorrow} 16:00",
        "STEP_SIZE": "1 h",
        "QUANTITIES": "2,9",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        text = resp.text
    except requests.exceptions.RequestException as e:
        logger.warning("Horizons fetch failed for %s: %s", comet_id, e)
        return None

    if "No ephemeris" in text or "Cannot find" in text:
        return None

    rows = _parse_ephemeris(text)
    if not rows:
        return None

    if not _load_skyfield():
        logger.warning("Skyfield not available; skipping altitude computation for %s", comet_id)
        return None

    from skyfield.api import Star, wgs84

    location = wgs84.latlon(lat, lon)
    observer = _eph["earth"] + location
    best_alt, best_jst_str, best_mag = -90.0, None, None

    for utc_dt, ra_hours, dec_deg, mag in rows:
        if mag > 10.0:
            continue
        t = _ts.from_datetime(utc_dt)
        star = Star(ra_hours=ra_hours, dec_degrees=dec_deg)
        alt, _, _ = observer.at(t).observe(star).apparent().altaz()
        jst_hour = utc_dt.astimezone(JST).hour
        if 21 <= jst_hour <= 23 and alt.degrees >= 10.0 and alt.degrees > best_alt:
            best_alt = alt.degrees
            best_jst_str = utc_dt.astimezone(JST).strftime("%H:%M")
            best_mag = mag

    if best_jst_str is None:
        return None

    return CometInfo(
        name=comet_id,
        best_time=best_jst_str,
        altitude=round(best_alt, 1),
        magnitude=best_mag,
    )


def _parse_ephemeris(text: str) -> list[tuple[datetime, float, float, float]]:
    rows = []
    in_data = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "$$SOE":
            in_data = True
            continue
        if stripped == "$$EOE":
            break
        if not in_data or not stripped:
            continue
        parts = stripped.split()
        # flag文字（"*" など）がRA列の前に入る場合のオフセット
        offset = 1 if len(parts) > 2 and not parts[2].replace(".", "").lstrip("-").isdigit() else 0
        if len(parts) < 9 + offset:
            continue
        try:
            dt = datetime.strptime(
                f"{parts[0]} {parts[1]}", "%Y-%b-%d %H:%M"
            ).replace(tzinfo=timezone.utc)
            ra_h = float(parts[2 + offset])
            ra_m = float(parts[3 + offset])
            ra_s = float(parts[4 + offset])
            ra_hours = ra_h + ra_m / 60 + ra_s / 3600
            dec_str = parts[5 + offset]
            dec_sign = -1 if dec_str.startswith("-") else 1
            dec_d = abs(float(dec_str))
            dec_m = float(parts[6 + offset])
            dec_s = float(parts[7 + offset])
            dec_deg = dec_sign * (dec_d + dec_m / 60 + dec_s / 3600)
            mag = float(parts[8 + offset])
            rows.append((dt, ra_hours, dec_deg, mag))
        except (ValueError, IndexError):
            continue
    return rows
