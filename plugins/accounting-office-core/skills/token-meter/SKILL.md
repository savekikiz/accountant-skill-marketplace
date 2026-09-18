---
name: token-meter
description: วัดจำนวน token และคิดเป็นราคา (USD/บาท) ของการใช้ Claude — ทั้ง session ของ Claude Code, แต่ละ turn, แต่ละ skill ที่ถูกเรียก, ขนาด SKILL.md/description ของ skill, และไฟล์ prompt/system prompt/CLAUDE.md/memory ใช้ skill นี้ทุกครั้งที่ผู้ใช้ถามว่า "กิน token เท่าไหร่", "ใช้ไปกี่บาท/กี่ดอลลาร์", "skill นี้แพงไหม", "context เต็มเพราะอะไร", "นับ token", "token usage", "cost report", "ค่าใช้จ่าย Claude Code", "เทียบต้นทุน skill", "system prompt ยาวเกินไหม" หรืออยากเห็นรายงานการใช้ token เป็น Excel แม้ไม่ได้พูดคำว่า token-meter ตรง ๆ
---

# token-meter

วัด token และต้นทุนของการใช้ Claude ได้ 3 มุม ด้วยสคริปต์ใน `scripts/` (Python 3 มาตรฐาน; ใช้ openpyxl เฉพาะตอนออก Excel)

| คำถามของผู้ใช้ | สคริปต์ |
|---|---|
| session นี้/เมื่อวาน/โปรเจกต์นี้ใช้ไปเท่าไร, skill ไหนกินเยอะ | `session_usage.py` |
| skill ตัวนี้ (หรือทั้งโฟลเดอร์) กิน context เท่าไรในแต่ละชั้น | `skill_footprint.py` |
| prompt / system prompt / CLAUDE.md / ไฟล์ memory ยาวกี่ token | `count_prompt.py` |

สคริปต์อยู่ใน plugin นี้ — เรียกด้วย path เต็มเสมอ:
`python3 "${CLAUDE_PLUGIN_ROOT}/skills/token-meter/scripts/<ชื่อสคริปต์>.py"`
(ตัวอย่างข้างล่างย่อเป็น `scripts/...` เพื่อให้อ่านง่าย เวลารันจริงให้เติม `${CLAUDE_PLUGIN_ROOT}/skills/token-meter/` ข้างหน้า)

## 1. การใช้งานจริงจาก transcript — `session_usage.py`

Claude Code เก็บทุก session เป็น JSONL ที่ `~/.claude/projects/<project>/<session-id>.jsonl` (หรือใต้ `$CLAUDE_CONFIG_DIR`) ทุกข้อความของ assistant มี `usage` จริงจาก API สคริปต์จะรวมยอด ตัด entry ซ้ำจาก streaming และคิดราคาจาก `references/pricing.json`

```bash
python3 scripts/session_usage.py                          # session ล่าสุด
python3 scripts/session_usage.py --turns                  # แยกราย turn พร้อมชื่อ skill ที่ถูกเรียก
python3 scripts/session_usage.py --all --since 2026-09-01 --by-skill --fx 32.5 --xlsx token_report.xlsx
python3 scripts/session_usage.py --project neo-corporate --by-skill
python3 scripts/session_usage.py --session <id บางส่วน หรือ path .jsonl>
```

วิธีตีความผลที่ควรอธิบายให้ผู้ใช้:
- **turn** = prompt หนึ่งครั้งของผู้ใช้ + ทุก API call ที่ Claude ทำต่อจนถึง prompt ถัดไป (รวม tool call หลายรอบ)
- **--by-skill** นับ turn ที่มีการเรียก Skill tool หรือ `/slash-command` แล้วยกยอดทั้ง turn ให้ skill นั้น จึงเป็น "ต้นทุนของงานที่ใช้ skill" ไม่ใช่เฉพาะเนื้อหา SKILL.md ถ้าต้องการเฉพาะขนาด skill ให้ใช้ `skill_footprint.py`
- **cache_read** มักเป็นตัวเลขใหญ่ที่สุดแต่ราคาถูก (~10% ของ input) อย่าให้ผู้ใช้ตกใจกับยอด total token
- ผู้ใช้แพ็กเกจ Pro/Max ไม่ได้จ่ายตามนี้ ตัวเลข USD คือราคาเทียบ API ใช้เปรียบเทียบขนาดงาน
- ถ้าหาโฟลเดอร์ไม่เจอ (เช่นรันใน claude.ai ที่ไม่มี transcript) ให้บอกผู้ใช้ตรง ๆ และให้เขาอัปโหลดไฟล์ `.jsonl` มาแล้วใช้ `--path <ไฟล์>`

## 2. ขนาดของ skill — `skill_footprint.py`

skill โหลดเป็น 3 ชั้น ตัวเลขแต่ละชั้นจึงมีความหมายต่างกัน:
- **L1 meta** (name + description) อยู่ใน context ทุก session แม้ไม่เคยเรียกใช้ → skill ยิ่งมากตัว ยิ่งเสียทุกครั้ง
- **L2 SKILL.md body** โหลดเมื่อ skill ถูกเรียก
- **L3** ไฟล์ใน references/ โหลดเมื่อ Claude เปิดอ่าน; scripts/ ที่แค่ "รัน" ไม่กิน context (กินเฉพาะ output ที่พิมพ์ออกมา)

```bash
python3 scripts/skill_footprint.py ~/.claude/skills/wht-extractor --files
python3 scripts/skill_footprint.py ~/.claude/skills --model claude-opus-5 --fx 32.5
```

ถ้ามี `ANTHROPIC_API_KEY` จะนับแบบแม่นยำผ่าน `/v1/messages/count_tokens` ไม่มีก็จะใช้ค่าประมาณ (±30%, ภาษาไทยคลาดเคลื่อนได้มากกว่า) และหัวรายงานจะบอกโหมดเสมอ — ต้องแจ้งผู้ใช้ว่าเป็นค่าประมาณทุกครั้งที่ไม่ได้ใช้ API

คำแนะนำที่ควรให้จากผล: description ยาวเกิน ~150 tokens ให้กระชับ; SKILL.md เกิน ~5,000 tokens ให้ย้ายตาราง/ตัวอย่างยาวไป references/; ข้อมูลที่ใช้คำนวณควรอยู่ในสคริปต์มากกว่าเขียนในเนื้อหา

## 3. prompt และไฟล์ใด ๆ — `count_prompt.py`

```bash
python3 scripts/count_prompt.py CLAUDE.md system_prompt.txt --model claude-sonnet-5
python3 scripts/count_prompt.py --text "ข้อความที่ต้องการนับ" --calls 500 --fx 32.5
```

`--calls` ใช้ประมาณต้นทุนเมื่อ prompt เดิมถูกส่งซ้ำหลายครั้ง (เช่น system prompt ใน n8n workflow ที่รันวันละ 500 รอบ) และคอลัมน์ cached แสดงราคาถ้าเปิด prompt caching

## กฎของ plugin ชุดนี้ที่ใช้กับ skill นี้

skill นี้ไม่แตะโฟลเดอร์ลูกค้าและไม่เขียนอะไรเข้า ERP กฎข้อ 1–4 ของ plugin จึงไม่บังคับใช้ แต่ยังต้องทำตาม:

- **ห้ามแสดงเนื้อหาในไฟล์ transcript** — ไฟล์ `.jsonl` มีบทสนทนางานลูกค้าอยู่ (ชื่อบริษัท เลขผู้เสียภาษี ยอดเงิน)
  รายงานได้เฉพาะ **ตัวเลขการใช้ token** ชื่อ session/skill และช่วงเวลา เท่านั้น
- **ห้ามอัปโหลด `.jsonl` ไปที่ไหน** และห้ามส่งเนื้อหางานลูกค้าเข้า API `count_tokens`
  (สคริปต์ส่งเฉพาะไฟล์ที่ผู้ใช้ชี้ให้นับเท่านั้น ถ้าไฟล์นั้นมีข้อมูลลูกค้า ให้เตือนก่อนรัน)
- **ใส่หัวไฟล์ทุกครั้งที่ออก `.xlsx`** — ระบุ `accounting-office-core` + เลขเวอร์ชัน วันที่ที่ออกรายงาน
  โมเดลที่ใช้คิดราคา อัตราแลกเปลี่ยน และโหมดนับ token (exact / estimate)
- **ห้ามบอกว่าเป็นเงินที่จ่ายจริง** ถ้าผู้ใช้อยู่ในแพ็กเกจ Pro/Max — เป็นราคาเทียบ API เพื่อดูขนาดงาน

## ราคา

`references/pricing.json` เป็นราคาต่อ 1M tokens (อัปเดต ก.ย. 2026) แก้ไขได้เอง key จับคู่แบบ substring ของ model id ถ้ามีโมเดลที่ไม่รู้ราคา รายงานจะเตือนและไม่นับรวม ก่อนนำตัวเลขไปเสนอลูกค้า ให้ผู้ใช้ตรวจราคากับ https://docs.claude.com/en/docs/about-claude/pricing

อัตราแลกเปลี่ยน `--fx` ไม่มีค่าเริ่มต้น ถ้าผู้ใช้อยากเห็นเป็นบาท ให้ถามอัตราที่ต้องการหรือค้นหาอัตราวันนี้แล้วบอกว่าใช้อัตราเท่าไร

## การรายงานผล

สรุปผลเป็นภาษาไทยสั้น ๆ: ยอดรวม, 3 อันดับที่กินมากสุด, และข้อเสนอแนะที่ลดต้นทุนได้จริง (ใช้ `/compact` หรือ `/clear`, ย่อ description, แยก references, ใช้โมเดลที่ถูกกว่าสำหรับงานซ้ำ) แล้วแนบตาราง markdown ที่สคริปต์พิมพ์ออกมา ถ้าผู้ใช้อยู่ใน Claude Code แนะนำ `/context` ควบคู่สำหรับดูสัดส่วน context ขณะนั้น
