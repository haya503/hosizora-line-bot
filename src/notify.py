from datetime import datetime, timedelta, timezone
from typing import Optional
import config
from sky_forecast import fetch_sky_conditions, SkyConditions
from astro_events import get_astro_data, PlanetInfo
from astro_client import HourlyAstroData, fetch_7timer_astro, fetch_constellations
from line_client import send_messages

JST = timezone(timedelta(hours=9))

_HOURLY_EMOJI = {5: "✨", 4: "😊", 3: "🌤", 2: "⛅", 1: "☁️"}


def calculate_hourly_score(
    cloud_cover: int, visibility: int, seeing: int, transparency: int,
    weather_penalty: int = 0
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
    score += weather_penalty
    return max(1, score)


def format_stars(score: int) -> str:
    return "★" * score + "☆" * (5 - score)


def moon_phase(age: float) -> tuple[str, str]:
    """月齢から (絵文字, 名称) を返す"""
    if age < 1.5 or age >= 28.0:
        return "🌑", "新月"
    if age < 6.5:
        return "🌒", "三日月"
    if age < 9.5:
        return "🌓", "上弦"
    if age < 13.5:
        return "🌔", "十三夜"
    if age < 16.5:
        return "🌕", "満月"
    if age < 20.5:
        return "🌖", "十六夜"
    if age < 24.0:
        return "🌗", "下弦"
    return "🌘", "有明月"


def format_message(
    conditions: SkyConditions,
    astro_data: dict[int, HourlyAstroData],
    moon_age: float,
    moonrise: Optional[str],
    planets: list[PlanetInfo],
    meteor_showers: list[tuple[str, int]],
    constellations: list[str],
) -> str:
    emoji, phase_name = moon_phase(moon_age)
    moon_str = f"{phase_name}（月齢{moon_age:.0f}）"
    if moonrise:
        moon_str += f"　月の出: {moonrise}"

    hourly_lines = []
    for reading in conditions.hourly:
        ad = astro_data.get(reading.hour, HourlyAstroData(1, 1))
        score = calculate_hourly_score(
            reading.cloud_cover, reading.visibility, ad.seeing, ad.transparency
        )
        hourly_lines.append(f"{reading.hour}時 {_HOURLY_EMOJI[score]} {format_stars(score)}")

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
        f"{emoji} {moon_str}",
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
        date_jst = datetime.now(JST).date().isoformat()
        constellations = fetch_constellations(cfg.LOCATION_LAT, cfg.LOCATION_LON, date_jst, cfg.HOSHIMIRU_API_TOKEN)
    except Exception:
        constellations = []

    message = format_message(conditions, astro_data, moon_age, moonrise, planets, meteor_showers, constellations)
    send_messages(cfg.LINE_CHANNEL_ACCESS_TOKEN, cfg.LINE_NOTIFY_TARGETS, message)


if __name__ == "__main__":
    main()
