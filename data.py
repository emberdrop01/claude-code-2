import json, time, requests
import config as cfg

SEC = {"30m": 1800, "1d": 86400}
UA = {"User-Agent": "Mozilla/5.0"}


def _yahoo(sid, tf, n):
    rng = "60d" if tf == "30m" else "2y"
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sid}",
                     params={"interval": tf, "range": rng}, headers=UA, timeout=25)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    out = []
    for i, t in enumerate(res.get("timestamp") or []):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        out.append(dict(t=int(t), o=o, h=h, l=l, c=c, v=q["volume"][i] or 0))
    return out[-n:]


def _deriv(sid, tf, n):
    import websocket  # pip install websocket-client
    ws = websocket.create_connection(cfg.DERIV_WS, timeout=25)
    try:
        ws.send(json.dumps({"ticks_history": sid, "adjust_start_time": 1, "count": min(n, 5000),
                            "end": "latest", "granularity": SEC[tf], "style": "candles"}))
        d = json.loads(ws.recv())
    finally:
        ws.close()
    if "error" in d:
        raise RuntimeError("deriv: " + str(d["error"].get("message")))
    return [dict(t=int(c["epoch"]), o=float(c["open"]), h=float(c["high"]), l=float(c["low"]),
                 c=float(c["close"]), v=0) for c in d["candles"]]


def fetch(src, sid, tf="30m", n=None):
    n = n or cfg.HIST
    if src == "deriv":
        if not cfg.DERIV_WS:
            raise RuntimeError("DERIV_WS blank")
        return _deriv(sid, tf, n)
    if src == "yahoo":
        return _yahoo(sid, tf, n)
    raise RuntimeError("unknown source " + src)


def split(cs, tf="30m"):
    """(closed candles, live forming candle or None)"""
    now, s = time.time(), SEC[tf]
    closed = [x for x in cs if x["t"] + s <= now]
    live = [x for x in cs if x["t"] + s > now]
    return closed, (live[-1] if live else None)
