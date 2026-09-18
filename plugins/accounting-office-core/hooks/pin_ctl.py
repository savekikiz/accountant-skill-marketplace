#!/usr/bin/env python3
"""ปลด pin ลูกค้าออกจาก session ปัจจุบัน — ใช้โดยคำสั่ง /switch-client

รองรับ --release อย่างเดียว โดยตั้งใจ ไม่มี --set:
การ pin รายใหม่ต้องไปอ่าน client-profile.md ของรายนั้น ซึ่งจะตรวจ checksum
และสร้าง ledger ใหม่ให้เอง ถ้ามี --set โมเดลจะ pin ข้ามรายได้โดยไม่ผ่านการตรวจ

path_guard ดักคำสั่งนี้แล้วตอบ ask เสมอ — การกดยืนยันของมนุษย์คือด่าน
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from state import State  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="ปลด pin ลูกค้าของ accounting-office")
    parser.add_argument("--release", action="store_true", required=True,
                        help="ล้าง pin, ledger การอ่านโปรไฟล์, การยืนยันเลขภาษี "
                             "และรายการเอกสารที่ส่งไปแล้วของ session นี้")
    parser.add_argument("--session", default=os.environ.get("CLAUDE_SESSION_ID", ""),
                        help="session id (ปกติไม่ต้องระบุ)")
    args = parser.parse_args(argv)

    session = args.session
    if not session:
        session = _latest_session()
    if not session:
        print("ไม่พบ session ที่มี pin อยู่ — ไม่มีอะไรต้องปลด")
        return 0

    st = State(session)
    pin = st.pin()
    who = os.path.basename(pin["realpath"]) if pin else None
    removed = st.release()
    if who:
        print("ปลด pin ลูกค้า %s แล้ว (ล้าง: %s)" % (who, ", ".join(removed) or "ไม่มีไฟล์"))
    else:
        print("ไม่มี pin ค้างอยู่ (ล้าง: %s)" % (", ".join(removed) or "ไม่มีไฟล์"))
    print("เริ่มงานลูกค้ารายใหม่ด้วยการอ่าน client-profile.md ของรายนั้น")
    return 0


def _latest_session():
    """เดา session ล่าสุดจาก mtime — ใช้เมื่อ harness ไม่ได้ส่ง session id มาทาง env"""
    base = os.path.join(__import__("state").state_root(), "sessions")
    try:
        entries = [(os.path.getmtime(os.path.join(base, n)), n) for n in os.listdir(base)]
    except OSError:
        return ""
    return max(entries)[1] if entries else ""


if __name__ == "__main__":
    sys.exit(main())
