"""ตรวจ payload ของ PEAK — learn-mode: ไม่ตรวจอะไรเลยโดยตั้งใจ

ชื่อ tool และรูป payload ของ PEAK ยังไม่ได้ถูกยืนยันกับ endpoint จริง
(ดู agents/peak-lookup.md ที่ ship มาด้วย tools: [] ด้วยเหตุผลเดียวกัน)

การเขียนตัวตรวจโครงสร้างสำหรับ payload ที่ไม่เคยเห็น = โกหกใน code
ผู้ใช้จะเข้าใจว่ามีด่านตรวจทั้งที่ไม่มี ซึ่งอันตรายกว่าไม่มีด่าน
โมดูลนี้จึงประกาศตรง ๆ ว่าตรวจไม่ได้ แล้วให้ erp_guard ถามผู้ใช้ทุกใบแทน

เมื่อยืนยัน payload จริงแล้ว: ก็อป payload_fa.py มาแก้ให้ตรงกับ PEAK
แล้วเปลี่ยน AVAILABLE เป็น True
"""
from __future__ import annotations

import hashlib

AVAILABLE = False

UNAVAILABLE_NOTE = (
    "ด่านตรวจโครงสร้าง payload ของ PEAK ยังไม่พร้อมใช้ (ยังไม่ได้ยืนยันรูป payload จริง) "
    "จึงถามผู้ใช้ทุกใบ — ต้องตรวจตาราง preview ด้วยตาเองก่อนกดอนุมัติทุกครั้ง"
)


def validate(tool_input):
    """ไม่อ้างอะไรทั้งนั้น — ยกเว้น flag ที่ปิดกลไกกันซ้ำ ซึ่งชื่อเหมือนกันทุก ERP"""
    errors = []
    if isinstance(tool_input, dict):
        for flag in ("force", "skip_duplicate_check", "ignore_duplicate", "no_dedupe"):
            if tool_input.get(flag):
                errors.append("มี flag `%s` ที่ข้ามกลไกกันเอกสารซ้ำ" % flag)
        if tool_input.get("idempotency") is False:
            errors.append("ตั้ง idempotency=false ซึ่งปิดกลไกกันเอกสารซ้ำ")
    return errors


def is_commit(tool_input):
    if not isinstance(tool_input, dict):
        return True
    if "confirm" not in tool_input:
        return True
    return bool(tool_input.get("confirm"))


def dup_key(tool_input):
    """ไม่รู้ชื่อฟิลด์จริง จึงแฮชทั้ง payload — หยาบกว่า FlowAccount แต่ยังกันยิงซ้ำซ้ำเป๊ะ ๆ ได้"""
    import json
    try:
        blob = json.dumps(tool_input, sort_keys=True, ensure_ascii=False)
    except Exception:
        blob = repr(tool_input)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def describe(tool_input):
    if not isinstance(tool_input, dict):
        return "(อ่าน payload ไม่ได้)"
    doc = tool_input.get("document") if isinstance(tool_input.get("document"), dict) else tool_input
    bits = []
    for key in ("reference", "document_date", "date", "total", "total_amount",
                "contact_name", "contact_id"):
        if doc.get(key) is not None:
            bits.append("%s=%s" % (key, doc[key]))
    return " · ".join(bits) if bits else "(ไม่มีฟิลด์ที่รู้จักใน payload)"
