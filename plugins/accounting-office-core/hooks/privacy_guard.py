#!/usr/bin/env python3
"""ด่านกันข้อมูลลูกค้ารั่วออกนอกเครื่อง (PDPA)

ระวัง: skill token-meter ของ plugin นี้เองอ่าน ~/.claude/projects/**/*.jsonl
และ tm_common.py ยิง POST ไป api.anthropic.com — กฎกว้าง ๆ จะทำให้ /token-report พังทันที
กฎจึงแคบมาก:

  * Read tool บนไฟล์ transcript  -> deny  (ความเสี่ยงคือเนื้อหาเข้า context ไม่ใช่การอ่าน)
    สคริปต์ token-meter ที่พิมพ์ออกมาแค่ยอดรวม ยังรันผ่าน Bash ได้ (path_guard ปล่อยให้)
  * ขณะ pin ลูกค้า: WebFetch / WebSearch -> deny
  * ขณะ pin ลูกค้า: mcp__* ทุกตัวที่ไม่ใช่ ERP -> deny
    กฎเดียวคลุม Gmail, ms365, Drive, Notion, Slack, Supabase, browser และทุก connector ในอนาคต
    โดยไม่ต้องดูแล blocklist ที่ตามไม่ทัน

PreToolUse: WebFetch|WebSearch|mcp__.*
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import audit            # noqa: E402
import clientpath as cp  # noqa: E402
import hookio           # noqa: E402
from state import State  # noqa: E402

TRANSCRIPT_RE = re.compile(r"[/\\]\.claude[/\\]projects[/\\].*\.jsonl$")
ERP_SERVER = re.compile(r"(?i)flow[_-]?account|(?:^|_)peak(?:account|mcp)?(?:_|$)")


def decide(event):
    tool = event.get("tool_name") or ""
    tool_input = event.get("tool_input") or {}
    st = State(event.get("session_id"))

    if tool == "Read":
        path = tool_input.get("file_path") or tool_input.get("path") or ""
        if TRANSCRIPT_RE.search(str(path)):
            return hookio.deny(
                "ไฟล์ transcript มีบทสนทนางานลูกค้าอยู่ (ชื่อบริษัท เลขผู้เสียภาษี ยอดเงิน) "
                "ห้ามอ่านเข้า context — ใช้ /token-report ซึ่งรันสคริปต์ที่พิมพ์ออกมาแค่ตัวเลขรวมแทน",
                rule_id="no-transcript-read")
        return hookio.skip()

    pin = st.pin()
    if not pin:
        return hookio.skip()    # ไม่ได้ทำงานลูกค้าอยู่ ไม่ใช่เรื่องของ guard ตัวนี้
    client = os.path.basename(pin["realpath"])

    if tool in ("WebFetch", "WebSearch"):
        return hookio.deny(
            "ขณะ pin ลูกค้า %s ห้ามต่อออกเน็ต — ข้อมูลอ้างอิงภาษีอยู่ใน references/ ของ skill แล้ว "
            "ถ้าจำเป็นต้องค้นจริงให้ /clear ก่อน" % client,
            rule_id="no-web-while-pinned")

    if tool.startswith("mcp__"):
        server = tool.split("__")[1] if len(tool.split("__")) > 2 else ""
        if ERP_SERVER.search(server):
            return hookio.skip()        # ปล่อยให้ erp_guard ของ plugin ERP ตัดสิน
        if server in _extra_allow():
            return hookio.skip()
        return hookio.deny(
            "ขณะ pin ลูกค้า %s ใช้ได้เฉพาะ MCP ของ ERP เท่านั้น — `%s` เป็นช่องทางที่ข้อมูลลูกค้า"
            "ออกนอกเครื่องได้ (PDPA) ถ้าจำเป็นจริงให้เพิ่มชื่อ server ใน extra_mcp_allow "
            "ของ %s/config.json" % (client, server, _config_dir()),
            rule_id="no-foreign-mcp")

    return hookio.skip()


def _config_dir():
    return os.environ.get("ACCOUNTING_OFFICE_STATE") \
        or os.path.join("~", ".accounting-office")


def _extra_allow():
    base = os.environ.get("ACCOUNTING_OFFICE_STATE") \
        or os.path.join(os.path.expanduser("~"), ".accounting-office")
    try:
        with open(os.path.join(os.path.expanduser(base), "config.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        value = data.get("extra_mcp_allow") or []
        return set(str(v) for v in value)
    except Exception:
        return set()


def _decide_and_log(event):
    decision = decide(event)
    audit.log(event, decision)
    return decision


if __name__ == "__main__":
    hookio.safe_main(
        _decide_and_log, "PreToolUse",
        hookio.fail_deny("guard ความเป็นส่วนตัวของ accounting-office ทำงานผิดพลาด — "
                         "หยุดไว้ก่อนเพื่อไม่ให้ข้อมูลลูกค้าหลุด"))
