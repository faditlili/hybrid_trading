import asyncio
import logging
import re
import time
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import urljoin, urlparse, urlunparse

import aiohttp

from config import (
    NEWS_REFRESH_SECONDS,
    NEWS_MAX_ITEMS,
    NEWS_REQUEST_TIMEOUT_SECONDS,
)


logger = logging.getLogger(__name__)


FEED_URLS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
]


class NewsEngine:

    def __init__(self):

        self.session = None

        self.latest_news = []

        self.lock = asyncio.Lock()
        self.refresh_lock = asyncio.Lock()

        self.last_fetch = 0.0
        self.last_attempt = 0.0

        self.fetch_interval = max(
            30,
            int(NEWS_REFRESH_SECONDS)
        )

        self.request_timeout = max(
            3,
            int(NEWS_REQUEST_TIMEOUT_SECONDS)
        )

        self.max_feed_size = 2 * 1024 * 1024

        self.max_items_per_feed = min(
            30,
            max(1, int(NEWS_MAX_ITEMS))
        )

        self.max_total_items = max(
            1,
            int(NEWS_MAX_ITEMS)
        )

        self.retry_cooldown = 30

        self.available = False

    async def start(self):

        if self.session and not self.session.closed:
            self.available = True
            return

        timeout = aiohttp.ClientTimeout(
            total=self.request_timeout,
            connect=min(8, self.request_timeout)
        )

        connector = aiohttp.TCPConnector(
            limit=10,
            ttl_dns_cache=300
        )

        try:

            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    "User-Agent": "AI-QUANT/3.1",
                    "Accept": (
                        "application/rss+xml, "
                        "application/atom+xml, "
                        "application/xml, "
                        "text/xml"
                    )
                }
            )

            self.available = True

            logger.info("News engine started")

        except Exception:

            self.session = None
            self.available = False

            logger.exception(
                "News engine initialization failed"
            )

    async def close(self):

        async with self.lock:

            session = self.session

            self.session = None
            self.available = False

            if session and not session.closed:

                try:
                    await session.close()

                except Exception:

                    logger.exception(
                        "News session close failed"
                    )

        logger.info("News engine stopped")

    @staticmethod
    def clean_text(text):

        if text is None:
            return ""

        text = unescape(str(text))

        text = re.sub(
            r"<[^>]*>",
            " ",
            text
        )

        text = re.sub(
            r"[\x00-\x08\x0b\x0c\x0e-\x1f]",
            "",
            text
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        return text.strip()

    @staticmethod
    def valid_url(url):

        if not isinstance(url, str):
            return ""

        url = url.strip()

        if not url or len(url) > 2000:
            return ""

        try:

            parsed = urlparse(url)

            if parsed.scheme not in ("http", "https"):
                return ""

            if not parsed.hostname:
                return ""

            if parsed.username or parsed.password:
                return ""

            if any(
                char.isspace()
                for char in parsed.netloc
            ):
                return ""

            return urlunparse(parsed)

        except (ValueError, TypeError):

            return ""

    @staticmethod
    def normalize_date(value):

        if not value:
            return ""

        value = str(value).strip()

        try:

            try:

                date = datetime.fromisoformat(
                    value.replace("Z", "+00:00")
                )

            except ValueError:

                date = parsedate_to_datetime(value)

            if date.tzinfo is None:

                date = date.replace(
                    tzinfo=timezone.utc
                )

            return date.astimezone(
                timezone.utc
            ).isoformat()

        except (
            ValueError,
            TypeError,
            OverflowError
        ):

            return ""

    @staticmethod
    def date_timestamp(value):

        if not value:
            return 0.0

        try:

            date = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )

            if date.tzinfo is None:

                date = date.replace(
                    tzinfo=timezone.utc
                )

            return date.timestamp()

        except (
            ValueError,
            TypeError,
            OverflowError
        ):

            return 0.0

    @staticmethod
    def get_child(element, names):

        if element is None:
            return None

        for child in element.iter():

            if child is element:
                continue

            tag = child.tag

            if not isinstance(tag, str):
                continue

            local_name = tag.split("}")[-1].lower()

            if local_name in names:
                return child

        return None

    @staticmethod
    def get_element_text(element):

        if element is None:
            return ""

        return "".join(
            element.itertext()
        ).strip()

    @staticmethod
    def normalize_title(title):

        if not isinstance(title, str):
            return ""

        title = title.lower()

        title = re.sub(
            r"[^\w\s]",
            " ",
            title
        )

        title = re.sub(
            r"\s+",
            " ",
            title
        )

        return title.strip()

    def parse_feed(self, root, source_url):

        news = []
        items = []

        for element in root.iter():

            if not isinstance(element.tag, str):
                continue

            tag = element.tag.split("}")[-1].lower()

            if tag in ("item", "entry"):
                items.append(element)

        for item in items[:self.max_items_per_feed]:

            title_element = self.get_child(
                item,
                {"title"}
            )

            if title_element is None:
                continue

            title = self.clean_text(
                self.get_element_text(title_element)
            )

            if not title:
                continue

            link = ""

            for child in item:

                if not isinstance(child.tag, str):
                    continue

                tag = child.tag.split("}")[-1].lower()

                if tag != "link":
                    continue

                rel = child.attrib.get(
                    "rel",
                    "alternate"
                )

                if rel not in ("alternate", ""):
                    continue

                link = (
                    child.attrib.get("href")
                    or self.get_element_text(child)
                )

                if link:
                    break

            if link:

                link = urljoin(
                    source_url,
                    link.strip()
                )

                link = self.valid_url(link)

            description_element = self.get_child(
                item,
                {
                    "description",
                    "summary",
                    "content",
                    "encoded",
                }
            )

            description = self.clean_text(
                self.get_element_text(
                    description_element
                )
            )

            date_element = self.get_child(
                item,
                {
                    "pubdate",
                    "published",
                    "updated",
                    "date",
                }
            )

            published_raw = self.get_element_text(
                date_element
            )

            published = self.normalize_date(
                published_raw
            )

            news.append({

                "title": title[:300],

                "link": link[:1000],

                "description": description[:700],

                "published": published,

                "source": source_url,

            })

        return news

    async def _fetch_feed_result(self, url):

        session = self.session

        if not session or session.closed:
            return False, []

        try:

            async with session.get(
                url,
                allow_redirects=True,
                max_redirects=5
            ) as response:

                if response.status != 200:

                    logger.warning(
                        "RSS source returned HTTP %s",
                        response.status
                    )

                    return False, []

                final_url = self.valid_url(
                    str(response.url)
                )

                if not final_url:

                    logger.warning(
                        "RSS source returned an invalid final URL"
                    )

                    return False, []

                content_length = response.content_length

                if (
                    content_length is not None
                    and content_length > self.max_feed_size
                ):

                    logger.warning(
                        "RSS feed exceeds size limit"
                    )

                    return False, []

                raw_content = await response.content.read(
                    self.max_feed_size + 1
                )

                if len(raw_content) > self.max_feed_size:

                    logger.warning(
                        "RSS feed exceeds size limit"
                    )

                    return False, []

                encoding = response.charset or "utf-8"

                content = raw_content.decode(
                    encoding,
                    errors="replace"
                )

            root = ET.fromstring(content)

            news = self.parse_feed(
                root,
                final_url
            )

            return True, news

        except asyncio.CancelledError:
            raise

        except asyncio.TimeoutError:

            logger.warning(
                "RSS request timeout"
            )

            return False, []

        except (
            aiohttp.ClientError,
            ET.ParseError,
            ValueError,
            TypeError,
            LookupError
        ) as error:

            logger.warning(
                "RSS fetch failed: %s",
                type(error).__name__
            )

            return False, []

        except Exception:

            logger.exception(
                "Unexpected RSS error"
            )

            return False, []

    async def fetch_feed(self, url):

        success, news = await self._fetch_feed_result(
            url
        )

        return news if success else []

    async def fetch_all(self):

        async with self.lock:

            session = self.session

            if not session or session.closed:

                self.available = False

                return self.latest_news

            self.last_attempt = time.monotonic()

            tasks = [
                self._fetch_feed_result(url)
                for url in FEED_URLS
            ]

            try:

                results = await asyncio.gather(
                    *tasks,
                    return_exceptions=True
                )

            except asyncio.CancelledError:
                raise

            combined = []
            successful_sources = 0

            for result in results:

                if isinstance(
                    result,
                    asyncio.CancelledError
                ):
                    raise result

                if isinstance(result, Exception):

                    logger.warning(
                        "RSS task failed: %s",
                        type(result).__name__
                    )

                    continue

                success, news = result

                if success:

                    successful_sources += 1
                    combined.extend(news)

            if successful_sources == 0:

                self.available = False

                logger.warning(
                    "All RSS sources failed; "
                    "keeping previous news"
                )

                return self.latest_news

            unique = {}

            for item in combined:

                normalized_title = self.normalize_title(
                    item.get("title", "")
                )

                if not normalized_title:
                    continue

                existing = unique.get(
                    normalized_title
                )

                if existing is None:

                    unique[normalized_title] = item

                elif (
                    not existing.get("description")
                    and item.get("description")
                ):

                    unique[normalized_title] = item

            news_list = list(unique.values())

            news_list.sort(
                key=lambda item: self.date_timestamp(
                    item.get("published", "")
                ),
                reverse=True
            )

            self.latest_news = news_list[
                :self.max_total_items
            ]

            self.last_fetch = time.monotonic()
            self.available = True

            logger.info(
                "News updated: %s items from %s sources",
                len(self.latest_news),
                successful_sources
            )

            return self.latest_news

    async def get_news(self, limit=20):

        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
        ):
            limit = 20

        limit = max(
            1,
            min(limit, self.max_total_items)
        )

        async with self.refresh_lock:

            now = time.monotonic()

            should_fetch = (
                now - self.last_fetch >= self.fetch_interval
            )

            retry_blocked = (
                self.last_attempt > 0
                and now - self.last_attempt < self.retry_cooldown
            )

            if should_fetch and not retry_blocked:

                await self.fetch_all()

            return self.latest_news[:limit]
