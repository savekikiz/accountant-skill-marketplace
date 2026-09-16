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

### `accounting-office-flowaccount`
| คำสั่ง | ทำอะไร |
|---|---|
| `/post-expense-flowaccount` | บันทึกค่าใช้จ่ายที่ตรวจแล้วเข้า FlowAccount (สถานะรออนุมัติ) |

### `accounting-office-peak`
| คำสั่ง | ทำอะไร |
|---|---|
| `/post-expense-peak` | บันทึกค่าใช้จ่ายที่ตรวจแล้วเข้า PEAK (สถานะรออนุมัติ) |

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

Plugin แต่ละตัวอ้างไฟล์ข้ามกันไม่ได้ กฎชุดเดียวกันนี้จึงถูกเขียนซ้ำไว้ต้นทุก skill

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
