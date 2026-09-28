"""One scheduled run (GitHub Actions calls this every 30 min). State lives in ./state (journal.db, meta.json)."""
import json, os, traceback
from datetime import datetime
import config as cfg
import agents, journal, telegram

META = os.path.join(os.path.dirname(cfg.DB), "meta.json")


def _load():
    try:
        return json.load(open(META))
    except Exception:
        return {}


def _save(m):
    os.makedirs(os.path.dirname(META), exist_ok=True)
    json.dump(m, open(META, "w"))


def ready():
    if not cfg.SYMBOLS:
        print("SYMBOLS blank - idle")
    elif not (cfg.AI_KEY and cfg.AI_MODEL and cfg.AI_BASE):
        print("AI_PROVIDER/AI_API_KEY/AI_MODEL blank or unknown provider - idle")
    else:
        return True
    return False


def morning():
    L = [f"MORNING BRIEF {datetime.now(cfg.TZ).strftime('%d %b %Y')} (GMT+6)"]
    for s in cfg.SYMBOLS:
        try:
            L.append(agents.morning_report(s))
        except Exception as e:
            L.append(f"{s}: SKIPPED ({str(e)[:100]})")
    telegram.send("\n\n".join(L))


def cycle():
    L = [f"REPORT {datetime.now(cfg.TZ).strftime('%H:%M')} GMT+6"]
    for s in cfg.SYMBOLS:
        try:
            L.append(agents.run_symbol(s))
        except Exception as e:
            L.append(f"{s}: SKIPPED - not confident/unavailable ({str(e)[:120]})")
    pnl, n = journal.total_pnl()
    L.append(f"TOTAL closed trades {n} | P&L {round(pnl, 5)} pts")
    telegram.send("\n\n".join(L))


def main():
    if not ready():
        return
    now = datetime.now(cfg.TZ)
    slot = now.replace(minute=0 if now.minute < 30 else 30, second=0, microsecond=0)
    force, m = cfg.env("FORCE") == "1", _load()
    inwin = cfg.WIN_START <= slot.strftime("%H:%M") <= cfg.WIN_END
    if not force and (not inwin or m.get("slot") == slot.isoformat()):
        print("skip: outside window or slot already done")
        return
    if not force:
        m["slot"] = slot.isoformat()
    if inwin and m.get("morning") != str(slot.date()):
        m["morning"] = str(slot.date())
        _save(m)
        morning()
    _save(m)
    cycle()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
