import os, pathlib
from datetime import timezone, timedelta

PROVIDERS = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    "openai": "https://api.openai.com/v1",
}


def env(k, d=""):
    return os.environ.get(k, "").strip() or d  # unset OR empty -> default


TG_TOKEN, TG_CHAT = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
AI_PROVIDER, AI_KEY, AI_MODEL = env("AI_PROVIDER").lower(), env("AI_API_KEY"), env("AI_MODEL")
AI_BASE = env("AI_BASE_URL") or PROVIDERS.get(AI_PROVIDER, "")
# Deriv synthetic symbol ids, comma separated (e.g. R_100,BOOM1000). Blank -> agents idle.
SYMBOLS = [s.strip() for s in env("SYMBOLS").split(",") if s.strip()]
DERIV_WS = env("DERIV_WS", "wss://api.derivws.com/trading/v1/options/ws/public")
TZ = timezone(timedelta(hours=float(env("TZ_OFFSET", "6"))))
WIN_START, WIN_END = env("WINDOW_START", "08:00"), env("WINDOW_END", "23:00")
MIN_CONF, MIN_SCORE = int(env("MIN_CONF", "60")), int(env("MIN_SCORE", "60"))
HIST = int(env("HIST_CANDLES", "1000"))
LLM_DELAY = float(env("LLM_DELAY", "2"))
DB = env("DB_PATH", str(pathlib.Path(__file__).parent / "state" / "journal.db"))
