import requests

_DISCORD_MAX_CONTENT = 2000


def _truncate(text: str) -> str:
    return text[:_DISCORD_MAX_CONTENT]


def send_message(webhook_url: str, text: str) -> None:
    resp = requests.post(webhook_url, json={"content": _truncate(text)}, timeout=10)
    resp.raise_for_status()


def send_embed_with_image(webhook_url: str, text: str, image_url: str) -> None:
    body = {
        "content": _truncate(text),
        "embeds": [{"image": {"url": image_url}}],
    }
    resp = requests.post(webhook_url, json=body, timeout=10)
    resp.raise_for_status()
