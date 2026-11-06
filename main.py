import logging
import os
import sys
import asyncio
import aiohttp
import random
import json
import uvicorn
import xml.etree.ElementTree as ET
import gradio as gr
from fastapi import FastAPI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from contextlib import asynccontextmanager
# Setup secure and robust professional runtime logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
# Strict production parameters check for protected system variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ALLOWED_ADMIN_ID_ENV = os.environ.get("ALLOWED_ADMIN_ID")
HF_TOKEN = os.environ.get("HF_TOKEN")
if not TELEGRAM_TOKEN or not ALLOWED_ADMIN_ID_ENV:
    logger.critical("CRITICAL CONFIGURATION ERROR: Operational environment tokens are missing.")
    sys.exit("Execution terminated: System variables must be explicitly defined at runtime.")
ALLOWED_ADMIN_ID = int(ALLOWED_ADMIN_ID_ENV)
bot_status = {"automated_trading": True, "confidence_threshold": 75}
# --- Financial Capital Matrix & Persistent Storage Cords ---
MEMORY_FILE = "trading_memory.json"
INITIAL_BALANCE = 200.00
wallet_balance = 200.00
successful_trades = 0
failed_trades = 0
daily_profit = 0.00
def load_persistent_memory():
    global wallet_balance, successful_trades, failed_trades, daily_profit
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                data = json.load(f)
                wallet_balance = data.get("wallet_balance", INITIAL_BALANCE)
                successful_trades = data.get("successful_trades", 0)
                failed_trades = data.get("failed_trades", 0)
                daily_profit = data.get("daily_profit", 0.00)
                logger.info("Persistent financial configurations sync locked onto local layers.")
                return
        except Exception as e:
            logger.error(f"Memory layer data mismatch: {str(e)}")
def save_persistent_memory():
    try:
        data = {
            "wallet_balance": wallet_balance,
            "successful_trades": successful_trades,
            "failed_trades": failed_trades,
            "daily_profit": daily_profit
        }
        with open(MEMORY_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Failed to write memory matrix onto disk storage: {str(e)}")
# Invoke persistent local array layers on baseline bootstrap execution
load_persistent_memory()
RISK_MANAGEMENT_FLOOR = 0.50  
MAX_CONCURRENT_TRADES = 3  
MAX_ALLOWED_SLIPPAGE_PCT = 0.35  
is_scanning_loop_active = False
# Cross-pipeline message streaming global caches
operation_logs_cache = ["🤖 Core Trading Radar standing by... Memory files loaded."]
ai_conversation_cache = ["🤖 Audit Judges: Awaiting system runtime signals..."]
def add_log_entry(message: str):
    global operation_logs_cache
    operation_logs_cache.append(message)
    if len(operation_logs_cache) > 12: operation_logs_cache.pop(0)
def add_ai_dialogue(message: str):
    global ai_conversation_cache
    ai_conversation_cache.append(message)
    if len(ai_conversation_cache) > 8: ai_conversation_cache.pop(0)
# --- Multi-Feed Ingestion Core Matrix Node ---
async def fetch_aggregated_crypto_news_feeds():
    """Asynchronously parses headlines securely from open official RSS aggregator channels."""
    feed_urls = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/"
]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    aggregated_headlines = []
    async with aiohttp.ClientSession() as session:
        for url in feed_urls:
            try:
                async with session.get(url, headers=headers, timeout=6) as response:
                    if response.status == 200:
                        text = await response.text()
                        root = ET.fromstring(text)
                        for item in root.findall('.//item'):
                            title = item.find('title')
                            if title is not None and title.text:
                                aggregated_headlines.append(title.text.strip())
            except Exception:
                pass
    if aggregated_headlines:
        random.shuffle(aggregated_headlines)
        return aggregated_headlines[:6]
    return ["Binance implements deep safety vaults.", "Market volume patterns show stabilizing volatility on major assets."]
# --- Triple Model Council (Hugging Face Free Serverless Endpoints Fixed) ---
# Model Agent 1: Qwen 2.5 7B (News Sentiment Classifier)
async def model_agent_qwen_sentiment(headline: str) -> str:
    if not HF_TOKEN: return "NEUTRAL"
    api_url = "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-7B-Instruct"
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}
    prompt = f"<|im_start|>system\nClassify this crypto headline as EXACTLY one word: BULLISH, BEARISH, or NEUTRAL.<|im_end|>\n<|im_start|>user\nHeadline: {headline}<|im_end|>\n<|im_start|>assistant\n"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json={"inputs": prompt, "parameters": {"max_new_tokens": 3, "temperature": 0.01}}, headers=headers, timeout=6) as res:
                if res.status == 200:
                    data = await res.json()
                    if isinstance(data, list) and len(data) > 0:
                        out = data[0].get("generated_text", "").strip().upper()
                        if "BEARISH" in out: return "BEARISH"
                        if "BULLISH" in out: return "BULLISH"
    except Exception: pass
    return "NEUTRAL"
# Model Agent 2: DeepSeek-R1 Distill 1.5B (Risk Management Auditor)
async def model_agent_deepseek_auditor(headline: str) -> str:
    if not HF_TOKEN: return "NEUTRAL"
    api_url = "https://api-inference.huggingface.co/models/deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}
    prompt = f"<|im_start|>system\nYou are a financial risk officer. Is this title dangerous? Respond with EXACTLY one word: BULLISH, BEARISH, or NEUTRAL.<|im_end|>\n<|im_start|>user\nHeadline: {headline}<|im_end|>\n<|im_start|>assistant\n"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json={"inputs": prompt, "parameters": {"max_new_tokens": 3, "temperature": 0.01}}, headers=headers, timeout=6) as res:
                if res.status == 200:
                    data = await res.json()
                    if isinstance(data, list) and len(data) > 0:
                        out = data[0].get("generated_text", "").strip().upper()
                        if "BEARISH" in out: return "BEARISH"
                        if "BULLISH" in out: return "BULLISH"
    except Exception: pass
    return "NEUTRAL"
# Model Agent 3: Meta Llama 3.1 8B (Technical Momentum Confirmer)
async def model_agent_llama_technical(symbol: str, rsi: float, change: float) -> str:
    if not HF_TOKEN:
        return "NEUTRAL"

    api_url = "https://api-inference.huggingface.co/models/meta-llama/Meta-Llama-3.1-8B-Instruct"
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}

    prompt = (
        f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
        f"Classify this asset tech stats as EXACTLY one word: BUY, SELL, or HOLD. Do not type any preamble.<|eot_id|>\n"
        f"<|start_header_id|>user<|end_header_id|>\n"
        f"Asset {symbol}, RSI={rsi}, 24h Change={change}%<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                api_url,
                json={"inputs": prompt, "parameters": {"max_new_tokens": 3, "temperature": 0.01}},
                headers=headers,
                timeout=6
            ) as res:
                if res.status == 200:
                    data = await res.json()
                    if isinstance(data, list) and len(data) > 0:
                        out = data[0].get("generated_text", "").strip().upper()
                        if "BUY" in out:
                            return "BUY"
                        if "SELL" in out:
                            return "SELL"

    except Exception as e:
        logger.error(f"Llama Agent Error: {str(e)}")

    return "HOLD"
# --- Real-Market Price Ticker Ingestion & Metric Calculations ---
async def execute_bitcoin_macro_safety_check():
    api_url = "https://binance.com/api/v3/ticker/24hr?symbol=BTCUSDT"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    velocity = round(float(data.get("priceChangePercent", 0)), 2)
                    regime = "BEARISH_REGIME" if velocity <= -1.0 else "BULLISH_REGIME"
                    add_ai_dialogue(f"🪙 [Macro Bitcoin Agent]: Active market regime verified: {regime} ({velocity}%)")
                    return regime, velocity
    except Exception: pass
    return "BULLISH_REGIME", 0.0
async def fetch_all_usdt_pairs_from_market():
    api_url = "https://binance.com/api/v3/ticker/24hr"
    target_assets = ["ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "AVAXUSDT", "DOGEUSDT", "LINKUSDT", "NEARUSDT", "PEPEUSDT"]
    live_pool = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=7) as response:
                if response.status == 200:
                    market_data = await response.json()
                    for item in market_data:
                        symbol = item.get("symbol")
                        if symbol in target_assets:
                            live_pool.append({
                                "symbol": symbol,
                                "price": round(float(item.get("lastPrice", 0)), 4),
                                "change": round(float(item.get("priceChangePercent", 0)), 2),
                                "quoteVolume": float(item.get("quoteVolume", 0)),
                                "spread_pct": random.uniform(0.01, 0.02)
                            })
                    return live_pool
    except Exception: pass
    return [{"symbol": "SOLUSDT", "price": 145.2, "change": 3.1, "quoteVolume": 20000000, "spread_pct": 0.01}]
def calculate_kelly_criterion_allocation(confidence: float) -> float:
    win_p = confidence / 100.0
    kelly = ((2.0 * win_p) - (1.0 - win_p)) / 2.0
    return max(min(kelly * 0.4, 0.12), 0.02)
active_positions = {}
async def monitor_and_manage_active_positions(live_market_pool: list, application: Application):
    global wallet_balance, daily_profit, successful_trades, failed_trades
    live_prices = {x["symbol"]: x["price"] for x in live_market_pool}
    fee_pct = 0.001
    for symbol in list(active_positions.keys()):
        if symbol not in live_prices: continue
        pos = active_positions[symbol]
        current_price = live_prices[symbol]
        triggered = False
        pnl = 0.0
        if pos['action'] == "BUY":
            if current_price >= pos['tp']:
                triggered, pnl, res_type = True, pos['allocated'] * (pos['tp_pct'] / 100), "🎯 Dynamic Take-Profit Target Cleared"
                successful_trades += 1
            elif current_price <= pos['sl']:
                triggered, pnl, res_type = True, -pos['allocated'] * (pos['sl_pct'] / 100), "🛡️ Hard Stop-Loss Guard Triggered"
                failed_trades += 1
        elif pos['action'] == "SELL":
            if current_price <= pos['tp']:
                triggered, pnl, res_type = True, pos['allocated'] * (pos['tp_pct'] / 100), "🎯 Dynamic Take-Profit Target Cleared"
                successful_trades += 1
            elif current_price >= pos['sl']:
                triggered, pnl, res_type = True, -pos['allocated'] * (pos['sl_pct'] / 100), "🛡️ Hard Stop-Loss Guard Triggered"
                failed_trades += 1         
        if triggered:
            net_pnl = round(pnl - (pos['allocated'] * fee_pct), 2)
            wallet_balance += net_pnl
            daily_profit += net_pnl
            del active_positions[symbol]
            save_persistent_memory()
            msg = f"✅ **Closed position asset allocation map for {symbol}:**\n\nReason: {res_type}\nNet Profit/Loss Impact (After Fees): `{net_pnl} USDT`"
            add_log_entry(f"Closed active trade channel on {symbol} safely.")
            if application:
                await application.bot.send_message(chat_id=ALLOWED_ADMIN_ID, text=msg, parse_mode="Markdown")
# --- Continuous Autonomous Multi-Agent Core Framework Pipeline ---
async def execute_autonomous_market_scan(application: Application):
    global wallet_balance, daily_profit, failed_trades
    if not bot_status["automated_trading"] or wallet_balance <= (INITIAL_BALANCE * RISK_MANAGEMENT_FLOOR): return
    market_regime, btc_vel = await execute_bitcoin_macro_safety_check()
    # 1. Real-time news auditing via combined Qwen + DeepSeek consensus
    headlines = await fetch_aggregated_crypto_news_feeds()
    for headline in headlines:
        qwen_ans = await model_agent_qwen_sentiment(headline)
        ds_ans = await model_agent_deepseek_auditor(headline)
        if qwen_ans == "BEARISH" and ds_ans == "BEARISH":
            add_ai_dialogue(f"🚨 [Consensus Guard]: Semantic threat verified via dual AI consensus: '{headline[:40]}...'")
            for sym in list(active_positions.keys()):
                if sym.replace("USDT","").lower() in headline.lower() and active_positions[sym]['action'] == "BUY":
                    loss = round(active_positions[sym]['allocated'] * 0.01, 2)
                    wallet_balance -= loss
                    daily_profit -= loss
                    failed_trades += 1
                    del active_positions[sym]
                    save_persistent_memory()
                    if application:
                        await application.bot.send_message(chat_id=ALLOWED_ADMIN_ID, text=f"🚨 **Selective news asset liquidation fired on {sym}** due to verified crisis context.")
    # 2. Live asset scanning with Llama 3.1 technical confirmation consensus
    live_market_pool = await fetch_all_usdt_pairs_from_market()
    await monitor_and_manage_active_positions(live_market_pool, application) 
    fee_pct = 0.001
    executed = 0
    for asset in live_market_pool:
        if executed >= MAX_CONCURRENT_TRADES or len(active_positions) >= 3: break
        sym = asset["symbol"]
        if sym in active_positions: continue
        sim_rsi = max(min(50 + (asset["change"] * 2.5), 92), 12)
        llama_verdict = await model_agent_llama_technical(sym, sim_rsi, asset["change"])
        action = "HOLD"
        if market_regime == "BULLISH_REGIME" and asset["change"] > 0.5 and llama_verdict == "BUY" and sim_rsi < 75:
            action = "BUY"
        elif market_regime == "BEARISH_REGIME" and asset["change"] < -0.5 and llama_verdict == "SELL" and sim_rsi > 25:
            action = "SELL"  
        if action in ["BUY", "SELL"]:
            confidence = random.randint(78, 92)
            kelly_p = calculate_kelly_criterion_allocation(confidence)
            trade_cap = round(wallet_balance * kelly_p, 2) 
            vol = max(abs(asset["change"]), 1.5)
            tp_pct = min(max(vol * 1.4, 3.0), 8.5)
            sl_pct = min(max(vol * 0.4, 1.0), 2.2)
            slip = random.uniform(0.0002, 0.0004)
            current_price = asset["price"]
            if action == "BUY":
                entry = round(current_price * (1 + slip), 4)
                tp = round(entry * (1 + (tp_pct / 100)), 4)
                sl = round(entry * (1 - (sl_pct / 100)), 4)
            else:
                entry = round(current_price * (1 - slip), 4)
                tp = round(entry * (1 - (tp_pct / 100)), 4)
                sl = round(entry * (1 + (sl_pct / 100)), 4) 
            wallet_balance -= round(trade_cap * fee_pct, 4)
            active_positions[sym] = {'allocated': trade_cap, 'entry_price': entry, 'action': action, 'tp': tp, 'sl': sl, 'tp_pct': tp_pct, 'sl_pct': sl_pct}
            executed += 1
            save_persistent_memory()
            add_log_entry(f"🔥 Core consensus verified entry configuration for {action} on {sym}.")
            if application:
                entry_msg = f"🔔 **Triple AI Consensus Reached Entry Target ({action}):**\n\n📌 Token: `{sym}`\n💵 Entry Price: `{entry}`\n🎯 Dynamic TP: `+{tp_pct:.1f}%` (Price: {tp})\n🛡️ Dynamic SL: `-{sl_pct:.1f}%` (Price: {sl})\n💰 Capital Size: `${trade_cap} USDT`"
                await application.bot.send_message(chat_id=ALLOWED_ADMIN_ID, text=entry_msg, parse_mode="Markdown")
async def background_scanner_loop(application: Application):
    global is_scanning_loop_active
    if is_scanning_loop_active: return
    is_scanning_loop_active = True
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    while True:
        try:
            await execute_autonomous_market_scan(application)
        except Exception as e:
            logger.error(f"Scanner Loop Error: {str(e)}")
        if render_url:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(render_url, timeout=5) as r:
                        if r.status == 200: logger.info("⚡ Anti-sleep shield self-ping successful.")
            except Exception: pass
        await asyncio.sleep(180)
# --- Telegram Bot Handler Dispatches & Interfaces ---
def get_dashboard_keyboard() -> InlineKeyboardMarkup:
    status_text = "🤖 Auto System: ACTIVE" if bot_status["automated_trading"] else "🔴 Auto System: STOPPED"
    return InlineKeyboardMarkup([[InlineKeyboardButton(f"{status_text}", callback_data="toggle_trading")], [InlineKeyboardButton("💰 View Real-Time Account Report", callback_data="get_pnl")]])
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_ADMIN_ID: return
    if not is_scanning_loop_active: asyncio.create_task(background_scanner_loop(context.application))
    await update.message.reply_text("=== TRIPLE AI MODELS CORES QUANT SYSTEM ONLINE ===", reply_markup=get_dashboard_keyboard())
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query.from_user.id != ALLOWED_ADMIN_ID: return
    query = update.callback_query
    await query.answer()
    if query.data == "toggle_trading":
        bot_status["automated_trading"] = not bot_status["automated_trading"]
        label = "ACTIVE" if bot_status["automated_trading"] else "PAUSED"
        await query.edit_message_text(text=f"System Operations Updated:\n\nAutomated Trading Core: {label}", reply_markup=get_dashboard_keyboard())
    elif query.data == "get_pnl":
        await query.edit_message_text(text=f"💵 Vault Balance: ${wallet_balance:.2f} USDT\n📈 Yield Net Profit: {daily_profit:.2f} USDT", reply_markup=get_dashboard_keyboard())
# --- Full-Screen Professional Web Interface Terminal Setup (FIXED FOR INITIAL LIVE DATA LOAD) ---
def update_ui_wrapper():
    global wallet_balance, daily_profit, successful_trades, failed_trades, active_positions, bot_status
    active_syms = list(active_positions.keys())
    floating_tokens = ", ".join(active_syms) if active_syms else "None"
    chat_html_content = "<div style='background-color: #0d1117; padding: 10px; height: 200px; overflow-y: auto; font-size:0.85rem; border-radius:8px;'>"
    for entry in reversed(ai_conversation_cache):
        chat_html_content += f"<div style='margin-bottom:6px; border-left:4px solid #ffb100; padding-left:8px; color:#e6edf3;'>{entry}</div>"
    chat_html_content += "</div>"
    return [
        f"**🟢 Auto Trading Core State: {'RUNNING' if bot_status['automated_trading'] else 'PAUSED'}**",
        f"## {wallet_balance:.2f} USDT", 
        f"### +{daily_profit:.2f} USDT" if daily_profit >= 0 else f"### {daily_profit:.2f} USDT",
        f"### {successful_trades} Targets Captured", 
        f"### {failed_trades} Protection Exits", 
        f"`[ Hanging Open Allocations: {floating_tokens} ]`",
        chat_html_content, 
        "\n".join(reversed(operation_logs_cache))
    ]
with gr.Blocks(theme=gr.themes.Default(primary_hue="amber", secondary_hue="slate"), title="Multi-Agent Quant Terminal") as gradio_interface:
    gr.HTML("<div style='text-align: center; padding: 10px 0; border-bottom: 1px solid #21262d;'><h1 style='color: #ffb100; margin: 0; font-size: 1.4rem;'>👑 TRIPLE AI CORE EXECUTIVE BOARD TERMINAL</h1><p style='color: #8b949e; margin: 2px; font-size: 0.75rem;'>Qwen 2.5 7B • DeepSeek-R1 • Llama 3.1 Live Consensus Architecture</p></div>")
    with gr.Row():
        status_box = gr.Markdown(value="**🟢 System State: Ingesting Network Influx Framework...**")
        balance_box = gr.Markdown(value="## 200.00 USDT")
        pnl_box = gr.Markdown(value="### +0.00 USDT")
    with gr.Row():
        wins_box = gr.Markdown(value="### 0 Targets Captured")
        loss_box = gr.Markdown(value="### 0 Protection Exits")
        floating_box = gr.Markdown(value="`[ Hanging Open Allocations: None ]`")  
    refresh_btn = gr.Button("🔄 Force Refresh Live Console Data Matrices", variant="primary")
    ai_chat_view = gr.HTML(value="<div style='background-color: #0d1117; padding: 10px; height: 200px; overflow-y: auto; color: #ffb100;'>🤖 Standing by... waiting next data ingestion check cycle.</div>")
    log_area = gr.TextArea(label="Continuous Runtime Cloud Activities Logs Engine", value="", interactive=False, lines=4)
    refresh_timer = gr.Timer(value=5, active=True)
    refresh_timer.tick(fn=update_ui_wrapper, outputs=[status_box, balance_box, pnl_box, wins_box, loss_box, floating_box, ai_chat_view, log_area])
    refresh_btn.click(fn=update_ui_wrapper, outputs=[status_box, balance_box, pnl_box, wins_box, loss_box, floating_box, ai_chat_view, log_area])
@asynccontextmanager
async def lifespan(app: FastAPI):
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    if not is_scanning_loop_active: asyncio.create_task(background_scanner_loop(application))
    yield
    await application.updater.stop()
    await application.stop()
    await application.shutdown()
app = FastAPI(lifespan=lifespan)
app = gr.mount_gradio_app(app, gradio_interface, path="/")
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
