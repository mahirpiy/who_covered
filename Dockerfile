FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    CHALK_REPORT_DB=/data/chalk_report.db \
    TZ=America/New_York

# No ENTRYPOINT: Railway's startCommand replaces CMD outright, and an
# ENTRYPOINT would end up prefixing it.
CMD ["python", "src/bot.py", "--leagues", "nfl", "cfb", "--interval", "120"]
