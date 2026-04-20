FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY kol_bot/ kol_bot/
COPY telegram_kol_mvp_bot.py .

RUN useradd -m botuser && chown -R botuser:botuser /app
USER botuser

ENV PYTHONUNBUFFERED=1

# Cloud Run injects PORT; gunicorn binds to it.
# --workers 1 --threads 8: single process, concurrent threads (safe for shared state).
# --timeout 0: disable worker timeout (Apify calls can take up to 3 min).
CMD exec gunicorn \
      --bind "0.0.0.0:${PORT:-8080}" \
      --workers 1 \
      --threads 8 \
      --timeout 0 \
      --access-logfile - \
      "kol_bot.wsgi:app"
