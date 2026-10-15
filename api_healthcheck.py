"""一時的な API ヘルスチェック（2回目: 気象庁・Horizons の修正方針の確認）。LINE には何も送らない。"""
import os
from datetime import datetime, timedelta, timezone

import requests

JST = timezone(timedelta(hours=9))
LAT, LON = 32.8022, 130.7081
DATE_JST = datetime.now(JST).date().isoformat()
print(f"now JST = {datetime.now(JST).isoformat()}")

# --- 気象庁: 府県予報区コード 430000 での構造確認 ---
for code in ["430000"]:
    r = requests.get(f"https://www.jma.go.jp/bosai/forecast/data/forecast/{code}.json", timeout=10)
    print(f"[JMA {code}] status={r.status_code}")
    if r.ok:
        d = r.json()
        print("  office:", d[0].get("publishingOffice"), "report:", d[0].get("reportDatetime"))
        for i, ts in enumerate(d[0]["timeSeries"]):
            a0 = ts["areas"][0]
            print(f"  ts[{i}] timeDefines={ts['timeDefines']}")
            print(f"        areas={[a['area'] for a in ts['areas']]}")
            print(f"        area0 keys={list(a0.keys())}")
            for k in ("weatherCodes", "pops"):
                if k in a0:
                    print(f"        area0 {k}={a0[k]}")

# --- Horizons: パラメータを単一引用符で囲んだ場合 ---
from horizons_client import KNOWN_COMETS, _parse_ephemeris

def q(v):
    return f"'{v}'"

for comet_id in KNOWN_COMETS + ["12P"]:
    params = {
        "format": "text", "COMMAND": q(f"DES={comet_id};"), "OBJ_DATA": "NO", "MAKE_EPHEM": "YES",
        "EPHEM_TYPE": "OBSERVER", "CENTER": q("coord@399"), "SITE_COORD": q(f"{LON},{LAT},0"),
        "START_TIME": q(f"{DATE_JST} 12:00"), "STOP_TIME": q(f"{DATE_JST} 15:00"),
        "STEP_SIZE": q("1 h"), "QUANTITIES": q("2,9"),
    }
    r = requests.get("https://ssd.jpl.nasa.gov/api/horizons.api", params=params, timeout=20)
    text = r.text
    rows = _parse_ephemeris(text)
    print(f"[Horizons {comet_id}] status={r.status_code} SOE={'$$SOE' in text} rows={len(rows)} mags={[m for *_, m in rows]}")
    if not rows:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        print("   head:", " | ".join(lines[:12])[:900])
    else:
        soe = text.index("$$SOE")
        print("   sample:", " | ".join(text[soe - 300:soe + 250].splitlines()[-6:]))
