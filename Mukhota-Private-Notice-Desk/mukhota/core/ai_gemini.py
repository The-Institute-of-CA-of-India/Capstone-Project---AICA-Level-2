"""Google Gemini (google-genai SDK): PDF as an inline part, grounding with Google Search.

Called only through core.ai, after the network guard has opened the provider's host.
"""
from __future__ import annotations

import base64
import logging
from typing import Any, Callable

from .ai_client import DraftResult
from .models import UserFacingError

log = logging.getLogger("mukhota.ai")
Progress = Callable[[int, str], None]
REFUSALS = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"}


def _client(pc: dict[str, Any], key: str, timeout_s: int):
    from google import genai
    from google.genai import types

    return genai.Client(api_key=key, http_options=types.HttpOptions(base_url=pc["base_url"] + "/", timeout=timeout_s * 1000))


def _parts(content: list[dict[str, Any]]) -> list[Any]:
    from google.genai import types

    parts: list[Any] = []
    for b in content:
        if b.get("type") == "document":
            parts.append(types.Part.from_bytes(data=base64.b64decode(b["source"]["data"]), mime_type="application/pdf"))
        elif b.get("type") == "text":
            parts.append(types.Part.from_text(text=b["text"]))
    return parts


def _friendly(exc: Exception, name: str) -> UserFacingError:
    code = int(getattr(exc, "code", 0) or 0)
    if code in (401, 403):
        return UserFacingError(f"The {name} API key was rejected. Check it in Settings > AI providers.")
    if code == 404:
        return UserFacingError(f"{name} did not accept the model name. Check it in Settings > AI providers.")
    if code == 429:
        return UserFacingError(f"{name} rate limit or quota reached. Wait a minute or check your account.")
    if code == 400:
        log.warning("%s rejected the request (400)", name)
        return UserFacingError(f"{name} could not accept this request (it may be too large). Try 'Text only'.")
    return UserFacingError(f"{name} returned an error. Please try again in a few minutes.")


def count_tokens(system_prompt: str, content: list[dict[str, Any]], pc: dict[str, Any], key: str) -> int:
    from google.genai import types

    client = _client(pc, key, 60)
    # The system prompt is counted as an ordinary part (the Gemini API does not count system_instruction).
    parts = [types.Part.from_text(text=system_prompt)] + _parts(content)
    return int(client.models.count_tokens(model=pc["model"], contents=parts).total_tokens or 0)


def draft(system_prompt: str, content: list[dict[str, Any]], pc: dict[str, Any], key: str, web: bool,
          max_tokens: int, name: str, progress: Progress) -> DraftResult:
    """Streaming generate_content; Google Search grounding when web search is ticked."""
    from google.genai import errors, types

    client = _client(pc, key, 900)
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        max_output_tokens=max_tokens or None,
        tools=[types.Tool(google_search=types.GoogleSearch())] if web else None,
    )
    result = DraftResult("", pc["model"])
    parts: list[str] = []
    queries: set[str] = set()
    words = 0
    finish = ""
    usage = None
    progress(5, f"Sending the redacted notice to {name}...")
    try:
        for chunk in client.models.generate_content_stream(model=pc["model"], contents=_parts(content), config=config):
            for cand in chunk.candidates or []:
                for part in (cand.content.parts if cand.content and cand.content.parts else []):
                    if part.text and not part.thought:
                        parts.append(part.text)
                        words += part.text.count(" ")
                gm = cand.grounding_metadata
                if gm and gm.web_search_queries:
                    queries.update(gm.web_search_queries)
                if cand.finish_reason:
                    finish = getattr(cand.finish_reason, "name", str(cand.finish_reason))
            if chunk.usage_metadata:
                usage = chunk.usage_metadata
            if chunk.model_version:
                result.model = chunk.model_version
            progress(min(10 + words // 40, 95), f"{name} is drafting... about {words} words so far")
    except errors.APIError as exc:
        raise _friendly(exc, name) from exc
    result.text = "".join(parts).strip()
    if finish in REFUSALS and not result.text:
        raise UserFacingError(f"{name} declined this request. Try again with Text only, or shorten the facts you typed.")
    if usage is not None:
        result.input_tokens = (usage.prompt_token_count or 0) + (usage.tool_use_prompt_token_count or 0)
        result.output_tokens = (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
    result.searches = len(queries)
    if finish == "MAX_TOKENS":
        result.truncated = True
        result.notes.append("The answer hit the length limit and may be cut short.")
    progress(100, "Draft received")
    return result
