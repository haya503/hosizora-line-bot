# Cloud Scheduler で定期通知を時刻どおりに起動する

GitHub Actions の定期実行（`schedule`）は、数時間遅れたり、予約した回数より大幅に少なくしか起動しなかったりします。
そこで Google Cloud の Cloud Scheduler から、GitHub API でワークフロー（`notify.yml`）を毎日決まった時刻に起動します。

- Cloud Scheduler からの起動は `scheduled=true` を付けた `workflow_dispatch` です。ワークフローは GitHub の定期実行と同じ「自動実行」として扱います
- 自動実行は 1 日 1 回だけ通知します（日付ごとの通知済みマーカーで判定）。そのため、Cloud Scheduler を 1 日に複数回起動しても、GitHub の定期実行（予備として残しています）が後から起動しても、二重には届きません
- Cloud Scheduler からの 19:00 JST より前の起動で気象データの取得に失敗した場合は、失敗を通知せず、次の起動（18:00・19:00）でやり直します。GitHub の定期実行は次の起動が当てにならないので、その場で失敗を Discord に通知します

## 1. GitHub のトークンを作る

1. GitHub の Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token
2. 次のように設定します
   - Token name: `hosizora-cloud-scheduler` など
   - Expiration: 任意（期限が切れると通知が止まるので、期限前に作り直してください）
   - Repository access: **Only select repositories** → `hosizora-line-bot`
   - Permissions → Repository permissions → **Actions: Read and write**（ほかは不要）
3. 表示されたトークン（`github_pat_...`）を控えます

## 2. Cloud Scheduler のジョブを作る

Cloud Shell などで、次のコマンドを実行します。`PROJECT_ID` を GCP のプロジェクト ID（Cloud Run と同じもの）に置き換えてください。
`GITHUB_TOKEN` はコマンド履歴に残らないように `read -s` で入力します。

```bash
PROJECT_ID=your-project-id
read -s -p "GitHub token: " GITHUB_TOKEN; echo

gcloud services enable cloudscheduler.googleapis.com --project "$PROJECT_ID"

gcloud scheduler jobs create http hosizora-notify \
  --project "$PROJECT_ID" \
  --location asia-northeast1 \
  --schedule "0 17-19 * * *" \
  --time-zone "Asia/Tokyo" \
  --uri "https://api.github.com/repos/haya503/hosizora-line-bot/actions/workflows/notify.yml/dispatches" \
  --http-method POST \
  --headers "Authorization=Bearer ${GITHUB_TOKEN},Accept=application/vnd.github+json,X-GitHub-Api-Version=2022-11-28,Content-Type=application/json" \
  --message-body '{"ref":"master","inputs":{"scheduled":"true"}}'
```

- `--schedule "0 17-19 * * *"` は 17:00・18:00・19:00 JST に起動します。通知されるのは 17:00 の 1 回だけで、18:00・19:00 は 17:00 の取得に失敗したときの再試行用です
- 通知時刻を変えたいときは `--schedule` を変えます（例: 16:30 にするなら `"30 16,17,18 * * *"`）。ただし `.github/workflows/notify.yml` の `NOTIFY_START_HOUR_JST`（16）より前の時刻にすると、その起動はスキップされます
- トークンは Cloud Scheduler のジョブ設定にヘッダーとして保存され、このプロジェクトでジョブを閲覧できる人には見えます。権限は Actions の実行だけに絞ってあります

## 3. 動作確認

```bash
gcloud scheduler jobs run hosizora-notify --project "$PROJECT_ID" --location asia-northeast1
```

GitHub の Actions タブに `workflow_dispatch` の実行が現れれば成功です。

- 16:00 JST 以降で、その日まだ通知していなければ、LINE に予報が届きます
- 16:00 JST より前や通知済みの日は、`check` ジョブだけが動いて送信はスキップされます

起動の記録は `gcloud scheduler jobs describe hosizora-notify --project "$PROJECT_ID" --location asia-northeast1` の `status` や、Cloud Logging で確認できます。
GitHub API が 401 を返す場合はトークンの期限切れか権限不足です。トークンを作り直したら、次のコマンドでヘッダーを更新します。

```bash
read -s -p "GitHub token: " GITHUB_TOKEN; echo
gcloud scheduler jobs update http hosizora-notify \
  --project "$PROJECT_ID" --location asia-northeast1 \
  --update-headers "Authorization=Bearer ${GITHUB_TOKEN}"
```
