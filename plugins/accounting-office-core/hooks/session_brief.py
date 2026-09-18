#!/usr/bin/env python3
"""ฉีดบริบทตอนเปิด session + เก็บกวาด state เก่า

ชุดนี้มี skill วัด token อยู่ จะไปยัด brief 3 อันทุกเซสชันไม่ได้ —
plugin ของ ERP จึงไม่มี SessionStart เลย สถานะของมันไปโผล่ใน permissionDecisionReason
ครั้งแรกที่ถูกใช้แทน

SessionStart  (รัน --selftest เพื่อตรวจว่า hook ทั้งชุดทำงานได้จริงในเครื่องนี้)
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import hookio           # noqa: E402
import state            # noqa: E402
import version          # noqa: E402
from state import State  # noqa: E402

BRIEF = """[accounting-office] ด่านตรวจอัตโนมัติทำงานอยู่ — กฎเหล่านี้บังคับด้วย hook ไม่ใช่คำแนะนำ

🔒 ทำงานได้ทีละลูกค้า: pin เกิดตอนอ่าน client-profile.md และแตะรายอื่นไม่ได้จนจบ session
🔒 เขียนได้เฉพาะ <งวด>/output/ — ocr-output/ source-docs/ bank/ อ่านอย่างเดียว
🔒 ห้ามเขียนทับ client-profile.md / mapping-overrides.md ที่มีอยู่แล้ว และห้ามสร้าง chart-of-accounts.xlsx
🔒 ERP: สร้างได้เฉพาะเอกสารรออนุมัติ — อนุมัติ/void/ลบ/จ่ายชำระ/ส่งอีเมล ถูก deny ทุกกรณี
🔒 ขณะ pin ลูกค้า: ห้ามต่อเน็ตและห้ามใช้ MCP ที่ไม่ใช่ ERP (PDPA)
🔒 หัวไฟล์ `%(header)s` ถูกเติมให้อัตโนมัติตอน Write ลง output/ — ไม่ต้องพิมพ์เอง

%(pin)s
เปลี่ยนลูกค้า: /clear เปิดเซสชันใหม่ (หรือ /switch-client ถ้าไม่อยากเสีย context)"""


def build_brief(st, root=None, today=None):
    pin = st.pin()
    if pin:
        line = "ตอนนี้ pin ลูกค้า **%s** ไว้แล้ว — โฟลเดอร์รายอื่นถูกบล็อกทั้งหมด" \
            % os.path.basename(pin["realpath"])
    else:
        line = "ยังไม่ได้ pin ลูกค้า — เริ่มงานด้วยการอ่าน client-profile.md ของรายที่จะทำ"
    return BRIEF % {"header": version.header_line(root, today), "pin": line}


def decide(event):
    st = State(event.get("session_id"))
    try:
        state.gc()
    except Exception:
        pass
    return hookio.note(build_brief(st), rule_id="session-brief")


def selftest():
    """ให้ผู้ใช้ตรวจ install ได้เองโดยไม่ต้องรู้จัก unittest"""
    here = os.path.dirname(os.path.abspath(__file__))
    runner = os.path.join(here, "tests", "run_tests.py")
    if not os.path.isfile(runner):
        sys.stderr.write("ไม่พบชุดทดสอบที่ %s\n" % runner)
        return 1
    proc = subprocess.run([sys.executable, runner], capture_output=True, text=True)
    sys.stderr.write(proc.stdout + proc.stderr)
    if proc.returncode == 0:
        sys.stderr.write("\n✅ ด่านตรวจของ accounting-office ทำงานถูกต้องในเครื่องนี้\n")
    else:
        sys.stderr.write("\n❌ ด่านตรวจมีปัญหา — อย่าเพิ่งใช้กับงานลูกค้าจริง\n")
    return proc.returncode


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    hookio.safe_main(decide, "SessionStart", hookio.fail_silent)
