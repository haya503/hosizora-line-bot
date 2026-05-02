import requests

_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def send_message(token: str, user_id: str, text: str) -> None:
    resp = requests.post(
        _PUSH_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        json={
            "to": user_id,
            "messages": [{"type": "text", "text": text}],
        },
        timeout=10,
    )
    resp.raise_for_status()
