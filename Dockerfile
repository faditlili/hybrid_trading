
FROM python:3.11-slim

# Python runtime settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

# Install dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Verify required project files
RUN set -eux; \
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

# Create a non-root application user
RUN groupadd --system app \
    && useradd --system --gid app --create-home app \
    && chown -R app:app /code

USER app

# Start AI QUANT
CMD ["python", "-u", "main.py"]
