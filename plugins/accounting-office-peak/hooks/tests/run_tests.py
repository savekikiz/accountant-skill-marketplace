#!/usr/bin/env python3
"""ชุดทดสอบ hook ของ accounting-office-peak (learn-mode)

รัน:  python3 plugins/accounting-office-peak/hooks/tests/run_tests.py
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
import payload_peak as payload  # noqa: E402
from state import State      # noqa: E402

VALID_ID = "0105567069510"
OTHER_ID = "0994000165676"

PREFIXES = ("mcp__peak__", "mcp__claude_ai_PeakMCP__")


class Base(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ao-peak-")
        os.environ["ACCOUNTING_OFFICE_STATE"] = os.path.join(self.tmp, "state")
        os.environ["CLAUDE_PLUGIN_DATA"] = os.path.join(self.tmp, "plugindata")
        self.client = os.path.join(self.tmp, "ลูกค้า", "ตัวอย่าง")
        os.makedirs(os.path.join(self.client, "2569-09", "output"))
        with open(os.path.join(self.client, cp.PROFILE_NAME), "w", encoding="utf-8") as fh:
            fh.write("| เลขประจำตัวผู้เสียภาษี | %s |\n" % VALID_ID)
        self.session = "s-" + os.path.basename(self.tmp)
        self.st = State(self.session)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("ACCOUNTING_OFFICE_STATE", None)
        os.environ.pop("CLAUDE_PLUGIN_DATA", None)

    def ev(self, tool, tool_input, event="PreToolUse", response=None):
        payload_ev = {"hook_event_name": event, "session_id": self.session, "cwd": self.tmp,
                      "tool_name": tool, "tool_input": tool_input}
        if response is not None:
            payload_ev["tool_response"] = response
        return payload_ev

    def ready(self, company_taxid=VALID_ID):
        self.st.pin_once({"realpath": os.path.realpath(self.client), "pinned_at": time.time()})
        self.st.save("profile", {"read": True, "taxid": VALID_ID, "taxid_valid": True})
        self.st.save("erp-peak", {"company_taxid": company_taxid,
                                  "company_name": "บริษัท ตัวอย่าง จำกัด"})
        return State(self.session)


class TestVendorMatching(unittest.TestCase):

    def test_both_prefixes_recognised(self):
        for prefix in PREFIXES:
            server, _, _ = erpname.split_tool(prefix + "documents__create_expense")
            self.assertTrue(erpname.is_vendor(server, "peak"), prefix)

    def test_flowaccount_not_matched(self):
        server, _, _ = erpname.split_tool("mcp__claude_ai_FlowAccount_MCP__contacts__list")
        self.assertFalse(erpname.is_vendor(server, "peak"))

    def test_unrelated_server_ignored(self):
        server, _, _ = erpname.split_tool("mcp__claude_ai_Gmail__send_message")
        self.assertFalse(erpname.is_vendor(server, "peak"))


class TestLearnMode(Base):

    def test_auth_allowed_before_anything(self):
        """ถ้าด่านบล็อก authenticate ผู้ใช้จะเชื่อมต่อ PEAK ไม่ได้เลย"""
        for prefix in PREFIXES:
            d = erp_guard.decide(self.ev(prefix + "authenticate", {}))
            self.assertEqual(d.verdict, hookio.ALLOW, prefix)
        d = erp_guard.decide(self.ev("mcp__claude_ai_PeakMCP__complete_authentication", {}))
        self.assertEqual(d.verdict, hookio.ALLOW)

    def test_clear_read_verbs_pass(self):
        for name in ("contacts__list", "accounting__get_chart_of_accounts",
                     "documents__get_document", "expense__list_expenses"):
            d = erp_guard.decide(self.ev("mcp__peak__" + name, {}))
            self.assertEqual(d.verdict, hookio.SKIP, name)

    def test_forbidden_verbs_denied(self):
        for name in ("documents__approve", "documents__void_document", "expense__delete_expense",
                     "payment__record_payment", "documents__send_email", "sales__create_invoice"):
            d = erp_guard.decide(self.ev("mcp__peak__" + name, {}))
            self.assertEqual(d.rule_id, "erp-forbidden", name)

    def test_unknown_verb_denied_not_asked(self):
        """FlowAccount ask / PEAK deny — สะท้อนว่า tools: [] ของ peak-lookup ตั้งใจให้เป็นแบบนี้"""
        self.ready()
        d = erp_guard.decide(self.ev("mcp__peak__documents__ทำอะไรสักอย่าง", {}))
        self.assertEqual(d.rule_id, "erp-unknown-peak")
        self.assertIn("peak-tools.json", d.reason)

    def test_allowlisted_unknown_tool_passes(self):
        path = os.path.join(HOOKS, "peak-tools.json")
        with open(path, encoding="utf-8") as fh:
            original = fh.read()
        try:
            data = json.loads(original)
            data["read_tools"] = ["documents__ทำอะไรสักอย่าง"]
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False)
            d = erp_guard.decide(self.ev("mcp__peak__documents__ทำอะไรสักอย่าง", {}))
            self.assertEqual(d.verdict, hookio.SKIP)
        finally:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(original)

    def test_create_asks_every_single_document(self):
        """ตรวจ payload ไม่ได้ จึงไม่มีสิทธิ์ปล่อยทั้งกองด้วยการกดครั้งเดียว"""
        self.ready()
        for ref in ("A-1", "A-2", "A-3"):
            d = erp_guard.decide(self.ev("mcp__peak__expense__create_expense",
                                         {"reference": ref, "total": 100}))
            self.assertEqual(d.verdict, hookio.ASK, ref)
            self.assertEqual(d.rule_id, "erp-ask-every-doc")
            self.assertIn("ยังไม่พร้อมใช้", d.reason)

    def test_preconditions_enforced(self):
        d = erp_guard.decide(self.ev("mcp__peak__expense__create_expense", {"reference": "A-1"}))
        self.assertEqual(d.rule_id, "erp-no-pin")

    def test_company_mismatch_denied(self):
        self.ready(company_taxid=OTHER_ID)
        d = erp_guard.decide(self.ev("mcp__peak__expense__create_expense", {"reference": "A-1"}))
        self.assertEqual(d.rule_id, "erp-company-mismatch")

    def test_identical_payload_denied_as_duplicate(self):
        self.ready()
        body = {"reference": "A-1", "total": 100}
        erp_guard.decide(self.ev("mcp__peak__expense__create_expense", body))
        again = erp_guard.decide(self.ev("mcp__peak__expense__create_expense", body))
        self.assertEqual(again.rule_id, "erp-duplicate")

    def test_skip_dup_flag_denied(self):
        self.ready()
        d = erp_guard.decide(self.ev("mcp__peak__expense__create_expense",
                                     {"reference": "A-1", "force": True}))
        self.assertEqual(d.rule_id, "erp-payload")

    def test_payload_module_claims_nothing(self):
        """stub ต้องไม่แกล้งตรวจ payload ที่ไม่เคยเห็น"""
        self.assertFalse(payload.AVAILABLE)
        self.assertEqual(payload.validate({"อะไรก็ได้": 1}), [])


class TestObservedTools(Base):

    def test_tool_names_are_recorded_for_the_user(self):
        erp_post.decide(self.ev("mcp__peak__contacts__list", {}, "PostToolUse", response="[]"))
        erp_post.decide(self.ev("mcp__peak__documents__approve", {}, "PostToolUse", response="{}"))
        path = os.path.join(os.environ["CLAUDE_PLUGIN_DATA"], "observed-tools.json")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data["tools"]["contacts__list"]["kind"], erpname.READ)
        self.assertEqual(data["tools"]["documents__approve"]["kind"], erpname.FORBIDDEN)

    def test_repeat_calls_counted(self):
        for _ in range(3):
            erp_post.decide(self.ev("mcp__peak__contacts__list", {}, "PostToolUse", response="[]"))
        path = os.path.join(os.environ["CLAUDE_PLUGIN_DATA"], "observed-tools.json")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data["tools"]["contacts__list"]["count"], 3)


class TestPostHook(Base):

    def test_permission_denied_sets_kill_switch(self):
        self.ready()
        erp_post.decide(self.ev("mcp__peak__expense__create_expense", {"reference": "A"},
                                "PostToolUse", response='{"error":"permission_denied"}'))
        d = erp_guard.decide(self.ev("mcp__peak__expense__create_expense", {"reference": "B"}))
        self.assertEqual(d.rule_id, "erp-kill-switch")

    def test_non_awaiting_status_warns(self):
        self.ready()
        d = erp_post.decide(self.ev("mcp__peak__expense__create_expense", {"reference": "A"},
                                    "PostToolUse", response='{"status":"approved"}'))
        self.assertEqual(d.rule_id, "erp-bad-status")

    def test_company_tool_captures_taxid(self):
        self.st.save("profile", {"read": True, "taxid": VALID_ID, "taxid_valid": True})
        erp_post.decide(self.ev("mcp__peak__company__get_info", {}, "PostToolUse",
                                response='{"name":"บริษัท ตัวอย่าง จำกัด","taxId":"%s"}' % VALID_ID))
        self.assertEqual(State(self.session).load("erp-peak")["company_taxid"], VALID_ID)


class TestFailMode(Base):

    def test_crash_denies(self):
        script = (
            "import sys; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
            "import hookio\n"
            "def boom(ev): raise RuntimeError('boom')\n"
            "hookio.safe_main(boom, 'PreToolUse', hookio.fail_deny('ด่าน PEAK พัง'))\n"
        ) % (HOOKS, os.path.join(HOOKS, "lib"))
        proc = subprocess.run([sys.executable, "-c", script], input="{}",
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_smoke_valid_json(self):
        self.ready()
        for script, ev in (("erp_guard.py", self.ev("mcp__peak__contacts__list", {})),
                           ("erp_post.py", self.ev("mcp__peak__contacts__list", {},
                                                   "PostToolUse", response="[]"))):
            proc = subprocess.run([os.path.join(HOOKS, "run.sh"), script],
                                  input=json.dumps(ev), capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIsInstance(json.loads(proc.stdout), dict)


if __name__ == "__main__":
    unittest.main(verbosity=2)
