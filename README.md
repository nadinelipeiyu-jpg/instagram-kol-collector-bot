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
- 支援本機啟動與 macOS `launchd` 常駐執行

## 專案結構

```text
kol-bot/
├── kol_bot/
│   ├── app.py              # Bot 主流程
│   ├── cli.py              # CLI 入口
│   ├── config.py           # 環境變數與設定載入
│   ├── integrations.py     # Telegram / Sheets / GCS / Apify 整合
│   ├── models.py           # 資料模型
│   └── parsing.py          # Instagram URL / Bio 解析
├── telegram_kol_mvp_bot.py # 相容入口
├── run_bot.sh              # 啟動腳本
├── com.kolbot.agent.plist  # macOS launchd 設定
├── requirements.txt
└── .env.example
```

## Google Sheet 欄位順序

目前 Sheet 表頭固定為：

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

## 安裝方式

### 1. 建立虛擬環境

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 建立環境變數檔

```bash
cp .env.example .env
```

### 3. 填入 `.env`

```env
TG_TOKEN=你的 telegram bot token
APIFY_API_TOKEN=你的 apify token
SHEET_NAME=KOL_Master
WORKSHEET_NAME=Creator_Master
GOOGLE_SERVICE_ACCOUNT_JSON=service_account.json
POLL_INTERVAL_SECONDS=5
OFFSET_FILE=.telegram_offset
APIFY_PROFILE_ACTOR_ID=dSCLg0C3YEZ83HzYX
APIFY_REEL_ACTOR_ID=apify~instagram-reel-scraper
GCS_BUCKET_NAME=你的公開 bucket 名稱
GCS_AVATAR_PREFIX=avatars
```

### 4. 放入 Google Service Account 檔

請將金鑰檔放在專案根目錄：

```text
./service_account.json
```

## 使用方式

### 啟動 Bot

```bash
source venv/bin/activate
python -m kol_bot.cli run
```

也可以使用相容入口：

```bash
source venv/bin/activate
python telegram_kol_mvp_bot.py
```

### 批次補齊缺少頭像的資料

```bash
source venv/bin/activate
python -m kol_bot.cli backfill-avatars
```

## Telegram 回覆格式

Bot 目前回覆格式如下：

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

## Google Cloud Storage 設定重點

頭像圖片要能在 Google Sheets 用 `IMAGE()` 顯示，GCS 物件必須可以被公開讀取。

請確認：

- bucket 已建立
- service account 對 bucket 具有上傳權限
- bucket 允許公開讀取圖片
- 已授予 `allUsers` -> `Storage Object Viewer`

公開圖片網址格式會像這樣：

```text
https://storage.googleapis.com/<bucket>/avatars/<username>.jpg
```

## macOS 自動啟動

專案已附：

- `run_bot.sh`
- `com.kolbot.agent.plist`

安裝方式：

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

## 發佈到 GitHub 前要注意

以下檔案不應該提交：

- `.env`
- `service_account.json`
- `venv/`
- `bot.stdout.log`
- `bot.stderr.log`
- `.telegram_offset`

另外，若任何 token 曾出現在聊天紀錄、截圖或公開環境中，建議立即輪替。

## 建議後續優化

- 增加 parsing 與 row mapping 的單元測試
- 為 Apify / GCS / Telegram 請求補上 retry / backoff
- 加入結構化 logging
- 增加更明確的錯誤分類與回報
- 若未來要正式部署，可把 secrets 移到 Secret Manager
