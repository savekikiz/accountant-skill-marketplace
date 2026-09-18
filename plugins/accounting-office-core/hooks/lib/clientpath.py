"""จำแนก path ว่าอยู่ในโฟลเดอร์ลูกค้ารายไหน และอยู่โซนที่เขียนได้หรือไม่

โครงโฟลเดอร์ที่ /new-client สร้าง:
    <client root>/                     <- มี client-profile.md อยู่ในนี้ = นิยามของ "client root"
        client-profile.md
        mapping-overrides.md
        chart-of-accounts.xlsx
        <งวด เช่น 2569-09>/
            ocr-output/  source-docs/  bank/    <- อ่านอย่างเดียว
            output/                             <- โซนเดียวที่เขียนได้

ห้ามเทียบ path ด้วย startswith เด็ดขาด — ชื่อลูกค้าไทยเป็น prefix ของกันได้
("ตัวอย่างเทรดดิ้ง" เป็น prefix ของ "ตัวอย่างเทรดดิ้ง 2") เทียบด้วย samefile/inode/segment แทน

สำเนาไฟล์นี้ต้องตรงกันทั้ง 3 plugin — ดู scripts/sync_hooks_lib.py
"""
from __future__ import annotations

import os

PROFILE_NAME = "client-profile.md"
MAPPING_NAME = "mapping-overrides.md"
COA_NAME = "chart-of-accounts.xlsx"

PROTECTED_NAMES = (PROFILE_NAME, MAPPING_NAME)
READONLY_ZONES = ("ocr-output", "source-docs", "bank")
WRITABLE_ZONE = "output"

# เพดานการไต่หา client root — กันการเดินขึ้นไปถึง / บนเครื่องที่ path ลึกผิดปกติ
_MAX_ASCEND = 12


def resolve(path, cwd=None):
    """ทำ path ให้เป็น absolute โดยไม่ยุบ symlink (เก็บทั้งสองแบบไว้เทียบทีหลัง)"""
    if not path:
        return None
    p = os.path.expanduser(str(path))
    if not os.path.isabs(p):
        p = os.path.join(cwd or os.getcwd(), p)
    return os.path.normpath(p)


def client_root(path, cwd=None):
    """ไดเรกทอรีบรรพบุรุษที่ใกล้ที่สุดซึ่งมี client-profile.md อยู่ — คือนิยามของโฟลเดอร์ลูกค้า

    ถ้า path เองคือ client-profile.md ให้คืนไดเรกทอรีที่มันอยู่
    """
    p = resolve(path, cwd)
    if p is None:
        return None
    cur = p if os.path.isdir(p) else os.path.dirname(p)
    for _ in range(_MAX_ASCEND):
        if not cur or cur == os.path.dirname(cur):
            break
        if os.path.isfile(os.path.join(cur, PROFILE_NAME)):
            return cur
        cur = os.path.dirname(cur)
    return None


def looks_client(raw):
    """เช็คหยาบ ๆ แบบไม่แตะดิสก์ ว่า string นี้ "มีกลิ่น" ของโฟลเดอร์ลูกค้าไหม

    ใช้ในสาขา fail-closed ของ path_guard: ต้องไม่โยน exception เด็ดขาด
    จึงเป็นแค่การหา substring ไม่มี I/O
    """
    try:
        s = str(raw or "")
    except Exception:
        return False
    for marker in ("ลูกค้า", PROFILE_NAME, MAPPING_NAME, "source-docs", "ocr-output"):
        if marker in s:
            return True
    return False


def same_client(a, b):
    """เทียบว่าเป็นโฟลเดอร์ลูกค้าเดียวกันไหม — samefile -> dev/ino -> segment"""
    if not a or not b:
        return False
    if a == b:
        return True
    try:
        if os.path.exists(a) and os.path.exists(b) and os.path.samefile(a, b):
            return True
    except OSError:
        pass
    try:
        sa, sb = os.stat(a), os.stat(b)
        if (sa.st_dev, sa.st_ino) == (sb.st_dev, sb.st_ino):
            return True
    except OSError:
        pass
    return _segments(_real(a)) == _segments(_real(b))


def _real(p):
    """realpath ที่ทนไฟล์ยังไม่มีอยู่จริง — ปลายทางของ Write ยังไม่ถูกสร้างตอนที่ guard ตรวจ

    ไต่ขึ้นไปหาบรรพบุรุษที่มีอยู่จริง realpath ตรงนั้น แล้วต่อส่วนที่เหลือกลับ
    """
    p = os.path.normpath(p)
    tail = []
    cur = p
    for _ in range(_MAX_ASCEND + 4):
        if os.path.exists(cur):
            break
        parent = os.path.dirname(cur)
        if not parent or parent == cur:
            return p
        tail.append(os.path.basename(cur))
        cur = parent
    return os.path.join(os.path.realpath(cur), *reversed(tail)) if tail \
        else os.path.realpath(cur)


def _segments(p):
    return [os.path.normcase(s) for s in os.path.normpath(p).split(os.sep) if s]


def within(root, path):
    """path อยู่ใต้ root ไหม — เทียบทีละ segment ไม่ใช่ startswith"""
    if not root or not path:
        return False
    rseg = _segments(_real(root))
    pseg = _segments(_real(path))
    if len(pseg) < len(rseg):
        return False
    return pseg[:len(rseg)] == rseg


def zone(root, path):
    """บอกว่า path อยู่โซนไหนของโฟลเดอร์ลูกค้า

    คืนค่า: 'profile' | 'mapping' | 'coa' | 'output' | 'readonly' | 'client-misc' | None
    """
    if not root:
        return None
    p = resolve(path)
    if p is None or not within(root, p):
        return None
    name = os.path.basename(p)
    if name == PROFILE_NAME:
        return "profile"
    if name == MAPPING_NAME:
        return "mapping"
    if name == COA_NAME:
        return "coa"
    # ต้อง realpath ทั้งสองฝั่งเสมอ — บน macOS โฟลเดอร์ชั่วคราวอยู่ใต้ /var ซึ่งเป็น
    # symlink ไป /private/var ถ้า realpath ข้างเดียวจำนวน segment จะไม่ตรงกันและ slice เพี้ยน
    rel = _segments(_real(p))[len(_segments(_real(root))):]
    # <งวด>/<zone>/... — โซนอยู่ที่ระดับที่สองเสมอ
    if len(rel) >= 2:
        if rel[1] == WRITABLE_ZONE:
            return "output"
        if rel[1] in READONLY_ZONES:
            return "readonly"
    return "client-misc"


def is_writable_target(root, path):
    """เขียนไฟล์นี้ได้ไหมตามกฎ 'เขียนได้เฉพาะ <งวด>/output/'"""
    z = zone(root, path)
    return z in ("output", "profile", "mapping")


def input_paths(tool_name, tool_input):
    """ดึง path ทั้งหมดที่ tool call นี้จะไปแตะ (ยกเว้น Bash ซึ่งไม่แกะ — ดู path_guard)"""
    if not isinstance(tool_input, dict):
        return []
    out = []
    for key in ("file_path", "path", "notebook_path", "filePath"):
        val = tool_input.get(key)
        if isinstance(val, str) and val:
            out.append(val)
    # Glob/Grep: pattern อาจเป็น path เองได้
    pattern = tool_input.get("pattern")
    if isinstance(pattern, str) and (os.sep in pattern or "ลูกค้า" in pattern):
        out.append(pattern)
    return out
