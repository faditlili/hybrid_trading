import aiohttp
import pandas as pd
from config import BINANCE_BASE_URL, MIN_QUOTE_VOLUME, TIMEFRAME, KLINE_LIMIT


class MarketData:
    def __init__(self):
        self.session = None

    async def start(self):
        timeout = aiohttp.ClientTimeout(total=15)
        self.session = aiohttp.ClientSession(timeout=timeout)

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def _get(self, endpoint, params=None):
        if not self.session:
            raise RuntimeError("MarketData session not started")

        url = f"{BINANCE_BASE_URL}{endpoint}"

        async with self.session.get(url, params=params) as response:
            response.raise_for_status()
            return await response.json()

    async def get_ticker(self, symbol):
        data = await self._get(
            "/api/v3/ticker/24hr",
            {"symbol": symbol}
        )

        price = float(data["lastPrice"])
        quote_volume = float(data["quoteVolume"])

        if price <= 0:
            raise ValueError(f"Invalid price for {symbol}")

        return {
            "symbol": symbol,
            "price": price,
            "change_pct": float(data["priceChangePercent"]),
            "quote_volume": quote_volume,
            "high": float(data["highPrice"]),
            "low": float(data["lowPrice"]),
            "open": float(data["openPrice"])
        }

    async def get_klines(self, symbol, interval=None, limit=None):
        data = await self._get(
            "/api/v3/klines",
            {
                "symbol": symbol,
                "interval": interval or TIMEFRAME,
                "limit": limit or KLINE_LIMIT
            }
        )

        columns = [
            "open_time", "open", "high", "low", "close",
            "volume", "close_time", "quote_volume",
            "trades", "taker_buy_base", "taker_buy_quote",
            "ignore"
        ]

        df = pd.DataFrame(data, columns=columns)

        for column in [
            "open", "high", "low", "close",
            "volume", "quote_volume"
        ]:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

        return df.dropna().reset_index(drop=True)

    async def get_market_snapshot(self, symbol):
        ticker = await self.get_ticker(symbol)

        if ticker["quote_volume"] < MIN_QUOTE_VOLUME:
            return None

        candles = await self.get_klines(symbol)

        if len(candles) < 60:
            return None

        return {
            "ticker": ticker,
            "candles": candles
        }
