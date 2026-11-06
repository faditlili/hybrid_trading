import aiohttp
import asyncio
import re

from config import (
    HF_TOKEN,
    HF_API_URL,
    HF_QWEN_MODEL,
    HF_DEEPSEEK_MODEL,
    HF_LLAMA_MODEL
)


class AICouncil:

    def __init__(self):
        self.session = None

    async def start(self):
        timeout = aiohttp.ClientTimeout(total=35)

        self.session = aiohttp.ClientSession(
            timeout=timeout
        )

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    def extract_vote(self, output):

        if not output:
            return "UNAVAILABLE"

        text = str(output).strip().upper()

        text = re.sub(
            r"<[^>]+>",
            " ",
            text
        )

        text = text.strip(" \n\r\t.:,!?*`\"'")

        match = re.fullmatch(
            r"(BUY|SELL|HOLD)",
            text
        )

        if match:
            return match.group(1)

        match = re.search(
            r"(?:FINAL ANSWER|DECISION|VOTE)\s*[:=]\s*(BUY|SELL|HOLD)\b",
            text
        )

        if match:
            return match.group(1)

        return "UNAVAILABLE"

    async def ask_model(self, model, prompt):

        if not HF_TOKEN:
            return {
                "available": False,
                "vote": "UNAVAILABLE",
                "error": "HF_TOKEN is missing"
            }

        url = f"{HF_API_URL}/{model}"

        headers = {
            "Authorization": f"Bearer {HF_TOKEN}",
            "Content-Type": "application/json"
        }

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 80,
                "return_full_text": False,
                "temperature": 0.1
            }
        }

        try:

            async with self.session.post(
                url,
                headers=headers,
                json=payload
            ) as response:

                if response.status != 200:

                    body = await response.text()

                    return {
                        "available": False,
                        "vote": "UNAVAILABLE",
                        "error": (
                            f"HTTP {response.status}: "
                            f"{body[:250]}"
                        )
                    }

                data = await response.json()

                if isinstance(data, list) and data:

                    output = data[0].get(
                        "generated_text",
                        ""
                    )

                elif isinstance(data, dict):

                    output = data.get(
                        "generated_text",
                        ""
                    )

                else:
                    output = ""

                vote = self.extract_vote(output)

                return {
                    "available": vote != "UNAVAILABLE",
                    "vote": vote,
                    "output": str(output)[:500],
                    "error": None
                }

        except Exception as exc:

            return {
                "available": False,
                "vote": "UNAVAILABLE",
                "error": str(exc)[:250]
            }

    async def analyze(
        self,
        symbol,
        indicators,
        market_regime
    ):

        prompt = f"""
You are a cautious market research assistant.

This is a paper-trading simulation.
Do not predict guaranteed profits.

Analyze these indicators:

Symbol: {symbol}
Market regime: {market_regime}
Price: {indicators['price']}
EMA9: {indicators['ema9']}
EMA21: {indicators['ema21']}
EMA50: {indicators['ema50']}
RSI: {indicators['rsi']}
MACD: {indicators['macd']}
MACD signal: {indicators['macd_signal']}
ATR: {indicators['atr']}

Choose exactly one label.

BUY
SELL
HOLD

Do not explain.
Return only the label.
"""

        models = [
            HF_QWEN_MODEL,
            HF_DEEPSEEK_MODEL,
            HF_LLAMA_MODEL
        ]

        results = await asyncio.gather(
            *[
                self.ask_model(model, prompt)
                for model in models
            ],
            return_exceptions=True
        )

        votes = []

        for result in results:

            if isinstance(result, Exception):

                votes.append({
                    "available": False,
                    "vote": "UNAVAILABLE",
                    "error": str(result)[:250]
                })

            else:
                votes.append(result)

        valid_votes = [
            item["vote"]
            for item in votes
            if item["available"]
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
            "models": votes,
            "valid_models": len(valid_votes),
            "buy_votes": buy_count,
            "sell_votes": sell_count
        }
