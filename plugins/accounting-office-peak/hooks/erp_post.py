#!/usr/bin/env python3
"""อ่านผลที่ PEAK ตอบกลับ + เก็บรายชื่อ tool ที่เจอจริง

งานพิเศษของไฟล์นี้ที่ FlowAccount ไม่มี: **บันทึกชื่อ tool ของ PEAK ทุกตัวที่ถูกเรียก**
ลง ${CLAUDE_PLUGIN_DATA}/observed-tools.json

agents/peak-lookup.md บอกให้ผู้ใช้ไปเติมชื่อ tool เองใน tools: แต่ไม่ได้บอกว่าจะรู้ชื่อจากไหน
ไฟล์นี้ทำให้ขั้นตอนนั้นกลายเป็น copy-paste แทนที่จะเป็นการเดา

PostToolUse: mcp__.*|Write
"""
from __future__ import annotations

import errno
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import erpname          # noqa: E402
import hookio           # noqa: E402
import payload_peak as payload  # noqa: E402
from state import State  # noqa: E402

VENDOR = "peak"
STATE_KEY = "erp-peak"
ERP_LABEL = "PEAK"
BATCH_DONE_FILE = re.compile(r"post-peak-[^/\\]*\.md$")

TAXID_RE = re.compile(r"\b(\d{13})\b")
AWAITING = re.compile(r"(?i)awaiting|pending|รออนุมัติ|draft")
BAD_STATUS = re.compile(r"(?i)\bapproved\b|\bvoid(ed)?\b|\bpaid\b|\bcancelled\b")
PERMISSION_DENIED = re.compile(r"(?i)permission_denied|forbidden|unauthorized|403")
STATUS_TOOL = re.compile(r"(?i)(creation_status|document_status|get_status)")
COMPANY_TOOL = re.compile(r"(?i)(company|organisation|organization).*(load|get|info|detail|list)")


def decide(event):
    tool = event.get("tool_name") or ""
    st = State(event.get("session_id"))

    if tool in ("Write", "Edit"):
        return _on_write(event, st)

    server, namespace, action = erpname.split_tool(tool)
    if not erpname.is_vendor(server, VENDOR):
        return hookio.skip()

    full = ("%s__%s" % (namespace, action)) if namespace else (action or "")
    kind, _ = erpname.classify(namespace, action)
    _observe(full, kind)

    erp = st.load(STATE_KEY)
    body = _response_text(event)

    if PERMISSION_DENIED.search(body):
        erp["kill_switch"] = True
        st.save(STATE_KEY, erp)
        return hookio.note(
            "🛑 %s ตอบกลับว่าไม่มีสิทธิ์ — หยุดการบันทึกทั้งกองแล้ว ห้ามไล่ยิงใบที่เหลือ "
            "ตรวจสิทธิ์ผู้ใช้และบริษัทปลายทางก่อน" % ERP_LABEL,
            rule_id="erp-permission-denied")

    if STATUS_TOOL.search(full):
        erp["last_status_check_at"] = time.time()
        st.save(STATE_KEY, erp)
        return hookio.skip()

    if COMPANY_TOOL.search(full):
        return _capture_company(st, erp, body)

    if kind != erpname.CREATE:
        return hookio.skip()

    return _on_create_result(st, erp, event, body)


def _capture_company(st, erp, body):
    match = TAXID_RE.search(body)
    if not match:
        return hookio.skip()
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

    if re.search(r"(?i)\"(error|errors)\"|validation_error|failed", body):
        erp["failed"] = erp.get("failed") or {}
        erp["failed"][key] = entry
        erp["pending"] = pending
        st.save(STATE_KEY, erp)
        return hookio.skip()

    submitted[key] = entry
    erp["pending"] = pending
    erp["submitted"] = submitted
    st.save(STATE_KEY, erp)

    if BAD_STATUS.search(body) and not AWAITING.search(body):
        return hookio.note(
            "🛑 เอกสารที่สร้างมีสถานะที่ไม่ใช่ 'รออนุมัติ' — plugin ชุดนี้ต้องไม่ทำให้เกิดสถานะนี้ "
            "(กฎบังคับข้อ 4) หยุดแล้วแจ้งผู้ใช้ทันที อย่าสร้างใบถัดไป",
            rule_id="erp-bad-status")
    return hookio.skip()


def _on_write(event, st):
    path = str((event.get("tool_input") or {}).get("file_path") or "")
    if not BATCH_DONE_FILE.search(path):
        return hookio.skip()
    erp = st.load(STATE_KEY)
    if erp.get("batch"):
        erp["batch"] = {}
        st.save(STATE_KEY, erp)
    return hookio.skip()


def _observe(full, kind):
    """เก็บชื่อ tool ที่เจอจริง ให้ผู้ใช้ก็อปไปเติม peak-tools.json และ agents/peak-lookup.md"""
    if not full:
        return
    base = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".accounting-office", "peak")
    path = os.path.join(base, "observed-tools.json")
    try:
        try:
            os.makedirs(base, 0o700)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("_readme", [
            "ชื่อ tool ของ PEAK MCP ที่ถูกเรียกจริงในเครื่องนี้ พร้อมการจำแนกของด่านตรวจ",
            "คัดตัวที่เป็น read ไปใส่ read_tools ใน hooks/peak-tools.json",
            "และใส่แบบเต็ม (mcp__peak__<ชื่อ>) ใน tools: ของ agents/peak-lookup.md",
        ])
        tools = data.get("tools") or {}
        row = tools.get(full) or {}
        row["kind"] = kind
        row["count"] = int(row.get("count") or 0) + 1
        row["last_seen"] = time.strftime("%Y-%m-%d %H:%M")
        tools[full] = row
        data["tools"] = tools
        tmp = path + ".tmp%d" % os.getpid()
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass


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
