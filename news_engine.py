
"""RSS/Atom headline risk filter for AI QUANT.

Educational paper simulation only.
Headlines never generate trading signals.
If all news sources fail, new paper entries are blocked.
"""

import asyncio
import logging
import re
import time

import aiohttp
from defusedxml import ElementTree as ET

from config import NEWS_REFRESH_SECONDS, HTTP_TIMEOUT_SECONDS


logger = logging.getLogger("AI_QUANT.news")


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
    "exchange suspended",
    "exchange insolvency",
    "اختراق",
    "قرصنة",
    "إفلاس",
    "احتيال",
    "سرقة أموال",
    "تعليق السحب",
    "إيقاف التداول",
    "تحقيق تنظيمي",
)

MAX_FEED_BYTES = 1_000_000
MAX_ITEMS_PER_FEED = 30
MAX_TITLE_LENGTH = 300
MAX_LINK_LENGTH = 500

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
        self.available_feed_count = 0
        self.refresh_lock = asyncio.Lock()

    # --------------------------------------------------
    # Lifecycle
    # --------------------------------------------------

    async def start(self):

        if self.session is not None and not self.session.closed:
            return

        timeout = aiohttp.ClientTimeout(
            total=HTTP_TIMEOUT_SECONDS
        )

        connector = aiohttp.TCPConnector(
            limit=10,
            ttl_dns_cache=300,
        )

        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={
                "User-Agent": "AI-QUANT-Paper-Research/4.0"
            },
        )

    async def close(self):

        if self.session is not None:
            if not self.session.closed:
                await self.session.close()

        self.session = None

    # --------------------------------------------------
    # XML helpers
    # --------------------------------------------------

    @staticmethod
    def _local_name(tag):
        if not isinstance(tag, str):
            return ""

        return tag.rsplit("}", 1)[-1].lower()

    @classmethod
    def _child_text(cls, element, name):

        for child in element:

            if cls._local_name(child.tag) == name.lower():
                return "".join(child.itertext()).strip()

        return ""

    @classmethod
    def _extract_link(cls, element):

        # RSS link.
        link = cls._child_text(element, "link")

        if link:
            return link[:MAX_LINK_LENGTH]

        # Atom link.
        for child in element:

            if cls._local_name(child.tag) != "link":
                continue

            rel = child.attrib.get("rel", "alternate")

            if rel not in ("alternate", ""):
                continue

            href = child.attrib.get("href", "").strip()

            if href:
                return href[:MAX_LINK_LENGTH]

        return ""

    @classmethod
    def _parse_feed(cls, raw, source):

        if not isinstance(raw, bytes) or not raw:
            raise ValueError("Empty RSS response")

        root = ET.fromstring(raw)

        found = []

        for element in root.iter():

            element_name = cls._local_name(element.tag)

            if element_name not in ("item", "entry"):
                continue

            title = cls._child_text(element, "title")

            if not title:
                continue

            # Normalize whitespace.
            title = " ".join(title.split())

            found.append({
                "title": title[:MAX_TITLE_LENGTH],
                "link": cls._extract_link(element),
                "source": source,
            })

            if len(found) >= MAX_ITEMS_PER_FEED:
                break

        return found

    # --------------------------------------------------
    # Feed retrieval
    # --------------------------------------------------

    async def _get_feed(self, url):
        """Return a list on success, None on failure."""

        try:

            if self.session is None or self.session.closed:
                await self.start()

            async with self.session.get(
                url,
                allow_redirects=True,
            ) as response:

                if response.status != 200:
                    raise RuntimeError(
                        f"RSS HTTP status {response.status}"
                    )

                content_length = response.content_length

                if (
                    content_length is not None
                    and content_length > MAX_FEED_BYTES
                ):
                    raise ValueError(
                        "RSS feed exceeds size limit"
                    )

                raw = await response.content.read(
                    MAX_FEED_BYTES + 1
                )

                if len(raw) > MAX_FEED_BYTES:
                    raise ValueError(
                        "RSS feed exceeds size limit"
                    )

                return self._parse_feed(raw, url)

        except asyncio.CancelledError:
            raise

        except Exception as exc:

            logger.warning(
                "RSS feed unavailable (%s): %s",
                url,
                type(exc).__name__,
            )

            return None

    # --------------------------------------------------
    # Refresh
    # --------------------------------------------------

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
                return_exceptions=True,
            )

            gathered = []
            successful_feeds = 0

            for batch in batches:

                if isinstance(batch, list):

                    successful_feeds += 1
                    gathered.extend(batch)

                elif isinstance(batch, Exception):

                    logger.warning(
                        "Unexpected RSS retrieval error: %s",
                        type(batch).__name__,
                    )

            self.available_feed_count = successful_feeds

            # Deduplicate by normalized headline.
            unique = {}

            for item in gathered:

                key = " ".join(
                    item["title"].casefold().split()
                )

                if key:
                    unique.setdefault(key, item)

            if successful_feeds == 0:

                self.last_error = "All RSS feeds unavailable"

                logger.error(self.last_error)

                # Retain previous headlines for diagnostics.
                # blocks() still fails closed.

            else:

                self.items = list(unique.values())

                if successful_feeds < len(FEEDS):

                    self.last_error = (
                        "Some RSS feeds unavailable"
                    )

                    logger.warning(self.last_error)

                else:

                    self.last_error = None

            self.updated = time.time()

            return self.items

    # --------------------------------------------------
    # Symbol matching
    # --------------------------------------------------

    @staticmethod
    def _symbol_terms(symbol):

        base = (
            str(symbol)
            .upper()
            .split("-")[0]
            .split("/")[0]
            .strip()
        )

        aliases = SYMBOL_ALIASES.get(
            base,
            (base.lower(),),
        )

        return tuple(
            term.casefold()
            for term in aliases
            if term
        )

    @staticmethod
    def _contains_term(text, term):
        """Match whole words or phrases, not substrings."""

        pattern = (
            r"(?<!\w)"
            + re.escape(term)
            + r"(?!\w)"
        )

        return re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        ) is not None

    @classmethod
    def _is_relevant(cls, title, symbol):

        terms = cls._symbol_terms(symbol)

        return any(
            cls._contains_term(title, term)
            for term in terms
        )

    @classmethod
    def _is_critical(cls, title):

        return any(
            cls._contains_term(title, keyword)
            for keyword in CRITICAL
        )

    # --------------------------------------------------
    # Risk filter
    # --------------------------------------------------

    async def blocks(self, symbol):
        """
        Return True when a new paper entry should be blocked.

        Reasons:
        - All news feeds unavailable.
        - A relevant critical headline was detected.

        News never creates BUY or SELL signals.
        """

        await self.refresh()

        if self.available_feed_count == 0:

            logger.warning(
                "Blocking %s: all news sources unavailable",
                symbol,
            )

            return True

        for item in self.items:

            title = item.get("title", "")

            if not self._is_relevant(title, symbol):
                continue

            if self._is_critical(title):

                logger.warning(
                    "Critical headline detected for %s",
                    symbol,
                )

                return True

        return False
