
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=7860

WORKDIR /code

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definitions
COPY requirements.txt .

# Install Python dependencies
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

# Copy application source
COPY . .

# Create persistent data directory
RUN mkdir -p /data \
    && useradd --create-home --uid 10001 app \
    && chown -R app:app /code /data

USER app

EXPOSE 7860

# Start FastAPI application
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]
