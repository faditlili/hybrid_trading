
import html
import logging
import gradio as gr

logger = logging.getLogger(__name__)


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


def safe_float(value):
    try:
        number = float(value)

        if not __import__("math").isfinite(number):
            return 0.0

        return number

    except (TypeError, ValueError):
        return 0.0


def money(value):
    return f"{safe_float(value):.4f} USDT"


def safe_text(value):
    return html.escape(
        str(value if value is not None else ""),
        quote=True
    ).replace("|", "&#124;").replace("\n", " ")


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

        last_scan = safe_text(
            engine.last_scan or "Not scanned yet"
        )

        regime = safe_text(
            engine.market_regime or "UNKNOWN"
        )

        last_error = safe_text(
            engine.last_error or ""
        )

        account_html = f"""
        <div style="
            display:grid;
            grid-template-columns:repeat(2,minmax(0,1fr));
            gap:10px;
        ">

            <div class="metric">
                <div class="metric-label">AVAILABLE BALANCE</div>
                <div class="metric-value">
                    {money(summary['balance'])}
                </div>
            </div>

            <div class="metric">
                <div class="metric-label">TOTAL EQUITY</div>
                <div class="metric-value">
                    {money(summary['equity'])}
                </div>
            </div>

            <div class="metric">
                <div class="metric-label">REALIZED P/L</div>
                <div class="metric-value">
                    {money(summary['realized_pnl'])}
                </div>
            </div>

            <div class="metric">
                <div class="metric-label">UNREALIZED P/L</div>
                <div class="metric-value">
                    {money(summary['unrealized_pnl'])}
                </div>
            </div>

            <div class="metric">
                <div class="metric-label">RESERVED CAPITAL</div>
                <div class="metric-value">
                    {money(summary['reserved'])}
                </div>
            </div>

            <div class="metric">
                <div class="metric-label">WIN RATE</div>
                <div class="metric-value">
                    {safe_float(summary['win_rate']):.1f}%
                </div>
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
                {last_error}
            </div>
        </div>
        """

        positions = summary["positions"]

        if positions:

            position_rows = []

            for p in positions:

                position_rows.append(
                    f"| {safe_text(p['symbol'])} "
                    f"| {safe_float(p['entry_price']):.6f} "
                    f"| {safe_float(p['current_price']):.6f} "
                    f"| {safe_float(p['unrealized_pnl']):.4f} |"
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
                    f"| {safe_text(d['symbol'])} "
                    f"| {safe_text(d['action'])} "
                    f"| {safe_float(d['score']):.0f} "
                    f"| {safe_text(d.get('ai_vote', 'N/A'))} |"
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
                    f"| {safe_text(t['symbol'])} "
                    f"| {safe_float(t['entry_price']):.6f} "
                    f"| {safe_float(t['exit_price']):.6f} "
                    f"| {safe_float(t['net_pnl']):.4f} "
                    f"| {safe_text(t['reason'])} |"
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

        engine = controller.engine

        if engine.scan_lock.locked():

            return (
                "الفحص جارٍ بالفعل.",
                *get_dashboard()
            )

        try:

            results = await engine.scan_once()

            message = (
                f"اكتمل الفحص. عدد النتائج: {len(results)}"
            )

        except Exception:

            logger.exception(
                "Dashboard manual scan failed"
            )

            message = (
                "تعذر إكمال الفحص. راجع سجل النظام."
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

        outputs = [
            account,
            status,
            positions,
            decisions,
            trades
        ]

        scan_button.click(
            force_scan,
            outputs=[message] + outputs
        )

        refresh_button.click(
            get_dashboard,
            outputs=outputs
        )

        demo.load(
            get_dashboard,
            outputs=outputs
        )

        timer = gr.Timer(15)

        timer.tick(
            get_dashboard,
            outputs=outputs
        )

    return demo
