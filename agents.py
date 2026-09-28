import json, time
from datetime import datetime
import config as cfg
import data, journal, llm, indicators as ind

CACHE = {}  # symbol name -> all 30m candles (shared with news reaction study)

BASE = ("You are one member of a trading desk with a shared BOARD (messages from teammates). "
        "Use ONLY numbers in DATA. Never invent prices, news, levels or statistics. If evidence is missing, "
        "thin (small n) or contradictory, say so and lean WAIT. Reply with ONE JSON object, no prose. ")
PROMPT = {
    "research": "ROLE=research. " + BASE + "Read trend, news, time-of-day stats, track record. "
                'JSON: {"bias":"BUY|SELL|WAIT","conf":0-100,"notes":"<=200 chars","msg":"<=150 chars to team"}',
    "analyst": "ROLE=analyst. " + BASE + "Quant read of EMA50/200, RSI, MACD, VWAP, ATR and the quant score; "
               "confirm or challenge research. Pick stop/target in ATR multiples. "
               'JSON: {"bias":"BUY|SELL|WAIT","conf":0-100,"sl_atr":1-3,"tp_atr":1-5,"notes":"<=200 chars","msg":"<=150 chars"}',
    "red": "ROLE=red. " + BASE + "Red team: try to break the trade. Look for contradictions, exhaustion "
           "(RSI extremes), news risk, tiny samples, past errors in track record. "
           'JSON: {"veto":true|false,"risk":0-100,"notes":"<=200 chars","msg":"<=150 chars"}',
    "audit": "ROLE=audit. " + BASE + "Audit: check every number/claim in BOARD against DATA. Fail on any mismatch "
             "or unsupported claim. "
             'JSON: {"pass":true|false,"issues":["..."],"msg":"<=150 chars"}',
    "manager": "ROLE=manager. " + BASE + "Manager: final call after reading the whole BOARD. If the team is split, "
               "audit failed, or you are unsure, set skip=true and action WAIT. "
               'JSON: {"action":"BUY|SELL|WAIT","score":0-100,"conf":0-100,"sl_atr":1-3,"tp_atr":1-5,'
               '"skip":true|false,"reason":"<=200 chars"}',
}


def num(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def clamp(x, a, b):
    return max(a, min(b, x))


def decide(pack, q, atr, price):
    board, out = [], {}
    for role in ("research", "analyst", "red", "audit", "manager"):
        out[role] = llm.chat(PROMPT[role], json.dumps({"DATA": pack, "BOARD": board}, separators=(",", ":")))
        board.append({"from": role, "said": out[role]})
    m, an = out["manager"], out["analyst"]
    cand = str(m.get("action", "WAIT")).upper()
    cand = cand if cand in ("BUY", "SELL") else "WAIT"
    qs = q["buy"] if cand == "BUY" else q["sell"] if cand == "SELL" else 50
    conf = int(clamp(num(m.get("conf")), 0, 100))
    score = round(0.6 * clamp(num(m.get("score")), 0, 100) + 0.4 * qs)
    why = []
    if cand == "WAIT":
        why.append("manager: wait")
    if m.get("skip"):
        why.append("manager unsure")
    if not out["audit"].get("pass", False):
        why.append("audit failed")
    if out["red"].get("veto"):
        why.append("red veto")
    if cand != "WAIT" and str(an.get("bias", "")).upper() != cand:
        why.append("analyst disagrees")
    if cand != "WAIT" and qs < 55:
        why.append(f"quant {qs}<55")
    if conf < cfg.MIN_CONF:
        why.append(f"conf<{cfg.MIN_CONF}")
    if score < cfg.MIN_SCORE:
        why.append(f"score<{cfg.MIN_SCORE}")
    if atr <= 0:
        why.append("atr invalid")
    go = cand != "WAIT" and not why
    slm = clamp(num(m.get("sl_atr"), num(an.get("sl_atr"), 1.5)), 1, 3)
    tpm = clamp(num(m.get("tp_atr"), num(an.get("tp_atr"), 2.5)), 1, 5)
    d = 1 if cand == "BUY" else -1
    return {"cand": cand, "action": cand if go else "WAIT", "go": go, "score": score, "conf": conf,
            "entry": price, "sl": ind.sig(price - d * slm * atr), "tp": ind.sig(price + d * tpm * atr),
            "rr": round(tpm / slm, 2), "why": str(m.get("reason", ""))[:200],
            "blocked": [] if go else why, "out": out}


def run_symbol(sym):
    name, src, sid = sym
    cs = data.fetch(src, sid, "30m", cfg.HIST)
    CACHE[name] = cs
    closed, live = data.split(cs, "30m")
    if len(closed) < 150:
        raise RuntimeError(f"only {len(closed)} candles (<150)")
    f = ind.features(closed, live)
    price = ind.sig((live or closed[-1])["c"])
    journal.resolve(name, cs, price)
    slot = ind.slot_stats(closed, cfg.TZ)
    q = ind.quant(f, slot)
    hm = lambda t: datetime.fromtimestamp(t, cfg.TZ).strftime("%H:%M")
    pack = {"symbol": name, "now": datetime.now(cfg.TZ).strftime("%H:%M GMT+6"), "price": price,
            "live_candle": live and [hm(live["t"]), live["o"], live["h"], live["l"], live["c"]],
            "last6_closed[t,o,h,l,c]": [[hm(x["t"]), x["o"], x["h"], x["l"], x["c"]] for x in closed[-6:]],
            "ind": f, "slot_stats": slot, "quant": q,
            "news_6h": [{"cat": n["cat"], "title": n["title"][:100], "hist": journal.similar(n["cat"], name)}
                        for n in journal.news_recent(name, 6)],
            "track": journal.stats(name), "open_trade": journal.open_signal(name) and
            {k: journal.open_signal(name)[k] for k in ("action", "entry", "sl", "tp")}}
    r = decide(pack, q, f["atr"], price)
    journal.log_opinion(name, r["action"], r["go"] and not journal.open_signal(name), r["score"], r["conf"],
                        price, r["sl"], r["tp"], f["atr"], r["why"])
    return fmt(name, r, f, slot, live, closed[-1], price)


def fmt(name, r, f, slot, live, last, price):
    st = journal.stats(name)
    o = journal.open_signal(name)
    L = [f"{name} 30m | price {price}",
         f"DECISION: {r['action']} | GO: {'YES' if r['go'] else 'NO'} | SCORE {r['score']} | CONF {r['conf']}"]
    if r["go"]:
        L.append(f"Entry {r['entry']} | SL {r['sl']} | TP {r['tp']} | RR {r['rr']}")
    else:
        L.append(f"Candidate {r['cand']} blocked: {', '.join(r['blocked'])}")
    L.append(f"Trend {f['trend']} | EMA50 {f['ema50']} EMA200 {f['ema200']} | RSI {f['rsi'] and round(f['rsi'])} | "
             f"MACD hist {f['macd_hist']} | VWAP {f['vwap']} | ATR {f['atr']}")
    c = live or last
    L.append(f"{'Live' if live else 'Last'} candle O{c['o']} H{c['h']} L{c['l']} C{c['c']}")
    L.append(f"Slot {slot['slot']}: n={slot['n']} up30m={slot['up1']}% avg={slot['avg1']} | up60m={slot['up2']}% avg={slot['avg2']}")
    if o:
        d = 1 if o["action"] == "BUY" else -1
        L.append(f"OPEN {o['action']} @ {o['entry']} SL {o['sl']} TP {o['tp']} | floating {ind.sig((price - o['entry']) * d)} pts")
    L.append(f"Why: {r['why']}")
    L.append(f"Record: {st['wins']}W/{st['losses']}L pnl {st['pnl_pts']} pts | opinion acc {st['opinion_acc']}% (n={st['n_opinions']})")
    return "\n".join(L)


def morning_report(sym):
    name, src, sid = sym
    cs = data.fetch(src, sid, "1d", 260)
    closed, _ = data.split(cs, "1d")
    if len(closed) < 30:
        raise RuntimeError(f"only {len(closed)} daily candles")
    f = ind.features(closed)
    p = closed[-1]
    n5 = closed[-1]["c"] - closed[-6]["c"]
    L = [f"{name} D1 | prev {datetime.fromtimestamp(p['t'], cfg.TZ).strftime('%d %b')}: O{p['o']} H{p['h']} L{p['l']} C{p['c']} "
         f"({ind.sig(p['c'] - p['o'])} pts)",
         f"5d net {ind.sig(n5)} | D trend {f['trend']} | EMA50 {f['ema50']} EMA200 {f['ema200']} | RSI {f['rsi'] and round(f['rsi'])} | D ATR {f['atr']}"]
    for n in journal.news_today(name, 24):
        t = datetime.fromtimestamp(n["ts"], cfg.TZ).strftime("%H:%M")
        s = journal.similar(n["cat"], name)
        L.append(f"NEWS [{n['cat']}] {t}: {n['title'][:90]}" + (f" | hist n={s['n']} up60m={s['up_pct']}% {s['avg_abs_atr']}ATR" if s else ""))
    return "\n".join(L)
