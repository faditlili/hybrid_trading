import asyncio
import aiohttp
import pandas as pd

from config import (
    BINANCE_BASE_URL,
    MIN_QUOTE_VOLUME,
    TIMEFRAME,
    KLINE_LIMIT
)


class MarketData:

    def __init__(self):
        self.session = None

    async def start(self):

        if self.session and not self.session.closed:
            return

        timeout = aiohttp.ClientTimeout(
            total=15,
            connect=5
        )

        connector = aiohttp.TCPConnector(
            limit=20,
            ttl_dns_cache=300
        )

        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={
                "User-Agent": "AI-QUANT-PAPER/1.0"
            }
        )

    async def close(self):

        if self.session and not self.session.closed:
            await self.session.close()

    async def _get(self, endpoint, params=None):

        if not self.session or self.session.closed:
            raise RuntimeError(
                "MarketData session not started"
            )

        url = f"{BINANCE_BASE_URL}{endpoint}"

        last_error = None

        for attempt in range(3):

            try:

                async with self.session.get(
                    url,
                    params=params
                ) as response:

                    if response.status in (418, 429):
                        raise RuntimeError(
                            f"Market data rate limited: HTTP {response.status}"
                        )

                    if response.status >= 500:
                        raise RuntimeError(
                            f"Market data server error: HTTP {response.status}"
                        )

                    response.raise_for_status()

                    return await response.json()

            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
                RuntimeError
            ) as exc:

                last_error = exc

                if isinstance(exc, RuntimeError):
                    message = str(exc)

                    if "rate limited" in message:
                        break

                    if "server error" not in message:
                        break

                if attempt < 2:
                    await asyncio.sleep(
                        1.5 * (attempt + 1)
                    )

        raise RuntimeError(
            f"Market request failed: {str(last_error)[:200]}"
        )

    async def get_ticker(self, symbol):

        data = await self._get(
            "/api/v3/ticker/24hr",
            {"symbol": symbol}
        )

        price = float(data["lastPrice"])

        quote_volume = float(
            data["quoteVolume"]
        )

        if price <= 0:
            raise ValueError(
                f"Invalid price for {symbol}"
            )

        return {
            "symbol": symbol,
            "price": price,
            "change_pct": float(
                data["priceChangePercent"]
            ),
            "quote_volume": quote_volume,
            "high": float(data["highPrice"]),
            "low": float(data["lowPrice"]),
            "open": float(data["openPrice"])
        }

    async def get_klines(
        self,
        symbol,
        interval=None,
        limit=None
    ):

        data = await self._get(
            "/api/v3/klines",
            {
                "symbol": symbol,
                "interval": interval or TIMEFRAME,
                "limit": limit or KLINE_LIMIT
            }
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
            "ignore"
        ]

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

        df["close_time"] = pd.to_numeric(
            df["close_time"],
            errors="coerce"
        )

        df = df.dropna(
            subset=numeric_columns + ["close_time"]
        )

        return df.reset_index(drop=True)

    async def get_market_snapshot(self, symbol):

        ticker = await self.get_ticker(symbol)

        if ticker["quote_volume"] < MIN_QUOTE_VOLUME:
            return None

        candles = await self.get_klines(symbol)

        if len(candles) < 61:
            return None

        return {
            "ticker": ticker,
            "candles": candles
        }
