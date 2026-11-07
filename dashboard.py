
"""Public read-only Gradio dashboard.
No username/password prompt.
Paper simulation only. No real exchange orders.
"""

import logging
import os

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
).rstrip("/")

try:
    HTTP_TIMEOUT = max(
        2,
        int(os.getenv("DASHBOARD_HTTP_TIMEOUT", "8"))
    )
except (TypeError, ValueError):
    HTTP_TIMEOUT = 8


# --------------------------------------------------
# API client
# --------------------------------------------------

def fetch(path):
    """Fetch read-only data from the local FastAPI backend."""

    if not path.startswith("/"):
        raise ValueError("API path must start with '/'")

    try:
        response = requests.get(
            f"{API_URL}{path}",
            timeout=HTTP_TIMEOUT,
            headers={"Accept": "application/json"},
        )

        response.raise_for_status()

        return response.json()

    except requests.Timeout:
        logger.warning("Dashboard request timed out: %s", path)

        return {
            "dashboard_error": "Request timed out.",
            "endpoint": path,
        }

    except requests.HTTPError as exc:
        status_code = (
            exc.response.status_code
            if exc.response is not None
            else None
        )

        logger.warning(
            "Dashboard HTTP error for %s: status=%s",
            path,
            status_code,
        )

        return {
            "dashboard_error": "Backend returned an HTTP error.",
            "status_code": status_code,
            "endpoint": path,
        }

    except requests.RequestException:
        logger.exception(
            "Dashboard connection failed for %s",
            path,
        )

        return {
            "dashboard_error": "Unable to connect to the backend.",
            "endpoint": path,
        }

    except ValueError:
        logger.exception(
            "Invalid JSON response from %s",
            path,
        )

        return {
            "dashboard_error": "Backend returned invalid JSON.",
            "endpoint": path,
        }


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
