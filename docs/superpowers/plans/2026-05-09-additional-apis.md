# Additional APIs (OpenAQ / CAMS / JPL Horizons) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 星空予報LINEボットに OpenAQ PM2.5・Open-Meteo CAMS AOD・JPL Horizons 彗星データを追加し、スコア補正と通知メッセージの両方を強化する。

**Architecture:** 3つの新規クライアントモジュール（openaq_client.py / cams_client.py / horizons_client.py）を `src/` に追加し、既存の `notify.py` から呼び出す。失敗時は `None` または空リストを返し既存APIと同じ「失敗スキップ」パターンを踏襲する。

**Tech Stack:** Python 3.12, requests, skyfield==1.49（既存依存）, pytest（既存）, Open-Meteo Air Quality API, JPL Horizons API, OpenAQ v3 API

---

### Task 1: OpenAQ PM2.5 クライアント

**Files:**
- Create: `src/openaq_client.py`
- Create: `tests/test_openaq_client.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_openaq_client.py` を新規作成:

```python
from unittest.mock import MagicMock, patch
from openaq_client import fetch_pm25


def _make_mock(results):
    m = MagicMock()
    m.json.return_value = {"results": results}
    m.raise_for_status.return_value = None
    return m


def test_fetch_pm25_returns_float():
    results = [
        {"sensors": [{"parameter": {"name": "pm25"}, "latest": {"value": 12.3}}]}
    ]
    with patch("openaq_client.requests.get", return_value=_make_mock(results)):
        result = fetch_pm25(32.8022, 130.7081)
    assert result == 12.3


def test_fetch_pm25_skips_non_pm25_sensors():
    results = [
        {"sensors": [
            {"parameter": {"name": "no2"}, "latest": {"value": 50.0}},
            {"parameter": {"name": "pm25"}, "latest": {"value": 8.0}},
        ]}
    ]
    with patch("openaq_client.requests.get", return_value=_make_mock(results)):
        result = fetch_pm25(32.8022, 130.7081)
    assert result == 8.0


def test_fetch_pm25_returns_none_when_no_pm25():
    results = [
        {"sensors": [{"parameter": {"name": "no2"}, "latest": {"value": 50.0}}]}
    ]
    with patch("openaq_client.requests.get", return_value=_make_mock(results)):
        result = fetch_pm25(32.8022, 130.7081)
    assert result is None


def test_fetch_pm25_returns_none_on_empty_results():
    with patch("openaq_client.requests.get", return_value=_make_mock([])):
        result = fetch_pm25(32.8022, 130.7081)
    assert result is None


def test_fetch_pm25_returns_none_on_exception():
    with patch("openaq_client.requests.get", side_effect=Exception("network error")):
        result = fetch_pm25(32.8022, 130.7081)
    assert result is None
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
cd /home/kaede/stargazing-line-bot/.claude/worktrees/xenodochial-elbakyan-e26b16
python -m pytest tests/test_openaq_client.py -v 2>&1 | head -20
```

期待: `ModuleNotFoundError: No module named 'openaq_client'`

- [ ] **Step 3: 実装を書く**

`src/openaq_client.py` を新規作成:

```python
import requests


def fetch_pm25(lat: float, lon: float) -> float | None:
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
                    val = sensor.get("latest", {}).get("value")
                    if val is not None:
                        return float(val)
        return None
    except Exception:
        return None
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
cd /home/kaede/stargazing-line-bot/.claude/worktrees/xenodochial-elbakyan-e26b16
python -m pytest tests/test_openaq_client.py -v
```

期待: 5件 PASSED

- [ ] **Step 5: コミット**

```bash
git add src/openaq_client.py tests/test_openaq_client.py
git commit -m "feat: add OpenAQ PM2.5 client"
```

---

### Task 2: CAMS AOD クライアント（Open-Meteo Air Quality経由）

**Files:**
- Create: `src/cams_client.py`
- Create: `tests/test_cams_client.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_cams_client.py` を新規作成:

```python
from unittest.mock import MagicMock, patch
from cams_client import fetch_aod


def _make_mock(times, values):
    m = MagicMock()
    m.json.return_value = {
        "hourly": {"time": times, "aerosol_optical_depth": values}
    }
    m.raise_for_status.return_value = None
    return m


def test_fetch_aod_returns_evening_average():
    times = [f"2026-05-09T{h:02d}:00" for h in range(24)]
    values = [0.0] * 21 + [0.3, 0.5, 0.4] + [0.0]
    with patch("cams_client.requests.get", return_value=_make_mock(times, values)):
        result = fetch_aod(32.8022, 130.7081)
    assert result == round((0.3 + 0.5 + 0.4) / 3, 3)


def test_fetch_aod_skips_none_values():
    times = [f"2026-05-09T{h:02d}:00" for h in range(24)]
    values = [0.0] * 21 + [0.3, None, 0.5] + [0.0]
    with patch("cams_client.requests.get", return_value=_make_mock(times, values)):
        result = fetch_aod(32.8022, 130.7081)
    assert result == round((0.3 + 0.5) / 2, 3)


def test_fetch_aod_returns_none_when_all_none():
    times = [f"2026-05-09T{h:02d}:00" for h in range(24)]
    values = [0.0] * 21 + [None, None, None] + [0.0]
    with patch("cams_client.requests.get", return_value=_make_mock(times, values)):
        result = fetch_aod(32.8022, 130.7081)
    assert result is None


def test_fetch_aod_returns_none_on_exception():
    with patch("cams_client.requests.get", side_effect=Exception("timeout")):
        result = fetch_aod(32.8022, 130.7081)
    assert result is None
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
cd /home/kaede/stargazing-line-bot/.claude/worktrees/xenodochial-elbakyan-e26b16
python -m pytest tests/test_cams_client.py -v 2>&1 | head -20
```

期待: `ModuleNotFoundError: No module named 'cams_client'`

- [ ] **Step 3: 実装を書く**

`src/cams_client.py` を新規作成:

```python
import requests


def fetch_aod(lat: float, lon: float) -> float | None:
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
    except Exception:
        return None
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
cd /home/kaede/stargazing-line-bot/.claude/worktrees/xenodochial-elbakyan-e26b16
python -m pytest tests/test_cams_client.py -v
```

期待: 4件 PASSED

- [ ] **Step 5: コミット**

```bash
git add src/cams_client.py tests/test_cams_client.py
git commit -m "feat: add CAMS AOD client via Open-Meteo Air Quality API"
```

---

### Task 3: JPL Horizons 彗星クライアント

**Files:**
- Create: `src/horizons_client.py`
- Create: `tests/test_horizons_client.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_horizons_client.py` を新規作成:

```python
from unittest.mock import MagicMock, patch
from horizons_client import fetch_visible_comets, _parse_ephemeris, CometInfo

SAMPLE_HORIZONS_TEXT = """
*******************************************************************************
 Revised: ...
*******************************************************************************
$$SOE
2026-May-09 12:00 *  10 30 00.00  +20 00 00.0  5.5
2026-May-09 21:00 *  10 30 00.00  +20 00 00.0  5.5
2026-May-09 22:00 *  10 30 00.00  +20 00 00.0  5.5
2026-May-09 23:00 *  10 30 00.00  +20 00 00.0  5.5
$$EOE
*******************************************************************************
"""

SAMPLE_HORIZONS_TEXT_NO_COMET = """
$$SOE
$$EOE
"""

SAMPLE_HORIZONS_TEXT_FAINT = """
$$SOE
2026-May-09 21:00 *  10 30 00.00  +20 00 00.0  11.0
$$EOE
"""


def test_parse_ephemeris_returns_rows():
    rows = _parse_ephemeris(SAMPLE_HORIZONS_TEXT)
    assert len(rows) == 4


def test_parse_ephemeris_correct_magnitude():
    rows = _parse_ephemeris(SAMPLE_HORIZONS_TEXT)
    _, _, _, mag = rows[0]
    assert mag == 5.5


def test_parse_ephemeris_empty_on_no_data():
    rows = _parse_ephemeris(SAMPLE_HORIZONS_TEXT_NO_COMET)
    assert rows == []


def test_fetch_visible_comets_returns_list():
    mock = MagicMock()
    mock.text = SAMPLE_HORIZONS_TEXT
    mock.raise_for_status.return_value = None
    with patch("horizons_client.requests.get", return_value=mock):
        result = fetch_visible_comets(32.8022, 130.7081, "2026-05-09")
    assert isinstance(result, list)


def test_fetch_visible_comets_filters_faint():
    mock = MagicMock()
    mock.text = SAMPLE_HORIZONS_TEXT_FAINT
    mock.raise_for_status.return_value = None
    with patch("horizons_client.requests.get", return_value=mock):
        result = fetch_visible_comets(32.8022, 130.7081, "2026-05-09")
    assert result == []


def test_fetch_visible_comets_returns_empty_on_exception():
    with patch("horizons_client.requests.get", side_effect=Exception("timeout")):
        result = fetch_visible_comets(32.8022, 130.7081, "2026-05-09")
    assert result == []


def test_fetch_visible_comets_returns_empty_when_no_ephemeris():
    mock = MagicMock()
    mock.text = "No ephemeris for target"
    mock.raise_for_status.return_value = None
    with patch("horizons_client.requests.get", return_value=mock):
        result = fetch_visible_comets(32.8022, 130.7081, "2026-05-09")
    assert result == []
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
cd /home/kaede/stargazing-line-bot/.claude/worktrees/xenodochial-elbakyan-e26b16
python -m pytest tests/test_horizons_client.py -v 2>&1 | head -20
```

期待: `ModuleNotFoundError: No module named 'horizons_client'`

- [ ] **Step 3: 実装を書く**

`src/horizons_client.py` を新規作成:

```python
import re
import requests
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from skyfield.api import Loader, Star, wgs84

_loader = Loader("/app/skyfield-data")
_ts = _loader.timescale(builtin=True)
_eph = _loader("de421.bsp")

JST = timezone(timedelta(hours=9))

KNOWN_COMETS = [
    "C/2025 E3",
    "C/2023 A3",
    "12P/Pons-Brooks",
    "C/2024 G3",
    "C/2021 S3",
]


@dataclass
class CometInfo:
    name: str
    best_time: str   # JST "HH:MM"
    altitude: float  # 度
    magnitude: float


def fetch_visible_comets(lat: float, lon: float, date_jst: str) -> list[CometInfo]:
    result = []
    for comet_id in KNOWN_COMETS:
        info = _query_comet(comet_id, lat, lon, date_jst)
        if info is not None:
            result.append(info)
    return result


def _query_comet(comet_id: str, lat: float, lon: float, date_jst: str) -> CometInfo | None:
    date_obj = date.fromisoformat(date_jst)
    tomorrow = date_obj + timedelta(days=1)
    url = "https://ssd.jpl.nasa.gov/api/horizons.api"
    params = {
        "format": "text",
        "COMMAND": f"'DES={comet_id};'",
        "OBJ_DATA": "NO",
        "MAKE_EPHEM": "YES",
        "EPHEM_TYPE": "OBSERVER",
        "CENTER": "coord@399",
        "SITE_COORD": f"'{lon},{lat},0'",
        "START_TIME": f"'{date_obj} 12:00'",
        "STOP_TIME": f"'{tomorrow} 16:00'",
        "STEP_SIZE": "1 h",
        "QUANTITIES": "2,9",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        text = resp.text
    except Exception:
        return None

    if "No ephemeris" in text or "Cannot find" in text:
        return None

    rows = _parse_ephemeris(text)
    if not rows:
        return None

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
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
cd /home/kaede/stargazing-line-bot/.claude/worktrees/xenodochial-elbakyan-e26b16
python -m pytest tests/test_horizons_client.py -v
```

期待: 7件 PASSED

- [ ] **Step 5: コミット**

```bash
git add src/horizons_client.py tests/test_horizons_client.py
git commit -m "feat: add JPL Horizons comet visibility client"
```

---

### Task 4: `calculate_hourly_score` に AOD・PM2.5 ペナルティを追加

**Files:**
- Modify: `src/notify.py`（`calculate_hourly_score` 関数）
- Modify: `tests/test_notify.py`（新パラメータのテスト追加）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_notify.py` の `# --- calculate_hourly_score ---` セクション末尾（`test_calculate_hourly_score_weather_penalty_minimum_score` の後）に以下を追加:

```python
def test_calculate_hourly_score_aod_penalty():
    # AOD > 0.4 でスコアが1減る
    assert calculate_hourly_score(10, 20000, 1, 1, aod=0.5) == 4

def test_calculate_hourly_score_aod_no_penalty_below_threshold():
    # AOD <= 0.4 はペナルティなし
    assert calculate_hourly_score(10, 20000, 1, 1, aod=0.4) == 5

def test_calculate_hourly_score_pm25_light_penalty():
    # PM2.5 > 35 かつ <= 75 で -1
    assert calculate_hourly_score(10, 20000, 1, 1, pm25=50.0) == 4

def test_calculate_hourly_score_pm25_heavy_penalty():
    # PM2.5 > 75 で -2
    assert calculate_hourly_score(10, 20000, 1, 1, pm25=80.0) == 3

def test_calculate_hourly_score_pm25_no_penalty_below_threshold():
    # PM2.5 <= 35 はペナルティなし
    assert calculate_hourly_score(10, 20000, 1, 1, pm25=35.0) == 5

def test_calculate_hourly_score_aod_and_pm25_combined():
    # AOD > 0.4 かつ PM2.5 > 35 で合計 -2
    assert calculate_hourly_score(10, 20000, 1, 1, aod=0.5, pm25=50.0) == 3

def test_calculate_hourly_score_none_aod_no_change():
    # aod=None はペナルティなし（デフォルト動作）
    assert calculate_hourly_score(10, 20000, 1, 1, aod=None) == 5

def test_calculate_hourly_score_none_pm25_no_change():
    # pm25=None はペナルティなし（デフォルト動作）
    assert calculate_hourly_score(10, 20000, 1, 1, pm25=None) == 5

def test_calculate_hourly_score_penalty_minimum_is_1_with_aod_pm25():
    # すべてのペナルティを重ねても最低1
    assert calculate_hourly_score(100, 0, 8, 8, weather_penalty=-5, aod=0.9, pm25=100.0) >= 1
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
cd /home/kaede/stargazing-line-bot/.claude/worktrees/xenodochial-elbakyan-e26b16
python -m pytest tests/test_notify.py::test_calculate_hourly_score_aod_penalty -v
```

期待: FAIL（`calculate_hourly_score` が `aod` 引数を受け付けない）

- [ ] **Step 3: `src/notify.py` の `calculate_hourly_score` を変更する**

現在のシグネチャ:
```python
def calculate_hourly_score(
    cloud_cover, visibility, seeing, transparency, weather_penalty=0
) -> int:
```

変更後のシグネチャとペナルティロジック追加:
```python
def calculate_hourly_score(
    cloud_cover, visibility, seeing, transparency,
    weather_penalty=0, aod=None, pm25=None
) -> int:
```

既存の `score = max(1, score + weather_penalty)` の直前に以下を挿入:
```python
    if aod is not None and aod > 0.4:
        score -= 1
    if pm25 is not None and pm25 > 75:
        score -= 2
    elif pm25 is not None and pm25 > 35:
        score -= 1
```

`score = max(1, score + weather_penalty)` は変更なし（AOD/PM25 ペナルティも max で保護される）。

正確な変更箇所の確認: `src/notify.py` の `calculate_hourly_score` 関数末尾付近を読んで、`weather_penalty` の行を特定してから編集する。

- [ ] **Step 4: テストが通ることを確認する**

```bash
cd /home/kaede/stargazing-line-bot/.claude/worktrees/xenodochial-elbakyan-e26b16
python -m pytest tests/test_notify.py -v -k "calculate_hourly_score"
```

期待: 全 `calculate_hourly_score` テスト PASSED

- [ ] **Step 5: コミット**

```bash
git add src/notify.py tests/test_notify.py
git commit -m "feat: add AOD/PM2.5 score penalty to calculate_hourly_score"
```

---

### Task 5: `format_message` と `main()` に新クライアントを統合

**Files:**
- Modify: `src/notify.py`（`format_message`・`main`）
- Modify: `tests/test_notify.py`（`format_message` テスト追加・`main()` テストのパッチ追加）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_notify.py` に以下を追加（`# --- format_message ---` セクション末尾）:

```python
from horizons_client import CometInfo

SAMPLE_COMETS = [CometInfo(name="C/2025 E3", best_time="22:00", altitude=28.5, magnitude=6.2)]

def test_format_message_shows_comet_info():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [], comets=SAMPLE_COMETS)
    assert "C/2025 E3" in msg
    assert "22:00" in msg

def test_format_message_no_comets_no_comet_line():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [], comets=[])
    assert "が見頃" not in msg

def test_format_message_shows_pm25():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [], pm25=12.0)
    assert "PM2.5" in msg
    assert "12" in msg

def test_format_message_shows_aod():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [], aod=0.15)
    assert "AOD" in msg
    assert "0.15" in msg

def test_format_message_omits_pm25_when_none():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [], pm25=None)
    assert "PM2.5" not in msg

def test_format_message_omits_aod_when_none():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [], aod=None)
    assert "AOD" not in msg
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
cd /home/kaede/stargazing-line-bot/.claude/worktrees/xenodochial-elbakyan-e26b16
python -m pytest tests/test_notify.py::test_format_message_shows_comet_info -v
```

期待: FAIL（`format_message` が `comets` 引数を受け付けない）

- [ ] **Step 3: `src/notify.py` の `format_message` シグネチャを変更する**

現在:
```python
def format_message(
    conditions, astro_data, moon_age, twilight_time, planets, meteor_showers, constellations,
    weather_penalties=None
) -> str:
```

変更後（末尾に追加）:
```python
def format_message(
    conditions, astro_data, moon_age, twilight_time, planets, meteor_showers, constellations,
    weather_penalties=None, comets=None, aod=None, pm25=None
) -> str:
```

- [ ] **Step 4: `format_message` の湿度行に PM2.5・AOD 表示を追加する**

`src/notify.py` の湿度・風速行の出力箇所を探して変更する。現在の出力（湿度+風速）の後に追記:

```python
# 湿度行の文字列構築箇所（既存コードを参考に）
humidity_line = f"💧 湿度: {conditions.humidity}%　🌬 風速: {conditions.wind_speed}m/s"
if pm25 is not None:
    humidity_line += f"　🏭 PM2.5: {pm25:.0f}μg/m³"
if aod is not None:
    humidity_line += f"　🌫 AOD: {aod}"
```

実際の変更は `src/notify.py` の該当行を Read して確認してから行う。

- [ ] **Step 5: `format_message` の「今夜のポイント」に彗星を追加する**

「今夜のポイント」セクションを構築する箇所に彗星の追記を追加:

```python
if comets:
    for comet in comets:
        points.append(
            f"・{comet.name} が見頃 {comet.best_time}（高度 {comet.altitude}°, 等級 {comet.magnitude}）"
        )
```

実際の変更は `src/notify.py` の該当セクションを Read して確認してから行う。

- [ ] **Step 6: `format_message` テストが通ることを確認する**

```bash
cd /home/kaede/stargazing-line-bot/.claude/worktrees/xenodochial-elbakyan-e26b16
python -m pytest tests/test_notify.py -v -k "format_message"
```

期待: 全 `format_message` テスト PASSED

- [ ] **Step 7: `main()` に3クライアント呼び出しを追加する**

`src/notify.py` の `main()` 関数に以下を追加（既存の `fetch_sky_conditions` 等の呼び出し群と同じパターン）:

```python
from cams_client import fetch_aod
from openaq_client import fetch_pm25
from horizons_client import fetch_visible_comets, CometInfo

# main() 内、format_message 呼び出し前:
try:
    aod = fetch_aod(cfg.LOCATION_LAT, cfg.LOCATION_LON)
except Exception:
    aod = None

try:
    pm25 = fetch_pm25(cfg.LOCATION_LAT, cfg.LOCATION_LON)
except Exception:
    pm25 = None

try:
    comets = fetch_visible_comets(cfg.LOCATION_LAT, cfg.LOCATION_LON, today_jst.isoformat())
except Exception:
    comets = []
```

`format_message` と `calculate_hourly_score` の呼び出しに `aod`・`pm25`・`comets` を渡す。

- [ ] **Step 8: `main()` の既存テストを更新する**

`test_main_happy_path`・`test_main_7timer_failure_still_sends`・`test_main_constellation_failure_still_sends` の各テストに、以下の3つのパッチを追加:

```python
@patch("notify.fetch_visible_comets")
@patch("notify.fetch_pm25")
@patch("notify.fetch_aod")
```

各テスト関数の引数リストの先頭（`mock_config` の前）に `mock_fetch_aod, mock_fetch_pm25, mock_fetch_comets` を追加し、本体で:

```python
mock_fetch_aod.return_value = None
mock_fetch_pm25.return_value = None
mock_fetch_comets.return_value = []
```

を設定する。

`test_main_weather_error_sends_error_notification` は `fetch_sky_conditions` が例外を投げて早期リターンするため変更不要。

- [ ] **Step 9: 全テストが通ることを確認する**

```bash
cd /home/kaede/stargazing-line-bot/.claude/worktrees/xenodochial-elbakyan-e26b16
python -m pytest tests/ -v
```

期待: 全テスト PASSED

- [ ] **Step 10: コミット**

```bash
git add src/notify.py tests/test_notify.py
git commit -m "feat: integrate CAMS/OpenAQ/Horizons into format_message and main"
```
