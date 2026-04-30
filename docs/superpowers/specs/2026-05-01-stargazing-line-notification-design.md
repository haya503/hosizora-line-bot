# 星空予報 LINE通知システム 設計ドキュメント

**日付:** 2026-05-01  
**ステータス:** 承認済み

---

## 概要

毎日決まった時刻に、固定地点の星空予報をLINE Messaging API経由でプッシュ通知するシステム。GitHub Actions を実行基盤として使用し、サーバー管理コストをゼロに抑える。

---

## アーキテクチャ

```
GitHub Actions (cron: 毎日18:00 JST)
        ↓
  notify.py（メインスクリプト）
     ├── Open-Meteo API（無料・APIキー不要）
     │     → 雲量・視程・湿度・風速
     ├── skyfield ライブラリ（ローカル計算）
     │     → 月齢・惑星の南中時刻・主要天文イベント
     └── LINE Messaging API
           → 固定ユーザーへプッシュ通知
```

### ファイル構成

```
.github/workflows/notify.yml   # スケジュール設定・手動トリガー
src/
  notify.py        # エントリーポイント
  sky_forecast.py  # Open-Meteoから気象データ取得
  astro_events.py  # skyfieldで天文イベント計算
  line_client.py   # LINE Messaging API送信
  config.py        # GitHub Secretsから設定読み込み
requirements.txt
```

---

## コンポーネント詳細

### `sky_forecast.py`
Open-Meteo APIから以下を取得する（APIキー不要・無料）。
- 雲量（%）
- 視程（m）
- 湿度（%）
- 風速（m/s）

### `astro_events.py`
`skyfield` ライブラリを用いてローカル計算する。
- 月齢・月の出没時刻
- 主要惑星（金星・木星・土星）の南中時刻と最大高度
- 流星群情報（ピーク日のハードコードリスト）

### `line_client.py`
LINE Messaging API の Push Message エンドポイントを呼び出す。
- チャネルアクセストークン・User IDはGitHub Secretsから取得
- テキストメッセージ形式で送信

### `config.py`
環境変数（GitHub Secrets）から以下を読み込む。
- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_USER_ID`
- `LOCATION_LAT`（観測地点の緯度）
- `LOCATION_LON`（観測地点の経度）

---

## 通知メッセージフォーマット

```
🌙 今夜の星空予報

☁️ 雲量: 20%
💧 湿度: 55%　🌬 風速: 3m/s
🌙 月齢: 12（月の出: 21:30）

🔭 今夜のポイント:
・木星が南中 22:30（高度 58°）
・ペルセウス座流星群まであと3日

総合評価: ★★★★☆
```

### 総合評価ロジック
以下のスコアを合算してStar 1〜5を算出する。

| 要素 | 満点 | 減点条件 |
|------|------|----------|
| 雲量 | 3点 | 雲量50%超で-1、80%超で-2 |
| 月明かり | 1点 | 月齢10〜20日で-1 |
| 視程 | 1点 | 視程10km未満で-1 |

---

## エラーハンドリング

| 障害 | 対応 |
|------|------|
| Open-Meteo API失敗 | 1回リトライ。失敗なら「気象データ取得失敗」を通知してスキップ |
| LINE API送信失敗 | GitHub Actionsのジョブ失敗として記録（ログに出力） |
| skyfield計算 | 外部API非依存のため基本的に失敗しない |

---

## テスト方針

- `.github/workflows/notify.yml` に `workflow_dispatch` を追加し、任意タイミングで手動テスト送信できる
- `src/` の各モジュールに対して軽量なユニットテスト（メッセージフォーマット関数を中心に）
- ローカルから `python src/notify.py` で動作確認できるよう、環境変数を `.env` ファイルからも読めるようにする（`.env` は `.gitignore` に追加）

---

## シークレット管理

GitHubリポジトリのSettings → Secrets and variables → Actionsに以下を登録する。

- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_USER_ID`
- `LOCATION_LAT`
- `LOCATION_LON`

---

## 使用ライブラリ・API

| 名前 | 用途 | 費用 |
|------|------|------|
| Open-Meteo | 気象データ | 無料 |
| skyfield | 天文計算 | 無料（OSS） |
| requests | HTTP通信 | 無料（OSS） |
| python-dotenv | ローカル開発用環境変数 | 無料（OSS） |
| LINE Messaging API | 通知送信 | 無料枠あり |
| GitHub Actions | スケジュール実行 | 無料枠あり |
