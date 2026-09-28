"""Offline test (mock Deriv + mock LLM). Run: python selftest.py"""
import os, time, random, tempfile, json
d = tempfile.mkdtemp()
os.environ.update(SYMBOLS="R_100,BOOM1000", AI_PROVIDER="groq", AI_API_KEY="x", AI_MODEL="m", LLM_DELAY="0",
                  DB_PATH=d + "/state/journal.db", TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_ID="", FORCE="1")
import config as cfg, data, llm, telegram, agents, journal, run_once, indicators as ind
random.seed(1)


def candles(base, n=1000):
    t0 = int(time.time()) // 1800 * 1800 - (n - 1) * 1800
    out, p = [], base
    for i in range(n):
        o = p; p = o * (1 + 0.00002 + random.gauss(0, 0.0005))
        out.append(dict(t=t0 + i * 1800, o=o, h=max(o, p) * 1.0002, l=min(o, p) * 0.9998, c=p))
    return out


DATA = {"R_100": candles(1000), "BOOM1000": candles(9000)}
data.fetch = lambda sid, tf="30m", n=None: DATA[sid] if tf == "30m" else [
    dict(x, t=(x["t"] // 86400 - k) * 86400) for k, x in enumerate(DATA[sid][-300:][::-1])][::-1]
CALLS = []


def fake(system, user, max_tokens=800):
    role = system.split("ROLE=")[1].split(".")[0]
    assert json.loads(user)["DATA"]["ind"]["atr"] > 0
    CALLS.append(role)
    return {"research": {"bias": "BUY", "conf": 75}, "analyst": {"bias": "BUY", "conf": 74, "sl_atr": 1.5, "tp_atr": 2.5},
            "red": {"veto": False, "risk": 30}, "audit": {"pass": True, "issues": []},
            "manager": {"action": "BUY", "score": 90, "conf": 80, "sl_atr": 1.5, "tp_atr": 2.5, "skip": False, "reason": "aligned"}}[role]


llm.chat = fake
SENT = []
telegram.send = SENT.append
f = ind.features(DATA["R_100"][:-1])
assert f["trend"] in ("up", "down", "mixed") and 0 <= f["rsi"] <= 100 and f["atr"] > 0

run_once.main()  # forced: morning + cycle
out = "\n".join(SENT); print(out)
assert "MORNING BRIEF" in out and "DECISION:" in out and len(CALLS) == 10
o = journal.open_signal("R_100") or journal.open_signal("BOOM1000")
sym = "R_100" if journal.open_signal("R_100") else "BOOM1000"
assert o, "no GO trade opened in mock (check quant gate)"

DATA[sym][-1]["h"] = o["tp"] * 1.01
SENT.clear(); run_once.main()
st = journal.stats(sym); print(st)
assert st["wins"] >= 1 and st["pnl_pts"] > 0 and st["opinion_acc"] == 100

os.environ["FORCE"] = "0"; SENT.clear(); run_once.main()  # non-forced: window/dedupe logic must not crash
llm.chat = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("LLM failed: HTTP 429"))
os.environ["FORCE"] = "1"; SENT.clear(); run_once.main()
assert "SKIPPED" in "\n".join(SENT)
cfg.SYMBOLS[:] = []; SENT.clear(); run_once.main(); assert not SENT
print("\nALL TESTS PASSED")
