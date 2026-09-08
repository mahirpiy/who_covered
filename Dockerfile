FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# BOT_ARGS defaults to print-only. Nothing posts until it is overridden with
# --live, so a misconfigured deploy is silent rather than loud.
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    CHALK_REPORT_DB=/data/chalk_report.db \
    TZ=America/New_York \
    BOT_ARGS="--leagues nfl cfb --interval 120"

# No ENTRYPOINT: Railway's startCommand replaces CMD outright, and an
# ENTRYPOINT would end up prefixing it. Unquoted $BOT_ARGS is intentional --
# it must word-split into separate arguments.
CMD ["sh", "-c", "python src/bot.py $BOT_ARGS"]
