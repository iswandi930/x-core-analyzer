from __future__ import annotations
from typing import Any
import os, math
from fastapi import FastAPI, Header, HTTPException

APP_VERSION = "2.0.0"
app = FastAPI(title="X-Core Analyzer", version=APP_VERSION)
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "")
PRIMARY_TF = ["D1", "H4", "H1"]
TIMING_TF = ["M30", "M15", "M5", "M1"]
SUPPORTED_TF = PRIMARY_TF + TIMING_TF

def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None

def normalize_candles(rows):
    out = []
    for r in rows or []:
        if not isinstance(r, dict): continue
        o,h,l,c = (num(r.get(k)) for k in ("open","high","low","close"))
        if None not in (o,h,l,c) and h >= max(o,c) and l <= min(o,c):
            out.append({"open":o,"high":h,"low":l,"close":c,"time":r.get("time")})
    return out

def get_tf_candles(payload, tf=None):
    if tf:
        mapping = payload.get("timeframes") or {}
        if isinstance(mapping, dict) and tf in mapping:
            data = mapping[tf]
            if isinstance(data, dict): data = data.get("candles") or data.get("ohlc") or []
            return normalize_candles(data)
    return normalize_candles(payload.get("candles") or payload.get("ohlc") or [])

def pivots(c, left=2, right=2):
    highs,lows=[],[]
    for i in range(left,len(c)-right):
        if c[i]["high"] > max(x["high"] for x in c[i-left:i]) and c[i]["high"] >= max(x["high"] for x in c[i+1:i+right+1]): highs.append(i)
        if c[i]["low"] < min(x["low"] for x in c[i-left:i]) and c[i]["low"] <= min(x["low"] for x in c[i+1:i+right+1]): lows.append(i)
    return highs,lows

def liquidity_sweep(c):
    if len(c)<7: return "none",None
    highs,lows=pivots(c); last=c[-1]
    if highs:
        level=c[highs[-1]]["high"]
        if last["high"]>level and last["close"]<level: return "bearish",level
    if lows:
        level=c[lows[-1]]["low"]
        if last["low"]<level and last["close"]>level: return "bullish",level
    return "none",None

def mss_choch(c):
    if len(c)<8: return "none",None
    highs,lows=pivots(c); last=c[-1]
    rh=[c[i]["high"] for i in highs if i<len(c)-2]
    rl=[c[i]["low"] for i in lows if i<len(c)-2]
    if rh and last["close"]>rh[-1]: return "bullish",rh[-1]
    if rl and last["close"]<rl[-1]: return "bearish",rl[-1]
    return "none",None

def displacement(a,b):
    return abs(b["close"]-b["open"]) > max(a["high"]-a["low"],1e-12)*0.35

def order_block(c):
    if len(c)<5: return "none",None
    for i in range(len(c)-2,max(1,len(c)-15),-1):
        cur,nxt=c[i],c[i+1]
        if cur["close"]<cur["open"] and nxt["close"]>cur["high"] and displacement(cur,nxt): return "bullish",[cur["low"],cur["high"]]
        if cur["close"]>cur["open"] and nxt["close"]<cur["low"] and displacement(cur,nxt): return "bearish",[cur["low"],cur["high"]]
    return "none",None

def fair_value_gap(c):
    if len(c)<3: return "none",None
    a,b=c[-3],c[-1]
    if b["low"]>a["high"]: return "bullish",[a["high"],b["low"]]
    if b["high"]<a["low"]: return "bearish",[b["high"],a["low"]]
    return "none",None

def fibonacci(c):
    if len(c)<8: return {"direction":"none","fib50":None,"fib618":None,"zone":None}
    highs,lows=pivots(c)
    if highs and lows:
        hi_i,lo_i=highs[-1],lows[-1]; hi,lo=c[hi_i]["high"],c[lo_i]["low"]
        direction="bullish" if lo_i<hi_i else "bearish"
    else:
        hi=max(x["high"] for x in c[-20:]); lo=min(x["low"] for x in c[-20:])
        direction="bullish" if c[-1]["close"] >= (hi+lo)/2 else "bearish"
    span=hi-lo
    if span<=0: return {"direction":"none","fib50":None,"fib618":None,"zone":None}
    if direction=="bullish":
        fib50=hi-span*.5; fib618=hi-span*.618
    else:
        fib50=lo+span*.5; fib618=lo+span*.618
    return {"direction":direction,"fib50":fib50,"fib618":fib618,"zone":[min(fib50,fib618),max(fib50,fib618)],"swing_high":hi,"swing_low":lo}

def analyze(c):
    if len(c)<20: return {"status":"insufficient_data","reason":"Need at least 20 valid OHLC candles","candles":len(c)}
    sweep,sl=liquidity_sweep(c); mss,ml=mss_choch(c); ob,oz=order_block(c); fvg,fz=fair_value_gap(c); fib=fibonacci(c)
    bull=(2 if sweep=="bullish" else 0)+(2 if mss=="bullish" else 0)+(1.5 if ob=="bullish" else 0)+(1.5 if fvg=="bullish" else 0)
    bear=(2 if sweep=="bearish" else 0)+(2 if mss=="bearish" else 0)+(1.5 if ob=="bearish" else 0)+(1.5 if fvg=="bearish" else 0)
    price=c[-1]["close"]
    if fib["zone"] and fib["zone"][0]<=price<=fib["zone"][1]:
        if fib["direction"]=="bullish": bull+=1
        elif fib["direction"]=="bearish": bear+=1
    if bull>bear: direction="BUY"
    elif bear>bull: direction="SELL"
    elif mss=="bullish": direction="BUY"
    elif mss=="bearish": direction="SELL"
    else: direction="BUY" if price>=sum(x["close"] for x in c[-5:])/5 else "SELL"
    confidence=round(min(.99,max(.50,.50+abs(bull-bear)/12)),2)
    return {"status":"analyzed","direction":direction,"confidence":confidence,"scores":{"bullish":bull,"bearish":bear},
            "factors":{"liquidity_sweep":{"direction":sweep,"level":sl},"mss_choch":{"direction":mss,"level":ml},
            "order_block":{"direction":ob,"zone":oz},"fvg":{"direction":fvg,"zone":fz},"fibonacci_0.5_0.618":fib},
            "price":price,"entry_area":fib.get("zone") or oz or fz,
            "correction_reversal_area":[fib.get("swing_low"),fib.get("swing_high")]}

def x_core_analysis(payload):
    mapping=payload.get("timeframes")
    if isinstance(mapping,dict) and mapping:
        analyses={}
        for tf in SUPPORTED_TF:
            candles=get_tf_candles(payload,tf)
            if candles: analyses[tf]=analyze(candles)
        primary={tf:analyses[tf] for tf in PRIMARY_TF if tf in analyses and analyses[tf].get("status")=="analyzed"}
        timing={tf:analyses[tf] for tf in TIMING_TF if tf in analyses and analyses[tf].get("status")=="analyzed"}
        pb=sum(v["scores"]["bullish"] for v in primary.values()); ps=sum(v["scores"]["bearish"] for v in primary.values())
        tb=sum(v["scores"]["bullish"] for v in timing.values()); ts=sum(v["scores"]["bearish"] for v in timing.values())
        direction="BUY" if pb>ps else "SELL" if ps>pb else ("BUY" if tb>ts else "SELL")
        return {"system":"X-Core","mode":"analysis_only","symbol":payload.get("symbol","UNKNOWN"),"price":num(payload.get("price")),
                "direction":direction,"swing_timeframes":PRIMARY_TF,"timing_timeframes":TIMING_TF,
                "primary":primary,"timing":timing,"status":"analyzed" if primary else "insufficient_data"}
    result=analyze(get_tf_candles(payload))
    return {"system":"X-Core","mode":"analysis_only","symbol":payload.get("symbol","UNKNOWN"),"timeframe":payload.get("timeframe","UNKNOWN"),"price":num(payload.get("price")),**result}

@app.get("/")
def root(): return {"name":"X-Core Analyzer","status":"online","mode":"analysis_only","version":APP_VERSION}

@app.get("/health")
def health(): return {"status":"ok","engine":"x-core","version":APP_VERSION,"mode":"analysis_only"}

@app.post("/webhook/tradingview")
def tradingview_webhook(payload:dict[str,Any], x_webhook_token:str|None=Header(default=None)):
    if WEBHOOK_TOKEN and x_webhook_token!=WEBHOOK_TOKEN: raise HTTPException(status_code=401,detail="Invalid webhook token")
    return x_core_analysis(payload)
