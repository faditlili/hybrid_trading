import gradio as gr

from datetime import datetime


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


def safe_float(value):

    try:

        result = float(value)

        if result != result:
            return 0.0

        return result

    except (TypeError, ValueError, OverflowError):

        return 0.0


def money(value):

    return f"{safe_float(value):,.2f} USDT"


def get_dashboard(controller):

    trader = controller.trader
    engine = controller.engine
    db = controller.db

    summary = trader.get_summary()

    balance = summary.get("balance", 0)
    equity = summary.get("equity", 0)
    realized = summary.get("realized_pnl", 0)
    unrealized = summary.get("unrealized_pnl", 0)
    reserved = summary.get("reserved", 0)

    positions = summary.get("positions", [])

    decisions = db.get_recent_decisions(15)
    trades = db.get_recent_trades(15)
    events = db.get_recent_events(20)

    stats = engine.scan_stats

    status = (
        "RUNNING"
        if engine.running
        else "STOPPED"
    )

    regime = engine.market_regime

    last_scan = (
        engine.last_scan
        or "Not scanned yet"
    )

    error = (
        engine.last_error
        or "No system errors"
    )

    position_rows = []

    for position in positions:

        position_rows.append([
            position.get("symbol", ""),
            round(
                safe_float(position.get("entry_price")),
                8
            ),
            round(
                safe_float(position.get("current_price")),
                8
            ),
            round(
                safe_float(position.get("quantity")),
                6
            ),
            round(
                safe_float(position.get("unrealized_pnl")),
                4
            ),
            round(
                safe_float(position.get("stop_loss")),
                8
            ),
            round(
                safe_float(position.get("take_profit")),
                8
            )
        ])

    decision_rows = []

    for decision in decisions:

        reasons = decision.get("reasons", "")

        if isinstance(reasons, list):

            reasons = " | ".join(
                str(item)
                for item in reasons
            )

        decision_rows.append([
            decision.get("symbol", ""),
            decision.get("action", ""),
            decision.get("score", 0),
            decision.get("ai_vote", ""),
            str(reasons)[:350],
            decision.get("timestamp", "")
        ])

    trade_rows = []

    for trade in trades:

        trade_rows.append([
            trade.get("symbol", ""),
            round(
                safe_float(trade.get("entry_price")),
                8
            ),
            round(
                safe_float(trade.get("exit_price")),
                8
            ),
            round(
                safe_float(trade.get("net_pnl")),
                4
            ),
            trade.get("reason", ""),
            trade.get("timestamp", "")
        ])

    event_rows = []

    for event in events:

        event_rows.append([
            event.get("level", ""),
            event.get("message", ""),
            event.get("timestamp", "")
        ])

    return (
        money(balance),
        money(equity),
        money(realized),
        money(unrealized),
        money(reserved),
        len(positions),
        f"{safe_float(summary.get('win_rate')):.2f}%",
        status,
        regime,
        last_scan,
        error,
        stats.get("scanned", 0),
        stats.get("approved", 0),
        stats.get("rejected", 0),
        stats.get("errors", 0),
        position_rows,
        decision_rows,
        trade_rows,
        event_rows
    )


def force_scan(controller):

    engine = controller.engine

    if engine.scan_lock.locked():

        return (
            "A scan is already running.",
            *get_dashboard(controller)
        )

    import asyncio

    try:

        loop = asyncio.get_running_loop()

        # Gradio callback executes inside the running server loop.
        # Schedule the scan without blocking the event loop.
        task = loop.create_task(
            engine.scan_once()
        )

        task.add_done_callback(
            lambda completed: completed.exception()
            if not completed.cancelled()
            else None
        )

        message = "Market scan started."

    except RuntimeError:

        message = "Unable to start scan."

    return (
        message,
        *get_dashboard(controller)
    )


def build_dashboard(controller):

    with gr.Blocks(
        css=CSS,
        title="AI QUANT"
    ) as demo:

        gr.Markdown(
            "# AI QUANT",
            elem_id="main-title"
        )

        gr.Markdown(
            "AUTONOMOUS MARKET ANALYSIS | PAPER TRADING",
            elem_id="subtitle"
        )

        gr.Markdown(
            "SIMULATION MODE ONLY — NO REAL ORDERS",
            elem_classes=["status-text"]
        )

        with gr.Row():

            balance = gr.Textbox(
                label="Available Balance",
                interactive=False
            )

            equity = gr.Textbox(
                label="Total Equity",
                interactive=False
            )

            reserved = gr.Textbox(
                label="Reserved Capital",
                interactive=False
            )

        with gr.Row():

            realized = gr.Textbox(
                label="Realized PnL",
                interactive=False
            )

            unrealized = gr.Textbox(
                label="Unrealized PnL",
                interactive=False
            )

            win_rate = gr.Textbox(
                label="Win Rate",
                interactive=False
            )

        with gr.Row():

            open_count = gr.Number(
                label="Open Positions",
                interactive=False
            )

            status = gr.Textbox(
                label="Engine Status",
                interactive=False
            )

            regime = gr.Textbox(
                label="BTC Market Regime",
                interactive=False
            )

        with gr.Row():

            last_scan = gr.Textbox(
                label="Last Scan",
                interactive=False
            )

        with gr.Row():

            scanned = gr.Number(
                label="Scanned",
                interactive=False
            )

            approved = gr.Number(
                label="Approved",
                interactive=False
            )

            rejected = gr.Number(
                label="Rejected",
                interactive=False
            )

            errors = gr.Number(
                label="Errors",
                interactive=False
            )

        system_error = gr.Textbox(
            label="System Diagnostics",
            interactive=False
        )

        gr.Markdown(
            "## MARKET CONTROL",
            elem_classes=["section-title"]
        )

        scan_button = gr.Button(
            "SCAN MARKET NOW",
            variant="primary"
        )

        scan_message = gr.Textbox(
            label="Scan Result",
            interactive=False
        )

        gr.Markdown(
            "## OPEN PAPER POSITIONS",
            elem_classes=["section-title"]
        )

        positions = gr.Dataframe(
            headers=[
                "Symbol",
                "Entry",
                "Current",
                "Quantity",
                "Unrealized PnL",
                "Stop Loss",
                "Take Profit"
            ],
            datatype=[
                "str",
                "number",
                "number",
                "number",
                "number",
                "number",
                "number"
            ],
            interactive=False
        )

        gr.Markdown(
            "## AI DECISION HISTORY",
            elem_classes=["section-title"]
        )

        decisions = gr.Dataframe(
            headers=[
                "Symbol",
                "Action",
                "Score",
                "AI Vote",
                "Reasons",
                "Timestamp"
            ],
            interactive=False
        )

        gr.Markdown(
            "## CLOSED PAPER TRADES",
            elem_classes=["section-title"]
        )

        trades = gr.Dataframe(
            headers=[
                "Symbol",
                "Entry",
                "Exit",
                "Net PnL",
                "Reason",
                "Timestamp"
            ],
            interactive=False
        )

        gr.Markdown(
            "## SYSTEM EVENTS",
            elem_classes=["section-title"]
        )

        events = gr.Dataframe(
            headers=[
                "Level",
                "Message",
                "Timestamp"
            ],
            interactive=False
        )

        refresh_button = gr.Button(
            "REFRESH DASHBOARD"
        )

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
            events
        ]

        refresh_button.click(
            fn=lambda: get_dashboard(controller),
            outputs=outputs
        )

        scan_button.click(
            fn=lambda: force_scan(controller),
            outputs=[
                scan_message,
                *outputs
            ]
        )

        timer = gr.Timer(
            value=15
        )

        timer.tick(
            fn=lambda: get_dashboard(controller),
            outputs=outputs
        )

        demo.load(
            fn=lambda: get_dashboard(controller),
            outputs=outputs
        )

    return demo


def create_dashboard(controller):

    return build_dashboard(controller)
