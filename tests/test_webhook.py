# tests/test_webhook.py
import base64
import hashlib
import hmac
import json
import os
from unittest.mock import patch, MagicMock

# モジュールインポート前に環境変数を設定
os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "test_tok"
os.environ["LINE_CHANNEL_SECRET"] = "test_secret"
os.environ["LINE_BOT_USER_ID"] = "Ubot12345"
os.environ["HOSHIMIRU_API_TOKEN"] = ""

from fastapi.testclient import TestClient
from webhook import app, _verify_signature, _is_mention_event

SECRET = "test_secret"
BOT_USER_ID = "Ubot12345"
client = TestClient(app)


def _sig(body: bytes) -> str:
    return base64.b64encode(
        hmac.new(SECRET.encode(), body, hashlib.sha256).digest()
    ).decode()


def _mention_payload(text: str) -> bytes:
    payload = {
        "events": [{
            "type": "message",
            "replyToken": "reply_tok_001",
            "message": {
                "type": "text",
                "text": text,
                "mention": {"mentionees": [{"userId": BOT_USER_ID}]},
            },
        }]
    }
    return json.dumps(payload).encode()


# --- _verify_signature ---

def test_verify_signature_valid():
    body = b"hello"
    sig = _sig(body)
    assert _verify_signature(body, sig, SECRET) is True


def test_verify_signature_invalid():
    assert _verify_signature(b"hello", "invalidsig==", SECRET) is False


# --- _is_mention_event ---

def test_is_mention_event_true():
    event = {
        "type": "message",
        "message": {
            "type": "text",
            "mention": {"mentionees": [{"userId": BOT_USER_ID}]},
        },
    }
    assert _is_mention_event(event, BOT_USER_ID) is True


def test_is_mention_event_false_no_mentionee():
    event = {
        "type": "message",
        "message": {
            "type": "text",
            "mention": {"mentionees": []},
        },
    }
    assert _is_mention_event(event, BOT_USER_ID) is False


def test_is_mention_event_false_wrong_type():
    event = {"type": "follow"}
    assert _is_mention_event(event, BOT_USER_ID) is False


# --- POST /webhook ---

def test_invalid_signature_returns_400():
    body = b'{"events":[]}'
    resp = client.post("/webhook", content=body, headers={"X-Line-Signature": "bad=="})
    assert resp.status_code == 400


def test_empty_events_returns_200():
    body = json.dumps({"events": []}).encode()
    resp = client.post("/webhook", content=body, headers={"X-Line-Signature": _sig(body)})
    assert resp.status_code == 200


def test_mention_event_triggers_handle_mention():
    body = _mention_payload("@Bot 今日 夜 東京")
    with patch("webhook._handle_mention") as mock_handle:
        resp = client.post("/webhook", content=body, headers={"X-Line-Signature": _sig(body)})
    assert resp.status_code == 200
    mock_handle.assert_called_once_with("reply_tok_001", "@Bot 今日 夜 東京")


def test_non_mention_event_does_not_trigger():
    payload = {
        "events": [{
            "type": "message",
            "replyToken": "reply_tok_002",
            "message": {"type": "text", "text": "hello", "mention": {"mentionees": []}},
        }]
    }
    body = json.dumps(payload).encode()
    with patch("webhook._handle_mention") as mock_handle:
        resp = client.post("/webhook", content=body, headers={"X-Line-Signature": _sig(body)})
    assert resp.status_code == 200
    mock_handle.assert_not_called()


# --- _format_night_forecast with AOD/PM2.5/comets ---

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from sky_forecast import SkyConditions, HourlySkyReading
from horizons_client import CometInfo
from webhook import _format_night_forecast, _format_hour_forecast


def _make_conditions():
    return SkyConditions(
        humidity=60,
        wind_speed=2.0,
        hourly=[HourlySkyReading(hour=21, cloud_cover=10, visibility=20000)],
    )


def test_format_night_forecast_shows_aod():
    msg = _format_night_forecast(
        _make_conditions(), 5.0, None, [], [], "5月10日", "東京",
        aod=0.52,
    )
    assert "AOD: 0.52" in msg


def test_format_night_forecast_shows_pm25():
    msg = _format_night_forecast(
        _make_conditions(), 5.0, None, [], [], "5月10日", "東京",
        pm25=45.0,
    )
    assert "PM2.5: 45" in msg


def test_format_night_forecast_shows_comet():
    comet = CometInfo(name="C/2025 E3", best_time="22:00", altitude=35.0, magnitude=6.5)
    msg = _format_night_forecast(
        _make_conditions(), 5.0, None, [], [], "5月10日", "東京",
        comets=[comet],
    )
    assert "C/2025 E3" in msg


def test_format_hour_forecast_shows_aod():
    msg = _format_hour_forecast(
        _make_conditions(), 21, 5.0, [], "5月10日", "東京",
        aod=0.35,
    )
    assert "AOD: 0.35" in msg


def test_format_hour_forecast_shows_pm25():
    msg = _format_hour_forecast(
        _make_conditions(), 21, 5.0, [], "5月10日", "東京",
        pm25=20.0,
    )
    assert "PM2.5: 20" in msg


# --- _handle_mention calls CAMS/OpenAQ/Horizons ---

from webhook import _handle_mention


def test_handle_mention_calls_aod_pm25_comets(monkeypatch):
    from datetime import date
    from sky_forecast import SkyConditions, HourlySkyReading
    from astro_events import PlanetInfo

    conditions = _make_conditions()
    planets = []
    moon_age = 5.0

    monkeypatch.setattr("webhook._geocode", lambda loc: (33.0, 130.0))
    monkeypatch.setattr("webhook.fetch_sky_conditions", lambda *a, **kw: conditions)
    monkeypatch.setattr("webhook.get_astro_data", lambda *a, **kw: (moon_age, None, planets, None))
    monkeypatch.setattr("webhook.fetch_constellations", lambda *a, **kw: [])

    aod_calls = []
    pm25_calls = []
    comet_calls = []

    monkeypatch.setattr("webhook.fetch_aod", lambda lat, lon: aod_calls.append((lat, lon)) or 0.3)
    monkeypatch.setattr("webhook.fetch_pm25", lambda lat, lon: pm25_calls.append((lat, lon)) or 15.0)
    monkeypatch.setattr("webhook.fetch_visible_comets", lambda lat, lon, d: comet_calls.append((lat, lon, d)) or [])
    monkeypatch.setattr("webhook.reply_message", lambda *a, **kw: None)

    _handle_mention("tok", "@Bot 今夜 夜 東京")

    assert len(aod_calls) == 1
    assert len(pm25_calls) == 1
    assert len(comet_calls) == 1
