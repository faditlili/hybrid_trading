
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

        if (
            self.session is None
            or self.session.closed
        ):

            timeout = aiohttp.ClientTimeout(
                total=HTTP_TIMEOUT_SECONDS
            )

            connector = aiohttp.TCPConnector(
                limit=10,
                ttl_dns_cache=300
            )

            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    "User-Agent": (
                        "AI-QUANT-Paper-Research/4.0"
                    )
                }
            )

    async def close(self):

        if (
            self.session is not None
            and not self.session.closed
        ):

            await self.session.close()

        self.session = None

    # --------------------------------------------------
    # XML helpers
    # --------------------------------------------------

    @staticmethod
    def _local_name(tag):
        """Return an XML tag without its namespace."""

        if not isinstance(tag, str):
            return ""

        return tag.rsplit("}", 1)[-1].lower()

    @classmethod
    def _child_text(cls, element, name):

        for child in element:

            if cls._local_name(child.tag) == name.lower():

                return (
                    "".join(child.itertext()).strip()
                )

        return ""

    @classmethod
    def _extract_link(cls, element):

        # RSS format.
        link = cls._child_text(
            element,
            "link"
        )

        if link:
            return link[:MAX_LINK_LENGTH]

        # Atom format: <link href="..."/>
        for child in element:

            if cls._local_name(child.tag) == "link":

                href = child.attrib.get(
                    "href",
                    ""
                )

                if href:
                    return href[:MAX_LINK_LENGTH]

        return ""

    @classmethod
    def _parse_feed(cls, raw, source):

        root = ET.fromstring(raw)

        found = []

        # Supports RSS <item> and Atom <entry>.
        for element in root.iter():

            element_name = cls._local_name(
                element.tag
            )

            if element_name not in (
                "item",
                "entry"
            ):
                continue

            title = cls._child_text(
                element,
                "title"
            )

            if not title:
                continue

            link = cls._extract_link(
                element
            )

            found.append({
                "title": title[:MAX_TITLE_LENGTH],
                "link": link,
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

            if (
                self.session is None
                or self.session.closed
            ):
                await self.start()

            async with self.session.get(url) as response:

                if response.status != 200:

                    raise RuntimeError(
                        f"RSS HTTP status {response.status}"
                    )

                raw = await response.content.read(
                    MAX_FEED_BYTES + 1
                )

                if len(raw) > MAX_FEED_BYTES:

                    raise ValueError(
                        "RSS feed exceeds size limit"
                    )

                return self._parse_feed(
                    raw,
                    url
                )

        except Exception as exc:

            logger.warning(
                "RSS feed unavailable (%s): %s",
                url,
                exc
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
                return_exceptions=True
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
                        batch
                    )

            self.available_feed_count = (
                successful_feeds
            )

            # Deduplicate headlines.
            unique = {}

            for item in gathered:

                key = item["title"].casefold()

                unique[key] = item

            if successful_feeds == 0:

                self.last_error = (
                    "All RSS feeds unavailable"
                )

                logger.error(
                    self.last_error
                )

                # Keep previous headlines for diagnostics,
                # but blocks() will fail closed.

            else:

                self.items = list(
                    unique.values()
                )

                if successful_feeds < len(FEEDS):

                    self.last_error = (
                        "Some RSS feeds unavailable"
                    )

                    logger.warning(
                        self.last_error
                    )

                else:

                    self.last_error = None

            # Avoid excessive retries during an outage.
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
            (base.lower(),)
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
            flags=re.IGNORECASE
        ) is not None

    @classmethod
    def _is_relevant(cls, title, symbol):

        terms = cls._symbol_terms(
            symbol
        )

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

        # Fail closed if no source is available.
        if self.available_feed_count == 0:

            logger.warning(
                "Blocking %s: all news sources unavailable",
                symbol
            )

            return True

        for item in self.items:

            title = item.get(
                "title",
                ""
            ).casefold()

            relevant = self._is_relevant(
                title,
                symbol
            )

            if not relevant:
                continue

            if self._is_critical(title):

                logger.warning(
                    "Critical headline detected for %s: %s",
                    symbol,
                    title
                )

                return True

        return False
