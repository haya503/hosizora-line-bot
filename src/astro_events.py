from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from skyfield.api import Loader, wgs84
from skyfield import almanac

JST = timezone(timedelta(hours=9))
_KNOWN_NEW_MOON = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
_LUNAR_CYCLE = 29.530589  # days

METEOR_SHOWERS = [
    ("しぶんぎ座流星群", 1, 3),
    ("4月こと座流星群", 4, 22),
    ("みずがめ座η流星群", 5, 5),
    ("ペルセウス座流星群", 8, 12),
    ("オリオン座流星群", 10, 21),
    ("おうし座流星群", 11, 5),
    ("しし座流星群", 11, 17),
    ("ふたご座流星群", 12, 13),
    ("こぐま座流星群", 12, 22),
]

_PLANET_KEYS = {
    "venus": "金星",
    "jupiter barycenter": "木星",
    "saturn barycenter": "土星",
}


@dataclass
class PlanetInfo:
    name: str
    transit_time: Optional[str]
    max_altitude: Optional[float]


def get_moon_age(now_utc: datetime) -> float:
    days_since = (now_utc - _KNOWN_NEW_MOON).total_seconds() / 86400
    return days_since % _LUNAR_CYCLE


def get_upcoming_meteor_showers(today: date, days_ahead: int = 7) -> list[tuple[str, int]]:
    result = []
    for name, month, day in METEOR_SHOWERS:
        try:
            peak = date(today.year, month, day)
        except ValueError:
            continue
        days_until = (peak - today).days
        if 0 <= days_until <= days_ahead:
            result.append((name, days_until))
    return result


def get_moonrise(ts, eph, lat: float, lon: float, date_jst: date) -> Optional[str]:
    location = wgs84.latlon(lat, lon)
    f = almanac.risings_and_settings(eph, eph["moon"], location)
    t0 = ts.utc(date_jst.year, date_jst.month, date_jst.day, 9)
    t1 = ts.utc(date_jst.year, date_jst.month, date_jst.day + 1, 9)
    times, events = almanac.find_discrete(t0, t1, f)
    for t, e in zip(times, events):
        if e == 1:
            return t.astimezone(JST).strftime("%H:%M")
    return None


def get_planet_best_time(
    ts, eph, lat: float, lon: float, planet_key: str, date_jst: date
) -> tuple[Optional[str], Optional[float]]:
    location = wgs84.latlon(lat, lon)
    observer = eph["earth"] + location
    planet = eph[planet_key]
    best_alt = -90.0
    best_time = None
    t = datetime(date_jst.year, date_jst.month, date_jst.day, 18, tzinfo=JST)
    end = datetime(date_jst.year, date_jst.month, date_jst.day + 1, 6, tzinfo=JST)
    while t <= end:
        alt, _, _ = observer.at(ts.from_datetime(t)).observe(planet).apparent().altaz()
        if alt.degrees > best_alt:
            best_alt = alt.degrees
            best_time = t
        t += timedelta(minutes=10)
    if best_alt < 10.0:
        return None, None
    return best_time.strftime("%H:%M"), round(best_alt, 1)  # type: ignore[union-attr]


def get_astro_data(
    lat: float, lon: float, now_utc: datetime
) -> tuple[float, Optional[str], list[PlanetInfo], list[tuple[str, int]]]:
    load = Loader("/tmp/skyfield-data")
    ts = load.timescale()
    eph = load("de421.bsp")
    date_jst = now_utc.astimezone(JST).date()

    moon_age = get_moon_age(now_utc)
    moonrise = get_moonrise(ts, eph, lat, lon, date_jst)

    planets = []
    for key, name in _PLANET_KEYS.items():
        transit_time, max_alt = get_planet_best_time(ts, eph, lat, lon, key, date_jst)
        planets.append(PlanetInfo(name=name, transit_time=transit_time, max_altitude=max_alt))

    meteor_showers = get_upcoming_meteor_showers(date_jst)
    return moon_age, moonrise, planets, meteor_showers
