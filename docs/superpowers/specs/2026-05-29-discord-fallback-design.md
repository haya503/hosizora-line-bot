# Discord フォールバック通知 — 設計書

## 概要

LINE送信が全失敗した場合に Discord Webhook へフォールバックする機能を追加する。

## 変更ファイル

| ファイル | 変更内容 |
|---|---|
| `src/discord_client.py` | 新規作成 — Webhook送信ロジック |
| `src/config.py` | `DISCORD_WEBHOOK_URL` を追加（任意項目） |
| `src/notify.py` | LINE失敗時にDiscordフォールバックを呼ぶ |

## `discord_client.py`

### インターフェース

```python
def send_message(webhook_url: str, text: str) -> None
def send_embed_with_image(webhook_url: str, text: str, image_url: str) -> None
```

### 仕様

- `POST https://discord.com/api/webhooks/{id}/{token}` を呼ぶ
- テキストは `content` フィールドに送信
  - Discord の2000文字制限を超過する場合は末尾を切り捨て
- 画像は `embeds[0].image.url` で添付
- HTTPエラー時は `requests.HTTPError` をそのまま raise する

## `config.py`

- `DISCORD_WEBHOOK_URL` を `os.environ.get("DISCORD_WEBHOOK_URL", "")` で取得（任意）
- 空文字列の場合はDiscordフォールバックを無効とみなす

## `notify.py` のフォールバックロジック

```
LINE送信（send_messages）→ RuntimeError（全ターゲット失敗）
  ↓
cfg.DISCORD_WEBHOOK_URL が設定されていれば:
  - apod_image_url があれば send_embed_with_image(text + image)
  - なければ send_message(text)
  ↓
設定なければ: stderr にログして終了（現在の挙動を維持）
```

APOD画像はDiscordフォールバック時にテキストと同一リクエストで送信する（LINE送信の個別呼び出しとは異なる）。

## 環境変数

| 変数名 | 必須 | 説明 |
|---|---|---|
| `DISCORD_WEBHOOK_URL` | 任意 | DiscordのWebhook URL。未設定の場合フォールバックなし |

## テスト方針

- `tests/test_discord_client.py` を新規作成
- `requests.post` をモックして正常系・文字数超過・HTTPエラーをテスト
- `tests/test_notify.py` にフォールバック呼び出しのテストを追加
