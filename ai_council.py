import aiohttp
import asyncio
from config import HF_TOKEN, HF_API_URL, HF_QWEN_MODEL, HF_DEEPSEEK_MODEL, HF_LLAMA_MODEL


class AICouncil:
    def __init__(self):
        self.session = None

    async def start(self):
        timeout = aiohttp.ClientTimeout(total=35)
        self.session = aiohttp.ClientSession(timeout=timeout)

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

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
                "max_new_tokens": 180,
                "return_full_text": False
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
                        "error": f"HTTP {response.status}: {body[:250]}"
                    }

                data = await response.json()

                if isinstance(data, list) and data:
                    output = data[0].get("generated_text", "")
                elif isinstance(data, dict):
                    output = data.get("generated_text", "")
                else:
                    output = ""

                output = str(output).upper()

                if "BUY" in output:
                    vote = "BUY"
                elif "SELL" in output:
                    vote = "SELL"
                elif "HOLD" in output:
                    vote = "HOLD"
                else:
                    vote = "UNAVAILABLE"

                return {
                    "available": vote != "UNAVAILABLE",
                    "vote": vote,
                    "output": output[:1000],
                    "error": None
                }

        except Exception as exc:
            return {
                "available": False,
                "vote": "UNAVAILABLE",
                "error": str(exc)[:250]
            }

    async def analyze(self, symbol, indicators, market_regime):
        prompt = f"""
You are a cautious market analysis assistant.
This is a paper-trading research simulation only.

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

Return exactly one word:
BUY, SELL, or HOLD.

Use BUY only when the indicators show a clear bullish setup.
Otherwise return HOLD.
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

        if not valid_votes:
            final_vote = "UNAVAILABLE"
        elif valid_votes.count("BUY") >= 2:
            final_vote = "BUY"
        elif valid_votes.count("SELL") >= 2:
            final_vote = "SELL"
        else:
            final_vote = "HOLD"

        return {
            "vote": final_vote,
            "models": votes,
            "valid_models": len(valid_votes)
        }
