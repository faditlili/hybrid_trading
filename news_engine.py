
"""Optional RSS headline risk filter.
Headlines never create trade signals.
RSS failures never authorize an entry by themselves.
"""

import asyncio
import logging
import time

import aiohttp
from defusedxml import ElementTree as ET

from config import NEWS_REFRESH_SECONDS, HTTP_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

FEEDS = (
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
)

CRITICAL = (
    "exploit",
    "security breach",
    "bankruptcy",
    "insolvency",
    "trading halted",
    "exchange hacked",
    "major hack",
    "funds stolen",
    "withdrawals suspended",
    "regulatory investigation",
)

MAX_FEED_BYTES = 1_000_000
MAX_ITEMS_PER_FEED = 30

# Conservative aliases for common symbols.
SYMBOL_ALIASES = {
    "BTC": ("bitcoin", "btc"),
    "ETH": ("ethereum", "ether", "eth"),
    "BNB": ("binance coin", "bnb"),
    "SOL": ("solana", "sol"),
    "XRP": ("ripple", "xrp"),
}


class NewsEngine:

    def __init__(self):
        self.session = None
        self.items = []
        self.updated = 0
        self.last_error = None
        self.refresh_lock = asyncio.Lock()

    async def start(self):
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(
                total=HTTP_TIMEOUT_SECONDS
            )

            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "User-Agent": "AI-QUANT-Paper-Research/4.0"
                }
            )

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

        self.session = None

    async def _get_feed(self, url):
        try:
            async with self.session.get(url) as response:

                if response.status != 200:
                    raise RuntimeError(
                        f"RSS HTTP status {response.status}"
                    )

                raw = await response.content.read(
                    MAX_FEED_BYTES + 1
                )

                if len(raw) > MAX_FEED_BYTES:
                    raise ValueError("RSS feed exceeds size limit")

                root = ET.fromstring(raw)

                found = []

                for item in root.findall(".//item")[
                    :MAX_ITEMS_PER_FEED
                ]:
                    title = (
                        item.findtext("title") or ""
                    ).strip()

                    link = (
                        item.findtext("link") or ""
                    ).strip()

                    if not title:
                        continue

                    found.append({
                        "title": title[:300],
                        "link": link[:500],
                        "source": url,
                    })

                return found

        except Exception as exc:
            logger.warning(
                "RSS feed unavailable (%s): %s",
                url,
                exc
            )
            return []

    async def refresh(self, force=False):

        async with self.refresh_lock:

            now = time.time()

            if (
                not force
                and self.updated
                and now - self.updated < NEWS_REFRESH_SECONDS
            ):
                return self.items

            await self.start()

            batches = await asyncio.gather(
                *(
                    self._get_feed(url)
                    for url in FEEDS
                ),
                return_exceptions=True
            )

            gathered = []

            for batch in batches:
                if isinstance(batch, list):
                    gathered.extend(batch)

            # Deduplicate headlines.
            unique = {}
            for item in gathered:
                key = item["title"].casefold()
                unique[key] = item

            if gathered:
                self.items = list(unique.values())
                self.last_error = None
            else:
                self.last_error = "All RSS feeds unavailable"
                logger.warning(self.last_error)

            # Record refresh time to avoid excessive retries.
            self.updated = time.time()

            return self.items

    @staticmethod
    def _symbol_terms(symbol):
        base = str(symbol).upper().split("-")[0]

        aliases = SYMBOL_ALIASES.get(
            base,
            (base.lower(),)
        )

        return tuple(
            term.casefold()
            for term in aliases
        )

    async def blocks(self, symbol):

        items = await self.refresh()

        terms = self._symbol_terms(symbol)

        for item in items:

            title = item["title"].casefold()

            relevant = any(
                term in title
                for term in terms
            )

            critical = any(
                keyword in title
                for keyword in CRITICAL
            )

            if relevant and critical:
                logger.warning(
                    "Critical headline detected for %s",
                    symbol
                )
                return True

        return False
