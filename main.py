from fastapi import FastAPI, Header, HTTPException
from typing import Any
import os

app = FastAPI(title="X-Core Analyzer", version="0.2.0")

WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "")


def x_core_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    """Analysis-only webhook receiver. No broker/order execution."""
    symbol = payload.get("symbol", "UNKNOWN")
    timeframe = payload.get("timeframe", "UNKNOWN")
    price = payload.get("price")

    # For now we only validate/forward incoming TradingView data.
    # The real X-Core decision engine will be added after the webhook path is verified.
    return {
        "system": "X-Core",
        "mode": "analysis_only",
        "status": "received",
        "symbol": symbol,
        "timeframe": timeframe,
        "price": price,
        "direction": None,
        "entry_area": None,
        "correction_reversal_area": None,
        "factors": {
            "liquidity_sweep": payload.get("liquidity_sweep"),
            "mss_choch": payload.get("mss_choch"),
            "order_block": payload.get("order_block"),
            "fvg": payload.get("fvg"),
            "fibonacci_0.5_0.618": payload.get("fibonacci_0.5_0.618"),
        },
        "note": "Webhook received. X-Core does not execute trades.",
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
