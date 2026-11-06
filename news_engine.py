import asyncio
import aiohttp
import logging
import re
import xml.etree.ElementTree as ET

from html import unescape

logger = logging.getLogger(__name__)


FEED_URLS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/"
]


class NewsEngine:

    def __init__(self):

        self.session = None
        self.latest_news = []

    async def start(self):

        if self.session and not self.session.closed:
            return

        timeout = aiohttp.ClientTimeout(
            total=15,
            connect=5
        )

        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "User-Agent": "AI-QUANT-PAPER/1.0"
            }
        )

    async def close(self):

        if self.session and not self.session.closed:
            await self.session.close()

    def clean_text(self, value):

        if not value:
            return ""

        value = re.sub(
            r"<[^>]+>",
            " ",
            value
        )

        value = unescape(value)

        value = re.sub(
            r"\s+",
            " ",
            value
        )

        return value.strip()

    async def fetch_feed(self, url):

        if not self.session or self.session.closed:
            return []

        try:

            async with self.session.get(url) as response:

                response.raise_for_status()

                content = await response.text()

            root = ET.fromstring(content)

            items = root.findall(".//item")

            news = []

            for item in items[:30]:

                title = self.clean_text(
                    item.findtext("title", "")
                )

                link = self.clean_text(
                    item.findtext("link", "")
                )

                description = self.clean_text(
                    item.findtext("description", "")
                )

                published = self.clean_text(
                    item.findtext("pubDate", "")
                )

                if not title:
                    continue

                news.append({
                    "title": title[:300],
                    "description": description[:1000],
                    "link": link[:1000],
                    "published": published[:100]
                })

            return news

        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            ET.ParseError,
            ValueError
        ) as exc:

            logger.warning(
                "News feed failed (%s): %s",
                url,
                str(exc)[:200]
            )

            return []

    async def fetch_all(self):

        feeds = await asyncio.gather(
            *[
                self.fetch_feed(url)
                for url in FEED_URLS
            ],
            return_exceptions=True
        )

        combined = []
        seen = set()

        for feed in feeds:

            if isinstance(feed, Exception):
                continue

            for item in feed:

                key = item["title"].lower()

                if key in seen:
                    continue

                seen.add(key)
                combined.append(item)

        self.latest_news = combined[:30]

        return self.latest_news

        async def get_news(self, limit=20):

        if not isinstance(limit, int):
            limit = 20

        limit = max(1, min(limit, 30))

        news = await self.fetch_all()

        return news[:limit]
