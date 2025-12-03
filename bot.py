#!/usr/bin/env python3

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from decimal import Decimal
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException

load_dotenv()

apikey = os.getenv("API_KEY")
apisecret = os.getenv("API_SECRET")

if not apikey or not apisecret:
    print("API keys missing")
    sys.exit(1)

log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)

console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(message)s"))
log.addHandler(console)

file = RotatingFileHandler("bot.log", maxBytes=2000000, backupCount=3)
file.setLevel(logging.DEBUG)
file.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
log.addHandler(file)

class Bot:
    def __init__(self, key, secret, testnet=True):
        self.client = Client(key, secret, testnet=testnet)
        if testnet:
            self.client.FUTURES_URL = "https://testnet.binancefuture.com/fapi"
        try:
            self.info = self.client.futures_exchange_info()
        except Exception as e:
            log.error(e)
            self.info = {}

    def filters(self, symbol):
        for s in self.info.get("symbols", []):
            if s["symbol"] == symbol.upper():
                return {f["filterType"]: f for f in s["filters"]}
        return None

    def qtyfix(self, symbol, qty):
        f = self.filters(symbol)
        if not f:
            return qty
        step = Decimal(f["LOT_SIZE"]["stepSize"])
        return (qty // step) * step

    def mincheck(self, symbol, price, qty):
        f = self.filters(symbol)
        if not f:
            return True
        mn = Decimal(f.get("MIN_NOTIONAL", {"minNotional": "0"})["minNotional"])
        return price * qty >= mn

    def market(self, symbol, side, qty):
        try:
            r = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=str(qty)
            )
            log.info("Market Order OK | OrderId %s", r.get("orderId"))
            return r
        except (BinanceAPIException, BinanceRequestException) as e:
            log.error(e)
            raise

    def limit(self, symbol, side, qty, price):
        if not self.mincheck(symbol, price, qty):
            raise ValueError("minNotional failed")
        qty = self.qtyfix(symbol, qty)
        if qty <= 0:
            raise ValueError("qty zero")
        try:
            r = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="LIMIT",
                timeInForce="GTC",
                quantity=str(qty),
                price=str(price)
            )
            log.info("Limit Order OK | OrderId %s", r.get("orderId"))
            return r
        except (BinanceAPIException, BinanceRequestException) as e:
            log.error(e)
            raise

    def stoplimit(self, symbol, side, qty, stop, price):
        qty = self.qtyfix(symbol, qty)
        if qty <= 0:
            raise ValueError("qty zero")
        try:
            r = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="STOP",
                quantity=str(qty),
                stopPrice=str(stop),
                price=str(price),
                timeInForce="GTC"
            )
            log.info("Stop-Limit OK | OrderId %s", r.get("orderId"))
            return r
        except (BinanceAPIException, BinanceRequestException) as e:
            log.error(e)
            raise

    def balances(self):
        return self.client.futures_account().get("assets", [])

    def showbalances(self):
        bal = self.balances()
        print("\nUSDT-M FUTURES BALANCE")
        print("-" * 30)
        for b in bal:
            if float(b.get("walletBalance", 0)) > 0:
                print(b["asset"], b["walletBalance"])
        print()

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def box(title):
    print("╔" + "═"*38 + "╗")
    print("║" + title.center(38) + "║")
    print("╚" + "═"*38 + "╝")

def menu():
    box("BINANCE FUTURES TESTNET BOT")
    print(" 1) Market Order")
    print(" 2) Limit Order")
    print(" 3) Stop-Limit Order")
    print(" 4) View Balance")
    print(" 5) Exit")

def getsymbol():
    return input("Symbol (BTCUSDT): ").upper()

def getside():
    while True:
        s = input("Side BUY/SELL: ").upper()
        if s in ("BUY", "SELL"):
            return s

def getnum(t):
    while True:
        try:
            v = Decimal(input(t))
            if v > 0:
                return v
        except:
            print("Invalid number")

def main():
    bot = Bot(apikey, apisecret, True)
    while True:
        clear()
        menu()
        c = input("Choose: ")
        try:
            if c == "1":
                bot.market(getsymbol(), getside(), getnum("Qty: "))
            elif c == "2":
                bot.limit(getsymbol(), getside(), getnum("Qty: "), getnum("Price: "))
            elif c == "3":
                s = getsymbol()
                side = getside()
                q = getnum("Qty: ")
                st = getnum("Stop Price: ")
                p = getnum("Limit Price: ")
                bot.stoplimit(s, side, q, st, p)
            elif c == "4":
                bot.showbalances()
            elif c == "5":
                break
        except Exception as e:
            print("Error:", e)
        input("\nPress Enter...")

if __name__ == "__main__":
    main()
