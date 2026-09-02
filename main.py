import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NIFTY_50_TICKERS = [
    "HEROMOTOCO.NS",
    "BAJAJ-AUTO.NS",
    "TITAN.NS",
    "SHRIRAMFIN.NS",
    "BAJAJFINSV.NS",
    "HCLTECH.NS",
    "M&M.NS",
    "GRASIM.NS",
    "BAJFINANCE.NS",
    "HINDALCO.NS",
    "EICHERMOT.NS",
    "TECHM.NS",
    "KOTAKBANK.NS",
    "LT.NS",
    "JSWSTEEL.NS",
    "NESTLEIND.NS",
    "BHARTIARTL.NS",
    "ICICIBANK.NS",
    "RELIANCE.NS",
    "SBIN.NS",
]


def calculate_rsi(series, window=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


@app.get("/api/screen")
def screen_market():
    # 1. Fetch Nifty Index Data
    try:
        nifty = yf.Ticker("^NSEI").history(period="1y")
        if nifty.empty:
            raise ValueError("No data returned for ^NSEI")

        close_s = nifty["Close"]
        dma50_s = close_s.rolling(50).mean()
        dma200_s = close_s.rolling(200).mean()
        rsi_s = calculate_rsi(close_s)

        nifty_last = float(close_s.iloc[-1])
        nifty_50dma = float(dma50_s.iloc[-1])
        nifty_200dma = float(dma200_s.iloc[-1])
        nifty_rsi = float(rsi_s.iloc[-1])

        regime = "CASH / STANDBY"
        if nifty_last > nifty_50dma and nifty_rsi > 50:
            regime = (
                "AGGRESSIVE BUYING"
                if nifty_last > nifty_200dma
                else "CAUTION (SMALL POSITIONS)"
            )
        elif nifty_last < nifty_200dma and nifty_rsi < 50:
            regime = "CASH / STANDBY"

        market_summary = {
            "price": round(nifty_last, 2),
            "dma50": round(nifty_50dma, 2),
            "dma200": round(nifty_200dma, 2),
            "rsi": round(nifty_rsi, 2),
            "regime": regime,
        }
    except Exception as e:
        market_summary = {
            "price": 0.0,
            "dma50": 0.0,
            "dma200": 0.0,
            "rsi": 0.0,
            "regime": "Data Error: " + str(e),
        }

    # 2. Process Watchlist Tickers
    stock_results = []

    for ticker in NIFTY_50_TICKERS:
        try:
            df = yf.Ticker(ticker).history(period="1y")
            if df.empty or len(df) < 200:
                continue

            close_series = df["Close"]
            df["20_DMA"] = close_series.rolling(20).mean()
            df["50_DMA"] = close_series.rolling(50).mean()
            df["200_DMA"] = close_series.rolling(200).mean()
            df["RSI"] = calculate_rsi(close_series)
            df["Vol_10MA"] = df["Volume"].rolling(10).mean()

            last = df.iloc[-1]
            prev = df.iloc[-2]

            c = float(last["Close"])
            d20 = float(last["20_DMA"])
            d50 = float(last["50_DMA"])
            d200 = float(last["200_DMA"])
            rsi_val = float(last["RSI"])
            pct_50 = float(((c - d50) / d50) * 100)

            # Technical Conditions Check
            trend_pass = bool(c > d20 and c > d50 and c > d200 and d50 > d200)
            rsi_pass = bool(55.0 <= rsi_val <= 70.0)
            not_extended = bool(pct_50 <= 10.0)

            eligible = bool(trend_pass and rsi_pass and not_extended)

            # Pattern Recognition
            pattern = "None"
            near_ma = bool(
                abs(c - d20) / d20 <= 0.025 or abs(c - d50) / d50 <= 0.025
            )
            bullish_candle = bool(c > float(last["Open"]) and c > float(prev["High"]))
            vol_confirm = bool(float(last["Volume"]) > float(last["Vol_10MA"]))

            if near_ma and bullish_candle and vol_confirm and c > d50:
                pattern = "Pattern A (Pullback Reversal)"

            range_high = float(df["High"].iloc[-21:-1].max())
            if c > range_high and float(last["Volume"]) >= 1.5 * float(last["Vol_10MA"]):
                pattern = "Pattern B (Volume Breakout)"

            symbol_clean = str(ticker.replace(".NS", ""))

            stock_results.append({
                "symbol": symbol_clean,
                "price": round(c, 2),
                "dma20": round(d20, 2),
                "dma50": round(d50, 2),
                "dma200": round(d200, 2),
                "rsi": round(rsi_val, 2),
                "pct_50dma": round(pct_50, 2),
                "eligible": eligible,
                "pattern": pattern,
            })
        except Exception:
            continue

    return {"market": market_summary, "stocks": stock_results}