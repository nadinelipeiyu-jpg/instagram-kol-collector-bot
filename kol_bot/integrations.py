from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import gspread
import requests
from google.cloud import storage
from google.oauth2.service_account import Credentials

from .config import Settings
from .models import CreatorRecord
from .parsing import (
    build_instagram_profile_url,
    detect_source_type,
    extract_bio_links,
    extract_email_from_bio,
    parse_shortcode_from_url,
    parse_username_from_url,
)

LEGACY_HEADERS = [
    "created_at",
    "updated_at",
    "platform",
    "source_type",
    "source_url",
    "username",
    "display_name",
    "bio",
    "followers",
    "email_from_bio",
    "has_email_in_bio",
    "notes",
]

CURRENT_HEADERS = [
    "建立時間",
    "更新時間",
    "平台",
    "來源類型",
    "來源連結",
    "帳號",
    "主頁連結",
    "名稱",
    "Bio",
    "多連結",
    "粉絲數",
    "Bio Email",
    "Bio 有 Email",
    "頭像圖片",
    "備註",
]

SHEET_HEADERS = [
    "建立時間",
    "平台",
    "帳號",
    "主頁連結",
    "頭像圖片",
    "名稱",
    "粉絲數",
    "Email",
    "Bio",
    "多連結",
    "備註",
    "來源類型",
    "來源連結",
]


class TelegramClient:
    def __init__(self, settings: Settings) -> None:
        self.api_base = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

    def get_updates(self, offset: Optional[int] = None, timeout: int = 20) -> dict:
        params = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        response = requests.get(f"{self.api_base}/getUpdates", params=params, timeout=timeout + 10)
        response.raise_for_status()
        return response.json()

    def send_message(self, chat_id: int, text: str) -> None:
        response = requests.post(
            f"{self.api_base}/sendMessage",
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            timeout=20,
        )
        response.raise_for_status()


class GCSAvatarStorage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: storage.Client | None = None

    def upload_avatar(self, username: str, avatar_url: str) -> str:
        if not avatar_url or not self.settings.gcs_bucket_name:
            return avatar_url

        response = requests.get(avatar_url, timeout=30)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        ext = self._guess_image_extension(avatar_url, content_type)
        safe_username = re.sub(r"[^a-zA-Z0-9_.-]", "_", username or "unknown")
        prefix = self.settings.gcs_avatar_prefix
        object_name = f"{prefix}/{safe_username}{ext}" if prefix else f"{safe_username}{ext}"

        bucket = self._get_client().bucket(self.settings.gcs_bucket_name)
        blob = bucket.blob(object_name)
        blob.cache_control = "public, max-age=604800"
        blob.upload_from_string(response.content, content_type=content_type or "image/jpeg")
        return f"https://storage.googleapis.com/{self.settings.gcs_bucket_name}/{object_name}"

    def _get_client(self) -> storage.Client:
        if self._client is None:
            self._client = storage.Client.from_service_account_json(
                self.settings.google_service_account_json
            )
        return self._client

    @staticmethod
    def _guess_image_extension(url: str, content_type: str) -> str:
        if content_type:
            if "png" in content_type:
                return ".png"
            if "webp" in content_type:
                return ".webp"
            if "gif" in content_type:
                return ".gif"
        lowered = url.lower()
        for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            if ext in lowered:
                return ext
        return ".jpg"


class SheetsRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._worksheet = None

    def get_worksheet(self):
        if self._worksheet is not None:
            return self._worksheet

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(
            self.settings.google_service_account_json,
            scopes=scopes,
        )
        gc = gspread.authorize(creds)
        sh = gc.open(self.settings.google_sheet_name)
        try:
            ws = sh.worksheet(self.settings.google_worksheet_name)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=self.settings.google_worksheet_name, rows=1000, cols=20)
        self._ensure_header(ws)
        self._worksheet = ws
        return ws

    def find_row_by_username(self, username: str) -> Optional[int]:
        values = self.get_worksheet().get_all_values()
        for idx, row in enumerate(values[1:], start=2):
            if len(row) >= 4 and row[3].strip().lower() == username.lower():
                return idx
        return None

    def upsert_record(self, record: CreatorRecord) -> tuple[str, int]:
        ws = self.get_worksheet()
        row_index = self.find_row_by_username(record.username)
        row = self._build_sheet_row(record)

        if row_index is None:
            ws.append_row(row, value_input_option="USER_ENTERED")
            return "inserted", ws.row_count

        existing_created_at = ws.cell(row_index, 1).value
        row[0] = existing_created_at
        ws.update(
            values=[row],
            range_name=f"A{row_index}:M{row_index}",
            value_input_option="USER_ENTERED",
        )
        return "updated", row_index

    def iter_rows(self) -> list[tuple[int, list[str]]]:
        values = self.get_worksheet().get_all_values()
        return list(enumerate(values[1:], start=2))

    def update_avatar_formula(self, row_index: int, avatar_formula: str) -> None:
        self.get_worksheet().update(
            values=[[avatar_formula]],
            range_name=f"E{row_index}",
            value_input_option="USER_ENTERED",
        )

    def _ensure_header(self, ws) -> None:
        row1 = ws.row_values(1)
        if row1 == SHEET_HEADERS:
            return
        if row1 == LEGACY_HEADERS:
            self._migrate_legacy_sheet(ws)
            return
        if row1 == CURRENT_HEADERS:
            self._migrate_current_sheet(ws)
            return
        ws.update(values=[SHEET_HEADERS], range_name="A1:M1", value_input_option="USER_ENTERED")

    def _migrate_legacy_sheet(self, ws) -> None:
        values = ws.get_all_values()
        migrated_rows = [SHEET_HEADERS]
        for row in values[1:]:
            legacy = row + [""] * (len(LEGACY_HEADERS) - len(row))
            username = legacy[5].strip().lower()
            bio = legacy[7]
            migrated_rows.append(
                self._build_sheet_row_from_mapping(
                    {
                        "created_at": legacy[0],
                        "platform": legacy[2],
                        "source_type": legacy[3],
                        "username": username,
                        "profile_url": build_instagram_profile_url(username),
                        "display_name": legacy[6],
                        "followers": legacy[8],
                        "email_from_bio": legacy[9],
                        "bio": bio,
                        "bio_links": extract_bio_links(bio),
                        "notes": legacy[11],
                        "source_url": legacy[4],
                    }
                )
            )
        ws.clear()
        ws.update(values=migrated_rows, range_name=f"A1:M{len(migrated_rows)}", value_input_option="USER_ENTERED")

    def _migrate_current_sheet(self, ws) -> None:
        values = ws.get_all_values()
        migrated_rows = [SHEET_HEADERS]
        for row in values[1:]:
            current = row + [""] * (len(CURRENT_HEADERS) - len(row))
            migrated_rows.append(
                self._build_sheet_row_from_mapping(
                    {
                        "created_at": current[0],
                        "platform": current[2],
                        "source_type": current[3],
                        "username": current[5],
                        "profile_url": current[6],
                        "avatar_formula": current[13],
                        "display_name": current[7],
                        "followers": current[10],
                        "email_from_bio": current[11],
                        "bio": current[8],
                        "bio_links": current[9],
                        "notes": current[14],
                        "source_url": current[4],
                    }
                )
            )
        ws.clear()
        ws.update(values=migrated_rows, range_name=f"A1:M{len(migrated_rows)}", value_input_option="USER_ENTERED")

    def _build_sheet_row(self, record: CreatorRecord) -> list[str]:
        return self._build_sheet_row_from_mapping(
            {
                "created_at": record.created_at,
                "platform": record.platform,
                "username": record.username,
                "profile_url": record.profile_url,
                "avatar_url": record.avatar_url,
                "display_name": record.display_name,
                "followers": record.followers,
                "email_from_bio": record.email_from_bio,
                "bio": record.bio,
                "bio_links": record.bio_links,
                "notes": record.notes,
                "source_type": record.source_type,
                "source_url": record.source_url,
            }
        )

    @staticmethod
    def _build_sheet_row_from_mapping(record: dict) -> list[str]:
        avatar_formula = record.get("avatar_formula")
        if not avatar_formula:
            avatar_url = record.get("avatar_url", "")
            avatar_formula = f'=IMAGE("{avatar_url}")' if avatar_url else ""
        return [
            record.get("created_at", ""),
            record.get("platform", "instagram"),
            record.get("username", ""),
            record.get("profile_url", ""),
            avatar_formula,
            record.get("display_name", ""),
            str(record.get("followers", "")),
            record.get("email_from_bio", ""),
            record.get("bio", ""),
            record.get("bio_links", ""),
            record.get("notes", ""),
            record.get("source_type", "profile"),
            record.get("source_url", ""),
        ]


class ApifyClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def fetch_instagram_record(self, url: str) -> CreatorRecord:
        if detect_source_type(url) == "profile":
            return self.fetch_profile(url)
        return self.fetch_reel(url)

    def fetch_profile(self, url: str) -> CreatorRecord:
        username = parse_username_from_url(url)
        if not username:
            raise ValueError("無法從 profile URL 解析 username")

        last_error = None
        payload_candidates = [
            {"usernames": [username], "resultsType": "details", "resultsLimit": 1},
            {"usernames": [username]},
            {"username": username},
        ]

        for payload in payload_candidates:
            try:
                items = self._run_sync(self.settings.apify_profile_actor_id, payload)
                if items:
                    return self._normalize_profile_record(url, items[0])
            except Exception as exc:
                last_error = exc

        if last_error:
            raise RuntimeError(f"profile actor 失敗：{last_error}")
        raise RuntimeError("Apify 沒有找到這個 Instagram profile")

    def fetch_reel(self, url: str) -> CreatorRecord:
        reel_item = self._fetch_reel_raw(url)
        owner_username = (reel_item.get("ownerUsername") or reel_item.get("username") or "").strip().lower()

        if owner_username:
            profile_url = build_instagram_profile_url(owner_username)
            try:
                profile_record = self.fetch_profile(profile_url)
                likes = reel_item.get("likesCount") or reel_item.get("likeCount") or 0
                comments = reel_item.get("commentsCount") or reel_item.get("commentCount") or 0
                timestamp = reel_item.get("timestamp") or reel_item.get("publishedAt") or ""
                profile_record.source_type = "reel"
                profile_record.source_url = url
                profile_record.notes = (
                    f"reel + profile | ownerUsername={owner_username}, "
                    f"likes={likes}, comments={comments}, timestamp={timestamp}"
                )
                return profile_record
            except Exception as exc:
                raw_record = self._normalize_reel_record(url, reel_item)
                raw_record.notes = f"{raw_record.notes} | profile_fetch_failed={str(exc)[:180]}"
                return raw_record

        return self._normalize_reel_record(url, reel_item)

    def _fetch_reel_raw(self, url: str) -> dict:
        errors: list[str] = []
        for payload in [{"username": [url], "resultsLimit": 1}, {"username": [url]}]:
            try:
                items = self._run_sync(self.settings.apify_reel_actor_id, payload)
                if items:
                    return items[0]
            except Exception as exc:
                errors.append(f"payload={payload} -> {exc}")
        if errors:
            raise RuntimeError(f"reel actor 失敗：{errors[-1]}")
        raise RuntimeError("Apify 沒有找到這支 Reel")

    def _run_sync(self, actor_id: str, payload: dict) -> list:
        if not self.settings.apify_api_token:
            raise RuntimeError("缺少 APIFY_API_TOKEN")
        if not actor_id:
            raise RuntimeError("缺少 Apify actor id")

        response = requests.post(
            f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items",
            json=payload,
            headers={"Authorization": f"Bearer {self.settings.apify_api_token}"},
            timeout=180,
        )
        if response.status_code == 401:
            raise RuntimeError("Apify token 無效")
        if response.status_code == 402:
            raise RuntimeError("Apify credits 不足")
        if response.status_code == 404:
            raise RuntimeError(f"找不到 Apify actor：{actor_id}")
        if response.status_code == 400:
            raise RuntimeError(f"Apify 請求格式錯誤：{response.text[:500]}")
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise RuntimeError("Apify 回傳格式異常")
        return data

    @staticmethod
    def _normalize_profile_record(url: str, item: dict) -> CreatorRecord:
        username = (item.get("username") or item.get("ownerUsername") or "").strip().lower()
        if not username:
            raise RuntimeError("Profile actor 沒有回傳 username")

        bio = item.get("biography") or item.get("bio") or item.get("description") or ""
        email = extract_email_from_bio(bio)
        return CreatorRecord(
            platform="instagram",
            source_type="profile",
            source_url=url,
            username=username,
            profile_url=build_instagram_profile_url(username),
            display_name=item.get("fullName") or item.get("full_name") or item.get("name") or username,
            followers=item.get("followersCount") or item.get("followers") or 0,
            email_from_bio=email or "",
            has_email_in_bio=bool(email),
            avatar_url=(
                item.get("profilePicHd")
                or item.get("profilePicUrlHD")
                or item.get("profilePicUrl")
                or item.get("profilePictureUrl")
                or item.get("profile_picture_url")
                or ""
            ),
            bio=bio,
            bio_links=extract_bio_links(
                bio,
                item.get("bioLinks") or item.get("links") or item.get("externalUrls") or item.get("external_urls"),
            ),
            notes="Apify profile actor",
        )

    @staticmethod
    def _normalize_reel_record(url: str, item: dict) -> CreatorRecord:
        username = (item.get("ownerUsername") or item.get("username") or "").strip().lower()
        shortcode = parse_shortcode_from_url(url) or "unknown"
        if not username:
            username = f"reel_{shortcode.lower()}"
        full_name = item.get("ownerFullName") or item.get("fullName") or username
        likes = item.get("likesCount") or item.get("likeCount") or 0
        comments = item.get("commentsCount") or item.get("commentCount") or 0
        timestamp = item.get("timestamp") or item.get("publishedAt") or ""
        caption = item.get("caption") or ""
        return CreatorRecord(
            platform="instagram",
            source_type="reel",
            source_url=url,
            username=username,
            profile_url=build_instagram_profile_url(username) if not username.startswith("reel_") else "",
            display_name=full_name,
            followers=0,
            email_from_bio="",
            has_email_in_bio=False,
            avatar_url="",
            bio="",
            bio_links="",
            notes=(
                f"Reel actor raw only | likes={likes}, comments={comments}, "
                f"timestamp={timestamp}, caption_len={len(caption)}"
            ),
        )


def load_offset(offset_file: str) -> Optional[int]:
    path = Path(offset_file)
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def save_offset(offset_file: str, offset: int) -> None:
    Path(offset_file).write_text(str(offset), encoding="utf-8")

