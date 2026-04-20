"""WSGI entry point for gunicorn (Cloud Run / Docker webhook mode)."""
from __future__ import annotations

import logging

from .app import BotApp
from .config import load_settings
from .webhook import create_webhook_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

_settings = load_settings()
_bot = BotApp(_settings)
_bot.validate_env()
_bot.sheets.get_worksheet()

if _settings.webhook_url:
    _endpoint = f"{_settings.webhook_url}/webhook/{_settings.telegram_bot_token}"
    _bot.telegram.set_webhook(_endpoint)
    logger.info("Telegram webhook registered: %s", _endpoint)
else:
    logger.warning("WEBHOOK_URL not set — Telegram will not deliver messages to this server.")

app = create_webhook_app(_bot, _settings)
