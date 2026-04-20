from __future__ import annotations

import logging

from flask import Flask, abort, request

from .app import BotApp
from .config import Settings

logger = logging.getLogger(__name__)


def create_webhook_app(bot_app: BotApp, settings: Settings) -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # The token in the path acts as a shared secret — only Telegram knows it.
    webhook_path = f"/webhook/{settings.telegram_bot_token}"

    @app.post(webhook_path)
    def webhook():
        data = request.get_json(silent=True)
        if not data:
            abort(400)
        message = data.get("message") or data.get("edited_message")
        if message:
            try:
                bot_app.handle_message(message)
            except Exception:
                logger.exception("Unhandled error in webhook handler")
        # Always return 200 so Telegram doesn't retry
        return {"ok": True}

    return app
