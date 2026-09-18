# Prompt สำหรับสร้าง skill — สำหรับผู้เรียน

โฟลเดอร์นี้ **ไม่ใช่ส่วนหนึ่งของ plugin** และไม่ถูกโหลดเข้า context เวลาใช้งานจริง
มันคือ "แม่พิมพ์" — prompt ที่ใช้ **สร้าง skill แต่ละตัวในโฟลเดอร์ `plugins/*/skills/` ขึ้นมาใหม่**
เพื่อให้ผู้เรียนได้ลองปรับ prompt แล้วดูว่า skill ที่ออกมาเปลี่ยนไปอย่างไร

โครงโฟลเดอร์ **สะท้อน `plugins/`** — prompt ของ skill ตัวไหน อยู่ในโฟลเดอร์ชื่อเดียวกับ plugin ที่มันสังกัด

```
prompts/
├── accounting-office-core/          6 prompt
├── accounting-office-flowaccount/   2 prompt
└── accounting-office-peak/          2 prompt
```

---

## prompt ทั้งหมด

### [`accounting-office-core/`](accounting-office-core/)

| Prompt | สร้าง skill | จุดที่ฝึกใน prompt ตัวนี้ |
|---|---|---|
| [`bank-reconcile.md`](accounting-office-core/bank-reconcile.md) | `bank-reconcile` | ลำดับการจับคู่ และเกณฑ์ที่หลวม-แน่นแลกกับ false positive |
| [`ocr-review.md`](accounting-office-core/ocr-review.md) | `ocr-review` | เลือกว่ากฎไหนคุ้มที่จะตรวจ และกฎไหนควรเป็น "ต้องดู" ไม่ใช่ "ต้องแก้" |
| [`vouch-expense.md`](accounting-office-core/vouch-expense.md) | `vouch-expense` | ทิศทางของงาน (vouching ไม่ใช่ tracing) และการแมปผลเข้า audit assertion |
| [`wht-prep.md`](accounting-office-core/wht-prep.md) | `wht-prep` | ผลลัพธ์ที่ต้องตรงรูปแบบปลายทางเป๊ะ ๆ และการแยกกฎรูปแบบไปไว้ใน references |
| [`close-report.md`](accounting-office-core/close-report.md) | `close-report` | แยก "ยังไม่ได้ทำ" ออกจาก "ทำแล้วผ่าน" |
| [`token-meter.md`](accounting-office-core/token-meter.md) | `token-meter` | อะไรควรเป็นโค้ด อะไรควรเป็นคำสั่งใน SKILL.md |

### [`accounting-office-flowaccount/`](accounting-office-flowaccount/) และ [`accounting-office-peak/`](accounting-office-peak/)

| Prompt | สร้าง skill | จุดที่ฝึกใน prompt ตัวนี้ |
|---|---|---|
| [`flowaccount-posting.md`](accounting-office-flowaccount/flowaccount-posting.md) | `flowaccount-posting` | เขียน skill ที่ทำสิ่งที่ย้อนกลับยากให้ปลอดภัย |
| [`peak-posting.md`](accounting-office-peak/peak-posting.md) | `peak-posting` | เขียน skill สำหรับ ERP ที่ยังไม่ยืนยันชื่อ tool และรูป payload |
| [`flowaccount-dashboard.md`](accounting-office-flowaccount/flowaccount-dashboard.md) | `flowaccount-dashboard` | สัญญาระหว่าง skill กับสคริปต์ และกฎ "ดึงไม่ได้ ห้ามกลายเป็น 0" |
| [`peak-dashboard.md`](accounting-office-peak/peak-dashboard.md) | `peak-dashboard` | เขียน skill ให้ทำงานกับระบบที่ยังไม่รู้ว่ามี tool อะไรให้ใช้ |

ตารางนี้มี **คู่เทียบสองคู่** — งานเหมือนกันแต่ต่าง ERP และ
**ไม่ควรเขียนเป็น skill ตัวเดียวกัน** เหตุผลอยู่ในตารางจุดต่างที่หัวไฟล์ของฝั่ง PEAK
(`peak-posting.md` สำหรับคู่บันทึกข้อมูล · `peak-dashboard.md` สำหรับคู่ออกรายงาน)

> คำสั่ง `/new-client` และ `/switch-client` ไม่มี prompt ในโฟลเดอร์นี้
> เพราะเป็น command ที่ไม่มี skill อยู่ข้างหลัง

> prompt ของ skill ที่ออกไฟล์ Excel สองตัว (`*-dashboard`) มีส่วนที่ 7 เพิ่มจากโครงมาตรฐาน:
> **สัญญาของไฟล์ข้อมูลกลาง** (data pack JSON) เพราะ skill กับสคริปต์ต้องตกลงรูปข้อมูลกันก่อน
> และทั้งสองตัวสั่งให้ **รันสคริปต์กับข้อมูลตัวอย่างจริง** ก่อนถือว่าเสร็จ —
> ไม่ใช่เขียนไฟล์ทิ้งไว้แล้วบอกว่าเสร็จ

---

## วิธีใช้

1. เปิดไฟล์ prompt ของ skill ที่อยากสร้าง
2. แก้ค่าในบล็อก **ค่าตั้งของงานนี้** ให้ตรงกับงานของตัวเอง (นี่คือจุดที่ต้องลองปรับ)
3. ก็อป prompt ทั้งบล็อกไปวางใน Claude Code ที่เปิดอยู่ใน repo นี้ — หรือใน repo เปล่าถ้าอยากสร้างของตัวเอง
4. เทียบผลที่ได้กับ SKILL.md ตัวจริงในโฟลเดอร์ `plugins/`
5. ลองแบบฝึกหัดท้ายไฟล์ทีละข้อ แล้วดูว่า skill เปลี่ยนไปอย่างไร
6. ถ้าอยากวัดคุณภาพเป็นคะแนน ใช้ skill `skill-evaluator` กับไฟล์ที่ได้

**ลำดับที่แนะนำสำหรับผู้เริ่มต้น:** `bank-reconcile` → `ocr-review` → `vouch-expense`
→ `close-report` → `wht-prep` → `flowaccount-posting` → `peak-posting` → `token-meter`
→ `flowaccount-dashboard` → `peak-dashboard`

ห้าตัวแรกเป็นงานอ่านไฟล์แล้วออกไฟล์ (พลาดแล้วแก้ได้) · สองตัว `*-posting`
เป็นงานเขียนข้อมูลออกข้างนอก (พลาดแล้วแก้ยาก) · `token-meter` เป็น skill ที่มีโค้ดประกอบ ·
สองตัว `*-dashboard` เป็นตัวที่ยากที่สุด เพราะรวมทั้งการอ่านจากระบบภายนอก
การเขียนสคริปต์ และสัญญาระหว่างสองฝั่ง

---

## โครงของ prompt ทุกตัวในโฟลเดอร์นี้

ทุกไฟล์ใช้โครงเดียวกัน 6 ส่วน — ถ้าจะเขียน prompt ของ skill ตัวใหม่เอง ให้ลอกโครงนี้

| ส่วน | ทำหน้าที่อะไร | ถ้าขาดจะเกิดอะไร |
|---|---|---|
| **1. ค่าตั้งของงานนี้** | ตัวแปรที่ผู้เรียนกรอก (tolerance, อัตราภาษี, สี, path) | Claude เดาค่าให้ แล้วได้ skill ที่ตัวเลขไม่ตรงงานจริง |
| **2. บทบาทและสิ่งที่ต้องส่งมอบ** | บอกว่าจะได้ไฟล์อะไร ที่ path ไหน รูปแบบไหน | ได้คำอธิบายในแชตแทนไฟล์ |
| **3. ความรู้โดเมนที่ต้องฝังใน skill** | ตรรกะทางบัญชีที่ต้องเขียนลงไป — เป็นส่วนที่ยาวที่สุด | ได้ skill ที่ "ดูดี" แต่ไม่รู้กฎบัญชีไทย |
| **4. ข้อกำหนดผลลัพธ์** | หน้าตาไฟล์ที่ skill ต้องผลิต (sheet, column, สี) | ผลลัพธ์ต่างกันทุกครั้งที่รัน |
| **5. กฎห้าม** | ขอบเขตที่ห้ามข้าม — ห้ามเดา ห้ามทำให้ตัวเลขลงตัวเอง | skill เติมค่าให้ดูสมบูรณ์ ซึ่งอันตรายที่สุดในงานบัญชี |
| **6. เกณฑ์ตรวจรับ** | checklist ที่ Claude ต้องเดินก่อนบอกว่าเสร็จ | ได้ SKILL.md ที่ขาดหัวข้อสำคัญโดยไม่มีใครรู้ |

ส่วนที่ผู้เรียนควรใช้เวลากับมันมากที่สุดคือ **3 และ 5** — ไม่ใช่ 2
ความแม่นของ skill มาจากความรู้โดเมนที่ฝังไว้และขอบเขตที่ห้ามข้าม ไม่ใช่จากการสั่งให้ "ทำให้ดี"

ทุกไฟล์ปิดท้ายด้วย **แบบฝึกหัดปรับแต่ง** (แก้ค่าไหน → ควรเห็นอะไร → บทเรียน)
และ **กรณีทดสอบ** พร้อมคำตอบที่ถูก ใช้ตรวจว่า skill ที่ได้ใช้งานได้จริงหรือแค่ดูดี

---

## ข้อควรรู้

- prompt ในโฟลเดอร์นี้สร้าง **skill เปล่าที่ทำงานได้เอง** — ยังไม่ผูกกับ hook ของ plugin
  ทุกไฟล์ที่แตะโฟลเดอร์ลูกค้ามีค่าตั้ง `โหมดกฎบังคับ` ไว้ให้เปิดเมื่อต้องการให้ skill อ้างกฎ hook
  (`token-meter` ไม่มี เพราะไม่แตะโฟลเดอร์ลูกค้าและไม่เขียนอะไรเข้า ERP)
  และถ้าจะให้เหมือนตัวจริง ต้องวางไฟล์ไว้ใน `plugins/<plugin>/skills/<ชื่อ>/`
- ผลที่ได้จะไม่ตรงกับ SKILL.md ตัวจริงแบบคำต่อคำ และไม่ต้องให้ตรง
  สิ่งที่ต้องตรงคือ **ตรรกะการทำงาน ตัวเลขเกณฑ์ และกฎห้าม**
- อย่าใส่ข้อมูลลูกค้าจริงลงใน prompt ตอนฝึก — ใช้ตัวเลขสมมติ (PDPA)
- prompt บางตัวมีค่าตั้งที่ "ผิดในเชิงโดเมน" ให้ลองกรอกดู (เช่น รวม ภ.ง.ด.3 กับ 53 ไว้ไฟล์เดียว)
  สิ่งที่ถูกคือ Claude **ปฏิเสธและอธิบาย** ไม่ใช่ทำตาม — ใช้ข้อนี้ทดสอบ prompt ของตัวเองได้
