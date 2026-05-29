# Discord フォールバック通知 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** LINE送信が全失敗した場合に Discord Webhook へフォールバックして通知する

**Architecture:** `discord_client.py` を新規作成してWebhook送信ロジックを実装し、`config.py` に `DISCORD_WEBHOOK_URL` 環境変数を追加、`notify.py` の LINE 失敗時フォールバックパスで Discord を呼ぶ。

**Tech Stack:** Python, requests, unittest.mock

---

## ファイル構成

| ファイル | 変更種別 | 役割 |
|---|---|---|
| `src/discord_client.py` | 新規作成 | Discord Webhook 送信ロジック |
| `src/config.py` | 修正 | `DISCORD_WEBHOOK_URL` を追加 |
| `src/notify.py` | 修正 | LINE 失敗時に Discord フォールバック |
| `tests/test_discord_client.py` | 新規作成 | `discord_client` のユニットテスト |
| `tests/test_notify.py` | 修正 | フォールバックのテスト追加、`FAKE_CFG` 更新 |

---

### Task 1: `discord_client.py` のテストを書く

**Files:**
- Create: `tests/test_discord_client.py`

- [ ] **Step 1: テストファイルを新規作成する**

```python
# tests/test_discord_client.py
from unittest.mock import patch, MagicMock
import requests
import pytest
import discord_client

WEBHOOK_URL = "https://discord.com/api/webhooks/123/abc"


def test_send_message_posts_to_webhook():
    with patch("discord_client.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=204)
        discord_client.send_message(WEBHOOK_URL, "テストメッセージ")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == WEBHOOK_URL
        assert kwargs["json"]["content"] == "テストメッセージ"


def test_send_message_truncates_long_text():
    long_text = "あ" * 3000
    with patch("discord_client.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=204)
        discord_client.send_message(WEBHOOK_URL, long_text)
        sent = mock_post.call_args[1]["json"]["content"]
        assert len(sent) <= 2000


def test_send_message_raises_on_http_error():
    with patch("discord_client.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("400 Bad Request")
        mock_post.return_value = mock_resp
        with pytest.raises(requests.HTTPError):
            discord_client.send_message(WEBHOOK_URL, "エラーテスト")


def test_send_embed_with_image_sends_embed():
    with patch("discord_client.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=204)
        discord_client.send_embed_with_image(WEBHOOK_URL, "テキスト", "https://example.com/img.jpg")
        args, kwargs = mock_post.call_args
        assert args[0] == WEBHOOK_URL
        body = kwargs["json"]
        assert body["content"] == "テキスト"
        assert body["embeds"][0]["image"]["url"] == "https://example.com/img.jpg"


def test_send_embed_with_image_truncates_long_text():
    long_text = "あ" * 3000
    with patch("discord_client.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=204)
        discord_client.send_embed_with_image(WEBHOOK_URL, long_text, "https://example.com/img.jpg")
        sent = mock_post.call_args[1]["json"]["content"]
        assert len(sent) <= 2000
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
cd /home/kaede/stargazing-line-bot && python -m pytest tests/test_discord_client.py -v
```

期待: `ModuleNotFoundError: No module named 'discord_client'`

---

### Task 2: `discord_client.py` を実装する

**Files:**
- Create: `src/discord_client.py`

- [ ] **Step 3: `discord_client.py` を作成する**

```python
# src/discord_client.py
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
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
cd /home/kaede/stargazing-line-bot && python -m pytest tests/test_discord_client.py -v
```

期待: 5件すべて PASS

- [ ] **Step 5: コミットする**

```bash
git add src/discord_client.py tests/test_discord_client.py
git commit -m "feat: Discord Webhook クライアントを追加"
```

---

### Task 3: `config.py` に `DISCORD_WEBHOOK_URL` を追加する

**Files:**
- Modify: `src/config.py:26-43`
- Modify: `tests/test_notify.py:19-29`（`FAKE_CFG` に `DISCORD_WEBHOOK_URL` を追加）

- [ ] **Step 6: `FAKE_CFG` に `DISCORD_WEBHOOK_URL=""` を追加するテストを修正する**

`tests/test_notify.py` の `FAKE_CFG` に1行追加する:

```python
FAKE_CFG = SimpleNamespace(
    LINE_CHANNEL_ACCESS_TOKEN="tok",
    LINE_NOTIFY_TARGETS=["uid"],
    LOCATION_NAME="熊本市中央区横手3丁目",
    LOCATION_LAT=32.8022,
    LOCATION_LON=130.7081,
    HOSHIMIRU_API_TOKEN="test_token",
    JMA_AREA_CODE="130000",
    NASA_APOD_API_KEY="DEMO_KEY",
    DEEPL_API_KEY="",
    DISCORD_WEBHOOK_URL="",
)
```

- [ ] **Step 7: `config.py` の `load()` に `DISCORD_WEBHOOK_URL` を追加する**

`src/config.py` の `return SimpleNamespace(...)` ブロックに追加する:

```python
def load() -> SimpleNamespace:
    load_dotenv()
    targets = _parse_targets(os.environ["LINE_NOTIFY_TARGETS"])
    if not targets:
        raise ValueError(
            "LINE_NOTIFY_TARGETS must contain at least one valid 'type:id' entry"
        )
    return SimpleNamespace(
        LINE_CHANNEL_ACCESS_TOKEN=os.environ["LINE_CHANNEL_ACCESS_TOKEN"],
        LINE_NOTIFY_TARGETS=targets,
        LOCATION_NAME=FIXED_LOCATION_NAME,
        LOCATION_LAT=FIXED_LOCATION_LAT,
        LOCATION_LON=FIXED_LOCATION_LON,
        HOSHIMIRU_API_TOKEN=os.environ.get("HOSHIMIRU_API_TOKEN", ""),
        NASA_APOD_API_KEY=os.environ.get("NASA_APOD_API_KEY", "DEMO_KEY"),
        JMA_AREA_CODE=os.environ["JMA_AREA_CODE"],
        DEEPL_API_KEY=os.environ.get("DEEPL_API_KEY", ""),
        DISCORD_WEBHOOK_URL=os.environ.get("DISCORD_WEBHOOK_URL", ""),
    )
```

- [ ] **Step 8: 既存テストが壊れていないことを確認する**

```bash
cd /home/kaede/stargazing-line-bot && python -m pytest tests/test_config.py tests/test_notify.py -v
```

期待: すべて PASS

- [ ] **Step 9: コミットする**

```bash
git add src/config.py tests/test_notify.py
git commit -m "feat: config に DISCORD_WEBHOOK_URL を追加"
```

---

### Task 4: `notify.py` に Discord フォールバックを実装する

**Files:**
- Modify: `src/notify.py`
- Modify: `tests/test_notify.py`

- [ ] **Step 10: フォールバックのテストを `tests/test_notify.py` に追加する**

ファイル末尾に以下を追加する:

```python
@patch("notify.discord_client")
@patch("notify.send_image_message")
@patch("notify.translate_apod_explanation")
@patch("notify.fetch_apod")
@patch("notify.fetch_night_weather_penalties")
@patch("notify.fetch_astronomical_twilight")
@patch("notify.send_messages")
@patch("notify.fetch_constellations")
@patch("notify.fetch_7timer_astro")
@patch("notify.get_astro_data")
@patch("notify.fetch_sky_conditions")
@patch("notify.fetch_visible_comets")
@patch("notify.fetch_pm25")
@patch("notify.fetch_aod")
@patch("notify.config")
def test_main_line_failure_falls_back_to_discord(
    mock_config, mock_fetch_aod, mock_fetch_pm25, mock_fetch_comets,
    mock_fetch, mock_astro, mock_7timer, mock_const, mock_send,
    mock_twilight, mock_penalties, mock_apod, mock_summarize, mock_send_image,
    mock_discord,
):
    cfg = SimpleNamespace(**vars(FAKE_CFG))
    cfg.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/123/abc"
    mock_config.load.return_value = cfg
    mock_fetch.return_value = SAMPLE_CONDITIONS
    mock_astro.return_value = (5.0, "21:00", SAMPLE_PLANETS, [])
    mock_7timer.return_value = SAMPLE_ASTRO
    mock_const.return_value = []
    mock_twilight.return_value = None
    mock_penalties.return_value = None
    mock_apod.return_value = None
    mock_fetch_aod.return_value = None
    mock_fetch_pm25.return_value = None
    mock_fetch_comets.return_value = []
    mock_send.side_effect = RuntimeError("LINE send failed for all targets: uid")

    main()

    mock_discord.send_message.assert_called_once()
    url, text = mock_discord.send_message.call_args[0]
    assert url == "https://discord.com/api/webhooks/123/abc"
    assert "今夜の星空予報" in text


@patch("notify.discord_client")
@patch("notify.send_image_message")
@patch("notify.translate_apod_explanation")
@patch("notify.fetch_apod")
@patch("notify.fetch_night_weather_penalties")
@patch("notify.fetch_astronomical_twilight")
@patch("notify.send_messages")
@patch("notify.fetch_constellations")
@patch("notify.fetch_7timer_astro")
@patch("notify.get_astro_data")
@patch("notify.fetch_sky_conditions")
@patch("notify.fetch_visible_comets")
@patch("notify.fetch_pm25")
@patch("notify.fetch_aod")
@patch("notify.config")
def test_main_line_failure_with_apod_uses_embed(
    mock_config, mock_fetch_aod, mock_fetch_pm25, mock_fetch_comets,
    mock_fetch, mock_astro, mock_7timer, mock_const, mock_send,
    mock_twilight, mock_penalties, mock_apod, mock_summarize, mock_send_image,
    mock_discord,
):
    cfg = SimpleNamespace(**vars(FAKE_CFG))
    cfg.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/123/abc"
    mock_config.load.return_value = cfg
    mock_fetch.return_value = SAMPLE_CONDITIONS
    mock_astro.return_value = (5.0, "21:00", SAMPLE_PLANETS, [])
    mock_7timer.return_value = SAMPLE_ASTRO
    mock_const.return_value = []
    mock_twilight.return_value = None
    mock_penalties.return_value = None
    mock_apod.return_value = ("https://example.com/img.jpg", "Galaxy", "description")
    mock_summarize.return_value = "銀河"
    mock_fetch_aod.return_value = None
    mock_fetch_pm25.return_value = None
    mock_fetch_comets.return_value = []
    mock_send.side_effect = RuntimeError("LINE send failed for all targets: uid")

    main()

    mock_discord.send_embed_with_image.assert_called_once()
    url, text, image_url = mock_discord.send_embed_with_image.call_args[0]
    assert url == "https://discord.com/api/webhooks/123/abc"
    assert "今夜の星空予報" in text
    assert image_url == "https://example.com/img.jpg"


@patch("notify.discord_client")
@patch("notify.send_image_message")
@patch("notify.translate_apod_explanation")
@patch("notify.fetch_apod")
@patch("notify.fetch_night_weather_penalties")
@patch("notify.fetch_astronomical_twilight")
@patch("notify.send_messages")
@patch("notify.fetch_constellations")
@patch("notify.fetch_7timer_astro")
@patch("notify.get_astro_data")
@patch("notify.fetch_sky_conditions")
@patch("notify.fetch_visible_comets")
@patch("notify.fetch_pm25")
@patch("notify.fetch_aod")
@patch("notify.config")
def test_main_line_failure_no_discord_url_no_fallback(
    mock_config, mock_fetch_aod, mock_fetch_pm25, mock_fetch_comets,
    mock_fetch, mock_astro, mock_7timer, mock_const, mock_send,
    mock_twilight, mock_penalties, mock_apod, mock_summarize, mock_send_image,
    mock_discord,
):
    mock_config.load.return_value = FAKE_CFG  # DISCORD_WEBHOOK_URL=""
    mock_fetch.return_value = SAMPLE_CONDITIONS
    mock_astro.return_value = (5.0, "21:00", SAMPLE_PLANETS, [])
    mock_7timer.return_value = SAMPLE_ASTRO
    mock_const.return_value = []
    mock_twilight.return_value = None
    mock_penalties.return_value = None
    mock_apod.return_value = None
    mock_fetch_aod.return_value = None
    mock_fetch_pm25.return_value = None
    mock_fetch_comets.return_value = []
    mock_send.side_effect = RuntimeError("LINE send failed for all targets: uid")

    main()

    mock_discord.send_message.assert_not_called()
    mock_discord.send_embed_with_image.assert_not_called()
```

- [ ] **Step 11: テストが失敗することを確認する**

```bash
cd /home/kaede/stargazing-line-bot && python -m pytest tests/test_notify.py::test_main_line_failure_falls_back_to_discord -v
```

期待: FAIL（`discord_client` が `notify` にインポートされていないため）

- [ ] **Step 12: `notify.py` にフォールバックロジックを実装する**

`src/notify.py` の先頭 import に追加:

```python
import discord_client
```

`main()` の LINE 失敗時の処理（`notify.py:233-237`）を以下に置き換える:

```python
    try:
        send_messages(cfg.LINE_CHANNEL_ACCESS_TOKEN, cfg.LINE_NOTIFY_TARGETS, message)
    except RuntimeError as e:
        print(f"⚠️ LINE送信失敗: {e}", file=sys.stderr)
        if cfg.DISCORD_WEBHOOK_URL:
            if apod_image_url:
                discord_client.send_embed_with_image(cfg.DISCORD_WEBHOOK_URL, message, apod_image_url)
            else:
                discord_client.send_message(cfg.DISCORD_WEBHOOK_URL, message)
        return

    # APOD 画像のみ送信（タイトルは上の予報メッセージに統合済み）
    if apod_image_url:
        try:
            send_image_message(cfg.LINE_CHANNEL_ACCESS_TOKEN, cfg.LINE_NOTIFY_TARGETS, apod_image_url)
        except Exception:
            pass
```

- [ ] **Step 13: テストがすべて通ることを確認する**

```bash
cd /home/kaede/stargazing-line-bot && python -m pytest tests/test_notify.py tests/test_discord_client.py -v
```

期待: すべて PASS

- [ ] **Step 14: 全テストスイートを実行して回帰がないことを確認する**

```bash
cd /home/kaede/stargazing-line-bot && python -m pytest -v
```

期待: すべて PASS

- [ ] **Step 15: コミットする**

```bash
git add src/notify.py tests/test_notify.py
git commit -m "feat: LINE 失敗時に Discord へフォールバック"
```
