# 追加API実装設計: Copernicus CAMS / JPL Horizons / OpenAQ

**日付**: 2026-05-09  
**対象ブランチ**: claude/xenodochial-elbakyan-e26b16

---

## 概要

星空予報LINEボットに以下の3APIを追加し、スコア計算と通知メッセージの両方を強化する。

| API | 提供データ | 用途 |
|---|---|---|
| Copernicus CAMS | AOD（エアロゾル光学的厚さ） | 透明度の定量補正 |
| JPL Horizons | 彗星の位置・等級 | 今夜のポイントに彗星情報を追加 |
| OpenAQ | PM2.5（微小粒子状物質） | 大気汚染によるスコア補正と表示 |

---

## アーキテクチャ

### 新規ファイル

```
src/
  cams_client.py      # Copernicus CAMS AOD取得
  horizons_client.py  # JPL Horizons 彗星データ取得
  openaq_client.py    # OpenAQ PM2.5取得
```

### 既存ファイルへの変更

| ファイル | 変更内容 |
|---|---|
| `src/config.py` | `CAMS_ADS_API_KEY` 環境変数を追加（未設定時は空文字、スキップ） |
| `src/notify.py` | 3クライアント呼び出し追加、`calculate_hourly_score` 拡張、`format_message` 拡張 |

### データフロー

```
既存: sky_forecast → astro_events → 7timer → hoshimiru → usno → jma
追加:
  cams_client   → AOD値（日次、失敗 or キー未設定時: None）
  openaq_client → PM2.5値（最新観測値、失敗時: None）
  horizons_client → 可視彗星リスト（失敗時: 空リスト）
```

すべて失敗時スキップ（既存APIと同パターン）。

---

## スコア計算への統合

### `calculate_hourly_score` シグネチャ変更

```python
# 変更前
def calculate_hourly_score(
    cloud_cover, visibility, seeing, transparency, weather_penalty=0
) -> int

# 変更後
def calculate_hourly_score(
    cloud_cover, visibility, seeing, transparency,
    weather_penalty=0, aod=None, pm25=None
) -> int
```

### ペナルティ基準

| 条件 | スコア変化 | 根拠 |
|---|---|---|
| AOD > 0.4 | −1 | 霞が強く透明度が著しく低下 |
| PM2.5 > 35 μg/m³ | −1 | 環境省「注意喚起」基準 |
| PM2.5 > 75 μg/m³ | −2（合計） | 環境省「健康影響」基準 |

AOD・PM2.5 は日次単位の値のため、全時間帯に同一ペナルティを適用する。

---

## メッセージ表示

### 湿度・風速行への追記

```
💧 湿度: 60%　🌬 風速: 2.3m/s　🏭 PM2.5: 12μg/m³　🌫 AOD: 0.15
```

PM2.5・AOD どちらかが取得できない場合はその項目のみ省略する。

### 彗星を「今夜のポイント」に追加

```
🔭 今夜のポイント:
・木星が南中 22:30（高度 45°）
・C/2023 A3 が見頃 21:00（高度 28°, 等級 6.2）
・ふたご座流星群まであと3日
```

彗星が存在しない場合は追記なし。

---

## 各クライアント仕様

### `cams_client.py`

```python
def fetch_aod(lat: float, lon: float, api_key: str) -> float | None
```

- エンドポイント: CAMS ADS (`cdsapi`) 経由で `cams-global-atmospheric-composition-forecasts` を取得
- パラメータ: `aod550`（550nm AOD）、当日予報、最寄りグリッド点
- 失敗・キー未設定時: `None` を返す
- 環境変数: `CAMS_ADS_API_KEY`（未設定時スキップ）

### `horizons_client.py`

```python
@dataclass
class CometInfo:
    name: str
    best_time: str   # JST "HH:MM"
    altitude: float  # 度
    magnitude: float

def fetch_visible_comets(lat: float, lon: float, date_jst: str) -> list[CometInfo]
```

- エンドポイント: `https://ssd.jpl.nasa.gov/api/horizons.api`
- 対象: コード内定数として保持する明彗星リストを1件ずつ照会
- フィルタ: 等級 ≤ 10 かつ 21〜24時JST に高度 ≥ 10° の時間帯があるもの
- 認証不要

### `openaq_client.py`

```python
def fetch_pm25(lat: float, lon: float) -> float | None
```

- エンドポイント: `https://api.openaq.io/v3/locations` で最寄りステーションを検索し、最新 PM2.5 値を取得
- 失敗時: `None` を返す
- 認証不要

---

## テスト方針

各クライアントに対応するテストファイル（`tests/test_cams_client.py` 等）を追加し、既存テストと同パターン（モック + 正常系・失敗系）で実装する。`calculate_hourly_score` の拡張パラメータについても `tests/test_notify.py` に追加する。
