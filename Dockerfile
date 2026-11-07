
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first
COPY requirements.txt .

RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy application files
COPY . .

# Create a non-root user
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app

USER appuser

# Render-compatible port
ENV HOST=0.0.0.0
ENV PORT=7860

EXPOSE 7860

CMD ["sh", "-c", "python main.py"]
