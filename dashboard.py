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
    font-weight: 900;
    letter-spacing: 3px;
}

.subtitle {
    text-align: center;
    color: #7f9db8;
    font-size: 12px;
}

.metric {
    background: #101b2d;
    border: 1px solid #173a55;
    border-radius: 14px;
    padding: 15px;
    text-align: center;
}

.metric-label {
    color: #8ba8c1;
    font-size: 12px;
}

.metric-value {
    color: #00e5ff;
    font-size: 23px;
    font-weight: bold;
}

.status {
    color: #00e5a8;
    font-weight: bold;
}

button {
    border-radius: 10px !important;
}

@media (max-width: 600px) {
    #main-title {
        font-size: 23px;
    }

    .metric-value {
        font-size: 19px;
    }

    .gradio-container {
        padding: 8px !important;
    }
}
"""


def money(value):
    return f"{float(value):.4f} USDT"


def build_dashboard(controller):

    def get_dashboard():

        trader = controller.trader
        engine = controller.engine
        db = controller.db

        summary = trader.get_summary()

        status = (
            "ONLINE"
            if engine.running
            else "STOPPED"
        )

        last_scan = (
            engine.last_scan
            or "Not scanned yet"
        )

        regime = engine.market_regime

        account_html = f"""
        <div style="display:grid;
                    grid-template-columns:repeat(2,minmax(0,1fr));
                    gap:10px;">

            <div class="metric">
                <div class="metric-label">AVAILABLE BALANCE</div>
                <div class="metric-value">{money(summary['balance'])}</div>
            </div>

            <div class="metric">
                <div class="metric-label">TOTAL EQUITY</div>
                <div class="metric-value">{money(summary['equity'])}</div>
            </div>

            <div class="metric">
                <div class="metric-label">REALIZED P/L</div>
                <div class="metric-value">{money(summary['realized_pnl'])}</div>
            </div>

            <div class="metric">
                <div class="metric-label">UNREALIZED P/L</div>
                <div class="metric-value">{money(summary['unrealized_pnl'])}</div>
            </div>

            <div class="metric">
                <div class="metric-label">RESERVED CAPITAL</div>
                <div class="metric-value">{money(summary['reserved'])}</div>
            </div>

            <div class="metric">
                <div class="metric-label">WIN RATE</div>
                <div class="metric-value">{summary['win_rate']:.1f}%</div>
            </div>
        </div>
        """

        status_html = f"""
        <div class="metric">
            <div class="status">SYSTEM: {status}</div>
            <div>MARKET REGIME: {regime}</div>
            <div style="font-size:12px;color:#8ba8c1;">
                LAST SCAN: {last_scan}
            </div>
            <div style="font-size:12px;color:#8ba8c1;">
                MODE: PAPER TRADING ONLY
            </div>
            <div style="font-size:12px;color:#ffb86b;">
                {engine.last_error or ""}
            </div>
        </div>
        """

        positions = summary["positions"]

        if positions:

            position_rows = []

            for p in positions:

                position_rows.append(
                    f"| {p['symbol']} "
                    f"| {float(p['entry_price']):.6f} "
                    f"| {float(p['current_price']):.6f} "
                    f"| {float(p['unrealized_pnl']):.4f} |"
                )

            positions_md = (
                "| SYMBOL | ENTRY | CURRENT | P/L |\n"
                "|---|---:|---:|---:|\n"
                + "\n".join(position_rows)
            )

        else:
            positions_md = "لا توجد صفقات افتراضية مفتوحة."

        decisions = db.get_recent_decisions(15)

        if decisions:

            decision_rows = []

            for d in decisions:

                decision_rows.append(
                    f"| {d['symbol']} "
                    f"| {d['action']} "
                    f"| {d['score']} "
                    f"| {d.get('ai_vote', 'N/A')} |"
                )

            decisions_md = (
                "| SYMBOL | ACTION | SCORE | AI |\n"
                "|---|---|---:|---|\n"
                + "\n".join(decision_rows)
            )

        else:
            decisions_md = "لا توجد قرارات مسجلة بعد."

        trades = db.get_recent_trades(15)

        if trades:

            trade_rows = []

            for t in trades:

                trade_rows.append(
                    f"| {t['symbol']} "
                    f"| {float(t['entry_price']):.6f} "
                    f"| {float(t['exit_price']):.6f} "
                    f"| {float(t['net_pnl']):.4f} "
                    f"| {t['reason']} |"
                )

            trades_md = (
                "| SYMBOL | ENTRY | EXIT | NET P/L | REASON |\n"
                "|---|---:|---:|---:|---|\n"
                + "\n".join(trade_rows)
            )

        else:
            trades_md = "لا يوجد سجل صفقات بعد."

        return (
            account_html,
            status_html,
            positions_md,
            decisions_md,
            trades_md
        )

    async def force_scan():

        results = await controller.engine.scan_once()

        message = (
            f"اكتمل الفحص. عدد النتائج: {len(results)}"
        )

        return message, *get_dashboard()

    with gr.Blocks(
        css=CSS,
        title="AI QUANT"
    ) as demo:

        gr.HTML("""
        <div id="main-title">AI QUANT</div>
        <div class="subtitle">
            AUTONOMOUS MARKET ANALYSIS SYSTEM
        </div>
        <div class="subtitle">
            SIMULATION MODE · NO REAL ORDERS
        </div>
        """)

        with gr.Row():
            account = gr.HTML()

        status = gr.HTML()

        gr.Markdown("## OPEN POSITIONS")
        positions = gr.Markdown()

        gr.Markdown("## MARKET DECISIONS")
        decisions = gr.Markdown()

        gr.Markdown("## PAPER TRADE HISTORY")
        trades = gr.Markdown()

        scan_button = gr.Button(
            "SCAN MARKET NOW",
            variant="primary"
        )

        refresh_button = gr.Button(
            "REFRESH DASHBOARD"
        )

        message = gr.Textbox(
            label="SYSTEM MESSAGE",
            interactive=False
        )

        scan_button.click(
            force_scan,
            outputs=[
                message,
                account,
                status,
                positions,
                decisions,
                trades
            ]
        )

        refresh_button.click(
            get_dashboard,
            outputs=[
                account,
                status,
                positions,
                decisions,
                trades
            ]
        )

        demo.load(
            get_dashboard,
            outputs=[
                account,
                status,
                positions,
                decisions,
                trades
            ]
        )

    return demo
