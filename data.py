import json, re, time
import config as cfg

SEC = {"30m": 1800, "1d": 86400}
FALLBACKS = ["wss://api.derivws.com/trading/v1/options/ws/public",
             "wss://api.derivws.com/trading/V1/options/ws/public",
             "wss://ws.derivws.com/websockets/v3?app_id=1089"]  # legacy public endpoint, last resort
_ok = None  # endpoint that worked (reused for the rest of the run)


def norm(u):
    """https:// -> wss://, http:// -> ws://, add scheme if missing, strip quotes/spaces/trailing slash."""
    u = (u or "").strip().strip("\"'").strip().rstrip("/")
    if not u:
        return ""
    u = re.sub(r"^https://", "wss://", u, flags=re.I)
    u = re.sub(r"^http://", "ws://", u, flags=re.I)
    if not re.match(r"^wss?://", u, re.I):
        u = "wss://" + u.lstrip("/")
    return u


def candidates():
    c = []
    for u in [norm(cfg.DERIV_WS)] + FALLBACKS:
        if u and u not in c:
            c.append(u)
    return ([_ok] if _ok else []) + [u for u in c if u != _ok]


def _ask(url, req):
    import websocket  # pip install websocket-client
    ws = websocket.create_connection(url, timeout=30)  # plain WS upgrade: no auth, OTP or query params
    try:
        ws.send(json.dumps(req))
        for _ in range(10):
            d = json.loads(ws.recv())
            if d.get("req_id") == req["req_id"] or "candles" in d or "error" in d:
                return d
        raise RuntimeError("no reply")
    finally:
        ws.close()


def fetch(sid, tf="30m", n=None):
    """Deriv public market data. Tries configured endpoint, then fallbacks, automatically."""
    global _ok
    req = {"ticks_history": sid, "adjust_start_time": 1, "count": min(n or cfg.HIST, 5000),
           "end": "latest", "granularity": SEC[tf], "style": "candles", "req_id": 1}
    errs = []
    for url in candidates():
        try:
            d = _ask(url, req)
        except Exception as e:
            errs.append(f"{url.split('/')[2]}{url[url.find('/', 8):][:24]}: {str(e)[:70]}")
            continue
        _ok = url
        if d.get("error"):
            raise RuntimeError("deriv: " + str(d["error"].get("message")))
        if not d.get("candles"):
            raise RuntimeError("deriv: no candles for " + sid)
        return [dict(t=int(c["epoch"]), o=float(c["open"]), h=float(c["high"]), l=float(c["low"]),
                     c=float(c["close"])) for c in d["candles"]]
    raise RuntimeError("deriv connect failed: " + " | ".join(errs))


def split(cs, tf="30m"):
    """(closed candles, live forming candle or None)"""
    now, s = time.time(), SEC[tf]
    return [x for x in cs if x["t"] + s <= now], next((x for x in reversed(cs) if x["t"] + s > now), None)
