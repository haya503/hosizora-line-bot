# 星空予報 機能改善 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 時間帯別（21〜24時）の星の見えやすさ表示・7timer/星をみるひとAPI統合・LINEグループ通知対応を追加する。

**Architecture:** Open-Meteo（雲量・視程）と7timer ASTRO（シーイング・透明度）の複合スコアで1時間ごとの星5段階評価を算出。星をみるひとAPIで今夜見える星座を追加。LINEの送信先を `LINE_NOTIFY_TARGETS` で複数管理。

**Tech Stack:** Python 3.12, requests, skyfield, LINE Messaging API, Open-Meteo API, 7timer ASTRO API, 星をみるひとAPI, pytest, GitHub Actions

---

## ファイル変更一覧

| ファイル | 種別 | 内容 |
|---------|------|------|
| `src/config.py` | 変更 | `LINE_USER_ID` → `LINE_NOTIFY_TARGETS`（カンマ区切りパース） |
| `src/line_client.py` | 変更 | `send_message` → `send_messages`（複数送信先ループ） |
| `src/sky_forecast.py` | 変更 | `SkyConditions` を時間別構造に変更（21〜24時 + 夜間平均） |
| `src/astro_client.py` | 新規 | 7timer ASTRO API・星をみるひとAPI呼び出し |
| `src/notify.py` | 変更 | `calculate_hourly_score`・`format_message`・`main` 全面更新 |
| `.github/workflows/notify.yml` | 変更 | Secrets名 `LINE_USER_ID` → `LINE_NOTIFY_TARGETS` |
| `tests/test_config.py` | 新規 | config.py テスト |
| `tests/test_line_client.py` | 新規 | line_client.py テスト |
| `tests/test_sky_forecast.py` | 変更 | 時間別構造に対応したテスト更新 |
| `tests/test_astro_client.py` | 新規 | astro_client.py テスト |
| `tests/test_notify.py` | 変更 | 新シグネチャに対応したテスト全面更新 |

---

## Task 1: config.py — LINE_NOTIFY_TARGETS 対応

**Files:**
- Modify: `src/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_config.py` を新規作成：

```python
import pytest
from config import _parse_targets, load


def test_parse_targets_single_user():
    assert _parse_targets("userId:Uabc123") == ["Uabc123"]


def test_parse_targets_multiple():
    assert _parse_targets("userId:Uabc123,groupId:Cdef456") == ["Uabc123", "Cdef456"]


def test_parse_targets_strips_whitespace():
    assert _parse_targets("userId:Uabc123, groupId:Cdef456") == ["Uabc123", "Cdef456"]


def test_load_returns_notify_targets(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("LINE_NOTIFY_TARGETS", "userId:Uabc123")
    monkeypatch.setenv("LOCATION_LAT", "35.0")
    monkeypatch.setenv("LOCATION_LON", "135.0")
    cfg = load()
    assert cfg.LINE_NOTIFY_TARGETS == ["Uabc123"]
    assert cfg.LINE_CHANNEL_ACCESS_TOKEN == "tok"
    assert cfg.LOCATION_LAT == 35.0
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd /home/kaede/stargazing-line-bot && python -m pytest tests/test_config.py -v
```

期待: `ImportError` または `AttributeError`（`_parse_targets` が未定義）

- [ ] **Step 3: config.py を実装**

`src/config.py` を以下で置き換える：

```python
import os
from types import SimpleNamespace
from dotenv import load_dotenv


def _parse_targets(raw: str) -> list[str]:
    result = []
    for item in raw.split(","):
        item = item.strip()
        if ":" in item:
            _, target_id = item.split(":", 1)
            result.append(target_id)
    return result


def load() -> SimpleNamespace:
    load_dotenv()
    return SimpleNamespace(
        LINE_CHANNEL_ACCESS_TOKEN=os.environ["LINE_CHANNEL_ACCESS_TOKEN"],
        LINE_NOTIFY_TARGETS=_parse_targets(os.environ["LINE_NOTIFY_TARGETS"]),
        LOCATION_LAT=float(os.environ["LOCATION_LAT"]),
        LOCATION_LON=float(os.environ["LOCATION_LON"]),
    )
```

- [ ] **Step 4: テストがパスすることを確認**

```bash
cd /home/kaede/stargazing-line-bot && python -m pytest tests/test_config.py -v
```

期待: 4件すべて PASS

- [ ] **Step 5: コミット**

```bash
cd /home/kaede/stargazing-line-bot
git add src/config.py tests/test_config.py
git commit -m "feat: LINE_USER_ID を LINE_NOTIFY_TARGETS に変更し複数送信先をサポート"
```

---

## Task 2: line_client.py — 複数送信先対応

**Files:**
- Modify: `src/line_client.py`
- Create: `tests/test_line_client.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_line_client.py` を新規作成：

```python
import pytest
from unittest.mock import MagicMock, patch
from line_client import send_messages


def _make_ok_resp():
    m = MagicMock()
    m.raise_for_status.return_value = None
    return m


def _make_fail_resp():
    m = MagicMock()
    m.raise_for_status.side_effect = Exception("403 Forbidden")
    return m


def test_send_messages_calls_all_targets():
    with patch("line_client.requests.post", return_value=_make_ok_resp()) as mock_post:
        send_messages("tok", ["Uabc", "Cdef"], "hello")
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[0][1]["json"]["to"] == "Uabc"
    assert mock_post.call_args_list[1][1]["json"]["to"] == "Cdef"


def test_send_messages_uses_correct_auth_header():
    with patch("line_client.requests.post", return_value=_make_ok_resp()) as mock_post:
        send_messages("mytoken", ["Uabc"], "hello")
    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer mytoken"


def test_send_messages_continues_on_partial_failure():
    with patch("line_client.requests.post", side_effect=[_make_fail_resp(), _make_ok_resp()]):
        send_messages("tok", ["Ufail", "Uok"], "hello")


def test_send_messages_raises_when_all_fail():
    with patch("line_client.requests.post", return_value=_make_fail_resp()):
        with pytest.raises(Exception):
            send_messages("tok", ["Ufail"], "hello")
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd /home/kaede/stargazing-line-bot && python -m pytest tests/test_line_client.py -v
```

期待: `ImportError`（`send_messages` が未定義）

- [ ] **Step 3: line_client.py を実装**

`src/line_client.py` を以下で置き換える：

```python
import sys
import requests

_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def send_messages(token: str, targets: list[str], text: str) -> None:
    failures: list[tuple[str, Exception]] = []
    for target in targets:
        try:
            resp = requests.post(
                _PUSH_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                json={"to": target, "messages": [{"type": "text", "text": text}]},
                timeout=10,
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"LINE send failed for {target}: {e}", file=sys.stderr)
            failures.append((target, e))
    if failures and len(failures) == len(targets):
        raise failures[0][1]
```

- [ ] **Step 4: テストがパスすることを確認**

```bash
cd /home/kaede/stargazing-line-bot && python -m pytest tests/test_line_client.py -v
```

期待: 4件すべて PASS

- [ ] **Step 5: コミット**

```bash
cd /home/kaede/stargazing-line-bot
git add src/line_client.py tests/test_line_client.py
git commit -m "feat: send_message を send_messages に変更し複数送信先をサポート"
```

---

## Task 3: sky_forecast.py — 時間別データ追加

**Files:**
- Modify: `src/sky_forecast.py`
- Modify: `tests/test_sky_forecast.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_sky_forecast.py` を以下で**完全に置き換える**：

```python
from datetime import date
from unittest.mock import MagicMock, patch
import pytest
import requests
from sky_forecast import fetch_sky_conditions, SkyConditions, HourlySkyReading

TODAY = date(2026, 5, 2)
TOMORROW = date(2026, 5, 3)

def _make_mock_response(cloud_values=None, vis_values=None):
    times = (
        [f"{TODAY}T{h:02d}:00" for h in range(24)]
        + [f"{TOMORROW}T{h:02d}:00" for h in range(24)]
    )
    cloud = cloud_values or [10] * 48
    vis = vis_values or [20000] * 48
    m = MagicMock()
    m.json.return_value = {
        "hourly": {
            "time": times,
            "cloud_cover": cloud,
            "visibility": vis,
            "relative_humidity_2m": [50] * 48,
            "wind_speed_10m": [3.0] * 48,
        }
    }
    m.raise_for_status.return_value = None
    return m


def test_fetch_returns_sky_conditions():
    with patch("sky_forecast.requests.get", return_value=_make_mock_response()):
        result = fetch_sky_conditions(35.0, 135.0, TODAY)
    assert isinstance(result, SkyConditions)
    assert result.humidity == 50
    assert result.wind_speed == 3.0


def test_fetch_returns_4_hourly_readings():
    with patch("sky_forecast.requests.get", return_value=_make_mock_response()):
        result = fetch_sky_conditions(35.0, 135.0, TODAY)
    assert len(result.hourly) == 4
    hours = [r.hour for r in result.hourly]
    assert hours == [21, 22, 23, 24]


def test_fetch_hourly_reading_has_correct_values():
    with patch("sky_forecast.requests.get", return_value=_make_mock_response()):
        result = fetch_sky_conditions(35.0, 135.0, TODAY)
    r21 = result.hourly[0]
    assert r21.hour == 21
    assert r21.cloud_cover == 10
    assert r21.visibility == 20000


def test_fetch_24h_reads_tomorrows_midnight():
    # 24時は翌日T00:00 = tomorrow T00:00
    cloud = [10] * 48
    cloud[24] = 90  # tomorrow T00:00 = index 24
    with patch("sky_forecast.requests.get", return_value=_make_mock_response(cloud_values=cloud)):
        result = fetch_sky_conditions(35.0, 135.0, TODAY)
    r24 = result.hourly[3]
    assert r24.hour == 24
    assert r24.cloud_cover == 90


def test_fetch_humidity_is_evening_average():
    # 昼間0%、夕方18-23時は60%にして夜間平均だけ取れることを確認
    humidity = [0] * 18 + [60] * 6 + [0] * 24
    m = MagicMock()
    times = [f"{TODAY}T{h:02d}:00" for h in range(24)] + [f"{TOMORROW}T{h:02d}:00" for h in range(24)]
    m.json.return_value = {
        "hourly": {
            "time": times,
            "cloud_cover": [10] * 48,
            "visibility": [20000] * 48,
            "relative_humidity_2m": humidity + [0] * 24,
            "wind_speed_10m": [3.0] * 48,
        }
    }
    m.raise_for_status.return_value = None
    with patch("sky_forecast.requests.get", return_value=m):
        result = fetch_sky_conditions(35.0, 135.0, TODAY)
    assert result.humidity == 60


def test_fetch_retries_on_error():
    ok = _make_mock_response()
    fail = MagicMock()
    fail.raise_for_status.side_effect = requests.RequestException("timeout")
    with patch("sky_forecast.requests.get", side_effect=[fail, ok]):
        result = fetch_sky_conditions(35.0, 135.0, TODAY)
    assert isinstance(result, SkyConditions)


def test_fetch_raises_after_two_failures():
    fail = MagicMock()
    fail.raise_for_status.side_effect = requests.RequestException("timeout")
    with patch("sky_forecast.requests.get", return_value=fail):
        with pytest.raises(requests.RequestException):
            fetch_sky_conditions(35.0, 135.0, TODAY)
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd /home/kaede/stargazing-line-bot && python -m pytest tests/test_sky_forecast.py -v
```

期待: `ImportError`（`HourlySkyReading` が未定義）または複数 FAIL

- [ ] **Step 3: sky_forecast.py を実装**

`src/sky_forecast.py` を以下で**完全に置き換える**：

```python
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import requests

JST = timezone(timedelta(hours=9))


@dataclass
class HourlySkyReading:
    hour: int        # JST時 (21, 22, 23, 24)
    cloud_cover: int # %
    visibility: int  # m


@dataclass
class SkyConditions:
    humidity: int      # % 夜間(18-23時)平均
    wind_speed: float  # m/s 夜間平均
    hourly: list[HourlySkyReading]  # 21〜24時JST


def fetch_sky_conditions(
    lat: float, lon: float, today_jst: date | None = None
) -> SkyConditions:
    if today_jst is None:
        today_jst = datetime.now(JST).date()
    tomorrow_jst = today_jst + timedelta(days=1)

    target_times = {
        21: f"{today_jst}T21:00",
        22: f"{today_jst}T22:00",
        23: f"{today_jst}T23:00",
        24: f"{tomorrow_jst}T00:00",
    }

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "cloud_cover,visibility,relative_humidity_2m,wind_speed_10m",
        "timezone": "Asia/Tokyo",
        "forecast_days": 2,
    }
    last_exc: Exception | None = None
    for _ in range(2):
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()["hourly"]
            times = data["time"]

            evening_idx = [
                i for i, t in enumerate(times)
                if t.startswith(str(today_jst))
                and any(t.endswith(f"T{h:02d}:00") for h in range(18, 24))
            ]
            avg_humidity = round(
                sum(data["relative_humidity_2m"][i] for i in evening_idx) / len(evening_idx)
            )
            avg_wind = round(
                sum(data["wind_speed_10m"][i] for i in evening_idx) / len(evening_idx), 1
            )

            hourly = []
            for hour, target_time in target_times.items():
                if target_time in times:
                    i = times.index(target_time)
                    hourly.append(HourlySkyReading(
                        hour=hour,
                        cloud_cover=data["cloud_cover"][i],
                        visibility=data["visibility"][i],
                    ))

            return SkyConditions(humidity=avg_humidity, wind_speed=avg_wind, hourly=hourly)
        except requests.RequestException as e:
            last_exc = e
    raise last_exc  # type: ignore[misc]
```

- [ ] **Step 4: テストがパスすることを確認**

```bash
cd /home/kaede/stargazing-line-bot && python -m pytest tests/test_sky_forecast.py -v
```

期待: 7件すべて PASS

- [ ] **Step 5: コミット**

```bash
cd /home/kaede/stargazing-line-bot
git add src/sky_forecast.py tests/test_sky_forecast.py
git commit -m "feat: SkyConditions を21〜24時の時間別データ構造に変更"
```

---

## Task 4: astro_client.py — 7timer ASTRO API + 星をみるひとAPI

**Files:**
- Create: `src/astro_client.py`
- Create: `tests/test_astro_client.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_astro_client.py` を新規作成：

```python
from unittest.mock import MagicMock, patch
import pytest
from astro_client import (
    fetch_7timer_astro,
    fetch_constellations,
    HourlyAstroData,
)

# init=2026050209 → UTC 09:00 = JST 18:00 (通知時刻)
# timepoint 3 = UTC 12:00 = JST 21:00
# timepoint 6 = UTC 15:00 = JST 24:00
MOCK_7TIMER = {
    "init": "2026050209",
    "dataseries": [
        {"timepoint": 3, "seeing": 2, "transparency": 3,
         "cloudcover": 1, "lifted_index": 10, "rh2m": 5,
         "wind10m": {"direction": "N", "speed": 1}, "temp2m": 15, "prec_type": "none"},
        {"timepoint": 6, "seeing": 4, "transparency": 5,
         "cloudcover": 3, "lifted_index": 6, "rh2m": 8,
         "wind10m": {"direction": "S", "speed": 2}, "temp2m": 14, "prec_type": "none"},
        {"timepoint": 9, "seeing": 5, "transparency": 6,
         "cloudcover": 5, "lifted_index": 2, "rh2m": 10,
         "wind10m": {"direction": "W", "speed": 3}, "temp2m": 13, "prec_type": "none"},
    ],
}

MOCK_CONSTELLATION = {
    "result": [
        {"name": "さそり座"},
        {"name": "こと座"},
        {"name": "はくちょう座"},
        {"name": "わし座"},
        {"name": "いて座"},
        {"name": "へびつかい座"},  # 6件 → 5件に切り捨て
    ]
}


def _make_7timer_mock():
    m = MagicMock()
    m.json.return_value = MOCK_7TIMER
    m.raise_for_status.return_value = None
    return m


def _make_const_mock(data=None):
    m = MagicMock()
    m.json.return_value = data or MOCK_CONSTELLATION
    m.raise_for_status.return_value = None
    return m


# --- fetch_7timer_astro ---

def test_fetch_7timer_returns_all_4_hours():
    with patch("astro_client.requests.get", return_value=_make_7timer_mock()):
        result = fetch_7timer_astro(35.0, 135.0)
    assert set(result.keys()) == {21, 22, 23, 24}


def test_fetch_7timer_returns_hourly_astro_data():
    with patch("astro_client.requests.get", return_value=_make_7timer_mock()):
        result = fetch_7timer_astro(35.0, 135.0)
    assert isinstance(result[21], HourlyAstroData)


def test_fetch_7timer_jst21_and_22_map_to_tp3():
    # JST 21/22 → UTC 12/13 → nearest to timepoint 3
    with patch("astro_client.requests.get", return_value=_make_7timer_mock()):
        result = fetch_7timer_astro(35.0, 135.0)
    assert result[21].seeing == 2   # from tp3
    assert result[22].seeing == 2   # same tp3 (nearest)


def test_fetch_7timer_jst23_and_24_map_to_tp6():
    # JST 23/24 → UTC 14/15 → nearest to timepoint 6
    with patch("astro_client.requests.get", return_value=_make_7timer_mock()):
        result = fetch_7timer_astro(35.0, 135.0)
    assert result[23].seeing == 4   # from tp6
    assert result[24].seeing == 4   # same tp6 (nearest)


# --- fetch_constellations ---

def test_fetch_constellations_returns_names():
    with patch("astro_client.requests.get", return_value=_make_const_mock()):
        result = fetch_constellations(35.0, 135.0, "2026-05-02")
    assert "さそり座" in result


def test_fetch_constellations_limits_to_5():
    with patch("astro_client.requests.get", return_value=_make_const_mock()):
        result = fetch_constellations(35.0, 135.0, "2026-05-02")
    assert len(result) == 5


def test_fetch_constellations_empty_result():
    with patch("astro_client.requests.get", return_value=_make_const_mock({"result": []})):
        result = fetch_constellations(35.0, 135.0, "2026-05-02")
    assert result == []
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd /home/kaede/stargazing-line-bot && python -m pytest tests/test_astro_client.py -v
```

期待: `ModuleNotFoundError`（`astro_client` が未定義）

- [ ] **Step 3: astro_client.py を実装**

`src/astro_client.py` を新規作成：

```python
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import requests

JST = timezone(timedelta(hours=9))


@dataclass
class HourlyAstroData:
    seeing: int        # 1-8 (1=最良)
    transparency: int  # 1-8 (1=最良)


def fetch_7timer_astro(lat: float, lon: float) -> dict[int, HourlyAstroData]:
    """JST 21〜24時のシーイング・透明度を返す。keyはJST時(21,22,23,24)。"""
    url = "http://www.7timer.info/bin/astro.php"
    params = {"lon": lon, "lat": lat, "ac": 0, "lang": "en", "output": "json", "tzshift": 0}

    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    init_utc = datetime.strptime(data["init"], "%Y%m%d%H").replace(tzinfo=timezone.utc)
    today_jst = (init_utc + timedelta(hours=9)).date()
    dataseries = data["dataseries"]

    result: dict[int, HourlyAstroData] = {}
    for jst_hour in [21, 22, 23, 24]:
        if jst_hour == 24:
            jst_dt = (
                datetime(today_jst.year, today_jst.month, today_jst.day, 0, tzinfo=JST)
                + timedelta(days=1)
            )
        else:
            jst_dt = datetime(today_jst.year, today_jst.month, today_jst.day, jst_hour, tzinfo=JST)
        target_offset = (jst_dt.astimezone(timezone.utc) - init_utc).total_seconds() / 3600
        nearest = min(dataseries, key=lambda d, t=target_offset: abs(d["timepoint"] - t))
        result[jst_hour] = HourlyAstroData(
            seeing=nearest["seeing"],
            transparency=nearest["transparency"],
        )
    return result


def fetch_constellations(lat: float, lon: float, date_jst: str) -> list[str]:
    """22時JST時点で見える星座名を最大5件返す。"""
    url = "https://livlog.xyz/hoshimiru/constellation"
    params = {"lat": lat, "lng": lon, "date": date_jst, "hour": 22, "min": 0}

    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    items = data.get("result", [])
    names = [item["name"] for item in items if "name" in item]
    return names[:5]
```

- [ ] **Step 4: テストがパスすることを確認**

```bash
cd /home/kaede/stargazing-line-bot && python -m pytest tests/test_astro_client.py -v
```

期待: 8件すべて PASS

- [ ] **Step 5: コミット**

```bash
cd /home/kaede/stargazing-line-bot
git add src/astro_client.py tests/test_astro_client.py
git commit -m "feat: 7timer ASTRO API と星をみるひとAPI を追加"
```

---

## Task 5: notify.py — スコアリング・フォーマット・main 全面更新

**Files:**
- Modify: `src/notify.py`
- Modify: `tests/test_notify.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_notify.py` を以下で**完全に置き換える**：

```python
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from sky_forecast import SkyConditions, HourlySkyReading
from astro_events import PlanetInfo
from astro_client import HourlyAstroData
from notify import calculate_hourly_score, format_stars, format_message, main

_SAMPLE_HOURLY = [
    HourlySkyReading(21, 10, 20000),
    HourlySkyReading(22, 10, 20000),
    HourlySkyReading(23, 10, 20000),
    HourlySkyReading(24, 10, 20000),
]
SAMPLE_CONDITIONS = SkyConditions(humidity=50, wind_speed=3.0, hourly=_SAMPLE_HOURLY)
SAMPLE_ASTRO = {h: HourlyAstroData(1, 1) for h in [21, 22, 23, 24]}
SAMPLE_PLANETS = [PlanetInfo("木星", "22:30", 58.0)]
FAKE_CFG = SimpleNamespace(
    LINE_CHANNEL_ACCESS_TOKEN="tok",
    LINE_NOTIFY_TARGETS=["uid"],
    LOCATION_LAT=35.0,
    LOCATION_LON=135.0,
)


# --- calculate_hourly_score ---

def test_calculate_hourly_score_perfect():
    assert calculate_hourly_score(10, 20000, 1, 1) == 5

def test_calculate_hourly_score_partly_cloudy():
    assert calculate_hourly_score(60, 20000, 1, 1) == 4

def test_calculate_hourly_score_very_cloudy():
    assert calculate_hourly_score(85, 20000, 1, 1) == 3

def test_calculate_hourly_score_low_visibility():
    assert calculate_hourly_score(10, 5000, 1, 1) == 4

def test_calculate_hourly_score_bad_seeing():
    assert calculate_hourly_score(10, 20000, 5, 1) == 4

def test_calculate_hourly_score_bad_transparency():
    assert calculate_hourly_score(10, 20000, 1, 6) == 4

def test_calculate_hourly_score_all_bad():
    assert calculate_hourly_score(85, 5000, 5, 6) == 1

def test_calculate_hourly_score_minimum_is_1():
    assert calculate_hourly_score(100, 0, 8, 8) >= 1

def test_calculate_hourly_score_cloud_penalty_is_exclusive():
    # 雲量>80%は-2だけ（-2と-1が重複しない）
    assert calculate_hourly_score(85, 20000, 1, 1) == 3  # 5-2=3, not 5-3=2


# --- format_stars ---

def test_format_stars_full():
    assert format_stars(5) == "★★★★★"

def test_format_stars_partial():
    assert format_stars(3) == "★★★☆☆"

def test_format_stars_one():
    assert format_stars(1) == "★☆☆☆☆"


# --- format_message ---

def test_format_message_contains_header():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, "21:00", SAMPLE_PLANETS, [], [])
    assert "今夜の星空予報" in msg

def test_format_message_shows_hourly_display():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [])
    assert "21時" in msg
    assert "22時" in msg
    assert "23時" in msg
    assert "24時" in msg

def test_format_message_shows_stars_per_hour():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [])
    assert "★★★★★" in msg  # 全条件良好なら5つ星

def test_format_message_shows_constellations():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], ["さそり座", "こと座"])
    assert "今夜見える星座" in msg
    assert "さそり座" in msg

def test_format_message_no_constellations_skips_section():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [])
    assert "今夜見える星座" not in msg

def test_format_message_shows_planet_info():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, "21:00", SAMPLE_PLANETS, [], [])
    assert "木星が南中 22:30" in msg

def test_format_message_no_events_shows_placeholder():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [])
    assert "特になし" in msg

def test_format_message_meteor_shower_peak():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [("ペルセウス座流星群", 0)], [])
    assert "本日がピーク" in msg

def test_format_message_meteor_shower_upcoming():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [("ペルセウス座流星群", 3)], [])
    assert "あと3日" in msg

def test_format_message_shows_overall_score():
    msg = format_message(SAMPLE_CONDITIONS, SAMPLE_ASTRO, 5.0, None, [], [], [])
    assert "総合評価" in msg

def test_format_message_empty_astro_data_uses_defaults():
    # astro_data が空（7timer失敗時）でもクラッシュしない
    msg = format_message(SAMPLE_CONDITIONS, {}, 5.0, None, [], [], [])
    assert "今夜の星空予報" in msg


# --- main() ---

@patch("notify.send_messages")
@patch("notify.fetch_constellations")
@patch("notify.fetch_7timer_astro")
@patch("notify.get_astro_data")
@patch("notify.fetch_sky_conditions")
@patch("notify.config")
def test_main_happy_path(mock_config, mock_fetch, mock_astro, mock_7timer, mock_const, mock_send):
    mock_config.load.return_value = FAKE_CFG
    mock_fetch.return_value = SAMPLE_CONDITIONS
    mock_astro.return_value = (5.0, "21:00", SAMPLE_PLANETS, [])
    mock_7timer.return_value = SAMPLE_ASTRO
    mock_const.return_value = []

    main()

    mock_send.assert_called_once()
    text = mock_send.call_args[0][2]
    assert "今夜の星空予報" in text


@patch("notify.send_messages")
@patch("notify.fetch_sky_conditions")
@patch("notify.config")
def test_main_weather_error_sends_error_notification(mock_config, mock_fetch, mock_send):
    mock_config.load.return_value = FAKE_CFG
    mock_fetch.side_effect = Exception("connection timeout")

    main()

    mock_send.assert_called_once()
    text = mock_send.call_args[0][2]
    assert "気象データ取得失敗" in text


@patch("notify.send_messages")
@patch("notify.fetch_constellations")
@patch("notify.fetch_7timer_astro")
@patch("notify.get_astro_data")
@patch("notify.fetch_sky_conditions")
@patch("notify.config")
def test_main_7timer_failure_still_sends(mock_config, mock_fetch, mock_astro, mock_7timer, mock_const, mock_send):
    mock_config.load.return_value = FAKE_CFG
    mock_fetch.return_value = SAMPLE_CONDITIONS
    mock_astro.return_value = (5.0, None, [], [])
    mock_7timer.side_effect = Exception("7timer down")
    mock_const.return_value = []

    main()

    mock_send.assert_called_once()
    assert "今夜の星空予報" in mock_send.call_args[0][2]


@patch("notify.send_messages")
@patch("notify.fetch_constellations")
@patch("notify.fetch_7timer_astro")
@patch("notify.get_astro_data")
@patch("notify.fetch_sky_conditions")
@patch("notify.config")
def test_main_constellation_failure_still_sends(mock_config, mock_fetch, mock_astro, mock_7timer, mock_const, mock_send):
    mock_config.load.return_value = FAKE_CFG
    mock_fetch.return_value = SAMPLE_CONDITIONS
    mock_astro.return_value = (5.0, None, [], [])
    mock_7timer.return_value = SAMPLE_ASTRO
    mock_const.side_effect = Exception("constellation API down")

    main()

    mock_send.assert_called_once()
    assert "今夜の星空予報" in mock_send.call_args[0][2]
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd /home/kaede/stargazing-line-bot && python -m pytest tests/test_notify.py -v
```

期待: 複数 FAIL（`calculate_hourly_score` が未定義など）

- [ ] **Step 3: notify.py を実装**

`src/notify.py` を以下で**完全に置き換える**：

```python
from datetime import datetime, timedelta, timezone
from typing import Optional
import config
from sky_forecast import fetch_sky_conditions, SkyConditions, HourlySkyReading
from astro_events import get_astro_data, PlanetInfo
from astro_client import fetch_7timer_astro, fetch_constellations, HourlyAstroData
from line_client import send_messages

JST = timezone(timedelta(hours=9))

_HOURLY_EMOJI = {5: "✨", 4: "😊", 3: "🌤", 2: "⛅", 1: "☁️"}


def calculate_hourly_score(
    cloud_cover: int,
    visibility: int,
    seeing: int,
    transparency: int,
) -> int:
    score = 5
    if cloud_cover > 80:
        score -= 2
    elif cloud_cover > 50:
        score -= 1
    if visibility < 10000:
        score -= 1
    if seeing >= 5:
        score -= 1
    if transparency >= 6:
        score -= 1
    return max(1, score)


def format_stars(score: int) -> str:
    return "★" * score + "☆" * (5 - score)


def format_message(
    conditions: SkyConditions,
    astro_data: dict[int, HourlyAstroData],
    moon_age: float,
    moonrise: Optional[str],
    planets: list[PlanetInfo],
    meteor_showers: list[tuple[str, int]],
    constellations: list[str],
) -> str:
    hourly_lines = []
    scores = []
    for reading in conditions.hourly:
        ad = astro_data.get(reading.hour, HourlyAstroData(seeing=1, transparency=1))
        s = calculate_hourly_score(reading.cloud_cover, reading.visibility, ad.seeing, ad.transparency)
        scores.append(s)
        hour_label = "24時" if reading.hour == 24 else f"{reading.hour}時"
        hourly_lines.append(f"{hour_label} {_HOURLY_EMOJI[s]} {format_stars(s)}")

    overall_score = max(1, round(sum(scores) / len(scores))) if scores else 3

    constellation_section: list[str] = []
    if constellations:
        constellation_section = [
            "",
            "🌌 今夜見える星座:",
            "・" + "、".join(constellations),
        ]

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

    moon_str = f"月齢: {moon_age:.0f}"
    if moonrise:
        moon_str += f"（月の出: {moonrise}）"

    return "\n".join([
        "🌙 今夜の星空予報",
        "",
        "🔭 時間帯別の見えやすさ（21〜24時）",
        *hourly_lines,
        *constellation_section,
        "",
        f"💧 湿度: {conditions.humidity}%　🌬 風速: {conditions.wind_speed}m/s",
        f"🌙 {moon_str}",
        "",
        "🔭 今夜のポイント:",
        *event_lines,
        "",
        f"総合評価: {format_stars(overall_score)}",
    ])


def main() -> None:
    cfg = config.load()
    now_utc = datetime.now(timezone.utc)
    today_jst = now_utc.astimezone(JST).date()
    date_jst_str = today_jst.strftime("%Y-%m-%d")

    try:
        conditions = fetch_sky_conditions(cfg.LOCATION_LAT, cfg.LOCATION_LON, today_jst)
    except Exception as e:
        send_messages(cfg.LINE_CHANNEL_ACCESS_TOKEN, cfg.LINE_NOTIFY_TARGETS, f"⚠️ 気象データ取得失敗: {e}")
        return

    try:
        astro_data = fetch_7timer_astro(cfg.LOCATION_LAT, cfg.LOCATION_LON)
    except Exception:
        astro_data = {}

    try:
        constellations = fetch_constellations(cfg.LOCATION_LAT, cfg.LOCATION_LON, date_jst_str)
    except Exception:
        constellations = []

    moon_age, moonrise, planets, meteor_showers = get_astro_data(
        cfg.LOCATION_LAT, cfg.LOCATION_LON, now_utc
    )
    message = format_message(
        conditions, astro_data, moon_age, moonrise, planets, meteor_showers, constellations
    )
    send_messages(cfg.LINE_CHANNEL_ACCESS_TOKEN, cfg.LINE_NOTIFY_TARGETS, message)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: テストがパスすることを確認**

```bash
cd /home/kaede/stargazing-line-bot && python -m pytest tests/test_notify.py -v
```

期待: 全件 PASS

- [ ] **Step 5: 全テストスイートを確認**

```bash
cd /home/kaede/stargazing-line-bot && python -m pytest -v
```

期待: 全件 PASS

- [ ] **Step 6: コミット**

```bash
cd /home/kaede/stargazing-line-bot
git add src/notify.py tests/test_notify.py
git commit -m "feat: notify.py を時間別スコアリング・複数API対応に全面更新"
```

---

## Task 6: notify.yml — Secrets 名変更

**Files:**
- Modify: `.github/workflows/notify.yml`

- [ ] **Step 1: notify.yml を更新**

`.github/workflows/notify.yml` の `env:` セクションを以下に変更する：

```yaml
        env:
          LINE_CHANNEL_ACCESS_TOKEN: ${{ secrets.LINE_CHANNEL_ACCESS_TOKEN }}
          LINE_NOTIFY_TARGETS: ${{ secrets.LINE_NOTIFY_TARGETS }}
          LOCATION_LAT: ${{ secrets.LOCATION_LAT }}
          LOCATION_LON: ${{ secrets.LOCATION_LON }}
```

（`LINE_USER_ID: ${{ secrets.LINE_USER_ID }}` を削除し、`LINE_NOTIFY_TARGETS` に置き換える）

- [ ] **Step 2: コミット**

```bash
cd /home/kaede/stargazing-line-bot
git add .github/workflows/notify.yml
git commit -m "ci: LINE_USER_ID を LINE_NOTIFY_TARGETS に変更"
```

---

## セットアップ手順（実装後に必要）

### GitHub Secrets の更新

1. `LINE_USER_ID` を削除
2. `LINE_NOTIFY_TARGETS` を追加（値例: `userId:Uxxxxxxxxxx`）

### LINEグループIDの取得

1. [webhook.site](https://webhook.site) を開き、一意のURLをコピー
2. LINE Developers Console → Messaging API → Webhook URL に貼り付けて保存
3. LINEボットを対象グループに追加
4. グループ内でメッセージを送る（ボットへのメンション）
5. webhook.siteのJSONから `groupId`（`C`で始まる文字列）をコピー
6. LINE Developers ConsoleのWebhook URLを元のURL（またはブランクで無効化）に戻す
7. GitHub Secretsの `LINE_NOTIFY_TARGETS` を `userId:Uxx,groupId:Cxx` に更新
