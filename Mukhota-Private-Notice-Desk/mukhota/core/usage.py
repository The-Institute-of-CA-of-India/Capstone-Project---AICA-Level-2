"""Claude API spend tracking and cost estimates (amounts and dates only - no client data)."""
from __future__ import annotations

import json
import logging
from datetime import date

from .config import APP_ROOT

log = logging.getLogger("mukhota.usage")
USAGE_PATH = APP_ROOT / "usage.json"

# Typical output size per mode, used only for the estimate shown before sending.
EXPECTED_OUTPUT_TOKENS = {"framing": 2500, "reply": 5000, "advisory": 4000, "law": 6000}
SEARCH_RESULT_TOKENS = 3000  # rough input added per web search


def _month() -> str:
    return date.today().strftime("%Y-%m")


def _load() -> dict:
    try:
        return json.loads(USAGE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def month_spend() -> float:
    """US$ spent on drafts this calendar month."""
    return float(_load().get(_month(), {}).get("usd", 0.0))


def record(cost_usd: float) -> None:
    """Add one draft's cost to this month's total."""
    data = _load()
    m = data.setdefault(_month(), {"usd": 0.0, "drafts": 0})
    m["usd"] = round(m["usd"] + cost_usd, 4)
    m["drafts"] += 1
    try:
        USAGE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        log.warning("usage.json could not be written")


def estimate(price_in: float, price_out: float, input_tokens: int, output_mode: str, web_max: int,
             price_search: float = 0.01) -> tuple[float, float]:
    """(typical, worst case) US$ for one draft. Typical assumes up to 2 web searches; worst assumes all."""
    out = sum(EXPECTED_OUTPUT_TOKENS.get(k, 0) for k in output_mode.split("+")) or 9000

    def cost(searches: int, out_tokens: int) -> float:
        tokens_in = input_tokens + searches * SEARCH_RESULT_TOKENS
        return (tokens_in * price_in + out_tokens * price_out) / 1e6 + searches * price_search

    return cost(min(web_max, 2), out), cost(web_max, out * 2)
