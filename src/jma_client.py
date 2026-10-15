import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import requests

JST = timezone(timedelta(hours=9))
logger = logging.getLogger(__name__)

_BASE_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast"


def _penalty(weather_code: str) -> int:
    """天気コードの先頭1桁（1:晴れ 2:曇り 3:雨 4:雪）からスコア補正値を返す。"""
    return {1: 0, 2: -1, 3: -2, 4: -2}.get(int(weather_code[0]), 0)


def fetch_night_weather_penalties(
    area_code: str, today_jst: Optional[date] = None
) -> Optional[dict[int, int]]:
    """
    気象庁の府県天気予報から、時間帯別スコアの補正値を返す。取得失敗時は None。

    area_code は府県予報区のコード（例: 熊本 430000）で、先頭の一次細分区域の天気を使う。
    天気は日単位なので、21〜23時は今日、24時（翌0時）は明日の天気から補正値を決める。

    返り値: {時刻(JST時): 補正値} の辞書
    例: {21: 0, 22: 0, 23: 0, 24: -1}
    """
    if today_jst is None:
        today_jst = datetime.now(JST).date()
    try:
        url = f"{_BASE_URL}/{area_code}.json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # data[0]["timeSeries"][0] は今日・明日・明後日の日単位の天気
        time_series = response.json()[0]["timeSeries"][0]
        codes_by_date = {
            datetime.fromisoformat(t).date(): code
            for t, code in zip(time_series["timeDefines"], time_series["areas"][0]["weatherCodes"])
        }

        result = {}
        if today_jst in codes_by_date:
            penalty = _penalty(codes_by_date[today_jst])
            result.update({21: penalty, 22: penalty, 23: penalty})
        tomorrow_jst = today_jst + timedelta(days=1)
        if tomorrow_jst in codes_by_date:
            # sky_forecast は深夜0時を hour=24 で表現するため合わせる
            result[24] = _penalty(codes_by_date[tomorrow_jst])
        return result

    except Exception as e:
        logger.warning("JMA forecast fetch failed: %s", e)
        return None
