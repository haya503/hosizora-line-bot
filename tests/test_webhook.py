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
