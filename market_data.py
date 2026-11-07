"""Public BingX market-data client; contains no private/order endpoints."""
import asyncio
import aiohttp
from config import BINGX_BASE_URL, BINGX_TICKER_PATH, BINGX_KLINE_PATH, HTTP_TIMEOUT_SECONDS, KLINE_LIMIT

class BingXMarketData:
    def __init__(self):
        self.session = None
        self.last_error = None

    async def start(self):
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SECONDS)
            self.session = aiohttp.ClientSession(timeout=timeout, headers={"User-Agent":"AI-QUANT/4.0"})

    async def close(self):
        if self.session and not self.session.closed: await self.session.close()
        self.session = None

    async def _get(self, path, params):
        await self.start()
        try:
            async with self.session.get(BINGX_BASE_URL + path, params=params) as response:
                if response.status != 200: raise RuntimeError(f"BingX HTTP {response.status}")
                payload = await response.json(content_type=None)
                if not isinstance(payload, dict) or payload.get("code", 0) not in (0, "0", None):
                    raise RuntimeError(f"BingX API error: {str(payload)[:300]}")
                self.last_error = None
                return payload.get("data", payload)
        except Exception as exc:
            self.last_error = str(exc)
            raise

    async def ticker(self, symbol):
        data = await self._get(BINGX_TICKER_PATH, {"symbol": symbol})
        if isinstance(data, list): data = data[0] if data else {}
        if not isinstance(data, dict): raise ValueError("Unexpected ticker response")
        price = data.get("lastPrice", data.get("last", data.get("price")))
        return {"last": float(price), "raw": data}

    async def klines(self, symbol, interval="15m", limit=KLINE_LIMIT):
        data = await self._get(BINGX_KLINE_PATH, {"symbol": symbol, "interval": interval, "limit": int(limit)})
        if isinstance(data, dict): data = data.get("data", data.get("klines", []))
        if not isinstance(data, list): raise ValueError("Unexpected kline response")
        rows=[]
        for item in data:
            if isinstance(item, dict):
                get=lambda *keys: next((item[k] for k in keys if k in item), None)
                vals=[get("open","o"),get("high","h"),get("low","l"),get("close","c"),get("volume","v")]
            elif isinstance(item, (list,tuple)) and len(item)>=6: vals=item[1:6]
            else: continue
            try: rows.append([float(x) for x in vals])
            except (TypeError,ValueError): continue
        return rows
