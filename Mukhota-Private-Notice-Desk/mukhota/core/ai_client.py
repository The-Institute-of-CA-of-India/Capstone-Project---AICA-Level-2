"""The only Mukhota module that uses the network: calls the Claude API for Draft Reply.

Only content that has already passed verification (tokens, no PII) reaches here.
"""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from . import netguard
from .models import UserFacingError

log = logging.getLogger("mukhota.ai")
Progress = Callable[[int, str], None]

API_HOST = "api.anthropic.com"
KEYRING_SERVICE = "Mukhota"
KEYRING_USER = "anthropic-api-key"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
PRICE_SEARCH = 0.01  # US$ per web search
MAX_PAUSE_CONTINUATIONS = 4


@dataclass(frozen=True)
class ModelInfo:
    """Selectable model: label, US$ per million input/output tokens, and API capabilities."""

    label: str
    price_in: float
    price_out: float
    server_fallback: bool
    web_search_tool: str


MODELS: dict[str, ModelInfo] = {
    "claude-opus-5-5": ModelInfo("Claude Opus 5.5 - best quality", 4.00, 20.00, True, "web_search_20260209"),
    "claude-sonnet-5-5": ModelInfo("Claude Sonnet 5.5 - good quality, about half the cost", 2.00, 10.00, True, "web_search_20260209"),
    # Haiku 5.5 has no server-side refusal fallback and uses the basic web search tool.
    "claude-haiku-5-5": ModelInfo("Claude Haiku 5.5 - cheapest, for testing", 0.10, 0.50, False, "web_search_20250305"),
}


@dataclass
class DraftResult:
    """Claude's answer (token text only) and usage figures."""

    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    searches: int = 0
    truncated: bool = False
    notes: list[str] = field(default_factory=list)
    requested_model: str = ""
    prices: tuple[float, float, float] | None = None  # (in, out per M tokens, per search) for non-Claude providers

    @property
    def cost_usd(self) -> float:
        if self.prices is not None:
            p_in, p_out, p_search = self.prices
        else:
            info = MODELS.get(self.requested_model) or MODELS["claude-opus-5-5"]
            p_in, p_out, p_search = info.price_in, info.price_out, PRICE_SEARCH
        return (self.input_tokens * p_in + self.output_tokens * p_out) / 1e6 + self.searches * p_search


# --------------------------------------------------------------------------- API key

def set_api_key(key: str) -> None:
    """Store the API key in Windows Credential Manager."""
    import keyring

    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USER, key.strip())
    except Exception as exc:
        raise UserFacingError("The API key could not be saved in Windows Credential Manager.") from exc


def clear_api_key() -> None:
    """Remove the stored API key."""
    import keyring

    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:
        pass


def _get_api_key() -> str:
    import keyring

    try:
        key = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:
        key = None
    if not key:
        raise UserFacingError("No Claude API key is saved. Add it in Settings > Claude API.")
    return key


def has_api_key() -> bool:
    """True if a key is stored."""
    try:
        return bool(_get_api_key())
    except UserFacingError:
        return False


# --------------------------------------------------------------------------- request

def build_content(pdf_bytes: bytes | None, pdf_name: str, text: str | None, user_text: str) -> list[dict[str, Any]]:
    """User message content: optional PDF document block, optional extracted text, then instructions."""
    content: list[dict[str, Any]] = []
    if pdf_bytes is not None:
        content.append({
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.standard_b64encode(pdf_bytes).decode("ascii"),
            },
            "title": pdf_name,
        })
    if text is not None:
        content.append({"type": "text", "text": f"<notice_text>\n{text}\n</notice_text>"})
    content.append({"type": "text", "text": user_text})
    return content


def count_input_tokens(system_prompt: str, content: list[dict[str, Any]], cfg: dict[str, Any], use_web_search: bool) -> int:
    """Exact input size via Anthropic's free token-counting call; rough local count if that fails."""
    import anthropic

    ai = cfg["ai"]
    model = ai["model"] if ai["model"] in MODELS else "claude-opus-5-5"
    try:
        netguard.allow_host(API_HOST)
        client = anthropic.Anthropic(api_key=_get_api_key(), max_retries=1, timeout=60.0)
        kwargs: dict[str, Any] = dict(model=model, system=system_prompt, messages=[{"role": "user", "content": content}])
        if use_web_search:
            kwargs["tools"] = [{"type": MODELS[model].web_search_tool, "name": "web_search",
                                "max_uses": int(ai["web_search_max_uses"])}]
        return int(client.beta.messages.count_tokens(**kwargs).input_tokens)
    except Exception:
        log.warning("Token count unavailable; using a local estimate")
        chars = len(system_prompt) + sum(len(b.get("text", "")) for b in content)
        pdf_chars = sum(len(b["source"]["data"]) for b in content if b.get("type") == "document")
        return int(chars / 3.5 + pdf_chars / 40)


def draft_reply(
    system_prompt: str,
    content: list[dict[str, Any]],
    cfg: dict[str, Any],
    use_web_search: bool,
    progress: Progress | None = None,
) -> DraftResult:
    """Send one drafting request (streaming) and return the combined text."""
    progress = progress or (lambda _p, _m="": None)
    import anthropic

    ai = cfg["ai"]
    model = ai["model"] if ai["model"] in MODELS else "claude-opus-5-5"
    info = MODELS[model]
    netguard.allow_host(API_HOST)
    client = anthropic.Anthropic(api_key=_get_api_key(), max_retries=2, timeout=900.0)

    tools: list[dict[str, Any]] = []
    if use_web_search:
        tools.append({"type": info.web_search_tool, "name": "web_search", "max_uses": int(ai["web_search_max_uses"])})

    messages: list[dict[str, Any]] = [{"role": "user", "content": content}]
    result = DraftResult("", model, requested_model=model)
    parts: list[str] = []
    words = 0
    progress(5, "Sending the redacted notice to Claude...")
    try:
        for _turn in range(MAX_PAUSE_CONTINUATIONS + 1):
            kwargs: dict[str, Any] = dict(
                model=model,
                max_tokens=int(ai["max_tokens"]),
                system=system_prompt,
                messages=messages,
                output_config={"effort": ai["effort"]},
            )
            if info.server_fallback:
                kwargs["betas"] = [FALLBACK_BETA]
                kwargs["fallbacks"] = "default"
            if tools:
                kwargs["tools"] = tools
            with client.beta.messages.stream(**kwargs) as stream:
                for chunk in stream.text_stream:
                    words += chunk.count(" ")
                    progress(min(10 + words // 40, 95), f"Claude is drafting... about {words} words so far")
                final = stream.get_final_message()

            result.input_tokens += final.usage.input_tokens or 0
            result.output_tokens += final.usage.output_tokens or 0
            stu = getattr(final.usage, "server_tool_use", None)
            result.searches += int(getattr(stu, "web_search_requests", 0) or 0)
            result.model = final.model
            parts.extend(b.text for b in final.content if b.type == "text")

            if final.stop_reason == "refusal":
                raise UserFacingError(
                    "Claude declined this request. Try again with Text only, or shorten the facts you typed."
                )
            if final.stop_reason == "pause_turn":
                # Long web-search turns pause; send the turn back so Claude continues.
                messages = messages + [{"role": "assistant", "content": final.content}]
                continue
            if final.stop_reason == "max_tokens":
                result.truncated = True
                result.notes.append("The answer hit the length limit and may be cut short.")
            break
    except UserFacingError:
        raise
    except anthropic.AuthenticationError as exc:
        raise UserFacingError("The Claude API key was rejected. Check it in Settings > Claude API.") from exc
    except anthropic.PermissionDeniedError as exc:
        raise UserFacingError("This API key is not allowed to use the selected model.") from exc
    except anthropic.RateLimitError as exc:
        raise UserFacingError("Claude API rate limit or credit limit reached. Wait a minute or check your API credits.") from exc
    except anthropic.BadRequestError as exc:
        log.warning("Claude API rejected the request (400)")
        raise UserFacingError(
            "Claude could not accept this request (it may be too large). Try 'Text only'."
        ) from exc
    except anthropic.APIConnectionError as exc:
        raise UserFacingError(
            "Could not reach the Claude API. Check the internet connection (a proxy or VPN may block it)."
        ) from exc
    except anthropic.APIStatusError as exc:
        raise UserFacingError("The Claude API returned an error. Please try again in a few minutes.") from exc

    result.text = "".join(parts).strip()
    if not result.text:
        raise UserFacingError("Claude returned an empty answer. Please try again.")
    progress(100, "Draft received")
    log.info(
        "Draft received: model=%s in=%d out=%d searches=%d truncated=%s",
        result.model, result.input_tokens, result.output_tokens, result.searches, result.truncated,
    )
    return result
