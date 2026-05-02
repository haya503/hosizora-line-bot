from datetime import datetime, timezone
from typing import Optional
import config
from sky_forecast import fetch_sky_conditions, SkyConditions
from astro_events import get_astro_data, PlanetInfo
from astro_client import HourlyAstroData, fetch_7timer_astro, fetch_constellations
from line_client import send_messages


def calculate_hourly_score(
    cloud_cover: int, visibility: int, seeing: int, transparency: int
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
    moon_str = f"月齢: {moon_age:.0f}"
    if moonrise:
        moon_str += f"（月の出: {moonrise}）"

    hourly_lines = []
    for reading in conditions.hourly:
        ad = astro_data.get(reading.hour, HourlyAstroData(1, 1))
        score = calculate_hourly_score(
            reading.cloud_cover, reading.visibility, ad.seeing, ad.transparency
        )
        hourly_lines.append(f"  {reading.hour}時: {format_stars(score)}")

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

    scores = [
        calculate_hourly_score(
            r.cloud_cover,
            r.visibility,
            astro_data.get(r.hour, HourlyAstroData(1, 1)).seeing,
            astro_data.get(r.hour, HourlyAstroData(1, 1)).transparency,
        )
        for r in conditions.hourly
    ]
    overall = round(sum(scores) / len(scores)) if scores else 1

    lines = [
        "🌙 今夜の星空予報",
        "",
        "時間帯別:",
        *hourly_lines,
        "",
        f"💧 湿度: {conditions.humidity}%　🌬 風速: {conditions.wind_speed}m/s",
        f"🌙 {moon_str}",
        "",
        "🔭 今夜のポイント:",
        *event_lines,
    ]

    if constellations:
        lines += ["", "✨ 今夜見える星座:", "  " + "　".join(constellations)]

    lines += ["", f"総合評価: {format_stars(overall)}"]

    return "\n".join(lines)


def main() -> None:
    cfg = config.load()
    now_utc = datetime.now(timezone.utc)
    sky_error = None

    try:
        conditions = fetch_sky_conditions(cfg.LOCATION_LAT, cfg.LOCATION_LON)
    except Exception as e:
        sky_error = e

    if sky_error is not None:
        send_messages(cfg.LINE_CHANNEL_ACCESS_TOKEN, cfg.LINE_NOTIFY_TARGETS, f"⚠️ 気象データ取得失敗: {sky_error}")
        return

    moon_age, moonrise, planets, meteor_showers = get_astro_data(
        cfg.LOCATION_LAT, cfg.LOCATION_LON, now_utc
    )

    try:
        astro_data = fetch_7timer_astro(cfg.LOCATION_LAT, cfg.LOCATION_LON)
    except Exception:
        astro_data = {}

    try:
        from datetime import date, timedelta, timezone as tz
        JST = tz(timedelta(hours=9))
        date_jst = datetime.now(JST).date().isoformat()
        constellations = fetch_constellations(cfg.LOCATION_LAT, cfg.LOCATION_LON, date_jst)
    except Exception:
        constellations = []

    message = format_message(conditions, astro_data, moon_age, moonrise, planets, meteor_showers, constellations)
    send_messages(cfg.LINE_CHANNEL_ACCESS_TOKEN, cfg.LINE_NOTIFY_TARGETS, message)


if __name__ == "__main__":
    main()
