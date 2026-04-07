from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_local_env(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_local_path(raw_path: str) -> str:
    path = Path(raw_path)
    if path.is_absolute():
        return str(path)
    return str((BASE_DIR / path).resolve())


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    google_sheet_name: str
    google_worksheet_name: str
    google_service_account_json: str
    poll_interval_seconds: int
    offset_file: str
    apify_api_token: str
    apify_profile_actor_id: str
    apify_reel_actor_id: str
    gcs_bucket_name: str
    gcs_avatar_prefix: str


def load_settings() -> Settings:
    load_local_env(BASE_DIR / ".env")
    return Settings(
        telegram_bot_token=os.getenv("TG_TOKEN", ""),
        google_sheet_name=os.getenv("SHEET_NAME", "KOL_Master"),
        google_worksheet_name=os.getenv("WORKSHEET_NAME", "Creator_Master"),
        google_service_account_json=resolve_local_path(
            os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "service_account.json")
        ),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "5")),
        offset_file=resolve_local_path(os.getenv("OFFSET_FILE", ".telegram_offset")),
        apify_api_token=os.getenv("APIFY_API_TOKEN", ""),
        apify_profile_actor_id=os.getenv("APIFY_PROFILE_ACTOR_ID", "dSCLg0C3YEZ83HzYX"),
        apify_reel_actor_id=os.getenv("APIFY_REEL_ACTOR_ID", "apify~instagram-reel-scraper"),
        gcs_bucket_name=os.getenv("GCS_BUCKET_NAME", "").strip(),
        gcs_avatar_prefix=os.getenv("GCS_AVATAR_PREFIX", "avatars").strip().strip("/"),
    )

