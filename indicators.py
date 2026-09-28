from datetime import datetime


def sig(x):
    return float(f"{x:.6g}")


def ema(v, n):
    a = 2 / (n + 1)
    out = [v[0]]
    for x in v[1:]:
        out.append(a * x + (1 - a) * out[-1])
    return out


def rsi(c, n=14):
    if len(c) <= n:
        return None
    g = l = 0.0
    for i in range(1, n + 1):
        d = c[i] - c[i - 1]
        g += max(d, 0)
        l += max(-d, 0)
    g, l = g / n, l / n
    for i in range(n + 1, len(c)):
        d = c[i] - c[i - 1]
        g = (g * (n - 1) + max(d, 0)) / n
        l = (l * (n - 1) + max(-d, 0)) / n
    return 100.0 if l == 0 else 100 - 100 / (1 + g / l)


def atr(cs, n=14):
    tr = [cs[0]["h"] - cs[0]["l"]] + [
        max(cs[i]["h"] - cs[i]["l"], abs(cs[i]["h"] - cs[i - 1]["c"]), abs(cs[i]["l"] - cs[i - 1]["c"]))
        for i in range(1, len(cs))]
    a = sum(tr[:n]) / n
    for x in tr[n:]:
        a = (a * (n - 1) + x) / n
    return a


def macd(c):
    e12, e26 = ema(c, 12), ema(c, 26)
    line = [a - b for a, b in zip(e12, e26)]
    s = ema(line, 9)
    return line[-1], s[-1], line[-1] - s[-1]


def vwap(cs):
    """Session VWAP (UTC day). None when the feed has no volume (most spot FX, synthetics)."""
    if not cs:
        return None
    day = cs[-1]["t"] // 86400
    s = [x for x in cs if x["t"] // 86400 == day]
    vol = sum(x["v"] for x in s)
    if vol <= 0:
        return None
    return sum((x["h"] + x["l"] + x["c"]) / 3 * x["v"] for x in s) / vol


def features(cs, live=None):
    c = [x["c"] for x in cs]
    p = c[-1]
    e50 = ema(c, 50)[-1]
    e200 = ema(c, 200)[-1] if len(c) >= 200 else None
    m, s, h = macd(c)
    tr = "n/a" if e200 is None else ("up" if p > e50 > e200 else "down" if p < e50 < e200 else "mixed")
    f = dict(close=p, ema50=e50, ema200=e200, rsi=rsi(c), macd=m, macd_sig=s, macd_hist=h,
             atr=atr(cs), vwap=vwap(cs + ([live] if live else [])), trend=tr)
    return {k: (sig(v) if isinstance(v, float) else v) for k, v in f.items()}


def slot_stats(cs, tz):
    """History of what happened after the same time-of-day candle (next 30m / next 60m)."""
    key = lambda t: datetime.fromtimestamp(t, tz).strftime("%H:%M")
    k = key(cs[-1]["t"])
    r1, r2 = [], []
    for i in range(len(cs) - 1):
        if key(cs[i]["t"]) != k or cs[i + 1]["t"] - cs[i]["t"] != 1800:
            continue
        r1.append(cs[i + 1]["c"] - cs[i]["c"])
        if i + 2 < len(cs) and cs[i + 2]["t"] - cs[i]["t"] == 3600:
            r2.append(cs[i + 2]["c"] - cs[i]["c"])
    up = lambda r: round(100 * sum(1 for x in r if x > 0) / len(r)) if r else None
    avg = lambda r: sig(sum(r) / len(r)) if r else None
    return {"slot": k, "n": len(r1), "up1": up(r1), "avg1": avg(r1), "n2": len(r2), "up2": up(r2), "avg2": avg(r2)}


def quant(f, slot):
    """Deterministic anchor score so the LLM is never the only judge. Each input votes +1/-1/0."""
    p, v = f["close"], []
    v.append(1 if p > f["ema50"] else -1)
    if f["ema200"] is not None:
        v.append(1 if f["ema50"] > f["ema200"] else -1)
    v.append(1 if f["macd_hist"] > 0 else -1)
    if f["rsi"] is not None:
        v.append(1 if f["rsi"] > 55 else -1 if f["rsi"] < 45 else 0)
    if f["vwap"]:
        v.append(1 if p > f["vwap"] else -1)
    if slot and slot["n"] >= 15 and slot["up1"] is not None:
        v.append(1 if slot["up1"] > 60 else -1 if slot["up1"] < 40 else 0)
    x = sum(v) / len(v)
    return {"buy": round(50 + 50 * x), "sell": round(50 - 50 * x), "inputs": len(v)}
