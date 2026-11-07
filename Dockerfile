FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=7860
ENV DB_PATH=/data/ai_quant.db

WORKDIR /code

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt
COPY . .

RUN set -eux; \
    mkdir -p /data; \
    for file in \
        config.py \
        database.py \
        market_data.py \
        technical_analysis.py \
        ai_council.py \
        news_engine.py \
        decision_engine.py \
        paper_trading.py \
        engine.py \
        dashboard.py \
        telegram_bot.py \
        main.py \
    ; do \
        test -f "/code/$file"; \
    done

RUN groupadd --system app \
    && useradd --system --gid app --create-home app \
    && chown -R app:app /code /data

USER app
EXPOSE 7860

CMD ["python", "-u", "main.py"]
