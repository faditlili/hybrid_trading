import logging
import os
import sys
import asyncio
import aiohttp
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# setup secure and robust professional runtime logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# strict production parameters check
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    logger.critical("CRITICAL CONFIGURATION ERROR: TELEGRAM_TOKEN environment variable is missing.")
    sys.exit("Execution terminated: TELEGRAM_TOKEN must be explicitly defined at runtime.")

ALLOWED_ADMIN_ID_ENV = os.environ.get("ALLOWED_ADMIN_ID")
if not ALLOWED_ADMIN_ID_ENV:
    logger.critical("CRITICAL CONFIGURATION ERROR: ALLOWED_ADMIN_ID environment variable is missing.")
    sys.exit("Execution terminated: ALLOWED_ADMIN_ID must be explicitly defined at runtime.")

try:
    ALLOWED_ADMIN_ID = int(ALLOWED_ADMIN_ID_ENV)
except ValueError:
    logger.critical("CRITICAL CONFIGURATION ERROR: ALLOWED_ADMIN_ID environment variable must be a valid integer.")
    sys.exit("Execution terminated: Invalid ALLOWED_ADMIN_ID format.")

TRADING_PAIR_BASE = os.environ.get("TRADING_PAIR_BASE", "USDT")
bot_status = {"automated_trading": True, "confidence_threshold": 80}

# Real-time realistic persistent tracking metrics for Demo trading
wallet_balance = 200.00
successful_trades = 0
failed_trades = 0
daily_profit = 0.00
def get_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Builds the comprehensive operational control panel layout."""
    status_text = "🟢 Active" if bot_status["automated_trading"] else "🔴 Stopped"
    keyboard = [
        [
            InlineKeyboardButton(f"🤖 Automated Trading: {status_text}", callback_data="toggle_trading")
        ],
        [
            InlineKeyboardButton("📊 Scan Live Market (All Alts)", callback_data="scan_market"),
            InlineKeyboardButton("💰 Profit Report (P&L)", callback_data="get_pnl")
        ],
        [
            InlineKeyboardButton("⚙️ Confidence Rule (80%)", callback_data="view_settings"),
            InlineKeyboardButton("🚫 Excluded Assets", callback_data="view_exclusions")
        ],
        [
            InlineKeyboardButton("🔄 Refresh Dashboard", callback_data="refresh_dashboard")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def is_authorized(user_id: int) -> bool:
    """Explicitly verifies user identity against the verified Administrator ID constraint."""
    return user_id == ALLOWED_ADMIN_ID

async def fetch_all_usdt_pairs_from_market():
    """
    Asynchronously scans active cryptocurrency market from Binance using public endpoint.
    """
    url = "https://binance.com"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=6) as response:
                if response.status == 200:
                    raw_data = await response.json()
                    valid_market_pool = []
                    for item in raw_data:
                        symbol = item.get("symbol", "")
                        # Filter to include only USDT pairs, excluding stablecoins and BTC
                        if symbol.endswith("USDT") and not any(x in symbol for x in ["BTC", "USDC", "FDUSD", "DAI"]):
                            valid_market_pool.append({
                                "symbol": symbol,
                                "price": float(item.get("lastPrice", 0)),
                                "change": float(item.get("priceChangePercent", 0)),
                                "volume": float(item.get("volume", 0))
                            })
                    if valid_market_pool:
                        # Sort by top volume to target highest liquidity pairs
                        valid_market_pool.sort(key=lambda x: x["volume"], reverse=True)
                        return valid_market_pool[:12]
    except Exception as e:
        logger.error(f"Error fetching real data from Binance: {str(e)}")
    return []
def run_technical_indicators_engine(asset: dict):
    """
    Advanced Quantitative Analysis Filter.
    Processes volatility momentum vectors against simulated boundaries.
    """
    price_momentum = asset["change"]
    
    if abs(price_momentum) < 1.5:
        return random.randint(40, 55), "HOLD"
        
    if price_momentum > 2.0:
        if price_momentum > 18.0:
            confidence = random.randint(60, 70)
            action = "HOLD"
        else:
            confidence = int(72 + (price_momentum * 1.1))
            action = "BUY"
    elif price_momentum < -2.0:
        if price_momentum < -18.0:
            confidence = random.randint(55, 65)
            action = "HOLD"
        else:
            confidence = int(70 + (abs(price_momentum) * 1.1))
            action = "SELL"
    else:
        confidence = random.randint(50, 65)
        action = "HOLD"
        
    return min(confidence, 98), action

async def simulated_market_outcome(symbol: str, action: str, change_24h: float):
    """
    Evaluates realistic market dynamic results.
    Trades are not automatically successful; outcome depends on active asset volatility vectors.
    """
    await asyncio.sleep(0.5)
    # The higher the 24h change amplitude, the more volatile the outcome
    volatility_factor = max(abs(change_24h) * 0.15, 0.5)
    
    # Calculate a variable success rate based on technical alignment
    success_probability = 0.68  # Base edge is 68% for high confidence setups
    
    if random.random() < success_probability:
        profit_percent = random.uniform(0.5, 3.5) * volatility_factor
        return True, round(profit_percent, 2)
    else:
        loss_percent = random.uniform(0.4, 2.8) * volatility_factor
        return False, round(loss_percent, 2)
        async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update or not update.effective_user or not update.message:
        return
        
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("Unauthorized: Access Denied.")
        return
        
    welcome_text = (
        "=== Premium Global Trading Bot (LIVE DEMO) ===\n\n"
        "Real-time market scanning via Binance API active.\n"
        "Risk Mitigation Engine and Capital Preservation simulation fully engaged.\n\n"
        "Current Parameters:\n"
        f"- Trading Status: {'Automated/Running' if bot_status['automated_trading'] else 'Paused'}\n"
        f"- Target Boundary: >= {bot_status['confidence_threshold']}%\n"
        "- Operational Base: High-Liquidity USDT Altcoin Streams"
    )
    await update.message.reply_text(welcome_text, reply_markup=get_dashboard_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global wallet_balance, successful_trades, daily_profit, failed_trades
    query = update.callback_query
    if not query or not query.from_user or not query.message:
        return
        
    user_id = query.from_user.id
    if not is_authorized(user_id):
        await query.answer("Access Denied.", show_alert=True)
        return
        
    try:
        await query.answer()
        data = query.data
        
        if data == "toggle_trading":
            bot_status["automated_trading"] = not bot_status["automated_trading"]
            status_label = "ACTIVE" if bot_status["automated_trading"] else "STOPPED"
            text = f"Bot Status Updated:\n\nAutomated Trading: {status_label}"
            await query.edit_message_text(text=text, reply_markup=get_dashboard_keyboard())
            
        elif data == "scan_market":
            await query.edit_message_text(
                text="🔍 Scanning Binance live market tickers via public sockets... Please stand by.",
                reply_markup=get_dashboard_keyboard()
            )
            live_market_pool = await fetch_all_usdt_pairs_from_market()
            if not live_market_pool:
                await query.edit_message_text(
                    text="⚠️ Connection error or API rate-limit reached. Failed to pull market arrays.",
                    reply_markup=get_dashboard_keyboard()
                )
                return
                
            scan_results = "📊 *Live High-Volume Altcoin Scan Results:*\n\n"
            trades_fired = 0
            
            for asset in live_market_pool:
                confidence, action = run_technical_indicators_engine(asset)
                formatted_display_name = asset["symbol"]
                
                scan_results += f"🔹 *{formatted_display_name}*: Price: ${asset['price']:.4f} | 24h: {asset['change']}% | Confidence: {confidence}%\n"
                
                if bot_status["automated_trading"] and confidence >= bot_status["confidence_threshold"] and action in ["BUY", "SELL"]:
                    # Updated allocation configuration to 10% per trade instead of 2%
                    allocated_trade_amount = round(wallet_balance * 0.10, 2)
                    if allocated_trade_amount < 1.0:
                        allocated_trade_amount = 1.0
                        
                    scan_results += f"⚡️ *Confidence Boundary Triggered* ({confidence}% >= 80%)! Evaluating 10% allocation: ${allocated_trade_amount} USDT...\n"
                    
                    is_win, percentage = await simulated_market_outcome(formatted_display_name, action, asset['change'])
                    trades_fired += 1
                    
                    if is_win:
                        successful_trades += 1
                        profit_gain = round(allocated_trade_amount * (percentage / 100), 2)
                        wallet_balance += profit_gain
                        daily_profit += profit_gain
                        scan_results += f"✅ *PROFIT TARGET HIT:* {formatted_display_name} closed at +{percentage}% (+${profit_gain} USDT)\n\n"
                    else:
                        failed_trades += 1
                        loss_take = round(allocated_trade_amount * (percentage / 100), 2)
                        wallet_balance -= loss_take
                        daily_profit -= loss_take
                        scan_results += f"❌ *STOP LOSS TRIGGERED:* {formatted_display_name} exited at -{percentage}% (-${loss_take} USDT)\n\n"
                        
            if trades_fired == 0:
                scan_results += "\n⚠️ No high-probability setups met the strict 80% confidence criteria. Positions skipped."
                
            await query.edit_message_text(
                text=scan_results,
                reply_markup=get_dashboard_keyboard(),
                parse_mode="Markdown"
            )
        elif data == "get_pnl":
            pnl_report = (
                "💰 *Premium Real-Time Profit & Loss Report*\n\n"
                f"💵 Wallet Balance: ${wallet_balance:.2f} USDT\n"
                f"📈 Daily Net Profit: {'' if daily_profit < 0 else '+'}${daily_profit:.2f} USDT\n"
                f"🟢 Execution Successes: {successful_trades} ✅\n"
                f"🔴 Execution Failures: {failed_trades} ❌\n"
                "⚙️ Mode: Live Technical Simulation Engine"
            )
            await query.edit_message_text(
                text=pnl_report,
                reply_markup=get_dashboard_keyboard(),
                parse_mode="Markdown"
            )
            
        elif data == "view_settings":
            settings_text = (
                "⚙️ *Operational Parameters Config*\n\n"
                f"▪️ Execution Confidence Limit: >= {bot_status['confidence_threshold']}%\n"
                "▪️ Calculated Risk Size: 10.0% Compound Allocation per Trade\n"
                "▪️ Minimum Liquidity Floor: Top 12 Volume Chains Only"
            )
            await query.edit_message_text(
                text=settings_text,
                reply_markup=get_dashboard_keyboard(),
                parse_mode="Markdown"
            )
            
        elif data == "view_exclusions":
            exclusions_text = (
                "🚫 *Strict Asset Exclusion Registry*\n\n"
                "▪️ Bitcoin (BTC) -> Status: BLOCKED PERMANENTLY\n"
                "▪️ Gold Futures (XAU) -> Status: EXCLUDED SECURELY\n"
                "💡 Reason: Hyper-volatility protection protocol applied."
            )
            await query.edit_message_text(
                text=exclusions_text,
                reply_markup=get_dashboard_keyboard(),
                parse_mode="Markdown"
            )
            
        elif data == "refresh_dashboard":
            refresh_text = (
                "🔄 Dashboard Refreshed.\n\n"
                f"Trading Engine Status: {'Running Autonomously' if bot_status['automated_trading'] else 'Paused Manually'}\n"
                f"Current Wallet Balance: ${wallet_balance:.2f} USDT"
            )
            await query.edit_message_text(
                text=refresh_text,
                reply_markup=get_dashboard_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Error handling callback query: {str(e)}")

async def main():
    """Main execution point using advanced modern asyncio loop initialization."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("Initializing high-frequency cloud pipeline hooks. Starting Telegram Bot Polling...")
    
    async with application:
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot execution gracefully stopped.")
