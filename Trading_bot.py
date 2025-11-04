"""
Secure EMA + RSI Multi-Timeframe Trading Bot (Signal Mode)
Broker: XM MT5 (Forex + Commodities)
Author: Mazhar Ali
"""

# ================= Imports =================
import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime
import logging
import pytz
from telebot import TeleBot
import threading
from dotenv import load_dotenv
import os
from telebot import TeleBot
import MetaTrader5 as mt5
import time

print("✅ Trading Bot started successfully... waiting for signals.")

# ================= Load Env =================
load_dotenv()

MT5_SERVER = os.getenv("MT5_SERVER")
MT5_ACCOUNT = int(os.getenv("MT5_ACCOUNT"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TRADE_START = os.getenv("TRADE_START", "09:00")
TRADE_END = os.getenv("TRADE_END", "17:00")
LOT_SIZE = float(os.getenv("LOT_SIZE", 0.01))
AUTO_TRADE = os.getenv("AUTO_TRADE", "False").lower() == "true"

TIMEZ = pytz.timezone("Asia/Karachi")

# ================= Logging =================
logging.basicConfig(
    filename="trading_bot.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ================= Setup =================
def connect_mt5():
    if not mt5.initialize(server=MT5_SERVER, login=MT5_ACCOUNT, password=MT5_PASSWORD):
        logger.error(f"MT5 connection failed: {mt5.last_error()}")
        return False
    logger.info("Connected to MetaTrader 5.")
    return True

def send_telegram(msg):
    try:
        bot = TeleBot(TELEGRAM_BOT_TOKEN)
        bot.send_message(TELEGRAM_CHAT_ID, msg)
    except Exception as e:
        logger.error(f"Telegram send error: {e}")

# ================= Indicators =================
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# ================= Market Data =================
def get_candles(symbol, seconds, count=200):
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, count)
    if rates is None:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.set_index("time")
    df = df["close"].resample(f"{seconds}s").ohlc().dropna()
    df["ema10"] = ema(df["close"], 10)
    df["ema20"] = ema(df["close"], 20)
    df["rsi"] = rsi(df["close"])
    return df

# ================= Confirmation Logic =================
def confirm_signal(symbol, direction):
    timeframes = [15, 30, 60]  # seconds
    confirms = 0
    for tf in timeframes:
        df = get_candles(symbol, tf)
        if df is None or len(df) < 20:
            continue
        last = df.iloc[-1]
        trend_up = last["ema10"] > last["ema20"] and last["rsi"] > 55
        trend_dn = last["ema10"] < last["ema20"] and last["rsi"] < 45
        if direction == "BUY" and trend_up:
            confirms += 1
        if direction == "SELL" and trend_dn:
            confirms += 1
    return confirms >= 2

# ================= Trade Placeholder =================
def execute_trade(symbol, direction, lot):
    """Demo mode only. Enable later for live trading."""
    # Uncomment below lines when ready to trade
    # if not AUTO_TRADE:
    #     return {"success": False, "msg": "Auto trading disabled."}
    #
    # order_type = mt5.ORDER_BUY if direction == "BUY" else mt5.ORDER_SELL
    # tick = mt5.symbol_info_tick(symbol)
    # price = tick.ask if direction == "BUY" else tick.bid
    #
    # request = {
    #     "action": mt5.TRADE_ACTION_DEAL,
    #     "symbol": symbol,
    #     "volume": lot,
    #     "type": order_type,
    #     "price": price,
    #     "deviation": 20,
    #     "magic": 987654,
    #     "comment": "SecureBot",
    #     "type_time": mt5.ORDER_TIME_GTC,
    #     "type_filling": mt5.ORDER_FILLING_IOC,
    # }
    # result = mt5.order_send(request)
    # if result.retcode == mt5.TRADE_RETCODE_DONE:
    #     return {"success": True, "msg": f"{direction} executed on {symbol}"}
    # else:
    #     return {"success": False, "msg": f"Trade failed: {result.comment}"}
    return {"success": False, "msg": "Simulated trade (AUTO_TRADE=False)"}

# ================= Logic =================
def in_trading_window():
    now = datetime.now(TIMEZ).time()
    start = datetime.strptime(TRADE_START, "%H:%M").time()
    end = datetime.strptime(TRADE_END, "%H:%M").time()
    return start <= now <= end

def scan_symbol(symbol):
    try:
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return
        price = tick.bid
        direction = "BUY" if price % 2 > 1 else "SELL"
        if confirm_signal(symbol, direction):
            msg = f"✅ {direction} CONFIRMED on {symbol}\nTime: {datetime.now(TIMEZ).strftime('%H:%M:%S')}"
            logger.info(msg)
            send_telegram(msg)
            if AUTO_TRADE:
                res = execute_trade(symbol, direction, LOT_SIZE)
                send_telegram(f"⚙️ Trade Result: {res['msg']}")
    except Exception as e:
        logger.error(f"Scan error {symbol}: {e}")

def main_loop():
    if not connect_mt5():
        return
    all_symbols = [s.name for s in mt5.symbols_get()]
    logger.info(f"Scanning {len(all_symbols)} symbols...")
    send_telegram("🚀 Secure Trading Bot Started (Signal Mode)")
    while True:
        if in_trading_window():
            threads = []
            for sym in all_symbols:
                t = threading.Thread(target=scan_symbol, args=(sym,))
                t.start()
                threads.append(t)
            for t in threads:
                t.join()
        else:
            logger.info("Outside trading hours, sleeping...")
        time.sleep(60)

if __name__ == "__main__":
    main_loop()
