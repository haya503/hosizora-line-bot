import sys
import requests

_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def send_messages(token: str, targets: list[str], text: str) -> None:
    failures: list[tuple[str, Exception]] = []
    for target in targets:
        try:
            resp = requests.post(
                _PUSH_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                json={"to": target, "messages": [{"type": "text", "text": text}]},
                timeout=10,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"LINE send failed for {target}: {e}", file=sys.stderr)
            failures.append((target, e))
    if failures and len(failures) == len(targets):
        failed_ids = ", ".join(t for t, _ in failures)
        raise RuntimeError(f"LINE send failed for all targets: {failed_ids}") from failures[0][1]


def send_image_message(token: str, targets: list[str], image_url: str) -> None:
    """LINE image メッセージを各ターゲットに送信する。"""
    failures: list[tuple[str, Exception]] = []
    for target in targets:
        try:
            resp = requests.post(
                _PUSH_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                json={
                    "to": target,
                    "messages": [
                        {
                            "type": "image",
                            "originalContentUrl": image_url,
                            "previewImageUrl": image_url,
                        }
                    ],
                },
                timeout=10,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"LINE send failed for {target}: {e}", file=sys.stderr)
            failures.append((target, e))
    if failures and len(failures) == len(targets):
        failed_ids = ", ".join(t for t, _ in failures)
        raise RuntimeError(f"LINE send failed for all targets: {failed_ids}") from failures[0][1]
