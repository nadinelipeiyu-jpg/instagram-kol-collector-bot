# KOL Bot

Telegram bot for collecting Instagram creator data into Google Sheets.

It accepts Instagram profile or reel URLs in Telegram, resolves creator data through Apify, uploads avatars to Google Cloud Storage, and writes a normalized row into Google Sheets.

## Features

- Accept Instagram `profile` and `reel` links from Telegram
- Extract creator profile, follower count, bio, email, and bio links
- Upload avatar images to Google Cloud Storage for stable Google Sheets rendering
- Write data into a Google Sheet with a fixed Chinese header schema
- Backfill missing avatar images for existing rows
- Run as a local process or macOS `launchd` service

## Project Structure

```text
kol-bot/
├── kol_bot/
│   ├── app.py
│   ├── cli.py
│   ├── config.py
│   ├── integrations.py
│   ├── models.py
│   └── parsing.py
├── telegram_kol_mvp_bot.py
├── run_bot.sh
├── com.nadine.kolbot.plist
├── requirements.txt
└── .env.example
```

## Sheet Schema

The bot maintains this column order:

```text
建立時間 / 平台 / 帳號 / 主頁連結 / 頭像圖片 / 名稱 / 粉絲數 / Email / Bio / 多連結 / 備註 / 來源類型 / 來源連結
```

## Requirements

- Python 3.11+
- Telegram bot token
- Apify API token
- Google service account JSON with:
  - Google Sheets write access
  - Google Drive access for spreadsheet lookup
  - Google Cloud Storage write access for avatar uploads
- A public Google Cloud Storage bucket for avatar hosting

## Setup

1. Create a virtualenv and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Copy the environment template:

```bash
cp .env.example .env
```

3. Fill `.env`:

```env
TG_TOKEN=your-telegram-bot-token
APIFY_API_TOKEN=your-apify-token
SHEET_NAME=KOL_Master
WORKSHEET_NAME=Creator_Master
GOOGLE_SERVICE_ACCOUNT_JSON=service_account.json
POLL_INTERVAL_SECONDS=5
OFFSET_FILE=.telegram_offset
APIFY_PROFILE_ACTOR_ID=dSCLg0C3YEZ83HzYX
APIFY_REEL_ACTOR_ID=apify~instagram-reel-scraper
GCS_BUCKET_NAME=your-public-bucket
GCS_AVATAR_PREFIX=avatars
```

4. Put your Google service account file at:

```text
./service_account.json
```

## Google Cloud Storage Notes

`IMAGE()` in Google Sheets requires a publicly readable image URL.

Make sure your bucket:

- exists
- allows object uploads by your service account
- allows public object reads for `allUsers` with `Storage Object Viewer`

Example public object URL:

```text
https://storage.googleapis.com/<bucket>/avatars/<username>.jpg
```

## Usage

Run the bot:

```bash
source venv/bin/activate
python telegram_kol_mvp_bot.py
```

Or:

```bash
source venv/bin/activate
python -m kol_bot.cli run
```

Backfill missing avatars:

```bash
source venv/bin/activate
python -m kol_bot.cli backfill-avatars
```

## Telegram Reply Format

The bot replies with:

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

## macOS Auto Start

The repository includes:

- `run_bot.sh`
- `com.nadine.kolbot.plist`

Install with:

```bash
mkdir -p ~/Library/LaunchAgents
cp com.nadine.kolbot.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.nadine.kolbot.plist
launchctl start com.nadine.kolbot
```

Logs:

```bash
tail -f bot.stdout.log
tail -f bot.stderr.log
```

## GitHub Publishing Checklist

Before pushing to GitHub:

- keep `.env` out of git
- keep `service_account.json` out of git
- keep logs and offsets out of git
- confirm the bucket name in `.env.example` is only a placeholder
- rotate any token that has already been pasted into shared history

## Recommended Next Steps

- add unit tests for parsing and sheet row building
- add structured logging
- add retry/backoff around Apify and GCS operations
- move secrets to a dedicated secret manager if you deploy beyond local use
