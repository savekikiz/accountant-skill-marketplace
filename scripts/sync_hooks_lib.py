#!/usr/bin/env python3
"""ก็อป hooks/lib/ ที่ใช้ร่วมกันจาก core ไปยัง plugin ของ ERP

plugin อ้างไฟล์ข้ามกันไม่ได้ ไฟล์ชุดนี้จึงต้องมีสำเนาในทุก plugin
(เหมือนที่กฎบังคับ 5 ข้อถูกเขียนซ้ำในทุก SKILL.md อยู่แล้ว)

แก้ที่ core แล้วรัน:  python3 scripts/sync_hooks_lib.py
ตรวจอย่างเดียว:      python3 scripts/sync_hooks_lib.py --check
เทสต์ของ core จะ assert SHA-256 ของทุกสำเนาว่าตรงกัน drift จึงเป็นเทสต์แดง
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


def digest(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main(argv):
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    check_only = "--check" in argv
    drift = []
    for target in TARGETS:
        dest_dir = os.path.join(repo, target)
        os.makedirs(dest_dir, exist_ok=True)
        for name in SHARED:
            src = os.path.join(repo, SOURCE, name)
            dst = os.path.join(dest_dir, name)
            same = os.path.isfile(dst) and digest(src) == digest(dst)
            if same:
                continue
            drift.append(os.path.join(target, name))
            if not check_only:
                shutil.copy2(src, dst)
    if check_only:
        if drift:
            print("lib ไม่ตรงกัน %d ไฟล์:\n  %s" % (len(drift), "\n  ".join(drift)))
            return 1
        print("lib ตรงกันทุกสำเนา")
        return 0
    print("ซิงก์แล้ว %d ไฟล์" % len(drift) if drift else "ตรงกันอยู่แล้ว ไม่ต้องซิงก์")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
