"""Public BingX market-data client.
Uses public endpoints only. No private keys or order endpoints.
"""

import asyncio
import aiohttp

from config import (
    BINGX_BASE_URL,
    BINGX_TICKER_PATH,
    BINGX_KLINE_PATH,
    HTTP_TIMEOUT_SECONDS,
    KLINE_LIMIT,
)


class BingXMarketData:
    def __init__(self):
        self.session = None
        self.last_error = None
        self._lock = asyncio.Lock()

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
                    base_url=BINGX_BASE_URL.rstrip("/"),
                    timeout=timeout,
                    connector=connector,
                    headers={
                        "User-Agent": "AI-QUANT/4.0",
                        "Accept": "application/json",
                    },
                )

    async def close(self):
        """Close the HTTP session."""
        async with self._lock:
            if self.session and not self.session.closed:
                await self.session.close()

            self.session = None

    @staticmethod
    def normalize_symbol(symbol):
        """Normalize trading pair."""
        symbol = str(symbol).strip().upper().replace("/", "-")

        if not symbol:
            raise ValueError("Symbol cannot be empty")

        if "-" not in symbol:
            symbol += "-USDT"

        return symbol

    async def _request(self, path, params=None):
        """Perform a public GET request."""
        if self.session is None or self.session.closed:
            await self.start()

        try:
            async with self.session.get(
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
                        f"BingX API error: {data.get('msg', code)}"
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

    async def get_ticker(self, symbol):
        """Get public 24-hour ticker data."""
        normalized = self.normalize_symbol(symbol)

        data = await self._request(
            BINGX_TICKER_PATH,
            params={
                "symbol": normalized.replace("-", ""),
            },
        )

        result = data.get("data")

        if not isinstance(result, dict):
            raise ValueError("Invalid ticker data")

        return result

    async def get_klines(
        self,
        symbol,
        interval="15m",
        limit=None,
    ):
        """Get historical candlestick data."""
        normalized = self.normalize_symbol(symbol)

        if not isinstance(interval, str) or not interval.strip():
            raise ValueError("Invalid timeframe")

        limit = KLINE_LIMIT if limit is None else int(limit)

        if not 1 <= limit <= 1000:
            raise ValueError("Kline limit must be between 1 and 1000")

        data = await self._request(
            BINGX_KLINE_PATH,
            params={
                "symbol": normalized.replace("-", ""),
                "interval": interval,
                "limit": limit,
            },
        )

        result = data.get("data")

        if not isinstance(result, list):
            raise ValueError("Invalid kline data")

        if not result:
            raise ValueError("No candles returned by BingX")

        return result
