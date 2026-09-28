import time, traceback
from datetime import datetime
import config as cfg
import agents, journal, news, telegram


def ready():
    if not cfg.SYMBOLS:
        print("SYMBOLS blank - idle")
        return False
    if not (cfg.AI_KEY and cfg.AI_MODEL and cfg.AI_BASE):
        print("AI_PROVIDER/AI_API_KEY/AI_MODEL blank - idle")
        return False
    return True


def morning():
    if not cfg.SYMBOLS:
        return
    L = [f"MORNING BRIEF {datetime.now(cfg.TZ).strftime('%d %b %Y')} (GMT+6)"]
    if cfg.NEWS_FEEDS:
        try:
            L += news.scan()
        except Exception as e:
            L.append(f"news skipped: {e}")
    for s in cfg.SYMBOLS:
        try:
            L.append(agents.morning_report(s))
        except Exception as e:
            L.append(f"{s[0]}: SKIPPED ({str(e)[:100]})")
    telegram.send("\n\n".join(L))


def cycle():
    if not ready():
        return
    now = datetime.now(cfg.TZ).strftime("%H:%M")
    L = [f"REPORT {now} GMT+6"]
    if cfg.NEWS_FEEDS:
        try:
            L += news.scan()
        except Exception as e:
            L.append(f"news skipped: {e}")
    for s in cfg.SYMBOLS:
        try:
            L.append(agents.run_symbol(s))
        except Exception as e:
            L.append(f"{s[0]}: SKIPPED - not confident/unavailable ({str(e)[:120]})")
    try:
        L += news.study(agents.CACHE)
    except Exception as e:
        print("study error", e)
    pnl, n = journal.total_pnl()
    L.append(f"TOTAL closed trades {n} | P&L {round(pnl, 5)} pts")
    telegram.send("\n\n".join(L))


def slot_of(t):
    return t.replace(minute=0 if t.minute < 30 else 30, second=0, microsecond=0)


def main():
    last = None if cfg.RUN_ON_START else slot_of(datetime.now(cfg.TZ))
    mday = None
    print("desk running; window", cfg.WIN_START, "-", cfg.WIN_END, "GMT+6")
    while True:
        s = slot_of(datetime.now(cfg.TZ))
        if s != last:
            last = s
            if cfg.WIN_START <= s.strftime("%H:%M") <= cfg.WIN_END:
                try:
                    if mday != s.date():
                        mday = s.date()
                        morning()
                    cycle()
                except Exception:
                    traceback.print_exc()
        time.sleep(15)


if __name__ == "__main__":
    main()
