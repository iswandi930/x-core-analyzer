from fastapi import FastAPI, Header, HTTPException
from typing import Any
import os

app = FastAPI(title="X-Core Analyzer", version="0.1.0")

WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "")


def x_core_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    """Initial analysis shell. No broker/order execution is performed."""
    symbol = payload.get("symbol", "UNKNOWN")
    timeframe = payload.get("timeframe", "UNKNOWN")
    price = payload.get("price")

    return {
        "system": "X-Core",
        "mode": "analysis_only",
        "symbol": symbol,
        "timeframe": timeframe,
        "price": price,
        "direction": "BUY",
        "entry_area": None,
        "correction_reversal_area": None,
        "factors": {
            "liquidity_sweep": None,
            "mss_choch": None,
            "order_block": None,
            "fvg": None,
            "fibonacci_0.5_0.618": None,
        },
        "note": "Signal engine scaffold; no trade execution.",
    }


@app.get("/")
def root():
    return {"name": "X-Core Analyzer", "status": "online", "mode": "analysis_only"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook/tradingview")
def tradingview_webhook(payload: dict[str, Any], x_webhook_token: str | None = Header(default=None)):
    if WEBHOOK_TOKEN and x_webhook_token != WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid webhook token")
    return x_core_analysis(payload)
