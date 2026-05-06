# 新規API統合 設計書

**日付:** 2026-05-06  
**対象ブランチ:** master

## 概要

星空予報 LINE Bot に以下の3つの無料APIを追加統合する。

| API | 追加情報 | 無料枠 |
|---|---|---|
| USNO（米海軍天文台） | 天文薄明終了時刻 | 完全無料・登録不要 |
| NASA APOD | 今日の天文写真（画像メッセージ） | 完全無料（APIキー登録のみ） |
| 気象庁 JSON | 天気概況テキスト | 完全無料 |

AstronomyAPI（月50リクエスト上限）は毎日配信に足りないため除外。

---

## ファイル構成

```
src/
├── astro_client.py     # 既存（7timer・Hoshimiru）変更なし
├── astro_events.py     # 既存（Skyfield）変更なし
├── config.py           # 既存 → NASA_APOD_API_KEY, JMA_AREA_CODE を追加
├── line_client.py      # 既存 → 画像メッセージ送信関数を追加
├── notify.py           # 既存 → 新APIのオーケストレーションを追加
├── sky_forecast.py     # 既存（Open-Meteo）変更なし
├── apod_client.py      # 新規: NASA APOD クライアント
├── jma_client.py       # 新規: 気象庁 クライアント
└── usno_client.py      # 新規: USNO 天文薄明クライアント
```

---

## 各モジュール仕様

### `usno_client.py`

- **エンドポイント:** `https://aa.usno.navy.mil/api/rstt/oneday`
- **パラメータ:** `date`（YYYY-MM-DD）, `coords`（lat,lon）, `tz`（9 = JST）
- **取得データ:** 天文薄明終了時刻（`astronomical_twilight_end`）
- **返り値:** `str | None`（例: `"20:15"`）
- **用途:** 「この時刻から星空観測ベスト」としてメッセージに表示

### `apod_client.py`

- **エンドポイント:** `https://api.nasa.gov/planetary/apod`
- **パラメータ:** `api_key`
- **取得データ:** `url`（画像URL）、`title`（タイトル）、`media_type`
- **返り値:** `tuple[str, str] | None`（url, title）
- **注意:** `media_type == "video"` の日は `None` を返す（動画はLINEに送れないため）

### `jma_client.py`

- **エンドポイント:** `https://www.jma.go.jp/bosai/forecast/data/forecast/{JMA_AREA_CODE}.json`
- **取得データ:** 今日の天気概況テキスト
- **返り値:** `str | None`（例: `"晴れ時々曇り"`）
- **注意:** 気象庁APIは非公式扱いで仕様変更リスクあり。失敗時は静かにスキップ。

### `line_client.py` の変更

- `send_image_message(token, targets, image_url)` 関数を追加
- LINEの `image` メッセージ型で画像URLを送信

### `notify.py` の変更

- 上記3APIを呼び出してデータ取得
- テキストメッセージに天文薄明時刻・天気概況を追記
- APODは別の画像メッセージとして送信

**メッセージ構成（テキスト部分）:**
```
🌙 今夜の星空予報

☁️ 天気: 晴れ時々曇り
🌑 天文薄明: 20:15（この時刻から観測ベスト）

時間帯別:
21時 ✨ ★★★★★
...（以下既存）
```

---

## 設定・シークレット

### 新規環境変数

| 変数名 | 説明 | 必須 |
|---|---|---|
| `NASA_APOD_API_KEY` | NASA API キー（`DEMO_KEY` でも1日1回なら動作可） | 推奨 |
| `JMA_AREA_CODE` | 気象庁エリアコード（例: `130000` = 東京） | 必須 |

### GitHub Actions

`notify.yml` に `NASA_APOD_API_KEY` と `JMA_AREA_CODE` の secrets 参照を追加。

---

## エラーハンドリング

既存コードと同方針: **新APIが失敗しても通知全体は止めない。**

| API | 失敗時の挙動 |
|---|---|
| USNO | 天文薄明の行を省略してメッセージ送信 |
| NASA APOD | 画像メッセージをスキップ（テキストのみ送信） |
| 気象庁 | 天気概況の行を省略してメッセージ送信 |

---

## 対象外

- AstronomyAPI（有料、月50リクエスト上限のため除外）
- Open-Meteo の置き換え（気象庁は補完として使用）
- USNO の日の出・日の入り（天文薄明のみ取得）
