import os, sqlite3, time
import config as cfg

SCHEMA = """
CREATE TABLE IF NOT EXISTS opinions(id INTEGER PRIMARY KEY, ts INT, symbol TEXT, action TEXT, go INT,
 score INT, conf INT, entry REAL, sl REAL, tp REAL, atr REAL, verdict TEXT, status TEXT, pnl REAL,
 closed_ts INT, why TEXT);
"""


def db():
    os.makedirs(os.path.dirname(cfg.DB) or ".", exist_ok=True)
    c = sqlite3.connect(cfg.DB)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def log_opinion(sym, action, go, score, conf, entry, sl, tp, atr, why):
    c = db()
    c.execute("INSERT INTO opinions(ts,symbol,action,go,score,conf,entry,sl,tp,atr,status,why) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
              (int(time.time()), sym, action, int(go), score, conf, entry, sl, tp, atr,
               "open" if go else None, (why or "")[:300]))
    c.commit()
    c.close()


def resolve(sym, cs, price):
    """Judge previous opinions (next-cycle verdict) and settle open trades against candles."""
    c, now = db(), int(time.time())
    for r in c.execute("SELECT * FROM opinions WHERE symbol=? AND go=1 AND status='open'", (sym,)).fetchall():
        d, base, res = (1 if r["action"] == "BUY" else -1), r["ts"] // 1800 * 1800, None
        for x in cs:
            if x["t"] < base:
                continue
            sl_hit = x["l"] <= r["sl"] if d == 1 else x["h"] >= r["sl"]
            tp_hit = x["h"] >= r["tp"] if d == 1 else x["l"] <= r["tp"]
            if sl_hit:  # SL first when both hit in one candle (conservative)
                res = ("loss", (r["sl"] - r["entry"]) * d, x["t"])
                break
            if tp_hit:
                res = ("win", (r["tp"] - r["entry"]) * d, x["t"])
                break
        if not res and now - r["ts"] > 86400:
            res = ("expired", (price - r["entry"]) * d, now)
        if res:
            c.execute("UPDATE opinions SET status=?, pnl=?, closed_ts=? WHERE id=?", (*res, r["id"]))
    for r in c.execute("SELECT * FROM opinions WHERE symbol=? AND verdict IS NULL", (sym,)).fetchall():
        mv, a = price - r["entry"], r["atr"] or 0
        if r["go"] and r["status"] in ("win", "loss"):
            v = "right" if r["status"] == "win" else "wrong"
        elif r["action"] == "BUY":
            v = "right" if mv > 0 else "wrong"
        elif r["action"] == "SELL":
            v = "right" if mv < 0 else "wrong"
        else:
            v = "right" if abs(mv) < 0.5 * a else "missed"
        c.execute("UPDATE opinions SET verdict=? WHERE id=?", (v, r["id"]))
    c.commit()
    c.close()


def stats(sym):
    c = db()
    t = c.execute("SELECT status,pnl FROM opinions WHERE symbol=? AND go=1 AND status!='open'", (sym,)).fetchall()
    v = c.execute("SELECT verdict FROM opinions WHERE symbol=? AND verdict IS NOT NULL ORDER BY id DESC LIMIT 20", (sym,)).fetchall()
    w = c.execute("SELECT action,conf,why FROM opinions WHERE symbol=? AND verdict IN('wrong','missed') ORDER BY id DESC LIMIT 3", (sym,)).fetchall()
    c.close()
    return {"trades": len(t), "wins": sum(1 for x in t if x["status"] == "win"),
            "losses": sum(1 for x in t if x["status"] == "loss"),
            "pnl_pts": round(sum(x["pnl"] or 0 for x in t), 5),
            "opinion_acc": round(100 * sum(1 for x in v if x["verdict"] == "right") / len(v)) if v else None,
            "n_opinions": len(v),
            "recent_errors": [f'{x["action"]} conf{x["conf"]}: {(x["why"] or "")[:80]}' for x in w]}


def open_signal(sym):
    c = db()
    r = c.execute("SELECT * FROM opinions WHERE symbol=? AND go=1 AND status='open' ORDER BY id DESC LIMIT 1", (sym,)).fetchone()
    c.close()
    return dict(r) if r else None


def total_pnl():
    c = db()
    r = c.execute("SELECT COALESCE(SUM(pnl),0) s, COUNT(*) n FROM opinions WHERE go=1 AND status!='open'").fetchone()
    c.close()
    return r["s"], r["n"]
