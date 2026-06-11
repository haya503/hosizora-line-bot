import sys
from datetime import datetime, timedelta, timezone
from typing import Optional
import config
import discord_client
from sky_forecast import fetch_sky_conditions, SkyConditions
from astro_events import get_astro_data, PlanetInfo
from astro_client import HourlyAstroData, fetch_7timer_astro, fetch_constellations
from usno_client import fetch_astronomical_twilight
from jma_client import fetch_night_weather_penalties
from apod_client import fetch_apod, translate_apod_explanation
from line_client import send_messages, send_image_message
from cams_client import fetch_aod
from openaq_client import fetch_pm25
from horizons_client import fetch_visible_comets, CometInfo

JST = timezone(timedelta(hours=9))

_HOURLY_EMOJI = {5: "✨", 4: "😊", 3: "🌤", 2: "⛅", 1: "☁️"}


def calculate_hourly_score(
    cloud_cover: int, visibility: int, seeing: int, transparency: int,
    weather_penalty: int = 0, aod: Optional[float] = None, pm25: Optional[float] = None
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
    if aod is not None and aod > 0.4:
        score -= 1
    if pm25 is not None and pm25 > 75:
        score -= 2
    elif pm25 is not None and pm25 > 35:
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
    twilight_time: Optional[str] = None,
    weather_penalties: Optional[dict[int, int]] = None,
    location_name: Optional[str] = None,
    comets: Optional[list[CometInfo]] = None,
    aod: Optional[float] = None,
    pm25: Optional[float] = None,
    apod_title: Optional[str] = None,
) -> str:
    emoji, phase_name = moon_phase(moon_age)
    moon_str = f"{phase_name}（月齢{moon_age:.0f}）"
    if moonrise:
        moon_str += f"　月の出: {moonrise}"

    hourly_lines = []
    for reading in conditions.hourly:
        ad = astro_data.get(reading.hour, HourlyAstroData(1, 1))
        penalty = (weather_penalties or {}).get(reading.hour, 0)
        score = calculate_hourly_score(
            reading.cloud_cover, reading.visibility, ad.seeing, ad.transparency,
            weather_penalty=penalty, aod=aod, pm25=pm25
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
    if comets:
        for comet in comets:
            event_lines.append(
                f"・{comet.name} が見頃 {comet.best_time}（高度 {comet.altitude}°, 等級 {comet.magnitude}）"
            )
    if not event_lines:
        event_lines.append("・特になし")

    scores = [
        calculate_hourly_score(
            r.cloud_cover,
            r.visibility,
            astro_data.get(r.hour, HourlyAstroData(1, 1)).seeing,
            astro_data.get(r.hour, HourlyAstroData(1, 1)).transparency,
            weather_penalty=(weather_penalties or {}).get(r.hour, 0),
            aod=aod,
            pm25=pm25,
        )
        for r in conditions.hourly
    ]
    overall = round(sum(scores) / len(scores)) if scores else 1

    humidity_line = f"💧 湿度: {conditions.humidity}%　🌬 風速: {conditions.wind_speed}m/s"
    if pm25 is not None:
        humidity_line += f"　🏭 PM2.5: {pm25:.0f}μg/m³"
    if aod is not None:
        humidity_line += f"　🌫 AOD: {aod:.2f}"

    location_line = f"📍 {location_name}" if location_name else ""
    lines = ["🌙 今夜の星空予報", *(([location_line, ""] if location_line else [""]))]
    if twilight_time:
        lines += [f"🌑 天文薄明: {twilight_time}（この時刻から観測ベスト）", ""]
    lines += [
        "時間帯別:",
        *hourly_lines,
        "",
        humidity_line,
        f"{emoji} {moon_str}",
        "",
        "🔭 今夜のポイント:",
        *event_lines,
    ]

    if constellations:
        lines += ["", "✨ 今夜見える星座:", "  " + "　".join(constellations)]

    lines += ["", f"総合評価: {format_stars(overall)}"]

    if apod_title:
        lines += ["", f"📷 今日のNASA天文写真", apod_title]

    return "\n".join(lines)


def main() -> None:
    cfg = config.load()
    now_utc = datetime.now(timezone.utc)
    print(f"[notify] 開始: {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    sky_error = None
    try:
        conditions = fetch_sky_conditions(cfg.LOCATION_LAT, cfg.LOCATION_LON)
        print(f"[notify] 気象データ取得完了 (雲量: {[r.cloud_cover for r in conditions.hourly]}%)")
    except Exception as e:
        sky_error = e

    if sky_error is not None:
        print(f"[notify] ⚠️ 気象データ取得失敗: {sky_error}", file=sys.stderr)
        try:
            send_messages(cfg.LINE_CHANNEL_ACCESS_TOKEN, cfg.LINE_NOTIFY_TARGETS, f"⚠️ 気象データ取得失敗: {sky_error}")
        except RuntimeError as line_err:
            print(f"[notify] ⚠️ エラー通知の LINE送信も失敗: {line_err}", file=sys.stderr)
        sys.exit(1)

    moon_age, moonrise, planets, meteor_showers = get_astro_data(
        cfg.LOCATION_LAT, cfg.LOCATION_LON, now_utc
    )
    print(f"[notify] 天文データ取得完了 (月齢: {moon_age:.1f})")

    try:
        astro_data = fetch_7timer_astro(cfg.LOCATION_LAT, cfg.LOCATION_LON)
        print(f"[notify] 7timer シーイングデータ取得完了 ({len(astro_data)}件)")
    except Exception as e:
        print(f"[notify] 7timer 取得失敗（スキップ）: {e}", file=sys.stderr)
        astro_data = {}

    date_jst = datetime.now(JST).date().isoformat()
    try:
        constellations = fetch_constellations(cfg.LOCATION_LAT, cfg.LOCATION_LON, date_jst, cfg.HOSHIMIRU_API_TOKEN)
        print(f"[notify] 星座データ取得完了 ({len(constellations)}件)")
    except Exception as e:
        print(f"[notify] 星座データ取得失敗（スキップ）: {e}", file=sys.stderr)
        constellations = []

    twilight_time = fetch_astronomical_twilight(cfg.LOCATION_LAT, cfg.LOCATION_LON, date_jst)
    print(f"[notify] 天文薄明: {twilight_time or '取得失敗'}")

    weather_penalties = fetch_night_weather_penalties(cfg.JMA_AREA_CODE)
    print(f"[notify] JMA天気補正: {'取得完了' if weather_penalties is not None else '取得失敗（スキップ）'}")

    try:
        aod = fetch_aod(cfg.LOCATION_LAT, cfg.LOCATION_LON)
        print(f"[notify] AOD: {aod:.3f}" if aod is not None else "[notify] AOD: 取得失敗（スキップ）")
    except Exception as e:
        print(f"[notify] AOD取得失敗（スキップ）: {e}", file=sys.stderr)
        aod = None

    try:
        pm25 = fetch_pm25(cfg.LOCATION_LAT, cfg.LOCATION_LON)
        print(f"[notify] PM2.5: {pm25:.1f}μg/m³" if pm25 is not None else "[notify] PM2.5: 取得失敗（スキップ）")
    except Exception as e:
        print(f"[notify] PM2.5取得失敗（スキップ）: {e}", file=sys.stderr)
        pm25 = None

    try:
        comets = fetch_visible_comets(cfg.LOCATION_LAT, cfg.LOCATION_LON, date_jst)
        print(f"[notify] 彗星データ: {len(comets)}件")
    except Exception as e:
        print(f"[notify] 彗星データ取得失敗（スキップ）: {e}", file=sys.stderr)
        comets = []

    # APOD タイトルを取得して予報メッセージに統合（メッセージ数削減）
    apod_result = fetch_apod(cfg.NASA_APOD_API_KEY)
    apod_image_url: Optional[str] = None
    if apod_result:
        image_url, title, _ = apod_result
        translated_title = translate_apod_explanation(title, cfg.DEEPL_API_KEY) or title
        apod_image_url = image_url
        print(f"[notify] APOD取得完了: {title}")
    else:
        translated_title = None
        print("[notify] APOD取得失敗（スキップ）", file=sys.stderr)

    message = format_message(
        conditions, astro_data, moon_age, moonrise, planets, meteor_showers, constellations,
        twilight_time=twilight_time,
        weather_penalties=weather_penalties,
        location_name=cfg.LOCATION_NAME,
        comets=comets,
        aod=aod,
        pm25=pm25,
        apod_title=translated_title,
    )
    print(f"[notify] メッセージ生成完了 ({len(message)}文字)")

    notified = False
    try:
        send_messages(cfg.LINE_CHANNEL_ACCESS_TOKEN, cfg.LINE_NOTIFY_TARGETS, message)
        print(f"[notify] LINE送信完了 ({len(cfg.LINE_NOTIFY_TARGETS)}件)")
        notified = True
    except RuntimeError as e:
        print(f"[notify] ⚠️ LINE送信失敗（全ターゲット）: {e}", file=sys.stderr)
        if cfg.DISCORD_WEBHOOK_URL:
            try:
                if apod_image_url:
                    discord_client.send_embed_with_image(cfg.DISCORD_WEBHOOK_URL, message, apod_image_url)
                else:
                    discord_client.send_message(cfg.DISCORD_WEBHOOK_URL, message)
                print("[notify] Discord フォールバック送信完了")
                notified = True
            except Exception as discord_err:
                print(f"[notify] ⚠️ Discord送信失敗: {discord_err}", file=sys.stderr)
        else:
            print("[notify] DISCORD_WEBHOOK_URL が未設定のためフォールバック不可", file=sys.stderr)

    if not notified:
        sys.exit(1)

    # APOD 画像のみ送信（タイトルは上の予報メッセージに統合済み）
    if apod_image_url:
        try:
            send_image_message(cfg.LINE_CHANNEL_ACCESS_TOKEN, cfg.LINE_NOTIFY_TARGETS, apod_image_url)
            print("[notify] APOD画像送信完了")
        except Exception as e:
            print(f"[notify] APOD画像送信失敗（無視）: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
