"""หัวไฟล์ที่ต้องใส่ในทุกไฟล์ที่ plugin สร้าง (กฎบังคับข้อ 5)

เวอร์ชันอ่านจาก .claude-plugin/plugin.json เสมอ ไม่ hardcode —
ก่อนหน้านี้ prose ใน SKILL.md เขียน v1.1.0 ค้างไว้ขณะที่ manifest เป็น 1.2.0 แล้ว

สำเนาไฟล์นี้ต้องตรงกันทั้ง 3 plugin — ดู scripts/sync_hooks_lib.py
"""
from __future__ import annotations

import datetime
import json
import os
import re

HEADER_RE = re.compile(r"accounting-office-[a-z]+\s+v\d+\.\d+\.\d+")

_cache = {}


def plugin_root():
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env and os.path.isdir(env):
        return env
    # lib/ -> hooks/ -> <plugin root>
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def plugin_meta(root=None):
    root = root or plugin_root()
    if root in _cache:
        return _cache[root]
    name, version = "accounting-office", "0.0.0"
    try:
        with open(os.path.join(root, ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        name = data.get("name") or name
        version = data.get("version") or version
    except Exception:
        pass
    _cache[root] = (name, version)
    return name, version


def thai_today(today=None):
    d = today or datetime.date.today()
    return "%04d-%02d-%02d" % (d.year + 543, d.month, d.day)


def header_line(root=None, today=None):
    name, version = plugin_meta(root)
    return "%s v%s — %s" % (name, version, thai_today(today))


def has_header(content, lines=5):
    """หัวไฟล์ต้องอยู่ใน 5 บรรทัดแรก"""
    head = "\n".join(str(content or "").splitlines()[:lines])
    return bool(HEADER_RE.search(head))


def comment_header(path, root=None, today=None):
    """คืนหัวไฟล์ในรูปคอมเมนต์ที่เหมาะกับนามสกุลไฟล์ — คืน None ถ้าไม่รู้จักนามสกุล"""
    line = header_line(root, today)
    ext = os.path.splitext(str(path or ""))[1].lower()
    if ext in (".md", ".markdown", ".html"):
        return "<!-- %s -->" % line
    if ext in (".txt", ".csv", ".py", ".sh", ".yaml", ".yml", ".toml", ".ini"):
        return "# %s" % line
    return None
