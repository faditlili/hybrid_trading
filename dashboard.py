
    font-weight: 900 !important;
    margin-bottom: 2px !important;
}

#subtitle {
    color: #8495b5 !important;
    text-align: center;
    font-size: 12px !important;
    letter-spacing: 1px;
}

.section-title {
    color: #00d9f5 !important;
    font-size: 17px !important;
    font-weight: 800 !important;
}

.status-card {
    background: #101a2c;
    border: 1px solid #203650;
    border-radius: 14px;
    padding: 13px;
    min-height: 70px;
}

.metric-label {
    color: #91a3bf;
    font-size: 12px;
    margin-bottom: 7px;
}

.metric-value {
    color: #f1f7ff;
    font-size: 22px;
    font-weight: 800;
    overflow-wrap: anywhere;
}

.metric-unit {
    color: #8295b3;
    font-size: 11px;
}

.market-good {
    color: #30d99b;
    font-weight: 800;
}

.market-bad {
    color: #ff647c;
    font-weight: 800;
}

.market-warning {
    color: #ffc857;
    font-weight: 800;
}

button.primary {
    background: #00bcd4 !important;
    color: #06111d !important;
    border: none !important;
    font-weight: 800 !important;
}

button {
    border-radius: 12px !important;
    min-height: 44px !important;
}

.tabs {
    border: 1px solid #1c304b !important;
    border-radius: 14px !important;
    background: #0d1727 !important;
    padding: 8px !important;
}

.tab-nav button {
    border-radius: 10px !important;
    font-size: 13px !important;
}

input,
textarea,
.gr-box,
.gr-panel,
table {
    border-radius: 10px !important;
}

.gr-form,
.gr-panel {
    background: #101a2c !important;
    border-color: #203650 !important;
}

footer {
    display: none !important;
}

@media (max-width: 700px) {
    .gradio-container {
        padding: 7px !important;
    }

    #main-title {
        font-size: 24px !important;
    }

    #subtitle {
        font-size: 10px !important;
    }

    .metric-value {
        font-size: 18px;
    }

    .metric-label {
        font-size: 11px;
    }

    .tabs {
        padding: 4px !important;
    }

    .tab-nav button {
        font-size: 11px !important;
        padding: 8px 5px !important;
    }

    button {
        min-height: 46px !important;
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
        logger.exception("Dashboard data retrieval failed")
        return default


def safe_rows(value):

    if not isinstance(value, list):
        return []

    return [
        item for item in value
        if isinstance(item, dict)
    ]


def money(value):

    return f"{safe_float(value):,.2f} USDT"


def get_controller_components(controller):

    if controller is None:
        raise RuntimeError("Dashboard controller is missing")

    engine = getattr(controller, "engine", None)
    trader = getattr(controller, "trader", None)

    if engine is None:
        raise RuntimeError("Trading engine is missing")

    if trader is None:
        raise RuntimeError("Paper trader is missing")

    db = getattr(controller, "db", None)

    if db is None:
        db = getattr(engine, "db", None)

    return engine, trader, db


def get_market_data_component(controller, engine):

    market_data = getattr(
        controller,
        "market_data",
        None,
    )

    if market_data is None:
        market_data = getattr(
            engine,
            "market_data",
            None,
        )

    if market_data is None:
        market_data = getattr(
            engine,
            "market",
            None,
        )

    return market_data


def get_market_status(controller, engine):

    market_data = get_market_data_component(
        controller,
        engine,
    )

    if market_data is None:
        return (
            "NOT CONNECTED",
            "Market data component unavailable",
            "No successful request recorded",
        )

    status_function = getattr(
        market_data,
        "get_status",
        None,
    )

    if not callable(status_function):
        return (
            "UNKNOWN",
            "Market data status method unavailable",
            "Unknown",
        )

    data = safe_call(status_function, {})

    if not isinstance(data, dict):
        return (
            "UNKNOWN",
            "Invalid market data status",
            "Unknown",
        )

    errors = data.get("last_errors", {})

    if not isinstance(errors, dict):
        errors = {}

    error_messages = list(errors.values())

    error_text = (
        safe_text(error_messages[-1], 350)
        if error_messages
        else "No current market data errors"
    )

    last_success = data.get("last_success", {})

    if isinstance(last_success, dict) and last_success:
        success_text = safe_text(
            list(last_success.values())[-1],
            100,
        )
    else:
        success_text = "No successful request recorded"

    if "451" in error_text:
        market_status = "RESTRICTED - HTTP 451"

    elif "429" in error_text or "418" in error_text:
        market_status = "RATE LIMITED"

    elif not data.get("running", False):
        market_status = "STOPPED"

    elif error_messages:
        market_status = "ERROR"

    else:
        market_status = "RUNNING"

    return (
        market_status,
        error_text,
        success_text,
    )


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
            money(0), money(0), money(0),
            money(0), money(0), 0, "0.00%",
            "ERROR", "UNKNOWN", "Unavailable",
            "Dashboard components unavailable",
            "UNKNOWN", "Unavailable", "Unavailable",
            0, 0, 0, 0,
            [], [], [], [],
        )

    # --------------------------------------------------------
    # ACCOUNT
    # --------------------------------------------------------

    summary = safe_call(
        trader.get_summary,
        None,
    )

    summary_valid = isinstance(summary, dict)

    if not summary_valid:
        summary = {}

    positions_data = summary.get("positions", [])

    if not isinstance(positions_data, list):
        positions_data = []

    positions_data = [
        item for item in positions_data
        if isinstance(item, dict)
    ]

    # --------------------------------------------------------
    # DATABASE
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
        decisions = []
        trades = []
        events = []
        database_error = True

    decisions = safe_rows(decisions)
    trades = safe_rows(trades)
    events = safe_rows(events)

    # --------------------------------------------------------
    # ENGINE
    # --------------------------------------------------------

    stats = getattr(engine, "scan_stats", {})

    if not isinstance(stats, dict):
        stats = {}

    engine_status = (
        "RUNNING"
        if getattr(engine, "running", False)
        else "STOPPED"
    )

    regime = safe_text(
        getattr(engine, "market_regime", "UNKNOWN"),
        50,
    )

    last_scan = safe_text(
        getattr(engine, "last_scan", None)
        or "Not scanned yet",
        100,
    )

    error = safe_text(
        getattr(engine, "last_error", None)
        or "No system errors",
        500,
    )

    market_status, market_error, market_success = (
        get_market_status(controller, engine)
    )

    if not summary_valid:
        error = "Account summary unavailable."

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

        position_rows.append([

            safe_text(position.get("symbol", ""), 30),

            round(safe_float(position.get("entry_price")), 8),

            round(safe_float(position.get("current_price")), 8),

            round(safe_float(position.get("quantity")), 8),

            round(safe_float(position.get("unrealized_pnl")), 4),

            round(safe_float(position.get("stop_loss")), 8),

            round(safe_float(position.get("take_profit")), 8),

        ])

    # --------------------------------------------------------
    # DECISIONS
    # --------------------------------------------------------

    decision_rows = []

    for decision in decisions:

        reasons = decision.get("reasons", "")

        if isinstance(reasons, (list, tuple)):
            reasons = " | ".join(
                safe_text(item, 200)
                for item in reasons
            )
        else:
            reasons = safe_text(reasons, 350)

        decision_rows.append([

            safe_text(decision.get("symbol", ""), 30),

            safe_text(decision.get("action", ""), 30),

            safe_float(decision.get("score")),

            safe_text(decision.get("ai_vote", ""), 30),

            reasons[:350],

            safe_text(decision.get("timestamp", ""), 100),

        ])

    # --------------------------------------------------------
    # CLOSED TRADES
    # --------------------------------------------------------

    trade_rows = []

    for trade in trades:

        trade_rows.append([

            safe_text(trade.get("symbol", ""), 30),

            round(safe_float(trade.get("entry_price")), 8),

            round(safe_float(trade.get("exit_price")), 8),

            round(safe_float(trade.get("net_pnl")), 4),

            safe_text(trade.get("reason", ""), 100),

            safe_text(trade.get("timestamp", ""), 100),

        ])

    # --------------------------------------------------------
    # EVENTS
    # --------------------------------------------------------

    event_rows = []

    for event in events:

        event_rows.append([

            safe_text(event.get("level", ""), 30),

            safe_text(event.get("message", ""), 500),

            safe_text(event.get("timestamp", ""), 100),

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

        engine_status,
        regime,
        last_scan,
        error,

        market_status,
        market_error,
        market_success,

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

            status = result.get("status", "UNKNOWN")

            messages = {
                "COMPLETED": "Market scan completed.",
                "BUSY": "A scan is already running.",
                "TIMEOUT": "Market scan timed out.",
                "ERROR": "Market scan failed.",
                "STOPPED": "Engine stopped during scan.",
                "NOT_RUNNING": "Engine is not running.",
            }

            message = messages.get(
                status,
                f"Scan status: {safe_text(status, 50)}",
            )

            if status == "ERROR" and result.get("message"):
                message += " " + safe_text(
                    result.get("message"),
                    250,
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
        theme=gr.themes.Base(
            primary_hue="cyan",
            neutral_hue="slate",
        ),
    ) as demo:

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        gr.Markdown(
            "# AI QUANT",
            elem_id="main-title",
        )

        gr.Markdown(
            "INTELLIGENT MARKET ANALYSIS | PAPER TRADING",
            elem_id="subtitle",
        )

        gr.Markdown(
            "**SIMULATION MODE ONLY — NO REAL ORDERS**",
            elem_classes=["section-title"],
        )

        # ----------------------------------------------------
        # CONNECTION STATUS
        # ----------------------------------------------------

        gr.Markdown(
            "## SYSTEM STATUS",
            elem_classes=["section-title"],
        )

        with gr.Row():

            engine_status = gr.Textbox(
                label="ENGINE",
                interactive=False,
            )

            market_status = gr.Textbox(
                label="MARKET DATA",
                interactive=False,
            )

        market_error = gr.Textbox(
            label="Market Data Diagnostics",
            interactive=False,
            lines=2,
        )

        market_success = gr.Textbox(
            label="Last Successful Market Request",
            interactive=False,
        )

        # ----------------------------------------------------
        # ACCOUNT CARDS
        # ----------------------------------------------------

        gr.Markdown(
            "## ACCOUNT OVERVIEW",
            elem_classes=["section-title"],
        )

        with gr.Row():

            balance = gr.Textbox(
                label="Available Balance",
                interactive=False,
            )

            equity = gr.Textbox(
                label="Total Equity",
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

        with gr.Row():

            reserved = gr.Textbox(
                label="Reserved Capital",
                interactive=False,
            )

            win_rate = gr.Textbox(
                label="Win Rate",
                interactive=False,
            )

        # ----------------------------------------------------
        # MARKET SCANNER
        # ----------------------------------------------------

        gr.Markdown(
            "## MARKET SCANNER",
            elem_classes=["section-title"],
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

        with gr.Row():

            rejected = gr.Number(
                label="Rejected",
                interactive=False,
            )

            errors = gr.Number(
                label="Errors",
                interactive=False,
            )

        with gr.Row():

            regime = gr.Textbox(
                label="BTC Market Regime",
                interactive=False,
            )

            last_scan = gr.Textbox(
                label="Last Scan",
                interactive=False,
            )

        system_error = gr.Textbox(
            label="System Diagnostics",
            interactive=False,
            lines=2,
        )

        # ----------------------------------------------------
        # SCAN CONTROLS
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
        # TABS
        # ----------------------------------------------------

        with gr.Tabs():

            with gr.Tab("Positions"):

                gr.Markdown(
                    "### OPEN PAPER POSITIONS"
                )

                open_count = gr.Number(
                    label="Open Positions",
                    interactive=False,
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
                    wrap=True,
                )

            with gr.Tab("AI Decisions"):

                gr.Markdown(
                    "### AI DECISION HISTORY"
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
                    wrap=True,
                )

            with gr.Tab("Trade History"):

                gr.Markdown(
                    "### CLOSED PAPER TRADES"
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
                    wrap=True,
                )

            with gr.Tab("System Events"):

                gr.Markdown(
                    "### SYSTEM EVENTS"
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
                    wrap=True,
                )

        # ----------------------------------------------------
        # REFRESH
        # ----------------------------------------------------

        refresh_button = gr.Button(
            "REFRESH DASHBOARD",
        )

        # ----------------------------------------------------
        # OUTPUT ORDER
        # ----------------------------------------------------

        outputs = [

            balance,
            equity,
            realized,
            unrealized,
            reserved,

            open_count,
            win_rate,

            engine_status,
            regime,
            last_scan,
            system_error,

            market_status,
            market_error,
            market_success,

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
