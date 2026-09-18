"""อ่าน event จาก stdin เขียน decision ออก stdout — ใช้ร่วมกันทุก hook ของ accounting-office

กฎเหล็ก 2 ข้อของไฟล์นี้:
  1. stdout มีได้แค่ decision JSON เท่านั้น (print() ที่หลงเหลือ = JSON พัง = hook ถูกปล่อยผ่าน)
  2. exit 0 เสมอ — exit code อื่นที่ไม่ใช่ 2 ถือเป็น non-blocking error คือ "ปล่อยผ่าน"
     ซึ่งตรงข้ามกับสิ่งที่ guard ต้องการเมื่อพัง

สำเนาไฟล์นี้ต้องตรงกันทั้ง 3 plugin — ดู scripts/sync_hooks_lib.py
"""
from __future__ import annotations

import json
import sys

ALLOW = "allow"
DENY = "deny"
ASK = "ask"
SKIP = "skip"


class Decision(object):
    """ผลตัดสินของ guard หนึ่งตัว — เก็บเป็น object เพื่อให้เทสต์เทียบได้ตรง ๆ"""

    __slots__ = ("verdict", "reason", "context", "updated_input", "system_message", "rule_id")

    def __init__(self, verdict, reason=None, context=None,
                 updated_input=None, system_message=None, rule_id=None):
        self.verdict = verdict
        self.reason = reason
        self.context = context
        self.updated_input = updated_input
        self.system_message = system_message
        self.rule_id = rule_id

    def __repr__(self):
        return "Decision(%s, rule=%s, reason=%r)" % (self.verdict, self.rule_id, self.reason)

    def __eq__(self, other):
        return isinstance(other, Decision) and self.verdict == other.verdict \
            and self.rule_id == other.rule_id

    def to_output(self, event_name):
        out = {"hookEventName": event_name}
        if self.verdict != SKIP:
            out["permissionDecision"] = self.verdict
        if self.reason:
            out["permissionDecisionReason"] = self.reason
        if self.context:
            out["additionalContext"] = self.context
        if self.updated_input is not None:
            out["updatedInput"] = self.updated_input
        if self.system_message:
            out["systemMessage"] = self.system_message
        return {"hookSpecificOutput": out}


def allow(reason=None, rule_id=None, updated_input=None):
    return Decision(ALLOW, reason=reason, rule_id=rule_id, updated_input=updated_input)


def deny(reason, rule_id=None):
    return Decision(DENY, reason=reason, rule_id=rule_id)


def ask(reason, rule_id=None):
    return Decision(ASK, reason=reason, rule_id=rule_id)


def skip(rule_id=None):
    """ไม่มีความเห็น — ปล่อยให้ flow ปกติและ hook ตัวอื่นตัดสิน"""
    return Decision(SKIP, rule_id=rule_id)


def note(context, rule_id=None):
    """PostToolUse: ส่งข้อความกลับเข้า context โดยไม่บล็อกอะไร"""
    return Decision(SKIP, context=context, rule_id=rule_id)


def read_event():
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def emit(decision, event_name):
    if decision is None or (decision.verdict == SKIP and not decision.context
                            and not decision.system_message):
        sys.stdout.write("{}")
        return
    sys.stdout.write(json.dumps(decision.to_output(event_name), ensure_ascii=False))


def safe_main(decide, event_name, fail):
    """ห่อ guard ทั้งตัว: พังยังไงก็ยังพ่น JSON ที่ถูกต้องและ exit 0

    fail: ฟังก์ชัน (event_dict_or_None, exc) -> Decision  ที่บอกว่าพังแล้วให้ตัดสินยังไง
          guard ที่คุมงานแก้กลับไม่ได้ต้องส่งคืน deny ไม่ใช่ allow
    """
    event = None
    try:
        event = read_event()
        decision = decide(event)
        emit(decision, event.get("hook_event_name", event_name))
    except BaseException as exc:  # noqa: BLE001 — ตั้งใจจับทุกอย่าง รวม KeyboardInterrupt
        try:
            sys.stderr.write("accounting-office hook error: %r\n" % (exc,))
        except Exception:
            pass
        try:
            emit(fail(event, exc), event_name)
        except BaseException:
            # ทางสุดท้าย: hardcode deny ไม่ให้เงียบ
            sys.stdout.write(json.dumps({"hookSpecificOutput": {
                "hookEventName": event_name,
                "permissionDecision": DENY,
                "permissionDecisionReason": "guard ของ accounting-office ทำงานผิดพลาด — หยุดไว้ก่อนเพื่อความปลอดภัย",
            }}, ensure_ascii=False))
    sys.exit(0)


def fail_deny(message):
    def _fail(event, exc):
        return deny(message, rule_id="hook-error")
    return _fail


def fail_silent(event, exc):
    return None
