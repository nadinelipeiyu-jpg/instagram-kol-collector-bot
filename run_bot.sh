#!/bin/bash
set -euo pipefail

cd /Users/nadine/kol-bot
source /Users/nadine/kol-bot/venv/bin/activate
exec python -m kol_bot.cli run
