"""OpenAI (Responses API: PDF + web search) and OpenAI-compatible providers (chat completions, text only).

Called only through core.ai, after the network guard has opened the provider's host.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from .ai_client import DraftResult
from .models import UserFacingError

log = logging.getLogger("mukhota.ai")
Progress = Callable[[int, str], None]


def _client(pc: dict[str, Any], key: str, timeout: float, retries: int = 2):
    from openai import OpenAI

    # Local servers (Ollama, LM Studio) accept any key.
    return OpenAI(api_key=key or "not-needed", base_url=pc["base_url"], max_retries=retries, timeout=timeout)


def _responses_input(content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mukhota's content blocks (Claude format) as one Responses API user message."""
    parts: list[dict[str, Any]] = []
    for b in content:
        if b.get("type") == "document":
            parts.append({"type": "input_file", "filename": b.get("title") or "notice.pdf",
                          "file_data": f"data:application/pdf;base64,{b['source']['data']}"})
        elif b.get("type") == "text":
            parts.append({"type": "input_text", "text": b["text"]})
    return [{"role": "user", "content": parts}]


def _plain_text(content: list[dict[str, Any]]) -> str:
    return "\n\n".join(b["text"] for b in content if b.get("type") == "text")


def _reason(exc: Exception) -> str:
    """The provider's own one-line explanation (e.g. 'Model Not Exist'); it never contains client data."""
    body = getattr(exc, "body", None)
    msg = ""
    if isinstance(body, dict):
        err = body.get("error", body)
        msg = err.get("message", "") if isinstance(err, dict) else str(err)
    msg = " ".join(str(msg or getattr(exc, "message", "") or "").split())
    return f"\n\nThe provider said: {msg[:200]}" if msg else ""


def _friendly(exc: Exception, name: str, pdf_web: bool = False) -> UserFacingError:
    import openai

    reason = _reason(exc)
    if isinstance(exc, openai.AuthenticationError):
        return UserFacingError(f"The {name} API key was rejected. Check it in Settings > AI providers.{reason}")
    if isinstance(exc, (openai.PermissionDeniedError, openai.NotFoundError)):
        return UserFacingError(f"{name} did not accept the model name. Use the exact model ID from the provider's "
                               f"documentation in Settings > AI providers.{reason}")
    if isinstance(exc, openai.RateLimitError):
        return UserFacingError(f"{name} rate limit or credit limit reached. Wait a minute or check your account.{reason}")
    if isinstance(exc, openai.BadRequestError):
        log.warning("%s rejected the request (400)", name)
        hint = ("Try 'Text only' or untick web search." if pdf_web else
                "Check the model name in Settings > AI providers; it must be the exact model ID.")
        return UserFacingError(f"{name} could not accept this request. {hint}{reason}")
    if isinstance(exc, openai.APIStatusError) and exc.status_code == 402:
        return UserFacingError(f"{name} says the account has no balance left. Top up the account.{reason}")
    if isinstance(exc, openai.APIConnectionError):
        return UserFacingError(f"Could not reach {name}. Check the internet connection, or that the local model "
                               "server is running.")
    return UserFacingError(f"{name} returned an error. Please try again in a few minutes.")


def count_tokens(system_prompt: str, content: list[dict[str, Any]], pc: dict[str, Any], key: str, web: bool) -> int:
    client = _client(pc, key, 60.0, retries=1)
    kwargs: dict[str, Any] = dict(model=pc["model"], instructions=system_prompt, input=_responses_input(content))
    if web:
        kwargs["tools"] = [{"type": "web_search"}]
    return int(client.responses.input_tokens.count(**kwargs).input_tokens)


def draft_responses(system_prompt: str, content: list[dict[str, Any]], pc: dict[str, Any], key: str, web: bool,
                    web_max: int, max_tokens: int, name: str, progress: Progress) -> DraftResult:
    """OpenAI Responses API, streaming; the PDF is attached as an input file."""
    import openai

    client = _client(pc, key, 900.0)
    kwargs: dict[str, Any] = dict(model=pc["model"], instructions=system_prompt, input=_responses_input(content))
    if max_tokens:
        kwargs["max_output_tokens"] = max_tokens
    if web:
        kwargs["tools"] = [{"type": "web_search"}]
        kwargs["max_tool_calls"] = max(1, web_max)
    result = DraftResult("", pc["model"])
    words = 0
    progress(5, f"Sending the redacted notice to {name}...")
    try:
        with client.responses.stream(**kwargs) as stream:
            for event in stream:
                if event.type == "response.output_text.delta":
                    words += event.delta.count(" ")
                    progress(min(10 + words // 40, 95), f"{name} is drafting... about {words} words so far")
            final = stream.get_final_response()
    except openai.OpenAIError as exc:
        raise _friendly(exc, name, pdf_web=True) from exc
    result.text = (final.output_text or "").strip()
    result.model = final.model or pc["model"]
    if final.usage is not None:
        result.input_tokens = final.usage.input_tokens or 0
        result.output_tokens = final.usage.output_tokens or 0
    result.searches = sum(1 for item in final.output or [] if getattr(item, "type", "") == "web_search_call")
    if final.status == "incomplete":
        reason = getattr(final.incomplete_details, "reason", "") or ""
        if reason == "content_filter":
            raise UserFacingError(f"{name} declined this request. Try again with Text only, or shorten the facts you typed.")
        result.truncated = True
        result.notes.append("The answer hit the length limit and may be cut short.")
    progress(100, "Draft received")
    return result


def draft_compat(system_prompt: str, content: list[dict[str, Any]], pc: dict[str, Any], key: str, max_tokens: int,
                 name: str, progress: Progress) -> DraftResult:
    """OpenAI-compatible chat completions (DeepSeek, Mistral, Groq, OpenRouter, local models...), text only."""
    import openai

    client = _client(pc, key, 900.0)
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": _plain_text(content)}]
    kwargs: dict[str, Any] = dict(model=pc["model"], messages=messages, stream=True,
                                  stream_options={"include_usage": True})
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    result = DraftResult("", pc["model"])
    parts: list[str] = []
    words = 0
    finish = ""
    progress(5, f"Sending the redacted notice text to {name}...")
    try:
        try:
            stream = client.chat.completions.create(**kwargs)
        except openai.BadRequestError as exc:
            # Some servers reject stream_options; retry once without it (only when that is the complaint).
            if "stream" not in _reason(exc).lower():
                raise
            kwargs.pop("stream_options")
            stream = client.chat.completions.create(**kwargs)
        for chunk in stream:
            if getattr(chunk, "usage", None):
                result.input_tokens = chunk.usage.prompt_tokens or 0
                result.output_tokens = chunk.usage.completion_tokens or 0
            for choice in chunk.choices or []:
                delta = getattr(choice.delta, "content", None) or ""
                if delta:
                    parts.append(delta)
                    words += delta.count(" ")
                    progress(min(10 + words // 40, 95), f"{name} is drafting... about {words} words so far")
                if choice.finish_reason:
                    finish = choice.finish_reason
            if getattr(chunk, "model", None):
                result.model = chunk.model
    except openai.OpenAIError as exc:
        raise _friendly(exc, name) from exc
    result.text = "".join(parts).strip()
    if finish == "content_filter":
        raise UserFacingError(f"{name} declined this request. Try again, or shorten the facts you typed.")
    if finish == "length":
        result.truncated = True
        result.notes.append("The answer hit the length limit and may be cut short. Raise 'Max output tokens' "
                            "for this provider in Settings.")
    if not result.input_tokens and result.text:
        result.notes.append("This provider did not report token usage; the cost shown is an estimate.")
        result.input_tokens = int((len(system_prompt) + len(_plain_text(content))) / 3.5)
        result.output_tokens = int(len(result.text) / 3.5)
    progress(100, "Draft received")
    return result
