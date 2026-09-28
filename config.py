import os, pathlib
from datetime import timezone, timedelta

_p = pathlib.Path(__file__).parent / ".env"
if _p.exists():
    for _l in _p.read_text().splitlines():
        _l = _l.strip()
        if _l and not _l.startswith("#") and "=" in _l:
            k, v = _l.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def env(k, d=""):
    return os.environ.get(k, d).strip()


PROVIDERS = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    "openai": "https://api.openai.com/v1",
}
TG_TOKEN, TG_CHAT = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
AI_PROVIDER, AI_KEY, AI_MODEL = env("AI_PROVIDER").lower(), env("AI_API_KEY"), env("AI_MODEL")
AI_BASE = env("AI_BASE_URL") or PROVIDERS.get(AI_PROVIDER, "")

SYMBOLS = []  # (name, source, id) ; blank -> agents idle
for _s in env("SYMBOLS").split(","):
    _p2 = [x.strip() for x in _s.split(":")]
    if len(_p2) == 3 and all(_p2):
        SYMBOLS.append(tuple(_p2))
NEWS_FEEDS = [u.strip() for u in env("NEWS_FEEDS").split(",") if u.strip()]
DERIV_WS = env("DERIV_WS", "wss://api.derivws.com/trading/V1/options/ws/public")

TZ = timezone(timedelta(hours=float(env("TZ_OFFSET", "6"))))
WIN_START, WIN_END = env("WINDOW_START", "08:00"), env("WINDOW_END", "23:00")
MIN_CONF, MIN_SCORE = int(env("MIN_CONF", "60")), int(env("MIN_SCORE", "60"))
HIST = int(env("HIST_CANDLES", "1000"))
LLM_DELAY = float(env("LLM_DELAY", "2"))
RUN_ON_START = env("RUN_ON_START", "0") == "1"
DB = env("DB_PATH", str(pathlib.Path(__file__).parent / "journal.db"))
