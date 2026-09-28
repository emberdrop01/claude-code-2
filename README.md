# Deriv Synthetic Desk (GitHub Actions only)
Research / Analyst / Red / Audit / Manager agents -> Telegram. Advisory only, no orders.

## Setup (10 min)
1. Create a **private** GitHub repo, upload all files of this folder (keep `.github/workflows/desk.yml`).
2. Repo > Settings > Secrets and variables > Actions:
   - **Secrets**: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `AI_PROVIDER` (groq | google | openrouter | openai), `AI_API_KEY`, `AI_MODEL`
   - **Variables**: `SYMBOLS` (e.g. `R_100,R_50,BOOM1000,CRASH1000`). Optional: `WINDOW_START`(08:00) `WINDOW_END`(23:00) `MIN_CONF`(60) `MIN_SCORE`(60) `HIST_CANDLES`(1000) `DERIV_WS`
   - Example models: groq `llama-3.3-70b-versatile`, google `gemini-2.5-flash`, openrouter `meta-llama/llama-3.3-70b-instruct:free` (check current names)
3. Settings > Actions > General > Workflow permissions: **Read and write**.
4. Actions tab > `desk` > Run workflow (force=1). A report should land in Telegram. Then it runs itself every 30 min.

Change AI provider/model/symbols = edit secrets/variables in the UI. No code changes.

## Notes
- Journal (`journal.db`, `meta.json`) is stored on the `state` branch (overwritten each run, no history bloat). Keep the repo private.
- Cron is UTC and GitHub may delay runs 5-30+ min; that is GitHub, not a bug. Duplicate runs in one slot are skipped. Cron assumes GMT+6; if you change `TZ_OFFSET`, edit the cron hours too.
- Free private plan = 2000 Actions min/month. ~31 runs/day x ~1-2 min. Keep to ~4-5 symbols (each = 5 AI calls per run).
- GO=YES only if: manager BUY/SELL, audit pass, no red veto, analyst agrees, deterministic quant score >=55, conf>=MIN_CONF, score>=MIN_SCORE. Else WAIT + reason. Data/AI failure -> SKIPPED.
- `python selftest.py` runs offline with mocks.
