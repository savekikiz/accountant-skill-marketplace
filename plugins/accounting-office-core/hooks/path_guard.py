#!/usr/bin/env python3
"""ด่านตรวจ path — บังคับกฎบังคับข้อ 1, 2 และ 5 ของ accounting-office

  ข้อ 1  ทำงานเฉพาะโฟลเดอร์ลูกค้าที่ระบุ ห้ามข้ามไปรายอื่น
  ข้อ 2  ต้องอ่าน client-profile.md ก่อนเริ่มงาน
  ข้อ 5  ไฟล์ที่สร้างต้องมีหัวระบุ plugin + เวอร์ชัน (เติมให้อัตโนมัติด้วย updatedInput)

การ pin ลูกค้าผูกกับกฎข้อ 2: pin เกิดขึ้นตอนอ่าน client-profile.md เท่านั้น
ไม่ใช่ "แตะโฟลเดอร์ไหนก่อน" ซึ่งจะทำให้ Grep ที่ไม่เกี่ยวข้อง pin ผิดราย

PreToolUse: Read|Write|Edit|NotebookEdit|Glob|Grep|Bash
"""
from __future__ import annotations

import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import audit            # noqa: E402
import clientpath as cp  # noqa: E402
import hookio           # noqa: E402
import version          # noqa: E402
from state import State  # noqa: E402

WRITE_TOOLS = ("Write", "Edit", "NotebookEdit", "MultiEdit")
SWITCH_HINT = "จะเปลี่ยนลูกค้าให้ใช้ /clear เปิดเซสชันใหม่ หรือสั่ง /switch-client ถ้าไม่อยากเสีย context"

# --- Bash: ตรวจแค่ 3 อย่าง ไม่แกะ path (ดูเหตุผลใน README หัวข้อข้อจำกัด) ---
_PLUGIN_SCRIPT = re.compile(r"python3?\s+[\"']?\S*[/\\]plugins[/\\]accounting-office-[a-z]+[/\\]\S*\.py")
_EGRESS = re.compile(
    r"(?:^|[\s;&|(])(?:curl|wget|scp|rsync|sftp|ssh|nc|ncat|socat|rclone|aws|gcloud|az|gh"
    r"|mail|sendmail|mutt|msmtp)(?:$|[\s;&|)])"
    r"|git\s+push"
    r"|osascript[^\n]*\b(?:Mail|Messages)\b"
    r"|open\s+-a\s+[\"']?(?:Mail|Messages)"
)
_PROTECTED_IN_CMD = re.compile(r"client-profile\.md|mapping-overrides\.md|chart-of-accounts\.xlsx")
_DESTRUCTIVE = re.compile(r"(?:^|[\s;&|])(?:rm|mv|cp|truncate|dd|tee)\s|>\s*\S|sed\s+-i")
_PIN_RELEASE = re.compile(r"pin_ctl\.py[^\n]*--release")


def decide(event):
    tool = event.get("tool_name") or ""
    tool_input = event.get("tool_input") or {}
    cwd = event.get("cwd")
    st = State(event.get("session_id"))

    if tool == "Bash":
        return _bash(event, tool_input, st)

    paths = cp.input_paths(tool, tool_input)
    if not paths:
        return hookio.skip()

    pin = st.pin()

    for raw in paths:
        resolved = cp.resolve(raw, cwd)
        if resolved is None:
            continue

        # เขียนทับตัว plugin เองขณะทำงานลูกค้าอยู่ = ไม่มีเหตุผลที่ถูกต้อง
        if pin and tool in WRITE_TOOLS and _under_plugin(resolved):
            return hookio.deny(
                "ขณะ pin ลูกค้า %s อยู่ ห้ามเขียนไฟล์ของ plugin — ถ้าจะแก้ plugin ให้ /clear ก่อน"
                % os.path.basename(pin["realpath"]),
                rule_id="plugin-readonly-while-pinned")

        root = cp.client_root(resolved, cwd)
        if root is None:
            continue    # นอกโฟลเดอร์ลูกค้าทุกราย — ไม่ใช่เรื่องของ guard ตัวนี้

        if pin is None:
            # ยังไม่ pin: อ่าน client-profile.md ได้อย่างเดียว และนั่นคือสิ่งที่ pin
            if tool == "Read" and os.path.basename(resolved) == cp.PROFILE_NAME:
                _set_pin(st, root, event)
                return hookio.allow(rule_id="pin-set")
            return hookio.deny(
                "ยังไม่ได้ระบุลูกค้าที่จะทำงานด้วย — อ่าน %s ของลูกค้ารายนั้นก่อน (กฎบังคับข้อ 2)"
                % os.path.join(os.path.basename(root), cp.PROFILE_NAME),
                rule_id="profile-first")

        if not cp.same_client(pin["realpath"], root):
            return hookio.deny(
                "session นี้ pin ลูกค้า %s ไว้แล้ว ห้ามแตะโฟลเดอร์ของ %s (กฎบังคับข้อ 1) — %s"
                % (os.path.basename(pin["realpath"]), os.path.basename(root), SWITCH_HINT),
                rule_id="cross-client")

        if tool in WRITE_TOOLS:
            verdict = _write_scope(root, resolved, tool)
            if verdict is not None:
                return verdict

    # ผ่านทุก path แล้ว — เติมหัวไฟล์ให้ถ้าเป็น Write ลง output/
    if tool == "Write" and pin:
        return _stamp_header(pin, tool_input, cwd)
    return hookio.skip()


def _write_scope(root, resolved, tool):
    z = cp.zone(root, resolved)
    name = os.path.basename(resolved)

    if z == "readonly":
        return hookio.deny(
            "%s เป็นไฟล์ต้นทาง (อ่านอย่างเดียว) — ผลลัพธ์ทุกอย่างต้องเขียนลง <งวด>/output/ เท่านั้น"
            % name, rule_id="readonly-zone")

    if z == "coa" or name == cp.COA_NAME:
        return hookio.deny(
            "ห้ามสร้าง chart-of-accounts.xlsx — ผู้ใช้ต้องวางไฟล์จริงเอง (ดู /new-client)",
            rule_id="no-fake-coa")

    if z in ("profile", "mapping") and tool == "Write" and os.path.exists(resolved):
        return hookio.deny(
            "%s มีอยู่แล้ว ห้ามเขียนทับ — ถ้าต้องแก้ให้ใช้ Edit ทีละจุด" % name,
            rule_id="no-overwrite-profile")

    if z == "client-misc":
        return hookio.deny(
            "เขียนได้เฉพาะใน <งวด>/output/ (และ client-profile.md / mapping-overrides.md) เท่านั้น",
            rule_id="output-only")

    return None


def _stamp_header(pin, tool_input, cwd):
    """กฎข้อ 5 — เติมหัวไฟล์ให้เองแทนที่จะเตือนทีหลังแล้วให้โมเดลเขียนไฟล์ซ้ำ

    ทำเฉพาะ Write เพราะเห็นเนื้อหาทั้งไฟล์; Edit เห็นแค่บางส่วน เติมไม่ปลอดภัย
    """
    path = tool_input.get("file_path") or tool_input.get("path")
    content = tool_input.get("content")
    if not path or not isinstance(content, str):
        return hookio.skip()
    resolved = cp.resolve(path, cwd)
    if cp.zone(pin["realpath"], resolved) != "output":
        return hookio.skip()
    if version.has_header(content):
        return hookio.skip()
    head = version.comment_header(path)
    if head is None:
        return hookio.skip()
    updated = dict(tool_input)
    updated["content"] = head + "\n\n" + content
    return hookio.allow(rule_id="stamp-header", updated_input=updated)


def _bash(event, tool_input, st):
    cmd = tool_input.get("command") or ""

    # ปลด pin ต้องให้มนุษย์กดยืนยัน — การกดนั้นคือด่าน ไม่ได้สร้างช่องอนุญาตใหม่
    # ต้องตรวจก่อนกฎ "สคริปต์ของ plugin ผ่านได้" เพราะ pin_ctl.py ก็เป็นสคริปต์ของ plugin
    if _PIN_RELEASE.search(cmd):
        pin = st.pin()
        who = os.path.basename(pin["realpath"]) if pin else "(ยังไม่ได้ pin)"
        return hookio.ask(
            "จะปลด pin ลูกค้า %s ออกจาก session นี้ — ledger การอ่านโปรไฟล์ การยืนยันเลขภาษี "
            "และรายการเอกสารที่ส่งไปแล้วจะถูกล้างทั้งหมด" % who,
            rule_id="pin-release")

    # สคริปต์ของ plugin เอง (เช่น token-meter) — ผ่านก่อนกฎ egress
    # เพราะ tm_common.py ยิง count_tokens ไป api.anthropic.com โดยตั้งใจ
    if _PLUGIN_SCRIPT.search(cmd):
        return hookio.allow(rule_id="plugin-script")

    pin = st.pin()

    # 2. เครื่องมือส่งข้อมูลออกนอกเครื่อง — ขณะทำงานลูกค้าไม่มีเหตุผลที่ถูกต้องเลย
    if pin and _EGRESS.search(cmd):
        return hookio.deny(
            "ขณะ pin ลูกค้า %s ห้ามใช้คำสั่งที่ส่งข้อมูลออกนอกเครื่องหรือส่งอีเมล (PDPA)"
            % os.path.basename(pin["realpath"]),
            rule_id="bash-egress")

    # 3. คำสั่งทำลายไฟล์ที่ป้องกันไว้
    if _PROTECTED_IN_CMD.search(cmd) and _DESTRUCTIVE.search(cmd):
        return hookio.deny(
            "คำสั่งนี้แตะไฟล์ที่ป้องกันไว้ (client-profile.md / mapping-overrides.md / "
            "chart-of-accounts.xlsx) ด้วยคำสั่งที่เขียนทับหรือลบ",
            rule_id="bash-protected-file")

    return hookio.skip()


def _set_pin(st, root, event):
    record = {
        "literal_path": root,
        "realpath": os.path.realpath(root),
        "pinned_at": time.time(),
        "session_id": event.get("session_id"),
        "agent_id": event.get("agent_id"),
    }
    try:
        stat = os.stat(root)
        record["dev"] = stat.st_dev
        record["ino"] = stat.st_ino
    except OSError:
        pass
    return st.pin_once(record)


def _under_plugin(path):
    return "%splugins%saccounting-office-" % (os.sep, os.sep) in path \
        or cp.within(version.plugin_root(), path)


def _decide_and_log(event):
    decision = decide(event)
    audit.log(event, decision)
    return decision


def _fail(event, exc):
    """fail-closed แบบมีเงื่อนไข: Write/Edit ปิดเสมอ; Read/Glob/Grep/Bash ปิดเฉพาะที่มีกลิ่นลูกค้า

    สาขานี้ต้องไม่พึ่ง state หรือดิสก์ เพราะมันคือทางที่ใช้ตอนทุกอย่างพังไปแล้ว
    """
    msg = "guard ตรวจ path ของ accounting-office ทำงานผิดพลาด — หยุดไว้ก่อน (ดู stderr)"
    try:
        tool = (event or {}).get("tool_name") or ""
        if tool in WRITE_TOOLS:
            return hookio.deny(msg, rule_id="hook-error")
        blob = repr((event or {}).get("tool_input") or "")
        if cp.looks_client(blob):
            return hookio.deny(msg, rule_id="hook-error")
    except Exception:
        return hookio.deny(msg, rule_id="hook-error")
    return None


if __name__ == "__main__":
    hookio.safe_main(_decide_and_log, "PreToolUse", _fail)
