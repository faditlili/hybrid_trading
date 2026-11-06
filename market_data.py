
import asyncio
import logging
import math
from datetime import datetime, timezone

import aiohttp
import pandas as pd

from config import (
    BINANCE_BASE_URL,
    MIN_QUOTE_VOLUME,
    TIMEFRAME,
    KLINE_LIMIT,
    SYMBOLS,
    HTTP_TIMEOUT_SECONDS,
    HTTP_CONNECT_TIMEOUT_SECONDS,
    HTTP_MAX_CONNECTIONS,
    HTTP_RETRY_ATTEMPTS,
)

logger = logging.getLogger(__name__)


class MarketDataError(Exception):
    """Raised when market data cannot be retrieved or validated."""


class MarketData:

    def __init__(self):

        self.session = None
        self.base_url = BINANCE_BASE_URL.rstrip("/")

        self.timeout = aiohttp.ClientTimeout(
            total=HTTP_TIMEOUT_SECONDS,
            connect=HTTP_CONNECT_TIMEOUT_SECONDS,
        )

        self.connector_limit = HTTP_MAX_CONNECTIONS

        self.retry_attempts = HTTP_RETRY_ATTEMPTS

        self._session_lock = asyncio.Lock()

        self.last_success = {}
        self.last_errors = {}

    # ========================================================
    # SESSION MANAGEMENT
    # ========================================================

    async def start(self):

        async with self._session_lock:

            if self.session and not self.session.closed:
                return

            connector = aiohttp.TCPConnector(
                limit=self.connector_limit,
                enable_cleanup_closed=True,
            )

            self.session = aiohttp.ClientSession(
                timeout=self.timeout,
                connector=connector,
                headers={
                    "User-Agent": "AI-QUANT-PaperTrading/3.1"
                },
            )

            logger.info("Market data service started.")

    async def close(self):

        async with self._session_lock:

            if self.session and not self.session.closed:
                await self.session.close()

            self.session = None

            logger.info("Market data service closed.")

    async def _ensure_session(self):

        if self.session is None or self.session.closed:
            await self.start()

    # ========================================================
    # HTTP REQUEST
    # ========================================================

    async def _request_json(self, endpoint, params=None):

        await self._ensure_session()

        url = f"{self.base_url}{endpoint}"

        last_error = None

        for attempt in range(self.retry_attempts + 1):

            try:

                async with self.session.get(
                    url,
                    params=params,
                ) as response:

                    if response.status == 429:
                        retry_after = response.headers.get(
                            "Retry-After",
                            "2",
                        )

                        try:
                            delay = min(float(retry_after), 30)
                        except (ValueError, TypeError):
                            delay = 2

                        raise MarketDataError(
                            f"Binance rate limit reached. "
                            f"Retry after {delay} seconds."
                        )

                    if response.status == 418:
                        raise MarketDataError(
                            "Binance temporarily blocked this IP."
                        )

                    if response.status >= 500:
                        raise MarketDataError(
                            f"Binance server error: {response.status}"
                        )

                    if response.status != 200:
                        body = await response.text()

                        raise MarketDataError(
                            f"HTTP {response.status}: {body[:200]}"
                        )

                    return await response.json(
                        content_type=None
                    )

            except MarketDataError as exc:

                last_error = exc

                if "rate limit" in str(exc).lower():
                    raise

                if attempt >= self.retry_attempts:
                    break

            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
                ValueError,
            ) as exc:

                last_error = exc

                if attempt >= self.retry_attempts:
                    break

            delay = min(2 ** attempt, 8)

            await asyncio.sleep(delay)

        raise MarketDataError(
            f"Request failed: {last_error}"
        )

    # ========================================================
    # SYMBOL VALIDATION
    # ========================================================

    @staticmethod
    def _valid_symbol(symbol):

        if not isinstance(symbol, str):
            return False

        if not symbol:
            return False

        if symbol != symbol.upper():
            return False

        return symbol.isalnum()

    # ========================================================
    # EXCHANGE TICKER
    # ========================================================

    async def get_ticker(self, symbol):

        if not self._valid_symbol(symbol):
            raise MarketDataError("Invalid symbol.")

        try:

            data = await self._request_json(
                "/api/v3/ticker/24hr",
                params={"symbol": symbol},
            )

            price = float(data["lastPrice"])

            volume = float(data["quoteVolume"])

            if not math.isfinite(price) or price <= 0:
                raise MarketDataError(
                    "Invalid ticker price."
                )

            if not math.isfinite(volume) or volume < 0:
                raise MarketDataError(
                    "Invalid ticker volume."
                )

            return {
                "symbol": symbol,
                "price": price,
                "quote_volume": volume,
                "change_percent": float(
                    data["priceChangePercent"]
                ),
                "timestamp": datetime.now(
                    timezone.utc
                ).isoformat(),
            }

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as exc:

            self.last_errors[symbol] = str(exc)

            logger.exception(
                "Invalid ticker response for %s",
                symbol,
            )

            raise MarketDataError(
                f"Invalid ticker data for {symbol}"
            ) from exc

    # ========================================================
    # KLINES / OHLCV
    # ========================================================

    async def get_klines(
        self,
        symbol,
        interval=None,
        limit=None,
    ):

        if not self._valid_symbol(symbol):
            raise MarketDataError("Invalid symbol.")

        interval = interval or TIMEFRAME
        limit = limit or KLINE_LIMIT

        if not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise MarketDataError("Invalid kline limit.")

        try:

            raw = await self._request_json(
                "/api/v3/klines",
                params={
                    "symbol": symbol,
                    "interval": interval,
                    "limit": limit,
                },
            )

            if not isinstance(raw, list) or not raw:
                raise MarketDataError(
                    f"No kline data available for {symbol}."
                )

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
                "ignore",
            ]

            rows = []

            for item in raw:

                if not isinstance(item, list) or len(item) < 12:
                    continue

                rows.append(item[:12])

            if not rows:
                raise MarketDataError(
                    "Kline response has no valid rows."
                )

            df = pd.DataFrame(
                rows,
                columns=columns,
            )

            numeric_columns = [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "quote_volume",
                "trades",
                "taker_buy_base",
                "taker_buy_quote",
            ]

            for column in numeric_columns:

                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce",
                )

            df["open_time"] = pd.to_numeric(
                df["open_time"],
                errors="coerce",
            )

            df["close_time"] = pd.to_numeric(
                df["close_time"],
                errors="coerce",
            )

            df = df.dropna(
                subset=[
                    "open_time",
                    "close_time",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ]
            )

            df = df.sort_values(
                "open_time"
            )

            df = df.drop_duplicates(
                subset=["open_time"],
                keep="last",
            )

            df = df.reset_index(drop=True)

            if df.empty:
                raise MarketDataError(
                    "No valid candles remain after cleaning."
                )

            # Validate OHLCV values.
            for column in numeric_columns:

                values = df[column].to_numpy(
                    dtype=float
                )

                if not all(
                    math.isfinite(float(value))
                    for value in values
                ):

                    raise MarketDataError(
                        f"Non-finite values in {column}."
                    )

            if (
                (df["open"] <= 0).any()
                or (df["high"] <= 0).any()
                or (df["low"] <= 0).any()
                or (df["close"] <= 0).any()
            ):

                raise MarketDataError(
                    "OHLC prices must be positive."
                )

            if (
                (df["volume"] < 0).any()
                or (df["quote_volume"] < 0).any()
            ):

                raise MarketDataError(
                    "Volume cannot be negative."
                )

            invalid_ohlc = (
                (df["high"] < df["low"])
                | (df["high"] < df["open"])
                | (df["high"] < df["close"])
                | (df["low"] > df["open"])
                | (df["low"] > df["close"])
            )

            if invalid_ohlc.any():

                raise MarketDataError(
                    "Invalid OHLC candle structure."
                )

            # Remove only the currently unfinished candle.
            now_ms = int(
                datetime.now(timezone.utc).timestamp() * 1000
            )

            df = df[
                df["close_time"] < now_ms
            ].copy()

            df = df.reset_index(drop=True)

            if len(df) < 60:
                raise MarketDataError(
                    "Not enough completed candles for analysis."
                )

            df["timestamp"] = pd.to_datetime(
                df["open_time"],
                unit="ms",
                utc=True,
            )

            self.last_success[symbol] = datetime.now(
                timezone.utc
            ).isoformat()

            self.last_errors.pop(symbol, None)

            return df

        except MarketDataError:

            raise

        except (
            KeyError,
            TypeError,
            ValueError,
            OverflowError,
        ) as exc:

            self.last_errors[symbol] = str(exc)

            logger.exception(
                "Kline processing failed for %s",
                symbol,
            )

            raise MarketDataError(
                f"Could not process klines for {symbol}"
            ) from exc

    # ========================================================
    # MARKET SNAPSHOT
    # ========================================================

    async def get_market_snapshot(self, symbol):

        ticker_task = self.get_ticker(symbol)

        klines_task = self.get_klines(symbol)

        ticker, klines = await asyncio.gather(
            ticker_task,
            klines_task,
        )

        if klines.empty:
            raise MarketDataError(
                f"No candles for {symbol}"
            )

        latest_close = float(
            klines.iloc[-1]["close"]
        )

        return {
            "symbol": symbol,
            "price": ticker["price"],
            "quote_volume": ticker["quote_volume"],
            "change_percent": ticker["change_percent"],
            "latest_candle_close": latest_close,
            "candles": klines,
            "timestamp": ticker["timestamp"],
        }

    # ========================================================
    # MARKET FILTER
    # ========================================================

    async def get_liquid_symbols(self):

        results = []

        for symbol in SYMBOLS:

            try:

                ticker = await self.get_ticker(
                    symbol
                )

                if (
                    ticker["quote_volume"]
                    >= MIN_QUOTE_VOLUME
                ):

                    results.append(symbol)

            except Exception:

                logger.exception(
                    "Liquidity check failed for %s",
                    symbol,
                )

        return results

    # ========================================================
    # SERVICE STATUS
    # ========================================================

    def get_status(self):

        return {
            "service": "market_data",
            "running": (
                self.session is not None
                and not self.session.closed
            ),
            "last_success": dict(
                self.last_success
            ),
            "last_errors": dict(
                self.last_errors
            ),
        }
