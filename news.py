import re, hashlib, time, requests
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
import config as cfg
import journal, indicators as ind, data

CAT = [("CPI", r"\bcpi\b|inflation"), ("NFP", r"non-?farm|payrolls?|\bnfp\b"),
       ("FOMC", r"\bfomc\b|\bfed\b|powell|federal reserve|rate (decision|cut|hike)"),
       ("ECB", r"\becb\b|lagarde"), ("BOE", r"bank of england|\bboe\b|bailey"),
       ("BOJ", r"bank of japan|\bboj\b|ueda"), ("JOBS", r"unemployment|jobless|employment"),
       ("GDP", r"\bgdp\b"), ("PMI", r"\bpmi\b"), ("RETAIL", r"retail sales"),
       ("OIL", r"opec|crude|\boil\b|\bwti\b"), ("GOLD", r"\bgold\b|\bxau\b"),
       ("GEO", r"\bwar\b|missile|sanction|ceasefire")]
CCY = {"USD": r"\bUS\b|U\.S\.|(?i:\bfed\b|fomc|powell|dollar|treasury|non-?farm|payroll|federal reserve)",
       "EUR": r"(?i:\becb\b|eurozone|\beuro\b|lagarde|germany)",
       "GBP": r"(?i:\buk\b|bank of england|\bboe\b|sterling|\bpound\b|bailey)",
       "JPY": r"(?i:japan|\bboj\b|\byen\b|ueda)", "AUD": r"(?i:\brba\b|australia)",
       "CAD": r"(?i:\bboc\b|canada)", "CHF": r"(?i:\bsnb\b|swiss)", "NZD": r"(?i:\brbnz\b|new zealand)",
       "GOLD": r"(?i:\bgold\b|\bxau\b)", "OIL": r"(?i:opec|crude|\boil\b|\bwti\b)"}
US_IDX = {"ES", "NQ", "YM", "US30", "US500", "NAS100", "SPX", "DJI", "NDX", "SPX500", "USTEC"}
UA = {"User-Agent": "Mozilla/5.0"}


def _cat(title):
    for k, p in CAT:
        if re.search(p, title, re.I):
            return k
    return ""


def _tags(title):
    return [k for k, p in CCY.items() if re.search(p, title)]


def _match(name, tags):
    n = name.upper()
    for t in tags:
        if t in ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD") and t in n:
            return True
        if t == "USD" and n in US_IDX:
            return True
        if t == "GOLD" and (n == "GC" or any(k in n for k in ("XAU", "GOLD"))):
            return True
        if t == "OIL" and (n == "CL" or any(k in n for k in ("OIL", "WTI", "BRENT", "XTI", "XBR"))):
            return True
    return False


def _date(s):
    try:
        return int(parsedate_to_datetime(s).timestamp())
    except Exception:
        pass
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return int((d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp())
    except Exception:
        return int(time.time())


def fetch_feed(url):
    r = requests.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    out = []
    for it in ET.fromstring(r.content).iter():
        if it.tag.split("}")[-1] not in ("item", "entry"):
            continue
        g = lambda n: next(((e.text or "").strip() or e.attrib.get("href", "")
                            for e in it if e.tag.split("}")[-1] == n), "")
        out.append((g("title"), g("link"), _date(g("pubDate") or g("published") or g("updated"))))
    return out


def hist_line(cat, sym):
    s = journal.similar(cat, sym)
    return f"hist {cat}/{sym}: n={s['n']} up60m={s['up_pct']}% avg|move|={s['avg_abs_atr']}ATR" if s else f"hist {cat}/{sym}: none yet"


def scan():
    """New high-impact items (category + at least one of my symbols) -> alert lines."""
    names = [s[0] for s in cfg.SYMBOLS]
    alerts = []
    for url in cfg.NEWS_FEEDS:
        try:
            items = fetch_feed(url)
        except Exception as e:
            print("feed error", url, e)
            continue
        for title, link, ts in items:
            uid = hashlib.md5((link or title).encode()).hexdigest()
            if not title or journal.news_seen(uid):
                continue
            cat = _cat(title)
            syms = [n for n in names if _match(n, _tags(title))] if cat else []
            journal.news_add(uid, ts, title, link, cat, syms)
            if cat and syms and time.time() - ts < 86400 and len(alerts) < 8:
                t = datetime.fromtimestamp(ts, cfg.TZ).strftime("%H:%M")
                alerts.append(f"HIGH NEWS [{cat}] {t} GMT+6: {title[:140]}\n  pairs: {', '.join(syms)}\n  "
                              + "\n  ".join(hist_line(cat, s) for s in syms))
    return alerts


def study(cache):
    """Replay chart at the news time: log how each mapped symbol reacted (30/60/90m) into the journal."""
    lines = []
    for n in journal.news_pending_reaction():
        res = {}
        for sym in n["symbols"].split(","):
            cs = cache.get(sym)
            if not cs:
                continue
            i = next((k for k, x in enumerate(cs) if x["t"] <= n["ts"] < x["t"] + 1800), None)
            if i is None or i < 20 or i + 2 >= len(cs):
                continue
            base = cs[i - 1]["c"]
            a = ind.atr(cs[:i])
            res[sym] = {"m30": ind.sig(cs[i]["c"] - base), "m60": ind.sig(cs[i + 1]["c"] - base),
                        "m90": ind.sig(cs[i + 2]["c"] - base), "atr": ind.sig(a),
                        "rng": ind.sig(max(x["h"] for x in cs[i:i + 3]) - min(x["l"] for x in cs[i:i + 3]))}
            lines.append(f"JOURNAL {n['cat']} {sym}: 60m move {res[sym]['m60']} ({res[sym]['m60'] / a:+.1f} ATR) | {n['title'][:70]}")
        if res:
            journal.news_set_reaction(n["uid"], res)
    return lines
