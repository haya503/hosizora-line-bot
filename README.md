# stargazing-line-bot

毎晩17:00に今夜の星空予報をLINEに送るBot。

## 機能

- 時間帯別の星空スコア（21〜24時）
- 雲量・視程・湿度・風速の気象情報
- 天文薄明終了時刻（観測開始の目安）
- 月齢・月の出時刻
- 惑星の南中情報・流星群予報
- 今夜見える星座一覧
- 気象庁天気コードによるスコア補正
- 今日のNASA天文写真（APOD）を画像メッセージで送信
- 複数のLINEユーザー/グループへの一括通知

## 使用API

| API | 用途 |
|-----|------|
| [Open-Meteo](https://open-meteo.com/) | 雲量・視程・湿度・風速 |
| [7timer ASTRO](http://www.7timer.info/) | シーイング・透明度 |
| [星をみるひとAPI](https://hoshimiru.jp/) | 見える星座 |
| [気象庁 JSON](https://www.jma.go.jp/bosai/forecast/) | 夜間天気コード→スコア補正 |
| [NASA APOD](https://apod.nasa.gov/apod/astropix.html) | 今日の天文写真 |
| skyfield（ローカル計算） | 天文薄明時刻 |

## セットアップ

### 必要なもの

- Python 3.12+
- LINE Messaging API チャンネル
- GitHub リポジトリ（GitHub Actions用）

### インストール

```bash
pip install -r requirements.txt
```

### 環境変数

`.env.example` をコピーして設定：

```bash
cp .env.example .env
```

| 変数名 | 必須 | 説明 |
|--------|------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | ✓ | LINE Messaging API のチャンネルアクセストークン |
| `LINE_NOTIFY_TARGETS` | ✓ | 通知先のID（カンマ区切り、例: `user:Uxxxx,group:Cxxxx`） |
| `LOCATION_LAT` | ✓ | 観測地の緯度 |
| `LOCATION_LON` | ✓ | 観測地の経度 |
| `JMA_AREA_CODE` | ✓ | 気象庁の地域コード（例: 熊本 `430010`、東京 `130010`） |
| `HOSHIMIRU_API_TOKEN` | — | 星をみるひとAPIトークン（未設定時は星座情報をスキップ） |
| `NASA_APOD_API_KEY` | — | NASA APIキー（未設定時は `DEMO_KEY` を使用） |

### 通知先IDの確認方法

1. LINE Official Account Manager でWebhookを有効化
2. 通知したいユーザー/グループからBotにメッセージを送信
3. Webhookで受信したJSONの `source.userId` または `source.groupId` を使用

## 実行

```bash
python src/notify.py
```

## GitHub Actions

リポジトリの Secrets に以下を設定すると、毎日17:00 JSTに自動通知されます。

| Secret名 | 説明 |
|----------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINEトークン |
| `LINE_NOTIFY_TARGETS` | 通知先ID |
| `LOCATION_LAT` | 緯度 |
| `LOCATION_LON` | 経度 |
| `JMA_AREA_CODE` | 気象庁地域コード |
| `HOSHIMIRU_API_TOKEN` | 星をみるひとAPIトークン |
| `NASA_APOD_API_KEY` | NASA APIキー |

## テスト

```bash
pytest
```

## メッセージ例

```
🌙 今夜の星空予報

🌑 天文薄明: 20:34（この時刻から観測ベスト）

時間帯別:
21時 ✨ ★★★★★
22時 ✨ ★★★★★
23時 😊 ★★★★☆
24時 🌤 ★★★☆☆

💧 湿度: 45%　🌬 風速: 2.1m/s
🌒 三日月（月齢5）　月の出: 21:30

🔭 今夜のポイント:
・木星が南中 22:15（高度 58°）
・ペルセウス座流星群まであと3日

✨ 今夜見える星座:
  さそり座　こと座　はくちょう座

総合評価: ★★★★☆
```
