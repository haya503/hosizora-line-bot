from dataclasses import dataclass
import sys
import time
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


# Open-Meteo は混雑時に接続（TLS ハンドシェイク）や応答に 10 秒以上かかることがあるため、
# タイムアウトを長めにし、失敗したら間をあけて再試行する。
# なお TLS ハンドシェイク中のタイムアウトは接続タイムアウトの値で判定される
_TIMEOUT = (20, 30)  # (接続, 読み取り) 秒
_RETRY_WAITS = (5, 15)  # 2 回目・3 回目の前に待つ秒数

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Open-Meteo の無料 API は IP アドレスごとに回数制限があり、GitHub Actions のように
# 多くの利用者と IP を共有する環境では 429 (Too Many Requests) になることがある。
# その場合は MET Norway (ノルウェー気象局) の予報 API で代替する。
# MET Norway はアプリを識別できる User-Agent を必須としている（python-requests 既定の
# User-Agent は拒否される）。利用規約では連絡先 (URL やメールアドレス) を含めることが推奨されている
_MET_NO_URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete"
_MET_NO_USER_AGENT = "stargazing-line-bot/1.0"

# MET Norway は視程を返さないため、霧の割合 (fog_area_fraction) から目安の視程 (m) を決める
_CLEAR_VISIBILITY = 20000


def _target_times(today_jst: date) -> dict[int, str]:
    tomorrow_jst = today_jst + timedelta(days=1)
    return {
        21: f"{today_jst}T21:00",
        22: f"{today_jst}T22:00",
        23: f"{today_jst}T23:00",
        24: f"{tomorrow_jst}T00:00",
    }


def _build_conditions(
    today_jst: date,
    times: list[str],
    cloud_cover: list,
    visibility: list,
    humidity: list,
    wind_speed: list,
) -> SkyConditions:
    """JST の時刻文字列 ("YYYY-MM-DDTHH:MM") ごとの値から SkyConditions を組み立てる。"""
    evening_idx = [
        i for i, t in enumerate(times)
        if t.startswith(str(today_jst))
        and any(t.endswith(f"T{h:02d}:00") for h in range(18, 24))
    ]
    if not evening_idx:
        raise ValueError(f"{today_jst} 18〜23時の予報がありません")
    avg_humidity = round(sum(humidity[i] for i in evening_idx) / len(evening_idx))
    avg_wind = round(sum(wind_speed[i] for i in evening_idx) / len(evening_idx), 1)

    hourly = []
    for hour, target_time in _target_times(today_jst).items():
        if target_time in times:
            i = times.index(target_time)
            hourly.append(HourlySkyReading(
                hour=hour,
                cloud_cover=round(cloud_cover[i]),
                visibility=round(visibility[i]),
            ))

    return SkyConditions(humidity=avg_humidity, wind_speed=avg_wind, hourly=hourly)


def _is_rate_limited(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    return response is not None and response.status_code == 429


def _fetch_open_meteo(
    lat: float,
    lon: float,
    today_jst: date,
    attempts: int,
    timeout: float | tuple[float, float],
) -> SkyConditions:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "cloud_cover,visibility,relative_humidity_2m,wind_speed_10m",
        "wind_speed_unit": "ms",  # 既定は km/h なので m/s を指定する
        "timezone": "Asia/Tokyo",
        "forecast_days": 2,
    }
    last_exc: Exception | None = None
    for attempt in range(attempts):
        if attempt > 0:
            time.sleep(_RETRY_WAITS[min(attempt - 1, len(_RETRY_WAITS) - 1)])
        try:
            resp = requests.get(_OPEN_METEO_URL, params=params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()["hourly"]
            return _build_conditions(
                today_jst,
                data["time"],
                data["cloud_cover"],
                data["visibility"],
                data["relative_humidity_2m"],
                data["wind_speed_10m"],
            )
        except requests.RequestException as e:
            print(f"Open-Meteo 取得失敗 ({attempt + 1}/{attempts} 回目): {e}", file=sys.stderr)
            last_exc = e
            # 回数制限は数秒待っても解除されないので、すぐに代替 API に切り替える
            if _is_rate_limited(e):
                break
    raise last_exc  # type: ignore[misc]


def _visibility_from_fog(fog_area_fraction: float | None) -> int:
    if fog_area_fraction is None:
        return _CLEAR_VISIBILITY
    if fog_area_fraction >= 50:
        return 1000
    if fog_area_fraction >= 10:
        return 5000
    return _CLEAR_VISIBILITY


def _fetch_met_norway(
    lat: float,
    lon: float,
    today_jst: date,
    timeout: float | tuple[float, float],
) -> SkyConditions:
    # 座標は小数点以下 4 桁までにするよう求められている
    params = {"lat": round(lat, 4), "lon": round(lon, 4)}
    resp = requests.get(
        _MET_NO_URL,
        params=params,
        headers={"User-Agent": _MET_NO_USER_AGENT},
        timeout=timeout,
    )
    resp.raise_for_status()
    timeseries = resp.json()["properties"]["timeseries"]

    times, cloud, vis, humidity, wind = [], [], [], [], []
    for entry in timeseries:
        details = entry["data"]["instant"]["details"]
        utc = datetime.fromisoformat(entry["time"].replace("Z", "+00:00"))
        times.append(utc.astimezone(JST).strftime("%Y-%m-%dT%H:%M"))
        cloud.append(details["cloud_area_fraction"])
        vis.append(_visibility_from_fog(details.get("fog_area_fraction")))
        humidity.append(details["relative_humidity"])
        wind.append(details["wind_speed"])
    return _build_conditions(today_jst, times, cloud, vis, humidity, wind)


def fetch_sky_conditions(
    lat: float,
    lon: float,
    today_jst: date | None = None,
    attempts: int = 3,
    timeout: float | tuple[float, float] = _TIMEOUT,
) -> SkyConditions:
    """今夜の雲量・視程・湿度・風速を返す。

    Open-Meteo で取得し、失敗したら MET Norway で取得する。両方失敗したら
    requests.RequestException を送出する。
    """
    if today_jst is None:
        today_jst = datetime.now(JST).date()

    try:
        return _fetch_open_meteo(lat, lon, today_jst, attempts, timeout)
    except Exception as open_meteo_err:
        print(f"Open-Meteo を諦めて MET Norway で取得します: {open_meteo_err}", file=sys.stderr)
        try:
            conditions = _fetch_met_norway(lat, lon, today_jst, timeout)
        except Exception as met_err:
            print(f"MET Norway 取得失敗: {met_err}", file=sys.stderr)
            raise requests.RequestException(
                f"Open-Meteo: {open_meteo_err} / MET Norway: {met_err}"
            ) from met_err
        print("MET Norway から取得しました", file=sys.stderr)
        return conditions


if __name__ == "__main__":
    # 診断用: 各 API から個別に取得できるかを確かめる
    #   python src/sky_forecast.py [緯度] [経度]
    lat = float(sys.argv[1]) if len(sys.argv) > 1 else 32.8022
    lon = float(sys.argv[2]) if len(sys.argv) > 2 else 130.7081
    today = datetime.now(JST).date()
    for name, fetch in (
        ("Open-Meteo", lambda: _fetch_open_meteo(lat, lon, today, 1, _TIMEOUT)),
        ("MET Norway", lambda: _fetch_met_norway(lat, lon, today, _TIMEOUT)),
    ):
        try:
            print(f"{name}: {fetch()}")
        except Exception as e:
            print(f"{name}: 失敗 ({e})")
