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

## กฎบังคับที่มีอยู่ในทุก SKILL.md

Plugin แต่ละตัวอ้างไฟล์ข้ามกันไม่ได้ กฎชุดเดียวกันนี้จึงถูกเขียนซ้ำไว้ต้นทุก skill ที่ทำงานกับข้อมูลลูกค้า
(ยกเว้น `token-meter` ซึ่งไม่แตะโฟลเดอร์ลูกค้าและไม่เขียนเข้า ERP — ใช้เฉพาะข้อ 5 บวกข้อห้ามเปิดเผยเนื้อหา transcript)

1. ทำงานเฉพาะในโฟลเดอร์ลูกค้าที่ผู้ใช้ระบุ ห้ามอ่านหรือเขียนโฟลเดอร์ลูกค้าอื่น
2. อ่าน `client-profile.md` ก่อนเริ่มงานทุกครั้ง
3. ก่อนเขียนข้อมูลเข้า ERP ต้องแสดงชื่อบริษัทและเลขผู้เสียภาษีปลายทาง แล้วเทียบกับ
   `client-profile.md` — ไม่ตรงให้หยุด
4. สร้างเอกสารใน ERP เป็น **สถานะรออนุมัติ** เท่านั้น ห้ามอนุมัติ ห้ามบันทึกรับชำระ ห้าม void
5. ใส่ชื่อ plugin และเลขเวอร์ชันไว้ในหัวทุกไฟล์ที่สร้าง

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
