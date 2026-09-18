#!/usr/bin/env python3
"""ด่านตรวจก่อนเขียนข้อมูลเข้า FlowAccount — บังคับกฎบังคับข้อ 3 และ 4

  ข้อ 3  ต้องยืนยันว่าบริษัทปลายทางใน ERP ตรงกับ client-profile.md ก่อนเขียน
  ข้อ 4  สร้างได้เฉพาะเอกสารรออนุมัติ — ห้ามอนุมัติ ห้าม void ห้ามลบ ห้ามจ่ายชำระ

ด่านถามนับเฉพาะใบที่ commit จริง (confirm=true) ใบแรกของแต่ละกอง
ขั้น preview (validate_* / confirm=false) ผ่านเงียบ ไม่งั้นผู้ใช้เจอ dialog ทุกแถวตอน dry run
แล้วจะเริ่มกดผ่านแบบไม่อ่าน ซึ่งแย่กว่าไม่มีด่าน

PreToolUse: mcp__.*
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import audit            # noqa: E402
import erpname          # noqa: E402
import hookio           # noqa: E402
import payload_fa as payload  # noqa: E402
from state import State  # noqa: E402

VENDOR = "flowaccount"
STATE_KEY = "erp-flowaccount"
ERP_LABEL = "FlowAccount"

BATCH_MAX_DOCS = 50
BATCH_MAX_AGE = 20 * 60
BATCH_IDLE_GAP = 10 * 60


def decide(event):
    tool = event.get("tool_name") or ""
    tool_input = event.get("tool_input") or {}
    st = State(event.get("session_id"))

    server, namespace, action = erpname.split_tool(tool)
    if not erpname.is_vendor(server, VENDOR):
        return hookio.skip()

    kind, reason = erpname.classify(namespace, action)

    if kind == erpname.AUTH:
        return hookio.allow(rule_id="erp-auth")

    if kind == erpname.FORBIDDEN:
        return hookio.deny(
            "`%s` ถูกห้ามโดยกฎบังคับข้อ 4: %s — plugin ชุดนี้สร้างได้เฉพาะเอกสาร"
            "สถานะรออนุมัติ ถ้าต้องทำจริงให้เข้าไปทำใน %s เอง" % (action, reason, ERP_LABEL),
            rule_id="erp-forbidden")

    erp = st.load(STATE_KEY)

    if kind == erpname.READ:
        return hookio.skip()

    if erp.get("kill_switch"):
        return hookio.deny(
            "เจอ permission_denied จาก %s ก่อนหน้านี้ — หยุดทั้งกองไว้แล้ว "
            "ตรวจสิทธิ์และบริษัทปลายทางก่อน แล้วเปิด session ใหม่" % ERP_LABEL,
            rule_id="erp-kill-switch")

    if kind == erpname.UNKNOWN:
        return hookio.ask(
            "`%s` เป็น tool ของ %s ที่ด่านตรวจยังไม่รู้จัก (%s) — ตรวจเองก่อนว่าไม่ใช่การอนุมัติ "
            "ยกเลิก หรือจ่ายชำระ" % (tool, ERP_LABEL, reason),
            rule_id="erp-unknown")

    # --- ตั้งแต่นี้คือ verb สร้างเอกสาร ---
    gate = _preconditions(st, erp)
    if gate is not None:
        return gate

    errors = payload.validate(tool_input)
    if errors:
        return hookio.deny(
            "payload ของเอกสารนี้ยังไม่ผ่านการตรวจ:\n- %s" % "\n- ".join(errors),
            rule_id="erp-payload")

    if not payload.is_commit(tool_input):
        _mark_preview(st, erp)
        return hookio.skip()        # ขั้น preview — ปล่อยเงียบ

    key = payload.dup_key(tool_input)
    dup = _dup_check(erp, key)
    if dup is not None:
        return dup

    now = time.time()
    batch_key = "%s|%s" % (erp.get("pin_client") or "", namespace or "")
    if _batch_open(erp, batch_key, now):
        _record_commit(st, erp, key, batch_key, now, asked=False)
        return hookio.allow(rule_id="erp-batch-open")

    _record_commit(st, erp, key, batch_key, now, asked=True)
    return hookio.ask(_ask_text(erp, tool_input), rule_id="erp-batch-first")


def _preconditions(st, erp):
    """กฎข้อ 2 และ 3 — ขาดอะไรต้องบอกให้ชัดจนโมเดลแก้ได้ในเทิร์นเดียว"""
    pin = st.pin()
    if not pin:
        return hookio.deny(
            "ยังไม่ได้ระบุลูกค้าที่ทำงานด้วย — อ่าน client-profile.md ของรายนั้นก่อน (กฎบังคับข้อ 2)",
            rule_id="erp-no-pin")

    profile = st.load("profile")
    if not profile.get("read"):
        return hookio.deny(
            "ยังไม่ได้อ่าน client-profile.md ใน session นี้ — ต้องอ่านก่อนเขียนข้อมูลเข้า ERP (กฎบังคับข้อ 2)",
            rule_id="erp-no-profile")

    if not profile.get("taxid"):
        return hookio.deny(
            "client-profile.md ไม่มีเลขประจำตัวผู้เสียภาษี — เติมให้ครบก่อน (กฎบังคับข้อ 3)",
            rule_id="erp-no-taxid")

    if not profile.get("taxid_valid"):
        return hookio.deny(
            "เลขประจำตัวผู้เสียภาษีใน client-profile.md (%s) ไม่ผ่าน checksum 13 หลัก — "
            "ตรวจกับหนังสือรับรองก่อน" % profile.get("taxid"),
            rule_id="erp-bad-taxid")

    verified = erp.get("company_taxid")
    if not verified:
        return hookio.deny(
            "ยังไม่ได้ตรวจบริษัทปลายทางใน %s — เรียก company_settings__load แล้วเทียบ"
            "ชื่อบริษัทและเลขผู้เสียภาษีกับ client-profile.md ก่อน (กฎบังคับข้อ 3)" % ERP_LABEL,
            rule_id="erp-company-unverified")

    if verified != profile.get("taxid"):
        return hookio.deny(
            "บริษัทปลายทางใน %s มีเลขผู้เสียภาษี %s แต่ client-profile.md ระบุ %s — "
            "ไม่ตรงกัน หยุดทันที (กฎบังคับข้อ 3)"
            % (ERP_LABEL, verified, profile.get("taxid")),
            rule_id="erp-company-mismatch")

    if erp.get("pin_client") != os.path.basename(pin["realpath"]):
        erp["pin_client"] = os.path.basename(pin["realpath"])
        st.save(STATE_KEY, erp)
    return None


def _dup_check(erp, key):
    submitted = erp.get("submitted") or {}
    pending = erp.get("pending") or {}
    last_status = float(erp.get("last_status_check_at") or 0)

    for bucket, label in ((submitted, "ถูกสร้างไปแล้ว"), (pending, "ถูกส่งไปแล้วแต่ยังไม่รู้ผล")):
        if key not in bucket:
            continue
        entered = float(bucket[key].get("at") or 0) if isinstance(bucket[key], dict) else 0
        if last_status > entered:
            return None     # ตรวจสถานะหลังจากนั้นแล้ว ยิงซ้ำได้
        return hookio.deny(
            "เอกสารใบนี้ (reference + ยอด + วันที่ เดียวกัน) %s ใน session นี้ — "
            "ห้ามยิงซ้ำ ให้เรียก documents__get_creation_status ตรวจผลก่อน" % label,
            rule_id="erp-duplicate")
    return None


def _batch_open(erp, batch_key, now):
    batch = erp.get("batch") or {}
    if batch.get("key") != batch_key:
        return False
    if not batch.get("asked_at"):
        return False
    if batch.get("preview_since_commit"):
        return False        # เจอ preview คั่น = เริ่มกองใหม่ ต้องถามอีกรอบ
    if int(batch.get("count") or 0) >= BATCH_MAX_DOCS:
        return False
    if now - float(batch.get("asked_at") or 0) > BATCH_MAX_AGE:
        return False
    if now - float(batch.get("last_commit_at") or 0) > BATCH_IDLE_GAP:
        return False
    return True


def _record_commit(st, erp, key, batch_key, now, asked):
    batch = erp.get("batch") or {}
    if asked:
        batch = {"key": batch_key, "asked_at": now, "count": 0}
    batch["count"] = int(batch.get("count") or 0) + 1
    batch["last_commit_at"] = now
    batch["preview_since_commit"] = False
    erp["batch"] = batch
    pending = erp.get("pending") or {}
    pending[key] = {"at": now}
    erp["pending"] = pending
    st.save(STATE_KEY, erp)


def _mark_preview(st, erp):
    """preview หลัง commit = สัญญาณว่า Step 6 เริ่มกองใหม่ — เป็นตัวรีเซ็ตที่แม่นและฟรี"""
    batch = erp.get("batch") or {}
    if batch.get("last_commit_at"):
        batch["preview_since_commit"] = True
        erp["batch"] = batch
        st.save(STATE_KEY, erp)


def _ask_text(erp, tool_input):
    return (
        "จะสร้างเอกสารใน %s — บริษัทปลายทางที่ยืนยันแล้ว: %s (เลขภาษี %s)\n"
        "ใบนี้: %s\n"
        "เอกสารจะถูกสร้างเป็น **สถานะรออนุมัติ** เท่านั้น\n"
        "การอนุมัติครั้งนี้ครอบคลุมทั้งกองจนครบ %d ใบ หรือ %d นาที แล้วจะถามใหม่"
        % (ERP_LABEL, erp.get("company_name") or "(ไม่ทราบชื่อ)",
           erp.get("company_taxid") or "?", payload.describe(tool_input),
           BATCH_MAX_DOCS, BATCH_MAX_AGE // 60)
    )


def _decide_and_log(event):
    decision = decide(event)
    audit.log(event, decision, extra={"erp": VENDOR})
    return decision


if __name__ == "__main__":
    hookio.safe_main(
        _decide_and_log, "PreToolUse",
        hookio.fail_deny("ด่านตรวจก่อนเขียน FlowAccount ทำงานผิดพลาด — หยุดไว้ก่อน "
                         "ไม่บันทึกอะไรเข้า ERP จนกว่าจะแก้ (ดู stderr)"))
