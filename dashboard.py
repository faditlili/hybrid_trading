import math
import logging

import gradio as gr


logger = logging.getLogger(__name__)


# ============================================================
# STYLE
# ============================================================

CSS = """
.gradio-container {
    max-width: 1100px !important;
    margin: auto !important;
    background: #080d18 !important;
    color: #e5f3ff !important;
}

body {
    background: #080d18 !important;
}

#main-title {
    text-align: center;
    color: #00e5ff;
    font-size: 30px;
    font-weight: 800;
}

#subtitle {
    text-align: center;
    color: #8195b5;
    font-size: 13px;
}

.metric-card {
    background: #101a2c;
    border: 1px solid #1d3553;
    border-radius: 14px;
    padding: 14px;
}

.section-title {
    color: #00e5ff;
    font-weight: 700;
    font-size: 18px;
}

.status-text {
    color: #00e5ff;
    font-weight: 700;
}

button.primary {
    background: #00bcd4 !important;
    color: #06111d !important;
    border: none !important;
}

button {
    border-radius: 10px !important;
}

footer {
    display: none !important;
}

@media (max-width: 650px) {
    #main-title {
        font-size: 23px;
    }

    .metric-card {
        padding: 9px;
    }
}
"""


# ============================================================
# SAFE HELPERS
# ============================================================

def safe_float(value, default=0.0):

    if isinstance(value, bool):
        return float(default)

    try:

        result = float(value)

        if math.isfinite(result):
            return result

    except (TypeError, ValueError, OverflowError):
        pass

    return float(default)


def safe_text(value, limit=500):

    if value is None:
        return ""

    try:
        return str(value)[:limit]

    except Exception:
        return ""


def safe_call(function, default):

    try:

        result = function()

        return result if result is not None else default

    except Exception:

        logger.exception(
            "Dashboard data retrieval failed"
        )

        return default


def safe_rows(value):

    if not isinstance(value, list):
        return []

    return [
        item
        for item in value
        if isinstance(item, dict)
    ]


def money(value):

    return f"{safe_float(value):,.2f} USDT"


def get_controller_components(controller):

    if controller is None:
        raise RuntimeError(
            "Dashboard controller is missing"
        )

    engine = getattr(
        controller,
        "engine",
        None
    )

    trader = getattr(
        controller,
        "trader",
        None
    )

    if engine is None:
        raise RuntimeError(
            "Trading engine is missing"
        )

    if trader is None:
        raise RuntimeError(
            "Paper trader is missing"
        )

    db = getattr(
        controller,
        "db",
        None
    )

    if db is None:
        db = getattr(
            engine,
            "db",
            None
        )

    return engine, trader, db


# ============================================================
# DASHBOARD DATA
# ============================================================

def get_dashboard(controller):

    try:

        engine, trader, db = get_controller_components(
            controller
        )

    except Exception:

        logger.exception(
            "Dashboard component initialization failed"
        )

        return (
            money(0),
            money(0),
            money(0),
            money(0),
            money(0),
            0,
            "0.00%",
            "ERROR",
            "UNKNOWN",
            "Unavailable",
            "Dashboard components unavailable",
            0,
            0,
            0,
            0,
            [],
            [],
            [],
            [],
        )

    # --------------------------------------------------------
    # ACCOUNT SUMMARY
    # --------------------------------------------------------

    summary = safe_call(
        trader.get_summary,
        None,
    )

    summary_valid = isinstance(summary, dict)

    if not summary_valid:
        summary = {}

    positions_data = summary.get(
        "positions",
        []
    )

    if not isinstance(positions_data, list):
        positions_data = []

    positions_data = [
        position
        for position in positions_data
        if isinstance(position, dict)
    ]

    # --------------------------------------------------------
    # DATABASE DATA
    # --------------------------------------------------------

    database_error = False

    if db is not None:

        decisions = safe_call(
            lambda: db.get_recent_decisions(15),
            None,
        )

        trades = safe_call(
            lambda: db.get_recent_trades(15),
            None,
        )

        events = safe_call(
            lambda: db.get_recent_events(20),
            None,
        )

        if (
            decisions is None
            or trades is None
            or events is None
        ):
            database_error = True

    else:

        logger.error(
            "Dashboard database reference is unavailable"
        )

        decisions = []
        trades = []
        events = []

        database_error = True

    decisions = safe_rows(decisions)
    trades = safe_rows(trades)
    events = safe_rows(events)

    # --------------------------------------------------------
    # ENGINE STATUS
    # --------------------------------------------------------

    stats = getattr(
        engine,
        "scan_stats",
        {},
    )

    if not isinstance(stats, dict):
        stats = {}

    status = (
        "RUNNING"
        if getattr(engine, "running", False)
        else "STOPPED"
    )

    regime = safe_text(
        getattr(
            engine,
            "market_regime",
            "UNKNOWN"
        ),
        50,
    )

    last_scan = safe_text(
        getattr(
            engine,
            "last_scan",
            None
        ) or "Not scanned yet",
        100,
    )

    error = safe_text(
        getattr(
            engine,
            "last_error",
            None
        ) or "No system errors",
        500,
    )

    if not summary_valid:

        error = (
            "Account summary unavailable. "
            "Check paper trader and database logs."
        )

    elif database_error:

        error = (
            "Database data is partially unavailable. "
            + error
        )

    # --------------------------------------------------------
    # POSITIONS
    # --------------------------------------------------------

    position_rows = []

    for position in positions_data:

        symbol = safe_text(
            position.get("symbol", ""),
            30,
        )

        position_rows.append([

            symbol,

            round(
                safe_float(
                    position.get("entry_price")
                ),
                8,
            ),

            round(
                safe_float(
                    position.get("current_price")
                ),
                8,
            ),

            round(
                safe_float(
                    position.get("quantity")
                ),
                8,
            ),

            round(
                safe_float(
                    position.get("unrealized_pnl")
                ),
                4,
            ),

            round(
                safe_float(
                    position.get("stop_loss")
                ),
                8,
            ),

            round(
                safe_float(
                    position.get("take_profit")
                ),
                8,
            ),

        ])

    # --------------------------------------------------------
    # DECISIONS
    # --------------------------------------------------------

    decision_rows = []

    for decision in decisions:

        reasons = decision.get(
            "reasons",
            ""
        )

        if isinstance(reasons, (list, tuple)):

            reasons = " | ".join(
                safe_text(item, 200)
                for item in reasons
            )

        else:

            reasons = safe_text(
                reasons,
                350,
            )

        decision_rows.append([

            safe_text(
                decision.get("symbol", ""),
                30,
            ),

            safe_text(
                decision.get("action", ""),
                30,
            ),

            safe_float(
                decision.get("score")
            ),

            safe_text(
                decision.get("ai_vote", ""),
                30,
            ),

            reasons[:350],

            safe_text(
                decision.get("timestamp", ""),
                100,
            ),

        ])

    # --------------------------------------------------------
    # CLOSED TRADES
    # --------------------------------------------------------

    trade_rows = []

    for trade in trades:

        trade_rows.append([

            safe_text(
                trade.get("symbol", ""),
                30,
            ),

            round(
                safe_float(
                    trade.get("entry_price")
                ),
                8,
            ),

            round(
                safe_float(
                    trade.get("exit_price")
                ),
                8,
            ),

            round(
                safe_float(
                    trade.get("net_pnl")
                ),
                4,
            ),

            safe_text(
                trade.get("reason", ""),
                100,
            ),

            safe_text(
                trade.get("timestamp", ""),
                100,
            ),

        ])

    # --------------------------------------------------------
    # SYSTEM EVENTS
    # --------------------------------------------------------

    event_rows = []

    for event in events:

        event_rows.append([

            safe_text(
                event.get("level", ""),
                30,
            ),

            safe_text(
                event.get("message", ""),
                500,
            ),

            safe_text(
                event.get("timestamp", ""),
                100,
            ),

        ])

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    return (

        money(summary.get("balance")),

        money(summary.get("equity")),

        money(summary.get("realized_pnl")),

        money(summary.get("unrealized_pnl")),

        money(summary.get("reserved")),

        len(position_rows),

        f"{safe_float(summary.get('win_rate')):.2f}%",

        status,

        regime,

        last_scan,

        error,

        int(safe_float(stats.get("scanned"))),

        int(safe_float(stats.get("approved"))),

        int(safe_float(stats.get("rejected"))),

        int(safe_float(stats.get("errors"))),

        position_rows,

        decision_rows,

        trade_rows,

        event_rows,

    )


# ============================================================
# MANUAL SCAN
# ============================================================

async def force_scan(controller):

    try:

        engine, trader, db = get_controller_components(
            controller
        )

    except Exception:

        logger.exception(
            "Manual scan initialization failed"
        )

        return (
            "Dashboard components unavailable.",
            *get_dashboard(controller),
        )

    if not getattr(engine, "running", False):

        return (
            "Engine is not running.",
            *get_dashboard(controller),
        )

    try:

        result = await engine.scan_once()

        if not isinstance(result, dict):

            message = "Invalid scan response."

        else:

            status = result.get(
                "status",
                "UNKNOWN",
            )

            messages = {
                "COMPLETED": "Market scan completed successfully.",
                "BUSY": "A scan is already running.",
                "TIMEOUT": "Market scan exceeded its time limit.",
                "ERROR": "Market scan failed.",
                "STOPPED": "Engine stopped during the scan.",
                "NOT_RUNNING": "Engine is not running.",
            }

            message = messages.get(
                status,
                f"Scan status: {safe_text(status, 50)}",
            )

            if status == "ERROR":

                detail = result.get("message")

                if detail:

                    message += " " + safe_text(
                        detail,
                        250
                    )

    except asyncio.CancelledError:
        raise

    except Exception as exc:

        logger.exception(
            "Manual dashboard scan failed"
        )

        message = (
            f"Scan failed: {type(exc).__name__}: "
            f"{safe_text(exc, 250)}"
        )

    return (
        message,
        *get_dashboard(controller),
    )


# ============================================================
# DASHBOARD BUILDER
# ============================================================

def build_dashboard(controller):

    get_controller_components(controller)

    with gr.Blocks(
        css=CSS,
        title="AI QUANT",
    ) as demo:

        gr.Markdown(
            "# AI QUANT",
            elem_id="main-title",
        )

        gr.Markdown(
            "AUTONOMOUS MARKET ANALYSIS | PAPER TRADING",
            elem_id="subtitle",
        )

        gr.Markdown(
            "SIMULATION MODE ONLY — NO REAL ORDERS",
            elem_classes=["status-text"],
        )

        # ----------------------------------------------------
        # ACCOUNT
        # ----------------------------------------------------

        with gr.Row():

            balance = gr.Textbox(
                label="Available Balance",
                interactive=False,
            )

            equity = gr.Textbox(
                label="Total Equity",
                interactive=False,
            )

            reserved = gr.Textbox(
                label="Reserved Capital",
                interactive=False,
            )

        with gr.Row():

            realized = gr.Textbox(
                label="Realized PnL",
                interactive=False,
            )

            unrealized = gr.Textbox(
                label="Unrealized PnL",
                interactive=False,
            )

            win_rate = gr.Textbox(
                label="Win Rate",
                interactive=False,
            )

        # ----------------------------------------------------
        # ENGINE STATUS
        # ----------------------------------------------------

        with gr.Row():

            open_count = gr.Number(
                label="Open Positions",
                interactive=False,
            )

            status = gr.Textbox(
                label="Engine Status",
                interactive=False,
            )

            regime = gr.Textbox(
                label="BTC Market Regime",
                interactive=False,
            )

        last_scan = gr.Textbox(
            label="Last Scan",
            interactive=False,
        )

        with gr.Row():

            scanned = gr.Number(
                label="Scanned",
                interactive=False,
            )

            approved = gr.Number(
                label="Approved",
                interactive=False,
            )

            rejected = gr.Number(
                label="Rejected",
                interactive=False,
            )

            errors = gr.Number(
                label="Errors",
                interactive=False,
            )

        system_error = gr.Textbox(
            label="System Diagnostics",
            interactive=False,
        )

        # ----------------------------------------------------
        # MARKET CONTROL
        # ----------------------------------------------------

        gr.Markdown(
            "## MARKET CONTROL",
            elem_classes=["section-title"],
        )

        scan_button = gr.Button(
            "SCAN MARKET NOW",
            variant="primary",
        )

        scan_message = gr.Textbox(
            label="Scan Result",
            interactive=False,
        )

        # ----------------------------------------------------
        # OPEN POSITIONS
        # ----------------------------------------------------

        gr.Markdown(
            "## OPEN PAPER POSITIONS",
            elem_classes=["section-title"],
        )

        positions = gr.Dataframe(
            headers=[
                "Symbol",
                "Entry",
                "Current",
                "Quantity",
                "Unrealized PnL",
                "Stop Loss",
                "Take Profit",
            ],
            datatype=[
                "str",
                "number",
                "number",
                "number",
                "number",
                "number",
                "number",
            ],
            interactive=False,
        )

        # ----------------------------------------------------
        # AI DECISIONS
        # ----------------------------------------------------

        gr.Markdown(
            "## AI DECISION HISTORY",
            elem_classes=["section-title"],
        )

        decisions = gr.Dataframe(
            headers=[
                "Symbol",
                "Action",
                "Score",
                "AI Vote",
                "Reasons",
                "Timestamp",
            ],
            datatype=[
                "str",
                "str",
                "number",
                "str",
                "str",
                "str",
            ],
            interactive=False,
        )

        # ----------------------------------------------------
        # CLOSED TRADES
        # ----------------------------------------------------

        gr.Markdown(
            "## CLOSED PAPER TRADES",
            elem_classes=["section-title"],
        )

        trades = gr.Dataframe(
            headers=[
                "Symbol",
                "Entry",
                "Exit",
                "Net PnL",
                "Reason",
                "Timestamp",
            ],
            datatype=[
                "str",
                "number",
                "number",
                "number",
                "str",
                "str",
            ],
            interactive=False,
        )

        # ----------------------------------------------------
        # EVENTS
        # ----------------------------------------------------

        gr.Markdown(
            "## SYSTEM EVENTS",
            elem_classes=["section-title"],
        )

        events = gr.Dataframe(
            headers=[
                "Level",
                "Message",
                "Timestamp",
            ],
            datatype=[
                "str",
                "str",
                "str",
            ],
            interactive=False,
        )

        refresh_button = gr.Button(
            "REFRESH DASHBOARD",
        )

        # ----------------------------------------------------
        # OUTPUTS
        # ----------------------------------------------------

        outputs = [

            balance,
            equity,
            realized,
            unrealized,
            reserved,

            open_count,
            win_rate,

            status,
            regime,
            last_scan,
            system_error,

            scanned,
            approved,
            rejected,
            errors,

            positions,
            decisions,
            trades,
            events,

        ]

        # ----------------------------------------------------
        # CALLBACKS
        # ----------------------------------------------------

        async def run_manual_scan():

            return await force_scan(controller)

        def refresh_dashboard():

            return get_dashboard(controller)

        refresh_button.click(
            fn=refresh_dashboard,
            inputs=None,
            outputs=outputs,
        )

        scan_button.click(
            fn=run_manual_scan,
            inputs=None,
            outputs=[
                scan_message,
                *outputs,
            ],
        )

        # ----------------------------------------------------
        # AUTOMATIC REFRESH
        # ----------------------------------------------------

        timer = gr.Timer(
            value=15,
        )

        timer.tick(
            fn=refresh_dashboard,
            inputs=None,
            outputs=outputs,
        )

        # ----------------------------------------------------
        # INITIAL LOAD
        # ----------------------------------------------------

        demo.load(
            fn=refresh_dashboard,
            inputs=None,
            outputs=outputs,
        )

    return demo


# ============================================================
# PUBLIC API
# ============================================================

def create_dashboard(controller):

    return build_dashboard(controller)
