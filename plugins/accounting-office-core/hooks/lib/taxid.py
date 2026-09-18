"""ตรวจเลขประจำตัวผู้เสียภาษีไทย 13 หลัก

อัลกอริทึมเหมือนกับที่เขียนไว้ใน
skills/ocr-review/references/tax-id-checksum.md — ห้ามแก้ให้ต่างกัน

สำเนาไฟล์นี้ต้องตรงกันทั้ง 3 plugin — ดู scripts/sync_hooks_lib.py
"""
from __future__ import annotations

import re

_DIGITS = re.compile(r"\d")
# แถวในตารางของ client-profile.md: | เลขประจำตัวผู้เสียภาษี | 0105567069510 |
_PROFILE_ROW = re.compile(r"เลขประจำตัวผู้เสียภาษี\s*\|\s*([^|\n]+)")


def mod11_ok(tax_id):
    """ตรวจ checksum เลขผู้เสียภาษี/เลขบัตรประชาชนไทย 13 หลัก"""
    digits = "".join(ch for ch in str(tax_id or "") if ch.isdigit())
    if len(digits) != 13:
        return False
    d = [int(c) for c in digits]
    total = sum(d[i] * (13 - i) for i in range(12))
    return (11 - (total % 11)) % 10 == d[12]


def normalize(tax_id):
    """เหลือเฉพาะตัวเลข — ขีดคั่นต้องไม่หลุดเข้าไฟล์ ภ.ง.ด."""
    return "".join(ch for ch in str(tax_id or "") if ch.isdigit())


def extract_taxid(markdown):
    """ดึงเลขผู้เสียภาษีออกจากตารางใน client-profile.md

    คืน (เลขที่ normalize แล้ว, ผ่าน checksum ไหม) — คืน (None, False) ถ้าหาไม่เจอ
    ค่าที่ยังเป็น placeholder <13 หลัก ไม่มีขีด> จะไม่ผ่านเพราะไม่ครบ 13 หลัก
    """
    if not markdown:
        return None, False
    match = _PROFILE_ROW.search(markdown)
    if not match:
        return None, False
    raw = match.group(1)
    if "<" in raw or ">" in raw:      # ยังเป็น placeholder ของ template
        return None, False
    value = normalize(raw)
    if not value:
        return None, False
    return value, mod11_ok(value)


def find_all(text):
    """หาเลข 13 หลักทุกตัวในข้อความ พร้อมบอกว่าตัวไหนไม่ผ่าน checksum"""
    bad = []
    for token in re.findall(r"[\d\-]{13,20}", text or ""):
        value = normalize(token)
        if len(value) != 13:
            continue
        if not mod11_ok(value):
            bad.append(token.strip())
    return bad
