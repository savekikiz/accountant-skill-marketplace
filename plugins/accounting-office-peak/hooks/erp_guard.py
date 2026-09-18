#!/usr/bin/env python3
"""ด่านตรวจก่อนเขียนข้อมูลเข้า PEAK — ทำงานแบบ learn-mode

ต่างจาก FlowAccount ตรงนี้: ชื่อ tool และรูป payload ของ PEAK ยังไม่ได้ยืนยันกับ endpoint จริง
(agents/peak-lookup.md ship มาด้วย tools: [] ด้วยเหตุผลเดียวกัน) ด่านจึงตั้งค่าอนุรักษ์นิยม:

  verb ที่รู้ว่าต้องห้าม  -> deny   (กฎ verb ใช้ได้โดยไม่ต้องรู้ชื่อ tool)
  verb อ่านที่ชัดเจน      -> allow
  verb สร้าง             -> ask ทุกใบ (ไม่ใช่ใบแรกของกอง — เพราะตรวจ payload ไม่ได้)
  verb ที่ไม่รู้จัก        -> deny  (FlowAccount ask, PEAK deny)

เงื่อนไขกฎข้อ 2 และ 3 บังคับเหมือนกันทุกประการ

PreToolUse: mcp__.*
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import audit            # noqa: E402
import erpname          # noqa: E402
import hookio           # noqa: E402
import payload_peak as payload  # noqa: E402
from state import State  # noqa: E402

VENDOR = "peak"
STATE_KEY = "erp-peak"
ERP_LABEL = "PEAK"


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

    full = ("%s__%s" % (namespace, action)) if namespace else (action or "")

    if kind == erpname.READ or full in _read_allowlist():
        return hookio.skip()

    erp = st.load(STATE_KEY)
    if erp.get("kill_switch"):
        return hookio.deny(
            "เจอ permission_denied จาก %s ก่อนหน้านี้ — หยุดทั้งกองไว้แล้ว "
            "ตรวจสิทธิ์และบริษัทปลายทางก่อน แล้วเปิด session ใหม่" % ERP_LABEL,
            rule_id="erp-kill-switch")

    if kind == erpname.UNKNOWN:
        return hookio.deny(
            "`%s` เป็น tool ของ %s ที่ยังไม่ได้จัดประเภท (%s) — ชุด tool ของ PEAK "
            "ยังไม่ได้ยืนยันกับ endpoint จริง ถ้าเป็น tool อ่านให้เติมชื่อ `%s` ลงใน "
            "read_tools ของ %s/peak-tools.json ก่อน (ดูรายชื่อที่เจอจริงใน "
            "${CLAUDE_PLUGIN_DATA}/observed-tools.json)"
            % (tool, ERP_LABEL, reason, full, _plugin_hooks_dir()),
            rule_id="erp-unknown-peak")

    gate = _preconditions(st, erp)
    if gate is not None:
        return gate

    errors = payload.validate(tool_input)
    if errors:
        return hookio.deny("payload ของเอกสารนี้ยังไม่ผ่านการตรวจ:\n- %s" % "\n- ".join(errors),
                           rule_id="erp-payload")

    if not payload.is_commit(tool_input):
        return hookio.skip()

    key = payload.dup_key(tool_input)
    submitted = erp.get("submitted") or {}
    pending = erp.get("pending") or {}
    if key in submitted or key in pending:
        last_status = float(erp.get("last_status_check_at") or 0)
        entered = float((submitted.get(key) or pending.get(key) or {}).get("at") or 0)
        if last_status <= entered:
            return hookio.deny(
                "payload เดียวกันเป๊ะถูกส่งไปแล้วใน session นี้ — ห้ามยิงซ้ำ "
                "ให้ตรวจสถานะการสร้างเอกสารใน %s ก่อน" % ERP_LABEL,
                rule_id="erp-duplicate")

    pending[key] = {"at": time.time()}
    erp["pending"] = pending
    st.save(STATE_KEY, erp)

    # ถามทุกใบโดยตั้งใจ — ตรวจ payload ไม่ได้ จึงไม่มีสิทธิ์ปล่อยทั้งกองด้วยการกดครั้งเดียว
    return hookio.ask(
        "จะสร้างเอกสารใน %s — บริษัทปลายทางที่ยืนยันแล้ว: %s (เลขภาษี %s)\n"
        "ใบนี้: %s\n"
        "เอกสารจะถูกสร้างเป็น **สถานะรออนุมัติ** เท่านั้น\n"
        "⚠️ %s"
        % (ERP_LABEL, erp.get("company_name") or "(ไม่ทราบชื่อ)",
           erp.get("company_taxid") or "?", payload.describe(tool_input),
           payload.UNAVAILABLE_NOTE),
        rule_id="erp-ask-every-doc")


def _preconditions(st, erp):
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
            "ยังไม่ได้ตรวจบริษัทปลายทางใน %s — ดึงข้อมูลบริษัทแล้วเทียบชื่อและเลขผู้เสียภาษี"
            "กับ client-profile.md ก่อน (กฎบังคับข้อ 3)" % ERP_LABEL,
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


def _plugin_hooks_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _read_allowlist():
    """รายชื่อ tool อ่านที่ผู้ใช้ยืนยันเองใน peak-tools.json"""
    try:
        with open(os.path.join(_plugin_hooks_dir(), "peak-tools.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        return set(str(v) for v in (data.get("read_tools") or []))
    except Exception:
        return set()


def _decide_and_log(event):
    decision = decide(event)
    audit.log(event, decision, extra={"erp": VENDOR})
    return decision


if __name__ == "__main__":
    hookio.safe_main(
        _decide_and_log, "PreToolUse",
        hookio.fail_deny("ด่านตรวจก่อนเขียน PEAK ทำงานผิดพลาด — หยุดไว้ก่อน "
                         "ไม่บันทึกอะไรเข้า ERP จนกว่าจะแก้ (ดู stderr)"))
