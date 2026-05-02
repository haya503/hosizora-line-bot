# 星空予報 機能改善 設計ドキュメント

**日付:** 2026-05-02  
**ステータス:** 承認済み

---

## 概要

既存の星空予報LINE通知システムに3つの改善を加える。

1. **時間帯別の星の見えやすさ表示**（21〜24時・1時間ごと）
2. **複数APIによる多角的スコアリング**（7timer ASTRO API・星をみるひとAPI追加）
3. **LINEグループ通知対応**（複数送信先）

---

## 改善①：時間帯別の星の見えやすさ

### 概要

21・22・23・24時それぞれについて星の見えやすさを1〜5星で表示する。現在の夜間平均値（18〜23時）から変更し、実際の観測時間帯に特化した情報を提供する。

### データソース

| API | 取得データ | 備考 |
|-----|-----------|------|
| Open-Meteo | 1時間ごとの雲量（%）・視程（m） | 既存API・パラメータ追加のみ |
| 7timer ASTRO | 1時間ごとのシーイング（1〜8）・透明度（1〜8） | 新規追加・無料・APIキー不要 |

**7timer ASTRO APIエンドポイント：**
```
http://www.7timer.info/bin/astro.php?lon=<LON>&lat=<LAT>&ac=0&lang=en&output=json&tzshift=0
```

### スコアリングロジック（1時間ごと・5点満点）

| 条件 | 減点 |
|------|------|
| 雲量 > 80%（Open-Meteo） | -2 |
| 雲量 > 50%（Open-Meteo） | -1 |
| 視程 < 10km（Open-Meteo） | -1 |
| シーイング ≥ 5（7timer、揺らぎ大） | -1 |
| 透明度 ≥ 6（7timer、霞みがち） | -1 |

最低1点（`max(1, score)`）。

7timerのシーイングスケール：1（<0.5"・最良）〜 8（>2.5"・最悪）  
7timerの透明度スケール：1（extinction<0.3・最良）〜 8（extinction>1.0・最悪）

**7timerのデータ解像度について：** 7timer ASTROは3時間ごとのデータを返す。JST 21〜24時はUTC 12〜15時に相当し、UTC 12:00と15:00の2点が利用可能。各時間には最近傍のデータポイントを使用する（21・22時 → UTC 12:00、23・24時 → UTC 15:00）。

**総合評価**は21〜24時の平均スコアを四捨五入して算出する。

### 絵文字マッピング

| 星数 | 絵文字 | 説明 |
|------|--------|------|
| ★★★★★ | ✨ | 完璧！ |
| ★★★★☆ | 😊 | いい感じ |
| ★★★☆☆ | 🌤 | まあまあ |
| ★★☆☆☆ | ⛅ | やや曇り |
| ★☆☆☆☆ | ☁️ | 見えにくい |

---

## 改善②：今夜見える星座（星をみるひとAPI）

### 概要

22時時点で観測地点から見える星座を取得し、最大5件を通知に追加する。

### APIエンドポイント

```
https://livlog.xyz/hoshimiru/constellation?lat=<LAT>&lng=<LON>&date=<YYYY-MM-DD>&hour=22&min=00
```

- 認証：不要
- レスポンス形式：JSON

### エラーハンドリング

取得失敗時は星座セクションをスキップして通知を送信する（非必須情報のため）。

---

## 改善③：LINEグループ通知対応

### 送信先の管理

GitHub Secretsに `LINE_NOTIFY_TARGETS` を追加する（既存の `LINE_USER_ID` を廃止）。

```
# 書式：タイプ:ID をカンマ区切りで列挙
LINE_NOTIFY_TARGETS=userId:Uxxxxxxxxxx,groupId:Cxxxxxxxxxx
```

`userId`・`groupId` どちらもLINE Push APIの `to` フィールドに直接指定可能なため、コードは送信先をループするだけでよい。

### エラーハンドリング

一部の送信先への送信が失敗しても残りの送信先には送り続ける。失敗はログに記録しGitHub Actionsのジョブ失敗として扱う（全送信先失敗時のみ）。

### グループIDの取得手順

1. [webhook.site](https://webhook.site) を開き、一意のURLをコピーする
2. LINE Developers Console → Messaging API → Webhook URL に貼り付けて保存
3. LINEボットを対象グループに追加する
4. グループ内でボットにメンションしてメッセージを送る
5. webhook.siteの画面に届いたJSONから `groupId`（`C`で始まる文字列）をコピー
6. LINE Developers ConsoleのWebhook URLを元に戻す
7. GitHub Secretsの `LINE_NOTIFY_TARGETS` にカンマ区切りで追記する

---

## 更新後のメッセージフォーマット

```
🌙 今夜の星空予報

🔭 時間帯別の見えやすさ（21〜24時）
21時 ✨ ★★★★★
22時 😊 ★★★★☆
23時 🌤 ★★★☆☆
24時 ⛅ ★★☆☆☆

🌌 今夜見える星座:
・さそり座、こと座、はくちょう座...

💧 湿度: 55%　🌬 風速: 3m/s
🌙 月齢: 12（月の出: 21:30）

🔭 今夜のポイント:
・木星が南中 22:30（高度 58°）
・ペルセウス座流星群まであと3日

総合評価: ★★★★☆
```

---

## ファイル変更一覧

| ファイル | 変更内容 |
|---------|---------|
| `src/sky_forecast.py` | 21〜24時の時間別データを返す構造に変更 |
| `src/astro_events.py` | 変更なし |
| `src/line_client.py` | 複数送信先へのループ送信に変更 |
| `src/config.py` | `LINE_USER_ID` → `LINE_NOTIFY_TARGETS`（パース処理追加） |
| `src/notify.py` | 7timerAPI呼び出し・星をみるひとAPI呼び出し・時間別スコア計算・フォーマット更新 |
| `.github/workflows/notify.yml` | Secrets名の変更（LINE_USER_ID → LINE_NOTIFY_TARGETS） |

---

## テスト方針

- `calculate_hourly_score()` の単体テスト（Open-Meteoのみ・7timer加味・複合ペナルティ）
- `format_message()` のスナップショットテスト（星座あり・なし両パターン）
- `line_client.send_messages()` の複数送信先テスト（一部失敗ケース含む）

---

## 使用API一覧

| API | 用途 | 費用 |
|-----|------|------|
| Open-Meteo | 雲量・視程・湿度・風速（時間別） | 無料 |
| 7timer ASTRO | シーイング・透明度（時間別） | 無料 |
| 星をみるひとAPI | 今夜見える星座 | 無料 |
| LINE Messaging API | プッシュ通知 | 無料枠あり |
