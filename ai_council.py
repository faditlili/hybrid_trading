import asyncio
import aiohttp
import logging
import re

from config import (
    HF_TOKEN,
    HF_CHAT_COMPLETIONS_URL,
    HF_AI_TIMEOUT,
    HF_QWEN_MODEL,
    HF_DEEPSEEK_MODEL,
    HF_LLAMA_MODEL
)

logger = logging.getLogger(__name__)


class AICouncil:

    def __init__(self):
        self.session = None

        self.models = [
            HF_QWEN_MODEL,
            HF_DEEPSEEK_MODEL,
            HF_LLAMA_MODEL
        ]

    async def start(self):

        if not HF_TOKEN:
            logger.warning(
                "Hugging Face token is not configured"
            )
            return

        if self.session and not self.session.closed:
            return

        timeout = aiohttp.ClientTimeout(
            total=HF_AI_TIMEOUT
        )

        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {HF_TOKEN}",
                "Content-Type": "application/json"
            }
        )

    async def close(self):

        if self.session and not self.session.closed:
            await self.session.close()

    def extract_vote(self, response):

        if not response:
            return "UNAVAILABLE"

        text = str(response).upper()

        match = re.search(
            r"\b(BUY|SELL|HOLD)\b",
            text
        )

        if not match:
            return "UNAVAILABLE"

        return match.group(1)

    async def ask_model(self, model, market_data):

        if not self.session or self.session.closed:
            return "UNAVAILABLE"

        prompt = (
            "You are an educational market-analysis assistant "
            "for a paper-trading simulator. "
            "Analyze the supplied technical indicators only. "
            "Do not promise returns. "
            "Do not give personalized investment advice. "
            "Return exactly one label: BUY, SELL, or HOLD.\n\n"
            f"Market data:\n{market_data}"
        )

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You analyze market indicators cautiously. "
                        "Your output must be exactly BUY, SELL, or HOLD."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 20
        }

        try:

            async with self.session.post(
                HF_CHAT_COMPLETIONS_URL,
                json=payload
            ) as response:

                if response.status != 200:

                    body = await response.text()

                    logger.warning(
                        "AI model %s returned HTTP %s: %s",
                        model,
                        response.status,
                        body[:200]
                    )

                    return "UNAVAILABLE"

                data = await response.json()

                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )

                return self.extract_vote(content)

        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            KeyError,
            IndexError,
            ValueError
        ) as exc:

            logger.warning(
                "AI model request failed (%s): %s",
                model,
                str(exc)[:200]
            )

            return "UNAVAILABLE"

    async def analyze(self, market_data):

        if not self.session or self.session.closed:
            return {
                "vote": "UNAVAILABLE",
                "votes": {},
                "available_models": 0
            }

        results = await asyncio.gather(
            *[
                self.ask_model(model, market_data)
                for model in self.models
            ],
            return_exceptions=True
        )

        votes = {}

        for model, result in zip(self.models, results):

            if isinstance(result, Exception):
                votes[model] = "UNAVAILABLE"
            else:
                votes[model] = result

        valid_votes = [
            vote
            for vote in votes.values()
            if vote in ("BUY", "SELL", "HOLD")
        ]

        buy_count = valid_votes.count("BUY")
        sell_count = valid_votes.count("SELL")

        if buy_count >= 2:
            final_vote = "BUY"

        elif sell_count >= 2:
            final_vote = "SELL"

        elif len(valid_votes) >= 2:
            final_vote = "HOLD"

        else:
            final_vote = "UNAVAILABLE"

        return {
            "vote": final_vote,
            "votes": votes,
            "available_models": len(valid_votes)
        }
