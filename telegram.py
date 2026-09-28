import requests
import config as cfg


def send(text):
    if not (cfg.TG_TOKEN and cfg.TG_CHAT):
        print(text)
        return
    for i in range(0, len(text), 4000):
        try:
            requests.post(f"https://api.telegram.org/bot{cfg.TG_TOKEN}/sendMessage",
                          json={"chat_id": cfg.TG_CHAT, "text": text[i:i + 4000],
                                "disable_web_page_preview": True}, timeout=20).raise_for_status()
        except Exception as e:
            print("telegram error:", e)
