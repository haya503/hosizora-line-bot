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
    else:
        if visibility < 10000:
            score -= 1
    if 10 <= moon_age <= 20:
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
