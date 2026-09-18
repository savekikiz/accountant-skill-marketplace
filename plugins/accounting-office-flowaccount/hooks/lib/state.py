"""State ที่ hook ของทั้ง 3 plugin ใช้ร่วมกัน

อยู่ที่ ${ACCOUNTING_OFFICE_STATE:-$HOME/.accounting-office}/sessions/<session_id>/
ไม่ใช้ ${CLAUDE_PLUGIN_DATA} เพราะเป็น private ต่อ plugin — flowaccount จะอ่าน pin ของ core ไม่ได้
ไม่ใช้ ${CLAUDE_PROJECT_DIR} เพราะเปลี่ยนที่เปิด Claude Code = pin หาย = fail open
ไม่เก็บในโฟลเดอร์ลูกค้า เพราะโฟลเดอร์นั้นถูกซิปส่งให้ลูกค้า (PDPA)

แต่ละไฟล์มีผู้เขียนคนเดียว จึงไม่ต้องล็อก:
  pin.json / profile.json      -> core
  erp-flowaccount.json         -> flowaccount
  erp-peak.json                -> peak

สำเนาไฟล์นี้ต้องตรงกันทั้ง 3 plugin — ดู scripts/sync_hooks_lib.py
"""
from __future__ import annotations

import errno
import json
import os
import time

PIN_TTL_SEC = 12 * 3600
SESSION_GC_SEC = 7 * 86400


def state_root():
    override = os.environ.get("ACCOUNTING_OFFICE_STATE")
    if override:
        return os.path.abspath(os.path.expanduser(override))
    return os.path.join(os.path.expanduser("~"), ".accounting-office")


def session_dir(session_id):
    sid = _safe_id(session_id)
    return os.path.join(state_root(), "sessions", sid)


def _safe_id(session_id):
    """session_id มาจาก harness แต่เราไม่ไว้ใจว่าจะไม่มี path separator"""
    sid = str(session_id or "unknown")
    return "".join(ch if (ch.isalnum() or ch in "-_") else "_" for ch in sid)[:128]


class State(object):
    """อ่าน/เขียน state ของ session เดียว — ทุกการอ่านทนไฟล์หายและไฟล์เสียได้"""

    def __init__(self, session_id, root=None):
        self.session_id = session_id
        self._dir = os.path.join(root, "sessions", _safe_id(session_id)) if root \
            else session_dir(session_id)
        self._cache = {}

    @property
    def dir(self):
        return self._dir

    def load(self, kind):
        if kind in self._cache:
            return self._cache[kind]
        data = {}
        try:
            with open(os.path.join(self._dir, kind + ".json"), encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            data = {}
        self._cache[kind] = data
        return data

    def save(self, kind, data):
        self._cache[kind] = data
        path = os.path.join(self._dir, kind + ".json")
        _mkdirs(self._dir)
        tmp = path + ".tmp%d" % os.getpid()
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        os.replace(tmp, path)

    # ------------------------------------------------------------ pin
    def pin(self):
        """คืน pin ที่ยังไม่หมดอายุ; หมดอายุแล้วถือว่าไม่มี (กัน --resume ลากงานเมื่อวานมาทับ)"""
        data = self.load("pin")
        if not data.get("realpath"):
            return None
        if time.time() - float(data.get("pinned_at") or 0) > PIN_TTL_SEC:
            return None
        return data

    def pin_once(self, record):
        """สร้าง pin แบบ O_EXCL — ถ้ามีคนสร้างไปแล้วให้ใช้ของคนนั้น (ใครถึงก่อนชนะ)"""
        _mkdirs(self._dir)
        path = os.path.join(self._dir, "pin.json")
        payload = json.dumps(record, ensure_ascii=False).encode("utf-8")
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise
            self._cache.pop("pin", None)
            existing = self.pin()
            if existing:
                return existing
            self.save("pin", record)      # ของเดิมหมดอายุ/เสีย -> ทับได้
            return record
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
        self._cache["pin"] = record
        return record

    def release(self):
        """ล้างทุกอย่างของ session นี้ ยกเว้น audit log ที่อยู่คนละที่"""
        removed = []
        for name in ("pin", "profile", "erp-flowaccount", "erp-peak"):
            path = os.path.join(self._dir, name + ".json")
            try:
                os.remove(path)
                removed.append(name)
            except OSError:
                pass
        self._cache = {}
        return removed


def gc(root=None, now=None):
    """ลบ session ที่เก่ากว่า 7 วัน — เรียกจาก SessionStart ที่เดียว ไม่ต้องมี cron"""
    base = os.path.join(root or state_root(), "sessions")
    now = now if now is not None else time.time()
    removed = 0
    try:
        names = os.listdir(base)
    except OSError:
        return 0
    for name in names:
        path = os.path.join(base, name)
        try:
            if now - os.path.getmtime(path) <= SESSION_GC_SEC:
                continue
            for child in os.listdir(path):
                os.remove(os.path.join(path, child))
            os.rmdir(path)
            removed += 1
        except OSError:
            continue
    return removed


def _mkdirs(path):
    try:
        os.makedirs(path, 0o700)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
