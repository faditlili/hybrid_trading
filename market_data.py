
import asyncio
import logging
import math

import aiohttp
import pandas as pd

from config import (
    BINANCE_BASE_URL,
    MIN_QUOTE_VOLUME,
    TIMEFRAME,
    KLINE_LIMIT,
    SYMBOLS
)


logger = logging.getLogger(__name__)


class MarketData:

    def __init__(self):

        self.session = None
        self.base_url = BINANCE_BASE_URL.rstrip("/")

        self.timeout = aiohttp.ClientTimeout(
            total=15,
            connect=5,
            sock_read=10
        )

    async def start(self):

        if self.session is not None and not self.session.closed:
            return

        connector = aiohttp.TCPConnector(
            limit=50,
            ttl_dns_cache=300
        )

        self.session = aiohttp.ClientSession(
            timeout=self.timeout,
            connector=connector
        )

        logger.info("MARKET DATA STARTED")

    async def close(self):

        if self.session is not None and not self.session.closed:
            await self.session.close()

        self.session = None

        logger.info("MARKET DATA CLOSED")

    async def _get_json(self, endpoint, params=None):

        if self.session is None or self.session.closed:
            logger.error("MARKET DATA SESSION NOT STARTED")
            return None

        url = f"{self.base_url}{endpoint}"

        try:

            async with self.session.get(
                url,
                params=params
            ) as response:

                if response.status != 200:

                    body = await response.text()

                    logger.warning(
                        "BINANCE API ERROR %s | %s",
                        response.status,
                        body[:200]
                    )

                    return None

                return await response.json()

        except asyncio.TimeoutError:

            logger.warning(
                "BINANCE REQUEST TIMEOUT: %s",
                endpoint
            )

        except aiohttp.ClientError:

            logger.exception(
                "BINANCE CONNECTION ERROR: %s",
                endpoint
            )

        except Exception:

            logger.exception(
                "BINANCE UNKNOWN ERROR: %s",
                endpoint
            )

        return None

    async def get_ticker(self, symbol):

        symbol = str(symbol).upper()

        if symbol not in SYMBOLS:
            return None

        data = await self._get_json(
            "/api/v3/ticker/24hr",
            params={"symbol": symbol}
        )

        if not isinstance(data, dict):
            return None

        try:

            price = float(data["lastPrice"])
            quote_volume = float(data["quoteVolume"])
            change = float(data["priceChangePercent"])

            if not all(
                math.isfinite(value)
                for value in (price, quote_volume, change)
            ):
                return None

            if price <= 0 or quote_volume < 0:
                return None

            return {
                "symbol": symbol,
                "price": price,
                "quote_volume": quote_volume,
                "price_change_percent": change,
                "high": float(data["highPrice"]),
                "low": float(data["lowPrice"]),
                "volume": float(data["volume"]),
                "open": float(data["openPrice"])
            }

        except (KeyError, TypeError, ValueError):

            logger.exception(
                "INVALID TICKER DATA: %s",
                symbol
            )

            return None

    async def get_klines(self, symbol):

        symbol = str(symbol).upper()

        if symbol not in SYMBOLS:
            return None

        data = await self._get_json(
            "/api/v3/klines",
            params={
                "symbol": symbol,
                "interval": TIMEFRAME,
                "limit": KLINE_LIMIT
            }
        )

        if not isinstance(data, list) or not data:
            return None

        try:

            columns = [
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_volume",
                "trades",
                "taker_buy_base",
                "taker_buy_quote",
                "ignore"
            ]

            if any(
                not isinstance(row, list) or len(row) < 12
                for row in data
            ):
                return None

            df = pd.DataFrame(
                data,
                columns=columns
            )

            numeric_columns = [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "quote_volume"
            ]

            for column in numeric_columns:
                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce"
                )

            if df[numeric_columns].isnull().any().any():
                return None

            if not all(
                math.isfinite(float(value))
                for value in df[numeric_columns].to_numpy().flatten()
            ):
                return None

            if (
                (df["open"] <= 0).any()
                or (df["high"] <= 0).any()
                or (df["low"] <= 0).any()
                or (df["close"] <= 0).any()
                or (df["volume"] < 0).any()
            ):
                return None

            if (
                (df["high"] < df["low"]).any()
                or (df["high"] < df["open"]).any()
                or (df["high"] < df["close"]).any()
                or (df["low"] > df["open"]).any()
                or (df["low"] > df["close"]).any()
            ):
                return None

            df["open_time"] = pd.to_datetime(
                df["open_time"],
                unit="ms",
                utc=True
            )

            df["close_time"] = pd.to_datetime(
                df["close_time"],
                unit="ms",
                utc=True
            )

            return df

        except Exception:

            logger.exception(
                "KLINE PARSING ERROR: %s",
                symbol
            )

            return None

    async def get_market_snapshot(self, symbol):

        symbol = str(symbol).upper()

        if symbol not in SYMBOLS:

            logger.warning(
                "SNAPSHOT REJECTED %s: Symbol not configured",
                symbol
            )

            return None

        try:

            ticker, candles = await asyncio.gather(
                self.get_ticker(symbol),
                self.get_klines(symbol)
            )

            if ticker is None:

                logger.warning(
                    "SNAPSHOT REJECTED %s: Invalid ticker",
                    symbol
                )

                return None

            if ticker["quote_volume"] < MIN_QUOTE_VOLUME:

                logger.warning(
                    "SNAPSHOT REJECTED %s: Low volume %.2f < %.2f",
                    symbol,
                    ticker["quote_volume"],
                    MIN_QUOTE_VOLUME
                )

                return None

            if candles is None or len(candles) < 61:

                logger.warning(
                    "SNAPSHOT REJECTED %s: Insufficient candles (%s)",
                    symbol,
                    0 if candles is None else len(candles)
                )

                return None

            logger.info(
                "SNAPSHOT OK %s | Price: %.8f | Candles: %s",
                symbol,
                ticker["price"],
                len(candles)
            )

            return {
                "symbol": symbol,
                "ticker": ticker,
                "candles": candles,
                "klines": candles
            }

        except Exception:

            logger.exception(
                "MARKET SNAPSHOT ERROR: %s",
                symbol
            )

            return None
