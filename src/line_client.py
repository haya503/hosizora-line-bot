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
        except Exception as e:
            print(f"LINE send failed for {target}: {e}", file=sys.stderr)
            failures.append((target, e))
    if failures and len(failures) == len(targets):
        raise failures[0][1]
