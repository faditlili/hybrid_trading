import gradio as gr
from datetime import datetime

from config import APP_NAME


def create_dashboard(controller):
    def render():
        trader = controller.trader
        summary = trader.summary()

        positions = trader.db.positions()
        decisions = trader.db.recent("decisions", 15)
        trades = trader.db.recent("trades", 15)
        events = trader.db.recent("events", 10)

        status = (
            "RUNNING"
            if controller.running
            else "STOPPED"
        )

        position_rows = [
            [
                p["symbol"],
                round(p["entry"], 8),
                round(p["stop"], 8),
                round(p["target"], 8),
                round(p["quantity"], 6)
            ]
            for p in positions
        ]

        decision_rows = [
            [
                d["symbol"],
                d["score"],
                d["action"],
                d["created_at"][:19]
            ]
            for d in decisions
        ]

        trade_rows = [
            [
                t["symbol"],
                round(t["entry"], 8),
                round(t["exit"], 8),
                round(t["pnl"], 4),
                t["reason"]
            ]
            for t in trades
        ]

        event_rows = [
            [
                e["level"],
                e["message"],
                e["created_at"][:19]
            ]
            for e in events
        ]

        return (
            status,
            round(summary["available_balance"], 4),
            round(summary["realized_pnl"], 4),
            summary["open_positions"],
            position_rows,
            decision_rows,
            trade_rows,
            event_rows
        )

    async def force_scan():
        await controller.scan_once()
        return render()

    with gr.Blocks(
        title=APP_NAME,
        theme=gr.themes.Base(
            primary_hue="cyan",
            secondary_hue="blue",
            neutral_hue="slate"
        ),
        css="""
        body {
            background: #050914 !important;
        }

        .gradio-container {
            max-width: 1100px !important;
            margin: auto !important;
            background: #050914 !important;
            color: #e6f7ff !important;
        }

        .panel {
            border: 1px solid #12384a !important;
            border-radius: 14px !important;
            background: #091522 !important;
        }

        h1, h2, h3 {
            color: #00d9ff !important;
        }

        button {
            border-radius: 10px !important;
        }

        @media (max-width: 600px) {
            .gradio-container {
                padding: 8px !important;
            }
        }
        """
    ) as demo:

        gr.Markdown(
            f"""
            # ◈ {APP_NAME}

            ### AUTONOMOUS PAPER-TRADING SYSTEM

            <small>SIMULATION ONLY · NO REAL ORDERS</small>
            """
        )

        with gr.Row():
            status = gr.Textbox(
                label="ENGINE STATUS",
                interactive=False
            )

            balance = gr.Number(
                label="AVAILABLE VIRTUAL BALANCE",
                interactive=False
            )

        with gr.Row():
            pnl = gr.Number(
                label="REALIZED P/L",
                interactive=False
            )

            open_count = gr.Number(
                label="OPEN POSITIONS",
                interactive=False
            )

        refresh = gr.Button(
            "⟳ REFRESH DASHBOARD",
            variant="primary"
        )

        scan = gr.Button(
            "SCAN MARKET NOW",
            variant="secondary"
        )

        gr.Markdown("## OPEN POSITIONS")

        positions = gr.Dataframe(
            headers=[
                "Symbol",
                "Entry",
                "Stop",
                "Target",
                "Quantity"
            ],
            interactive=False
        )

        gr.Markdown("## RECENT DECISIONS")

        decisions = gr.Dataframe(
            headers=[
                "Symbol",
                "Score",
                "Action",
                "Time"
            ],
            interactive=False
        )

        gr.Markdown("## TRADE HISTORY")

        trades = gr.Dataframe(
            headers=[
                "Symbol",
                "Entry",
                "Exit",
                "Net P/L",
                "Reason"
            ],
            interactive=False
        )

        gr.Markdown("## SYSTEM EVENTS")

        events = gr.Dataframe(
            headers=[
                "Level",
                "Message",
                "Time"
            ],
            interactive=False
        )

        outputs = [
            status,
            balance,
            pnl,
            open_count,
            positions,
            decisions,
            trades,
            events
        ]

        refresh.click(
            fn=render,
            outputs=outputs
        )

        scan.click(
            fn=force_scan,
            outputs=outputs
        )

        demo.load(
            fn=render,
            outputs=outputs
        )

    return demo
