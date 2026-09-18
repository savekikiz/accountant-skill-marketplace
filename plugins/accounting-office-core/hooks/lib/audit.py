"""บันทึกการตัดสินของ guard ลง JSONL — stdout ใช้ไม่ได้ (ต้องเป็น decision JSON เท่านั้น)

เก็บไว้ที่ ${CLAUDE_PLUGIN_DATA}/audit/YYYY-MM-DD.jsonl (private ต่อ plugin — ไม่ต้องแชร์)
เก็บได้เฉพาะ "ชื่อโฟลเดอร์ลูกค้า" ไม่เก็บชื่อผู้ขาย ยอดเงิน หรือเนื้อหา payload
เพราะไฟล์นี้อาจถูกเปิดดูตอน QC ของสำนักงาน

สำเนาไฟล์นี้ต้องตรงกันทั้ง 3 plugin — ดู scripts/sync_hooks_lib.py
"""
from __future__ import annotations

import datetime
import errno
import hashlib
import json
import os


def audit_dir():
    base = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".accounting-office", "audit-fallback")
    return os.path.join(base, "audit")


def log(event, decision, client=None, extra=None):
    """เขียน 1 บรรทัด — ห้ามโยน exception ออกไปรบกวน guard ไม่ว่ากรณีใด"""
    try:
        if decision is None or decision.verdict == "skip":
            return
        record = {
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "session": (event or {}).get("session_id"),
            "agent": (event or {}).get("agent_id"),
            "event": (event or {}).get("hook_event_name"),
            "tool": (event or {}).get("tool_name"),
            "decision": decision.verdict,
            "rule": decision.rule_id,
            "client": os.path.basename(client) if client else None,
        }
        if extra:
            record.update(extra)
        path = os.path.join(audit_dir(), datetime.date.today().isoformat() + ".jsonl")
        _mkdirs(os.path.dirname(path))
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def payload_digest(payload):
    """แฮชสั้น ๆ ไว้อ้างอิงใน audit โดยไม่เปิดเผยเนื้อหา"""
    try:
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    except Exception:
        blob = repr(payload)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def _mkdirs(path):
    try:
        os.makedirs(path, 0o700)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
