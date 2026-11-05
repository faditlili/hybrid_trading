FROM python:3.10-slim

WORKDIR /code

RUN pip install --no-cache-dir --upgrade python-telegram-bot fastapi uvicorn gradio aiohttp

COPY . .

CMD ["python", "main.py"]
