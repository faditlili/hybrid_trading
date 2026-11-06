import asyncio
import logging
import math
import time

from datetime import datetime, timezone

import aiohttp
import pandas as pd

from config import (
    BINGX_BASE_URL,
    BINGX_SYMBOL_MAP,
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
    """Raised when BingX market data is unavailable or invalid."""


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat()


def valid_number(value):
    if isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def safe_float(value, default=None):
    if not valid_number(value):
        return default
    return float(value)


class MarketData:
    """
    BingX Spot public market-data client.

    Public market endpoints do not require an API key or secret.
    This class only reads public market data. It has no order,
    account, withdrawal, or private trading methods.
    """

    INTERVALS = {
        "1m", "3m", "5m", "15m", "30m",
        "1h", "2h", "4h", "6h", "8h",
        "12h", "1d", "3d", "1w", "1M",
    }

    def __init__(self):
        self.base_url = BINGX_BASE_URL.rstrip("/")
        self.symbols = list(SYMBOLS)
        self.symbol_map = dict(BINGX_SYMBOL_MAP)
        self.timeframe = TIMEFRAME
        self.kline_limit = int(KLINE_LIMIT)
        self.min_quote_volume = float(MIN_QUOTE_VOLUME)

        if self.timeframe not in self.INTERVALS:
            raise ValueError(f"Unsupported BingX interval: {self.timeframe}")

        if self.kline_limit < 60 or self.kline_limit > 1000:
            raise ValueError("KLINE_LIMIT must be between 60 and 1000.")

        if not valid_number(self.min_quote_volume) or self.min_quote_volume < 0:
            raise ValueError("MIN_QUOTE_VOLUME must be a non-negative number.")

        timeout = aiohttp.ClientTimeout(
            total=float(HTTP_TIMEOUT_SECONDS),
            connect=float(HTTP_CONNECT_TIMEOUT_SECONDS),
        )

        self._connector_limit = max(1, int(HTTP_MAX_CONNECTIONS))
        self._retry_attempts = max(0, int(HTTP_RETRY_ATTEMPTS))

        self._timeout = timeout
        self._session = None
        self._session_lock = asyncio.Lock()
        self._request_lock = asyncio.Lock()
        self._active_requests = 0
        self._idle_event = asyncio.Event()
        self._idle_event.set()
        self._closing = False
        self._last_request_monotonic = 0.0

        self.last_success = None
        self.last_errors = {}
        self.last_error = None

    async def start(self):
        async with self._session_lock:
            if self._closing:
                raise MarketDataError("Market data client is closing.")

            if self._session is None or self._session.closed:
                connector = aiohttp.TCPConnector(
                    limit=self._connector_limit,
                    enable_cleanup_closed=True,
                )
                self._session = aiohttp.ClientSession(
                    timeout=self._timeout,
                    connector=connector,
                    headers={"Accept": "application/json"},
                )

        return True

    async def close(self):
        self._closing = True

        await self._idle_event.wait()

        async with self._session_lock:
            if self._session is not None and not self._session.closed:
                await self._session.close()
            self._session = None

        return True

    async def _acquire_session(self):
        if self._closing:
            raise MarketDataError("Market data client is closing.")

        await self.start()

        async with self._session_lock:
            if self._session is None or self._session.closed:
                raise MarketDataError("HTTP session is unavailable.")

            self._active_requests += 1
            self._idle_event.clear()
            return self._session

    async def _release_session(self):
        async with self._session_lock:
            self._active_requests = max(0, self._active_requests - 1)
            if self._active_requests == 0:
                self._idle_event.set()

    @staticmethod
    def _extract_data(payload):
        if not isinstance(payload, dict):
            raise MarketDataError("BingX returned a non-object response.")

        code = payload.get("code")
        if str(code) != "0":
            message = payload.get("msg") or payload.get("message") or "Unknown API error"
            raise MarketDataError(
                f"BingX API error {code}: {message}"
            )

        if "data" not in payload:
            raise MarketDataError("BingX response does not contain data.")

        return payload["data"]

    async def _request_json(self, endpoint, params=None):
        """
        Perform a rate-limited public GET request.

        BingX public market endpoints are rate-limited. Requests are
        spaced by at least one second across this client instance.
        """
        params = params or {}
        url = f"{self.base_url}{endpoint}"

        last_exception = None

        for attempt in range(self._retry_attempts + 1):
            session = await self._acquire_session()

            try:
                async with self._request_lock:
                    elapsed = time.monotonic() - self._last_request_monotonic
                    if elapsed < 1.05:
                        await asyncio.sleep(1.05 - elapsed)

                    async with session.get(url, params=params) as response:
                        self._last_request_monotonic = time.monotonic()
                        status = response.status
                        text = await response.text()

                    if status in (418, 429):
                        raise MarketDataError(
                            f"BingX rate limit response HTTP {status}: {text[:300]}"
                        )

                    if status >= 500:
                        raise MarketDataError(
                            f"BingX server error HTTP {status}: {text[:300]}"
                        )

                    if status != 200:
                        raise MarketDataError(
                            f"BingX HTTP {status}: {text[:500]}"
                        )

                    try:
                        payload = await asyncio.to_thread(
                            __import__("json").loads, text
                        )
                    except Exception as exc:
                        raise MarketDataError(
                            "BingX returned invalid JSON."
                        ) from exc

                    data = self._extract_data(payload)
                    self.last_success = utc_timestamp()
                    self.last_error = None
                    return data

            except asyncio.CancelledError:
                raise

            except (aiohttp.ClientError, asyncio.TimeoutError, MarketDataError) as exc:
                last_exception = exc
                self.last_error = str(exc)
                self.last_errors[endpoint] = str(exc)[:500]

                # Do not retry rate limits or ordinary client errors.
                message = str(exc)
                if "HTTP 418" in message or "HTTP 429" in message:
                    break
                if "BingX HTTP 4" in message:
                    break

                if attempt < self._retry_attempts:
                    await asyncio.sleep(min(2 ** attempt, 5))

            finally:
                await self._release_session()

        raise MarketDataError(
            f"Unable to retrieve BingX data from {endpoint}: {last_exception}"
        )

    def _to_bingx_symbol(self, symbol):
        if not isinstance(symbol, str):
            raise MarketDataError("Symbol must be a string.")

        symbol = symbol.upper().strip()

        mapped = self.symbol_map.get(symbol)
        if mapped:
            return mapped

        # Accept an already formatted BASE-USDT symbol.
        if "-" in symbol and symbol.endswith("-USDT"):
            return symbol

        # Convert compact quote symbols such as ADAUSDT to ADA-USDT.
        if symbol.endswith("USDT") and len(symbol) > 4:
            return f"{symbol[:-4]}-USDT"

        raise MarketDataError(f"No BingX symbol mapping for {symbol}.")

    @staticmethod
    def _first_item(data, label):
        if isinstance(data, list):
            if not data:
                raise MarketDataError(f"BingX returned empty {label} data.")
            return data[0]

        if isinstance(data, dict):
            return data

        raise MarketDataError(f"Unexpected BingX {label} response format.")

    async def get_ticker(self, symbol):
        bingx_symbol = self._to_bingx_symbol(symbol)

        data = await self._request_json(
            "/openApi/spot/v1/ticker/24hr",
            {"symbol": bingx_symbol},
        )

        item = self._first_item(data, "ticker")

        price = safe_float(item.get("lastPrice"))
        quote_volume = safe_float(item.get("quoteVolume"))
        change_percent = safe_float(item.get("priceChangePercent"), 0.0)

        if price is None or price <= 0:
            raise MarketDataError(
                f"Invalid latest price for {symbol}."
            )

        if quote_volume is None or quote_volume < 0:
            raise MarketDataError(
                f"Invalid 24h quote volume for {symbol}."
            )

        exchange_time_ms = item.get("closeTime")
        exchange_timestamp = None

        if valid_number(exchange_time_ms):
            try:
                exchange_timestamp = datetime.fromtimestamp(
                    float(exchange_time_ms) / 1000.0,
                    tz=timezone.utc,
                ).isoformat()
            except (ValueError, OSError, OverflowError):
                exchange_timestamp = None

        # timestamp is local receipt time for PaperTrader's freshness check.
        return {
            "symbol": symbol,
            "provider_symbol": bingx_symbol,
            "price": price,
            "quote_volume": quote_volume,
            "change_percent": change_percent,
            "timestamp": utc_timestamp(),
            "exchange_timestamp": exchange_timestamp,
            "source": "BingX Spot",
        }

    async def get_klines(self, symbol, interval=None, limit=None):
        bingx_symbol = self._to_bingx_symbol(symbol)
        interval = interval or self.timeframe
        limit = int(limit or self.kline_limit)

        if interval not in self.INTERVALS:
            raise MarketDataError(
                f"Unsupported BingX kline interval: {interval}"
            )

        if limit < 1 or limit > 1440:
            raise MarketDataError("BingX kline limit must be between 1 and 1440.")

        data = await self._request_json(
            "/openApi/spot/v2/market/kline",
            {
                "symbol": bingx_symbol,
                "interval": interval,
                "limit": limit,
            },
        )

        if not isinstance(data, list) or not data:
            raise MarketDataError(
                f"No kline data returned for {symbol}."
            )

        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        rows = []
        seen = set()

        for candle in data:
            if not isinstance(candle, (list, tuple)) or len(candle) < 7:
                continue

            try:
                open_time = int(candle[0])
                open_price = float(candle[1])
                high_price = float(candle[2])
                low_price = float(candle[3])
                close_price = float(candle[4])
                volume = float(candle[5])
                close_time = int(candle[6])
                quote_volume = (
                    float(candle[7])
                    if len(candle) > 7 and valid_number(candle[7])
                    else 0.0
                )
            except (TypeError, ValueError, OverflowError):
                continue

            values = (
                open_price, high_price, low_price,
                close_price, volume, quote_volume,
            )

            if not all(valid_number(value) for value in values):
                continue

            if min(open_price, high_price, low_price, close_price) <= 0:
                continue

            if volume < 0 or quote_volume < 0:
                continue

            if high_price < max(open_price, close_price, low_price):
                continue

            if low_price > min(open_price, close_price, high_price):
                continue

            # Exclude the currently forming candle.
            if close_time >= now_ms:
                continue

            if open_time in seen:
                continue

            seen.add(open_time)

            rows.append({
                "timestamp": pd.to_datetime(
                    open_time, unit="ms", utc=True
                ),
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
                "quote_volume": quote_volume,
                "close_time": pd.to_datetime(
                    close_time, unit="ms", utc=True
                ),
            })

        if len(rows) < 60:
            raise MarketDataError(
                f"Not enough valid completed candles for {symbol}: {len(rows)}."
            )

        frame = pd.DataFrame(rows)
        frame = frame.sort_values("timestamp")
        frame = frame.drop_duplicates(
            subset=["timestamp"], keep="last"
        ).reset_index(drop=True)

        if frame.empty:
            raise MarketDataError(f"Empty validated candle frame for {symbol}.")

        # Reject candles that are too old for the configured interval.
        latest_close = frame["close_time"].iloc[-1]
        age_seconds = (
            datetime.now(timezone.utc) - latest_close.to_pydatetime()
        ).total_seconds()

        interval_seconds = {
            "1m": 60, "3m": 180, "5m": 300, "15m": 900,
            "30m": 1800, "1h": 3600, "2h": 7200,
            "4h": 14400, "6h": 21600, "8h": 28800,
            "12h": 43200, "1d": 86400, "3d": 259200,
            "1w": 604800,
        }

        max_age = interval_seconds.get(interval, 31 * 86400) * 3
        if age_seconds < 0 or age_seconds > max_age:
            raise MarketDataError(
                f"Latest BingX candle for {symbol} is stale "
                f"({age_seconds:.0f} seconds old)."
            )

        return frame

    async def get_market_snapshot(self, symbol):
        ticker, candles = await asyncio.gather(
            self.get_ticker(symbol),
            self.get_klines(symbol),
        )

        latest_candle = candles.iloc[-1]

        return {
            "symbol": symbol,
            "price": ticker["price"],
            "quote_volume": ticker["quote_volume"],
            "change_percent": ticker["change_percent"],
            "timestamp": ticker["timestamp"],
            "exchange_timestamp": ticker.get("exchange_timestamp"),
            "latest_candle_close": float(latest_candle["close"]),
            "candles": candles,
            "klines": candles,
            "source": "BingX Spot",
        }

    def _check_liquidity(self, ticker):
        volume = safe_float(ticker.get("quote_volume"))
        return volume is not None and volume >= self.min_quote_volume

    async def get_liquid_symbols(self):
        """
        Return configured symbols whose 24h quote volume passes the
        configured threshold. This avoids scanning unconfigured pairs.
        """
        results = []

        for symbol in self.symbols:
            try:
                ticker = await self.get_ticker(symbol)
                if self._check_liquidity(ticker):
                    results.append(symbol)
            except MarketDataError as exc:
                logger.warning(
                    "Skipping %s during liquidity check: %s",
                    symbol, exc,
                )

        return results

    def get_status(self):
        session_running = (
            self._session is not None
            and not self._session.closed
            and not self._closing
        )

        return {
            "service": "BingX Spot Public Market Data",
            "provider": "bingx",
            "running": session_running,
            "active_requests": self._active_requests,
            "last_success": self.last_success,
            "last_error": self.last_error,
            "last_errors": dict(self.last_errors),
            "closing": self._closing,
            "authenticated": False,
            "trading_enabled": False,
        }
