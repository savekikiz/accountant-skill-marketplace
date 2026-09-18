# Thai Accounting Office Plugins

ชุด plugin สำหรับ **สำนักงานบัญชีไทย** ใช้กับ Claude Code

แยกเป็น **plugin หลัก** ที่ทุกสำนักงานติดตั้งเหมือนกัน กับ **plugin ของแต่ละ ERP**
ที่ติดตั้งเฉพาะเมื่อมีลูกค้าใช้ ERP นั้นจริง — จึงไม่ถูกบังคับให้ล็อกอิน connector ที่ไม่ได้ใช้

| Plugin | ติดตั้งเมื่อไร | ต้องใช้ MCP |
|---|---|---|
| `accounting-office-core` | **ทุกสำนักงาน** | ไม่ต้อง |
| `accounting-office-flowaccount` | มีลูกค้าใช้ FlowAccount | FlowAccount MCP |
| `accounting-office-peak` | มีลูกค้าใช้ PEAK | PEAK MCP |

---

## ติดตั้ง

```bash
/plugin marketplace add <github-user>/thai-accounting-office-plugins
```

```bash
/plugin install accounting-office-core@thai-accounting-office
```

ถ้ามีลูกค้าใช้ FlowAccount หรือ PEAK ค่อยติดตั้งเพิ่มทีหลัง

```bash
/plugin install accounting-office-flowaccount@thai-accounting-office
```

```bash
/plugin install accounting-office-peak@thai-accounting-office
```

> ⚠️ **ก่อนใช้ plugin ของ ERP ต้องตรวจ URL ของ MCP server ใน `.mcp.json` ของ plugin นั้นก่อน**
> URL ที่ใส่ไว้เป็นค่าตั้งต้น ยังไม่ได้ทดสอบกับ endpoint จริง
> ถ้าผู้ให้บริการใช้ URL อื่น ให้แก้ก่อนติดตั้ง มิฉะนั้นจะเชื่อมต่อไม่ได้
>
> `accounting-office-core` ใช้ได้เลยโดยไม่ต้องตั้งค่าอะไร

---

## คำสั่งที่ได้

### `accounting-office-core`

| คำสั่ง | ทำอะไร |
|---|---|
| `/new-client` | สร้างโฟลเดอร์ลูกค้ารายใหม่ตามมาตรฐาน พร้อม `client-profile.md` |
| `/review-ocr` | ตรวจผล OCR → `exceptions.xlsx` เฉพาะรายการที่ต้องแก้มือ |
| `/vouch-expense` | เทียบรายการค่าใช้จ่ายกับเอกสารต้นฉบับ |
| `/bank-reconcile` | กระทบยอด GL เงินฝากกับ Bank Statement |
| `/wht-prep` | เตรียมข้อมูล ภ.ง.ด.3 / ภ.ง.ด.53 |
| `/close-report` | สรุปสถานะปิดงวด + ร่างอีเมลขอเอกสาร |
| `/token-report` | รายงานการใช้ token และต้นทุน (USD/บาท) ของงานที่ทำไป |
| `/switch-client` | ปลด pin ลูกค้าปัจจุบัน เพื่อเปลี่ยนรายโดยไม่ต้อง `/clear` |

### `accounting-office-flowaccount`
| คำสั่ง | ทำอะไร |
|---|---|
| `/post-expense-flowaccount` | บันทึกค่าใช้จ่ายที่ตรวจแล้วเข้า FlowAccount (สถานะรออนุมัติ) |

### `accounting-office-peak`
| คำสั่ง | ทำอะไร |
|---|---|
| `/post-expense-peak` | บันทึกค่าใช้จ่ายที่ตรวจแล้วเข้า PEAK (สถานะรออนุมัติ) |

---

## Subagent ที่มาด้วย

Subagent ทำงานในหน้าต่าง context ของตัวเอง แล้วส่งกลับมาแค่ข้อสรุป
ประโยชน์คือ **กันงานที่กิน context** และ **จำกัดสิทธิ์ให้แคบกว่า agent หลัก**

| Subagent | อยู่ใน plugin | สิทธิ์ | ทำอะไร |
|---|---|---|---|
| `maker-checker-reviewer` | core | อ่านไฟล์ (`Read`, `Glob`, `Grep`) | ตรวจตาราง preview ก่อนบันทึกเข้า ERP และตรวจรายงานปิดงวด โดยเทียบกับเอกสารต้นทางเอง |
| `tax-compliance-checker` | core | อ่านไฟล์ (`Read`, `Glob`, `Grep`) | ไล่หาจุดเสี่ยงภาษี 4 กลุ่ม: ควรหัก ณ ที่จ่ายแต่ไม่ได้หัก, ใบกำกับอย่างย่อ, รายจ่ายต้องห้าม, ทรัพย์สินที่ลงเป็นค่าใช้จ่าย |
| `flowaccount-lookup` | flowaccount | **tool อ่านของ FlowAccount เท่านั้น** | ค้นเอกสารซ้ำ ค้น vendor ดึงยอดเจ้าหนี้/สมุดรายวัน |
| `peak-lookup` | peak | **tool อ่านของ PEAK เท่านั้น** | ค้นเอกสารซ้ำ ค้นคู่ค้า ดึงผังบัญชี/ยอด |

### ทำไม lookup ถึงแยกเป็นสองตัวแทนที่จะเป็น `erp-lookup` ตัวเดียว

การจำกัดสิทธิ์ให้เหลือ "อ่านอย่างเดียว" ต้องระบุชื่อ tool ทีละตัว
ถ้าใช้ `mcp__peak__*` หรือ `mcp__flowaccount__*` แบบเหมารวม **tool ที่เขียนข้อมูลจะติดเข้ามาด้วย**
ซึ่งทำลายเหตุผลทั้งหมดของการมี agent ตัวนี้ — และ allowlist ของสอง ERP ก็คนละชุดกัน
ถ้าใช้ชื่อเดียวกันทั้งสอง plugin สำนักงานที่ติดตั้งครบทั้งคู่จะเจอชื่อชน

### ⚠️ `peak-lookup` ต้องตั้งค่าก่อนใช้ครั้งแรก

ช่อง `tools:` ในไฟล์ agent **ยังว่างไว้โดยตั้งใจ** เพราะชื่อ tool ของ PEAK MCP ยังไม่ได้ยืนยัน
ต้องเชื่อมต่อ MCP ก่อน แล้วเติมเฉพาะ tool ที่อ่านอย่างเดียวลงไป — ขั้นตอนอยู่ในหัวไฟล์
[`plugins/accounting-office-peak/agents/peak-lookup.md`](plugins/accounting-office-peak/agents/peak-lookup.md)

ระหว่างที่ยังไม่ได้ตั้งค่า agent จะรายงานว่า **"ยังตั้งค่าไม่เสร็จ"** — ไม่ใช่ "ไม่พบข้อมูล"
ความต่างนี้สำคัญ เพราะการสับสนสองอย่างนี้ทำให้เกิดเอกสารซ้ำใน ERP

### กฎการใช้ maker-checker-reviewer

ส่งให้แค่ **path ของตาราง/รายงาน และ path ของเอกสารต้นทาง**
**ห้ามส่งเหตุผลว่าทำไมถึงกรอกแบบนั้นไปด้วย** — ผู้ตรวจที่รู้เหตุผลของผู้ทำ จะเห็นด้วยโดยอัตโนมัติ
และการตรวจจะไม่มีประโยชน์ ตัว agent ถูกเขียนให้ละเว้นข้อความแบบนั้นถ้าหลุดไป แล้วรายงานว่าได้รับมา

---

## วัดต้นทุน token — `/token-report`

skill `token-meter` อยู่ใน `accounting-office-core` จึงใช้ได้จากทุก plugin ในชุดนี้
(ไม่ต้องติดตั้งเพิ่ม และไม่ถูกก็อปซ้ำใน flowaccount/peak เพื่อไม่ให้กิน context ซ้ำซ้อน)

| อยากรู้ | ทำอะไร |
|---|---|
| งวดนี้ทำงานลูกค้าไปแล้วกิน token/เงินเท่าไร | `/token-report session` |
| skill ตัวไหนในชุดนี้กิน context เยอะ | `/token-report skills` |
| `CLAUDE.md` / system prompt ที่เขียนไว้ยาวกี่ token | `/token-report prompt <ไฟล์>` |

ตัวเลข `session` อ่านจาก transcript จริงของ Claude Code จึงตรงตาม API
ส่วน `skills` / `prompt` เป็น **ค่าประมาณ ±30%** ถ้าไม่ได้ตั้ง `ANTHROPIC_API_KEY`

> ตัวเลข USD คือราคาเทียบ API ไว้ดู "ขนาดงาน" — ผู้ใช้แพ็กเกจ Pro/Max ไม่ได้จ่ายตามนี้
> ก่อนเอาไปตั้งราคาลูกค้า ให้ตรวจ `skills/token-meter/references/pricing.json`
> เทียบกับ https://docs.claude.com/en/docs/about-claude/pricing ก่อน

---

## ลำดับงานที่ออกแบบไว้

```
/new-client        ครั้งเดียวต่อลูกค้า
      ↓
/review-ocr        ตรวจข้อมูลที่อ่านจากเอกสาร
      ↓
/vouch-expense     ยืนยันว่ามีเอกสารรองรับจริง
      ↓
/post-expense-*    บันทึกเข้า ERP (เฉพาะรายการที่ผ่านแล้ว)
      ↓
/bank-reconcile    กระทบยอดธนาคาร
      ↓
/wht-prep          เตรียมยื่น ภ.ง.ด.
      ↓
/close-report      สรุปปิดงวด + ร่างอีเมลขอเอกสารที่ขาด
```

`/token-report` ใช้ได้ทุกเมื่อ ไม่อยู่ในลำดับนี้ — เป็นงานวัดผล ไม่ใช่งานบัญชี

ข้ามขั้นได้ถ้างานนั้นไม่มี แต่ `/post-expense-*` **ควรทำหลัง** `/vouch-expense` เสมอ

---

## โฟลเดอร์ลูกค้าในเครื่องสำนักงาน

สร้างด้วย `/new-client` — อยู่ **นอก plugin** จึงไม่ถูกเขียนทับเมื่ออัปเดต

```
ลูกค้า/
└── <ชื่อลูกค้า>/
    ├── client-profile.md      ชื่อบริษัท เลขผู้เสียภาษี ERP ที่ใช้ รอบบัญชี
    ├── chart-of-accounts.xlsx (ผู้ใช้วางเอง)
    ├── mapping-overrides.md   ข้อยกเว้นเฉพาะลูกค้ารายนี้
    └── 2569-09/
        ├── ocr-output/        ผล OCR ดิบ
        ├── source-docs/       ภาพ/PDF เอกสารต้นฉบับ
        ├── bank/              statement และ GL เงินฝาก
        └── output/            ไฟล์ผลลัพธ์ที่ skill สร้าง
```

`mapping-overrides.md` **ชนะกฎ default ใน skill เสมอ** — ใช้บันทึกข้อตกลงเฉพาะลูกค้า

---

## ด่านตรวจอัตโนมัติ (hooks)

ก่อนเวอร์ชัน 1.3.0 กฎทุกข้อเป็นแค่ข้อความสั่งใน markdown — ถ้าโมเดลพลาด กฎก็ไม่ทำงาน
ตอนนี้กฎที่เครื่องตรวจได้ถูกย้ายไปเป็น **hook ระดับ plugin** ที่รันโค้ดจริงก่อน/หลังทุก tool call

| กฎ | บังคับที่ชั้นไหน | ทำผิดแล้วเกิดอะไร |
|---|---|---|
| ทำงานได้ทีละลูกค้า (pin ต่อ session) | hook `path_guard` | ปฏิเสธ tool call |
| ต้องอ่าน `client-profile.md` ก่อนแตะโฟลเดอร์ลูกค้า | hook `path_guard` | ปฏิเสธ tool call |
| เขียนได้เฉพาะ `<งวด>/output/` | hook `path_guard` | ปฏิเสธ tool call |
| ห้ามเขียนทับ `client-profile.md` / `mapping-overrides.md`, ห้ามสร้าง `chart-of-accounts.xlsx` | hook `path_guard` | ปฏิเสธ tool call |
| หัวไฟล์ plugin + เวอร์ชัน | hook `path_guard` | **เติมให้อัตโนมัติ** |
| ห้ามอ่านไฟล์ transcript เข้า context | hook `privacy_guard` | ปฏิเสธ tool call |
| ขณะทำงานลูกค้า: ห้ามต่อเน็ต / ใช้ MCP ที่ไม่ใช่ ERP / ส่งอีเมล | hook `privacy_guard` | ปฏิเสธ tool call |
| ERP: ห้ามอนุมัติ / void / ลบ / จ่ายชำระ / ส่งอีเมล / เอกสารฝั่งขาย | hook `erp_guard` | ปฏิเสธ tool call |
| ERP: เลขผู้เสียภาษีปลายทางต้องตรงกับโปรไฟล์ | hook `erp_guard` | ปฏิเสธ tool call |
| ERP: payload ครบถ้วน + กันเอกสารซ้ำ | hook `erp_guard` | ปฏิเสธ tool call |
| ERP: ยืนยันก่อนสร้างเอกสาร | hook `erp_guard` | ถามใบแรกของกอง (PEAK ถามทุกใบ) |
| ตรวจไฟล์ผลลัพธ์ (checksum, ข้อสรุปขัดกันเอง, หัวไฟล์) | hook `post_check` | เตือน ไม่บล็อก |
| ห้ามเดา / ต้อง preview ให้ครบ / ค้นคู่ค้าให้ครบก่อนสร้างใหม่ | SKILL.md | ต้องใช้วิจารณญาณ — ตรวจแทนไม่ได้ |

โค้ดอยู่ที่ `plugins/<plugin>/hooks/` เป็น Python 3 stdlib ล้วน ไม่มี dependency

### เปลี่ยนลูกค้าระหว่างทาง

pin ผูกกับ session วิธีปกติคือ **`/clear`** แล้วเริ่มใหม่
ถ้ายังอยากเก็บบริบทไว้ ใช้ `/switch-client` ซึ่งจะขึ้นกล่องให้กดยืนยัน — **การกดนั้นคือตัวด่าน**

> ⚠️ **อย่าใส่ `/switch-client` (หรือ `pin_ctl.py`) ลงใน permissions allowlist**
> ถ้า allowlist ไว้ กฎ "ทำงานได้ทีละลูกค้า" จะไม่เหลืออะไรเลย

### ถ้าเครื่องไม่มี python3

`hooks.json` เรียกผ่าน `run.sh` ซึ่งจะพ่นข้อความ **deny** ที่อ่านออกแทนการเงียบ ๆ ปล่อยผ่าน
(hook ที่พังแบบ exit code ผิด จะถูกถือเป็น non-blocking error แล้ว tool จะทำงานต่อ = ด่านถูกปลดโดยไม่มีใครรู้)

ตรวจว่า hook ทำงานจริงในเครื่องนี้:
```bash
python3 plugins/accounting-office-core/hooks/session_brief.py --selftest
```

### ข้อจำกัดที่ต้องรู้ — เขียนไว้ตรง ๆ

1. **Bash เป็นช่องที่ path guard ข้ามได้** — การแกะ path ออกจาก shell string เป็นงานที่ชนะไม่ได้
   (quoting, `$VAR`, command substitution, heredoc) และ parser ครึ่ง ๆ กลาง ๆ อันตรายกว่าไม่มี
   เพราะให้ความรู้สึกว่าครอบคลุม hook จึงตรวจ Bash แค่ 3 อย่าง: ปล่อยสคริปต์ของ plugin,
   บล็อกคำสั่งส่งข้อมูลออกนอกเครื่อง, บล็อกคำสั่งทำลายไฟล์ที่ป้องกันไว้
   **ใครอยากได้เส้นแข็งกว่านี้ ให้ใส่ `permissions.deny` ใน `settings.json`** ซึ่งเป็นคนละชั้น
2. **hook กันความผิดพลาดของโมเดลและ prompt injection จากเอกสาร OCR — ไม่ได้กันผู้ใช้ที่ตั้งใจหลบ**
   ผู้ใช้ที่ปิด plugin หรือ allowlist คำสั่งไว้ ย่อมข้ามได้ทั้งหมด และนั่นถูกต้องแล้ว
3. **ด่านของ PEAK ทำงานแบบ learn-mode** — ชื่อ tool และรูป payload ของ PEAK ยังไม่ได้ยืนยัน
   กับ endpoint จริง จึงตรวจโครงสร้าง payload ไม่ได้ และถามผู้ใช้ทุกใบ
   `hooks/erp_post.py` บันทึกชื่อ tool ที่เจอจริงลง `${CLAUDE_PLUGIN_DATA}/observed-tools.json`
   ให้ก็อปไปเติม `hooks/peak-tools.json` และ `tools:` ของ `agents/peak-lookup.md`
4. **state ของ session อยู่ที่ `~/.accounting-office/`** (เปลี่ยนได้ด้วย `ACCOUNTING_OFFICE_STATE`)
   ไม่ได้อยู่ในโฟลเดอร์ลูกค้า เพราะโฟลเดอร์นั้นถูกซิปส่งให้ลูกค้า — session ที่เก่ากว่า 7 วันถูกลบอัตโนมัติ
   audit log อยู่ที่ `${CLAUDE_PLUGIN_DATA}/audit/` และเก็บแค่ชื่อโฟลเดอร์ลูกค้า ไม่เก็บชื่อผู้ขายหรือยอดเงิน

### แก้โค้ด hook

`hooks/lib/` ที่ใช้ร่วมกันถูกก็อป 3 ชุด เพราะ plugin อ้างไฟล์ข้ามกันไม่ได้
แก้ที่ `accounting-office-core` แล้วรัน:

```bash
python3 scripts/sync_hooks_lib.py                                  # ซิงก์
python3 plugins/accounting-office-core/hooks/tests/run_tests.py
python3 plugins/accounting-office-flowaccount/hooks/tests/run_tests.py
python3 plugins/accounting-office-peak/hooks/tests/run_tests.py
```

เทสต์ของ core จะ assert SHA-256 ของทุกสำเนา — drift จึงกลายเป็นเทสต์แดง ไม่ใช่บั๊กลึกลับ
สิ่งที่ fixture พิสูจน์ไม่ได้อยู่ใน `plugins/accounting-office-core/hooks/tests/MANUAL.md`

---

## สิ่งที่ plugin ชุดนี้ **ไม่** ทำให้

- ไม่ยื่นแบบภาษีให้ และไม่เชื่อมต่อ e-Filing
- ไม่อนุมัติเอกสารใน ERP ไม่บันทึกการจ่ายชำระ ไม่ยกเลิกเอกสาร
- ไม่ส่งอีเมล (สร้างเป็นไฟล์ร่างให้ผู้ใช้ตรวจและกดส่งเอง)
- ไม่ตัดสินว่ารายจ่ายเป็นรายจ่ายต้องห้ามตามมาตรา 65 ตรี
- ไม่ตรวจจับการทุจริต และไม่ตรวจว่าเอกสารเป็นของแท้
- ไม่ปิดงบการเงิน ไม่คำนวณค่าเสื่อมราคา ไม่บันทึกรายการปรับปรุงปิดงวด

**ผลลัพธ์ทุกอย่างต้องถูกตรวจทานโดยผู้ทำบัญชีก่อนนำไปใช้**
plugin ชุดนี้เป็นเครื่องมือช่วยทำงาน ไม่ใช่ผู้รับผิดชอบความถูกต้อง

---

## ข้อมูลอ้างอิงทางภาษี

ข้อมูลกฎหมายและอัตราภาษีในชุดนี้ตรวจสอบล่าสุดเมื่อ **2026-09-16** สำหรับปีภาษี **2569**

อัตรา VAT 7% มาจากพระราชกฤษฎีกาที่ต่ออายุเป็นรายปี และคำสั่งกรมสรรพากรที่ ท.ป.4/2528
มีการแก้ไขเพิ่มเติมเป็นระยะ — **ก่อนใช้กับปีภาษีอื่น ให้ตรวจที่ [rd.go.th](https://www.rd.go.th) เสมอ**

---

## PDPA

เอกสารที่ประมวลผลมีเลขประจำตัวผู้เสียภาษี ชื่อ-ที่อยู่ และรายการเดินบัญชีธนาคาร
ซึ่งเป็นข้อมูลส่วนบุคคลและข้อมูลอ่อนไหว

- `accounting-office-core` ทำงาน **บนเครื่องสำนักงานเท่านั้น** ไม่ส่งข้อมูลออกภายนอก
- `accounting-office-flowaccount` และ `accounting-office-peak` **ส่งข้อมูลออกไปยังระบบ ERP ผ่าน MCP**
  — สำนักงานรับผิดชอบการขอความยินยอมและการจัดการสิทธิ์เข้าถึงบัญชีลูกค้าเอง

---

## ประวัติเวอร์ชัน

### 1.3.0 — 2026-09-18
- **เพิ่มชั้น hooks ให้ทั้ง 3 plugin** — กฎที่เครื่องตรวจได้ย้ายจากข้อความใน markdown
  มาเป็นโค้ดที่บล็อก tool call ได้จริง (ดูหัวข้อ "ด่านตรวจอัตโนมัติ")
  - core: `path_guard`, `privacy_guard`, `post_check`, `session_brief`
  - flowaccount / peak: `erp_guard`, `erp_post`
- เพิ่มคำสั่ง `/switch-client` สำหรับเปลี่ยนลูกค้าโดยไม่ต้อง `/clear`
- **ย่อบล็อกกฎบังคับใน SKILL.md ทั้ง 7 ไฟล์** เหลือตารางที่แยกชัดว่าข้อไหน hook บังคับ
  ข้อไหนต้องใช้วิจารณญาณ — L2 ของทุก skill สั้นลง
- เลิก hardcode เลขเวอร์ชันใน prose (ค้างที่ `v1.1.0` ขณะที่ manifest เป็น `1.2.0`)
  หัวไฟล์ให้ hook สร้างจาก `plugin.json` แล้วเติมให้เองตอนเขียนลง `output/`
- เพิ่มชุดทดสอบ 114 เคสในทั้ง 3 plugin รวม golden test บนรายชื่อ tool จริงของ FlowAccount
  ทั้งชุด × 2 รูปแบบชื่อ server (`mcp__flowaccount__` และ `mcp__claude_ai_FlowAccount_MCP__`)

### 1.2.0 — 2026-09-18
- เพิ่ม skill `token-meter` + คำสั่ง `/token-report` ใน `accounting-office-core`
  วัด token และต้นทุนได้ 3 มุม: ราย session/turn จาก transcript จริง,
  ขนาด L1/L2/L3 ของแต่ละ skill, และความยาวของไฟล์ prompt/`CLAUDE.md`
- วางไว้ใน core ตัวเดียวแทนที่จะก็อปลงทั้ง 3 plugin — flowaccount/peak ใช้ของ core ได้เลย
  เพราะติดตั้ง core อยู่แล้ว และไม่ทำให้ description ถูกโหลดเข้า context ซ้ำ 3 รอบ

### 1.1.0 — 2026-09-16
- เพิ่ม subagent 4 ตัว
  - core: `maker-checker-reviewer`, `tax-compliance-checker` (สิทธิ์อ่านไฟล์เท่านั้น)
  - flowaccount: `flowaccount-lookup` (tool อ่านของ FlowAccount เท่านั้น)
  - peak: `peak-lookup` (tool อ่านของ PEAK เท่านั้น — ต้องเติมชื่อ tool ก่อนใช้ครั้งแรก)
- ต่อ subagent เข้ากับ skill: `/vouch-expense` เรียกตรวจภาษีได้,
  `/close-report` ให้ตรวจรายงานก่อนส่ง, `/post-expense-*` ตรวจตาราง preview ก่อนบันทึก
- แยก lookup เป็นสองตัวตาม ERP แทน `erp-lookup` ตัวเดียว เพื่อให้ allowlist อ่านอย่างเดียวระบุได้จริง

### 1.0.0 — 2026-09-16
- เวอร์ชันแรก แยกเป็น 3 plugin: core, flowaccount, peak
- `accounting-office-core`: 6 คำสั่ง, 5 skill (`ocr-review`, `vouch-expense`,
  `bank-reconcile`, `wht-prep`, `close-report`)
- `accounting-office-flowaccount`: `/post-expense-flowaccount` + skill `flowaccount-posting`
- `accounting-office-peak`: `/post-expense-peak` + skill `peak-posting`
- กฎบังคับ 5 ข้อฝังไว้ในทุก SKILL.md
- ข้อมูลภาษีอ้างอิงปีภาษี 2569

---

## License

MIT
