"""จำแนก tool ของ MCP ว่าเป็นอ่าน เขียน หรือต้องห้าม

หลักการเดียวที่ทั้งไฟล์นี้ยืนอยู่บนมัน: **ตัดสินจาก verb ในตำแหน่ง action เท่านั้น
ห้ามใช้ substring** ถ้าใช้ substring จะบล็อกผิดตัวทันที เช่น

    accounting__list_payment_journal        มี "payment" แต่เป็น tool อ่าน
    company_settings__list_payment_channels มี "payment" แต่เป็น tool อ่าน
    overview__get_outstanding_payments      มี "payment" แต่เป็น tool อ่าน
    documents__get_creation_status          มี "creation" แต่เป็น tool ที่ระบบกันซ้ำ *ต้องใช้*

ทั้ง 4 ตัวอยู่ใน tools: allowlist ของ agents/flowaccount-lookup.md อยู่แล้ว
กลับกัน documents__get_share_link ขึ้นต้นด้วย get แต่เป็นการรั่วข้อมูล จึงต้องดักด้วยชื่อตรง

ชื่อ server ไม่แน่นอน: FlowAccount โผล่ได้ทั้ง mcp__flowaccount__… (จาก .mcp.json ของ plugin)
และ mcp__claude_ai_FlowAccount_MCP__… (จาก connector ของ claude.ai) จึงจับด้วย regex ไม่ใช่ prefix
"""
from __future__ import annotations

import re

FLOWACCOUNT = re.compile(r"(?i)flow[_-]?account")
PEAK = re.compile(r"(?i)(?:^|_)peak(?:account|mcp)?(?:_|$)")

# --- ผลการจำแนก ---
AUTH = "auth"
READ = "read"
CREATE = "create"
FORBIDDEN = "forbidden"
UNKNOWN = "unknown"

# ชั้น 1 — ล็อกอิน ต้องผ่านก่อนกฎอื่นทุกข้อ ไม่งั้นผู้ใช้เชื่อมต่อ PEAK ไม่ได้เลย
AUTH_RE = re.compile(r"(?i)^(authenticate|complete_authentication|authorize|oauth|login|connect)(_|$)")

# ชั้น 2 — ดักด้วยชื่อเต็ม สำหรับตัวที่ verb หลอกตา
EXACT_DENY = {
    "documents__email": "ส่งเอกสารออกทางอีเมล",
    "documents__get_share_link": "สร้างลิงก์แชร์เอกสารออกนอกระบบ",
    "gl__approve_journal_entry": "อนุมัติสมุดรายวัน",
    "gl__create_and_approve_journal_entry": "สร้างพร้อมอนุมัติสมุดรายวัน",
    "gl__create_journal_entry": "สร้างสมุดรายวันตรง ๆ (ข้ามการจับคู่หมวดหมู่และขั้น preview)",
    "gateway__submit_feedback": "ส่งข้อความออกไปนอกเครื่อง",
    "gateway__update_feedback": "ส่งข้อความออกไปนอกเครื่อง",
}

# ชั้น 3 — verb ที่ห้ามเด็ดขาด (กฎบังคับข้อ 4)
DENY_ACTION = re.compile(
    r"(?i)^(approve|unapprove|reapprove|void|cancel|delete|destroy|remove|purge|archive"
    r"|restore|revert|pay|payment|record_payment|make_payment|receive_payment|refund|settle"
    r"|submit|post|issue|finalize|lock|close_period|close_book"
    r"|email|mail|send|share|publish|broadcast|notify"
    r"|upload|attach|import|sync|push)(_|$)"
    r"|_and_approve(_|$)"
    r"|^get_(share|public|download|pdf|print)_link$"
)

# ชั้น 5 — แก้เอกสารที่มีอยู่แล้ว (ขอบเขตคือ "สร้างเอกสารรออนุมัติ" เท่านั้น)
UPDATE_ACTION = re.compile(r"(?i)^(update|edit|patch|set|modify|replace|merge)(_|$)")

# ชั้น 6 — verb อ่าน: ชั้นนี้คือสิ่งที่กันบล็อกผิดตัว
READ_ACTION = re.compile(
    r"(?i)^(list|get|search|find|fetch|read|load|describe|count|status|validate|verify"
    r"|preview|check|resolve)(_|$)")

# ชั้น 7 — verb สร้าง
CREATE_ACTION = re.compile(r"(?i)^(create|add|new|draft)(_|$)")

WRITE_ACTION = re.compile(r"(?i)^(create|add|new|draft|update|edit|patch|set|modify|save|issue)(_|$)")


def split_tool(name):
    """mcp__claude_ai_FlowAccount_MCP__expense__create_expense
       -> ('claude_ai_FlowAccount_MCP', 'expense', 'create_expense')"""
    parts = str(name or "").split("__")
    if len(parts) < 3 or parts[0] != "mcp":
        return None, None, None
    server = parts[1]
    rest = "__".join(parts[2:])
    namespace, _, action = rest.rpartition("__")
    return server, (namespace or None), (action or rest)


def is_vendor(server, vendor):
    if not server:
        return False
    pattern = FLOWACCOUNT if vendor == "flowaccount" else PEAK
    return bool(pattern.search(server))


def classify(namespace, action):
    """คืน (ประเภท, เหตุผลภาษาไทย) — ลำดับของ if สำคัญมาก อย่าสลับ"""
    ns = namespace or ""
    act = action or ""
    full = ("%s__%s" % (ns, act)) if ns else act

    if AUTH_RE.match(act):
        return AUTH, None

    if full in EXACT_DENY:
        return FORBIDDEN, EXACT_DENY[full]

    if DENY_ACTION.search(act):
        return FORBIDDEN, "เป็นการอนุมัติ ยกเลิก ลบ จ่ายชำระ หรือส่งข้อมูลออกนอกระบบ"

    if re.match(r"(?i)^sales(__|$)", ns) and WRITE_ACTION.match(act):
        return FORBIDDEN, "เอกสารฝั่งขายอยู่นอกขอบเขตของ plugin ชุดนี้"

    if UPDATE_ACTION.match(act):
        return FORBIDDEN, "แก้ไขเอกสารที่มีอยู่แล้ว — plugin ชุดนี้สร้างเอกสารรออนุมัติได้อย่างเดียว"

    if READ_ACTION.match(act):
        return READ, None

    if CREATE_ACTION.match(act):
        return CREATE, None

    return UNKNOWN, "ยังไม่ได้จัดประเภท verb `%s`" % act
