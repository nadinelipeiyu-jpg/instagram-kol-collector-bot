from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from .config import Settings
from .integrations import (
    ApifyClient,
    GCSAvatarStorage,
    SheetsRepository,
    TelegramClient,
    load_offset,
    save_offset,
)
from .models import CreatorRecord, count_bio_links
from .parsing import build_instagram_profile_url, extract_first_instagram_url


class BotApp:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.telegram = TelegramClient(settings)
        self.apify = ApifyClient(settings)
        self.storage = GCSAvatarStorage(settings)
        self.sheets = SheetsRepository(settings)

    def validate_env(self) -> None:
        missing = []
        if not self.settings.telegram_bot_token:
            missing.append("TG_TOKEN")
        if not self.settings.apify_api_token:
            missing.append("APIFY_API_TOKEN")
        if not self.settings.gcs_bucket_name:
            missing.append("GCS_BUCKET_NAME")
        has_json_content = bool(self.settings.google_service_account_json_content)
        has_json_file = Path(self.settings.google_service_account_json).exists()
        if not has_json_content and not has_json_file:
            missing.append(
                "GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT (env var) 或 service_account.json (本地檔案) 擇一"
            )
        if missing:
            raise RuntimeError("缺少必要設定：\n- " + "\n- ".join(missing))

    def run(self) -> None:
        self.validate_env()
        self.sheets.get_worksheet()
        offset = load_offset(self.settings.offset_file)
        print("Bot started. Polling Telegram...")

        while True:
            try:
                data = self.telegram.get_updates(offset=offset)
                if not data.get("ok"):
                    print("Telegram API returned not ok:", data)
                    time.sleep(self.settings.poll_interval_seconds)
                    continue

                for update in data.get("result", []):
                    update_id = update["update_id"]
                    offset = update_id + 1
                    save_offset(self.settings.offset_file, offset)

                    message = update.get("message") or update.get("edited_message")
                    if not message:
                        continue

                    print("Received message:", message.get("text", ""))
                    self.handle_message(message)

            except KeyboardInterrupt:
                print("Stopped by user.")
                break
            except Exception as exc:
                print("Loop error:", exc)
                time.sleep(self.settings.poll_interval_seconds)

    def handle_message(self, message: dict) -> None:
        chat_id = (message.get("chat") or {}).get("id")
        text = message.get("text", "")
        if not chat_id:
            return

        url = extract_first_instagram_url(text)
        if not url:
            self.telegram.send_message(chat_id, "請貼上 Instagram 主頁或 Reel 連結。")
            return

        try:
            record = self._enrich_record(self.apify.fetch_instagram_record(url))
            status, _ = self.sheets.upsert_record(record)
            self.telegram.send_message(chat_id, self._format_summary(record, status))
        except Exception as exc:
            self.telegram.send_message(chat_id, f"❌ 處理失敗：{exc}")

    def backfill_missing_avatars(self) -> tuple[int, int]:
        self.validate_env()
        updated = 0
        skipped = 0
        for row_index, row in self.sheets.iter_rows():
            current = row + [""] * (13 - len(row))
            username = current[2].strip().lower()
            avatar_formula = current[4].strip()
            if avatar_formula:
                continue
            if not username or username.startswith("reel_"):
                skipped += 1
                continue

            try:
                profile_url = current[3].strip() or build_instagram_profile_url(username)
                record = self._enrich_record(self.apify.fetch_profile(profile_url))
                self.sheets.update_avatar_formula(
                    row_index,
                    f'=IMAGE("{record.avatar_url}")' if record.avatar_url else "",
                )
                updated += 1
            except Exception:
                skipped += 1

        return updated, skipped

    def _enrich_record(self, record: CreatorRecord) -> CreatorRecord:
        avatar_url = self.storage.upload_avatar(record.username, record.avatar_url)
        record.avatar_url = avatar_url
        if not record.created_at:
            record.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return record

    @staticmethod
    def _format_summary(record: CreatorRecord, status: str) -> str:
        avatar_status = "獲取成功" if record.avatar_url else "未找到"
        email_status = "獲取成功" if record.email_from_bio else "未找到"
        bio_link_count = count_bio_links(record.bio_links)
        return (
            f"✅ 已{'更新' if status == 'updated' else '收錄'}到 Google Sheet\n\n"
            f"👤 @{record.username}\n"
            f"👥 粉絲數：{int(record.followers or 0):,}\n"
            f"🖼️ 頭像：{avatar_status}\n"
            f"🔗 主頁：{record.profile_url or '未找到'}\n"
            f"📌 類型：{record.source_type}\n"
            f"📝 Bio：{record.bio or '未提供'}\n"
            f"📩 信箱：{email_status}\n"
            f"🌐 多連結：獲取到{bio_link_count}條"
        )

