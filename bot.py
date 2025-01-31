import os
import requests
import pandas as pd
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

# Global variables
latest_top_coins = []
is_running = True

# Fetch Solana tokens from the API
def fetch_solana_tokens():
    url = "https://api.dexscreener.com/latest/dex/tokens/solana"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching Solana tokens: {e}")
        return {"pairs": []}

# Filter tokens based on liquidity and volume
def filter_tokens(tokens):
    filtered = []
    for token in tokens.get('pairs', []):
        liquidity = float(token.get('liquidity', {}).get('usd', 0))
        volume = float(token.get('volume', {}).get('h24', 0))
        if liquidity > 10_000 and volume > 5_000:
            filtered.append(token)
    return filtered

# Detect breakout using moving averages
def detect_breakout(prices):
    ma_short = prices['close'].rolling(window=20).mean()
    ma_long = prices['close'].rolling(window=50).mean()
    return ma_short.iloc[-1] > ma_long.iloc[-1]

# Analyze tokens to find top breakout coins
def analyze_tokens(filtered_tokens):
    analyzed = []
    for token in filtered_tokens:
        prices = pd.DataFrame(token.get('priceHistory', []))
        if not prices.empty:
            breakout = detect_breakout(prices)
            analyzed.append({
                'name': token.get('baseToken', {}).get('name', 'Unknown'),
                'symbol': token.get('baseToken', {}).get('symbol', 'UNK'),
                'breakout': breakout
            })
    # Filter only tokens with breakout signals
    analyzed = [coin for coin in analyzed if coin['breakout']]
    return analyzed

# Fetch and store top coins periodically
def fetch_and_store_top_coins():
    global latest_top_coins
    tokens = fetch_solana_tokens()
    filtered_tokens = filter_tokens(tokens)
    top_coins = analyze_tokens(filtered_tokens)[:10]
    latest_top_coins = top_coins
    print(f"Updated top coins at {datetime.now()}")

# Schedule periodic updates
def schedule_updates():
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_and_store_top_coins, 'interval', hours=1)
    scheduler.start()

# /start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands = """
    Available commands:
    /start - Start the bot and see available commands.
    /getcoins - Get the top 10 meme coins on Solana.
    /stop - Stop the bot.
    """
    await update.message.reply_text(f"Welcome to JellySoda! I'll help you find promising meme coins on Solana.\n{commands}")

# /getcoins command handler
async def get_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global latest_top_coins
    if not latest_top_coins:
        await update.message.reply_text("No data available yet. Please try again later.")
        return
    message = "\n".join([f"{i+1}. {coin['name']} ({coin['symbol']})" for i, coin in enumerate(latest_top_coins)])
    await update.message.reply_text(f"Top 10 Meme Coins:\n{message}")

# /stop command handler
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_running
    is_running = False
    await update.message.reply_text("Stopping the bot...")
    await app.stop()

if __name__ == "__main__":
    # Ensure the bot token is set as an environment variable
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")

    # Build the Telegram bot application
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getcoins", get_coins))
    app.add_handler(CommandHandler("stop", stop))

    # Schedule periodic updates
    schedule_updates()

    # Start the bot
    app.run_polling()