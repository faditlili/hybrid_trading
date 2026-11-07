
"""Public read-only Gradio dashboard.
No username/password prompt.
Paper simulation only.
"""

import os
import logging

import requests
import gradio as gr

logger = logging.getLogger(__name__)

API_PORT = os.getenv("PORT", "7860")

API_URL = os.getenv(
    "API_URL",
    f"http://127.0.0.1:{API_PORT}"
).rstrip("/")

HTTP_TIMEOUT = 8


def fetch(path):
    """Fetch dashboard data from the local FastAPI backend."""

    try:
        response = requests.get(
            f"{API_URL}{path}",
            timeout=HTTP_TIMEOUT
        )

        response.raise_for_status()

        data = response.json()

        return data

    except requests.RequestException as exc:

        logger.warning(
            "Dashboard request failed for %s: %s",
            path,
            exc
        )

        return {
            "dashboard_error": str(exc),
            "endpoint": path
        }

    except ValueError as exc:

        logger.warning(
            "Invalid JSON response from %s",
            path
        )

        return {
            "dashboard_error": str(exc),
            "endpoint": path
        }


def fetch_all():

    return (
        fetch("/dashboard/status"),
        fetch("/dashboard/positions"),
        fetch("/dashboard/trades"),
        fetch("/dashboard/decisions")
    )


def build_dashboard():

    with gr.Blocks(
        title="AI QUANT 4.0",
        theme=gr.themes.Soft()
    ) as app:

        gr.Markdown(
            """
            # AI QUANT 4.0

            **Advanced market analysis and paper portfolio simulation**

            <span style="color:green">
            PAPER MODE — No real exchange orders.
            </span>
            """
        )

        with gr.Row():

            refresh = gr.Button(
                "Refresh Dashboard",
                variant="primary"
            )

        with gr.Tab("Portfolio"):

            status = gr.JSON(
                label="Portfolio Status"
            )

        with gr.Tab("Positions"):

            positions = gr.JSON(
                label="Open Simulated Positions"
            )

        with gr.Tab("Trades"):

            trades = gr.JSON(
                label="Recent Simulated Trades"
            )

        with gr.Tab("AI Decisions"):

            decisions = gr.JSON(
                label="Recent AI Decisions"
            )

        outputs = [
            status,
            positions,
            trades,
            decisions
        ]

        refresh.click(
            fn=fetch_all,
            inputs=None,
            outputs=outputs
        )

        app.load(
            fn=fetch_all,
            inputs=None,
            outputs=outputs
        )

    return app
