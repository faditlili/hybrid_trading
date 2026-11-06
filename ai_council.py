import asyncio
import json
import logging
import math
import re
from collections import Counter
from urllib.parse import urlparse

import aiohttp
import config


logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

def _config_value(names, default):
    for name in names:
        if hasattr(config, name):
            value = getattr(config, name)
            if value is not None:
                return value
    return default


HF_API_URL = str(
    _config_value(
        ["HF_API_URL", "HF_ROUTER_URL"],
        "https://router.huggingface.co/v1",
    )
).strip().rstrip("/")

HF_API_TOKEN = str(
    _config_value(
        ["HF_API_TOKEN", "HF_TOKEN"],
        "",
    )
).strip()

HF_MODELS = _config_value(
    ["HF_MODELS", "AI_MODELS"],
    [],
)

AI_TIMEOUT_SECONDS = _config_value(
    ["AI_TIMEOUT_SECONDS", "HF_TIMEOUT_SECONDS"],
    30,
)

AI_MAX_CONCURRENCY = _config_value(
    ["AI_MAX_CONCURRENCY", "HF_MAX_CONCURRENCY"],
    3,
)

AI_MIN_MODELS = _config_value(
    ["AI_MIN_MODELS", "HF_MIN_MODELS"],
    2,
)

AI_MIN_AGREEMENT = _config_value(
    ["AI_MIN_AGREEMENT", "HF_MIN_AGREEMENT"],
    0.60,
)

MAX_RESPONSE_BYTES = 512 * 1024
MAX_PROMPT_LENGTH = 18000
MAX_REASON_LENGTH = 1000

VALID_VOTES = {"BUY", "SELL", "HOLD"}


# ============================================================
# VALIDATION HELPERS
# ============================================================

def valid_number(value):
    if isinstance(value, bool):
        return False

    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def normalize_vote(value):
    if not isinstance(value, str):
        return "UNAVAILABLE"

    vote = value.strip().upper()

    if vote in VALID_VOTES:
        return vote

    return "UNAVAILABLE"


def normalize_reason(value):
    if not isinstance(value, str):
        return "No explanation provided."

    value = re.sub(r"\s+", " ", value).strip()

    if not value:
        return "No explanation provided."

    return value[:MAX_REASON_LENGTH]


def _valid_https_url(value):
    try:
        parsed = urlparse(value)

        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
        )
    except Exception:
        return False


def _valid_models(models):
    if not isinstance(models, (list, tuple)):
        return []

    result = []
    seen = set()

    for model in models:
        if not isinstance(model, str):
            continue

        model = model.strip()

        if not model or len(model) > 300:
            continue

        if model in seen:
            continue

        seen.add(model)
        result.append(model)

    return result


def validate_ai_configuration():
    if not _valid_https_url(HF_API_URL):
        return False

    if not HF_API_TOKEN:
        return False

    if not isinstance(HF_API_TOKEN, str):
        return False

    if not valid_number(AI_TIMEOUT_SECONDS):
        return False

    if float(AI_TIMEOUT_SECONDS) <= 0:
        return False

    if not valid_number(AI_MAX_CONCURRENCY):
        return False

    if int(AI_MAX_CONCURRENCY) < 1:
        return False

    if not valid_number(AI_MIN_MODELS):
        return False

    if int(AI_MIN_MODELS) < 1:
        return False

    if not valid_number(AI_MIN_AGREEMENT):
        return False

    if not 0.5 <= float(AI_MIN_AGREEMENT) <= 1.0:
        return False

    return bool(_valid_models(HF_MODELS))


# ============================================================
# SAFE CONTEXT SERIALIZATION
# ============================================================

def _sanitize_context(value, depth=0):

    if depth > 8:
        return "[maximum depth reached]"

    if value is None or isinstance(value, (str, bool, int)):
        return value

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, dict):
        result = {}

        for key, item in list(value.items())[:100]:

            if not isinstance(key, str):
                continue

            if key.lower() in {"data", "candles", "klines"}:
                continue

            result[key[:100]] = _sanitize_context(
                item,
                depth + 1,
            )

        return result

    if isinstance(value, (list, tuple)):
        return [
            _sanitize_context(item, depth + 1)
            for item in value[:100]
        ]

    if hasattr(value, "shape") and hasattr(value, "columns"):
        return {
            "type": "tabular_data",
            "rows": int(value.shape[0]),
            "columns": [
                str(column)[:80]
                for column in list(value.columns)[:50]
            ],
        }

    return str(value)[:500]


# ============================================================
# AI COUNCIL
# ============================================================

class AICouncil:

    def __init__(self):

        self.session = None
        self.available = False

        self.model_status = []

        self.max_concurrency = max(
            1,
            int(AI_MAX_CONCURRENCY)
            if valid_number(AI_MAX_CONCURRENCY)
            else 3,
        )

        self.semaphore = asyncio.Semaphore(
            self.max_concurrency
        )

        self._session_lock = asyncio.Lock()
        self._lifecycle_lock = asyncio.Lock()

        self._closing = False
        self._active_requests = 0

        self._idle_event = asyncio.Event()
        self._idle_event.set()

        self._close_task = None

    # ========================================================
    # RESULT HELPERS
    # ========================================================

    @staticmethod
    def unavailable_result(reason, details=None):

        return {
            "available": False,
            "vote": "UNAVAILABLE",
            "reason": str(reason)[:MAX_REASON_LENGTH],
            "votes": {},
            "available_models": 0,
            "agreement": 0.0,
            "details": details or [],
        }

    @staticmethod
    def empty_result():

        return AICouncil.unavailable_result(
            "AI council has no valid results."
        )

    # ========================================================
    # LIFECYCLE
    # ========================================================

    async def start(self):

        async with self._lifecycle_lock:

            if self.session is not None and not self.session.closed:
                self.available = validate_ai_configuration()
                return self.available

            self._closing = False
            self._close_task = None

            if not validate_ai_configuration():

                self.available = False
                self.model_status = []

                logger.warning(
                    "AI council configuration is incomplete or invalid."
                )

                return False

            timeout = aiohttp.ClientTimeout(
                total=float(AI_TIMEOUT_SECONDS),
                connect=min(
                    10,
                    float(AI_TIMEOUT_SECONDS),
                ),
            )

            connector = aiohttp.TCPConnector(
                limit=self.max_concurrency,
                ttl_dns_cache=300,
            )

            try:

                self.session = aiohttp.ClientSession(
                    timeout=timeout,
                    connector=connector,
                    headers={
                        "Authorization": f"Bearer {HF_API_TOKEN}",
                        "Content-Type": "application/json",
                    },
                )

                self.available = True

                logger.info(
                    "AI council started with %s configured models.",
                    len(_valid_models(HF_MODELS)),
                )

                return True

            except Exception:

                self.session = None
                self.available = False

                logger.exception(
                    "Could not start AI council."
                )

                return False

    async def _finish_close(self):

        try:

            await self._idle_event.wait()

            async with self._session_lock:

                session = self.session
                self.session = None

                if session is not None and not session.closed:
                    await session.close()

        finally:

            self.available = False

    async def close(self):

        async with self._lifecycle_lock:

            if self._close_task is None:

                self._closing = True
                self.available = False

                self._close_task = asyncio.create_task(
                    self._finish_close()
                )

            task = self._close_task

        try:

            await asyncio.shield(task)

        except asyncio.CancelledError:
            raise

        finally:

            if task.done():

                async with self._lifecycle_lock:

                    if self._close_task is task:
                        self._close_task = None
                        self._closing = False

    async def _acquire_session(self):

        async with self._session_lock:

            if self._closing:
                return None

            if self.session is None or self.session.closed:
                return None

            self._active_requests += 1
            self._idle_event.clear()

            return self.session

    async def _release_session(self):

        async with self._session_lock:

            self._active_requests = max(
                0,
                self._active_requests - 1,
            )

            if self._active_requests == 0:
                self._idle_event.set()

    # ========================================================
    # PROMPT
    # ========================================================

    def build_prompt(self, context):

        safe_context = _sanitize_context(context)

        try:

            serialized = json.dumps(
                safe_context,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )

        except (TypeError, ValueError):

            serialized = "{}"

        serialized = serialized[:MAX_PROMPT_LENGTH]

        return f"""
You are an analytical assistant in a simulated trading research system.

Your task is to evaluate the supplied market information.

Rules:
- This system uses paper trading only.
- Do not claim certainty about future prices.
- Do not invent missing market information.
- If evidence is insufficient, choose HOLD.
- Consider technical indicators and market conditions.
- Do not treat this analysis as a guaranteed trading signal.

Return exactly one JSON object:
{{"vote":"BUY","reason":"Short explanation"}}

The vote must be exactly one of:
BUY, SELL, HOLD.

Market context:
{serialized}
""".strip()

    # ========================================================
    # RESPONSE PARSING
    # ========================================================

    @staticmethod
    def extract_content(payload):

        if not isinstance(payload, dict):
            return None

        choices = payload.get("choices")

        if not isinstance(choices, list) or not choices:
            return None

        first = choices[0]

        if not isinstance(first, dict):
            return None

        message = first.get("message")

        if not isinstance(message, dict):
            return None

        content = message.get("content")

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):

            parts = []

            for item in content:

                if not isinstance(item, dict):
                    continue

                text = item.get("text")

                if isinstance(text, str):
                    parts.append(text)

            return "\n".join(parts).strip()

        return None

    @staticmethod
    def extract_vote(content):

        if not isinstance(content, str):
            return "UNAVAILABLE", "Invalid model response."

        content = content.strip()

        try:

            parsed = json.loads(content)

            if isinstance(parsed, dict):

                vote = normalize_vote(
                    parsed.get("vote")
                )

                reason = normalize_reason(
                    parsed.get("reason")
                )

                if vote != "UNAVAILABLE":
                    return vote, reason

        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        cleaned = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            content,
            flags=re.IGNORECASE,
        ).strip()

        try:

            parsed = json.loads(cleaned)

            if isinstance(parsed, dict):

                vote = normalize_vote(
                    parsed.get("vote")
                )

                reason = normalize_reason(
                    parsed.get("reason")
                )

                if vote != "UNAVAILABLE":
                    return vote, reason

        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        return (
            "UNAVAILABLE",
            "Model response did not contain valid JSON.",
        )

    # ========================================================
    # SINGLE MODEL REQUEST
    # ========================================================

    async def ask_model(self, model, context):

        result = {
            "model": str(model),
            "vote": "UNAVAILABLE",
            "reason": "Model request was not completed.",
            "available": False,
        }

        if not self.available or self._closing:
            result["reason"] = "AI council is unavailable."
            return result

        async with self.semaphore:

            session = await self._acquire_session()

            if session is None:
                result["reason"] = "No active HTTP session."
                return result

            try:

                prompt = self.build_prompt(context)

                endpoint = (
                    HF_API_URL.rstrip("/")
                    + "/chat/completions"
                )

                request_data = {
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Return only the requested JSON object."
                            ),
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    "temperature": 0,
                    "max_tokens": 250,
                    "stream": False,
                }

                async with session.post(
                    endpoint,
                    json=request_data,
                ) as response:

                    if response.status != 200:

                        result["reason"] = (
                            f"Model HTTP error: {response.status}"
                        )

                        logger.warning(
                            "AI model request failed: model=%s status=%s",
                            model,
                            response.status,
                        )

                        return result

                    raw = await response.content.read(
                        MAX_RESPONSE_BYTES + 1
                    )

                    if len(raw) > MAX_RESPONSE_BYTES:

                        result["reason"] = (
                            "Model response exceeded size limit."
                        )

                        return result

                    try:

                        payload = json.loads(
                            raw.decode("utf-8")
                        )

                    except (
                        UnicodeDecodeError,
                        json.JSONDecodeError,
                    ):

                        result["reason"] = (
                            "Invalid JSON from model endpoint."
                        )

                        return result

                    content = self.extract_content(payload)

                    vote, reason = self.extract_vote(content)

                    if vote not in VALID_VOTES:

                        result["reason"] = reason
                        return result

                    result.update(
                        {
                            "vote": vote,
                            "reason": reason,
                            "available": True,
                        }
                    )

                    return result

            except asyncio.CancelledError:
                raise

            except asyncio.TimeoutError:

                result["reason"] = "Model request timed out."
                return result

            except aiohttp.ClientError:

                result["reason"] = (
                    "Network error while contacting model."
                )

                logger.warning(
                    "AI network error: model=%s",
                    model,
                )

                return result

            except Exception:

                result["reason"] = (
                    "Unexpected model processing error."
                )

                logger.exception(
                    "AI model processing failed: model=%s",
                    model,
                )

                return result

            finally:

                await self._release_session()

    # ========================================================
    # COUNCIL ANALYSIS
    # ========================================================

    async def analyze(self, context):

        self.model_status = []

        if not self.available:

            return self.unavailable_result(
                "AI council is not available."
            )

        models = _valid_models(HF_MODELS)

        if not models:

            return self.unavailable_result(
                "No valid AI models are configured."
            )

        required_models = int(AI_MIN_MODELS)
        required_agreement = float(AI_MIN_AGREEMENT)

        try:

            results = await asyncio.gather(
                *[
                    self.ask_model(model, context)
                    for model in models
                ],
                return_exceptions=True,
            )

        except asyncio.CancelledError:
            raise

        except Exception:

            logger.exception(
                "AI council analysis failed."
            )

            return self.unavailable_result(
                "AI council analysis failed."
            )

        valid_results = []
        details = []

        for model, item in zip(models, results):

            if isinstance(item, BaseException):

                details.append(
                    {
                        "model": model,
                        "vote": "UNAVAILABLE",
                        "reason": "Model task failed.",
                        "available": False,
                    }
                )

                continue

            if not isinstance(item, dict):
                continue

            vote = normalize_vote(
                item.get("vote")
            )

            available = (
                item.get("available") is True
                and vote in VALID_VOTES
            )

            detail = {
                "model": model,
                "vote": vote if available else "UNAVAILABLE",
                "reason": normalize_reason(
                    item.get("reason")
                ),
                "available": available,
            }

            details.append(detail)

            if available:
                valid_results.append(detail)

        # Always publish the latest model states.
        self.model_status = details

        votes = {
            item["model"]: item["vote"]
            for item in valid_results
        }

        available_count = len(votes)

        if available_count < required_models:

            return {
                "available": False,
                "vote": "UNAVAILABLE",
                "reason": (
                    "Insufficient valid model responses. "
                    f"Required: {required_models}, "
                    f"received: {available_count}."
                ),
                "votes": votes,
                "available_models": available_count,
                "agreement": 0.0,
                "details": details,
            }

        counts = Counter(votes.values())

        winner, winner_count = counts.most_common(1)[0]

        agreement = winner_count / available_count

        # Reject tied results explicitly.
        if list(counts.values()).count(winner_count) > 1:

            return {
                "available": False,
                "vote": "UNAVAILABLE",
                "reason": (
                    "AI council vote is tied. "
                    "No decision will be issued."
                ),
                "votes": votes,
                "available_models": available_count,
                "agreement": round(agreement, 4),
                "details": details,
            }

        if agreement < required_agreement:

            return {
                "available": False,
                "vote": "UNAVAILABLE",
                "reason": (
                    "Model agreement is below the required threshold."
                ),
                "votes": votes,
                "available_models": available_count,
                "agreement": round(agreement, 4),
                "details": details,
            }

        if winner not in VALID_VOTES:

            return self.unavailable_result(
                "The council did not reach a valid decision.",
                details,
            )

        winning_reasons = [
            item["reason"]
            for item in valid_results
            if item["vote"] == winner
        ]

        reason = (
            f"{winner} received {winner_count} of "
            f"{available_count} valid votes. "
            f"Agreement: {agreement:.1%}. "
            + " ".join(winning_reasons[:2])
        )

        logger.info(
            "AI council result: vote=%s agreement=%.2f models=%s",
            winner,
            agreement,
            available_count,
        )

        return {
            "available": True,
            "vote": winner,
            "reason": reason[:MAX_REASON_LENGTH],
            "votes": votes,
            "available_models": available_count,
            "agreement": round(agreement, 4),
            "details": details,
        }

    # ========================================================
    # STATUS
    # ========================================================

    def get_status(self):

        return {
            "available": bool(self.available),
            "models": len(_valid_models(HF_MODELS)),
            "active_requests": self._active_requests,
            "closing": self._closing,
            "model_status": list(self.model_status),
        }
