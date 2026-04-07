from __future__ import annotations

import argparse

from .app import BotApp
from .config import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Instagram KOL Telegram bot")
    subparsers = parser.add_subparsers(dest="command", required=False)

    subparsers.add_parser("run", help="Start the Telegram polling bot")
    subparsers.add_parser("backfill-avatars", help="Backfill missing avatar images in Google Sheets")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    command = args.command or "run"

    app = BotApp(load_settings())
    if command == "backfill-avatars":
        updated, skipped = app.backfill_missing_avatars()
        print(f"updated={updated} skipped={skipped}")
        return
    app.run()
