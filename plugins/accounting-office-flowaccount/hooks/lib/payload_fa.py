"""ตรวจโครงสร้าง payload ก่อนสร้างเอกสารใน FlowAccount

สัญญาของ payload อยู่ที่ skills/flowaccount-posting/references/expense-category-mapping.md
(หัวข้อโครงสร้างที่ส่งเข้า tool) — payload ห่ออยู่ใน {"document": {...}, "confirm": bool}

ทุกกฎในไฟล์นี้มาจากข้อห้ามที่เขียนไว้ใน SKILL.md อยู่แล้ว แค่ย้ายมาบังคับด้วยเครื่อง
"""
from __future__ import annotations

import hashlib
import re

ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
SKIP_DUP_FLAGS = ("force", "skip_duplicate_check", "skip_dup_check", "ignore_duplicate",
                  "bypass_duplicate", "no_dedupe")

# ฟิลด์ที่ SKILL.md ระบุว่า "ต้องถามผู้ใช้ ไม่มีค่า default"
EXPLICIT_BOOLS = ("is_vat_inclusive", "use_inline_vat", "use_inline_discount")


def document_of(tool_input):
    """payload จริงอยู่ใน tool_input['document'] — fallback เป็น flat เผื่อ schema เปลี่ยน"""
    if isinstance(tool_input, dict):
        doc = tool_input.get("document")
        if isinstance(doc, dict):
            return doc
    return tool_input if isinstance(tool_input, dict) else {}


def is_commit(tool_input):
    """นับเฉพาะใบที่ commit จริง — confirm=false และ validate_* คือขั้น preview ของ Step 6

    ถ้าไม่มีฟิลด์ confirm เลย ให้ถือว่า commit (tool ที่ไม่มี dry-run)
    """
    if not isinstance(tool_input, dict):
        return True
    if "confirm" not in tool_input:
        return True
    return bool(tool_input.get("confirm"))


def validate(tool_input):
    """คืน list ของข้อความภาษาไทยที่บอกว่าขาดอะไร — list ว่าง = ผ่าน"""
    doc = document_of(tool_input)
    errors = []

    for flag in SKIP_DUP_FLAGS:
        if tool_input.get(flag) or doc.get(flag):
            errors.append("มี flag `%s` ที่ข้ามกลไกกันเอกสารซ้ำ — ห้ามปิดกลไกนี้เพื่อให้งานเดินต่อ" % flag)
    if tool_input.get("idempotency") is False:
        errors.append("ตั้ง idempotency=false ซึ่งปิดกลไกกันเอกสารซ้ำ")

    if doc.get("contact_id") and doc.get("contact_name"):
        errors.append("ส่ง contact_id คู่กับ contact_name — เจอคู่ค้าแล้วให้ส่ง contact_id อย่างเดียว")

    reference = str(doc.get("reference") or "").strip()
    if not reference:
        errors.append("ไม่มี reference (เลขที่เอกสารของผู้ขาย) ซึ่งเป็น key ที่ใช้กันบันทึกซ้ำ")

    items = doc.get("items")
    if not isinstance(items, list) or not items:
        errors.append("ไม่มีรายการ items ในเอกสาร")
    else:
        missing = [i + 1 for i, row in enumerate(items)
                   if not isinstance(row, dict) or not row.get("category_id")]
        if missing:
            errors.append("บรรทัดที่ %s ไม่มี category_id — เป็นฟิลด์บังคับ ห้ามเดาแล้วบันทึก"
                          % ", ".join(str(n) for n in missing[:8]))

    for field in EXPLICIT_BOOLS:
        if field not in doc:
            errors.append("ไม่ได้ระบุ %s — ฟิลด์นี้ไม่มีค่า default ต้องถามผู้ใช้ก่อนทุกครั้ง" % field)
        elif not isinstance(doc.get(field), bool):
            errors.append("%s ต้องเป็น true/false ไม่ใช่ %r" % (field, doc.get(field)))

    errors.extend(_check_date(doc))
    errors.extend(_check_arithmetic(doc, items))
    return errors


def _check_date(doc):
    raw = doc.get("document_date") or doc.get("date")
    if not raw:
        return ["ไม่มี document_date"]
    match = ISO_DATE.match(str(raw))
    if not match:
        return ["document_date ต้องเป็นรูปแบบ YYYY-MM-DD (ค.ศ.) ไม่ใช่ %r" % raw]
    year = int(match.group(1))
    if year >= 2500:
        return ["document_date เป็น พ.ศ. (%d) — ERP รับเป็น ค.ศ. ผิดปีคือยื่นผิดงวด" % year]
    if year < 1990:
        return ["document_date ปี %d ไม่สมเหตุสมผล" % year]
    return []


def _check_arithmetic(doc, items):
    total = doc.get("total") or doc.get("total_amount") or doc.get("grand_total")
    if total is None or not isinstance(items, list):
        return []
    try:
        computed = 0.0
        for row in items:
            if not isinstance(row, dict):
                return []
            qty = float(row.get("quantity", row.get("qty", 1)) or 0)
            price = float(row.get("unit_price", row.get("price", 0)) or 0)
            computed += qty * price
        stated = float(total)
    except (TypeError, ValueError):
        return []
    if abs(computed - stated) > 0.02:
        return ["ยอดรวมไม่ตรงกับผลคูณในรายการ (คำนวณได้ %.2f แต่ส่งมา %.2f)" % (computed, stated)]
    return []


def dup_key(tool_input):
    """key กันซ้ำ = reference + ยอดรวม + วันที่ (ตามที่ SKILL.md กำหนดให้ตรวจ)"""
    doc = document_of(tool_input)
    total = doc.get("total") or doc.get("total_amount") or doc.get("grand_total") or ""
    try:
        total = "%.2f" % float(total)
    except (TypeError, ValueError):
        total = str(total)
    raw = "%s|%s|%s" % (
        str(doc.get("reference") or "").strip().lower(),
        total,
        str(doc.get("document_date") or doc.get("date") or "").strip(),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def describe(tool_input):
    """สรุปเอกสารสั้น ๆ ไว้แสดงในข้อความ ask — จุดเดียวที่มนุษย์ได้เห็นก่อนเอกสารเกิดจริง"""
    doc = document_of(tool_input)
    vendor = doc.get("contact_name") or doc.get("contact_id") or "(ไม่ระบุคู่ค้า)"
    total = doc.get("total") or doc.get("total_amount") or doc.get("grand_total") or "?"
    return "%s · เลขที่ %s · วันที่ %s · ยอด %s บาท" % (
        vendor,
        doc.get("reference") or "?",
        doc.get("document_date") or doc.get("date") or "?",
        total,
    )
