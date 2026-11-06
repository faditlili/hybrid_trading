import asyncio
import logging
import re

import aiohttp

from config import (
    HF_TOKEN,
    HF_API_URL,
    HF_TIMEOUT,
    HF_MODELS
)


logger = logging.getLogger(__name__)


class AICouncil:

    def __init__(self):

        self.session = None
        self.available = False
        self.model_status = {}

    async def start(self):

        if not HF_TOKEN:

            logger.warning(
                "Hugging Face token is not configured"
            )

            self.available = False
            return

        timeout = aiohttp.ClientTimeout(
            total=HF_TIMEOUT
        )

        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {HF_TOKEN}",
                "Content-Type": "application/json"
            }
        )

        self.available = True

        logger.info("AI Council started")

    async def close(self):

        if self.session and not self.session.closed:

            await self.session.close()

        self.session = None
        self.available = False

    def extract_vote(self, response):

        if not response:
            return "INVALID"

        text = str(response).strip().upper()

        match = re.search(
            r"\b(BUY|SELL|HOLD)\b",
            text
        )

        if not match:
            return "INVALID"

        return match.group(1)

    async def ask_model(self, model, context):

        if not self.session:

            return {
                "model": model,
                "vote": "UNAVAILABLE",
                "reason": "AI session unavailable"
            }

        prompt = f"""
You are an analytical assistant in a paper-trading
simulation.

Evaluate the supplied market indicators.

Return exactly one word:
BUY
SELL
HOLD

Do not provide financial promises.

Market data:
{context}
"""

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a cautious market-analysis "
                        "assistant. Return one valid vote only."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 30
        }

        try:

            async with self.session.post(
                HF_API_URL,
                json=payload
            ) as response:

                if response.status != 200:

                    error_text = await response.text()

                    logger.warning(
                        "Model %s returned HTTP %s",
                        model,
                        response.status
                    )

                    return {
                        "model": model,
                        "vote": "UNAVAILABLE",
                        "reason": (
                            f"HTTP {response.status}: "
                            f"{error_text[:150]}"
                        )
                    }

                data = await response.json()

                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )

                vote = self.extract_vote(content)

                return {
                    "model": model,
                    "vote": vote,
                    "reason": str(content)[:200]
                }

        except asyncio.TimeoutError:

            return {
                "model": model,
                "vote": "UNAVAILABLE",
                "reason": "Request timeout"
            }

        except (
            aiohttp.ClientError,
            ValueError,
            KeyError,
            IndexError,
            TypeError
        ) as error:

            logger.warning(
                "AI model request failed: %s",
                error
            )

            return {
                "model": model,
                "vote": "UNAVAILABLE",
                "reason": str(error)[:200]
            }

    async def analyze(self, context):

        if not self.session:

            return {
                "vote": "UNAVAILABLE",
                "reason": "AI session not initialized",
                "votes": {},
                "available_models": 0
            }

        if not isinstance(context, dict):

            return {
                "vote": "UNAVAILABLE",
                "reason": "Invalid analysis context",
                "votes": {},
                "available_models": 0
            }

        tasks = [
            self.ask_model(model, context)
            for model in HF_MODELS
        ]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=True
        )

        votes = {
            "BUY": 0,
            "SELL": 0,
            "HOLD": 0
        }

        details = []
        available_models = 0

        for result in results:

            if isinstance(result, Exception):

                details.append({
                    "vote": "UNAVAILABLE",
                    "reason": str(result)[:150]
                })

                continue

            details.append(result)

            vote = result.get("vote")

            if vote in votes:

                votes[vote] += 1
                available_models += 1

        self.model_status = details

        # Require at least two valid model responses
        if available_models < 2:

            return {
                "vote": "UNAVAILABLE",
                "reason": (
                    "Not enough valid AI model responses"
                ),
                "votes": votes,
                "available_models": available_models,
                "details": details
            }

        # Require a majority of all configured models
        if votes["BUY"] >= 2:

            final_vote = "BUY"

        elif votes["SELL"] >= 2:

            final_vote = "SELL"

        elif votes["HOLD"] >= 2:

            final_vote = "HOLD"

        else:

            final_vote = "UNAVAILABLE"

        return {
            "vote": final_vote,
            "reason": "AI council voting completed",
            "votes": votes,
            "available_models": available_models,
            "details": details
        }
