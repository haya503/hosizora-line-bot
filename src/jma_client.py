from datetime import datetime
from typing import Optional

import requests

_BASE_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast"


def fetch_night_weather_penalties(area_code: str) -> Optional[dict[int, int]]:
    """
    気象庁APIから夜間（18時〜翌3時）の天気コードを取得し、
    スコア補正値の辞書を返す。取得失敗時は None を返す。

    返り値: {時刻(JST時): 補正値} の辞書
    例: {18: 0, 21: -1, 24: -2}
    """
    try:
        url = f"{_BASE_URL}/{area_code}.json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()

        # data[0]["timeSeries"][0] に時系列データがある
        time_series = data[0]["timeSeries"][0]
        time_defines = time_series["timeDefines"]
        weather_codes = time_series["areas"][0]["weatherCodes"]

        result = {}

        for time_str, code in zip(time_defines, weather_codes):
            # ISO形式の日時文字列からJST時刻を取得
            dt = datetime.fromisoformat(time_str)
            hour = dt.hour

            # 夜間フィルタ: 18時以上 または 3時以下
            if hour >= 18 or hour <= 3:
                # 天気コードの先頭1文字から補正値を決定
                code_prefix = int(code[0])

                if code_prefix == 1:
                    penalty = 0
                elif code_prefix == 2:
                    penalty = -1
                elif code_prefix == 3:
                    penalty = -2
                elif code_prefix == 4:
                    penalty = -2
                else:
                    penalty = 0

                # sky_forecast は深夜0時を hour=24 で表現するため合わせる
                key = 24 if hour == 0 else hour
                result[key] = penalty

        return result

    except Exception:
        return None
