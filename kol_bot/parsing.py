from __future__ import annotations

import re
from typing import Optional

INSTAGRAM_URL_RE = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:(?:reel|reels|p)/[A-Za-z0-9_-]+/?|[A-Za-z0-9_.]+/?)(?:\?[^\s]+)?",
    re.IGNORECASE,
)
PROFILE_URL_RE = re.compile(
    r"https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)/?(?:\?[^\s]+)?$",
    re.IGNORECASE,
)
REEL_URL_RE = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:reel|reels|p)/([A-Za-z0-9_-]+)/?(?:\?[^\s]+)?$",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
URL_RE = re.compile(
    r"(?:(?:https?://|www\.)[^\s]+|(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?:/[^\s]*)?)",
    re.IGNORECASE,
)


def extract_first_instagram_url(text: str) -> Optional[str]:
    match = INSTAGRAM_URL_RE.search(text or "")
    return match.group(0) if match else None


def detect_source_type(url: str) -> str:
    if "/reel/" in url or "/reels/" in url or "/p/" in url:
        return "reel"
    return "profile"


def parse_username_from_url(url: str) -> Optional[str]:
    if detect_source_type(url) != "profile":
        return None
    match = PROFILE_URL_RE.match(url)
    if not match:
        return None
    username = match.group(1).strip().lower()
    if username in {"reel", "reels", "p", "explore"}:
        return None
    return username


def parse_shortcode_from_url(url: str) -> Optional[str]:
    match = REEL_URL_RE.match(url)
    return match.group(1) if match else None


def extract_email_from_bio(bio: str) -> Optional[str]:
    match = EMAIL_RE.search(bio or "")
    return match.group(0) if match else None


def normalize_url(raw: str) -> str:
    url = raw.strip().rstrip(".,;:!?)]")
    if url.startswith(("http://", "https://")):
        return url
    return f"https://{url}"


def extract_urls(text: str) -> list[str]:
    text = EMAIL_RE.sub(" ", text or "")
    urls: list[str] = []
    seen: set[str] = set()
    for match in URL_RE.findall(text):
        if "@" in match and not match.startswith(("http://", "https://", "www.")):
            continue
        url = normalize_url(match)
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def build_instagram_profile_url(username: str) -> str:
    username = (username or "").strip().lower()
    return f"https://www.instagram.com/{username}/" if username else ""


def extract_bio_links(bio: str, extra_links: Optional[list] = None) -> str:
    urls = extract_urls(bio)

    for link in extra_links or []:
        if isinstance(link, str):
            urls.extend(extract_urls(link))
            continue
        if isinstance(link, dict):
            candidate = (
                link.get("url")
                or link.get("link")
                or link.get("href")
                or link.get("title")
                or link.get("text")
                or ""
            )
            urls.extend(extract_urls(candidate))

    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return "\n".join(deduped)

