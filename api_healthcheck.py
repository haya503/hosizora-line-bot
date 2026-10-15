"""一時的な API ヘルスチェック。LINE には何も送らない。"""
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import requests

logging.basicConfig(level=logging.WARNING, format="  (log) %(name)s: %(message)s")
JST = timezone(timedelta(hours=9))
LAT, LON = 32.8022, 130.7081
DATE_JST = datetime.now(JST).date().isoformat()


def run(name, fn):
    t0 = time.monotonic()
    try:
        result = fn()
        print(f"[OK] {name} ({time.monotonic() - t0:.1f}s): {result!r}"[:3000], flush=True)
    except Exception as e:
        print(f"[NG] {name} ({time.monotonic() - t0:.1f}s): {type(e).__name__}: {e}"[:3000], flush=True)


print(f"now JST = {datetime.now(JST).isoformat()}  date_jst = {DATE_JST}")

from sky_forecast import fetch_sky_conditions
run("Open-Meteo forecast", lambda: fetch_sky_conditions(LAT, LON))

from astro_client import fetch_7timer_astro, fetch_constellations
run("7timer ASTRO", lambda: fetch_7timer_astro(LAT, LON))


def seven_timer_raw():
    r = requests.get(
        "http://www.7timer.info/bin/astro.php",
        params={"lon": LON, "lat": LAT, "ac": 0, "lang": "en", "output": "json", "tzshift": 0},
        timeout=15,
    )
    d = r.json()
    return {"status": r.status_code, "init": d.get("init"),
            "series": [(s["timepoint"], s["seeing"], s["transparency"]) for s in d["dataseries"][:6]]}


run("7timer raw", seven_timer_raw)
run("hoshimiru constellations",
    lambda: fetch_constellations(LAT, LON, DATE_JST, os.environ.get("HOSHIMIRU_API_TOKEN", "")))

from usno_client import fetch_astronomical_twilight
run("twilight (skyfield)", lambda: fetch_astronomical_twilight(LAT, LON, DATE_JST))

from astro_events import get_astro_data
run("astro_events (skyfield)", lambda: get_astro_data(LAT, LON, datetime.now(timezone.utc)))

from jma_client import fetch_night_weather_penalties
run("JMA penalties", lambda: fetch_night_weather_penalties(os.environ.get("JMA_AREA_CODE", "")))


def jma_raw():
    code = os.environ.get("JMA_AREA_CODE", "")
    r = requests.get(f"https://www.jma.go.jp/bosai/forecast/data/forecast/{code}.json", timeout=10)
    out = {"status": r.status_code, "code_len": len(code), "code_tail": code[-4:]}
    if r.ok:
        d = r.json()
        ts = d[0]["timeSeries"]
        out.update(
            office=d[0].get("publishingOffice"),
            report=d[0].get("reportDatetime"),
            ts0_timeDefines=ts[0]["timeDefines"],
            ts0_areas=[(a["area"]["name"], a.get("weatherCodes")) for a in ts[0]["areas"]],
            ts1_timeDefines=ts[1]["timeDefines"] if len(ts) > 1 else None,
            ts1_keys=list(ts[1]["areas"][0].keys()) if len(ts) > 1 else None,
        )
    return out


run("JMA raw", jma_raw)

from cams_client import fetch_aod, fetch_pm25
run("CAMS AOD", lambda: fetch_aod(LAT, LON))
run("CAMS PM2.5", lambda: fetch_pm25(LAT, LON))

from horizons_client import KNOWN_COMETS, _parse_ephemeris, fetch_visible_comets
run("Horizons comets", lambda: fetch_visible_comets(LAT, LON, DATE_JST))


def horizons_raw(comet_id):
    r = requests.get("https://ssd.jpl.nasa.gov/api/horizons.api", params={
        "format": "text", "COMMAND": f"DES={comet_id};", "OBJ_DATA": "NO", "MAKE_EPHEM": "YES",
        "EPHEM_TYPE": "OBSERVER", "CENTER": "coord@399", "SITE_COORD": f"{LON},{LAT},0",
        "START_TIME": f"{DATE_JST} 12:00", "STOP_TIME": f"{DATE_JST} 15:00",
        "STEP_SIZE": "1 h", "QUANTITIES": "2,9",
    }, timeout=15)
    text = r.text
    rows = _parse_ephemeris(text)
    info = {"status": r.status_code, "has_SOE": "$$SOE" in text, "rows": len(rows),
            "mags": [m for *_, m in rows]}
    if not rows:
        info["text_head"] = " | ".join(line.strip() for line in text.splitlines()[:25] if line.strip())[:1500]
    return info


for c in KNOWN_COMETS:
    run(f"Horizons raw {c}", lambda c=c: horizons_raw(c))

from apod_client import fetch_apod
run("APOD", fetch_apod)


def deepl_usage():
    key = os.environ.get("DEEPL_API_KEY", "")
    if not key:
        return "DEEPL_API_KEY 未設定"
    r = requests.get("https://api-free.deepl.com/v2/usage",
                     headers={"Authorization": f"DeepL-Auth-Key {key}"}, timeout=10)
    return r.status_code, r.text[:200]


run("DeepL usage", deepl_usage)
