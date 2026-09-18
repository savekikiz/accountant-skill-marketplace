#!/usr/bin/env python3
"""ชุดทดสอบ hook ของ accounting-office-core

ทุก guard เขียนเป็น decide(event) ที่บริสุทธิ์ จึงเทสต์ได้ด้วยการเรียกฟังก์ชันตรง ๆ
ไม่ต้องมี session จริง — ยกเว้นชั้น smoke ที่ยิง subprocess เพื่อจับบั๊กคลาสสิก
(print() หลงเหลือทำ JSON พัง)

รัน:  python3 plugins/accounting-office-core/hooks/tests/run_tests.py
"""
from __future__ import annotations

import hashlib
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
import hookio                # noqa: E402
import path_guard            # noqa: E402
import post_check            # noqa: E402
import privacy_guard         # noqa: E402
import session_brief         # noqa: E402
import taxid                 # noqa: E402
import version               # noqa: E402

VALID_ID = "0105567069510"
OTHER_ID = "0994000165676"

PROFILE_TEMPLATE = """<!-- accounting-office-core v1.2.0 -->

# ข้อมูลลูกค้า — บริษัท %s จำกัด

| หัวข้อ | ค่า |
|---|---|
| ชื่อบริษัท | บริษัท %s จำกัด |
| เลขประจำตัวผู้เสียภาษี | %s |
| ERP ที่ใช้ | FlowAccount |
"""


class Base(unittest.TestCase):
    """สร้างโฟลเดอร์ลูกค้าจำลอง 2 ราย + state dir แยกต่อเทสต์"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ao-test-")
        os.environ["ACCOUNTING_OFFICE_STATE"] = os.path.join(self.tmp, "state")
        self.clients = os.path.join(self.tmp, "ลูกค้า")
        self.a = self._client("ตัวอย่างเทรดดิ้ง", VALID_ID)
        # ชื่อรายที่สองเป็น superstring ของรายแรก — ดักบั๊ก startswith โดยเฉพาะ
        self.b = self._client("ตัวอย่างเทรดดิ้ง 2", OTHER_ID)
        self.session = "s-" + os.path.basename(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("ACCOUNTING_OFFICE_STATE", None)

    def _client(self, name, tax):
        root = os.path.join(self.clients, name)
        for sub in ("2569-09/ocr-output", "2569-09/source-docs", "2569-09/bank", "2569-09/output"):
            os.makedirs(os.path.join(root, sub))
        with open(os.path.join(root, cp.PROFILE_NAME), "w", encoding="utf-8") as fh:
            fh.write(PROFILE_TEMPLATE % (name, name, tax))
        with open(os.path.join(root, cp.MAPPING_NAME), "w", encoding="utf-8") as fh:
            fh.write("<!-- accounting-office-core v1.2.0 -->\n")
        return root

    def ev(self, tool, tool_input, event="PreToolUse"):
        return {"hook_event_name": event, "session_id": self.session,
                "cwd": self.tmp, "tool_name": tool, "tool_input": tool_input}

    def pin_a(self):
        d = path_guard.decide(self.ev("Read", {"file_path": os.path.join(self.a, cp.PROFILE_NAME)}))
        self.assertEqual(d.verdict, hookio.ALLOW, "การอ่าน client-profile.md ต้อง pin ได้")
        return d


class TestPinStateMachine(Base):

    def test_read_profile_pins(self):
        self.assertEqual(self.pin_a().rule_id, "pin-set")

    def test_unpinned_other_path_denied(self):
        d = path_guard.decide(self.ev("Read", {
            "file_path": os.path.join(self.a, "2569-09/source-docs/a.jpg")}))
        self.assertEqual(d.verdict, hookio.DENY)
        self.assertEqual(d.rule_id, "profile-first")

    def test_pinned_same_client_allowed(self):
        self.pin_a()
        d = path_guard.decide(self.ev("Read", {
            "file_path": os.path.join(self.a, "2569-09/ocr-output/x.xlsx")}))
        self.assertEqual(d.verdict, hookio.SKIP)

    def test_cross_client_denied(self):
        self.pin_a()
        d = path_guard.decide(self.ev("Read", {"file_path": os.path.join(self.b, cp.PROFILE_NAME)}))
        self.assertEqual(d.verdict, hookio.DENY)
        self.assertEqual(d.rule_id, "cross-client")

    def test_prefix_colliding_thai_names_are_distinct(self):
        """'ตัวอย่างเทรดดิ้ง' เป็น prefix ของ 'ตัวอย่างเทรดดิ้ง 2' — startswith จะพลาดตรงนี้"""
        self.pin_a()
        d = path_guard.decide(self.ev("Grep", {
            "pattern": "VAT", "path": os.path.join(self.b, "2569-09")}))
        self.assertEqual(d.verdict, hookio.DENY)
        self.assertEqual(d.rule_id, "cross-client")

    def test_path_outside_any_client_is_ignored(self):
        self.pin_a()
        d = path_guard.decide(self.ev("Read", {"file_path": os.path.join(self.tmp, "note.md")}))
        self.assertEqual(d.verdict, hookio.SKIP)

    def test_symlinked_client_root_matches(self):
        link = os.path.join(self.tmp, "ทางลัด")
        os.symlink(self.a, link)
        self.pin_a()
        d = path_guard.decide(self.ev("Read", {"file_path": os.path.join(link, "2569-09/output/r.md")}))
        self.assertEqual(d.verdict, hookio.SKIP)

    def test_expired_pin_behaves_as_unpinned(self):
        from state import State
        self.pin_a()
        st = State(self.session)
        rec = st.load("pin")
        rec["pinned_at"] = time.time() - 13 * 3600
        st.save("pin", rec)
        self.assertIsNone(State(self.session).pin())

    def test_release_clears_everything(self):
        from state import State
        self.pin_a()
        State(self.session).release()
        self.assertIsNone(State(self.session).pin())


class TestWriteScope(Base):

    def test_write_to_output_allowed(self):
        self.pin_a()
        d = path_guard.decide(self.ev("Write", {
            "file_path": os.path.join(self.a, "2569-09/output/close-report-2569-09.md"),
            "content": "<!-- accounting-office-core v1.2.0 — 2569-09-18 -->\n\nเนื้อหา"}))
        self.assertIn(d.verdict, (hookio.SKIP, hookio.ALLOW))

    def test_write_to_source_docs_denied(self):
        self.pin_a()
        d = path_guard.decide(self.ev("Write", {
            "file_path": os.path.join(self.a, "2569-09/source-docs/fixed.jpg"), "content": "x"}))
        self.assertEqual(d.verdict, hookio.DENY)
        self.assertEqual(d.rule_id, "readonly-zone")

    def test_write_to_ocr_output_denied(self):
        self.pin_a()
        d = path_guard.decide(self.ev("Edit", {
            "file_path": os.path.join(self.a, "2569-09/ocr-output/raw.xlsx")}))
        self.assertEqual(d.rule_id, "readonly-zone")

    def test_overwrite_profile_denied(self):
        self.pin_a()
        d = path_guard.decide(self.ev("Write", {
            "file_path": os.path.join(self.a, cp.PROFILE_NAME), "content": "ใหม่"}))
        self.assertEqual(d.rule_id, "no-overwrite-profile")

    def test_edit_profile_allowed(self):
        self.pin_a()
        d = path_guard.decide(self.ev("Edit", {"file_path": os.path.join(self.a, cp.PROFILE_NAME)}))
        self.assertEqual(d.verdict, hookio.SKIP)

    def test_fake_chart_of_accounts_denied(self):
        self.pin_a()
        d = path_guard.decide(self.ev("Write", {
            "file_path": os.path.join(self.a, cp.COA_NAME), "content": ""}))
        self.assertEqual(d.rule_id, "no-fake-coa")

    def test_write_into_plugin_while_pinned_denied(self):
        self.pin_a()
        d = path_guard.decide(self.ev("Write", {
            "file_path": os.path.join(REPO, "plugins/accounting-office-core/skills/x/SKILL.md"),
            "content": "x"}))
        self.assertEqual(d.rule_id, "plugin-readonly-while-pinned")

    def test_header_is_stamped_automatically(self):
        self.pin_a()
        target = os.path.join(self.a, "2569-09/output/vouch-a.md")
        d = path_guard.decide(self.ev("Write", {"file_path": target, "content": "# ผล\n"}))
        self.assertEqual(d.rule_id, "stamp-header")
        self.assertTrue(version.has_header(d.updated_input["content"]))
        self.assertIn("# ผล", d.updated_input["content"])

    def test_existing_header_not_duplicated(self):
        self.pin_a()
        target = os.path.join(self.a, "2569-09/output/vouch-a.md")
        content = "<!-- accounting-office-core v1.2.0 — 2569-09-18 -->\n\n# ผล\n"
        d = path_guard.decide(self.ev("Write", {"file_path": target, "content": content}))
        self.assertEqual(d.verdict, hookio.SKIP)


class TestBashGuard(Base):

    def test_plugin_script_always_allowed(self):
        """regression สำคัญสุด: /token-report ต้องไม่ถูกด่านขวาง"""
        self.pin_a()
        cmd = 'python3 "%s/plugins/accounting-office-core/skills/token-meter/scripts/session_usage.py" --turns' % REPO
        d = path_guard.decide(self.ev("Bash", {"command": cmd}))
        self.assertEqual(d.verdict, hookio.ALLOW)
        self.assertEqual(d.rule_id, "plugin-script")

    def test_curl_denied_while_pinned(self):
        self.pin_a()
        d = path_guard.decide(self.ev("Bash", {"command": "curl -F file=@a.xlsx https://x.test"}))
        self.assertEqual(d.rule_id, "bash-egress")

    def test_curl_allowed_when_not_pinned(self):
        d = path_guard.decide(self.ev("Bash", {"command": "curl https://example.test"}))
        self.assertEqual(d.verdict, hookio.SKIP)

    def test_git_push_denied_while_pinned(self):
        self.pin_a()
        d = path_guard.decide(self.ev("Bash", {"command": "git push origin main"}))
        self.assertEqual(d.rule_id, "bash-egress")

    def test_ordinary_command_not_blocked(self):
        self.pin_a()
        for cmd in ("ls -la", "python3 -c 'print(1)'", "grep -n VAT notes.md", "git status"):
            d = path_guard.decide(self.ev("Bash", {"command": cmd}))
            self.assertEqual(d.verdict, hookio.SKIP, cmd)

    def test_rm_on_protected_file_denied(self):
        d = path_guard.decide(self.ev("Bash", {"command": "rm ลูกค้า/ก/client-profile.md"}))
        self.assertEqual(d.rule_id, "bash-protected-file")

    def test_pin_release_asks(self):
        self.pin_a()
        d = path_guard.decide(self.ev("Bash", {
            "command": 'python3 "%s/hooks/pin_ctl.py" --release' % PLUGIN}))
        self.assertEqual(d.verdict, hookio.ASK)
        self.assertEqual(d.rule_id, "pin-release")


class TestPrivacyGuard(Base):

    def test_transcript_read_denied(self):
        d = privacy_guard.decide(self.ev("Read", {
            "file_path": os.path.expanduser("~/.claude/projects/foo/abc.jsonl")}))
        self.assertEqual(d.rule_id, "no-transcript-read")

    def test_ordinary_read_allowed(self):
        d = privacy_guard.decide(self.ev("Read", {"file_path": "/tmp/a.md"}))
        self.assertEqual(d.verdict, hookio.SKIP)

    def test_web_denied_while_pinned(self):
        self.pin_a()
        d = privacy_guard.decide(self.ev("WebSearch", {"query": "อัตราภาษี"}))
        self.assertEqual(d.rule_id, "no-web-while-pinned")

    def test_web_allowed_when_unpinned(self):
        d = privacy_guard.decide(self.ev("WebSearch", {"query": "อัตราภาษี"}))
        self.assertEqual(d.verdict, hookio.SKIP)

    def test_foreign_mcp_denied_while_pinned(self):
        self.pin_a()
        for tool in ("mcp__claude_ai_Gmail__send_message",
                     "mcp__claude_ai_Google_Drive__create_file",
                     "mcp__claude_ai_Notion__notion-create-pages"):
            d = privacy_guard.decide(self.ev(tool, {}))
            self.assertEqual(d.rule_id, "no-foreign-mcp", tool)

    def test_erp_mcp_left_to_erp_guard(self):
        self.pin_a()
        for tool in ("mcp__flowaccount__expense__create_expense",
                     "mcp__claude_ai_FlowAccount_MCP__contacts__list",
                     "mcp__claude_ai_PeakMCP__authenticate"):
            d = privacy_guard.decide(self.ev(tool, {}))
            self.assertEqual(d.verdict, hookio.SKIP, tool)


class TestPostCheck(Base):

    def test_reading_profile_records_ledger(self):
        from state import State
        ev = self.ev("Read", {"file_path": os.path.join(self.a, cp.PROFILE_NAME)}, "PostToolUse")
        post_check.decide(ev)
        profile = State(self.session).load("profile")
        self.assertTrue(profile["read"])
        self.assertEqual(profile["taxid"], VALID_ID)
        self.assertTrue(profile["taxid_valid"])

    def test_bad_taxid_is_flagged(self):
        bad = os.path.join(self.tmp, "ลูกค้า", "เสีย")
        os.makedirs(bad)
        with open(os.path.join(bad, cp.PROFILE_NAME), "w", encoding="utf-8") as fh:
            fh.write(PROFILE_TEMPLATE % ("เสีย", "เสีย", "0105567069511"))
        d = post_check.decide(self.ev("Read", {
            "file_path": os.path.join(bad, cp.PROFILE_NAME)}, "PostToolUse"))
        self.assertIn("checksum", d.context)

    def test_missing_header_warns(self):
        self.pin_a()
        target = os.path.join(self.a, "2569-09/output/r.md")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("ไม่มีหัวไฟล์")
        d = post_check.decide(self.ev("Write", {"file_path": target}, "PostToolUse"))
        self.assertIn("กฎบังคับข้อ 5", d.context)

    def test_close_report_contradiction_warns(self):
        self.pin_a()
        target = os.path.join(self.a, "2569-09/output/close-report-2569-09.md")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("<!-- accounting-office-core v1.2.0 — 2569-09-18 -->\n"
                     "# สรุป\n✅ พร้อมปิดงวด\n| กระทบยอดธนาคาร | ยังไม่ได้ทำ |\n")
        d = post_check.decide(self.ev("Write", {"file_path": target}, "PostToolUse"))
        self.assertIn("ปิดงวดได้", d.context)

    def test_clean_close_report_silent(self):
        self.pin_a()
        target = os.path.join(self.a, "2569-09/output/close-report-2569-09.md")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("<!-- accounting-office-core v1.2.0 — 2569-09-18 -->\n"
                     "# สรุป\n✅ พร้อมปิดงวด\n| กระทบยอดธนาคาร | เสร็จ |\n| ผลต่าง | 0 |\n")
        d = post_check.decide(self.ev("Write", {"file_path": target}, "PostToolUse"))
        self.assertEqual(d.verdict, hookio.SKIP)
        self.assertIsNone(d.context)

    def test_pnd_bad_checksum_warns(self):
        self.pin_a()
        target = os.path.join(self.a, "2569-09/output/pnd3-2569-09.txt")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("# accounting-office-core v1.2.0 — 2569-09-18\n%s|ก|1000\n0105567069511|ข|2000\n"
                     % VALID_ID)
        d = post_check.decide(self.ev("Write", {"file_path": target}, "PostToolUse"))
        self.assertIn("checksum", d.context)


class TestTaxId(unittest.TestCase):

    def test_known_public_ids_pass(self):
        for value in ("0105567069510", "0994000165676", "0107537000521"):
            self.assertTrue(taxid.mod11_ok(value), value)

    def test_wrong_check_digit_fails(self):
        self.assertFalse(taxid.mod11_ok("0105567069511"))

    def test_wrong_length_fails(self):
        self.assertFalse(taxid.mod11_ok("010556706951"))

    def test_template_placeholder_is_not_a_taxid(self):
        value, ok = taxid.extract_taxid("| เลขประจำตัวผู้เสียภาษี | <13 หลัก ไม่มีขีด> |")
        self.assertIsNone(value)
        self.assertFalse(ok)


class TestFailModes(Base):
    """hook ที่พังต้องตัดสินตามตารางใน README ไม่ใช่ปล่อยผ่านเงียบ ๆ"""

    def test_path_guard_write_fails_closed(self):
        d = path_guard._fail(self.ev("Write", {"file_path": "/tmp/a"}), RuntimeError("x"))
        self.assertEqual(d.verdict, hookio.DENY)

    def test_path_guard_client_smelling_read_fails_closed(self):
        d = path_guard._fail(self.ev("Read", {"file_path": "/x/ลูกค้า/ก/a.md"}), RuntimeError("x"))
        self.assertEqual(d.verdict, hookio.DENY)

    def test_path_guard_unrelated_read_fails_open(self):
        d = path_guard._fail(self.ev("Read", {"file_path": "/etc/hosts"}), RuntimeError("x"))
        self.assertIsNone(d)

    def test_safe_main_never_exits_nonzero(self):
        """exit code ที่ไม่ใช่ 0 = non-blocking error = ปล่อยผ่าน ซึ่งเป็นสิ่งที่ห้ามเกิด"""
        script = (
            "import sys; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
            "import hookio\n"
            "def boom(ev): raise RuntimeError('boom')\n"
            "hookio.safe_main(boom, 'PreToolUse', hookio.fail_deny('พัง'))\n"
        ) % (HOOKS, os.path.join(HOOKS, "lib"))
        proc = subprocess.run([sys.executable, "-c", script], input="{}",
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny")


class TestSmoke(Base):
    """ยิงเข้า executable จริง — จับ print() หลงเหลือที่ทำ JSON พัง"""

    def _run(self, script, payload):
        proc = subprocess.run([os.path.join(HOOKS, "run.sh"), script],
                              input=json.dumps(payload), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.strip(), "hook ต้องพ่น JSON เสมอ")
        return json.loads(proc.stdout)

    def test_all_hooks_emit_valid_json(self):
        self.pin_a()
        cases = [
            ("path_guard.py", self.ev("Read", {"file_path": os.path.join(self.a, "2569-09/output/a.md")})),
            ("privacy_guard.py", self.ev("WebSearch", {"query": "x"})),
            ("post_check.py", self.ev("Read", {"file_path": os.path.join(self.a, cp.PROFILE_NAME)}, "PostToolUse")),
            ("session_brief.py", {"hook_event_name": "SessionStart", "session_id": self.session,
                                  "session_mode": "startup"}),
        ]
        for script, payload in cases:
            self.assertIsInstance(self._run(script, payload), dict, script)

    def test_no_python_fallback_is_valid_json(self):
        patched = os.path.join(self.tmp, "run.sh")
        with open(os.path.join(HOOKS, "run.sh"), encoding="utf-8") as fh:
            body = fh.read()
        body = body.replace("/usr/bin/python3 /usr/local/bin/python3 /opt/homebrew/bin/python3",
                            "/nonexistent/a /nonexistent/b")
        with open(patched, "w", encoding="utf-8") as fh:
            fh.write(body)
        env = dict(os.environ, PATH="/nonexistent")
        proc = subprocess.run(["/bin/sh", patched, "path_guard.py"], input="{}",
                              capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny")

    def test_session_brief_mentions_pin(self):
        from state import State
        self.pin_a()
        brief = session_brief.build_brief(State(self.session))
        self.assertIn("ตัวอย่างเทรดดิ้ง", brief)
        self.assertIn(version.header_line(), brief)


class TestLibSync(unittest.TestCase):
    """lib/ ถูกก็อป 3 ชุดเพราะ plugin อ้างไฟล์ข้ามกันไม่ได้ — drift ต้องเป็นเทสต์แดง"""

    SHARED = ("hookio.py", "state.py", "clientpath.py", "taxid.py", "version.py", "audit.py")

    def test_shared_lib_identical_across_plugins(self):
        plugins = [os.path.join(REPO, "plugins", name, "hooks", "lib") for name in (
            "accounting-office-core", "accounting-office-flowaccount", "accounting-office-peak")]
        available = [p for p in plugins if os.path.isdir(p)]
        if len(available) < 2:
            self.skipTest("ยังมี lib ชุดเดียว")
        for name in self.SHARED:
            digests = {}
            for lib in available:
                path = os.path.join(lib, name)
                if not os.path.isfile(path):
                    continue
                with open(path, "rb") as fh:
                    digests[lib] = hashlib.sha256(fh.read()).hexdigest()
            self.assertLessEqual(len(set(digests.values())), 1,
                                 "%s ไม่ตรงกัน — รัน scripts/sync_hooks_lib.py" % name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
