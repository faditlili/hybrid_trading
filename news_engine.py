import asyncio
import logging
import re
import time
import xml.etree.ElementTree as ET

from html import unescape

import aiohttp


logger = logging.getLogger(__name__)


FEED_URLS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/"
]


class NewsEngine:

    def __init__(self):

        self.session = None
        self.latest_news = []
        self.lock = asyncio.Lock()

        self.last_fetch = 0
        self.fetch_interval = 300

    async def start(self):

        if self.session and not self.session.closed:
            return

        timeout = aiohttp.ClientTimeout(
            total=15,
            connect=8
        )

        connector = aiohttp.TCPConnector(
            limit=10,
            ttl_dns_cache=300
        )

        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={
                "User-Agent": "AI-QUANT/3.0"
            }
        )

        logger.info("News engine started")

    async def close(self):

        if self.session and not self.session.closed:

            await self.session.close()

        self.session = None

        logger.info("News engine stopped")

    def clean_text(self, text):

        if not text:
            return ""

        text = unescape(str(text))

        text = re.sub(
            r"<[^>]+>",
            " ",
            text
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        return text.strip()

    async def fetch_feed(self, url):

        if not self.session:
            return []

        try:

            async with self.session.get(url) as response:

                if response.status != 200:

                    logger.warning(
                        "RSS source returned HTTP %s",
                        response.status
                    )

                    return []

                content = await response.text()

            root = ET.fromstring(content)

            items = root.findall(
                ".//item"
            )

            # RSS 2.0 fallback for Atom feeds
            if not items:

                items = root.findall(
                    ".//{http://www.w3.org/2005/Atom}entry"
                )

            news = []

            for item in items[:30]:

                title_element = item.find("title")

                if title_element is None:

                    title_element = item.find(
                        "{http://www.w3.org/2005/Atom}title"
                    )

                if title_element is None:
                    continue

                title = self.clean_text(
                    title_element.text
                )

                if not title:
                    continue

                link_element = item.find("link")

                if link_element is None:

                    link_element = item.find(
                        "{http://www.w3.org/2005/Atom}link"
                    )

                link = ""

                if link_element is not None:

                    link = (
                        link_element.text
                        or link_element.attrib.get("href", "")
                    )

                description_element = item.find(
                    "description"
                )

                if description_element is None:

                    description_element = item.find(
                        "{http://www.w3.org/2005/Atom}summary"
                    )

                description = ""

                if description_element is not None:

                    description = self.clean_text(
                        description_element.text
                    )

                date_element = item.find("pubDate")

                if date_element is None:

                    date_element = item.find(
                        "{http://www.w3.org/2005/Atom}published"
                    )

                published = ""

                if date_element is not None:

                    published = self.clean_text(
                        date_element.text
                    )

                news.append({
                    "title": title[:300],
                    "link": str(link)[:1000],
                    "description": description[:700],
                    "published": published[:100],
                    "source": url
                })

            return news

        except asyncio.TimeoutError:

            logger.warning(
                "RSS timeout: %s",
                url
            )

            return []

        except (
            aiohttp.ClientError,
            ET.ParseError,
            ValueError,
            TypeError
        ) as error:

            logger.warning(
                "RSS fetch failed for %s: %s",
                url,
                error
            )

            return []

    async def fetch_all(self):

        async with self.lock:

            if not self.session:
                return self.latest_news

            tasks = [
                self.fetch_feed(url)
                for url in FEED_URLS
            ]

            results = await asyncio.gather(
                *tasks,
                return_exceptions=True
            )

            combined = []

            for result in results:

                if isinstance(result, Exception):

                    logger.warning(
                        "RSS task failed: %s",
                        result
                    )

                    continue

                combined.extend(result)

            unique = {}

            for item in combined:

                title = item.get(
                    "title",
                    ""
                ).strip().lower()

                if title and title not in unique:

                    unique[title] = item

            self.latest_news = list(
                unique.values()
            )[:60]

            self.last_fetch = time.time()

            logger.info(
                "News updated: %s items",
                len(self.latest_news)
            )

            return self.latest_news

    async def get_news(self, limit=20):

        if not isinstance(limit, int):
            limit = 20

        limit = max(
            1,
            min(limit, 60)
        )

        now = time.time()

        if (
            not self.latest_news
            or now - self.last_fetch >= self.fetch_interval
        ):

            await self.fetch_all()

        return self.latest_news[:limit]
