# สิ่งที่ fixture พิสูจน์ไม่ได้ — ต้องลองกับ Claude Code จริง

ชุดเทสต์อัตโนมัติครอบคลุมตรรกะการตัดสินทั้งหมด แต่มี 5 ข้อที่เป็น **พฤติกรรมของ harness**
ไม่ใช่ของโค้ดเรา จึงต้องลองเองแล้วติ๊กไว้ที่นี่

ติดตั้งก่อน:
```bash
/plugin marketplace add /Users/surapas/Documents/project/bancheetech/accountant-skill-marketplace
/plugin install accounting-office-core@thai-accounting-office
```

---

## ☐ 1. hook ยิงใน subagent ไหม และ `session_id` เดียวกับ agent หลักไหม

**สมมติฐานที่ state design ทั้งหมดยืนอยู่บนนี้** — pin ถูกเก็บต่อ `session_id`
ถ้า subagent ได้ `session_id` คนละตัว มันจะมองไม่เห็น pin ของ agent หลัก แล้วจะโดน deny
ด้วยเหตุผล "ยังไม่ได้ pin" ทั้งที่ pin อยู่

วิธีลอง: ให้ agent หลัก pin ลูกค้าแล้วเรียก `maker-checker-reviewer` ให้อ่านไฟล์ใน `output/`
จากนั้นเปิด `${CLAUDE_PLUGIN_DATA}/audit/<วันนี้>.jsonl`

- ถ้าเจอบรรทัดที่ `agent` ไม่เป็น null และ `session` เป็นตัวเดียวกับ agent หลัก → ผ่าน
- ถ้า `session` ต่างกัน → ต้องแก้ `lib/state.py` ให้ fallback ไปอ่าน pin จาก session ของ parent
  (เพิ่ม `latest.json` ที่ชี้ session ล่าสุด แล้วให้ `State.pin()` ถอยไปใช้เมื่อ session ตัวเองไม่มี pin)

## ☐ 2. Grep / Glob เคารพ `.gitignore` ไหม

`ลูกค้า/` อยู่ใน `.gitignore` ถ้า Grep/Glob เคารพ gitignore โดยปริยาย ไฟล์ลูกค้าจะมองไม่เห็น
ตั้งแต่แรก ซึ่งเป็นชั้นป้องกันฟรีที่เสริม `path_guard`

วิธีลอง: ในเซสชันที่ยังไม่ pin ให้ค้น `Grep` หาคำที่มีเฉพาะในไฟล์ลูกค้า จาก root ของโปรเจกต์

- ไม่เจอ → ดี (มีชั้นป้องกันเพิ่ม)
- เจอ → ยังปลอดภัย เพราะ `path_guard` deny อยู่แล้ว แต่ให้บันทึกไว้ว่าเป็นช่องที่ต้องระวังตอนขยาย

## ☐ 3. `updatedInput` บน `Write` ทำงานถูกกับเนื้อหาภาษาไทยไหม

`path_guard` เติมหัวไฟล์ให้อัตโนมัติผ่าน `updatedInput` (กฎบังคับข้อ 5)

วิธีลอง: pin ลูกค้าแล้วสั่งให้เขียนไฟล์ `.md` ภาษาไทยลง `<งวด>/output/` โดยไม่ใส่หัวไฟล์

- ไฟล์ที่ได้มีหัว `accounting-office-core v1.3.0 — <วันที่ พ.ศ.>` และภาษาไทยไม่เพี้ยน → ผ่าน
- ถ้าหัวไม่ถูกเติม → `updatedInput` ไม่ถูกนำไปใช้กับ tool นี้ ให้ถอยไปใช้ `post_check.py`
  เตือนแทน (โค้ดตรวจหัวไฟล์มีอยู่แล้วใน `post_check.py`)

## ☐ 4. marketplace install รักษา executable bit ของ `run.sh` ไหม

`hooks.json` เรียก `run.sh` โดยตรง ถ้า bit หายหลังติดตั้ง hook จะไม่ทำงานเลย —
และนั่นแปลว่า **ด่านถูกปลดเงียบ ๆ** ซึ่งเป็นสิ่งที่เรากลัวที่สุด

วิธีลอง: หลังติดตั้ง หา path ที่ติดตั้งจริง แล้ว `ls -l */hooks/run.sh`

- มี `x` → ผ่าน
- ไม่มี → เปลี่ยน `hooks.json` ให้เรียก `sh "${CLAUDE_PLUGIN_ROOT}/hooks/run.sh" <script>` แทน

## ☐ 5. `deny` ของ core ชนะ `ask` ของ plugin ERP จริงไหม

hook ของ core และของ ERP ต่าง match `mcp__.*` ทั้งคู่ — ออกแบบไว้ว่า deny ชนะ ask ชนะ allow
แต่ละตัวจึงเขียนให้จบในตัวเองโดยไม่สมมติลำดับ

วิธีลอง: pin ลูกค้า แล้วเรียก tool ของ MCP ที่ไม่ใช่ ERP (เช่น Gmail) — `privacy_guard` ต้อง deny
จากนั้นลอง tool สร้างเอกสารของ ERP ที่ payload ไม่ครบ — ต้องได้ deny ไม่ใช่ ask

- ผลตรงตามนี้ → ผ่าน
- ถ้า ask ชนะ → ต้องย้ายกฎของ `privacy_guard` ที่เกี่ยวกับ `mcp__*` ไปรวมใน `erp_guard` ของแต่ละ ERP

---

## ☐ 6. regression: `/token-report` ต้องยังทำงานได้

เทสต์สำคัญที่สุดของชุดนี้ เพราะ `token-meter` อ่าน `~/.claude/projects/**/*.jsonl`
และ `tm_common.py` ยิง POST ไป `api.anthropic.com` ซึ่งเป็นสองอย่างที่ `privacy_guard` กันอยู่

pin ลูกค้าแล้วสั่ง `/token-report skills` — ต้องได้รายงานตามปกติ ไม่มี deny

## ☐ 7. regression: งานลูกค้าปกติครบสาย

`/new-client` ลูกค้าทดลอง → `/review-ocr` → `/vouch-expense` → `/close-report`
ต้องไม่มีขั้นไหนถูกบล็อกโดยไม่จำเป็น ถ้ามี ให้บันทึก rule_id ที่บล็อกไว้แล้วแก้กฎนั้น

---

รันชุดอัตโนมัติทั้งหมดได้ด้วย:
```bash
python3 plugins/accounting-office-core/hooks/session_brief.py --selftest
```
