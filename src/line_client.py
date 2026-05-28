import sys
import time
import requests

_PUSH_URL = "https://api.line.me/v2/bot/message/push"
_MAX_RETRIES = 2
_DEFAULT_RETRY_WAIT = 60


def _post_with_retry(token: str, json_body: dict) -> requests.Response:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    for attempt in range(_MAX_RETRIES + 1):
        resp = requests.post(_PUSH_URL, headers=headers, json=json_body, timeout=10)
        if resp.status_code == 429 and attempt < _MAX_RETRIES:
            wait = int(resp.headers.get("Retry-After", _DEFAULT_RETRY_WAIT))
            print(f"LINE 429: Retry-After {wait}s (attempt {attempt + 1}/{_MAX_RETRIES})", file=sys.stderr)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp
    return resp


def send_messages(token: str, targets: list[str], text: str) -> None:
    failures: list[tuple[str, Exception]] = []
    for target in targets:
        try:
            _post_with_retry(token, {"to": target, "messages": [{"type": "text", "text": text}]})
        except requests.RequestException as e:
            print(f"LINE send failed for {target}: {e}", file=sys.stderr)
            failures.append((target, e))
    if failures and len(failures) == len(targets):
        failed_ids = ", ".join(t for t, _ in failures)
        raise RuntimeError(f"LINE send failed for all targets: {failed_ids}") from failures[0][1]


def send_image_message(token: str, targets: list[str], image_url: str) -> None:
    failures: list[tuple[str, Exception]] = []
    for target in targets:
        try:
            _post_with_retry(token, {
                "to": target,
                "messages": [
                    {
                        "type": "image",
                        "originalContentUrl": image_url,
                        "previewImageUrl": image_url,
                    }
                ],
            })
        except requests.RequestException as e:
            print(f"LINE send failed for {target}: {e}", file=sys.stderr)
            failures.append((target, e))
    if failures and len(failures) == len(targets):
        failed_ids = ", ".join(t for t, _ in failures)
        raise RuntimeError(f"LINE send failed for all targets: {failed_ids}") from failures[0][1]


_REPLY_URL = "https://api.line.me/v2/bot/message/reply"


def reply_message(token: str, reply_token: str, text: str) -> None:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}],
    }
    resp = requests.post(_REPLY_URL, headers=headers, json=payload, timeout=10)
    resp.raise_for_status()
