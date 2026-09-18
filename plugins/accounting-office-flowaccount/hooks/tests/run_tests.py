#!/usr/bin/env python3
"""ชุดทดสอบ hook ของ accounting-office-flowaccount

รัน:  python3 plugins/accounting-office-flowaccount/hooks/tests/run_tests.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HOOKS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.dirname(HOOKS)
REPO = os.path.dirname(os.path.dirname(PLUGIN))
sys.path.insert(0, HOOKS)
sys.path.insert(0, os.path.join(HOOKS, "lib"))

import clientpath as cp      # noqa: E402
import erp_guard             # noqa: E402
import erp_post              # noqa: E402
import erpname               # noqa: E402
import hookio                # noqa: E402
import payload_fa as payload  # noqa: E402
from state import State      # noqa: E402

VALID_ID = "0105567069510"
OTHER_ID = "0994000165676"
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

PREFIXES = ("mcp__flowaccount__", "mcp__claude_ai_FlowAccount_MCP__")


def good_doc(reference="INV-001", total=107.0, date="2026-09-01"):
    return {
        "document": {
            "reference": reference,
            "document_date": date,
            "contact_id": "c-1",
            "total": total,
            "is_vat_inclusive": True,
            "use_inline_vat": False,
            "use_inline_discount": False,
            "items": [{"category_id": "cat-1", "quantity": 1, "unit_price": total}],
        },
        "confirm": True,
    }


class TestClassification(unittest.TestCase):
    """เทสต์ที่คุ้มที่สุดในชุด — พิสูจน์ว่าด่านไม่บล็อกงานปกติ"""

    def _cases(self):
        with open(os.path.join(FIXTURES, "tool_names.txt"), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                name, expected = line.split()
                yield name, expected

    def test_golden_tool_list_under_both_prefixes(self):
        for name, expected in self._cases():
            for prefix in PREFIXES:
                _, ns, action = erpname.split_tool(prefix + name)
                kind, _ = erpname.classify(ns, action)
                self.assertEqual(kind, expected,
                                 "%s%s ควรเป็น %s แต่ได้ %s" % (prefix, name, expected, kind))

    def test_read_traps_are_not_blocked(self):
        """กับดัก substring — 4 ตัวนี้อยู่ใน allowlist ของ flowaccount-lookup อยู่แล้ว"""
        for name in ("accounting__list_payment_journal",
                     "company_settings__list_payment_channels",
                     "overview__get_outstanding_payments",
                     "documents__get_creation_status"):
            _, ns, action = erpname.split_tool("mcp__flowaccount__" + name)
            kind, _ = erpname.classify(ns, action)
            self.assertEqual(kind, erpname.READ, name)

    def test_share_link_blocked_despite_get_prefix(self):
        _, ns, action = erpname.split_tool("mcp__flowaccount__documents__get_share_link")
        self.assertEqual(erpname.classify(ns, action)[0], erpname.FORBIDDEN)

    def test_lookup_agent_allowlist_all_readable(self):
        """ทุก tool ใน tools: ของ agents/flowaccount-lookup.md ต้องไม่ถูกบล็อก"""
        agent = os.path.join(PLUGIN, "agents", "flowaccount-lookup.md")
        with open(agent, encoding="utf-8") as fh:
            body = fh.read()
        names = [t.strip() for t in body.split("tools:")[1].split("\n")[0].split(",")]
        names = [n for n in names if n.startswith("mcp__")]
        self.assertGreaterEqual(len(names), 5, "อ่าน allowlist จาก agent ไม่ได้")
        for name in names:
            _, ns, action = erpname.split_tool(name)
            kind, _ = erpname.classify(ns, action)
            self.assertIn(kind, (erpname.READ, erpname.AUTH), name)

    def test_other_vendor_not_matched(self):
        self.assertFalse(erpname.is_vendor("claude_ai_Gmail", "flowaccount"))
        self.assertFalse(erpname.is_vendor("claude_ai_PeakMCP", "flowaccount"))
        self.assertTrue(erpname.is_vendor("claude_ai_FlowAccount_MCP", "flowaccount"))
        self.assertTrue(erpname.is_vendor("flowaccount", "flowaccount"))
        self.assertTrue(erpname.is_vendor("claude_ai_PeakMCP", "peak"))


class TestPayload(unittest.TestCase):

    def test_good_payload_passes(self):
        self.assertEqual(payload.validate(good_doc()), [])

    def test_missing_category_id(self):
        doc = good_doc()
        doc["document"]["items"][0].pop("category_id")
        self.assertTrue(any("category_id" in e for e in payload.validate(doc)))

    def test_contact_id_and_name_together(self):
        doc = good_doc()
        doc["document"]["contact_name"] = "บริษัท ก"
        self.assertTrue(any("contact_id" in e for e in payload.validate(doc)))

    def test_missing_explicit_booleans(self):
        doc = good_doc()
        doc["document"].pop("is_vat_inclusive")
        self.assertTrue(any("is_vat_inclusive" in e for e in payload.validate(doc)))

    def test_false_boolean_is_a_valid_answer(self):
        """false เป็นคำตอบที่ถูก แต่ 'ไม่มี' ไม่ใช่ — ต้องเช็คด้วย in ไม่ใช่ truthiness"""
        doc = good_doc()
        doc["document"]["is_vat_inclusive"] = False
        self.assertEqual(payload.validate(doc), [])

    def test_buddhist_year_rejected(self):
        doc = good_doc(date="2569-09-01")
        self.assertTrue(any("พ.ศ." in e for e in payload.validate(doc)))

    def test_empty_reference_rejected(self):
        doc = good_doc(reference="")
        self.assertTrue(any("reference" in e for e in payload.validate(doc)))

    def test_arithmetic_mismatch_rejected(self):
        doc = good_doc()
        doc["document"]["total"] = 999.0
        self.assertTrue(any("ยอดรวมไม่ตรง" in e for e in payload.validate(doc)))

    def test_skip_duplicate_flag_rejected(self):
        doc = good_doc()
        doc["force"] = True
        self.assertTrue(any("force" in e for e in payload.validate(doc)))

    def test_is_commit(self):
        self.assertTrue(payload.is_commit({"confirm": True}))
        self.assertFalse(payload.is_commit({"confirm": False}))
        self.assertTrue(payload.is_commit({}))

    def test_dup_key_stable_and_distinct(self):
        self.assertEqual(payload.dup_key(good_doc()), payload.dup_key(good_doc()))
        self.assertNotEqual(payload.dup_key(good_doc()), payload.dup_key(good_doc("INV-002")))


class Base(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ao-fa-")
        os.environ["ACCOUNTING_OFFICE_STATE"] = os.path.join(self.tmp, "state")
        self.client = os.path.join(self.tmp, "ลูกค้า", "ตัวอย่าง")
        os.makedirs(os.path.join(self.client, "2569-09", "output"))
        with open(os.path.join(self.client, cp.PROFILE_NAME), "w", encoding="utf-8") as fh:
            fh.write("| เลขประจำตัวผู้เสียภาษี | %s |\n" % VALID_ID)
        self.session = "s-" + os.path.basename(self.tmp)
        self.st = State(self.session)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("ACCOUNTING_OFFICE_STATE", None)

    def ev(self, tool, tool_input, event="PreToolUse", response=None):
        payload_ev = {"hook_event_name": event, "session_id": self.session, "cwd": self.tmp,
                      "tool_name": tool, "tool_input": tool_input}
        if response is not None:
            payload_ev["tool_response"] = response
        return payload_ev

    def ready(self, company_taxid=VALID_ID):
        """พาไปถึงสถานะที่ผ่านเงื่อนไขข้อ 2 และ 3 แล้ว"""
        self.st.pin_once({"realpath": os.path.realpath(self.client), "pinned_at": time.time()})
        self.st.save("profile", {"read": True, "taxid": VALID_ID, "taxid_valid": True})
        self.st.save("erp-flowaccount", {"company_taxid": company_taxid,
                                         "company_name": "บริษัท ตัวอย่าง จำกัด"})
        return State(self.session)


class TestPreconditions(Base):

    CREATE = "mcp__flowaccount__expense__create_expense"

    def test_no_pin_denied(self):
        d = erp_guard.decide(self.ev(self.CREATE, good_doc()))
        self.assertEqual(d.rule_id, "erp-no-pin")

    def test_no_profile_read_denied(self):
        self.st.pin_once({"realpath": os.path.realpath(self.client), "pinned_at": time.time()})
        d = erp_guard.decide(self.ev(self.CREATE, good_doc()))
        self.assertEqual(d.rule_id, "erp-no-profile")

    def test_company_unverified_denied(self):
        self.st.pin_once({"realpath": os.path.realpath(self.client), "pinned_at": time.time()})
        self.st.save("profile", {"read": True, "taxid": VALID_ID, "taxid_valid": True})
        d = erp_guard.decide(self.ev(self.CREATE, good_doc()))
        self.assertEqual(d.rule_id, "erp-company-unverified")

    def test_company_mismatch_denied(self):
        self.ready(company_taxid=OTHER_ID)
        d = erp_guard.decide(self.ev(self.CREATE, good_doc()))
        self.assertEqual(d.rule_id, "erp-company-mismatch")

    def test_bad_profile_taxid_denied(self):
        self.st.pin_once({"realpath": os.path.realpath(self.client), "pinned_at": time.time()})
        self.st.save("profile", {"read": True, "taxid": "0105567069511", "taxid_valid": False})
        self.st.save("erp-flowaccount", {"company_taxid": "0105567069511"})
        d = erp_guard.decide(self.ev(self.CREATE, good_doc()))
        self.assertEqual(d.rule_id, "erp-bad-taxid")

    def test_reads_never_gated(self):
        """tool อ่านต้องผ่านแม้ยังไม่ pin — ไม่งั้น lookup agent ทำงานไม่ได้เลย"""
        d = erp_guard.decide(self.ev("mcp__flowaccount__contacts__list", {}))
        self.assertEqual(d.verdict, hookio.SKIP)

    def test_auth_never_gated(self):
        d = erp_guard.decide(self.ev("mcp__claude_ai_PeakMCP__authenticate", {}))
        self.assertEqual(d.verdict, hookio.SKIP)  # คนละ vendor -> skip


class TestForbidden(Base):

    def test_approve_denied(self):
        self.ready()
        d = erp_guard.decide(self.ev("mcp__flowaccount__gl__approve_journal_entry", {}))
        self.assertEqual(d.rule_id, "erp-forbidden")

    def test_email_denied(self):
        self.ready()
        d = erp_guard.decide(self.ev("mcp__flowaccount__documents__email", {}))
        self.assertEqual(d.rule_id, "erp-forbidden")

    def test_sales_create_denied(self):
        self.ready()
        d = erp_guard.decide(self.ev("mcp__flowaccount__sales__create_tax_invoice", {}))
        self.assertEqual(d.rule_id, "erp-forbidden")

    def test_forbidden_denied_even_before_pin(self):
        d = erp_guard.decide(self.ev("mcp__flowaccount__gl__approve_journal_entry", {}))
        self.assertEqual(d.rule_id, "erp-forbidden")


class TestBatchAndDuplicate(Base):

    CREATE = "mcp__flowaccount__expense__create_expense"
    STATUS = "mcp__flowaccount__documents__get_creation_status"

    def test_preview_passes_silently(self):
        self.ready()
        doc = good_doc()
        doc["confirm"] = False
        d = erp_guard.decide(self.ev(self.CREATE, doc))
        self.assertEqual(d.verdict, hookio.SKIP, "ขั้น preview ต้องไม่ถาม")

    def test_validate_tool_passes_silently(self):
        self.ready()
        d = erp_guard.decide(self.ev("mcp__flowaccount__expense__validate_expense", good_doc()))
        self.assertEqual(d.verdict, hookio.SKIP)

    def test_first_commit_asks_then_second_allows(self):
        self.ready()
        first = erp_guard.decide(self.ev(self.CREATE, good_doc("INV-001")))
        self.assertEqual(first.verdict, hookio.ASK)
        self.assertIn("รออนุมัติ", first.reason)
        second = erp_guard.decide(self.ev(self.CREATE, good_doc("INV-002", 214.0)))
        self.assertEqual(second.verdict, hookio.ALLOW)
        self.assertEqual(second.rule_id, "erp-batch-open")

    def test_duplicate_denied(self):
        self.ready()
        erp_guard.decide(self.ev(self.CREATE, good_doc("INV-001")))
        again = erp_guard.decide(self.ev(self.CREATE, good_doc("INV-001")))
        self.assertEqual(again.rule_id, "erp-duplicate")

    def test_status_check_unlocks_retry(self):
        self.ready()
        erp_guard.decide(self.ev(self.CREATE, good_doc("INV-001")))
        erp_post.decide(self.ev(self.STATUS, {}, "PostToolUse", response='{"status":"awaiting"}'))
        again = erp_guard.decide(self.ev(self.CREATE, good_doc("INV-001")))
        self.assertNotEqual(again.rule_id, "erp-duplicate")

    def test_batch_expires_after_ceiling(self):
        st = self.ready()
        erp_guard.decide(self.ev(self.CREATE, good_doc("INV-001")))
        erp = st.load("erp-flowaccount")
        erp["batch"]["count"] = erp_guard.BATCH_MAX_DOCS
        st.save("erp-flowaccount", erp)
        d = erp_guard.decide(self.ev(self.CREATE, good_doc("INV-999", 321.0)))
        self.assertEqual(d.verdict, hookio.ASK)

    def test_batch_expires_after_idle(self):
        st = self.ready()
        erp_guard.decide(self.ev(self.CREATE, good_doc("INV-001")))
        erp = st.load("erp-flowaccount")
        erp["batch"]["last_commit_at"] = time.time() - erp_guard.BATCH_IDLE_GAP - 60
        st.save("erp-flowaccount", erp)
        d = erp_guard.decide(self.ev(self.CREATE, good_doc("INV-999", 321.0)))
        self.assertEqual(d.verdict, hookio.ASK)

    def test_preview_after_commit_restarts_batch(self):
        self.ready()
        erp_guard.decide(self.ev(self.CREATE, good_doc("INV-001")))
        preview = good_doc("INV-050", 500.0)
        preview["confirm"] = False
        erp_guard.decide(self.ev(self.CREATE, preview))
        d = erp_guard.decide(self.ev(self.CREATE, good_doc("INV-050", 500.0)))
        self.assertEqual(d.verdict, hookio.ASK, "เจอ preview คั่น = กองใหม่ ต้องถามอีกรอบ")

    def test_bad_payload_denied_before_ask(self):
        self.ready()
        doc = good_doc()
        doc["document"]["items"][0].pop("category_id")
        d = erp_guard.decide(self.ev(self.CREATE, doc))
        self.assertEqual(d.rule_id, "erp-payload")


class TestPostHook(Base):

    def test_company_load_captures_taxid(self):
        self.st.pin_once({"realpath": os.path.realpath(self.client), "pinned_at": time.time()})
        self.st.save("profile", {"read": True, "taxid": VALID_ID, "taxid_valid": True})
        erp_post.decide(self.ev("mcp__flowaccount__company_settings__load", {}, "PostToolUse",
                                response='{"name":"บริษัท ตัวอย่าง จำกัด","taxId":"%s"}' % VALID_ID))
        erp = State(self.session).load("erp-flowaccount")
        self.assertEqual(erp["company_taxid"], VALID_ID)
        self.assertEqual(erp["company_name"], "บริษัท ตัวอย่าง จำกัด")

    def test_company_mismatch_warns_loudly(self):
        self.st.save("profile", {"read": True, "taxid": VALID_ID, "taxid_valid": True})
        d = erp_post.decide(self.ev("mcp__flowaccount__company_settings__load", {}, "PostToolUse",
                                    response='{"taxId":"%s"}' % OTHER_ID))
        self.assertEqual(d.rule_id, "erp-company-mismatch")

    def test_permission_denied_sets_kill_switch(self):
        self.ready()
        erp_post.decide(self.ev("mcp__flowaccount__expense__create_expense", good_doc(),
                                "PostToolUse", response='{"error":"permission_denied"}'))
        d = erp_guard.decide(self.ev("mcp__flowaccount__expense__create_expense", good_doc("X-1")))
        self.assertEqual(d.rule_id, "erp-kill-switch")

    def test_non_awaiting_status_warns(self):
        self.ready()
        d = erp_post.decide(self.ev("mcp__flowaccount__expense__create_expense", good_doc(),
                                    "PostToolUse", response='{"id":"d1","status":"approved"}'))
        self.assertEqual(d.rule_id, "erp-bad-status")

    def test_awaiting_status_silent(self):
        self.ready()
        d = erp_post.decide(self.ev("mcp__flowaccount__expense__create_expense", good_doc(),
                                    "PostToolUse", response='{"id":"d1","status":"awaiting"}'))
        self.assertEqual(d.verdict, hookio.SKIP)
        self.assertIsNone(d.context)

    def test_batch_file_write_resets_batch(self):
        st = self.ready()
        erp_guard.decide(self.ev("mcp__flowaccount__expense__create_expense", good_doc()))
        erp_post.decide(self.ev("Write", {
            "file_path": os.path.join(self.client, "2569-09/output/post-flowaccount-2569-09.md")},
            "PostToolUse"))
        self.assertFalse(State(self.session).load("erp-flowaccount").get("batch"))


class TestFailMode(Base):

    def test_crash_denies(self):
        script = (
            "import sys; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
            "import hookio\n"
            "def boom(ev): raise RuntimeError('boom')\n"
            "hookio.safe_main(boom, 'PreToolUse', hookio.fail_deny('ด่าน ERP พัง'))\n"
        ) % (HOOKS, os.path.join(HOOKS, "lib"))
        proc = subprocess.run([sys.executable, "-c", script], input="{}",
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_smoke_valid_json(self):
        self.ready()
        for script, ev in (("erp_guard.py", self.ev("mcp__flowaccount__contacts__list", {})),
                           ("erp_post.py", self.ev("mcp__flowaccount__company_settings__load", {},
                                                   "PostToolUse", response="{}"))):
            proc = subprocess.run([os.path.join(HOOKS, "run.sh"), script],
                                  input=json.dumps(ev), capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIsInstance(json.loads(proc.stdout), dict)


if __name__ == "__main__":
    unittest.main(verbosity=2)
