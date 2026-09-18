#!/usr/bin/env python3
"""Count tokens and input cost for any prompt / system prompt / memory / CLAUDE.md file.

Examples
  python count_prompt.py CLAUDE.md system_prompt.txt
  python count_prompt.py --text "สรุปใบกำกับภาษีนี้ให้หน่อย" --model claude-opus-5
  python count_prompt.py ~/.claude/CLAUDE.md --calls 200 --fx 32.5   # cost if sent 200 times
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tm_common import Counter, fmt_thb, fmt_usd, load_pricing, price_for_model  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--text", action="append", default=[], help="inline text (repeatable)")
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--calls", type=int, default=1, help="multiply cost by N requests")
    ap.add_argument("--fx", type=float)
    ap.add_argument("--estimate", action="store_true")
    ap.add_argument("--pricing")
    a = ap.parse_args()

    items = [(f, Path(f).expanduser().read_text(encoding="utf-8", errors="replace")) for f in a.files]
    items += [(f"text#{i+1}", t) for i, t in enumerate(a.text)]
    if not items:
        sys.exit("ระบุไฟล์หรือ --text อย่างน้อยหนึ่งรายการ")

    pricing = load_pricing(a.pricing)
    price = price_for_model(a.model, pricing)
    if not price:
        sys.exit(f"ไม่มีราคาของโมเดล {a.model}")
    rate = price["input"] / 1e6
    cr = price.get("cache_read", price["input"] * pricing["multipliers"]["cache_read"]) / 1e6
    c = Counter(a.model, force_estimate=a.estimate)

    print(f"model: {a.model} · {c.mode} · × {a.calls} call(s)\n")
    print("| item | chars | tokens | input USD | cached USD | THB |\n|---|---|---|---|---|---|")
    tot = 0
    for name, text in items:
        n = c.count(text)
        tot += n
        usd = n * rate * a.calls
        print(f"| {name} | {len(text):,} | {n:,} | {fmt_usd(usd)} | {fmt_usd(n * cr * a.calls)} | {fmt_thb(usd, a.fx)} |")
    if len(items) > 1:
        usd = tot * rate * a.calls
        print(f"| **TOTAL** | | {tot:,} | {fmt_usd(usd)} | {fmt_usd(tot * cr * a.calls)} | {fmt_thb(usd, a.fx)} |")


if __name__ == "__main__":
    main()
