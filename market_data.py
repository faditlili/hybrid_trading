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

        if (
            isinstance(self.retry_attempts, bool)
            or not isinstance(self.retry_attempts, int)
            or self.retry_attempts < 0
        ):
            raise ValueError(
                "HTTP_RETRY_ATTEMPTS must be non-negative"
            )

        if (
            isinstance(self.connector_limit, bool)
            or not isinstance(self.connector_limit, int)
            or self.connector_limit <= 0
        ):
            raise ValueError(
                "HTTP_MAX_CONNECTIONS must be positive"
            )

        self._session_lock = asyncio.Lock()
        self._closing = False

        self.last_success = {}
        self.last_errors = {}

        self._symbol_semaphore = asyncio.Semaphore(
            min(5, self.connector_limit)
        )

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def valid_number(value):

        if isinstance(value, bool):
            return False

        try:
            return math.isfinite(float(value))

        except (TypeError, ValueError, OverflowError):
            return False

    @staticmethod
    def utc_timestamp():

        return datetime.now(
            timezone.utc
        ).isoformat()

    def record_error(self, symbol, error):

        self.last_errors[symbol] = str(error)[:500]

    # ========================================================
    # SESSION MANAGEMENT
    # ========================================================

    async def start(self):

        async with self._session_lock:

            if self._closing:
                raise MarketDataError(
                    "Market data service is closing"
                )

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

            logger.info(
                "Market data service started"
            )

    async def close(self):

        async with self._session_lock:

            self._closing = True

            session = self.session
            self.session = None

            if session and not session.closed:
                await session.close()

            logger.info(
                "Market data service closed"
            )

    async def _ensure_session(self):

        if self._closing:
            raise MarketDataError(
                "Market data service is closed"
            )

        if self.session is None or self.session.closed:
            await self.start()

    # ========================================================
    # HTTP REQUEST
    # ========================================================

    async def _request_json(
        self,
        endpoint,
        params=None,
    ):

        await self._ensure_session()

        last_error = None

        for attempt in range(self.retry_attempts + 1):

            await self._ensure_session()

            try:

                async with self.session.get(
                    f"{self.base_url}{endpoint}",
                    params=params,
                ) as response:

                    if response.status == 429:

                        raise MarketDataError(
                            "Binance rate limit reached"
                        )

                    if response.status == 418:

                        raise MarketDataError(
                            "Binance temporarily blocked this IP"
                        )

                    if response.status >= 500:

                        last_error = MarketDataError(
                            f"Binance server error: {response.status}"
                        )

                    elif response.status != 200:

                        body = await response.text()

                        raise MarketDataError(
                            f"HTTP {response.status}: {body[:200]}"
                        )

                    else:

                        data = await response.json(
                            content_type=None
                        )

                        if not isinstance(data, (dict, list)):
                            raise MarketDataError(
                                "Unexpected Binance JSON response"
                            )

                        return data

            except asyncio.CancelledError:
                raise

            except MarketDataError as exc:

                message = str(exc).lower()

                if (
                    "rate limit" in message
                    or "blocked this ip" in message
                    or message.startswith("http 4")
                ):
                    raise

                last_error = exc

            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
                ValueError,
            ) as exc:

                last_error = exc

            if attempt < self.retry_attempts:

                delay = min(
                    2 ** attempt,
                    8,
                )

                await asyncio.sleep(delay)

        raise MarketDataError(
            f"Request failed: {last_error}"
        )

    # ========================================================
    # SYMBOL VALIDATION
    # ========================================================

    @staticmethod
    def _valid_symbol(symbol):

        return (
            isinstance(symbol, str)
            and bool(symbol)
            and symbol == symbol.upper()
            and symbol.isalnum()
        )

    # ========================================================
    # EXCHANGE TICKER
    # ========================================================

    async def get_ticker(self, symbol):

        if not self._valid_symbol(symbol):
            raise MarketDataError(
                "Invalid symbol"
            )

        try:

            data = await self._request_json(
                "/api/v3/ticker/24hr",
                params={
                    "symbol": symbol
                },
            )

            if not isinstance(data, dict):
                raise MarketDataError(
                    "Invalid ticker response"
                )

            price = float(data["lastPrice"])
            volume = float(data["quoteVolume"])
            change = float(data["priceChangePercent"])

            if not self.valid_number(price) or price <= 0:
                raise MarketDataError(
                    "Invalid ticker price"
                )

            if not self.valid_number(volume) or volume < 0:
                raise MarketDataError(
                    "Invalid ticker volume"
                )

            if not self.valid_number(change):
                raise MarketDataError(
                    "Invalid price change"
                )

            result = {
                "symbol": symbol,
                "price": price,
                "quote_volume": volume,
                "change_percent": change,
                "timestamp": self.utc_timestamp(),
            }

            self.last_success[symbol] = result["timestamp"]
            self.last_errors.pop(symbol, None)

            return result

        except asyncio.CancelledError:
            raise

        except Exception as exc:

            self.record_error(symbol, exc)

            logger.warning(
                "Ticker request failed for %s: %s",
                symbol,
                exc,
            )

            if isinstance(exc, MarketDataError):
                raise

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
            raise MarketDataError(
                "Invalid symbol"
            )

        interval = interval or TIMEFRAME

        limit = KLINE_LIMIT if limit is None else limit

        if (
            not isinstance(interval, str)
            or not interval.strip()
        ):
            raise MarketDataError(
                "Invalid kline interval"
            )

        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 1000
        ):
            raise MarketDataError(
                "Invalid kline limit"
            )

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
                    f"No kline data for {symbol}"
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

            rows = [
                item[:12]
                for item in raw
                if isinstance(item, list) and len(item) >= 12
            ]

            if not rows:
                raise MarketDataError(
                    "Kline response contains no valid rows"
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
                "open_time",
                "close_time",
            ]

            for column in numeric_columns:

                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce",
                )

            df = df.dropna(
                subset=numeric_columns
            )

            df = df.sort_values(
                "open_time"
            )

            df = df.drop_duplicates(
                subset=["open_time"],
                keep="last",
            )

            df = df.reset_index(
                drop=True
            )

            if df.empty:
                raise MarketDataError(
                    "No valid candles remain"
                )

            for column in numeric_columns:

                values = df[column].to_numpy(
                    dtype=float
                )

                if not all(
                    math.isfinite(float(value))
                    for value in values
                ):
                    raise MarketDataError(
                        f"Non-finite values in {column}"
                    )

            price_columns = [
                "open",
                "high",
                "low",
                "close",
            ]

            for column in price_columns:

                if (df[column] <= 0).any():
                    raise MarketDataError(
                        f"Invalid prices in {column}"
                    )

            if (
                (df["volume"] < 0).any()
                or (df["quote_volume"] < 0).any()
                or (df["trades"] < 0).any()
                or (df["taker_buy_base"] < 0).any()
                or (df["taker_buy_quote"] < 0).any()
            ):
                raise MarketDataError(
                    "Negative volume or trade count"
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
                    "Invalid OHLC candle structure"
                )

            now_ms = int(
                datetime.now(timezone.utc).timestamp() * 1000
            )

            df = df[
                df["close_time"] < now_ms
            ].copy()

            df = df.reset_index(
                drop=True
            )

            if len(df) < 60:
                raise MarketDataError(
                    "Not enough completed candles"
                )

            df["timestamp"] = pd.to_datetime(
                df["open_time"],
                unit="ms",
                utc=True,
            )

            timestamp = self.utc_timestamp()

            self.last_success[symbol] = timestamp
            self.last_errors.pop(symbol, None)

            return df

        except asyncio.CancelledError:
            raise

        except Exception as exc:

            self.record_error(symbol, exc)

            logger.warning(
                "Kline processing failed for %s: %s",
                symbol,
                exc,
            )

            if isinstance(exc, MarketDataError):
                raise

            raise MarketDataError(
                f"Could not process klines for {symbol}"
            ) from exc

    # ========================================================
    # MARKET SNAPSHOT
    # ========================================================

    async def get_market_snapshot(self, symbol):

        if not self._valid_symbol(symbol):
            raise MarketDataError(
                "Invalid symbol"
            )

        try:

            ticker, klines = await asyncio.gather(
                self.get_ticker(symbol),
                self.get_klines(symbol),
            )

            if (
                not isinstance(klines, pd.DataFrame)
                or klines.empty
            ):
                raise MarketDataError(
                    "Invalid candle DataFrame"
                )

            latest_close = float(
                klines.iloc[-1]["close"]
            )

            if (
                not self.valid_number(latest_close)
                or latest_close <= 0
            ):
                raise MarketDataError(
                    "Invalid latest candle close"
                )

            return {
                "symbol": symbol,
                "price": ticker["price"],
                "quote_volume": ticker["quote_volume"],
                "change_percent": ticker["change_percent"],
                "latest_candle_close": latest_close,
                "candles": klines,
                "klines": klines,
                "timestamp": ticker["timestamp"],
            }

        except asyncio.CancelledError:
            raise

        except Exception as exc:

            self.record_error(symbol, exc)

            if isinstance(exc, MarketDataError):
                raise

            raise MarketDataError(
                f"Could not create snapshot for {symbol}"
            ) from exc

    # ========================================================
    # MARKET FILTER
    # ========================================================

    async def _check_liquidity(self, symbol):

        async with self._symbol_semaphore:

            try:

                ticker = await self.get_ticker(
                    symbol
                )

                return (
                    symbol
                    if ticker["quote_volume"] >= MIN_QUOTE_VOLUME
                    else None
                )

            except asyncio.CancelledError:
                raise

            except Exception:

                logger.warning(
                    "Liquidity check failed for %s",
                    symbol,
                    exc_info=True,
                )

                return None

    async def get_liquid_symbols(self):

        symbols = [
            symbol
            for symbol in SYMBOLS
            if self._valid_symbol(symbol)
        ]

        results = await asyncio.gather(
            *[
                self._check_liquidity(symbol)
                for symbol in symbols
            ]
        )

        return [
            symbol
            for symbol in results
            if symbol is not None
        ]

    # ========================================================
    # SERVICE STATUS
    # ========================================================

    def get_status(self):

        return {
            "service": "market_data",
            "running": (
                self.session is not None
                and not self.session.closed
                and not self._closing
            ),
            "last_success": dict(
                self.last_success
            ),
            "last_errors": dict(
                self.last_errors
            ),
        }
