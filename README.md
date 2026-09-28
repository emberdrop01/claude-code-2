# AI Trading Desk (Research / Analyst / Red / Audit / Manager -> Telegram)

Advisory signals only. No orders are placed.

## Setup (Oracle VM Ubuntu, or any Linux)
```
git clone <your-repo> /opt/desk && cd /opt/desk
sudo apt update && sudo apt install -y python3-venv
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env          # fill secrets + SYMBOLS
./venv/bin/python selftest.py              # offline check -> ALL TESTS PASSED
RUN_ON_START=1 ./venv/bin/python main.py   # live test: sends one report now (Ctrl+C to stop)
sudo cp desk.service /etc/systemd/system/ && sudo systemctl enable --now desk
journalctl -u desk -f                      # logs
```
Docker alternative: `docker build -t desk . && docker run -d --restart=always --env-file .env -v desk-data:/data desk`

## Change AI provider
Edit only `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL` (or `AI_BASE_URL`) in `.env`, then `sudo systemctl restart desk`. No code changes.

## Move to another VM
Copy `.env` and `journal.db` (the learning journal). Repeat setup.

## Behaviour
- 08:00-23:00 GMT+6 (WINDOW_START/END), a report every :00/:30. First slot of the day also sends the morning brief (daily candle, D1 trend, marked news).
- Per symbol: 5 LLM calls (research, analyst, red, audit, manager) sharing a board. GO=YES only if: manager BUY/SELL, audit pass, no red veto, analyst agrees, deterministic quant score >=55, conf>=MIN_CONF, score>=MIN_SCORE. Otherwise WAIT with the blocked reason. Data failure -> SKIPPED.
- Journal (SQLite): every opinion is judged next cycle; GO trades settle on SL/TP (SL first if both hit in one candle); news reactions are logged 90+ min after each marked item and fed back as history.
- Blank SYMBOLS / AI vars / NEWS_FEEDS -> that part stays idle.
- Free-tier limits: cost = symbols x 5 calls per 30 min. Keep SYMBOLS small on Groq/Gemini free tiers.
