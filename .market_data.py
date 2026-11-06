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
            connect=5
        )

    async def start(self):

        if self.session and not self.session.closed:
            return

        connector = aiohttp.TCPConnector(
            limit=20,
            ttl_dns_cache=300
        )

        self.session = aiohttp.ClientSession(
            timeout=self.timeout,
            connector=connector,
            headers={
                "User-Agent": "AI-QUANT-PAPER/3.0"
            }
        )

        logger.info("Market data service started")

    async def close(self):

        if self.session and not self.session.closed:
            await self.session.close()

        self.session = None

        logger.info("Market data service stopped")

    @staticmethod
    def valid_number(value, minimum=None):

        try:

            number = float(value)

            if not math.isfinite(number):
                return False

            if minimum is not None and number < minimum:
                return False

            return True

        except (TypeError, ValueError, OverflowError):
            return False

    async def _get(self, endpoint, params=None):

        if not self.session or self.session.closed:
            raise RuntimeError("Market session is not started")

        url = f"{self.base_url}{endpoint}"

        for attempt in range(3):

            try:

                async with self.session.get(
                    url,
                    params=params
                ) as response:

                    if response.status in (418, 429):

                        raise RuntimeError(
                            f"Binance rate limit: {response.status}"
                        )

                    if response.status >= 500:

                        raise aiohttp.ClientError(
                            f"Binance server error: {response.status}"
                        )

                    response.raise_for_status()

                    return await response.json()

            except RuntimeError:
                raise

            except (
                aiohttp.ClientError,
                asyncio.TimeoutError
            ) as exc:

                if attempt == 2:
                    raise

                delay = 1.5 * (attempt + 1)

                logger.warning(
                    "Market request failed (%s), retrying in %.1fs",
                    str(exc)[:150],
                    delay
                )

                await asyncio.sleep(delay)

        raise RuntimeError("Market request failed")

    async def get_ticker(self, symbol):

        symbol = str(symbol).upper()

        data = await self._get(
            "/api/v3/ticker/24hr",
            {
                "symbol": symbol
            }
        )

        if not isinstance(data, dict):
            return None

        try:

            result = {
                "symbol": symbol,
                "price": float(data["lastPrice"]),
                "quote_volume": float(data["quoteVolume"]),
                "change_pct": float(data["priceChangePercent"]),
                "high": float(data["highPrice"]),
                "low": float(data["lowPrice"]),
                "open": float(data["openPrice"])
            }

            if not all(
                math.isfinite(value)
                for key, value in result.items()
                if key != "symbol"
            ):
                return None

            if result["price"] <= 0:
                return None

            if result["quote_volume"] < 0:
                return None

            return result

        except (KeyError, TypeError, ValueError, OverflowError):
            logger.warning("Invalid ticker data: %s", symbol)
            return None

    async def get_klines(
        self,
        symbol,
        interval=None,
        limit=None
    ):

        symbol = str(symbol).upper()

        interval = interval or TIMEFRAME
        limit = limit or KLINE_LIMIT

        data = await self._get(
            "/api/v3/klines",
            {
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }
        )

        if not isinstance(data, list) or not data:
            return pd.DataFrame()

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

        try:

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
                "close_time"
            ]

            for column in numeric_columns:

                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce"
                )

            df = df.dropna(
                subset=numeric_columns
            )

            df = df.reset_index(drop=True)

            if len(df) < 2:
                return pd.DataFrame()

            return df

        except (ValueError, TypeError, KeyError):
            logger.exception(
                "Failed to process klines: %s",
                symbol
            )

            return pd.DataFrame()

    async def get_market_snapshot(self, symbol):

        symbol = str(symbol).upper()

        if symbol not in SYMBOLS:
            logger.warning(
                "Symbol not configured: %s",
                symbol
            )

            return None

        try:

            ticker, candles = await asyncio.gather(
                self.get_ticker(symbol),
                self.get_klines(symbol)
            )

            if ticker is None:
                return None

            if ticker["quote_volume"] < MIN_QUOTE_VOLUME:
                return None

            if candles is None or len(candles) < 61:
                return None

            return {
                "symbol": symbol,
                "ticker": ticker,
                "candles": candles
            }

        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            RuntimeError,
            ValueError
        ):

            logger.exception(
                "Market snapshot failed: %s",
                symbol
            )

            return None

    async def get_all_tickers(self):

        data = await self._get(
            "/api/v3/ticker/24hr"
        )

        if not isinstance(data, list):
            return []

        results = []

        for item in data:

            try:

                symbol = item["symbol"]

                if symbol not in SYMBOLS:
                    continue

                price = float(item["lastPrice"])
                volume = float(item["quoteVolume"])
                change = float(item["priceChangePercent"])

                if not all(
                    math.isfinite(value)
                    for value in (price, volume, change)
                ):
                    continue

                if price <= 0 or volume < 0:
                    continue

                results.append({
                    "symbol": symbol,
                    "price": price,
                    "quote_volume": volume,
                    "change_pct": change
                })

            except (KeyError, TypeError, ValueError, OverflowError):
                continue

        return results
