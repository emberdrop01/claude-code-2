"""Diagnose Deriv connectivity: python check_deriv.py [SYMBOL]"""
import sys
import data

sym = sys.argv[1] if len(sys.argv) > 1 else "R_100"
for u in data.candidates():
    try:
        d = data._ask(u, {"ticks_history": sym, "count": 3, "end": "latest", "granularity": 1800,
                          "style": "candles", "req_id": 1})
        print("OK  ", u, "->", "error: " + str(d["error"].get("message")) if d.get("error") else f"{len(d['candles'])} candles")
    except Exception as e:
        print("FAIL", u, "->", str(e)[:120])
