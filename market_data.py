"""Asynchronous concurrent public REST collector pipeline tracking standard spot instruments."""
import asyncio
import json
import logging
from datetime import datetime, timezone
import aiohttp
import pandas as pd
import config

log = logging.getLogger(__name__)
class BingXMarketData:
    def __init__(self, session=None):
        self._session = session
        self._owned = session is None
        self.last_success = None
        self.last_error = None
    async def start(self):
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=config.HTTP_TIMEOUT_SECONDS
            )
            self._session = aiohttp.ClientSession(
                timeout=timeout, 
                headers={"User-Agent": "AI-QUANT/4.0"}
            )
        return self
    async def close(self):
        if (
            self._owned and self._session 
            and not self._session.closed
        ): 
            await self._session.close()
        self._session = None
    async def _get(self, path, params):
        await self.start()
        url = config.BINGX_BASE_URL + path
        async with self._session.get(
            url, params=params, 
            allow_redirects=False
        ) as r:
            if r.status != 200:
                raise RuntimeError(
                    f"BingX HTTP {r.status}"
                )
            raw = await r.content.read(
                1_048_577
            )
            if len(raw) > 1_048_576:
                raise ValueError(
                    "Response too large"
                )
            data = json.loads(raw)
            if (
                not isinstance(data, dict) 
                or data.get("code", 0) 
                not in (0, "0", None)
            ):
                raise ValueError(
                    "BingX API anomaly"
                )
            self.last_success = (
                datetime.now(timezone.utc)
                .isoformat()
            )
            return data.get("data")
    @staticmethod
    def normalize_symbol(symbol):
        s = (
            str(symbol).upper()
            .replace("/", "-")
        )
        if (
            "-" not in s 
            and s.endswith("USDT")
        ):
            s = s[:-4] + "-USDT"
        return s
    async def get_ticker(self, symbol):
        symbol = self.normalize_symbol(
            symbol
        )
        data = await self._get(
            config.BINGX_TICKER_PATH,
            {"symbol": symbol}
        )
        if isinstance(data, list):
            data = next(
                (
                    x for x in data 
                    if x.get("symbol") 
                    == symbol
                ), 
                None
            )
        return {
            "symbol": symbol,
            "last": float(
                data.get(
                    "lastPrice", 
                    data.get("last", 0)
                )
            ),
            "quote_volume": float(
                data.get("quoteVolume", 0)
            ),
            "change_pct": float(
                data.get(
                    "priceChangePercent", 0
                )
            )
        }
    async def get_klines(
        self, symbol, 
        interval=config.TIMEFRAME, 
        limit=config.KLINE_LIMIT
    ):
        symbol = self.normalize_symbol(
            symbol
        )
        raw_sym = symbol.replace(
            "-", ""
        )
        data = await self._get(
            config.BINGX_KLINE_PATH,
            {
                "symbol": raw_sym,
                "interval": interval,
                "limit": int(limit)
            }
        )
        rows = []
        for row in data:
            if isinstance(row, dict):
                vals = [
                    row.get(k)
                    for k in (
                        "time", "open",
                        "high", "low",
                        "close", "volume"
                    )
                ]
            else:
                vals = row[:6]
            rows.append(
                [float(x) for x in vals]
            )
        return pd.DataFrame(
            rows,
            columns=[
                "timestamp", "open",
                "high", "low",
                "close", "volume"
            ]
        )
    async def snapshot(self, symbol):
        ticker, candles = await asyncio.gather(
            self.get_ticker(symbol),
            self.get_klines(symbol)
        )
        return {
            "ticker": ticker,
            "candles": candles
        }

    def status(self):
        return {
            "provider": "BingX public API",
            "last_success": self.last_success,
            "last_error": self.last_error,
            "authenticated": False
        }
