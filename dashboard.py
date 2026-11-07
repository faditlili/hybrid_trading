
"""Public read-only Gradio dashboard.
No username/password prompt.
Paper simulation only. No real exchange orders.
"""

import json
import logging
import os
from urllib.parse import urlsplit

import gradio as gr
import requests


logger = logging.getLogger("AI_QUANT.dashboard")


# --------------------------------------------------
# Configuration
# --------------------------------------------------

API_PORT = os.getenv("PORT", "7860")

API_URL = os.getenv(
    "API_URL",
    f"http://127.0.0.1:{API_PORT}",
).strip().rstrip("/")

MAX_RESPONSE_BYTES = 2 * 1024 * 1024

ALLOWED_PATHS = frozenset({
    "/dashboard/status",
    "/dashboard/positions",
    "/dashboard/trades",
    "/dashboard/decisions",
})


def get_timeout():
    try:
        value = float(os.getenv("DASHBOARD_HTTP_TIMEOUT", "8"))
        return max(2.0, min(value, 30.0))
    except (TypeError, ValueError):
        return 8.0


HTTP_TIMEOUT = get_timeout()


def validate_api_url(url):
    """Accept only valid HTTP or HTTPS backend URLs."""

    try:
        parsed = urlsplit(url)

        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
        )

    except (TypeError, ValueError):
        return False


API_URL_VALID = validate_api_url(API_URL)


# --------------------------------------------------
# API client
# --------------------------------------------------

def error_response(message, path, status_code=None):
    result = {
        "dashboard_error": message,
        "endpoint": path,
    }

    if status_code is not None:
        result["status_code"] = status_code

    return result


def fetch(path):
    """Fetch one approved read-only endpoint."""

    if path not in ALLOWED_PATHS:
        logger.warning("Dashboard rejected an unknown API path")
        return error_response(
            "Invalid dashboard endpoint.",
            str(path),
        )

    if not API_URL_VALID:
        logger.error("Invalid dashboard API_URL configuration")
        return error_response(
            "Backend URL configuration is invalid.",
            path,
        )

    try:
        with requests.get(
            f"{API_URL}{path}",
            timeout=(3.0, HTTP_TIMEOUT),
            headers={
                "Accept": "application/json",
            },
            stream=True,
            allow_redirects=False,
        ) as response:

            response.raise_for_status()

            content_length = response.headers.get("Content-Length")

            if content_length:
                try:
                    if int(content_length) > MAX_RESPONSE_BYTES:
                        return error_response(
                            "Backend response is too large.",
                            path,
                        )
                except ValueError:
                    return error_response(
                        "Invalid response size.",
                        path,
                    )

            chunks = []
            total_size = 0

            for chunk in response.iter_content(
                chunk_size=16 * 1024
            ):
                if not chunk:
                    continue

                total_size += len(chunk)

                if total_size > MAX_RESPONSE_BYTES:
                    return error_response(
                        "Backend response is too large.",
                        path,
                    )

                chunks.append(chunk)

            raw_data = b"".join(chunks)

            try:
                return json.loads(raw_data)

            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.warning(
                    "Invalid JSON returned by dashboard endpoint: %s",
                    path,
                )

                return error_response(
                    "Backend returned invalid JSON.",
                    path,
                )

    except requests.Timeout:
        logger.warning(
            "Dashboard request timed out: %s",
            path,
        )

        return error_response(
            "Request timed out.",
            path,
        )

    except requests.HTTPError as exc:
        status_code = (
            exc.response.status_code
            if exc.response is not None
            else None
        )

        logger.warning(
            "Dashboard HTTP error: endpoint=%s status=%s",
            path,
            status_code,
        )

        return error_response(
            "Backend returned an HTTP error.",
            path,
            status_code,
        )

    except requests.RequestException:
        logger.warning(
            "Dashboard connection failed: %s",
            path,
        )

        return error_response(
            "Unable to connect to the backend.",
            path,
        )

    except Exception:
        logger.exception(
            "Unexpected dashboard error: %s",
            path,
        )

        return error_response(
            "Unexpected dashboard error.",
            path,
        )


# --------------------------------------------------
# Fetch all dashboard data
# --------------------------------------------------

def fetch_all():
    """Retrieve all dashboard sections."""

    return (
        fetch("/dashboard/status"),
        fetch("/dashboard/positions"),
        fetch("/dashboard/trades"),
        fetch("/dashboard/decisions"),
    )


# --------------------------------------------------
# Dashboard interface
# --------------------------------------------------

def build_dashboard():

    with gr.Blocks(
        title="AI QUANT 4.0",
        theme=gr.themes.Soft(),
    ) as app:

        gr.Markdown(
            """
            # AI QUANT 4.0

            **Advanced market analysis and paper portfolio simulation**

            <span style="color:green; font-weight:bold;">
            PAPER MODE — No real exchange orders.
            </span>

            This dashboard is read-only.

            Dashboard data is visible to anyone who can access this page.
            """
        )

        with gr.Row():
            refresh = gr.Button(
                "Refresh Dashboard",
                variant="primary",
            )

        with gr.Tab("Portfolio"):
            status = gr.JSON(
                label="Portfolio Status",
            )

        with gr.Tab("Positions"):
            positions = gr.JSON(
                label="Open Simulated Positions",
            )

        with gr.Tab("Trades"):
            trades = gr.JSON(
                label="Recent Simulated Trades",
            )

        with gr.Tab("AI Decisions"):
            decisions = gr.JSON(
                label="Recent AI Decisions",
            )

        outputs = [
            status,
            positions,
            trades,
            decisions,
        ]

        refresh.click(
            fn=fetch_all,
            inputs=None,
            outputs=outputs,
        )

        app.load(
            fn=fetch_all,
            inputs=None,
            outputs=outputs,
        )

    return app
