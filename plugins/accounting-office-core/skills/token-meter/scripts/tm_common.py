"""Shared helpers for token-meter: pricing lookup, cost calculation, token counting.

Token counting has two modes:
  * exact    -> Anthropic count_tokens API (needs ANTHROPIC_API_KEY)
  * estimate -> character heuristic, clearly labelled as an estimate
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
PRICING_FILE = SKILL_DIR / "references" / "pricing.json"

THAI_RE = re.compile(r"[\u0E00-\u0E7F]")


# ---------------------------------------------------------------- pricing
def load_pricing(path: str | None = None) -> dict:
    with open(path or PRICING_FILE, encoding="utf-8") as f:
        return json.load(f)


def price_for_model(model: str | None, pricing: dict) -> dict | None:
    """Match a model id to a pricing row by the longest matching key."""
    if not model:
        return None
    model = model.lower()
    best = None
    for key, row in pricing["models"].items():
        if key in model and (best is None or len(key) > len(best[0])):
            best = (key, row)
    return best[1] if best else None


def cost_usd(usage: dict, price: dict | None, pricing: dict) -> float | None:
    """Cost of one usage block. Returns None when the model has no price row."""
    if price is None:
        return None
    m = pricing["multipliers"]
    per = 1_000_000
    inp = price["input"] / per
    out = price["output"] / per
    cache_read_rate = price.get("cache_read", price["input"] * m["cache_read"]) / per

    cw5 = usage.get("cache_write_5m", 0)
    cw1h = usage.get("cache_write_1h", 0)
    return (
        usage.get("input", 0) * inp
        + usage.get("output", 0) * out
        + cw5 * inp * m["cache_write_5m"]
        + cw1h * inp * m["cache_write_1h"]
        + usage.get("cache_read", 0) * cache_read_rate
    )


# ---------------------------------------------------------- token counting
def estimate_tokens(text: str) -> int:
    """Rough estimate. Thai script tokenizes far denser than English."""
    thai = len(THAI_RE.findall(text))
    other = len(text) - thai
    return round(thai / 1.5 + other / 3.3)


def api_count_tokens(text: str, model: str, system: str | None = None) -> int:
    body = {"model": model, "messages": [{"role": "user", "content": text or "."}]}
    if system is not None:
        body["system"] = system
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages/count_tokens",
        data=json.dumps(body).encode(),
        headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["input_tokens"]


class Counter:
    """Counts tokens of a text block, exact if an API key is available."""

    def __init__(self, model: str, force_estimate: bool = False):
        self.model = model
        self.exact = bool(os.environ.get("ANTHROPIC_API_KEY")) and not force_estimate
        self._baseline = None

    @property
    def mode(self) -> str:
        return "exact (count_tokens API)" if self.exact else "estimate (±30%)"

    def count(self, text: str) -> int:
        if not text:
            return 0
        if not self.exact:
            return estimate_tokens(text)
        try:
            if self._baseline is None:
                # Overhead of the message wrapper itself, subtracted from every count
                self._baseline = api_count_tokens(".", self.model)
            return max(0, api_count_tokens(text, self.model) - self._baseline)
        except Exception as e:  # network / auth problem -> fall back, but say so
            print(f"[token-meter] count_tokens API failed ({e}); falling back to estimate")
            self.exact = False
            return estimate_tokens(text)


def fmt_usd(x: float | None) -> str:
    return "n/a" if x is None else f"${x:,.4f}"


def fmt_thb(x: float | None, fx: float | None) -> str:
    return "" if x is None or not fx else f"฿{x * fx:,.2f}"
