from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CreatorRecord:
    platform: str
    source_type: str
    source_url: str
    username: str
    profile_url: str
    display_name: str
    followers: int | str
    email_from_bio: str
    has_email_in_bio: bool
    avatar_url: str
    bio: str
    bio_links: str
    notes: str
    created_at: str = ""


def count_bio_links(bio_links: str) -> int:
    return len([line for line in (bio_links or "").splitlines() if line.strip()])

