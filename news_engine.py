import aiohttp
import asyncio
import re
import xml.etree.ElementTree as ET


FEED_URLS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/"
]


class NewsEngine:
    def __init__(self):
        self.session = None

    async def start(self):
        timeout = aiohttp.ClientTimeout(total=15)
        self.session = aiohttp.ClientSession(timeout=timeout)

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def fetch_feed(self, url):
        try:
            async with self.session.get(url) as response:
                response.raise_for_status()
                content = await response.text()

            root = ET.fromstring(content)
            articles = []

            for item in root.findall(".//item")[:20]:
                title = item.findtext("title", default="")
                description = item.findtext("description", default="")
                pub_date = item.findtext("pubDate", default="")
                link = item.findtext("link", default="")

                clean_title = re.sub(
                    r"<[^>]+>",
                    "",
                    title
                ).strip()

                clean_description = re.sub(
                    r"<[^>]+>",
                    "",
                    description
                ).strip()

                if clean_title:
                    articles.append({
                        "title": clean_title[:300],
                        "description": clean_description[:500],
                        "published": pub_date,
                        "link": link
                    })

            return articles

        except Exception:
            return []

    async def get_latest_news(self):
        results = await asyncio.gather(
            *[
                self.fetch_feed(url)
                for url in FEED_URLS
            ],
            return_exceptions=True
        )

        articles = []

        for result in results:
            if isinstance(result, list):
                articles.extend(result)

        unique = {}
        for article in articles:
            key = article["title"].lower()
            unique[key] = article

        return list(unique.values())[:30]
