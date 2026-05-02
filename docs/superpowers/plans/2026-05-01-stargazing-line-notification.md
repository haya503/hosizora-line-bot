# 星空予報 LINE通知システム 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GitHub Actions で毎日 18:00 JST に固定地点の星空予報（気象条件＋天文イベント）を LINE Messaging API でプッシュ通知する。

**Architecture:** Open-Meteo で気象データ取得 → skyfield でローカル天文計算（月齢・惑星・流星群）→ LINE Messaging API で送信。すべてのシークレットは GitHub Secrets で管理し、コードにハードコードしない。

**Tech Stack:** Python 3.12, skyfield 1.49, requests 2.32.3, python-dotenv 1.0.1, pytest 8.x, GitHub Actions

---

## File Map

| ファイル | 役割 |
|---------|------|
| `requirements.txt` | 依存パッケージ |
| `pytest.ini` | pytest 設定（pythonpath = src） |
| `.gitignore` | .env・キャッシュ・bspファイル除外 |
| `.env.example` | 環境変数テンプレート |
| `src/config.py` | 環境変数から設定を読み込む `load()` 関数 |
| `src/sky_forecast.py` | Open-Meteo API から気象データ取得・`SkyConditions` dataclass |
| `src/astro_events.py` | 月齢・惑星南中・流星群を計算する純関数群 + `get_astro_data()` |
| `src/line_client.py` | LINE Messaging API Push Message 送信 |
| `src/notify.py` | スコア計算・メッセージ整形・メインオーケストレーション |
| `.github/workflows/notify.yml` | cron スケジュール + workflow_dispatch |
| `tests/test_config.py` | config.load() のテスト |
| `tests/test_sky_forecast.py` | HTTP モックで fetch_sky_conditions のテスト |
| `tests/test_astro_events.py` | 純関数（月齢・流星群）のテスト |
| `tests/test_line_client.py` | HTTP モックで send_message のテスト |
| `tests/test_notify.py` | スコア・フォーマット・main() のテスト |

---

### Task 1: プロジェクトスキャフォルド

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `.gitignore`
- Create: `.env.example`

- [ ] **Step 1: requirements.txt を作成**

```
requests==2.32.3
skyfield==1.49
python-dotenv==1.0.1
pytest==8.3.5
```

- [ ] **Step 2: pytest.ini を作成**

```ini
[pytest]
pythonpath = src
testpaths = tests
```

- [ ] **Step 3: .gitignore を作成**

```
.env
__pycache__/
*.pyc
.pytest_cache/
/tmp/skyfield-data/
*.bsp
```

- [ ] **Step 4: .env.example を作成**

```
LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token_here
LINE_USER_ID=your_line_user_id_here
LOCATION_LAT=35.6762
LOCATION_LON=139.6503
```

- [ ] **Step 5: src/ と tests/ ディレクトリを作成**

```bash
mkdir -p src tests
touch src/__init__.py tests/__init__.py
```

- [ ] **Step 6: 依存パッケージをインストール**

```bash
pip install -r requirements.txt
```

Expected: skyfield, requests, python-dotenv, pytest がインストールされる

- [ ] **Step 7: コミット**

```bash
git add requirements.txt pytest.ini .gitignore .env.example src/__init__.py tests/__init__.py
git commit -m "chore: プロジェクトスキャフォルドを追加"
```

---

### Task 2: src/config.py

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: テストを書く**

`tests/test_config.py`:
```python
import pytest


def test_config_load_returns_all_fields(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "mytoken")
    monkeypatch.setenv("LINE_USER_ID", "myuserid")
    monkeypatch.setenv("LOCATION_LAT", "34.6937")
    monkeypatch.setenv("LOCATION_LON", "135.5023")

    import config
    cfg = config.load()

    assert cfg.LINE_CHANNEL_ACCESS_TOKEN == "mytoken"
    assert cfg.LINE_USER_ID == "myuserid"
    assert cfg.LOCATION_LAT == pytest.approx(34.6937)
    assert cfg.LOCATION_LON == pytest.approx(135.5023)


def test_config_load_raises_on_missing_env(monkeypatch):
    for key in ["LINE_CHANNEL_ACCESS_TOKEN", "LINE_USER_ID", "LOCATION_LAT", "LOCATION_LON"]:
        monkeypatch.delenv(key, raising=False)

    import config
    with pytest.raises(KeyError):
        config.load()
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: src/config.py を実装**

```python
import os
from types import SimpleNamespace
from dotenv import load_dotenv


def load() -> SimpleNamespace:
    load_dotenv()
    return SimpleNamespace(
        LINE_CHANNEL_ACCESS_TOKEN=os.environ["LINE_CHANNEL_ACCESS_TOKEN"],
        LINE_USER_ID=os.environ["LINE_USER_ID"],
        LOCATION_LAT=float(os.environ["LOCATION_LAT"]),
        LOCATION_LON=float(os.environ["LOCATION_LON"]),
    )
```

- [ ] **Step 4: テストが通ることを確認**

```bash
pytest tests/test_config.py -v
```

Expected: 2 passed

- [ ] **Step 5: コミット**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: 環境変数から設定を読み込む config.load() を追加"
```

---

### Task 3: src/sky_forecast.py

**Files:**
- Create: `src/sky_forecast.py`
- Create: `tests/test_sky_forecast.py`

- [ ] **Step 1: テストを書く**

`tests/test_sky_forecast.py`:
```python
import pytest
from unittest.mock import MagicMock, patch
import requests
from sky_forecast import fetch_sky_conditions, SkyConditions

MOCK_RESPONSE = {
    "hourly": {
        "time": [f"2026-05-01T{h:02d}:00" for h in range(24)],
        "cloud_cover": [10] * 24,
        "visibility": [20000] * 24,
        "relative_humidity_2m": [50] * 24,
        "wind_speed_10m": [3.0] * 24,
    }
}


def make_mock_resp(data=None):
    m = MagicMock()
    m.json.return_value = data or MOCK_RESPONSE
    m.raise_for_status.return_value = None
    return m


def test_fetch_returns_sky_conditions():
    with patch("sky_forecast.requests.get", return_value=make_mock_resp()):
        result = fetch_sky_conditions(35.0, 135.0)
    assert isinstance(result, SkyConditions)
    assert result.cloud_cover == 10
    assert result.visibility == 20000
    assert result.humidity == 50
    assert result.wind_speed == 3.0


def test_fetch_averages_evening_hours_only():
    # 昼間 0、夜間18-23は60にして夜間平均だけ取れることを確認
    data = {
        "hourly": {
            "time": MOCK_RESPONSE["hourly"]["time"],
            "cloud_cover": [0] * 18 + [60] * 6,
            "visibility": [20000] * 24,
            "relative_humidity_2m": [50] * 24,
            "wind_speed_10m": [3.0] * 24,
        }
    }
    with patch("sky_forecast.requests.get", return_value=make_mock_resp(data)):
        result = fetch_sky_conditions(35.0, 135.0)
    assert result.cloud_cover == 60


def test_fetch_retries_once_on_failure():
    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise requests.RequestException("timeout")
        return make_mock_resp()

    with patch("sky_forecast.requests.get", side_effect=side_effect):
        result = fetch_sky_conditions(35.0, 135.0)

    assert call_count == 2
    assert result.cloud_cover == 10


def test_fetch_raises_after_two_failures():
    with patch("sky_forecast.requests.get", side_effect=requests.RequestException("error")):
        with pytest.raises(requests.RequestException):
            fetch_sky_conditions(35.0, 135.0)
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
pytest tests/test_sky_forecast.py -v
```

Expected: `ModuleNotFoundError: No module named 'sky_forecast'`

- [ ] **Step 3: src/sky_forecast.py を実装**

```python
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
```

- [ ] **Step 4: テストが通ることを確認**

```bash
pytest tests/test_sky_forecast.py -v
```

Expected: 4 passed

- [ ] **Step 5: コミット**

```bash
git add src/sky_forecast.py tests/test_sky_forecast.py
git commit -m "feat: Open-Meteo から夜間の気象データを取得する sky_forecast を追加"
```

---

### Task 4: src/astro_events.py

**Files:**
- Create: `src/astro_events.py`
- Create: `tests/test_astro_events.py`

- [ ] **Step 1: 純関数のテストを書く**

`tests/test_astro_events.py`:
```python
from datetime import date, datetime, timezone
from astro_events import get_moon_age, get_upcoming_meteor_showers


def test_get_moon_age_at_reference_new_moon():
    known_new_moon = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    age = get_moon_age(known_new_moon)
    assert abs(age) < 0.01


def test_get_moon_age_is_in_valid_range():
    now = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    age = get_moon_age(now)
    assert 0 <= age < 29.531


def test_get_upcoming_meteor_showers_on_peak_day():
    result = get_upcoming_meteor_showers(date(2026, 8, 12))
    assert ("ペルセウス座流星群", 0) in result


def test_get_upcoming_meteor_showers_days_before_peak():
    result = get_upcoming_meteor_showers(date(2026, 8, 9))
    assert ("ペルセウス座流星群", 3) in result


def test_get_upcoming_meteor_showers_excludes_after_peak():
    result = get_upcoming_meteor_showers(date(2026, 8, 14))
    names = {name for name, _ in result}
    assert "ペルセウス座流星群" not in names


def test_get_upcoming_meteor_showers_excludes_outside_window():
    result = get_upcoming_meteor_showers(date(2026, 8, 1))
    names = {name for name, _ in result}
    assert "ペルセウス座流星群" not in names
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
pytest tests/test_astro_events.py -v
```

Expected: `ModuleNotFoundError: No module named 'astro_events'`

- [ ] **Step 3: src/astro_events.py を実装**

```python
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
```

- [ ] **Step 4: テストが通ることを確認**

```bash
pytest tests/test_astro_events.py -v
```

Expected: 6 passed

- [ ] **Step 5: コミット**

```bash
git add src/astro_events.py tests/test_astro_events.py
git commit -m "feat: 月齢・惑星・流星群を計算する astro_events を追加"
```

---

### Task 5: src/line_client.py

**Files:**
- Create: `src/line_client.py`
- Create: `tests/test_line_client.py`

- [ ] **Step 1: テストを書く**

`tests/test_line_client.py`:
```python
from unittest.mock import MagicMock, patch
from line_client import send_message


def test_send_message_posts_to_line_api():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None

    with patch("line_client.requests.post", return_value=mock_resp) as mock_post:
        send_message("tok123", "uid456", "テストメッセージ")

    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["to"] == "uid456"
    assert kwargs["json"]["messages"][0]["text"] == "テストメッセージ"
    assert kwargs["headers"]["Authorization"] == "Bearer tok123"
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
pytest tests/test_line_client.py -v
```

Expected: `ModuleNotFoundError: No module named 'line_client'`

- [ ] **Step 3: src/line_client.py を実装**

```python
import requests

_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def send_message(token: str, user_id: str, text: str) -> None:
    resp = requests.post(
        _PUSH_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        json={
            "to": user_id,
            "messages": [{"type": "text", "text": text}],
        },
        timeout=10,
    )
    resp.raise_for_status()
```

- [ ] **Step 4: テストが通ることを確認**

```bash
pytest tests/test_line_client.py -v
```

Expected: 1 passed

- [ ] **Step 5: コミット**

```bash
git add src/line_client.py tests/test_line_client.py
git commit -m "feat: LINE Messaging API へテキスト送信する line_client を追加"
```

---

### Task 6: src/notify.py

**Files:**
- Create: `src/notify.py`
- Create: `tests/test_notify.py`

- [ ] **Step 1: テストを書く**

`tests/test_notify.py`:
```python
from types import SimpleNamespace
from unittest.mock import patch
from sky_forecast import SkyConditions
from astro_events import PlanetInfo
from notify import calculate_score, format_stars, format_message, main

SAMPLE_CONDITIONS = SkyConditions(cloud_cover=10, visibility=20000, humidity=50, wind_speed=3.0)
SAMPLE_PLANETS = [PlanetInfo("木星", "22:30", 58.0)]
FAKE_CFG = SimpleNamespace(
    LINE_CHANNEL_ACCESS_TOKEN="tok",
    LINE_USER_ID="uid",
    LOCATION_LAT=35.0,
    LOCATION_LON=135.0,
)


# --- calculate_score ---

def test_calculate_score_clear_no_moon():
    assert calculate_score(10, 5.0, 20000) == 5

def test_calculate_score_partly_cloudy():
    assert calculate_score(60, 5.0, 20000) == 4

def test_calculate_score_very_cloudy():
    assert calculate_score(85, 5.0, 20000) == 3

def test_calculate_score_full_moon():
    assert calculate_score(10, 15.0, 20000) == 4

def test_calculate_score_low_visibility():
    assert calculate_score(10, 5.0, 5000) == 4

def test_calculate_score_worst_case():
    assert calculate_score(90, 15.0, 5000) == 2

def test_calculate_score_minimum_is_1():
    # 減点が重なっても最低1
    assert calculate_score(100, 15.0, 0) >= 1


# --- format_stars ---

def test_format_stars_full():
    assert format_stars(5) == "★★★★★"

def test_format_stars_partial():
    assert format_stars(3) == "★★★☆☆"

def test_format_stars_one():
    assert format_stars(1) == "★☆☆☆☆"


# --- format_message ---

def test_format_message_contains_key_info():
    msg = format_message(SAMPLE_CONDITIONS, 5.0, "21:00", SAMPLE_PLANETS, [])
    assert "今夜の星空予報" in msg
    assert "雲量: 10%" in msg
    assert "月の出: 21:00" in msg
    assert "木星が南中 22:30" in msg
    assert "★" in msg

def test_format_message_no_events_shows_placeholder():
    msg = format_message(SAMPLE_CONDITIONS, 5.0, None, [], [])
    assert "特になし" in msg

def test_format_message_meteor_shower_peak():
    msg = format_message(SAMPLE_CONDITIONS, 5.0, None, [], [("ペルセウス座流星群", 0)])
    assert "本日がピーク" in msg

def test_format_message_meteor_shower_upcoming():
    msg = format_message(SAMPLE_CONDITIONS, 5.0, None, [], [("ペルセウス座流星群", 3)])
    assert "あと3日" in msg


# --- main() ---

@patch("notify.send_message")
@patch("notify.get_astro_data")
@patch("notify.fetch_sky_conditions")
@patch("notify.config")
def test_main_happy_path(mock_config, mock_fetch, mock_astro, mock_send):
    mock_config.load.return_value = FAKE_CFG
    mock_fetch.return_value = SAMPLE_CONDITIONS
    mock_astro.return_value = (5.0, "21:00", SAMPLE_PLANETS, [])

    main()

    mock_send.assert_called_once()
    text = mock_send.call_args[0][2]
    assert "今夜の星空予報" in text


@patch("notify.send_message")
@patch("notify.fetch_sky_conditions")
@patch("notify.config")
def test_main_weather_error_sends_error_notification(mock_config, mock_fetch, mock_send):
    mock_config.load.return_value = FAKE_CFG
    mock_fetch.side_effect = Exception("connection timeout")

    main()

    mock_send.assert_called_once()
    text = mock_send.call_args[0][2]
    assert "気象データ取得失敗" in text
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
pytest tests/test_notify.py -v
```

Expected: `ModuleNotFoundError: No module named 'notify'`

- [ ] **Step 3: src/notify.py を実装**

```python
import sys
from datetime import datetime, timezone
from typing import Optional
import config
from sky_forecast import fetch_sky_conditions, SkyConditions
from astro_events import get_astro_data, PlanetInfo
from line_client import send_message


def calculate_score(cloud_cover: int, moon_age: float, visibility: int) -> int:
    score = 5
    if cloud_cover > 80:
        score -= 2
    elif cloud_cover > 50:
        score -= 1
    if 10 <= moon_age <= 20:
        score -= 1
    if visibility < 10000:
        score -= 1
    return max(1, score)


def format_stars(score: int) -> str:
    return "★" * score + "☆" * (5 - score)


def format_message(
    conditions: SkyConditions,
    moon_age: float,
    moonrise: Optional[str],
    planets: list[PlanetInfo],
    meteor_showers: list[tuple[str, int]],
) -> str:
    score = calculate_score(conditions.cloud_cover, moon_age, conditions.visibility)
    moon_str = f"月齢: {moon_age:.0f}"
    if moonrise:
        moon_str += f"（月の出: {moonrise}）"

    event_lines = []
    for p in planets:
        if p.transit_time:
            event_lines.append(f"・{p.name}が南中 {p.transit_time}（高度 {p.max_altitude}°）")
    for name, days in meteor_showers:
        if days == 0:
            event_lines.append(f"・{name} 本日がピーク！")
        else:
            event_lines.append(f"・{name}まであと{days}日")
    if not event_lines:
        event_lines.append("・特になし")

    return "\n".join([
        "🌙 今夜の星空予報",
        "",
        f"☁️ 雲量: {conditions.cloud_cover}%",
        f"💧 湿度: {conditions.humidity}%　🌬 風速: {conditions.wind_speed}m/s",
        f"🌙 {moon_str}",
        "",
        "🔭 今夜のポイント:",
        *event_lines,
        "",
        f"総合評価: {format_stars(score)}",
    ])


def main() -> None:
    cfg = config.load()
    now_utc = datetime.now(timezone.utc)
    sky_error = None

    try:
        conditions = fetch_sky_conditions(cfg.LOCATION_LAT, cfg.LOCATION_LON)
    except Exception as e:
        sky_error = e

    if sky_error is not None:
        send_message(cfg.LINE_CHANNEL_ACCESS_TOKEN, cfg.LINE_USER_ID, f"⚠️ 気象データ取得失敗: {sky_error}")
        return

    moon_age, moonrise, planets, meteor_showers = get_astro_data(
        cfg.LOCATION_LAT, cfg.LOCATION_LON, now_utc
    )
    message = format_message(conditions, moon_age, moonrise, planets, meteor_showers)
    send_message(cfg.LINE_CHANNEL_ACCESS_TOKEN, cfg.LINE_USER_ID, message)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: テストが通ることを確認**

```bash
pytest tests/test_notify.py -v
```

Expected: 15 passed

- [ ] **Step 5: 全テストを実行**

```bash
pytest -v
```

Expected: 全テスト passed（test_config + test_sky_forecast + test_astro_events + test_line_client + test_notify）

- [ ] **Step 6: コミット**

```bash
git add src/notify.py tests/test_notify.py
git commit -m "feat: スコア計算・メッセージ整形・メインオーケストレーションを実装"
```

---

### Task 7: GitHub Actions ワークフロー

**Files:**
- Create: `.github/workflows/notify.yml`

- [ ] **Step 1: ワークフローディレクトリを作成**

```bash
mkdir -p .github/workflows
```

- [ ] **Step 2: .github/workflows/notify.yml を作成**

```yaml
name: 星空予報 LINE通知

on:
  schedule:
    - cron: '0 9 * * *'  # 18:00 JST (UTC+9)
  workflow_dispatch:

jobs:
  notify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: skyfield データキャッシュ
        uses: actions/cache@v4
        with:
          path: /tmp/skyfield-data
          key: skyfield-de421

      - name: パッケージをインストール
        run: pip install -r requirements.txt

      - name: 星空予報を送信
        run: python src/notify.py
        env:
          LINE_CHANNEL_ACCESS_TOKEN: ${{ secrets.LINE_CHANNEL_ACCESS_TOKEN }}
          LINE_USER_ID: ${{ secrets.LINE_USER_ID }}
          LOCATION_LAT: ${{ secrets.LOCATION_LAT }}
          LOCATION_LON: ${{ secrets.LOCATION_LON }}
```

- [ ] **Step 3: GitHub Secrets に以下を登録する（手動作業）**

GitHubリポジトリの Settings → Secrets and variables → Actions → New repository secret から4つ追加する：

| Name | Value の例 |
|------|-----------|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Developers から取得したトークン |
| `LINE_USER_ID` | 通知先ユーザーの LINE User ID |
| `LOCATION_LAT` | 観測地点の緯度（例: `35.6762`） |
| `LOCATION_LON` | 観測地点の経度（例: `139.6503`） |

> **LINE User ID の確認方法:** LINE Developers Console → チャネル → Messaging API → Your user ID

- [ ] **Step 4: コミット＆GitHubへプッシュ**

```bash
git add .github/workflows/notify.yml
git commit -m "ci: GitHub Actions の定期通知ワークフローを追加"
git remote add origin https://github.com/<your-username>/stargazing-line-bot.git
git push -u origin master
```

- [ ] **Step 5: workflow_dispatch で手動テスト**

GitHub リポジトリの Actions タブ → 「星空予報 LINE通知」→ Run workflow → Run workflow をクリックする

Expected: ワークフローが緑になり、LINE に通知メッセージが届く

---

## ローカルでの動作確認（任意）

全タスク完了後、ローカルから手動実行する場合：

```bash
cp .env.example .env
# .env に実際の値を記入してから
python src/notify.py
```
