#!/usr/bin/env python3
"""อ่านผลที่ FlowAccount ตอบกลับ แล้วอัปเดต state ให้ด่านก่อนหน้าใช้ตัดสินใบถัดไป

สามอย่างที่ต้องเก็บจากตรงนี้ เพราะ PreToolUse มองไม่เห็น response:
  1. เลขผู้เสียภาษีบริษัทปลายทางจาก company_settings__load  -> เป็น input ของกฎข้อ 3
  2. ผลการสร้างเอกสาร: pending -> submitted / failed         -> เป็น input ของกลไกกันซ้ำ
  3. permission_denied                                        -> ตั้ง kill switch หยุดทั้งกอง

PostToolUse: mcp__.*|Write
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import erpname          # noqa: E402
import hookio           # noqa: E402
import payload_fa as payload  # noqa: E402
from state import State  # noqa: E402

VENDOR = "flowaccount"
STATE_KEY = "erp-flowaccount"
ERP_LABEL = "FlowAccount"
BATCH_DONE_FILE = re.compile(r"post-flowaccount-[^/\\]*\.md$")

TAXID_RE = re.compile(r"\b(\d{13})\b")
AWAITING = re.compile(r"(?i)awaiting|pending|รออนุมัติ|draft")
BAD_STATUS = re.compile(r"(?i)\bapproved\b|\bvoid(ed)?\b|\bpaid\b|\bcancelled\b")
PERMISSION_DENIED = re.compile(r"(?i)permission_denied|forbidden|unauthorized|403")


def decide(event):
    tool = event.get("tool_name") or ""
    st = State(event.get("session_id"))

    if tool in ("Write", "Edit"):
        return _on_write(event, st)

    server, namespace, action = erpname.split_tool(tool)
    if not erpname.is_vendor(server, VENDOR):
        return hookio.skip()

    erp = st.load(STATE_KEY)
    body = _response_text(event)
    full = ("%s__%s" % (namespace, action)) if namespace else (action or "")

    if PERMISSION_DENIED.search(body):
        erp["kill_switch"] = True
        st.save(STATE_KEY, erp)
        return hookio.note(
            "🛑 %s ตอบกลับว่าไม่มีสิทธิ์ — หยุดการบันทึกทั้งกองแล้ว ห้ามไล่ยิงใบที่เหลือ "
            "ตรวจสิทธิ์ผู้ใช้และบริษัทปลายทางก่อน" % ERP_LABEL,
            rule_id="erp-permission-denied")

    if full == "company_settings__load":
        return _capture_company(st, erp, event, body)

    if full == "documents__get_creation_status":
        erp["last_status_check_at"] = time.time()
        st.save(STATE_KEY, erp)
        return hookio.skip()

    kind, _ = erpname.classify(namespace, action)
    if kind != erpname.CREATE:
        return hookio.skip()

    return _on_create_result(st, erp, event, body)


def _capture_company(st, erp, event, body):
    """เก็บเลขผู้เสียภาษีที่ ERP ตอบกลับ — ไม่มีตัวนี้ erp_guard จะไม่ยอมให้สร้างเอกสารเลย"""
    match = TAXID_RE.search(body)
    if not match:
        return hookio.note(
            "อ่านเลขประจำตัวผู้เสียภาษีของบริษัทปลายทางจากผล company_settings__load ไม่ได้ — "
            "ด่านตรวจจะยังไม่ยอมให้สร้างเอกสารจนกว่าจะยืนยันได้ (กฎบังคับข้อ 3)",
            rule_id="erp-company-unparsed")
    erp["company_taxid"] = match.group(1)
    name = re.search(r'"(?:name|company_?name|companyName)"\s*:\s*"([^"]{1,120})"', body)
    if name:
        erp["company_name"] = name.group(1)
    st.save(STATE_KEY, erp)

    profile = st.load("profile")
    if profile.get("taxid") and profile["taxid"] != erp["company_taxid"]:
        return hookio.note(
            "🛑 บริษัทปลายทางใน %s (เลขภาษี %s) ไม่ตรงกับ client-profile.md (%s) — "
            "หยุดทันที อย่าบันทึกอะไรเข้าไป (กฎบังคับข้อ 3)"
            % (ERP_LABEL, erp["company_taxid"], profile["taxid"]),
            rule_id="erp-company-mismatch")
    return hookio.skip()


def _on_create_result(st, erp, event, body):
    key = payload.dup_key(event.get("tool_input") or {})
    pending = erp.get("pending") or {}
    submitted = erp.get("submitted") or {}
    entry = pending.pop(key, {"at": time.time()})

    failed = bool(re.search(r"(?i)\"(error|errors)\"|validation_error|failed", body))
    if failed:
        erp["failed"] = erp.get("failed") or {}
        erp["failed"][key] = entry
    else:
        doc_id = re.search(r'"(?:id|document_?id|recordId)"\s*:\s*"?([\w-]{1,64})', body)
        entry["id"] = doc_id.group(1) if doc_id else None
        submitted[key] = entry
    erp["pending"] = pending
    erp["submitted"] = submitted
    st.save(STATE_KEY, erp)

    if failed:
        return hookio.skip()

    if BAD_STATUS.search(body) and not AWAITING.search(body):
        return hookio.note(
            "🛑 เอกสารที่สร้างมีสถานะที่ไม่ใช่ 'รออนุมัติ' — plugin ชุดนี้ต้องไม่ทำให้เกิดสถานะนี้ "
            "(กฎบังคับข้อ 4) หยุดแล้วแจ้งผู้ใช้ทันที อย่าสร้างใบถัดไป",
            rule_id="erp-bad-status")
    return hookio.skip()


def _on_write(event, st):
    """เขียนไฟล์สรุปการบันทึก = จบกอง (Step 9) -> ถามใหม่เมื่อเริ่มกองหน้า"""
    path = str((event.get("tool_input") or {}).get("file_path") or "")
    if not BATCH_DONE_FILE.search(path):
        return hookio.skip()
    erp = st.load(STATE_KEY)
    if erp.get("batch"):
        erp["batch"] = {}
        st.save(STATE_KEY, erp)
    return hookio.skip()


def _response_text(event):
    response = event.get("tool_response")
    if response is None:
        return ""
    if isinstance(response, str):
        return response[:20000]
    try:
        return json.dumps(response, ensure_ascii=False)[:20000]
    except Exception:
        return repr(response)[:20000]


if __name__ == "__main__":
    hookio.safe_main(decide, "PostToolUse", hookio.fail_silent)
