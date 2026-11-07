
"""Public BingX market-data client.

Public market data only.
No private keys and no exchange order functionality.
Paper simulation support only.
"""

import asyncio
import math

import aiohttp

from config import (
    BINGX_BASE_URL,
    BINGX_TICKER_PATH,
    BINGX_KLINE_PATH,
    HTTP_TIMEOUT_SECONDS,
    KLINE_LIMIT,
    TIMEFRAMES,
)


class BingXMarketData:

    def __init__(self):
        self.session = None
        self.last_error = None
        self._lock = asyncio.Lock()

    # --------------------------------------------------
    # HTTP session
    # --------------------------------------------------

    async def start(self):
        """Create an HTTP session safely."""

        async with self._lock:

            if self.session is None or self.session.closed:

                timeout = aiohttp.ClientTimeout(
                    total=HTTP_TIMEOUT_SECONDS
                )

                connector = aiohttp.TCPConnector(
                    limit=20,
                    ttl_dns_cache=300,
                    enable_cleanup_closed=True,
                )

                self.session = aiohttp.ClientSession(
                    base_url=BINGX_BASE_URL,
                    timeout=timeout,
                    connector=connector,
                    headers={
                        "User-Agent": "AI-QUANT/4.0",
                        "Accept": "application/json",
                    },
                )

    async def close(self):
        """Close the HTTP session safely."""

        async with self._lock:

            session = self.session
            self.session = None

            if session is not None and not session.closed:
                await session.close()

    # --------------------------------------------------
    # Validation helpers
    # --------------------------------------------------

    @staticmethod
    def _positive_number(value):
        try:

            number = float(value)

            return (
                math.isfinite(number)
                and number > 0
            )

        except (TypeError, ValueError, OverflowError):
            return False

    @staticmethod
    def _nonnegative_number(value):
        try:

            number = float(value)

            return (
                math.isfinite(number)
                and number >= 0
            )

        except (TypeError, ValueError, OverflowError):
            return False

    @staticmethod
    def normalize_symbol(symbol):
        """Normalize a market symbol to BASE-USDT format."""

        symbol = (
            str(symbol)
            .strip()
            .upper()
            .replace("/", "-")
        )

        if not symbol:
            raise ValueError(
                "Symbol cannot be empty"
            )

        if "-" not in symbol:
            symbol += "-USDT"

        parts = symbol.split("-")

        if (
            len(parts) != 2
            or not parts[0]
            or not parts[1]
        ):
            raise ValueError(
                "Invalid market symbol"
            )

        return symbol

    # --------------------------------------------------
    # HTTP request
    # --------------------------------------------------

    async def _request(self, path, params=None):
        """Perform a public GET request."""

        if self.session is None or self.session.closed:
            await self.start()

        session = self.session

        if session is None or session.closed:
            raise RuntimeError(
                "HTTP session unavailable"
            )

        try:

            async with session.get(
                path,
                params=params or {},
            ) as response:

                response.raise_for_status()

                data = await response.json(
                    content_type=None
                )

                if not isinstance(data, dict):
                    raise ValueError(
                        "Invalid BingX API response"
                    )

                code = data.get("code")

                if code not in (None, 0, "0"):
                    raise RuntimeError(
                        "BingX API error: "
                        f"{data.get('msg', code)}"
                    )

                if "data" not in data:
                    raise ValueError(
                        "BingX response has no data field"
                    )

                self.last_error = None

                return data

        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            ValueError,
            RuntimeError,
        ) as exc:

            self.last_error = str(exc)
            raise

    # --------------------------------------------------
    # Ticker
    # --------------------------------------------------

    async def get_ticker(self, symbol):
        """Get public 24-hour ticker data."""

        normalized = self.normalize_symbol(symbol)

        data = await self._request(
            BINGX_TICKER_PATH,
            params={
                "symbol": normalized,
            },
        )

        result = data.get("data")

        if isinstance(result, list):

            if len(result) != 1:
                raise ValueError(
                    "Unexpected ticker response"
                )

            result = result[0]

        if not isinstance(result, dict):
            raise ValueError(
                "Invalid ticker data"
            )

        last = (
            result.get("last")
            or result.get("lastPrice")
            or result.get("close")
        )

        if not self._positive_number(last):
            raise ValueError(
                f"Invalid last price for {normalized}"
            )

        normalized_result = dict(result)
        normalized_result["last"] = float(last)

        return normalized_result

    async def ticker(self, symbol):
        """Compatibility method used by TradingEngine."""

        return await self.get_ticker(symbol)

    # --------------------------------------------------
    # Kline normalization
    # --------------------------------------------------

    @staticmethod
    def _normalize_candle(candle):
        """Convert a candle into a standard OHLCV dictionary."""

        if isinstance(candle, dict):

            normalized = {
                "open": candle.get("open"),
                "high": candle.get("high"),
                "low": candle.get("low"),
                "close": candle.get("close"),
                "volume": candle.get("volume"),
            }

            timestamp = (
                candle.get("time")
                or candle.get("timestamp")
                or candle.get("openTime")
            )

        elif isinstance(candle, (list, tuple)):

            # Standard OHLCV array:
            # [timestamp, open, high, low, close, volume]

            if len(candle) < 6:
                raise ValueError(
                    "Invalid candle array"
                )

            timestamp = candle[0]

            normalized = {
                "open": candle[1],
                "high": candle[2],
                "low": candle[3],
                "close": candle[4],
                "volume": candle[5],
            }

        else:

            raise ValueError(
                "Unsupported candle format"
            )

        # OHLC prices must be positive.
        for key in (
            "open",
            "high",
            "low",
            "close",
        ):

            value = normalized[key]

            if not BingXMarketData._positive_number(value):
                raise ValueError(
                    f"Invalid candle field: {key}"
                )

            normalized[key] = float(value)

        # Volume may legitimately be zero.
        volume = normalized["volume"]

        if not BingXMarketData._nonnegative_number(volume):
            raise ValueError(
                "Invalid candle field: volume"
            )

        normalized["volume"] = float(volume)

        # Validate OHLC consistency.
        if (
            normalized["high"] < normalized["low"]
            or normalized["high"] < normalized["open"]
            or normalized["high"] < normalized["close"]
            or normalized["low"] > normalized["open"]
            or normalized["low"] > normalized["close"]
        ):

            raise ValueError(
                "Inconsistent candle OHLC values"
            )

        if timestamp is not None:

            try:

                normalized["time"] = int(timestamp)

            except (TypeError, ValueError, OverflowError):

                raise ValueError(
                    "Invalid candle timestamp"
                ) from None

        return normalized

    # --------------------------------------------------
    # Historical candles
    # --------------------------------------------------

    async def get_klines(
        self,
        symbol,
        interval="15m",
        limit=None,
    ):
        """Get normalized historical OHLCV candles."""

        normalized = self.normalize_symbol(symbol)

        if (
            not isinstance(interval, str)
            or interval not in TIMEFRAMES
        ):

            raise ValueError(
                f"Unsupported timeframe: {interval}"
            )

        try:

            limit = (
                KLINE_LIMIT
                if limit is None
                else int(limit)
            )

        except (TypeError, ValueError, OverflowError):

            raise ValueError(
                "Invalid kline limit"
            ) from None

        if not 1 <= limit <= 500:

            raise ValueError(
                "Kline limit must be between 1 and 500"
            )

        data = await self._request(
            BINGX_KLINE_PATH,
            params={
                "symbol": normalized,
                "interval": interval,
                "limit": limit,
            },
        )

        result = data.get("data")

        if not isinstance(result, list):
            raise ValueError(
                "Invalid kline response"
            )

        if not result:
            raise ValueError(
                "No candles returned by BingX"
            )

        candles = [
            self._normalize_candle(candle)
            for candle in result
        ]

        # Sort chronologically when timestamps are available.
        if all("time" in candle for candle in candles):

            candles.sort(
                key=lambda candle: candle["time"]
            )

            # Remove duplicate timestamps.
            unique = {}

            for candle in candles:
                unique[candle["time"]] = candle

            candles = list(unique.values())

        if len(candles) < 2:
            raise ValueError(
                "Insufficient valid candles returned"
            )

        return candles

    async def klines(
        self,
        symbol,
        interval="15m",
        limit=None,
    ):
        """Compatibility method used by TradingEngine."""

        return await self.get_klines(
            symbol,
            interval,
            limit,
        )
