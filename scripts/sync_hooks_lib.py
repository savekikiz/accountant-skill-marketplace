#!/usr/bin/env python3
"""ก็อปไฟล์ที่ใช้ร่วมกันระหว่าง plugin

plugin อ้างไฟล์ข้ามกันไม่ได้ ไฟล์ชุดนี้จึงต้องมีสำเนาในทุก plugin
(เหมือนที่กฎบังคับ 5 ข้อถูกเขียนซ้ำในทุก SKILL.md อยู่แล้ว)

สองกลุ่มที่ต้องซิงก์:
  1. `hooks/lib/` — จาก core ไปยัง plugin ของ ERP ทั้งสอง
  2. ตัวสร้าง Dashboard — จาก flowaccount ไปยัง peak
     (สคริปต์ตัวเดียวกันและสัญญา data pack ฉบับเดียวกัน คนละ ERP ใช้ร่วมกันได้
      เพราะสคริปต์ไม่รู้จัก ERP — มันรู้แค่รูปของ JSON)

แก้ที่ต้นทางแล้วรัน:  python3 scripts/sync_hooks_lib.py
ตรวจอย่างเดียว:       python3 scripts/sync_hooks_lib.py --check
เทสต์ของ core จะ assert SHA-256 ของสำเนา hooks/lib ว่าตรงกัน drift จึงเป็นเทสต์แดง
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys

SHARED = ("hookio.py", "state.py", "clientpath.py", "taxid.py", "version.py", "audit.py")
SOURCE = "plugins/accounting-office-core/hooks/lib"
TARGETS = ("plugins/accounting-office-flowaccount/hooks/lib",
           "plugins/accounting-office-peak/hooks/lib")

_FA_DASH = "plugins/accounting-office-flowaccount/skills/flowaccount-dashboard"
_PK_DASH = "plugins/accounting-office-peak/skills/peak-dashboard"

# (ต้นทาง, ปลายทาง) — path เต็มจากรากของ repo เพราะชื่อโฟลเดอร์ skill คนละชื่อกัน
PAIRS = (
    ("%s/scripts/build_dashboard.py" % _FA_DASH, "%s/scripts/build_dashboard.py" % _PK_DASH),
    ("%s/references/dashboard-layout.md" % _FA_DASH,
     "%s/references/dashboard-layout.md" % _PK_DASH),
)


def digest(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _sync(src, dst, check_only, drift, label):
    if not os.path.isfile(src):
        print("ไม่พบต้นทาง %s — ข้าม" % label)
        return
    if os.path.isfile(dst) and digest(src) == digest(dst):
        return
    drift.append(label)
    if not check_only:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)


def main(argv):
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    check_only = "--check" in argv
    drift = []

    for target in TARGETS:
        dest_dir = os.path.join(repo, target)
        os.makedirs(dest_dir, exist_ok=True)
        for name in SHARED:
            _sync(os.path.join(repo, SOURCE, name), os.path.join(dest_dir, name),
                  check_only, drift, os.path.join(target, name))

    for src, dst in PAIRS:
        _sync(os.path.join(repo, src), os.path.join(repo, dst), check_only, drift, dst)

    if check_only:
        if drift:
            print("สำเนาไม่ตรงกัน %d ไฟล์:\n  %s" % (len(drift), "\n  ".join(drift)))
            return 1
        print("ทุกสำเนาตรงกัน")
        return 0
    print("ซิงก์แล้ว %d ไฟล์" % len(drift) if drift else "ตรงกันอยู่แล้ว ไม่ต้องซิงก์")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
