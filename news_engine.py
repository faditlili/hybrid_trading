"""Defensive asynchronous syndication ingestion stack layer."""
import asyncio
import aiohttp
from defusedxml import ElementTree as ET

FEEDS = (
    "https://coindesk.com"
    "/outboundfeeds/rss/",
    "https://cointelegraph.com"
)
class NewsEngine:
    CRITICAL_KEYWORDS = {
        "hack", "exploit", "sec", 
        "lawsuit", "bankruptcy", 
        "ban", "scam", "fraud", 
        "اختراق", "حظر", "إفلاس", 
        "قضية"
    }

    def __init__(self):
        self.items = []
        self.last_error = None
    async def _fetch_feed(
        self, session, url
    ):
        try:
            async with session.get(
                url, allow_redirects=False, 
                timeout=6
            ) as r:
                if r.status != 200: 
                    return []
                raw = await r.content.read(
                    512001
                )
                if len(raw) > 512000: 
                    return []
                root = ET.fromstring(raw)
                collected = []
                for item in root.findall(
                    ".//item"
                )[:10]:
                    title = item.findtext(
                        "title", default=""
                    ).strip()[:200]
                    desc = item.findtext(
                        "description", 
                        default=""
                    ).strip()[:400]
                    if title: 
                        collected.append({
                            "title": title, 
                            "summary": desc
                        })
                return collected
        except Exception: 
            return []
    async def refresh(self):
        try:
            async with aiohttp.ClientSession() as s:
                tasks = [
                    self._fetch_feed(s, url) 
                    for url in FEEDS
                ]
                results = await asyncio.gather(
                    *tasks
                )
                combined = []
                for res in results: 
                    combined.extend(res)
                self.items = combined[:30]
                self.last_error = None
        except Exception as e: 
            self.last_error = type(e).__name__
        return self.items
        
    async def is_market_unsafe(self, symbol):
        symbol_base = str(symbol).split("-")[0].lower()
        for item in self.items:
            text = (
                item["title"] + " " + 
                item["summary"]
            ).lower()
            if symbol_base in text:
                if any(
                    kw in text 
                    for kw in 
                    self.CRITICAL_KEYWORDS
                ):
                    return True
        return False
        
    async def get_context(self): 
        return self.items[:15]
