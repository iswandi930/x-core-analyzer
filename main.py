from fastapi import FastAPI, Header, HTTPException
from typing import Any
import os

app = FastAPI(title="X-Core Analyzer", version="1.0.0")
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _candles(payload):
    rows = payload.get("candles") or payload.get("ohlc") or []
    out = []
    for r in rows:
        if isinstance(r, dict):
            o, h, l, c = map(_num, (r.get("open"), r.get("high"), r.get("low"), r.get("close")))
            if None not in (o, h, l, c): out.append({"open":o,"high":h,"low":l,"close":c})
    return out


def analyze(c):
    if len(c) < 8:
        return {"status":"insufficient_data","reason":"Need at least 8 OHLC candles"}
    last = c[-1]; prev = c[:-1]
    recent_high = max(x["high"] for x in prev[-5:])
    recent_low = min(x["low"] for x in prev[-5:])
    sweep_up = last["high"] > recent_high and last["close"] < recent_high
    sweep_down = last["low"] < recent_low and last["close"] > recent_low
    prior_high = max(x["high"] for x in c[-7:-2])
    prior_low = min(x["low"] for x in c[-7:-2])
    mss_bull = last["close"] > prior_high
    mss_bear = last["close"] < prior_low
    bullish_ob = next((x for x in reversed(c[:-1]) if x["close"] < x["open"]), None)
    bearish_ob = next((x for x in reversed(c[:-1]) if x["close"] > x["open"]), None)
    fvg_bull = c[-1]["low"] > c[-3]["high"]
    fvg_bear = c[-1]["high"] < c[-3]["low"]
    swing_hi = max(x["high"] for x in c[-10:]); swing_lo = min(x["low"] for x in c[-10:])
    fib50 = swing_lo + (swing_hi-swing_lo)*0.5
    fib618 = swing_lo + (swing_hi-swing_lo)*0.618
    bull = int(sweep_down)+int(mss_bull)+int(fvg_bull)+int(last["close"] >= fib50)
    bear = int(sweep_up)+int(mss_bear)+int(fvg_bear)+int(last["close"] <= fib618)
    direction = "BUY" if bull >= bear else "SELL"
    return {
        "status":"analyzed", "direction":direction,
        "scores":{"bullish":bull,"bearish":bear},
        "factors":{
            "liquidity_sweep":"bullish" if sweep_down else "bearish" if sweep_up else "none",
            "mss_choch":"bullish" if mss_bull else "bearish" if mss_bear else "none",
            "order_block":"bullish" if bullish_ob and direction=="BUY" else "bearish" if bearish_ob else "none",
            "fvg":"bullish" if fvg_bull else "bearish" if fvg_bear else "none",
            "fibonacci_0.5_0.618":{"fib50":fib50,"fib618":fib618,"price":last["close"]}
        },
        "entry_area": [fib50, fib618],
        "correction_reversal_area": [swing_lo, swing_hi]
    }


def x_core_analysis(payload: dict[str, Any]):
    result = analyze(_candles(payload))
    return {"system":"X-Core","mode":"analysis_only","symbol":payload.get("symbol","UNKNOWN"),"timeframe":payload.get("timeframe","UNKNOWN"),"price":_num(payload.get("price")),**result}


@app.get("/")
def root(): return {"name":"X-Core Analyzer","status":"online","mode":"analysis_only","version":"1.0.0"}

@app.get("/health")
def health(): return {"status":"ok","version":"1.0.0"}

@app.post("/webhook/tradingview")
def tradingview_webhook(payload: dict[str, Any], x_webhook_token: str | None = Header(default=None)):
    if WEBHOOK_TOKEN and x_webhook_token != WEBHOOK_TOKEN: raise HTTPException(status_code=401, detail="Invalid webhook token")
    return x_core_analysis(payload)
