#!/usr/bin/env python3
"""Measure how many context tokens a skill costs at each loading level.

  Level 1  metadata (name + description) -> in context every session, always
  Level 2  SKILL.md body                 -> loaded when the skill triggers
  Level 3  references / assets / scripts -> only when Claude opens the file
           (scripts that are only *executed* cost nothing except their output)

Examples
  python skill_footprint.py ~/.claude/skills/wht-extractor
  python skill_footprint.py ~/.claude/skills --model claude-sonnet-5 --fx 32.5
  python skill_footprint.py ./my-skill --files          # per-file detail
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tm_common import Counter, fmt_thb, fmt_usd, load_pricing, price_for_model  # noqa: E402

TEXT_EXT = {".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".py", ".js", ".ts",
            ".sh", ".html", ".xml", ".sql", ".toml", ".ini"}
SKIP_DIRS = {"__pycache__", "node_modules", ".git", "evals"}


def split_frontmatter(text: str):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[3:end].strip(), text[end + 4:].lstrip("\n")
    return "", text


def meta_fields(fm: str) -> str:
    """name + description as they appear in the skills list."""
    keep, grab = [], False
    for line in fm.splitlines():
        if line.startswith(("name:", "description:")):
            keep.append(line)
            grab = line.startswith("description:")
        elif grab and (line.startswith((" ", "\t")) or not line.strip()):
            keep.append(line)
        else:
            grab = False
    return "\n".join(keep)


def find_skills(root: Path):
    if (root / "SKILL.md").exists():
        return [root]
    return sorted(p.parent for p in root.rglob("SKILL.md")
                  if not SKIP_DIRS & set(p.parts))


def measure(skill: Path, counter: Counter):
    text = (skill / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    fm, body = split_frontmatter(text)
    res = {"skill": skill.name, "meta": counter.count(meta_fields(fm)),
           "body": counter.count(body), "files": []}
    for p in sorted(skill.rglob("*")):
        if not p.is_file() or p.name == "SKILL.md" or SKIP_DIRS & set(p.relative_to(skill).parts):
            continue
        rel = str(p.relative_to(skill))
        if p.suffix.lower() in TEXT_EXT:
            tok = counter.count(p.read_text(encoding="utf-8", errors="replace"))
            kind = "script (run)" if rel.startswith("scripts") else "reference (read)"
        else:
            tok, kind = None, f"binary {p.stat().st_size/1024:,.0f} KB"
        res["files"].append((rel, kind, tok))
    res["l3_read"] = sum(t for _, k, t in res["files"] if t and k.startswith("reference"))
    res["l3_scripts"] = sum(t for _, k, t in res["files"] if t and k.startswith("script"))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="a skill folder, or a folder containing many skills")
    ap.add_argument("--model", default="claude-sonnet-5", help="model for pricing / count_tokens")
    ap.add_argument("--fx", type=float, help="USD->THB rate")
    ap.add_argument("--files", action="store_true", help="per-file detail")
    ap.add_argument("--estimate", action="store_true", help="force offline estimate")
    ap.add_argument("--pricing")
    a = ap.parse_args()

    pricing = load_pricing(a.pricing)
    price = price_for_model(a.model, pricing)
    if not price:
        sys.exit(f"ไม่มีราคาของโมเดล {a.model} ใน pricing.json")
    in_rate = price["input"] / 1e6
    cr_rate = price.get("cache_read", price["input"] * pricing["multipliers"]["cache_read"]) / 1e6

    skills = find_skills(Path(a.path).expanduser())
    if not skills:
        sys.exit("ไม่พบ SKILL.md")
    counter = Counter(a.model, force_estimate=a.estimate)
    results = [measure(s, counter) for s in skills]

    print(f"model: {a.model} (input ${price['input']}/MTok) · token count: {counter.mode}\n")
    head = ["skill", "L1 meta (always)", "L2 SKILL.md (on trigger)", "L3 refs (if read)",
            "L3 scripts (if read)", "trigger cost USD", "cached USD", "THB"]
    print("| " + " | ".join(head) + " |\n" + "|---" * len(head) + "|")
    tot_meta = 0
    for r in results:
        tot_meta += r["meta"]
        c = r["body"] * in_rate
        print(f"| {r['skill']} | {r['meta']:,} | {r['body']:,} | {r['l3_read']:,} | "
              f"{r['l3_scripts']:,} | {fmt_usd(c)} | {fmt_usd(r['body'] * cr_rate)} | {fmt_thb(c, a.fx)} |")
    if len(results) > 1:
        print(f"\nรวม L1 ของทุก skill ({len(results)} ตัว) ที่โหลดทุก session: {tot_meta:,} tokens "
              f"≈ {fmt_usd(tot_meta * in_rate)} ต่อ request ที่ไม่ได้ cache")
    print("\n_trigger cost = ค่า input ของ SKILL.md หนึ่งครั้ง (ยังไม่รวม output และไฟล์ L3)_")
    print("_cached = ราคาเมื่อ SKILL.md อยู่ใน prompt cache แล้ว (turn ถัด ๆ ไปใน session เดียวกัน)_")

    if a.files:
        for r in results:
            print(f"\n### {r['skill']}\n\n| file | type | tokens |\n|---|---|---|")
            for rel, kind, tok in r["files"]:
                print(f"| {rel} | {kind} | {'-' if tok is None else f'{tok:,}'} |")

    warn = [r["skill"] for r in results if r["body"] > 5000]
    if warn:
        print(f"\n⚠️ SKILL.md ยาวเกิน ~5,000 tokens: {', '.join(warn)} — พิจารณาย้ายรายละเอียดไป references/")


if __name__ == "__main__":
    main()
