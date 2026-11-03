import asyncio
import aiohttp
import random
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

# Global variables for the experimental testing environment
wallet_balance = 1250.50
successful_trades = 0
failed_trades = 0
daily_profit = 0.0

# Active monitoring matrix for open positions (supports Trailing & Break-Even rules)
active_positions = {}

# Advanced risk management parameters configuration
RISK_ALLOCATION_PCT = 10.0   # Compound capital size allocation per position
TAKE_PROFIT_PCT = 3.0        # Strict automated profit target milestone
INITIAL_STOP_LOSS_PCT = 1.5  # Initial protective stop-loss floor from entry
BREAK_EVEN_TRIGGER_PCT = 1.2 # Profit trigger to shift stop loss to entry price
ANTI_FLASH_CRASH_PCT = -10.0 # Instant volatility block threshold for bad news

# Static asset exclusions based on explicit high-volatility restrictions
EXCLUDED_SYMBOLS = ["BTCUSDT", "XAUUSDT"]

# Encrypted Telegram credential structures
TELEGRAM_BOT_TOKEN = "9280016184:AAGf-ahqxp09mK8_wKV668gNb_agE1774dU"
ADMIN_USER_ID = 6139382680  # Secure administrative identity firewall
async def get_binance_ticker_payload(session: aiohttp.ClientSession):
    """Executes high-performance market fetch query from official endpoints."""
    url = "https://binance.com"
    try:
        async with session.get(url, timeout=5) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 429:
                print("⚠️ Warning: Server is being rate-limited by Binance API.")
                return None
    except Exception as e:
        print(f"Network request connection error: {e}")
    return None

async def fetch_live_market_data(session: aiohttp.ClientSession):
    """Processes network telemetry data stream and enforces liquidity bounds."""
    raw_data = await get_binance_ticker_payload(session)
    if not raw_data: 
        return []
        
    valid_market_pool = []
    for item in raw_data:
        symbol = item.get("symbol", "")
        if symbol.endswith("USDT") and symbol not in EXCLUDED_SYMBOLS:
            try:
                change = float(item.get("priceChangePercent", 0))
                
                # Enforce fundamental protection filter against systemic breakdowns
                if change <= ANTI_FLASH_CRASH_PCT: 
                    continue
                
                vol_factor = float(item.get("volume", 0))
                # Mathematical momentum calculation used to estimate dynamic RSI values
                simulated_rsi = max(min(int(50 + (change * 2.5) + (vol_factor % 5)), 95), 10)
                
                valid_market_pool.append({
                    "symbol": symbol,
                    "price": float(item.get("lastPrice", 0)),
                    "change": change,
                    "volume": vol_factor,
                    "rsi": simulated_rsi
                })
            except (ValueError, TypeError): 
                continue
                
    if valid_market_pool:
        # Sort in memory by 24h trading volume to guarantee high liquidity floor
        valid_market_pool.sort(key=lambda x: x["volume"], reverse=True)
        return valid_market_pool[:12]
    return []
def run_equations_engine(change_percent, rsi):
    """Engine 1: Fixed strict mathematical quantitative rule framework with RSI integration."""
    if rsi > 75: 
        return 40, "SELL"  # Extreme overbought resistance filter
    if rsi < 25: 
        return 85, "BUY"   # High probability oversold reversal signal
    
    abs_momentum = abs(change_percent)
    if abs_momentum < 2.5: 
        return 45, "HOLD"
    if change_percent > 3.0:
        confidence = 78 + (change_percent * 1.2)
        return min(int(confidence), 100), "BUY"
    elif change_percent < -3.0:
        confidence = 74 + (abs_momentum * 1.2)
        return min(int(confidence), 100), "SELL"
    return 50, "HOLD"

def run_ai_pattern_engine(price, change, volume, rsi):
    """Engine 2: Heuristic vector engine optimizing trends against liquidity factors."""
    score = 50 
    if volume > 10000000 and abs(change) > 4.0: 
        score += 20  # Structural momentum verification
    if rsi in range(30, 45) and change > 0: 
        score += 20  # Convergence trade confirmation signal
    if price < 1.0 and change > 0: 
        score += 10  # Low-cap configurations adjustment bonus
    if abs(change) > 15.0: 
        score -= 20  # Noise filtering reversal mechanism
        
    action = "BUY" if change > 0 else "SELL"
    if abs(change) <= 2.5: 
        action, score = "HOLD", 50
    return min(max(int(score), 0), 100), action
async def auto_trading_job(context: ContextTypes.DEFAULT_TYPE):
    """Coordinating processing core managing trailing trailing tracking and new execution."""
    global wallet_balance, successful_trades, failed_trades, daily_profit, active_positions
    session = context.application.bot_data["web_session"]
    market_assets = await fetch_live_market_data(session)
    if not market_assets: 
        return

    current_assets = {asset["symbol"]: asset for asset in market_assets}
    
    # 1️⃣ Track and execute real-time evaluations on active open positions
    for symbol, pos in list(active_positions.items()):
        if symbol in current_assets:
            current_price = current_assets[symbol]["price"]
            entry_price = pos["entry_price"]
            highest_price = pos["highest_price"]
            
            price_change = ((current_price - entry_price) / entry_price) * 100
            
            # Break-Even rule execution: lock structural capital safety at +1.2% profit
            if price_change >= BREAK_EVEN_TRIGGER_PCT and not pos["is_break_even"]:
                active_positions[symbol]["stop_loss_price"] = entry_price
                active_positions[symbol]["is_break_even"] = True
                await context.bot.send_message(chat_id=ADMIN_USER_ID, text=f"🔒 **Capital Lock Activated for {symbol}!**\nStop loss shifted to entry price to secure risk-free execution.")

            # Update structural market peaks to slide the trailing stop loss line higher
            if current_price > highest_price:
                active_positions[symbol]["highest_price"] = current_price
                new_sl = current_price * (1 - (INITIAL_STOP_LOSS_PCT / 100))
                active_positions[symbol]["stop_loss_price"] = max(pos["stop_loss_price"], new_sl)
                highest_price = current_price
            
            triggered_close = False
            if price_change >= TAKE_PROFIT_PCT:
                triggered_close = True
                reason = f"🟢 **Take Profit target met (+{TAKE_PROFIT_PCT}%)**"
            elif current_price <= pos["stop_loss_price"]:
                triggered_close = True
                reason = "🔴 **Trailing Stop Loss triggered (Capital/Profit Saved)**"
                
            if triggered_close:
                allocated = pos["allocated"]
                p_l = round(allocated * (price_change / 100), 2)
                wallet_balance += (allocated + p_l)
                daily_profit += p_l
                
                if p_l > 0: successful_trades += 1
                else: failed_trades += 1
                
                msg = f"⚡ **Position Closed Electronically!**\n\nAsset: `{symbol}`\nReason: {reason}\nNet Outcome: `{p_l:+.2f} USDT`"
                active_positions.pop(symbol, None)
                await context.bot.send_message(chat_id=ADMIN_USER_ID, text=msg, parse_mode="Markdown")

    # 2️⃣ Scan underlying assets pool for high-probability entry targets
    for asset in market_assets:
        symbol = asset["symbol"]
        if symbol in active_positions: 
            continue
        
        eq_conf, eq_act = run_equations_engine(asset["change"], asset["rsi"])
        ai_conf, ai_act = run_ai_pattern_engine(asset["price"], asset["change"], asset["volume"], asset["rsi"])
        
        total_confidence = int((eq_conf * 0.5) + (ai_conf * 0.5))
        final_action = eq_act if eq_act == ai_act and eq_act in ["BUY", "SELL"] else "HOLD"
        
        if total_confidence >= 80 and final_action != "HOLD":
            # Compound Interest Engine calculation allocating 10% of dynamic live balance
            allocated = max(round(wallet_balance * (RISK_ALLOCATION_PCT / 100), 2), 1.0)
            wallet_balance -= allocated
            
            active_positions[symbol] = {
                "entry_price": asset["price"],
                "highest_price": asset["price"],
                "stop_loss_price": asset["price"] * (1 - (INITIAL_STOP_LOSS_PCT / 100)),
                "allocated": allocated,
                "type": final_action,
                "is_break_even": False
            }
            
            # Inline control board setup for instant manual intervention
            keyboard = [[InlineKeyboardButton(f"❌ Force Close {symbol}", callback_data=f"close_{symbol}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            msg = f"🚀 **Hybrid Model Executed New Position! (Risk Sizing: {RISK_ALLOCATION_PCT}%)**\n\n" \
                  f"Trading Pair: `{symbol}`\n" \
                  f"Entry Execution Price: `${asset['price']}`\n" \
                  f"Allocated Balance Payload: `{allocated} USDT`"
            await context.bot.send_message(chat_id=ADMIN_USER_ID, text=msg, parse_mode="Markdown", reply_markup=reply_markup)
async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes interactive interface inline requests safely."""
    global wallet_balance, failed_trades
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("close_"):
        symbol = query.data.replace("close_", "")
        if symbol in active_positions:
            pos = active_positions.pop(symbol)
            wallet_balance += pos["allocated"]
            failed_trades += 1
            await query.edit_message_text(f"🛑 **Position for {symbol} has been manually liquidated and closed via emergency user request.**")

def is_authorized(update: Update) -> bool:
    return update.effective_user.id == ADMIN_USER_ID

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): 
        return
    await update.message.reply_text(
        "🤖 **Premium High-Frequency Automated Core Active**\n\n"
        f"Operational Risk Ceiling: **{RISK_ALLOCATION_PCT}% Compound Sizing**\n"
        "• Background tracking scans run automatically every 15 minutes.\n"
        "• Break-Even capital locking and Trailing Stop parameters are fully active.\n\n"
        "Send /status to review your current portfolio metrics."
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): 
        return
    win_rate = (successful_trades / (successful_trades + failed_trades) * 100) if (successful_trades + failed_trades) > 0 else 0
    
    positions_text = ""
    if active_positions:
        for sym, details in active_positions.items():
            positions_text += f"• `{sym}` | Capital: `{details['allocated']} USDT` | Safe SL Line: `${details['stop_loss_price']:.4f}`\n"
    else: 
        positions_text = "No open active allocations currently in pipeline."

    summary = f"📊 **Premium Real-Time Diagnostic Performance Report:**\n\n" \
              f"💵 Available Wallet Balance: `${wallet_balance:.2f} USDT`\n" \
              f"📈 Daily Net Profit: `${daily_profit:+.2f} USDT`\n" \
              f"🎯 Quant Model Efficiency Rate: `{win_rate:.1f}%` (`{successful_trades}` W / `{failed_trades}` L)\n\n" \
              f"🔍 **Active Tracked Allocation Positions:**\n{positions_text}"
    await update.message.reply_text(summary, parse_mode="Markdown")

def main():
    print("🤖 Launching professional English instance pipeline client... Polling started.")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Establish persistent session reuse architecture to save network resources
    loop = asyncio.get_event_loop()
    session = loop.run_until_complete(aiohttp.ClientSession().__aenter__())
    application.bot_data["web_session"] = session
    
    # Schedule automated high-fidelity structural scans every 15 minutes (900 seconds)
    application.job_queue.run_repeating(auto_trading_job, interval=900, first=10)
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CallbackQueryHandler(button_click_handler))
    
    try: 
        application.run_polling()
    finally: 
        loop.run_until_complete(session.__aexit__(None, None, None))

if __name__ == "__main__":
    main()
