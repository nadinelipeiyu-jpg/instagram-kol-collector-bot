# Instagram KOL Collector Bot

一個用來蒐集 Instagram KOL / Creator 資料的 Telegram Bot。

使用者只要把 Instagram 個人主頁或 Reel 連結貼到 Telegram，Bot 就會自動：

- 透過 Apify 擷取帳號資料
- 解析粉絲數、Bio、Email、多連結
- 下載並上傳頭像到 Google Cloud Storage
- 將整理後的結果寫入 Google Sheets

這個專案適合用在：

- KOL 蒐集
- Creator 名單整理
- 商務開發名單初步建立
- 社群資料半自動收錄

## 功能特色

- 支援 Instagram `profile` 與 `reel` 連結
- 透過 Telegram 作為輸入介面，操作成本低
- 自動寫入固定欄位順序的 Google Sheet
- 使用 Google Cloud Storage 轉存頭像，避免 Instagram CDN 連結失效
- 在 Google Sheets 內直接顯示頭像圖片
- 可批次補齊既有資料中缺少的頭像
- **支援 Cloud Run Webhook 模式，不需要電腦長期開著**

## 專案結構

```text
kol-bot/
├── kol_bot/
│   ├── app.py              # Bot 主流程
│   ├── cli.py              # CLI 入口（run / serve / backfill-avatars）
│   ├── config.py           # 環境變數與設定載入
│   ├── integrations.py     # Telegram / Sheets / GCS / Apify 整合
│   ├── models.py           # 資料模型
│   ├── parsing.py          # Instagram URL / Bio 解析
│   ├── webhook.py          # Flask Webhook Server（Cloud Run 用）
│   └── wsgi.py             # Gunicorn WSGI 入口
├── .github/workflows/
│   └── deploy.yml          # GitHub Actions → 自動部署到 Cloud Run
├── Dockerfile
├── .dockerignore
├── telegram_kol_mvp_bot.py # 相容入口
├── run_bot.sh              # 本機啟動腳本
├── com.kolbot.agent.plist  # macOS launchd 設定（本機）
├── requirements.txt
└── .env.example
```

## Google Sheet 欄位順序

```text
建立時間 / 平台 / 帳號 / 主頁連結 / 頭像圖片 / 名稱 / 粉絲數 / Email / Bio / 多連結 / 備註 / 來源類型 / 來源連結
```

## 系統需求

- Python 3.11 以上
- Telegram Bot Token
- Apify API Token
- Google Service Account JSON
- Google Sheets 寫入權限
- Google Drive 存取權限
- Google Cloud Storage 寫入權限
- 一個可公開讀取圖片的 GCS Bucket

---

## 本機安裝與使用

### 1. 建立虛擬環境

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 建立環境變數檔

```bash
cp .env.example .env
# 填入各項 token 與設定
```

### 3. 放入 Google Service Account 檔

```text
./service_account.json
```

### 4. 啟動 Bot（Polling 模式）

```bash
source venv/bin/activate
python -m kol_bot.cli run
```

### 5. 批次補齊缺少頭像的資料

```bash
python -m kol_bot.cli backfill-avatars
```

---

## 雲端部署（Cloud Run）— 不用開電腦

### 架構說明

| 模式 | 說明 | 適合情境 |
|------|------|---------|
| **Polling**（`run`）| Bot 主動輪詢 Telegram | 本機、macOS launchd |
| **Webhook**（`serve`）| Telegram 主動推送到你的 HTTPS 伺服器 | Cloud Run、Docker |

Cloud Run Webhook 模式：**沒有訊息時費用幾乎是零**（scale-to-zero），每次有人傳連結才喚醒。

---

### 方法一：GitHub Actions 自動部署（推薦）

#### 前置準備

1. **GCP 專案** — 啟用 Cloud Run API、Artifact Registry API、Cloud Build API
2. **Service Account**（兩個）：
   - **部署用 SA**：有 `Cloud Run Admin`、`Artifact Registry Writer`、`Service Account User` 權限，金鑰存為 GitHub Secret `GCP_SA_KEY`（base64：`base64 -w0 key.json`）
   - **Bot 用 SA**：有 Google Sheets / GCS 權限，JSON 內容存為 GCP Secret Manager `GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT`
3. **GCP Secret Manager** — 建立以下 secrets：
   ```
   TG_TOKEN
   APIFY_API_TOKEN
   GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT   ← service_account.json 的完整內容
   ```
4. **GCS Bucket** — 建立並開放公開讀取（`allUsers` Storage Object Viewer）

#### GitHub Secrets 設定

在 GitHub Repo → Settings → Secrets → Actions 新增：

| Secret | 說明 |
|--------|------|
| `GCP_SA_KEY` | 部署用 SA 金鑰（base64）|
| `GCP_PROJECT_ID` | GCP 專案 ID |
| `GCS_BUCKET_NAME` | GCS Bucket 名稱 |
| `SHEET_NAME` | Google Sheet 名稱（預設 KOL_Master）|
| `WORKSHEET_NAME` | Worksheet 名稱（預設 Creator_Master）|
| `WEBHOOK_URL` | 第一次部署後填入 Cloud Run URL（見下方）|

#### 部署流程

```bash
git push origin main   # 觸發 GitHub Actions 自動建置並部署
```

**第一次部署後**：

1. 到 GCP Console → Cloud Run 複製服務 URL（格式：`https://kol-bot-xxxx-de.a.run.app`）
2. 將此 URL 填入 GitHub Secret `WEBHOOK_URL`
3. 再推送一次 `git push origin main` 讓 Bot 向 Telegram 註冊 Webhook

---

### 方法二：手動 Docker 部署

#### 建立映像檔並本機測試

```bash
# 建置
docker build -t kol-bot .

# 本機測試（使用 .env 檔）
docker run --rm \
  --env-file .env \
  -e GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT="$(cat service_account.json)" \
  -p 8080:8080 \
  kol-bot
```

#### 推送到 Cloud Run（手動）

```bash
PROJECT_ID=你的_gcp_project_id
REGION=asia-east1

# 設定認證
gcloud auth configure-docker $REGION-docker.pkg.dev

# 建立 Artifact Registry repo（只需一次）
gcloud artifacts repositories create kol-bot \
  --repository-format=docker \
  --location=$REGION

# 建置並推送
IMAGE=$REGION-docker.pkg.dev/$PROJECT_ID/kol-bot/kol-bot:latest
docker build -t $IMAGE .
docker push $IMAGE

# 部署
gcloud run deploy kol-bot \
  --image $IMAGE \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 1 \
  --memory 512Mi \
  --timeout 300 \
  --set-env-vars "GCS_BUCKET_NAME=你的bucket,SHEET_NAME=KOL_Master,WEBHOOK_URL=https://kol-bot-xxxx-de.a.run.app" \
  --set-secrets "TG_TOKEN=TG_TOKEN:latest,APIFY_API_TOKEN=APIFY_API_TOKEN:latest,GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT=GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT:latest"
```

---

### 設定 Telegram Webhook（手動）

如果自動註冊沒生效，可手動設定：

```bash
curl "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://kol-bot-xxxx-de.a.run.app/webhook/<YOUR_TOKEN>"
```

確認狀態：

```bash
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo"
```

---

## Google Cloud Storage 設定重點

頭像圖片要能在 Google Sheets 用 `IMAGE()` 顯示，GCS 物件必須可以被公開讀取。

請確認：

- bucket 已建立
- service account 對 bucket 具有上傳權限
- bucket 允許公開讀取圖片：`allUsers` → `Storage Object Viewer`

公開圖片網址格式：

```text
https://storage.googleapis.com/<bucket>/avatars/<username>.jpg
```

---

## macOS 本機自動啟動（launchd）

```bash
mkdir -p ~/Library/LaunchAgents
cp com.kolbot.agent.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.kolbot.agent.plist
launchctl start com.kolbot.agent
```

查看 log：

```bash
tail -f bot.stdout.log
tail -f bot.stderr.log
```

---

## 發佈到 GitHub 前要注意

以下檔案不應該提交：

- `.env`
- `service_account.json`
- `venv/`
- `bot.stdout.log`
- `bot.stderr.log`
- `.telegram_offset`

若任何 token 曾出現在聊天紀錄、截圖或公開環境中，建議立即輪替。

## Telegram 回覆格式

```text
✅ 已收錄到 Google Sheet

👤 @帳號名稱
👥 粉絲數：
🖼️ 頭像：獲取成功
🔗 主頁：主頁連結
📌 類型：
📝 Bio：
📩 信箱：獲取成功
🌐 多連結：獲取到N條
```
