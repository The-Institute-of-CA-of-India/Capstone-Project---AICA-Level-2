"""Draft Reply's choice of AI: Claude (ai_client) or another provider (ai_openai / ai_gemini).

A "choice" is what the model list shows: a Claude model id such as ``claude-opus-5-5``, or
``p:<provider>`` for a provider set up in Settings. Only verified, tokenised content reaches here.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from . import ai_client, netguard
from .ai_client import DraftResult, Progress
from .config import DEFAULTS
from .models import UserFacingError

log = logging.getLogger("mukhota.ai")
PREFIX = "p:"


@dataclass(frozen=True)
class Provider:
    """A non-Claude provider: how to talk to it and what it supports."""

    label: str
    kind: str  # "openai" (Responses API), "gemini" (google-genai) or "compat" (OpenAI-compatible chat)
    pdf: bool
    web: bool
    needs_key: bool = True
    url_editable: bool = False
    example_model: str = ""


PROVIDERS: dict[str, Provider] = {
    "openai": Provider("OpenAI (GPT)", "openai", True, True, example_model="gpt-5"),
    "gemini": Provider("Google Gemini", "gemini", True, True, example_model="gemini-3.8-flash"),
    "deepseek": Provider("DeepSeek", "compat", False, False, example_model="deepseek-flash"),
    "mistral": Provider("Mistral", "compat", False, False, example_model="mistral-large-latest"),
    "groq": Provider("Groq", "compat", False, False, example_model="llama-3.3-70b-versatile"),
    "openrouter": Provider("OpenRouter", "compat", False, False, example_model="openai/gpt-5"),
    "ollama": Provider("Local - Ollama (this computer)", "compat", False, False, needs_key=False, url_editable=True,
                       example_model="llama3.1"),
    "lmstudio": Provider("Local - LM Studio (this computer)", "compat", False, False, needs_key=False, url_editable=True,
                         example_model="local-model"),
    "custom": Provider("Custom (OpenAI-compatible)", "compat", False, False, url_editable=True),
}
NO_PDF_WEB = "PDF and web search are not available for this provider through its API; the notice text and your law library are sent instead."


# --------------------------------------------------------------------------- keys
def _keyring_user(pid: str) -> str:
    return f"{pid}-api-key"


def set_key(pid: str, key: str) -> None:
    if pid == "claude":
        ai_client.set_api_key(key)
        return
    import keyring

    try:
        keyring.set_password(ai_client.KEYRING_SERVICE, _keyring_user(pid), key.strip())
    except Exception as exc:
        raise UserFacingError("The API key could not be saved in Windows Credential Manager.") from exc


def clear_key(pid: str) -> None:
    if pid == "claude":
        ai_client.clear_api_key()
        return
    import keyring

    try:
        keyring.delete_password(ai_client.KEYRING_SERVICE, _keyring_user(pid))
    except Exception:
        pass


def get_key(pid: str) -> str:
    import keyring

    try:
        return keyring.get_password(ai_client.KEYRING_SERVICE, _keyring_user(pid)) or ""
    except Exception:
        return ""


def key_saved(pid: str) -> bool:
    return ai_client.has_api_key() if pid == "claude" else bool(get_key(pid))


# --------------------------------------------------------------------------- choices
def provider_cfg(cfg: dict[str, Any], pid: str) -> dict[str, Any]:
    """A provider's settings; fixed providers always use the built-in address (a saved one can go stale)."""
    pc = dict(cfg.get("providers", {}).get(pid, {}))
    if pid in PROVIDERS and not PROVIDERS[pid].url_editable:
        pc["base_url"] = DEFAULTS["providers"][pid]["base_url"]
    return pc


def check_model(name: str) -> str:
    """Model IDs never contain spaces (e.g. 'deepseek-flash', not 'DeepSeek Chat')."""
    name = name.strip()
    if any(c.isspace() for c in name):
        raise UserFacingError(f"The model name '{name}' contains spaces. Use the exact model ID from the provider's "
                              "documentation, for example deepseek-flash or gpt-5.")
    return name


def check_url(url: str) -> str:
    """Provider address: https only, except on this computer (local models)."""
    url = url.strip().rstrip("/")
    u = urlparse(url)
    host = (u.hostname or "").lower()
    local = host in ("localhost", "127.0.0.1", "::1") or host.startswith("127.")
    if not host or u.scheme not in ("https", "http") or (u.scheme == "http" and not local):
        raise UserFacingError("The provider address must start with https:// (http:// is allowed only for localhost).")
    return url


def choices(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Every model the user can pick: the Claude models, then each provider that has a model name set."""
    out = [{"id": k, "label": m.label, "pdf": True, "web": True, "ready": ai_client.has_api_key()}
           for k, m in ai_client.MODELS.items()]
    for pid, p in PROVIDERS.items():
        pc = provider_cfg(cfg, pid)
        if not str(pc.get("model", "")).strip() or not str(pc.get("base_url", "")).strip():
            continue
        out.append({"id": PREFIX + pid, "label": f"{p.label} - {pc['model']}", "pdf": p.pdf, "web": p.web,
                    "ready": (not p.needs_key) or key_saved(pid)})
    return out


def valid_choice(cfg: dict[str, Any], choice: str) -> bool:
    return any(c["id"] == choice for c in choices(cfg))


def current(cfg: dict[str, Any]) -> str:
    """The chosen model, or the first Claude model if the saved choice is no longer set up."""
    c = cfg["ai"]["model"]
    return c if valid_choice(cfg, c) else next(iter(ai_client.MODELS))


def capabilities(cfg: dict[str, Any], choice: str) -> tuple[bool, bool]:
    """(can read the PDF, can search the web) for a choice."""
    if not choice.startswith(PREFIX):
        return True, True
    p = PROVIDERS[choice[len(PREFIX):]]
    return p.pdf, p.web


def label(choice: str, cfg: dict[str, Any]) -> str:
    if not choice.startswith(PREFIX):
        return ai_client.MODELS[choice].label.split(" - ")[0]
    pid = choice[len(PREFIX):]
    return f"{PROVIDERS[pid].label} ({provider_cfg(cfg, pid).get('model', '')})"


def prices(cfg: dict[str, Any], choice: str) -> tuple[float, float, float]:
    """US$ per million input / output tokens and per web search."""
    if not choice.startswith(PREFIX):
        m = ai_client.MODELS[choice]
        return m.price_in, m.price_out, ai_client.PRICE_SEARCH
    pc = provider_cfg(cfg, choice[len(PREFIX):])
    return float(pc.get("price_in") or 0), float(pc.get("price_out") or 0), float(pc.get("price_search") or 0)


def ensure_ready(cfg: dict[str, Any], choice: str) -> None:
    if not choice.startswith(PREFIX):
        if not ai_client.has_api_key():
            raise UserFacingError("No Claude API key is saved. Add it in Settings > AI providers.")
        return
    pid = choice[len(PREFIX):]
    if PROVIDERS[pid].needs_key and not key_saved(pid):
        raise UserFacingError(f"No API key is saved for {PROVIDERS[pid].label}. Add it in Settings > AI providers.")


# --------------------------------------------------------------------------- requests
def _target(cfg: dict[str, Any]) -> tuple[str, Provider, dict[str, Any], str]:
    choice = current(cfg)
    pid = choice[len(PREFIX):]
    p = PROVIDERS[pid]
    pc = provider_cfg(cfg, pid)
    pc["base_url"] = check_url(pc["base_url"])
    pc["model"] = check_model(pc.get("model", ""))
    host = urlparse(pc["base_url"]).hostname or ""
    netguard.allow_host(host)
    return pid, p, pc, get_key(pid)


def count_input_tokens(system_prompt: str, content: list[dict[str, Any]], cfg: dict[str, Any], use_web_search: bool) -> int:
    """Input size for the cost question (exact where the provider can count, else a local estimate)."""
    if not current(cfg).startswith(PREFIX):
        return ai_client.count_input_tokens(system_prompt, content, cfg, use_web_search)
    pid, p, pc, key = _target(cfg)
    try:
        if p.kind == "openai":
            from . import ai_openai

            return ai_openai.count_tokens(system_prompt, content, pc, key, use_web_search)
        if p.kind == "gemini":
            from . import ai_gemini

            return ai_gemini.count_tokens(system_prompt, content, pc, key)
    except Exception:
        log.warning("Token count unavailable for %s; using a local estimate", pid)
    return local_estimate(system_prompt, content)


def local_estimate(system_prompt: str, content: list[dict[str, Any]]) -> int:
    chars = len(system_prompt) + sum(len(b.get("text", "")) for b in content)
    pdf_chars = sum(len(b["source"]["data"]) for b in content if b.get("type") == "document")
    return int(chars / 3.5 + pdf_chars / 40)


def draft_reply(system_prompt: str, content: list[dict[str, Any]], cfg: dict[str, Any], use_web_search: bool,
                progress: Progress | None = None) -> DraftResult:
    """Send the drafting request to the chosen provider."""
    choice = current(cfg)
    if not choice.startswith(PREFIX):
        return ai_client.draft_reply(system_prompt, content, cfg, use_web_search, progress)
    progress = progress or (lambda _p, _m="": None)
    pid, p, pc, key = _target(cfg)
    if p.needs_key and not key:
        raise UserFacingError(f"No API key is saved for {p.label}. Add it in Settings > AI providers.")
    if not p.pdf:
        content = [b for b in content if b.get("type") != "document"]
    web = use_web_search and p.web
    max_tokens = int(pc.get("max_tokens") or 0) or (int(cfg["ai"]["max_tokens"]) if p.kind != "compat" else 0)
    web_max = int(cfg["ai"]["web_search_max_uses"])
    if p.kind == "openai":
        from . import ai_openai

        result = ai_openai.draft_responses(system_prompt, content, pc, key, web, web_max, max_tokens, p.label, progress)
    elif p.kind == "gemini":
        from . import ai_gemini

        result = ai_gemini.draft(system_prompt, content, pc, key, web, max_tokens, p.label, progress)
    else:
        from . import ai_openai

        result = ai_openai.draft_compat(system_prompt, content, pc, key, max_tokens, p.label, progress)
    result.requested_model = choice
    result.prices = prices(cfg, choice)
    if not result.text:
        raise UserFacingError(f"{p.label} returned an empty answer. Please try again.")
    if not any(m in result.text for m in ("<<<FRAMING>>>", "<<<REPLY>>>", "<<<ADVISORY>>>", "<<<LAW_NOTE>>>")):
        result.notes.append("This model did not use Mukhota's section markers, so the whole answer is in the first "
                            "tab; move any advisory part out by hand before saving.")
    log.info("Draft received from provider %s: in=%d out=%d searches=%d truncated=%s",
             pid, result.input_tokens, result.output_tokens, result.searches, result.truncated)
    return result
