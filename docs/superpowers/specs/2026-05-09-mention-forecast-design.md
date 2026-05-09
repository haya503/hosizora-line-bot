# 設計書：LINEメンション星空予報機能

**日付:** 2026-05-09  
**ステータス:** 承認済み

---

## 概要

LINEでBotをメンションし、日付・時間・場所を自然言語で指定すると、その条件に応じた星空予報を返信する機能を追加する。

---

## 要件

- **トリガー:** LINEグループまたはトーク内でBotをメンション
- **入力形式:** `@Bot [日付] [時間] [場所]`（全パラメータ必須）
- **言語:** 日本語自然言語
- **利用者制限:** なし（Botがいるトーク全員が使用可能）
- **費用:** 無料（Google Cloud Run 無料枠 + OpenStreetMap Nominatim）

---

## アーキテクチャ

### 新規コンポーネント

| ファイル | 役割 |
|----------|------|
| `src/webhook.py` | FastAPI Webhookサーバー |
| `src/message_parser.py` | 日本語自然言語パーサー |
| `Dockerfile` | Cloud Run用コンテナ定義 |
| `.dockerignore` | Dockerビルド除外設定 |

### 既存コンポーネントの変更

| ファイル | 変更内容 |
|----------|----------|
| `src/line_client.py` | Reply API送信関数を追加（現在はPush APIのみ） |
| `src/config.py` | `LINE_CHANNEL_SECRET`・`LINE_BOT_USER_ID` を追加 |
| `requirements.txt` | `fastapi`・`uvicorn` を追加 |

### データフロー

```
ユーザー「@Bot 明日 夜 東京」
    ↓ LINE Webhook POST
webhook.py
    → X-Line-Signature を検証
    → HTTP 200 を即返却
    → BackgroundTask:
        1. message_parser.py でテキスト解析
           → 日付・時間種別（夜/単時間）・場所名
        2. OpenStreetMap Nominatim で場所名 → 緯度・経度
        3. 既存の forecast 関数で予報生成
        4. LINE Reply API で返信
```

---

## メッセージパーサー仕様（`message_parser.py`）

### 日付パターン

| 入力例 | 解釈 |
|--------|------|
| 今日 | 当日 |
| 明日 | 翌日 |
| 明後日 | 翌々日 |
| 5月15日、5/15 | 指定日（過去日の場合は翌年） |

### 時間パターン

| 入力例 | 解釈 | 種別 |
|--------|------|------|
| 夜、今夜、今日の夜、明日の夜 | 21〜24時 | `night`（フル予報） |
| 21時 | 21:00 | `hour`（単時間予報） |
| 夜9時、夜の9時 | 21:00 | `hour` |
| 午後9時 | 21:00 | `hour` |
| 午前2時 | 02:00 | `hour` |

### 複合表現の扱い

「明日の夜」「今日の夜」のように日付と時間が一語になっている場合、パーサーは日付と時間を同時に抽出する。別途日付トークンがあれば複合表現側を優先する。

### 場所パターン

- 日付・時間トークンを除去した残りのテキストをNominatimに投げる
- 例: 「明日 21時 阿蘇山」→ 除去後「阿蘇山」→ Nominatimクエリ
- Nominatimのクエリに `accept-language: ja` を設定し、日本語地名を優先

### 解析失敗時のエラー返信

```
❌ 形式が正しくありません。
以下の形式でメンションしてください：

@Bot [日付] [時間] [場所]

例：
・@Bot 明日 夜 東京
・@Bot 今日 21時 阿蘇山
・@Bot 5月20日 午後9時 新宿区
```

エラー種別:
- 日付が解析できない
- 時間が解析できない
- 場所が解析できない（Nominatim 結果0件）
- 全パラメータのいずれかが欠落

---

## 予報出力仕様

### 夜指定時（`night`）：21〜24時フル予報

現在の `notify.py` の `format_message()` と同形式。JMAスコア補正は省略（任意座標のエリアコード特定が複雑なため）。

```
🌙 5月10日 東京の星空予報（今夜）

🌑 天文薄明: 20:34（この時刻から観測ベスト）

時間帯別:
21時 ✨ ★★★★★
22時 😊 ★★★★☆
23時 🌤 ★★★☆☆
24時 ⛅ ★★☆☆☆

💧 湿度: 45%　🌬 風速: 2.1m/s
🌒 三日月（月齢5）　月の出: 21:30

🔭 今夜のポイント:
・木星が南中 22:15（高度 58°）

✨ 今夜見える星座:
  さそり座　こと座

総合評価: ★★★★☆
```

### 単時間指定時（`hour`）

```
🌙 5月11日 21時 東京の星空予報

✨ ★★★★★

💧 湿度: 45%　🌬 風速: 2.1m/s
🌒 三日月（月齢5）

🔭 見どころ:
・木星が南中 22:15（高度 58°）
```

---

## Webhookサーバー仕様（`webhook.py`）

- **エンドポイント:** `POST /webhook`
- **署名検証:** `X-Line-Signature` を HMAC-SHA256 で検証（`LINE_CHANNEL_SECRET` 使用）
- **処理対象イベント:** `message` イベント、`text` 型、Botへのメンションを含むもの
- **メンション検出:** `message.mention.mentionees` に `LINE_BOT_USER_ID` が含まれるか確認
- **非同期処理:** FastAPI `BackgroundTasks` で即時200返却、処理はバックグラウンドで実行

---

## 新規環境変数

| 変数名 | 必須 | 説明 |
|--------|------|------|
| `LINE_CHANNEL_SECRET` | ✓ | Webhook署名検証用（LINE Developersで確認） |
| `LINE_BOT_USER_ID` | ✓ | Botの userId（メンション検出用） |

---

## デプロイ（Google Cloud Run）

### 追加パッケージ

```
fastapi
uvicorn[standard]
```

### Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ ./src/
CMD ["uvicorn", "src.webhook:app", "--host", "0.0.0.0", "--port", "8080"]
```

### セットアップ手順

```bash
# 1. gcloud CLI インストール後ログイン
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# 2. Cloud Run API を有効化
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com

# 3. イメージをビルド＆プッシュ
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/stargazing-bot

# 4. Cloud Run にデプロイ
gcloud run deploy stargazing-bot \
  --image gcr.io/YOUR_PROJECT_ID/stargazing-bot \
  --region asia-northeast1 \
  --allow-unauthenticated \
  --set-env-vars "LINE_CHANNEL_ACCESS_TOKEN=xxx,LINE_CHANNEL_SECRET=xxx,LINE_BOT_USER_ID=xxx,..."

# 5. 発行されたURLをLINE DevelopersのWebhook URLに設定
#    例: https://stargazing-bot-xxxxx-an.a.run.app/webhook
```

### LINE Developers側の設定

1. LINE Developers Console → チャンネル設定
2. Messaging API → Webhook設定
3. Webhook URL: `https://[Cloud RunのURL]/webhook`
4. 「Webhookの利用」→ ON
5. `LINE_CHANNEL_SECRET`（チャンネルシークレット）と `LINE_BOT_USER_ID`（BotのユーザーID）を確認し、Cloud Runの環境変数に追加

---

## 制約・注意事項

- JMAスコア補正はオンデマンドリクエスト時は省略（固定エリアコードが必要なため）
- Nominatim利用規約に従い、リクエスト間隔は最低1秒空ける（1リクエスト/秒制限）
- LINE Reply Token は受信から30秒以内に使用する必要がある
- Cloud Run のコールドスタートは通常1〜3秒（Webhook 200返却後にバックグラウンド処理するため問題なし）
