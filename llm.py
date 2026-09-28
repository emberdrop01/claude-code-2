import json, re, time, requests
import config as cfg

_last = 0.0


def _parse(t):
    t = re.sub(r"```(?:json)?", "", t).strip()
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b < 0:
        raise ValueError("no json")
    return json.loads(t[a:b + 1])


def chat(system, user, max_tokens=800):
    """Any OpenAI-compatible provider (Groq / OpenRouter / Google / OpenAI). Change .env only."""
    global _last
    if not (cfg.AI_KEY and cfg.AI_MODEL and cfg.AI_BASE):
        raise RuntimeError("AI variables blank")
    body = {"model": cfg.AI_MODEL, "temperature": 0.2, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"}}
    h = {"Authorization": "Bearer " + cfg.AI_KEY, "Content-Type": "application/json"}
    err = None
    for a in range(4):
        w = cfg.LLM_DELAY - (time.time() - _last)
        if w > 0:
            time.sleep(w)
        try:
            r = requests.post(cfg.AI_BASE.rstrip("/") + "/chat/completions", headers=h, json=body, timeout=90)
            _last = time.time()
            if r.status_code == 400 and "response_format" in body:
                body.pop("response_format")
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                err = f"HTTP {r.status_code}"
                time.sleep(8 * (a + 1))
                continue
            r.raise_for_status()
            return _parse(r.json()["choices"][0]["message"]["content"])
        except (requests.RequestException, KeyError, ValueError, IndexError) as e:
            err = str(e)[:100]
            time.sleep(3 * (a + 1))
    raise RuntimeError("LLM failed: " + str(err))
