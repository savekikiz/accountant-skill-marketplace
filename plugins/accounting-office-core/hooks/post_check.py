#!/usr/bin/env python3
"""ตรวจหลังทำ — เตือนอย่างเดียว ไม่บล็อก (ของเกิดไปแล้ว)

หน้าที่สำคัญที่สุดคืออันแรก: PreToolUse มองไม่เห็นเนื้อไฟล์ จึงเป็นที่นี่เท่านั้นที่
เลขผู้เสียภาษีจาก client-profile.md จะถูกอ่านเข้ามาเป็น ledger ให้กฎข้อ 2 และ 3 ใช้บังคับต่อ

PostToolUse: Read|Write|Edit|Bash
"""
from __future__ import annotations

import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import clientpath as cp  # noqa: E402
import hookio           # noqa: E402
import taxid            # noqa: E402
import version          # noqa: E402
from state import State  # noqa: E402

PLACEHOLDER = re.compile(r"<[^<>\n]{1,60}>")
READY_MARK = re.compile(r"✅\s*(?:พร้อม)?ปิดงวด(?:ได้)?")
NOT_DONE = re.compile(r"ยังไม่ได้ทำ|ยังไม่เสร็จ|ค้างอยู่")
NONZERO_DIFF = re.compile(r"ผลต่าง[^\n|]*\|\s*[-+]?\s*(?!0(?:\.0+)?\s*\|)[\d,]+\.?\d*")
DRAFT_MARK = re.compile(r"ยังไม่ได้ส่ง|ไฟล์ร่าง")


def decide(event):
    tool = event.get("tool_name") or ""
    tool_input = event.get("tool_input") or {}
    cwd = event.get("cwd")
    st = State(event.get("session_id"))

    if tool == "Read":
        return _on_read(event, tool_input, cwd, st)
    if tool in ("Write", "Edit", "MultiEdit"):
        return _on_write(tool_input, cwd, st)
    if tool == "Bash":
        return _on_bash(tool_input, cwd, st)
    return hookio.skip()


def _on_read(event, tool_input, cwd, st):
    """อ่าน client-profile.md แล้ว -> บันทึก ledger ให้ erp_guard ใช้เป็นเงื่อนไขก่อนเขียน ERP"""
    path = tool_input.get("file_path") or tool_input.get("path") or ""
    if os.path.basename(str(path)) != cp.PROFILE_NAME:
        return hookio.skip()
    resolved = cp.resolve(path, cwd)
    content = _read_text(resolved)
    if content is None:
        return hookio.skip()

    value, ok = taxid.extract_taxid(content)
    st.save("profile", {
        "read": True,
        "path": resolved,
        "client": os.path.basename(os.path.dirname(resolved)),
        "taxid": value,
        "taxid_valid": bool(ok),
    })
    if value is None:
        return hookio.note(
            "⚠️ อ่าน client-profile.md แล้วแต่หาเลขประจำตัวผู้เสียภาษีไม่เจอ (หรือยังเป็น placeholder) "
            "— ต้องเติมให้ครบก่อน ไม่งั้นด่านตรวจจะไม่ยอมให้บันทึกเข้า ERP",
            rule_id="profile-no-taxid")
    if not ok:
        return hookio.note(
            "⚠️ เลขประจำตัวผู้เสียภาษีใน client-profile.md (%s) ไม่ผ่าน checksum 13 หลัก "
            "— ตรวจกับหนังสือรับรองก่อน ด่านตรวจจะไม่ยอมให้บันทึกเข้า ERP จนกว่าจะแก้" % value,
            rule_id="profile-bad-taxid")
    return hookio.skip()


def _on_write(tool_input, cwd, st):
    path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not path:
        return hookio.skip()
    resolved = cp.resolve(path, cwd)
    name = os.path.basename(resolved)
    content = _read_text(resolved)
    if content is None:
        return hookio.skip()

    warnings = []

    if name == cp.PROFILE_NAME:
        left = PLACEHOLDER.findall(content)
        if left:
            warnings.append("client-profile.md ยังเหลือ placeholder ที่ไม่ได้แทนค่า: %s"
                            % ", ".join(sorted(set(left))[:5]))
        # อ่านใหม่เข้า ledger ทันที ผู้ใช้จะได้ไม่ต้อง Read ซ้ำหลังแก้
        value, ok = taxid.extract_taxid(content)
        profile = st.load("profile")
        if profile.get("read") or value:
            st.save("profile", {"read": True, "path": resolved,
                                "client": os.path.basename(os.path.dirname(resolved)),
                                "taxid": value, "taxid_valid": bool(ok)})

    pin = st.pin()
    if pin and cp.zone(pin["realpath"], resolved) == "output":
        if not version.has_header(content):
            warnings.append("ไฟล์นี้ไม่มีหัวระบุ plugin + เวอร์ชัน (กฎบังคับข้อ 5) — ควรเป็น `%s`"
                            % version.header_line())

    if name.startswith("pnd3-") or name.startswith("pnd53-"):
        warnings.extend(_check_pnd(content, st))

    if name.startswith("close-report-"):
        if READY_MARK.search(content) and (NOT_DONE.search(content) or NONZERO_DIFF.search(content)):
            warnings.append("รายงานสรุปว่าปิดงวดได้ ทั้งที่ในไฟล์ยังมีผลต่างที่ไม่เป็นศูนย์ "
                            "หรือขั้นที่ยังไม่ได้ทำ — ต้องแก้ข้อสรุปหรืออธิบายรายการค้างให้ครบก่อน")

    if name.startswith("draft-email-") and not DRAFT_MARK.search(content):
        warnings.append("ไฟล์ร่างอีเมลไม่มีเครื่องหมายว่ายังไม่ได้ส่ง — ใส่ไว้ในหัวไฟล์กันเข้าใจผิด")

    if not warnings:
        return hookio.skip()
    return hookio.note("⚠️ ด่านตรวจหลังเขียนไฟล์ %s:\n- %s" % (name, "\n- ".join(warnings)),
                       rule_id="post-write")


def _check_pnd(content, st):
    warnings = []
    if "-" in content:
        lines = [ln for ln in content.splitlines() if re.search(r"\d-\d", ln)]
        if lines:
            warnings.append("ไฟล์ ภ.ง.ด. มีเลขที่ใส่ขีดคั่น — เลขผู้เสียภาษีต้องเป็น 13 หลักติดกัน")
    bad = taxid.find_all(content)
    if bad:
        warnings.append("เลข 13 หลักที่ไม่ผ่าน checksum: %s" % ", ".join(bad[:5]))
    payer = st.load("profile").get("taxid")
    if payer and payer not in content:
        warnings.append("ไม่พบเลขผู้เสียภาษีของลูกค้า (%s) ในไฟล์ — ตรวจว่าช่อง"
                        "ผู้มีหน้าที่หักภาษี ณ ที่จ่าย ถูกต้อง" % payer)
    return warnings


def _on_bash(tool_input, cwd, st):
    """ไฟล์ .xlsx ที่สคริปต์สร้างไม่ผ่าน Write tool — ตรวจหัวไฟล์ด้วย zipfile ของ stdlib"""
    pin = st.pin()
    if not pin:
        return hookio.skip()
    cmd = str(tool_input.get("command") or "")
    targets = re.findall(r"[\w\-./\\ก-๛]+\.xlsx", cmd)
    warnings = []
    for target in targets[:3]:
        resolved = cp.resolve(target, cwd)
        if not resolved or not os.path.isfile(resolved):
            continue
        if cp.zone(pin["realpath"], resolved) != "output":
            continue
        if _xlsx_has_header(resolved) is False:
            warnings.append("%s ไม่มีหัวระบุ plugin + เวอร์ชัน (กฎบังคับข้อ 5)"
                            % os.path.basename(resolved))
    if not warnings:
        return hookio.skip()
    return hookio.note("⚠️ %s — ควรใส่ `%s` ไว้ในแถวแรกของชีตสรุป"
                       % ("; ".join(warnings), version.header_line()),
                       rule_id="xlsx-header")


def _xlsx_has_header(path):
    """คืน True/False/None (None = ตรวจไม่ได้ ไม่ต้องเตือน)"""
    try:
        with zipfile.ZipFile(path) as zf:
            names = [n for n in zf.namelist()
                     if n.endswith("sharedStrings.xml") or "worksheets/sheet" in n]
            for name in names[:4]:
                if b"accounting-office-" in zf.read(name):
                    return True
        return False
    except Exception:
        return None


def _read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read(400000)
    except Exception:
        return None


if __name__ == "__main__":
    hookio.safe_main(decide, "PostToolUse", hookio.fail_silent)
