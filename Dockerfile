FROM python:3.11-slim

WORKDIR /code

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN echo "===== PROJECT FILES =====" \
    && ls -la /code \
    && echo "===== MARKET DATA CHECK =====" \
    && test -f /code/market_data.py

CMD ["python", "main.py"]
