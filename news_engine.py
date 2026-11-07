"""Optional RSS headline risk filter; headlines never create trade signals."""
import time
import aiohttp
from defusedxml import ElementTree as ET
from config import NEWS_REFRESH_SECONDS, HTTP_TIMEOUT_SECONDS
FEEDS=("https://www.coindesk.com/arc/outboundfeeds/rss/","https://cointelegraph.com/rss")
CRITICAL=("exploit","security breach","bankruptcy","insolvency","trading halted")
class NewsEngine:
    def __init__(self): self.session=None; self.items=[]; self.updated=0
    async def start(self):
        if self.session is None or self.session.closed: self.session=aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SECONDS))
    async def close(self):
        if self.session and not self.session.closed: await self.session.close()
        self.session=None
    async def refresh(self):
        if time.time()-self.updated<NEWS_REFRESH_SECONDS: return self.items
        await self.start(); gathered=[]
        async def get(url):
            try:
                async with self.session.get(url) as r:
                    if r.status!=200: return []
                    raw=await r.read()
                    if len(raw)>1_000_000: return []
                    root=ET.fromstring(raw)
                    found=[]
                    for item in root.findall('.//item')[:30]:
                        title=item.findtext('title') or ''
                        link=item.findtext('link') or ''
                        found.append({"title":title[:300],"link":link[:500]})
                    return found
            except Exception: return []
        import asyncio
        for batch in await asyncio.gather(*(get(u) for u in FEEDS)):
            gathered.extend(batch)
        self.items=gathered; self.updated=time.time(); return self.items
    async def blocks(self, symbol):
        items=await self.refresh(); key=symbol.split("-")[0].lower()
        return any(key in x["title"].lower() and any(w in x["title"].lower() for w in CRITICAL) for x in items)
