# src/webhook.py
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

import requests as _requests
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from astro_events import get_astro_data
from astro_client import fetch_constellations
from line_client import reply_message
from message_parser import ERROR_MESSAGE, ParseError, parse_mention_text
from notify import calculate_hourly_score, format_stars, moon_phase
from sky_forecast import SkyConditions, fetch_sky_conditions

JST = timezone(timedelta(hours=9))
_HOURLY_EMOJI = {5: "✨", 4: "😊", 3: "🌤", 2: "⛅", 1: "☁️"}

_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
_SECRET = os.environ["LINE_CHANNEL_SECRET"]
_BOT_USER_ID = os.environ["LINE_BOT_USER_ID"]
_HOSHIMIRU_TOKEN = os.environ.get("HOSHIMIRU_API_TOKEN", "")

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger(__name__)

app = FastAPI()


def _verify_signature(body: bytes, signature: str, secret: str) -> bool:
    expected = base64.b64encode(
        hmac.new(secret.encode(), body, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(expected, signature)


def _is_mention_event(event: dict, bot_user_id: str) -> bool:
    if event.get("type") != "message":
        return False
    msg = event.get("message", {})
    if msg.get("type") != "text":
        return False
    if event.get("source", {}).get("type") == "user":
        return True
    mentionees = msg.get("mention", {}).get("mentionees", [])
    return any(
        m.get("userId") == bot_user_id or m.get("isSelf") is True
        for m in mentionees
    )


def _geocode(location: str) -> tuple[float, float]:
    resp = _requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": location, "format": "json", "limit": 1},
        headers={"User-Agent": "stargazing-line-bot/1.0", "Accept-Language": "ja"},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        raise ValueError(f"場所が見つかりません: {location}")
    return float(results[0]["lat"]), float(results[0]["lon"])


def _format_night_forecast(
    conditions: SkyConditions,
    moon_age: float,
    moonrise: str | None,
    planets: list,
    constellations: list[str],
    date_label: str,
    location_name: str,
) -> str:
    emoji, phase_name = moon_phase(moon_age)
    moon_str = f"{phase_name}（月齢{moon_age:.0f}）"
    if moonrise:
        moon_str += f"　月の出: {moonrise}"

    hourly_lines, scores = [], []
    for reading in conditions.hourly:
        score = calculate_hourly_score(reading.cloud_cover, reading.visibility, 1, 1)
        scores.append(score)
        hourly_lines.append(f"{reading.hour}時 {_HOURLY_EMOJI[score]} {format_stars(score)}")

    overall = round(sum(scores) / len(scores)) if scores else 1

    event_lines = [
        f"・{p.name}が南中 {p.transit_time}（高度 {p.max_altitude}°）"
        for p in planets if p.transit_time
    ]
    if not event_lines:
        event_lines = ["・特になし"]

    lines = [f"🌙 {date_label} {location_name}の星空予報（夜）", "", "時間帯別:", *hourly_lines, ""]
    lines += [
        f"💧 湿度: {conditions.humidity}%　🌬 風速: {conditions.wind_speed}m/s",
        f"{emoji} {moon_str}",
        "",
        "🔭 今夜のポイント:",
        *event_lines,
    ]
    if constellations:
        lines += ["", "✨ 見える星座:", "  " + "　".join(constellations)]
    lines += ["", f"総合評価: {format_stars(overall)}"]
    return "\n".join(lines)


def _format_hour_forecast(
    conditions: SkyConditions,
    hour: int,
    moon_age: float,
    planets: list,
    date_label: str,
    location_name: str,
) -> str:
    reading = next((r for r in conditions.hourly if r.hour == hour), None)
    if reading is None:
        return (
            f"🌙 {date_label} {hour}時 {location_name}の星空予報\n\n"
            "⚠️ 該当時間のデータがありません（対応時間: 21〜24時）"
        )

    score = calculate_hourly_score(reading.cloud_cover, reading.visibility, 1, 1)
    emoji, phase_name = moon_phase(moon_age)

    event_lines = [
        f"・{p.name}が南中 {p.transit_time}（高度 {p.max_altitude}°）"
        for p in planets if p.transit_time
    ]
    if not event_lines:
        event_lines = ["・特になし"]

    lines = [
        f"🌙 {date_label} {hour}時 {location_name}の星空予報",
        "",
        f"{_HOURLY_EMOJI[score]} {format_stars(score)}",
        "",
        f"💧 湿度: {conditions.humidity}%　🌬 風速: {conditions.wind_speed}m/s",
        f"{emoji} {phase_name}（月齢{moon_age:.0f}）",
        "",
        "🔭 見どころ:",
        *event_lines,
    ]
    return "\n".join(lines)


def _handle_mention(reply_token: str, text: str) -> None:
    import time
    t0 = time.monotonic()
    today = datetime.now(JST).date()
    try:
        req = parse_mention_text(text, today)
    except ParseError as e:
        reply_message(_TOKEN, reply_token, str(e))
        return

    try:
        lat, lon = _geocode(req.location)
        _log.info("geocode %.1fs", time.monotonic() - t0)
    except Exception:
        reply_message(_TOKEN, reply_token, ERROR_MESSAGE)
        return

    try:
        conditions = fetch_sky_conditions(lat, lon, req.target_date)
        _log.info("sky_forecast %.1fs", time.monotonic() - t0)
    except Exception as e:
        reply_message(_TOKEN, reply_token, f"⚠️ 気象データ取得失敗: {e}")
        return

    try:
        moon_age, moonrise, planets, _ = get_astro_data(lat, lon, datetime.now(timezone.utc))
        _log.info("astro_data %.1fs", time.monotonic() - t0)
    except Exception as e:
        reply_message(_TOKEN, reply_token, f"⚠️ 天体データ取得失敗: {e}")
        return

    date_label = f"{req.target_date.month}月{req.target_date.day}日"

    if req.time_type == "night":
        try:
            constellations = fetch_constellations(
                lat, lon, req.target_date.isoformat(), _HOSHIMIRU_TOKEN
            )
        except Exception:
            constellations = []
        msg = _format_night_forecast(
            conditions, moon_age, moonrise, planets, constellations, date_label, req.location
        )
    else:
        msg = _format_hour_forecast(conditions, req.hour, moon_age, planets, date_label, req.location)

    try:
        reply_message(_TOKEN, reply_token, msg)
    except Exception:
        pass


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")
    if not _verify_signature(body, signature, _SECRET):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = json.loads(body)
    for event in payload.get("events", []):
        logger.info("event type=%s source=%s", event.get("type"), event.get("source", {}).get("type"))
        if _is_mention_event(event, _BOT_USER_ID):
            background_tasks.add_task(
                _handle_mention,
                event["replyToken"],
                event["message"]["text"],
            )

    return {"status": "ok"}
