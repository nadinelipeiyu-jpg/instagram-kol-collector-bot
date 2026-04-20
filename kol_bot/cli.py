from __future__ import annotations

import argparse
import logging

from .app import BotApp
from .config import load_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Instagram KOL Telegram bot")
    subparsers = parser.add_subparsers(dest="command", required=False)

    subparsers.add_parser("run", help="Start the Telegram polling bot (local / always-on)")
    subparsers.add_parser("serve", help="Start webhook HTTP server (Cloud Run / Docker)")
    subparsers.add_parser("backfill-avatars", help="Backfill missing avatar images in Google Sheets")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    command = args.command or "run"

    settings = load_settings()
    app = BotApp(settings)

    if command == "backfill-avatars":
        updated, skipped = app.backfill_missing_avatars()
        print(f"updated={updated} skipped={skipped}")
        return

    if command == "serve":
        _serve(app, settings)
        return

    app.run()


def _serve(app: BotApp, settings) -> None:
    from .webhook import create_webhook_app

    logger = logging.getLogger(__name__)

    app.validate_env()
    app.sheets.get_worksheet()

    if settings.webhook_url:
        webhook_endpoint = f"{settings.webhook_url}/webhook/{settings.telegram_bot_token}"
        app.telegram.set_webhook(webhook_endpoint)
    else:
        logger.warning(
            "WEBHOOK_URL not set — Telegram will not know where to send updates. "
            "Set WEBHOOK_URL to the public HTTPS URL of this service."
        )

    flask_app = create_webhook_app(app, settings)
    logger.info("Starting webhook server on port %d", settings.webhook_port)
    # Use threaded=True so slow Apify calls don't block other requests
    flask_app.run(host="0.0.0.0", port=settings.webhook_port, threaded=True)
