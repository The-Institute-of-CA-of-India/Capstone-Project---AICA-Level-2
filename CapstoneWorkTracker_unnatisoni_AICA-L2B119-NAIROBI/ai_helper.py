"""Gemini (Google AI Studio) helpers. The app works normally if no key is set."""
import os, json, re
from datetime import date
from dotenv import load_dotenv

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
DEFAULT_MODEL = "gemini-3.8-flash"


def _load():
    # utf-8-sig tolerates the invisible BOM that Notepad can add
    if os.path.exists(ENV_PATH):
        load_dotenv(ENV_PATH, override=True, encoding="utf-8-sig")
    key = os.getenv("GEMINI_API_KEY", "").strip().strip("\"'").strip()
    if key and key != "your_key_here":
        os.environ["GEMINI_API_KEY"] = key
        return key
    return ""


def available():
    return bool(_load())


def get_model():
    _load()
    return os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_MODEL


def _write_env(updates):
    """Update keys in .env, keeping the other lines."""
    lines = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, encoding="utf-8-sig") as f:
            for ln in f:
                if "=" in ln and not ln.strip().startswith("#"):
                    k, v = ln.split("=", 1)
                    lines[k.strip()] = v.strip()
    lines.update(updates)
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        for k, v in lines.items():
            f.write(f"{k}={v}\n")
    for k, v in updates.items():
        os.environ[k] = v


def save_key(key):
    """Write the key to .env next to the app and use it immediately."""
    _write_env({"GEMINI_API_KEY": key.strip().strip("\"'").strip()})


def save_model(name):
    _write_env({"GEMINI_MODEL": name.strip()})


def list_models():
    """Names of models this key can use for text generation."""
    from google import genai
    client = genai.Client(api_key=_load())
    out = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if not actions or "generateContent" in actions:
            out.append(m.name.replace("models/", ""))
    return sorted(out)


def _generate(prompt):
    """Call Gemini (google-genai package). Retries on busy/timeout errors."""
    import time
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=_load(), http_options=types.HttpOptions(timeout=60000))
    last = None
    for attempt in range(3):
        try:
            return client.models.generate_content(model=get_model(), contents=prompt).text
        except Exception as e:
            last = e
            if any(c in str(e) for c in ("504", "503", "429", "DEADLINE", "UNAVAILABLE")):
                time.sleep(2 * (attempt + 1))
                continue
            raise
    raise last


def parse_task(text, employee_names):
    """Turn a typed instruction into a task dict."""
    prompt = f"""Today is {date.today().isoformat()}.
Convert the instruction into JSON with exactly these keys:
title, description, client, category, priority (High/Medium/Low), assigned_to, due_date (YYYY-MM-DD or null).
assigned_to must be one of: {employee_names} (or null if unclear).
Return only JSON, no markdown.
Instruction: {text}"""
    out = _generate(prompt)
    out = re.sub(r"```json|```", "", out).strip()
    return json.loads(out)


def weekly_summary(tasks):
    lines = [f"- {t['title']} | {t['assignee']} | {t['status']} | due {t['due_date']}" for t in tasks]
    prompt = ("You are an office manager's assistant. Write a short plain-English summary of this "
              "task list: what is done, what is pending review, what is overdue, who is overloaded, "
              "and 3 suggested actions.\n" + "\n".join(lines))
    return _generate(prompt)
