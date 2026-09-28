import json, time
import config as cfg

SEC = {"30m": 1800, "1d": 86400}


def fetch(sid, tf="30m", n=None):
    """Deriv public WS (no key): OHLC candles, oldest -> newest, last one may be the forming candle."""
    import websocket  # websocket-client
    n = min(n or cfg.HIST, 5000)
    ws = websocket.create_connection(cfg.DERIV_WS, timeout=30)
    try:
        ws.send(json.dumps({"ticks_history": sid, "adjust_start_time": 1, "count": n, "end": "latest",
                            "granularity": SEC[tf], "style": "candles", "req_id": 1}))
        for _ in range(10):
            d = json.loads(ws.recv())
            if "error" in d:
                raise RuntimeError("deriv: " + str(d["error"].get("message")))
            if "candles" in d:
                break
        else:
            raise RuntimeError("deriv: no candles in reply")
    finally:
        ws.close()
    return [dict(t=int(c["epoch"]), o=float(c["open"]), h=float(c["high"]), l=float(c["low"]),
                 c=float(c["close"])) for c in d["candles"]]


def split(cs, tf="30m"):
    """(closed candles, live forming candle or None)"""
    now, s = time.time(), SEC[tf]
    return [x for x in cs if x["t"] + s <= now], next((x for x in reversed(cs) if x["t"] + s > now), None)
