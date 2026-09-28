"""Offline test: mocks market data, news and LLM. Run: python selftest.py"""
import os, sys, time, random, tempfile, json
from email.utils import formatdate

os.environ.update(SYMBOLS="EURUSD:yahoo:EURUSD=X,XAUUSD:yahoo:GC=F", AI_PROVIDER="groq", AI_API_KEY="x",
                  AI_MODEL="m", NEWS_FEEDS="http://feed.test/rss", LLM_DELAY="0",
                  DB_PATH=tempfile.mktemp(suffix=".db"), TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_ID="")
import config as cfg, data, llm, news, telegram, agents, journal, main, indicators as ind

random.seed(1)


def candles(base, n=1000, drift=0.00002):
    t0 = int(time.time()) // 1800 * 1800 - (n - 1) * 1800
    out, p = [], base
    for i in range(n):
        o = p
        p = o * (1 + drift + random.gauss(0, 0.0005))
        out.append(dict(t=t0 + i * 1800, o=o, h=max(o, p) * 1.0002, l=min(o, p) * 0.9998, c=p, v=100 + i % 7))
    return out


DATA = {"EURUSD=X": candles(1.08), "GC=F": candles(2350)}
data.fetch = lambda src, sid, tf="30m", n=None: (DATA[sid] if tf == "30m" else
                                                   [dict(x, t=x["t"] // 86400 * 86400 - 86400 * k, ) for k, x in enumerate(DATA[sid][-300:][::-1])][::-1])

CALLS = []


def fake_llm(system, user, max_tokens=800):
    role = system.split("ROLE=")[1].split(".")[0]
    d = json.loads(user)
    assert "DATA" in d and d["DATA"]["ind"]["atr"] > 0
    CALLS.append(role)
    return {"research": {"bias": "BUY", "conf": 75, "notes": "n", "msg": "m"},
            "analyst": {"bias": "BUY", "conf": 74, "sl_atr": 1.5, "tp_atr": 2.5, "notes": "n", "msg": "m"},
            "red": {"veto": False, "risk": 30, "notes": "n", "msg": "m"},
            "audit": {"pass": True, "issues": [], "msg": "ok"},
            "manager": {"action": "BUY", "score": 80, "conf": 78, "sl_atr": 1.5, "tp_atr": 2.5, "skip": False, "reason": "aligned"}}[role]


llm.chat = fake_llm
SENT = []
telegram.send = lambda t: SENT.append(t)

RSS = f"""<rss><channel><item><title>US CPI hotter than expected as Fed holds</title><link>http://a/1</link>
<pubDate>{formatdate(time.time() - 3 * 3600)}</pubDate></item>
<item><title>Local bakery opens</title><link>http://a/2</link><pubDate>{formatdate(time.time())}</pubDate></item></channel></rss>"""


class R:
    content = RSS.encode()
    def raise_for_status(self): pass


news.requests.get = lambda *a, **k: R()

# indicators sanity
c = DATA["EURUSD=X"]
f = ind.features(c[:-1], c[-1])
assert f["trend"] in ("up", "down", "mixed") and 0 <= f["rsi"] <= 100 and f["atr"] > 0, f
assert ind.vwap(c) is not None

# cycle 1
main.cycle()
out = "\n".join(SENT)
print(out)
assert "DECISION:" in out and "HIGH NEWS [CPI]" in out and "EURUSD" in out
assert CALLS.count("manager") == 2 and len(CALLS) == 10
assert "JOURNAL CPI EURUSD" in out, "news reaction study did not run"
o = journal.open_signal("XAUUSD")
assert o and o["action"] == "BUY", o

# force TP hit, then cycle 2 must settle the trade and score previous opinion
DATA["GC=F"][-1]["h"] = o["tp"] * 1.01
SENT.clear(); CALLS.clear()
main.cycle()
st = journal.stats("XAUUSD")
print(st)
assert st["wins"] >= 1 and st["pnl_pts"] > 0 and st["opinion_acc"] is not None

# failure path: audit fail -> no GO
llm_orig = fake_llm
def bad(system, user, max_tokens=800):
    r = llm_orig(system, user)
    return {"pass": False, "issues": ["x"], "msg": "bad"} if "ROLE=audit" in system else r
llm.chat = bad
SENT.clear()
main.cycle()
assert "audit failed" in "\n".join(SENT) and "GO: YES" not in "\n".join(SENT)

# LLM down -> graceful skip
def dead(*a, **k): raise RuntimeError("LLM failed: HTTP 429")
llm.chat = dead
SENT.clear()
main.cycle()
assert "SKIPPED" in "\n".join(SENT)

# blank variable -> idle
cfg.SYMBOLS[:] = []
SENT.clear(); main.cycle(); assert not SENT

# morning brief
cfg.SYMBOLS[:] = [("EURUSD", "yahoo", "EURUSD=X")]
main.morning()
print(SENT[-1])
assert "MORNING BRIEF" in SENT[-1] and "D1" in SENT[-1]
print("\nALL TESTS PASSED")
